import unittest
import numpy as np
from ringlab.probability import HistoricalProbability


class ProbabilityTests(unittest.TestCase):
    def test_translation_and_scale_invariance_and_overlapping_events(self):
        estimator = HistoricalProbability.__new__(HistoricalProbability)
        estimator.residuals = {1: np.array([[0, 0], [.1, 0], [-.1, 0], [0, .1]])}
        observed = [{"r": 1000}]
        model = {"x": 500, "y": 500, "r": 250}
        first = estimator.estimate(model, model, observed)
        other = {"x": 600, "y": 500, "r": 250}
        second = estimator.estimate(other, model, observed)
        translated = estimator.estimate({"x": 3200, "y": 3000, "r": 500},
                                        {"x": 3000, "y": 3000, "r": 500}, [{"r": 2000}])
        self.assertEqual(second, translated)
        self.assertGreater(first["value"] + second["value"], 1)
        self.assertLess(first["value"], 1)
        self.assertGreater(first["interval_95"][1], first["interval_95"][0])

    def test_missing_or_overlapping_reference_data_is_rejected(self):
        for ids in ([], ["train"], ["test"]):
            manifest = {"validation_ids": ids, "training_ids": ["train"], "reserved_test_ids": ["test"]}
            with self.assertRaises(ValueError):
                HistoricalProbability([], manifest, {})


if __name__ == "__main__":
    unittest.main()
