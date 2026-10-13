import base64
import copy
import json
import math
import unittest
from fastapi.testclient import TestClient

from ringlab.config import Settings
from ringlab.server import MAX_REQUEST_BYTES, Workbench, create_app


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workbench = Workbench()
        cls.app = create_app(Settings(prediction_rate=1000, recognition_rate=1000), lambda: cls.workbench)
        cls.client = TestClient(cls.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def request(self, method, path, body=None, headers=None):
        if isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")
        response = self.client.request(method, path, content=body,
                                       headers=headers or {"Content-Type": "application/json"})
        return response.status_code, response.content, dict(response.headers)

    def test_page_and_assets_are_served_without_exposing_project_files(self):
        status, body, headers = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("圈位实验室", body.decode("utf-8"))
        self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])
        self.assertEqual(self.request("GET", "/assets/worlds-edge.jpg")[0], 200)
        status, _, headers = self.request("GET", "/geometry.mjs")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["content-type"])
        status, _, headers = self.request("GET", "/session.mjs")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["content-type"])
        for path in ("/data/rings.json", "/../data/rings.json", "/%2e%2e/PROJECT_PLAN.md", "/models/stage-3.joblib"):
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_metadata_and_each_stage_predict_without_answers_in_query(self):
        status, body, _ = self.request("GET", "/api/meta")
        metadata = json.loads(body)
        self.assertEqual(status, 200)
        self.assertNotIn("final_ring", metadata["example"])
        self.assertFalse(metadata["screenshot_verified"])
        for stage in (1, 2, 3):
            query = copy.deepcopy(metadata["example"])
            query["known_rings"] = query["known_rings"][:stage]
            status, body, _ = self.request("POST", "/api/predict", query)
            result = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(len(result["known_rings"]), stage)
            self.assertEqual(result["reference_count"], len(self.workbench.library))
            self.assertEqual(result["baseline"]["x"], query["known_rings"][-1]["x"])
            self.assertEqual(result["model"]["final_ring"]["r"], 728)
            self.assertFalse(result["model"]["probabilities_calibrated"])
            self.assertLessEqual(len(result["retrieval"]["candidates"]), 5)
            shortlist = result["predictions"]
            self.assertGreaterEqual(len(shortlist), 1)
            self.assertLessEqual(len(shortlist), 5)
            self.assertEqual(sum(c["kind"] == "model" for c in shortlist), 1)
            values = [c["probability"]["value"] for c in shortlist]
            self.assertEqual(values, sorted(values, reverse=True))
            for candidate in shortlist:
                probability = candidate["probability"]
                self.assertGreater(probability["value"], 0)
                self.assertLess(probability["value"], 1)
                self.assertEqual(probability["sample_count"], 193)
                self.assertFalse(probability["calibrated"])
                ring = candidate["final_ring"]
                for known in query["known_rings"]:
                    self.assertLessEqual(math.hypot(ring["x"]-known["x"], ring["y"]-known["y"])+ring["r"], known["r"]+20.00001)
            for i, candidate in enumerate(shortlist):
                ring = candidate["final_ring"]
                for other in shortlist[i+1:]:
                    self.assertGreater(math.hypot(ring["x"]-other["final_ring"]["x"], ring["y"]-other["final_ring"]["y"]), ring["r"]*.6)

    def test_invalid_scope_and_circle_order_return_readable_errors(self):
        for kind in ("scope", "stage", "outside"):
            query = copy.deepcopy(self.workbench.example)
            if kind == "scope":
                query["map_version"] = "another_map"
            elif kind == "stage":
                query["known_rings"][0]["stage"] = 3
            else:
                query["known_rings"][0]["x"] = -1
            status, body, _ = self.request("POST", "/api/predict", query)
            self.assertEqual(status, 400)
            self.assertTrue(json.loads(body)["error"])

    def test_origin_content_type_and_upload_size_are_rejected(self):
        headers = {"Content-Type": "application/json", "Origin": "https://external.invalid"}
        self.assertEqual(self.request("POST", "/api/predict", {}, headers)[0], 403)
        self.assertEqual(self.request("POST", "/api/predict", b"{}", {"Content-Type": "text/plain"})[0], 415)
        headers = {"Content-Type": "application/json", "Content-Length": str(MAX_REQUEST_BYTES + 1)}
        self.assertEqual(self.request("POST", "/api/recognize", b"{}", headers)[0], 413)

    def test_bad_json_and_invalid_image_do_not_break_service(self):
        self.assertEqual(self.request("POST", "/api/predict", b"{broken}")[0], 400)
        image = base64.b64encode(b"not-an-image").decode("ascii")
        self.assertEqual(self.request("POST", "/api/recognize", {"image": image})[0], 400)
        self.assertEqual(self.request("POST", "/api/recognize", {"image": "???"})[0], 400)
        self.assertEqual(self.request("GET", "/api/health")[0], 200)


if __name__ == "__main__":
    unittest.main()
