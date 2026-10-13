import asyncio
import base64
import logging
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from ringlab.config import Settings
from ringlab.limits import RateLimiter
from ringlab.server import MAX_PREDICT_BYTES, create_app, read_json
from ringlab.workbench import Workbench, model_path


class StubWorkbench:
    artifacts = {1: {}, 2: {}, 3: {}}

    def metadata(self):
        return {"count": 1}

    def predict(self, query):
        return {"predictions": []}

    recognize = predict


class ServiceTests(unittest.TestCase):
    def test_default_capacity_accepts_four_recognition_requests_and_rejects_fifth(self):
        started, release = threading.Event(), threading.Event()
        class Slow(StubWorkbench):
            def recognize(self, query):
                started.set()
                release.wait(3)
                return {"status": "aligned"}
        app = create_app(workbench_factory=Slow)
        async def scenario():
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    requests = [asyncio.create_task(client.post("/api/recognize", json={})) for _ in range(4)]
                    try:
                        self.assertTrue(await asyncio.to_thread(started.wait, 2))
                        for _ in range(100):
                            if app.state.pools["recognize"].pending == 4:
                                break
                            await asyncio.sleep(.005)
                        self.assertEqual(app.state.pools["recognize"].pending, 4)
                        self.assertEqual((await client.post("/api/recognize", json={})).status_code, 503)
                        self.assertEqual((await client.post("/api/predict", json={})).status_code, 200)
                        self.assertEqual((await client.get("/api/health")).status_code, 200)
                    finally:
                        release.set()
                    self.assertEqual([response.status_code for response in await asyncio.gather(*requests)], [200]*4)
        asyncio.run(scenario())

    def test_https_origin_is_explicit_and_does_not_trust_forwarded_headers(self):
        settings = Settings(public_origin="https://rings.example.com")
        with TestClient(create_app(settings, StubWorkbench)) as client:
            valid = {"Origin": settings.public_origin}
            self.assertEqual(client.post("/api/predict", json={}, headers=valid).status_code, 200)
            for origin in ("https://evil.example", "null", "http://rings.example.com", "http://localhost:8765"):
                response = client.post("/api/predict", json={}, headers={"Origin": origin,
                                       "X-Forwarded-Host": "rings.example.com", "X-Forwarded-Proto": "https"})
                self.assertEqual(response.status_code, 403)
            metadata = client.get("/api/meta").json()
            self.assertEqual(metadata["processing"]["mode"], "server")
            self.assertIn("HTTPS", metadata["processing"]["notice"])
            self.assertFalse(metadata["processing"]["images_saved"])
            self.assertEqual(client.get("/api/meta", headers={"Origin": "https://evil.example"}).status_code, 403)

    def test_health_not_ready_before_startup_and_after_shutdown(self):
        app = create_app(workbench_factory=StubWorkbench)
        client = TestClient(app)
        self.assertEqual(client.get("/api/health").status_code, 503)
        with client:
            self.assertEqual(client.get("/api/health").json()["models"], [1, 2, 3])
        self.assertEqual(client.get("/api/health").status_code, 503)

    def test_failed_startup_is_not_reported_as_ready(self):
        def fail():
            raise ValueError("bad model hash")
        app = create_app(workbench_factory=fail)
        with self.assertRaises(ValueError):
            with TestClient(app):
                pass
        self.assertFalse(app.state.ready)

    def test_rate_limit_has_readable_feedback_and_bounded_identity_table(self):
        with TestClient(create_app(Settings(prediction_rate=1), StubWorkbench)) as client:
            self.assertEqual(client.post("/api/predict", json={}).status_code, 200)
            response = client.post("/api/predict", json={})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["retry-after"], "60")
            self.assertIn("已保留", response.json()["error"])
        now = [0]
        limiter = RateLimiter(1, lambda: now[0])
        self.assertTrue(limiter.allow("a", "predict", 1))
        self.assertFalse(limiter.allow("b", "predict", 1))
        now[0] = 61
        self.assertTrue(limiter.allow("b", "predict", 1))
        self.assertEqual(len(limiter.clients), 1)

    def test_busy_recognizer_does_not_block_prediction_or_health(self):
        started, release = threading.Event(), threading.Event()
        class Slow(StubWorkbench):
            def recognize(self, query):
                started.set()
                release.wait(3)
                return {"status": "aligned"}
        app = create_app(Settings(recognition_queue=0), Slow)
        with TestClient(app) as client, ThreadPoolExecutor(1) as threads:
            request = threads.submit(client.post, "/api/recognize", json={})
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(client.post("/api/recognize", json={}).status_code, 503)
                self.assertEqual(client.post("/api/predict", json={}).status_code, 200)
                self.assertEqual(client.get("/api/health").status_code, 200)
                self.assertEqual(app.state.pools["recognize"].pending, 1)
            finally:
                release.set()
            self.assertEqual(request.result(timeout=3).status_code, 200)

    def test_timeout_retains_running_slot_until_worker_finishes(self):
        release = threading.Event()
        class Slow(StubWorkbench):
            def recognize(self, query):
                release.wait(3)
                return {"status": "aligned"}
        app = create_app(Settings(task_timeout=.03, recognition_queue=0), Slow)
        with TestClient(app) as client:
            try:
                self.assertEqual(client.post("/api/recognize", json={}).status_code, 504)
                self.assertEqual(app.state.pools["recognize"].pending, 1)
                self.assertEqual(client.post("/api/recognize", json={}).status_code, 503)
            finally:
                release.set()
        self.assertEqual(app.state.pools["recognize"].pending, 0)

    def test_queue_has_a_finite_capacity(self):
        started, release = threading.Event(), threading.Event()
        class Slow(StubWorkbench):
            def recognize(self, query):
                started.set()
                release.wait(3)
                return {"status": "aligned"}
        app = create_app(Settings(recognition_queue=1), Slow)
        async def scenario():
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    a = asyncio.create_task(client.post("/api/recognize", json={}))
                    self.assertTrue(await asyncio.to_thread(started.wait, 2))
                    b = asyncio.create_task(client.post("/api/recognize", json={}))
                    for _ in range(50):
                        if app.state.pools["recognize"].pending == 2:
                            break
                        await asyncio.sleep(.005)
                    try:
                        self.assertEqual(app.state.pools["recognize"].pending, 2)
                        self.assertEqual((await client.post("/api/recognize", json={})).status_code, 503)
                    finally:
                        release.set()
                    self.assertEqual([r.status_code for r in await asyncio.gather(a, b)], [200, 200])
        asyncio.run(scenario())

    def test_logs_omit_queries_bodies_and_exception_text(self):
        secret = "visitor-private-ring-and-image"
        class Failing(StubWorkbench):
            def predict(self, query):
                raise RuntimeError(secret)
        with TestClient(create_app(workbench_factory=Failing), raise_server_exceptions=False) as client:
            with self.assertLogs("ringlab.http", level=logging.INFO) as captured:
                response = client.post("/api/predict?image=" + secret, json={"image": secret})
            self.assertEqual(response.status_code, 500)
            self.assertIn("content-security-policy", response.headers)
            self.assertNotIn(secret, " ".join(captured.output))
            self.assertNotIn(secret, response.text)

    def test_invalid_json_lengths_and_predict_limit_release_reservations(self):
        app = create_app(workbench_factory=StubWorkbench)
        with TestClient(app) as client:
            for body in (b"", b"{", b'"\xff"', b'{"x":NaN}', b'{"x":Infinity}'):
                self.assertEqual(client.post("/api/predict", content=body,
                                            headers={"Content-Type": "application/json"}).status_code, 400)
            for length in ("nope", "-1", "10"):
                self.assertEqual(client.post("/api/predict", content=b"{}", headers={
                    "Content-Type": "application/json", "Content-Length": length}).status_code, 400)
            self.assertEqual(client.post("/api/predict", content=b"x" * (MAX_PREDICT_BYTES + 1),
                                        headers={"Content-Type": "application/json"}).status_code, 413)
            self.assertEqual(app.state.pools["predict"].pending, 0)

    def test_real_screenshot_api_matches_recognizer_without_saving_upload(self):
        workbench = Workbench()
        path = Path(__file__).parent / "fixtures" / "worlds-edge-user.png"
        query = {"image": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()}
        with TestClient(create_app(workbench_factory=lambda: workbench)) as client:
            result = client.post("/api/recognize", json=query)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["status"], "aligned")
            self.assertEqual(len(result.json()["candidates"]), 2)
            self.assertEqual(result.json()["quality"]["method"], "sift_homography")
        with patch.object(workbench.recognizer, "auto_homography", side_effect=AssertionError):
            query["bounds"] = {"x0": 0, "y0": 0, "x1": 700, "y1": 700}
            self.assertEqual(workbench.recognize(query)["status"], "aligned")


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_is_limited_even_without_content_length(self):
        from starlette.exceptions import HTTPException
        from starlette.requests import Request
        calls = []
        async def receive():
            calls.append(True)
            return {"type": "http.request", "body": b"x" * 20, "more_body": True}
        request = Request({"type": "http", "headers": []}, receive)
        with self.assertRaises(HTTPException) as error:
            await read_json(request, 30, 1)
        self.assertEqual(error.exception.status_code, 413)
        self.assertEqual(len(calls), 2)

    async def test_slow_upload_is_timed_out(self):
        from starlette.requests import Request
        async def receive():
            await asyncio.sleep(1)
        with self.assertRaises(TimeoutError):
            await read_json(Request({"type": "http", "headers": []}, receive), 30, .01)


class ConfigurationTests(unittest.TestCase):
    def test_local_and_public_settings_reject_invalid_configuration(self):
        for values in ({"host": "0.0.0.0"}, {"public_origin": "http://rings.example"},
                       {"public_origin": "https://rings.example/path"}, {"trusted_proxies": "*"},
                       {"task_timeout": float("nan")}, {"prediction_queue": -1}, {"port": 70000}):
            with self.assertRaises(ValueError):
                Settings(**values)
        self.assertEqual(Settings(host="0.0.0.0", public_origin="https://rings.example").allowed_origins,
                         {"https://rings.example"})
        with patch.dict("os.environ", {"RINGLAB_TRUSTED_PROXIES": "", "RINGLAB_TASK_TIMEOUT": "12.5"}):
            self.assertEqual(Settings.from_env().trusted_proxies, "")
            self.assertEqual(Settings.from_env().task_timeout, 12.5)

    def test_windows_model_paths_work_in_posix_without_rewriting_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(model_path(r"models\stage-1.joblib", root), root.resolve() / "models" / "stage-1.joblib")
            for path in (r"C:\models\stage-1.joblib", "../outside", r"models\..\outside"):
                with self.assertRaises(ValueError):
                    model_path(path, root)
