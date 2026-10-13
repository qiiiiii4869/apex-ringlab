"""Exact SIFT matching with bounded distance blocks and candidate-only reverse checks."""
from __future__ import annotations

import cv2
import numpy as np

BLOCK_ROWS = 128


def quantized_sift(descriptors):
    # OpenCV's default float SIFT descriptors contain quantized byte values.
    # For 128 such values, squared distances are exact integers below 2**24.
    return (descriptors.dtype == np.float32 and descriptors.ndim == 2
            and descriptors.shape[1] == 128 and np.isfinite(descriptors).all()
            and (descriptors >= 0).all() and (descriptors <= 255).all()
            and np.equal(descriptors, np.floor(descriptors)).all())


def nearest(descriptors, reference, count):
    """Return stable exact nearest indices and L2 distances for quantized SIFT."""
    reference_norm = np.sum(reference * reference, axis=1)
    transposed = np.ascontiguousarray(reference.T)
    indices = np.empty((len(descriptors), count), dtype=np.int32)
    distances = np.empty((len(descriptors), count), dtype=np.float32)
    for start in range(0, len(descriptors), BLOCK_ROWS):
        block = descriptors[start:start + BLOCK_ROWS]
        squared = block @ transposed
        squared *= -2
        squared += np.sum(block * block, axis=1)[:, None]
        squared += reference_norm[None, :]
        np.maximum(squared, 0, out=squared)
        rows = np.arange(len(block))
        for rank in range(count):
            selected = np.argmin(squared, axis=1)
            indices[start:start + len(block), rank] = selected
            distances[start:start + len(block), rank] = np.sqrt(squared[rows, selected])
            squared[rows, selected] = np.inf
    return indices, distances


def sift_matches(descriptors, reference, ratio=.78):
    """Keep the original ratio and mutual nearest rules, without approximate search."""
    if not len(descriptors) or len(reference) < 2:
        return []
    if quantized_sift(descriptors) and quantized_sift(reference):
        indices, distances = nearest(descriptors, reference, 2)
        good = [cv2.DMatch(i, int(indices[i, 0]), 0, float(distances[i, 0]))
                for i in range(len(descriptors))
                if float(distances[i, 0]) < ratio * float(distances[i, 1])]
        if not good:
            return []
        candidates = np.unique([match.trainIdx for match in good])
        reverse, _ = nearest(reference[candidates], descriptors, 1)
        back = dict(zip(candidates, reverse[:, 0]))
    else:
        # Other descriptor representations retain OpenCV's original distance path.
        matcher = cv2.BFMatcher(cv2.NORM_L2)
        pairs = matcher.knnMatch(descriptors, reference, k=2)
        good = [a for pair in pairs if len(pair) == 2 for a, b in [pair]
                if a.distance < ratio * b.distance]
        if not good:
            return []
        candidates = np.unique([match.trainIdx for match in good])
        back = {int(candidates[m.queryIdx]): m.trainIdx
                for m in matcher.match(reference[candidates], descriptors)}
    return [match for match in good if back[match.trainIdx] == match.queryIdx]
