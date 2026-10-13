"""Shared inference and screenshot workbench."""
from __future__ import annotations

import base64
import hashlib
import json
import platform
import threading
from importlib.metadata import version
from pathlib import PureWindowsPath

import joblib

from .data import COORD_SIZE, DATA_FILE, ROOT, load_records
from .model import predict_one
from .probability import HistoricalProbability, shortlist
from .retrieval import retrieve, validate_observations
from .vision import MAX_IMAGE_BYTES, ScreenshotRecognizer

def model_path(value, root=ROOT):
    """Read the original Windows manifest unchanged on Windows and Linux."""
    portable = PureWindowsPath(value)
    if portable.is_absolute() or portable.drive or ".." in portable.parts:
        raise ValueError("模型路径必须位于项目目录内")
    path = root.joinpath(*portable.parts).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("模型路径必须位于项目目录内")
    return path


class Workbench:
    def __init__(self):
        self.records = load_records()
        fingerprint = hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()
        manifest = json.loads((ROOT / "data" / "training" / "manifest.json").read_text(encoding="utf-8"))
        packages = {"numpy": "numpy", "sklearn": "scikit-learn", "joblib": "joblib",
                    "scipy": "scipy", "threadpoolctl": "threadpoolctl"}
        if any(version(package) != manifest["versions"][key] for key, package in packages.items()):
            raise ValueError("推理依赖版本与训练清单不一致，请安装 requirements.lock.txt")
        if platform.python_version_tuple()[:2] != tuple(manifest["versions"]["python"].split(".")[:2]):
            raise ValueError("Python 主次版本与训练清单不一致，请使用 Python 3.13")
        if manifest["dataset_sha256"] != fingerprint:
            raise ValueError("正式库已变化，请先核查并更新训练模型")
        self.artifacts = {}
        for entry in manifest["models"]:
            path = model_path(entry["model_file"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["model_sha256"]:
                raise ValueError("模型文件与训练记录不一致")
            artifact = joblib.load(path)
            if artifact["dataset_sha256"] != fingerprint:
                raise ValueError("模型数据版本不一致")
            self.artifacts[entry["stages"]] = artifact
        if sorted(self.artifacts) != [1, 2, 3]:
            raise ValueError("启动需要完整的首圈、前两圈和前三圈模型")
        self.scope = manifest["scope"]
        ids = set(manifest["training_ids"])
        self.library = [r for r in self.records if r["id"] in ids]
        if len(self.library) != len(ids):
            raise ValueError("历史参考库样本缺失")
        self.probability = HistoricalProbability(self.records, manifest, self.artifacts)
        self.example = json.loads((ROOT / "data" / "training" / "example-query.json").read_text(encoding="utf-8"))
        self.recognizer = ScreenshotRecognizer()
        self.vision_lock = threading.Lock()

    def metadata(self):
        return {"count": len(self.records), "public_count": sum(r["source_mode"] == "PUBLIC" for r in self.records),
                "algs_count": sum(r["source_mode"] == "ALGS" for r in self.records),
                "reference_count": len(self.library), "model_stages": sorted(self.artifacts),
                "scope": self.scope, "coordinate_size": COORD_SIZE, "target_radius": 728,
                "screenshot_verified": False, "example": self.example}

    def predict(self, query):
        if not isinstance(query, dict):
            raise ValueError("请求需要包含已知圈")
        observed = query.get("known_rings")
        validate_observations(observed)
        if (query.get("map_version"), query.get("build"), query.get("source_mode")) != (
                self.scope["map_version"], self.scope["build"], self.scope["source_mode"]):
            raise ValueError("当前模型只支持所示世界尽头历史版本和 PUBLIC 来源")
        prediction = predict_one(self.artifacts[len(observed)], observed, query["map_version"],
                                 query.get("build"), query["source_mode"])
        candidates = retrieve(self.library, observed, query["map_version"], limit=12)
        predictions = shortlist(prediction, candidates, observed, self.probability)
        # Legacy diagnostic fields remain limited; the UI uses only predictions.
        candidates["candidates"] = candidates["candidates"][:5]
        last = observed[-1]
        return {"predictions": predictions, "model": prediction, "retrieval": candidates,
                "baseline": {"x": last["x"], "y": last["y"], "r": 728, "label": "latest_known_center"},
                "known_rings": observed, "reference_count": len(self.library),
                "probability_note": f"估计命中概率来自 {self.probability.sample_count} 条独立历史验证对局的模型误差，表示真实目标圆心落入该预测圈。圈可重叠，概率不相加；未计入截图识别误差，尚未在当前排位校准。",
                "notice": "目标圈内部圈次及当前排位版本适用性尚未核实。"}

    def recognize(self, query):
        if not isinstance(query, dict) or not isinstance(query.get("image"), str):
            raise ValueError("请上传 JPG 或 PNG 截图")
        value = query["image"]
        if len(value) > (MAX_IMAGE_BYTES + 2) // 3 * 4 + 128:
            raise ValueError("图片不能超过 8 MB")
        if value.startswith("data:"):
            if "," not in value:
                raise ValueError("图片编码无效")
            header, value = value.split(",", 1)
            if header not in ("data:image/jpeg;base64", "data:image/png;base64"):
                raise ValueError("只支持 JPG 或 PNG 截图")
        try:
            raw = base64.b64decode(value, validate=True)
        except ValueError as error:
            raise ValueError("图片编码无效") from error
        # Uploaded bytes and aligned previews never touch disk.
        with self.vision_lock:
            return self.recognizer.recognize(raw, query.get("bounds"))


