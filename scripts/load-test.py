"""Run a finite local burst against a disposable server, recording aggregate costs."""
from __future__ import annotations

import argparse
import base64
import json
import platform
import statistics
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import psutil

ROOT = Path(__file__).resolve().parents[1]


def send(url, body=None):
    request = Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
    started = time.monotonic()
    try:
        with urlopen(request, timeout=75) as response:
            status, raw = response.status, response.read()
    except HTTPError as error:
        status, raw = error.code, error.read()
    payload = json.loads(raw) if raw.startswith(b"{") else {}
    return status, payload, time.monotonic() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--pid", type=int, required=True, help="Exact disposable server PID to measure")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--moderate-clients", type=int, choices=(2, 4), default=2)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "deployment-validation.json")
    args = parser.parse_args()
    process = psutil.Process(args.pid)
    if "ringlab.server" not in " ".join(process.cmdline()):
        raise ValueError("PID is not the intended ringlab.server process")
    base = f"http://127.0.0.1:{args.port}"
    if send(base + "/api/health")[1].get("status") != "ready":
        raise ValueError("Server is not ready")
    status, meta, _ = send(base + "/api/meta")
    query = json.dumps(meta["example"]).encode()
    screenshot = (ROOT / "tests" / "fixtures" / "worlds-edge-user.png").read_bytes()
    image = json.dumps({"image": "data:image/png;base64," + base64.b64encode(screenshot).decode()}).encode()
    # A Windows venv python.exe can be a launcher with the real interpreter child.
    peaks = {"rss_bytes": 0, "cpu_percent_one_core": 0.0, "includes_child_processes": True}
    stop = threading.Event()

    def monitor():
        tracked = {}
        while not stop.is_set():
            rss, cpu = 0, 0.0
            for item in [process, *process.children(recursive=True)]:
                if item.pid not in tracked:
                    tracked[item.pid] = item
                    item.cpu_percent()
                try:
                    rss += item.memory_info().rss
                    cpu += tracked[item.pid].cpu_percent()
                except psutil.NoSuchProcess:
                    continue
            peaks["rss_bytes"] = max(peaks["rss_bytes"], rss)
            peaks["cpu_percent_one_core"] = max(peaks["cpu_percent_one_core"], cpu)
            stop.wait(.1)

    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    scenarios = {}
    try:
        for route, body in (("predict", query), ("recognize", image)):
            with ThreadPoolExecutor(args.moderate_clients) as pool:
                moderate = list(pool.map(lambda _: send(base + "/api/" + route, body), range(args.moderate_clients)))
            if any(code != 200 for code, _, _ in moderate):
                raise AssertionError("Concurrent friends exceeded the selected capacity")
            label = "two" if args.moderate_clients == 2 else "four"
            scenarios[route + "_" + label + "_clients"] = {"requests": args.moderate_clients,
                                                  "statuses": {"200": args.moderate_clients},
                                                  "success_rate": 1.0,
                                                  "max_seconds": max(r[2] for r in moderate)}
            with ThreadPoolExecutor(args.concurrency) as pool:
                results = list(pool.map(lambda _: send(base + "/api/" + route, body), range(args.requests)))
            durations = sorted(item[2] for item in results)
            scenarios[route] = {"requests": len(results), "statuses": dict(Counter(str(r[0]) for r in results)),
                                "success_rate": sum(r[0] == 200 for r in results) / len(results),
                                "median_seconds": statistics.median(durations), "max_seconds": max(durations),
                                "successful_max_seconds": max((r[2] for r in results if r[0] == 200), default=None)}
            successes = [payload for code, payload, _ in results if code == 200]
            if route == "recognize" and any(r.get("status") != "aligned" or len(r.get("candidates", [])) != 2
                                            for r in successes):
                raise AssertionError("A successful screenshot response lost the two real circles")
            if route == "predict" and any(not 1 <= len(r.get("predictions", [])) <= 5 for r in successes):
                raise AssertionError("Prediction response contract changed")
            if not successes or any(code not in (200, 429, 503) for code, _, _ in results):
                raise AssertionError("Unexpected failure under burst load")
        health = send(base + "/api/health")
        if health[0] != 200 or any(health[1]["pending"].values()):
            raise AssertionError("Server did not recover after burst")
    finally:
        stop.set()
        watcher.join(2)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "python": platform.python_version(), "concurrency": args.concurrency, "scenarios": scenarios,
              "process_peaks": peaks, "health_after": health[1], "actual_image_fixture_used": True,
              "limitations": ["Measurements reflect only this host and tested scenarios, not guaranteed capacity",
                              "Burst rejection is expected bounded overload feedback, not an inference error",
                              "Public HTTPS and browser interactions are not validated by this script"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
