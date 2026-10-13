from __future__ import annotations

import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "rings.json"
COORD_SIZE = 16384


def validate_record(record: dict) -> dict:
    if not isinstance(record, dict):
        raise ValueError("每局数据必须是对象")
    if not record.get("id") or not record.get("map_version"):
        raise ValueError("每局需要 id 和 map_version")
    if record.get("map") != "worlds_edge":
        raise ValueError("当前仅支持世界尽头")
    rings = record.get("known_rings", [])
    if not isinstance(rings, list) or not 1 <= len(rings) <= 3:
        raise ValueError("每局需要 1～3 个已知圈及配对的最终圈")
    for i, ring in enumerate(rings):
        if ring.get("stage") != i + 1:
            raise ValueError("圈数必须从 1 开始连续排列")
        for key in ("x", "y", "r"):
            value = ring.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError("圈坐标和半径必须是有限数字")
        if not (0 <= ring["x"] <= COORD_SIZE and 0 <= ring["y"] <= COORD_SIZE and 0 < ring["r"] <= COORD_SIZE):
            raise ValueError("圈坐标超出地图范围")
        if i:
            prev = rings[i - 1]
            if ring["r"] >= prev["r"] or math.hypot(ring["x"] - prev["x"], ring["y"] - prev["y"]) + ring["r"] > prev["r"] + 20:
                raise ValueError("后续圈必须缩小且包含在上一圈内")
    final = record.get("final_ring")
    if not isinstance(final, dict):
        raise ValueError("缺少同轮揭晓的最终圈")
    for key in ("x", "y"):
        value = final.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= COORD_SIZE:
            raise ValueError("最终圈圆心无效")
    radius = final.get("r")
    if radius is not None and (not isinstance(radius, (int, float)) or isinstance(radius, bool) or not math.isfinite(radius) or not 0 <= radius <= COORD_SIZE):
        raise ValueError("最终圈半径无效")
    for known in rings:
        if math.hypot(final["x"] - known["x"], final["y"] - known["y"]) + (radius or 0) > known["r"] + 20:
            raise ValueError("最终圈必须位于已知安全区内")
    if record.get("source_mode") not in ("ALGS", "PUBLIC"):
        raise ValueError("缺少数据来源模式")
    if record.get("game_mode") not in ("ranked", "tournament", "unknown"):
        raise ValueError("对局模式标签无效")
    return record


def load_records(path: Path = DATA_FILE) -> list[dict]:
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("样本文件必须是数组")
    for record in records:
        validate_record(record)
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("存在重复对局 ID")
    return records


def save_records(records: list[dict], path: Path = DATA_FILE):
    for record in records:
        validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("存在重复样本 ID")
    write_json_atomic(path, records)


def write_json_atomic(path: Path, value, attempts: int = 8):
    """Keep the previous file intact while retrying brief Windows sharing locks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(attempts):
        try:
            temporary.replace(path)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == attempts - 1:
                raise
            time.sleep(min(0.05 * 2 ** attempt, 0.5))


def metadata(records: list[dict]) -> dict:
    versions = sorted({r["map_version"] for r in records})
    return {
        "count": len(records), "versions": versions, "coordinate_size": COORD_SIZE,
        "ranked_count": sum(r.get("game_mode") == "ranked" for r in records),
        "source_modes": {mode: sum(r["source_mode"] == mode for r in records) for mode in ("ALGS", "PUBLIC")},
        "sources": sorted({r.get("source", "unknown") for r in records}),
        "assets": json.loads((ROOT / "data" / "assets.json").read_text(encoding="utf-8")) if (ROOT / "data" / "assets.json").exists() else [],
    }
