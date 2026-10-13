"""Historical residual estimates, not calibrated live-game probabilities."""
from __future__ import annotations

import math

import numpy as np

from .model import predict_centers, project_center


class HistoricalProbability:
    def __init__(self, records, manifest, artifacts):
        ids = set(manifest["validation_ids"])
        if ids & set(manifest["training_ids"]) or ids & set(manifest["reserved_test_ids"]):
            raise ValueError("概率参考样本不能与训练或旧测试对局重叠")
        by_id = {r["id"]: r for r in records}
        validation = [by_id[item] for item in sorted(ids)]
        if not validation:
            raise ValueError("没有独立验证数据，无法估计概率")
        self.residuals = {}
        for stage, artifact in artifacts.items():
            scope = artifact["scope"]
            if any((r["map_version"], r.get("build"), r["source_mode"], r["final_ring"]["r"]) !=
                   (scope["map_version"], scope["build"], scope["source_mode"], artifact["target_radius"])
                   for r in validation):
                raise ValueError("概率参考数据与模型范围不一致")
            observations = [r["known_rings"][:stage] for r in validation]
            predicted, _ = predict_centers(artifact["estimator"], observations, artifact["target_radius"])
            truth = np.asarray([[r["final_ring"]["x"], r["final_ring"]["y"]] for r in validation])
            radii = np.asarray([obs[-1]["r"] for obs in observations])[:, None]
            self.residuals[stage] = (truth - predicted) / radii
        self.sample_count = len(validation)

    def estimate(self, ring, model_ring, observed):
        # Assume normalized historical error transfers to the current query.
        # Each disk is an independent overlapping event; never normalize to 100%.
        scale = observed[-1]["r"]
        offset = np.asarray([ring["x"] - model_ring["x"], ring["y"] - model_ring["y"]]) / scale
        residuals = self.residuals[len(observed)]
        hits = int((np.linalg.norm(residuals - offset, axis=1) <= ring["r"] / scale).sum())
        n = len(residuals)
        p = hits / n
        z = 1.96
        denominator = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denominator
        width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
        return {"value": (hits + .5) / (n + 1), "historical_hits": hits, "sample_count": n,
                "interval_95": [max(0, center - width), min(1, center + width)],
                "method": "normalized_validation_residuals", "calibrated": False,
                "event": "true_target_center_inside_candidate_circle"}


def shortlist(prediction, retrieval, observed, probability, limit=5):
    model = prediction["final_ring"]
    pool = [{"id": "model", "kind": "model", "label": "模型预测", "final_ring": model}]
    for item in retrieval["candidates"]:
        source = item["known_rings"][len(observed) - 1]
        anchor = observed[-1]
        # Transfer the historical final offset to this query, then ensure every
        # displayed target lies within the user's known rings.
        historical = item["final_ring"]
        position = np.asarray([anchor["x"], anchor["y"]]) + (
            np.asarray([historical["x"] - source["x"], historical["y"] - source["y"]])
            * anchor["r"] / source["r"])
        position = project_center(position, observed, model["r"])
        ring = {"x": float(position[0]), "y": float(position[1]), "r": model["r"]}
        pool.append({"id": item["id"], "kind": "history", "label": "历史圈型参考", "final_ring": ring,
                     "distance": item["distance"], "source_url": item["source_url"]})
    for item in pool:
        item["probability"] = probability.estimate(item["final_ring"], model, observed)
    # Retain the model; suppress very similar circles before the total limit.
    chosen = [pool[0]]
    for item in sorted(pool[1:], key=lambda c: (-c["probability"]["value"], c["distance"], c["id"])):
        ring = item["final_ring"]
        if all(math.hypot(ring["x"] - c["final_ring"]["x"], ring["y"] - c["final_ring"]["y"]) > model["r"] * .6
               for c in chosen):
            chosen.append(item)
        if len(chosen) >= min(limit, 5):
            break
    return sorted(chosen, key=lambda c: -c["probability"]["value"])[:min(limit, 5)]
