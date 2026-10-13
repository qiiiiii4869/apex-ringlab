import copy
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np

from ringlab.model import (FEATURE_SCHEMA, decode_offset, features, predict_centers,
                           predict_one, project_center, target_offset)
from ringlab.train import build_estimator, checked_partitions, prediction_rows, select_candidate
from test_evaluation import record


class ModelTests(unittest.TestCase):
    def test_relative_target_round_trip_and_translation(self):
        r = record("a")
        offset = target_offset(r, 1)
        np.testing.assert_allclose(offset, [1000 / 4800, 0])
        np.testing.assert_allclose(decode_offset(offset, r["known_rings"]), [9000, 8000])
        moved = copy.deepcopy(r)
        for ring in [*moved["known_rings"], moved["final_ring"]]:
            ring["x"] += 500
            ring["y"] -= 500
        np.testing.assert_allclose(target_offset(moved, 1), offset)

    def test_features_do_not_read_target_or_source_identifier(self):
        r = record("a")
        original = features(r["known_rings"])
        r["final_ring"] = {"x": 0, "y": 0, "r": 1}
        r["source_game_id"] = "another_source"
        np.testing.assert_array_equal(features(r["known_rings"]), original)
        self.assertEqual(len(original), 3)

    def test_projection_enforces_all_known_circles_and_map_bounds(self):
        observed = [{"stage": 1, "x": 8000, "y": 8000, "r": 4800},
                    {"stage": 2, "x": 9500, "y": 8000, "r": 2000}]
        point = project_center([18000, 18000], observed, 728)
        self.assertTrue(((point >= 0) & (point <= 16384)).all())
        for ring in observed:
            self.assertLessEqual(np.linalg.norm(point - [ring["x"], ring["y"]]) + 728, ring["r"] + 20 + 1e-6)
        inside = np.array([9500., 8000.])
        np.testing.assert_array_equal(project_center(inside, observed), inside)

    def test_invalid_geometry_and_model_output_are_rejected(self):
        known = record("a")["known_rings"]
        for center in ([float("nan"), 0], [1, 2, 3]):
            with self.assertRaises(ValueError):
                project_center(center, known)
        with self.assertRaises(ValueError):
            project_center([8000, 8000], [{"stage": 1, "x": 8000, "y": 8000, "r": 100}])
        class BadModel:
            def predict(self, matrix):
                return np.zeros(len(matrix))
        with self.assertRaises(ValueError):
            predict_centers(BadModel(), [known])

    def test_inference_rejects_scope_and_stage_mismatch(self):
        artifact = {"feature_schema": FEATURE_SCHEMA, "stages": 1,
                    "scope": {"map_version": "v", "build": None, "source_mode": "PUBLIC"}}
        observed = record("a")["known_rings"]
        for version, build, mode in (("other", None, "PUBLIC"), ("v", "build", "PUBLIC"), ("v", None, "ALGS")):
            with self.assertRaises(ValueError):
                predict_one(artifact, observed, version, build, mode)
        with self.assertRaises(ValueError):
            predict_one({**artifact, "stages": 2}, observed, "v", None)

    def test_parameter_selection_uses_cv_not_validation_scores(self):
        def candidate(alpha, cv, validation):
            return {"config": {"family": "ridge", "alpha": alpha},
                    "cv": {"center_error": {"mean": cv, "p90": cv}}, "validation_score": validation}
        a, b = candidate(1, 10, 999), candidate(10, 20, 0)
        self.assertIs(select_candidate([a, b]), a)
        self.assertIs(select_candidate([b, a]), a)

    def test_partition_check_rejects_stale_hash_and_alias_tampering(self):
        records = [record("a"), record("b"), record("c")]
        manifest = {"dataset_sha256": "frozen", "groups": [
            {"group_id": r["id"], "record_ids": [r["id"]], "source_game_ids": [r["id"]], "split": split}
            for r, split in zip(records, ["library", "validation", "test"])]}
        for r in records:
            r["final_ring"]["r"] = 728
        train, validation, _, _ = checked_partitions(records, manifest, "frozen")
        self.assertEqual([r["id"] for r in train], ["a"])
        self.assertEqual([r["id"] for r in validation], ["b"])
        with self.assertRaises(ValueError):
            checked_partitions(records, manifest, "changed")
        records[1]["source_game_ids"].append("a")
        with self.assertRaises(ValueError):
            checked_partitions(records, manifest, "frozen")

    def test_trained_model_generalizes_simple_offset_and_survives_reload(self):
        observations, offsets = [], []
        for x in range(5000, 10001, 500):
            known = [{"stage": 1, "x": x, "y": 8000, "r": 4800}]
            observations.append(known)
            offsets.append([(x - 7500) / 20000, .05])
        estimator = build_estimator({"family": "ridge", "degree": 1, "alpha": 1e-8})
        estimator.fit(np.vstack([features(o) for o in observations]), np.array(offsets))
        query = [{"stage": 1, "x": 7750, "y": 8000, "r": 4800}]
        artifact = {"feature_schema": FEATURE_SCHEMA, "stages": 1, "estimator": estimator,
                    "target_radius": 728, "dataset_sha256": "fixture", "config": {"family": "ridge"},
                    "scope": {"map_version": "v", "build": None, "source_mode": "PUBLIC"}}
        predicted = predict_one(artifact, query, "v", None)
        np.testing.assert_allclose([predicted["final_ring"]["x"], predicted["final_ring"]["y"]], [7810, 8240], atol=.001)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.joblib"
            joblib.dump(artifact, path)
            self.assertEqual(predict_one(joblib.load(path), query, "v", None), predicted)

    def test_scoring_detects_missing_predictions_and_uses_euclidean_units(self):
        records = [record("a")]
        self.assertEqual(prediction_rows(records, [[9300, 8400]])[0]["center_error"], 500)
        with self.assertRaises(ValueError):
            prediction_rows(records, [])


if __name__ == "__main__":
    unittest.main()
