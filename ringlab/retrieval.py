from __future__ import annotations

import math
from collections import defaultdict

from .data import COORD_SIZE


def validate_observations(observed: list[dict]):
    if not isinstance(observed, list) or not 1 <= len(observed) <= 3:
        raise ValueError("请提供 1～3 个已知安全区")
    for i, ring in enumerate(observed):
        if not isinstance(ring, dict) or ring.get("stage") != i + 1:
            raise ValueError("已知圈必须从第 1 圈连续提供")
        for key in ("x", "y", "r"):
            value = ring.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError("请输入有效的圆心和半径")
        if not (0 <= ring["x"] <= COORD_SIZE and 0 <= ring["y"] <= COORD_SIZE and 0 < ring["r"] <= COORD_SIZE):
            raise ValueError("圈位超出地图范围")
        if i:
            prev = observed[i - 1]
            if ring["r"] >= prev["r"] or math.hypot(ring["x"] - prev["x"], ring["y"] - prev["y"]) + ring["r"] > prev["r"] + 50:
                raise ValueError("请检查圈数：后续安全区应位于上一圈内")


def distance(observed: list[dict], rings: list[dict]) -> float:
    # Later observations receive more weight. Score units are website map units.
    weights = [2 ** i for i in range(len(observed))]
    return math.sqrt(sum(w * ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + .25 * (a["r"] - b["r"]) ** 2)
                         for w, a, b in zip(weights, observed, rings)) / sum(weights))


def retrieve(records: list[dict], observed: list[dict], version: str, limit: int = 5, exclude_id: str | None = None) -> dict:
    validate_observations(observed)
    pool = [r for r in records if r["map_version"] == version and r["id"] != exclude_id]
    if not pool:
        return {"candidates": [], "status": "empty", "message": "此地图版本尚无可用样本", "pool_size": 0}
    ranked = sorted(((distance(observed, r["known_rings"]), r) for r in pool if len(r["known_rings"]) >= len(observed)), key=lambda item: (item[0], item[1]["id"]))
    if not ranked:
        return {"candidates": [], "status": "empty", "message": "样本缺少所需已知圈", "pool_size": 0}
    # Group identical target circles so repeated labels do not occupy every card.
    unique = []
    seen = set()
    for error, record in ranked:
        final = record["final_ring"]
        trajectory = (final["x"], final["y"], final.get("r"))
        if trajectory in seen:
            continue
        seen.add(trajectory)
        unique.append({"id": record["id"], "distance": round(error, 2), "known_rings": record["known_rings"], "final_ring": final,
                       "source_url": record.get("source_url"), "mode": record.get("game_mode", "unknown")})
        if len(unique) >= limit:
            break
    nearest = ranked[0][0]
    status = "exact" if nearest < .01 else "near" if nearest < 200 else "distant"
    messages = {"exact": "已知圈位与历史记录一致；最终圈仅代表该历史对局", "near": "找到相近历史圈型，请对比多个候选", "distant": "历史样本中没有接近的圈型，以下仅供参考"}
    return {"candidates": unique, "status": status, "message": messages[status], "pool_size": len(pool),
            "probabilities_calibrated": False, "ranked_validated": False}


def audit(records: list[dict]) -> dict:
    groups = defaultdict(list)
    for record in records:
        first = record["known_rings"][0]
        # Build is part of the key; do not merge different server versions.
        key = (record["map_version"], record.get("build"), record["source_mode"], first["x"], first["y"], first["r"])
        groups[key].append(record)
    repeated = [g for g in groups.values() if len(g) > 1]
    conflicts = []
    for group in repeated:
        tails = {(item["final_ring"]["x"], item["final_ring"]["y"], item["final_ring"].get("r")) for item in group}
        if len(tails) > 1:
            conflicts.append([r["id"] for r in group])
    return {"records": len(records), "unique_first_rings": len(groups), "repeated_first_ring_groups": len(repeated),
            "conflict_groups": len(conflicts), "conflict_examples": conflicts[:10],
            "interpretation": "仅为样本内检查，不能证明所有首圈唯一决定最终圈；build 未知时无法确认同机制版本"}
