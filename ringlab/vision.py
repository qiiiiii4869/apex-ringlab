"""Experimental screenshot registration and circle suggestions, kept in memory."""
from __future__ import annotations

import base64
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .data import COORD_SIZE, ROOT
from .matching import sift_matches

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAP_PIXELS = 1000


def decode_image(raw):
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("请选择不超过 8 MB 的 JPG 或 PNG 截图")
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ("JPEG", "PNG"):
                raise ValueError("截图只支持 JPG 或 PNG")
            if image.width * image.height > MAX_PIXELS or min(image.size) < 256:
                raise ValueError("图片至少为 256×256，且不能超过 2,000 万像素")
            image.load()
            array = np.array(ImageOps.exif_transpose(image).convert("RGB"))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("无法读取这张图片，请换用完整的 JPG 或 PNG 截图") from error
    return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)


def bounds_homography(bounds, width, height):
    if not isinstance(bounds, dict):
        raise ValueError("请框选截图中的完整地图区域")
    try:
        values = np.array([bounds[key] for key in ("x0", "y0", "x1", "y1")], dtype=float)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("地图区域坐标无效") from error
    if not np.isfinite(values).all():
        raise ValueError("地图区域坐标必须是有限数字")
    x0, y0, x1, y1 = values
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and min(x1 - x0, y1 - y0) >= 128):
        raise ValueError("请在图片内框选至少 128 像素宽高的完整地图")
    ratio = (x1 - x0) / (y1 - y0)
    if not .75 <= ratio <= 1.33:
        raise ValueError("世界尽头完整地图区域应接近正方形，请重新框选")
    source = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    destination = np.float32([[0, 0], [MAP_PIXELS, 0], [MAP_PIXELS, MAP_PIXELS], [0, MAP_PIXELS]])
    return cv2.getPerspectiveTransform(source, destination)


class ScreenshotRecognizer:
    def __init__(self, base_path=ROOT / "web" / "assets" / "worlds-edge.jpg"):
        raw = base_path.read_bytes()  # cv2.imread does not reliably accept Windows Unicode paths.
        base = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if base is None:
            raise ValueError("无法读取世界尽头底图")
        self.base = cv2.resize(base, (MAP_PIXELS, MAP_PIXELS))
        orb = cv2.ORB_create(nfeatures=3000, fastThreshold=12)
        self.keypoints, self.descriptors = orb.detectAndCompute(cv2.cvtColor(self.base, cv2.COLOR_BGR2GRAY), None)
        self.clahe = cv2.createCLAHE(clipLimit=3, tileGridSize=(8, 8))
        self.sift = cv2.SIFT_create(nfeatures=6000, contrastThreshold=.015)
        self.sift_keypoints, self.sift_descriptors = self.sift.detectAndCompute(
            self.clahe.apply(cv2.cvtColor(self.base, cv2.COLOR_BGR2GRAY)), None)

    def auto_homography(self, image):
        # HUD labels, orange damage tint and unequal screenshot scaling defeat ORB.
        # Keep its fast path, then match contrast-normalized SIFT features.
        for method in ("orb", "sift"):
            matrix, quality = self.feature_homography(image, method)
            if matrix is not None:
                return matrix, quality
        return None, quality

    def feature_homography(self, image, method):
        scale = min(1, 1600 / max(image.shape[:2]))
        small = cv2.resize(image, None, fx=scale, fy=scale) if scale < 1 else image
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if method == "sift":
            keypoints, descriptors = self.sift.detectAndCompute(self.clahe.apply(gray), None)
            base_keypoints, base_descriptors, norm, ratio = self.sift_keypoints, self.sift_descriptors, cv2.NORM_L2, .78
        else:
            keypoints, descriptors = cv2.ORB_create(nfeatures=4000, fastThreshold=12).detectAndCompute(gray, None)
            base_keypoints, base_descriptors, norm, ratio = self.keypoints, self.descriptors, cv2.NORM_HAMMING, .72
        quality = {"method": method + "_homography", "matched_features": 0, "inliers": 0}
        if descriptors is None or base_descriptors is None:
            return None, quality
        if method == "sift":
            good = sift_matches(descriptors, base_descriptors, ratio)
        else:
            matcher = cv2.BFMatcher(norm)
            pairs = matcher.knnMatch(descriptors, base_descriptors, k=2)
            good = [a for pair in pairs if len(pair) == 2 for a, b in [pair] if a.distance < ratio * b.distance]
        quality["matched_features"] = len(good)
        if len(good) < 16:
            return None, quality
        source = np.float32([keypoints[m.queryIdx].pt for m in good])
        destination = np.float32([base_keypoints[m.trainIdx].pt for m in good])
        homography, mask = cv2.findHomography(source, destination, cv2.RANSAC, 4)
        if homography is None or mask is None or not np.isfinite(homography).all():
            return None, quality
        inliers = mask.ravel().astype(bool)
        quality["inliers"] = int(inliers.sum())
        if quality["inliers"] < 12 or inliers.mean() < .3:
            return None, quality
        spread = np.ptp(destination[inliers], axis=0)
        if min(spread) < MAP_PIXELS * .35:
            return None, quality
        homography = homography @ np.diag([scale, scale, 1.0])
        if abs(np.linalg.det(homography)) < 1e-10:
            return None, quality
        corners = np.float32([[[0, 0], [MAP_PIXELS, 0], [MAP_PIXELS, MAP_PIXELS], [0, MAP_PIXELS]]])
        polygon = cv2.perspectiveTransform(corners, np.linalg.inv(homography))[0]
        h, w = image.shape[:2]
        if not np.isfinite(polygon).all() or not cv2.isContourConvex(polygon.astype(np.float32)):
            return None, quality
        if abs(cv2.contourArea(polygon)) < w * h * .08:
            return None, quality
        if (polygon[:, 0].min() < -.2 * w or polygon[:, 0].max() > 1.2 * w
                or polygon[:, 1].min() < -.2 * h or polygon[:, 1].max() > 1.2 * h):
            return None, quality
        quality["map_corners"] = polygon.tolist()
        return homography, quality

    @staticmethod
    def circle_suggestions(aligned):
        gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        detected = []
        # ALT checks aligned gradient directions, including dark color boundaries
        # and translucent grey circles. Separate scales also retain concentric rings.
        for low, high in ((45, 125), (110, 220), (205, 370), (355, 700)):
            circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT_ALT, dp=1.5, minDist=30,
                                      param1=80, param2=.8, minRadius=low, maxRadius=high)
            if circles is not None:
                detected.extend(circles[0])
        edges = cv2.Canny(gray, 25, 65)
        nearby = cv2.dilate(edges, np.ones((7, 7), np.uint8))
        suggestions = []
        angles = np.linspace(0, 2 * np.pi, 360, endpoint=False)
        for x, y, radius in detected[:100]:
            xs = np.rint(x + radius * np.cos(angles)).astype(int)
            ys = np.rint(y + radius * np.sin(angles)).astype(int)
            valid = (xs >= 0) & (xs < MAP_PIXELS) & (ys >= 0) & (ys < MAP_PIXELS)
            if valid.sum() < 100:
                continue
            supported = nearby[ys[valid], xs[valid]] > 0
            support = float(supported.mean())
            # Do not require bright pixels: an active ring can be an orange/dark
            # transition, and an upcoming ring may be a translucent filled disk.
            if support < .55 or valid.mean() < .4:
                continue
            candidate = {"x": float(x * COORD_SIZE / MAP_PIXELS), "y": float(y * COORD_SIZE / MAP_PIXELS),
                         "r": float(radius * COORD_SIZE / MAP_PIXELS), "stage": None,
                         "arc_support": round(support, 3), "requires_confirmation": True}
            if not any(np.hypot(candidate["x"] - c["x"], candidate["y"] - c["y"]) < 300
                       and abs(candidate["r"] - c["r"]) < 250 for c in suggestions):
                suggestions.append(candidate)
        return sorted(suggestions, key=lambda c: -c["r"])[:6]

    def recognize(self, raw, bounds=None):
        image = decode_image(raw)
        h, w = image.shape[:2]
        if bounds is not None:
            homography = bounds_homography(bounds, w, h)
            quality = {"method": "manual_bounds", "requires_confirmation": True}
        else:
            homography, quality = self.auto_homography(image)
        if homography is None:
            return {"status": "needs_map_bounds", "width": w, "height": h, "quality": quality, "candidates": [],
                    "message": "未可靠定位地图。请在截图中框选完整世界尽头地图；只截取局部地图无法正确换算。"}
        aligned = cv2.warpPerspective(image, homography, (MAP_PIXELS, MAP_PIXELS))
        candidates = self.circle_suggestions(aligned)
        success, encoded = cv2.imencode(".jpg", aligned, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            raise ValueError("截图预览生成失败")
        return {"status": "aligned", "width": w, "height": h, "quality": quality,
                "aligned_image": "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii"),
                "candidates": candidates, "message": f"已对齐地图，找到 {len(candidates)} 个安全区圆弧。请核对预览并选择圈次。"}
