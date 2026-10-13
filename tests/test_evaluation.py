import copy
import unittest

from ringlab.evaluate import (assert_no_leakage, compatible_pool, evaluate_queries,
                              make_split, percentile, source_groups, summarize)
from ringlab.ingest import normalize
from test_collection import pair


def record(key, aliases=None, mode="PUBLIC"):
    result = normalize(pair(mode, key))
    result["id"] = key
    result["source_game_ids"] = aliases or [key]
    return result


class EvaluationTests(unittest.TestCase):
    def test_aliases_are_transitive_and_cross_mode(self):
        a = record("a", ["a", "shared1"])
        b = record("b", ["b", "shared1", "shared2"], "ALGS")
        c = record("c", ["c", "shared2"])
        d = record("d")
        groups = source_groups([d, c, b, a])
        self.assertEqual([[r["id"] for r in g] for g in groups], [["a", "b", "c"], ["d"]])

    def test_split_deterministic_under_reordering_and_no_leakage(self):
        records = [record(f"r{i}") for i in range(30)]
        records[1]["source_game_ids"].append("r0")
        first = make_split(records)
        self.assertEqual(first, make_split(list(reversed(records))))
        assert_no_leakage(first)
        owners = {item: g["split"] for g in first for item in g["record_ids"]}
        self.assertEqual(owners["r0"], owners["r1"])
        self.assertEqual(set(owners.values()), {"library", "validation", "test"})

    def test_leakage_detection_rejects_reused_alias(self):
        with self.assertRaisesRegex(ValueError, "source"):
            assert_no_leakage([{"source_game_ids": ["same"], "record_ids": ["a"], "split": "library"},
                               {"source_game_ids": ["same"], "record_ids": ["b"], "split": "test"}])

    def test_pool_respects_mode_version_and_build(self):
        query = record("q")
        valid = record("valid")
        algs = record("algs", mode="ALGS")
        version = record("version")
        version["map_version"] = "another_version"
        build = record("build")
        build["build"] = "known-build"
        library = [valid, algs, version, build]
        self.assertEqual([r["id"] for r in compatible_pool(library, query)], ["valid"])
        self.assertEqual([r["id"] for r in compatible_pool(library, query, True)], ["valid", "algs"])

    def test_query_rejects_source_game_alias_leakage(self):
        with self.assertRaisesRegex(ValueError, "source game"):
            evaluate_queries([record("a", ["a", "shared"])], [record("q", ["q", "shared"])], 1)

    def test_center_metrics_candidate_dedup_and_boundary_coverage(self):
        query = record("query")
        query["final_ring"] = {"x": 9000, "y": 8000, "r": 500}
        nearest = record("nearest")
        nearest["final_ring"] = {"x": 9500, "y": 8000, "r": 700}
        duplicate = record("duplicate")
        duplicate["final_ring"] = copy.deepcopy(nearest["final_ring"])
        farther = record("farther")
        farther["known_rings"][0]["x"] += 200
        farther["final_ring"] = {"x": 9000, "y": 8000, "r": 700}
        rows = evaluate_queries([nearest, duplicate, farther], [query], 1)
        self.assertEqual(rows[0]["candidate_center_errors"], [500, 0])
        self.assertTrue(rows[0]["exact_input_seen"])
        self.assertTrue(rows[0]["hits"]["1"])
        metrics = summarize(rows)
        self.assertEqual(metrics["top1_center_error"]["median"], 500)
        self.assertEqual(metrics["top5_oracle_center_error"]["median"], 0)
        self.assertEqual(metrics["latest_known_center_error"]["median"], 1000)

    def test_abstention_counts_as_no_coverage(self):
        rows = evaluate_queries([], [record("query")], 1)
        metrics = summarize(rows)
        self.assertEqual(metrics["queries"], 1)
        self.assertEqual(metrics["abstentions"], 1)
        self.assertEqual(metrics["coverage"]["5"], 0)
        self.assertIsNone(metrics["top1_center_error"]["median"])

    def test_continuous_stage_validation_and_later_circle_disambiguation(self):
        query = record("query")
        second = {"stage": 2, "x": 8000, "y": 8000, "r": 2400}
        query["known_rings"].append(second)
        correct = record("z_correct")
        correct["known_rings"].append(copy.deepcopy(second))
        wrong = record("a_wrong")
        wrong["known_rings"].append({**second, "x": 9000})
        wrong["final_ring"]["x"] = 9500
        self.assertEqual(evaluate_queries([wrong, correct], [query], 1)[0]["candidate_ids"][0], "a_wrong")
        self.assertEqual(evaluate_queries([wrong, correct], [query], 2)[0]["candidate_ids"][0], "z_correct")
        broken = copy.deepcopy(query)
        broken["known_rings"][1]["stage"] = 3
        with self.assertRaises(ValueError):
            evaluate_queries([correct], [broken], 2)

    def test_percentiles_have_explicit_linear_interpolation(self):
        self.assertEqual(percentile([0, 100], .9), 90)
        self.assertEqual(percentile([100], .5), 100)
        self.assertIsNone(percentile([], .5))


if __name__ == "__main__":
    unittest.main()
