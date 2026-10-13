const SIZE = 16384;

export function validRing(ring) {
  return ["x", "y", "r"].every(key => ring[key] !== "" && ring[key] !== undefined && Number.isFinite(Number(ring[key])))
    && Number(ring.x) >= 0 && Number(ring.x) <= SIZE
    && Number(ring.y) >= 0 && Number(ring.y) <= SIZE
    && Number(ring.r) > 0 && Number(ring.r) <= SIZE;
}

export function fitCircle(points) {
  if (!Array.isArray(points) || points.length !== 3 || points.some(point => !Number.isFinite(point.x) || !Number.isFinite(point.y))) {
    throw new Error("请选择三个有效边界点。");
  }
  const [a, b, c] = points;
  const denominator = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y));
  if (Math.abs(denominator) < 10000) throw new Error("三个点过于接近或接近直线，请选择更分散的边界点。");
  const aa = a.x * a.x + a.y * a.y, bb = b.x * b.x + b.y * b.y, cc = c.x * c.x + c.y * c.y;
  const x = (aa * (b.y - c.y) + bb * (c.y - a.y) + cc * (a.y - b.y)) / denominator;
  const y = (aa * (c.x - b.x) + bb * (a.x - c.x) + cc * (b.x - a.x)) / denominator;
  const ring = {x, y, r: Math.hypot(x - a.x, y - a.y)};
  if (!validRing(ring)) throw new Error("取点拟合的圈超出范围，请检查边界位置。");
  return ring;
}
