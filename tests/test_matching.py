import unittest
import cv2
import numpy as np
from threadpoolctl import threadpool_limits
from ringlab.matching import BLOCK_ROWS, nearest, sift_matches


def original_matches(query, reference, ratio=.78):
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(query, reference, k=2)
    good = [a for pair in pairs if len(pair) == 2 for a, b in [pair]
            if a.distance < ratio * b.distance]
    reverse = {m.queryIdx: m.trainIdx for m in matcher.match(reference, query)}
    return [(m.queryIdx, m.trainIdx, m.distance) for m in good if reverse[m.trainIdx] == m.queryIdx]


class MatchingTests(unittest.TestCase):
    def test_quantized_distances_and_block_boundaries_match_opencv(self):
        rng = np.random.default_rng(891)
        query = rng.integers(0, 256, size=(BLOCK_ROWS + 3, 128)).astype(np.float32)
        reference = rng.integers(0, 256, size=(150, 128)).astype(np.float32)
        with threadpool_limits(limits=2, user_api='blas'):
            indices, distances = nearest(query, reference, 2)
        expected = cv2.BFMatcher(cv2.NORM_L2).knnMatch(query, reference, k=2)
        for i, pair in enumerate(expected):
            self.assertEqual(indices[i].tolist(), [m.trainIdx for m in pair])
            np.testing.assert_allclose(distances[i], [m.distance for m in pair], rtol=1e-7)

    def test_mutual_matches_and_ties_preserve_original_selection(self):
        rng = np.random.default_rng(31)
        query = rng.integers(10, 200, size=(150, 128)).astype(np.float32)
        query[1] = query[0]
        reference = query[:100].copy()
        reference[-1] = reference[-2]
        reference[10:20] += 1
        with threadpool_limits(limits=2, user_api='blas'):
            actual = [(m.queryIdx, m.trainIdx, m.distance) for m in sift_matches(query, reference)]
        self.assertEqual(actual, original_matches(query, reference))

    def test_non_quantized_descriptors_keep_exact_opencv_fallback(self):
        rng = np.random.default_rng(12)
        query = rng.random((50, 128), dtype=np.float32)
        reference = query[:30].copy()
        actual = [(m.queryIdx, m.trainIdx, m.distance) for m in sift_matches(query, reference)]
        self.assertEqual(actual, original_matches(query, reference))

    def test_empty_and_insufficient_reference_return_no_ratio_matches(self):
        self.assertEqual(sift_matches(np.zeros((0,128),np.float32),np.zeros((2,128),np.float32)), [])
        self.assertEqual(sift_matches(np.zeros((3,128),np.float32),np.zeros((1,128),np.float32)), [])
