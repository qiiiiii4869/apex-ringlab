"""Inference helpers for supervised final-circle offset regression."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import joblib
import numpy as np

from .data import COORD_SIZE, ROOT
from .retrieval import validate_observations

FEATURE_SCHEMA = "absolute-circles-and-relative-offsets-v1"
GEOMETRY_TOLERANCE = 20  # Same tolerance as formal dataset validation.


def features(observed):
    """Only observed circles are available at inference; no target or source ID."""
    validate_observations(observed)
    anchor = observed[-1]
    values = []
    for ring in observed:
        values.extend(((ring["x"] - COORD_SIZE / 2) / (COORD_SIZE / 2),
                       (ring["y"] - COORD_SIZE / 2) / (COORD_SIZE / 2), ring["r"] / COORD_SIZE))
    for ring in observed[:-1]:
        values.extend(((ring["x"] - anchor["x"]) / anchor["r"],
                       (ring["y"] - anchor["y"]) / anchor["r"], ring["r"] / anchor["r"]))
    for previous, ring in zip(observed, observed[1:]):
        values.append(math.hypot(ring["x"] - previous["x"], ring["y"] - previous["y"]) / previous["r"])
    return np.asarray(values, dtype=float)


def target_offset(record, stages):
    anchor = record["known_rings"][stages - 1]
    final = record["final_ring"]
    return np.array([(final["x"] - anchor["x"]) / anchor["r"],
                     (final["y"] - anchor["y"]) / anchor["r"]], dtype=float)


def decode_offset(offset, observed):
    anchor = observed[-1]
    return np.array([anchor["x"], anchor["y"]], dtype=float) + np.asarray(offset) * anchor["r"]


def project_center(center, observed, target_radius=728):
    """Project to the intersection of target-containment disks and map bounds."""
    validate_observations(observed)
    point = np.asarray(center, dtype=float).copy()
    if point.shape != (2,) or not np.isfinite(point).all():
        raise ValueError("模型圆心必须是两个有限数字")
    if not isinstance(target_radius, (int, float)) or not math.isfinite(target_radius) or target_radius <= 0:
        raise ValueError("目标半径无效")
    disks = [(np.array([r["x"], r["y"]], dtype=float), r["r"] - target_radius + GEOMETRY_TOLERANCE)
             for r in observed]
    if not disks or any(radius < 0 for _, radius in disks):
        raise ValueError("已知圈不足以包含当前模型的目标圈半径")
    for _ in range(256):
        point = np.clip(point, 0, COORD_SIZE)
        for center_i, radius in disks:
            difference = point - center_i
            distance = float(np.linalg.norm(difference))
            if distance > radius:
                point = center_i + difference * (radius / distance)
        feasible = bool(((point >= -1e-7) & (point <= COORD_SIZE + 1e-7)).all())
        feasible &= all(np.linalg.norm(point - c) <= radius + 1e-7 for c, radius in disks)
        if feasible:
            return np.clip(point, 0, COORD_SIZE)
    raise ValueError("已知圈之间没有找到可用目标区域，请核对圈次与半径")


def predict_centers(estimator, observations, target_radius=728):
    if not observations:
        raise ValueError("至少提供一组已知圈")
    matrix = np.vstack([features(observed) for observed in observations])
    offsets = np.asarray(estimator.predict(matrix), dtype=float)
    if offsets.shape != (len(observations), 2) or not np.isfinite(offsets).all():
        raise ValueError("模型输出需要每组两个有限偏移量")
    raw = [decode_offset(offset, observed) for offset, observed in zip(offsets, observations)]
    projected = [project_center(center, observed, target_radius) for center, observed in zip(raw, observations)]
    return np.asarray(projected), np.asarray(raw)


def predict_one(artifact, observed, version, build, source_mode="PUBLIC"):
    validate_observations(observed)
    if artifact.get("feature_schema") != FEATURE_SCHEMA:
        raise ValueError("模型特征版本不兼容")
    if len(observed) != artifact["stages"]:
        raise ValueError("输入圈数与模型不一致")
    scope = artifact["scope"]
    if (version, build, source_mode) != (scope["map_version"], scope["build"], scope["source_mode"]):
        raise ValueError("地图、build 或来源模式与模型不一致")
    centers, raw = predict_centers(artifact["estimator"], [observed], artifact["target_radius"])
    final = {"x": float(centers[0, 0]), "y": float(centers[0, 1]), "r": artifact["target_radius"],
             "label": "predicted_ringguessr_final", "stage": None}
    return {"final_ring": final, "method": artifact["config"],
            "geometry_adjusted": bool(np.linalg.norm(centers[0] - raw[0]) > 1e-7),
            "probabilities_calibrated": False, "validation_scope": "historical_source_coordinates",
            "dataset_sha256": artifact["dataset_sha256"], "build_known": scope["build"] is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", type=Path, help="JSON containing known_rings, map_version, build and source_mode")
    parser.add_argument("--models", type=Path, default=ROOT / "models")
    args = parser.parse_args()
    query = json.loads(args.query.read_text(encoding="utf-8-sig"))
    observed = query["known_rings"]
    validate_observations(observed)
    artifact = joblib.load(args.models / f"stage-{len(observed)}.joblib")
    print(json.dumps(predict_one(artifact, observed, query["map_version"], query["build"], query["source_mode"]),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
