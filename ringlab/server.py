"""FastAPI workbench; run locally with python -m ringlab.server."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import replace

import cv2
import uvicorn
from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException
from starlette.requests import ClientDisconnect
from starlette.responses import FileResponse, JSONResponse

from .config import Settings
from .data import ROOT
from .limits import BoundedPool, BusyError, RateLimiter
from .workbench import Workbench

MAX_REQUEST_BYTES = 12 * 1024 * 1024
MAX_PREDICT_BYTES = 64 * 1024
STATIC_FILES = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js",
                "/geometry.mjs": "geometry.mjs", "/session.mjs": "session.mjs", "/style.css": "style.css",
                "/assets/worlds-edge.jpg": "assets/worlds-edge.jpg"}
CONTENT_TYPES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript",
                 ".mjs": "text/javascript", ".jpg": "image/jpeg"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; script-src 'self'; "
                               "style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
    "Referrer-Policy": "no-referrer",
}
logger = logging.getLogger("ringlab.http")


def error(status, message, retry=False):
    return JSONResponse({"error": message}, status_code=status,
                        headers={**SECURITY_HEADERS, "Cache-Control": "no-store",
                                 **({"Retry-After": "60" if status == 429 else "5"} if retry else {})})


class ResponsePolicy:
    """Apply headers and aggregate metrics without logging IPs, URLs or bodies."""
    def __init__(self, app, settings, metrics):
        self.app, self.settings, self.metrics = app, settings, metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        route = path if path in STATIC_FILES or path in ("/api/meta", "/api/health", "/api/predict",
                                                        "/api/recognize") else "other"
        started, status = time.monotonic(), 500

        async def policy_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = dict(message.get("headers", []))
                headers.update({key.lower().encode(): value.encode() for key, value in SECURITY_HEADERS.items()})
                headers[b"cache-control"] = b"no-store" if path.startswith("/api/") else b"no-cache"
                if self.settings.public_origin:
                    headers[b"strict-transport-security"] = b"max-age=31536000"
                message["headers"] = list(headers.items())
            await send(message)

        try:
            origins = Request(scope).headers.getlist("origin")
            if path.startswith("/api/") and origins and (
                    len(origins) != 1 or origins[0] not in self.settings.allowed_origins):
                return await error(403, "请求来源不匹配")(scope, receive, policy_send)
            await self.app(scope, receive, policy_send)
        finally:
            key = f"{route}:{status}"
            stat = self.metrics.setdefault(key, {"requests": 0, "seconds": 0})
            stat["requests"] += 1
            stat["seconds"] += time.monotonic() - started
            logger.info("route=%s status=%s elapsed_ms=%.1f", route, status,
                        (time.monotonic() - started) * 1000)


def reject_constant(value):
    raise ValueError("请求不是有效 JSON")


async def read_json(request, limit, timeout):
    length = request.headers.get("content-length")
    if length is not None:
        try:
            length = int(length)
        except ValueError:
            raise HTTPException(400, "请求长度无效")
        if length <= 0:
            raise HTTPException(400, "请求内容为空")
        if length > limit:
            raise HTTPException(413, "请求过大，图片最多 8 MB" if limit == MAX_REQUEST_BYTES else "圈位请求过大")
    raw = bytearray()
    async with asyncio.timeout(timeout):
        async for chunk in request.stream():
            if len(raw) + len(chunk) > limit:
                raise HTTPException(413, "请求内容超过大小限制")
            raw.extend(chunk)
    if not raw:
        raise HTTPException(400, "请求内容为空")
    if length is not None and len(raw) != length:
        raise HTTPException(400, "请求内容不完整")
    try:
        return json.loads(raw, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(400, "请求不是有效 JSON")


def create_app(settings=None, workbench_factory=Workbench):
    settings = settings or Settings.from_env()
    metrics = {}

    @asynccontextmanager
    async def lifespan(app):
        cv2.setNumThreads(settings.cv_threads)
        app.state.ready = False
        app.state.workbench = await asyncio.to_thread(workbench_factory)
        app.state.pools = {"predict": BoundedPool(settings.prediction_workers, settings.prediction_queue, "prediction"),
                           "recognize": BoundedPool(1, settings.recognition_queue, "recognition")}
        app.state.limiter = RateLimiter(settings.rate_clients)
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False
            await asyncio.gather(*(pool.close() for pool in app.state.pools.values()))
            app.state.workbench = None

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.metrics = metrics
    app.state.ready = False
    app.add_middleware(ResponsePolicy, settings=settings, metrics=metrics)

    @app.exception_handler(HTTPException)
    async def handle_http_error(request, exc):
        return error(exc.status_code, str(exc.detail) if exc.status_code != 404 else "页面或接口不存在")

    @app.exception_handler(Exception)
    async def handle_failure(request, exc):
        logger.error("request_failed type=%s", type(exc).__name__)
        return error(500, "服务处理失败，请稍后重试")

    @app.get("/api/health")
    async def health():
        if not app.state.ready:
            return JSONResponse({"status": "not_ready", "models": []}, status_code=503)
        return {"status": "ready", "models": sorted(app.state.workbench.artifacts),
                "pending": {name: pool.pending for name, pool in app.state.pools.items()}}

    @app.get("/api/meta")
    async def metadata():
        if not app.state.ready:
            return error(503, "服务尚未就绪，请稍后重试", True)
        value = app.state.workbench.metadata()
        value["processing"] = {"mode": "server" if settings.public_origin else "local",
                               "images_saved": False,
                               "notice": "截图通过 HTTPS 发送到服务器，仅在服务器内存中临时处理，不保存图片、不进入训练库。"
                               if settings.public_origin else "截图发送到本机服务，仅在本机内存中处理，不保存图片。"}
        return value

    async def compute(request, kind):
        if not app.state.ready:
            return error(503, "服务尚未就绪，请稍后重试", True)
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return error(415, "请使用 JSON 请求")
        limit = settings.prediction_rate if kind == "predict" else settings.recognition_rate
        client = request.client.host if request.client else "unknown"
        if not app.state.limiter.allow(client, kind, limit):
            return error(429, "请求过于频繁，请等待一分钟后重试；本局圈位已保留", True)
        pool = app.state.pools[kind]
        try:
            pool.reserve()
        except BusyError:
            return error(503, "服务繁忙，请稍后重试；本局圈位已保留", True)
        transferred = False
        try:
            query = await read_json(request, MAX_PREDICT_BYTES if kind == "predict" else MAX_REQUEST_BYTES,
                                    settings.upload_timeout)
            future = pool.submit(getattr(app.state.workbench, kind), query)
            transferred = True
            value = await asyncio.wait_for(asyncio.shield(future), settings.task_timeout)
            return JSONResponse(value)
        except HTTPException as exc:
            return error(exc.status_code, str(exc.detail))
        except ClientDisconnect:
            return error(400, "上传连接中断，请重试；本局圈位已保留")
        except TimeoutError:
            return error(408 if not transferred else 504, "处理超时，请稍后重试；本局圈位已保留", True)
        except (ValueError, TypeError, KeyError) as exc:
            return error(400, str(exc)[:300])
        except Exception as exc:
            logger.error("request_failed type=%s", type(exc).__name__)
            return error(500, "服务处理失败，请稍后重试")
        finally:
            if not transferred:
                pool.release()

    @app.post("/api/predict")
    async def predict(request: Request):
        return await compute(request, "predict")

    @app.post("/api/recognize")
    async def recognize(request: Request):
        return await compute(request, "recognize")

    @app.get("/{path:path}")
    async def static(path: str):
        asset = STATIC_FILES.get("/" + path)
        if not asset or not (ROOT / "web" / asset).is_file():
            return error(404, "页面不存在")
        filename = ROOT / "web" / asset
        return FileResponse(filename, media_type=CONTENT_TYPES[filename.suffix])

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int)
    parser.add_argument("--host")
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.port is not None:
        settings = replace(settings, port=args.port)
    if args.host is not None:
        settings = replace(settings, host=args.host)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print(f"Local: http://{settings.host}:{settings.port}" if not settings.public_origin
          else f"Public Origin: {settings.public_origin}", flush=True)
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, workers=1, access_log=False,
                proxy_headers=True, forwarded_allow_ips=settings.trusted_proxies,
                limit_concurrency=settings.connections, timeout_keep_alive=5, server_header=False)


if __name__ == "__main__":
    main()
