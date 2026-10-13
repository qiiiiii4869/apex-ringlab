import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from ringlab.vision import MAP_PIXELS, MAX_IMAGE_BYTES, ScreenshotRecognizer, bounds_homography, decode_image


def image_bytes(image, format="PNG"):
    buffer = BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


class VisionTests(unittest.TestCase):
    def test_real_user_screenshot_registers_and_finds_both_dim_rings(self):
        raw = (Path(__file__).parent / "fixtures" / "worlds-edge-user.png").read_bytes()
        recognizer = ScreenshotRecognizer()
        result = recognizer.recognize(raw)
        self.assertEqual(result["status"], "aligned")
        self.assertEqual(result["quality"]["method"], "sift_homography")
        # Approximate centers/radii independently marked from the supplied image.
        for x, y, radius in ((9750, 7350, 4900), (8550, 7680, 2335)):
            ring = min(result["candidates"], key=lambda c: abs(c["r"] - radius))
            self.assertAlmostEqual(ring["x"], x, delta=150)
            self.assertAlmostEqual(ring["y"], y, delta=150)
            self.assertAlmostEqual(ring["r"], radius, delta=130)
            self.assertIsNone(ring["stage"])
        self.assertEqual(len(result["candidates"]), 2)

    def test_downsized_compressed_screenshot_still_finds_two_rings(self):
        raw = (Path(__file__).parent / "fixtures" / "worlds-edge-user.png").read_bytes()
        with Image.open(BytesIO(raw)) as image:
            smaller = image.convert("RGB").resize((888, 799))
            compressed = image_bytes(smaller, "JPEG")
        result = ScreenshotRecognizer().recognize(compressed)
        self.assertEqual(result["status"], "aligned")
        for radius in (4900, 2335):
            self.assertTrue(any(abs(c["r"] - radius) < 150 for c in result["candidates"]))

    def test_decode_checks_actual_format_size_and_dimensions(self):
        for raw in (b"not an image", b"x" * (MAX_IMAGE_BYTES + 1), image_bytes(Image.new("RGB", (300, 300)), "GIF"),
                    image_bytes(Image.new("RGB", (100, 100)))):
            with self.assertRaises(ValueError):
                decode_image(raw)
        image = decode_image(image_bytes(Image.new("RGB", (300, 400))))
        self.assertEqual(image.shape, (400, 300, 3))

    def test_manual_bounds_map_screen_corners_to_whole_map(self):
        matrix = bounds_homography({"x0": 200, "y0": 100, "x1": 1000, "y1": 900}, 1200, 1000)
        points = np.float32([[[200, 100], [1000, 900], [600, 500]]])
        transformed = cv2.perspectiveTransform(points, matrix)[0]
        np.testing.assert_allclose(transformed, [[0, 0], [MAP_PIXELS, MAP_PIXELS], [MAP_PIXELS / 2, MAP_PIXELS / 2]], atol=.01)

    def test_bad_bounds_are_rejected(self):
        for bounds in ({"x0": -1, "y0": 0, "x1": 800, "y1": 800},
                       {"x0": 0, "y0": 0, "x1": 10, "y1": 10},
                       {"x0": 0, "y0": 0, "x1": 800, "y1": 200},
                       {"x0": float("nan"), "y0": 0, "x1": 800, "y1": 800}):
            with self.assertRaises(ValueError):
                bounds_homography(bounds, 1000, 1000)

    def test_blank_image_requires_manual_registration_not_fake_circle(self):
        raw = image_bytes(Image.new("RGB", (512, 512)))
        recognizer = ScreenshotRecognizer()
        result = recognizer.recognize(raw)
        self.assertEqual(result["status"], "needs_map_bounds")
        self.assertEqual(result["candidates"], [])

    def test_manual_path_works_without_auto_matching_and_never_assigns_stages(self):
        canvas = np.zeros((MAP_PIXELS, MAP_PIXELS, 3), dtype=np.uint8)
        cv2.circle(canvas, (500, 500), 250, (255, 255, 255), 5)
        success, raw = cv2.imencode(".png", canvas)
        self.assertTrue(success)
        recognizer = ScreenshotRecognizer()
        with patch.object(recognizer, "auto_homography", side_effect=AssertionError("manual bounds must bypass matching")):
            result = recognizer.recognize(raw.tobytes(), {"x0": 0, "y0": 0, "x1": 1000, "y1": 1000})
        self.assertEqual(result["status"], "aligned")
        self.assertTrue(result["aligned_image"].startswith("data:image/jpeg;base64,"))
        self.assertTrue(result["candidates"])
        nearest = min(result["candidates"], key=lambda c: abs(c["r"] - 4096))
        self.assertAlmostEqual(nearest["r"], 4096, delta=120)
        self.assertIsNone(nearest["stage"])
        self.assertTrue(nearest["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
