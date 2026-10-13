"""Start and stop only our own disposable Uvicorn child for deployment QA."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
qa = root / "outputs" / "qa"
qa.mkdir(parents=True, exist_ok=True)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
env = {key: value for key, value in os.environ.items() if not key.startswith("RINGLAB_")}
creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
with (qa / "fastapi-server.log").open("w", encoding="utf-8") as log:
    process = subprocess.Popen([sys.executable, "-m", "ringlab.server", "--port", str(port)],
                               cwd=root, env=env, stdout=log, stderr=log, creationflags=creationflags)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("QA server failed; inspect outputs/qa/fastapi-server.log")
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                    if json.load(response).get("status") == "ready":
                        break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError("QA server not ready in startup window")
        subprocess.run([sys.executable, str(root / "scripts" / "load-test.py"), "--port", str(port),
                        "--pid", str(process.pid)], cwd=root, env=env, check=True,
                       creationflags=creationflags)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
