"""Small pixel-art helpers shared by the v2 tools (numpy RGBA canvases, masks, outlines)."""
import numpy as np

T = 16  # tile size in px


def shift(m, dx, dy):
    """Shift a 2D array by (dx, dy) pixels, filling with zeros/False."""
    o = np.zeros_like(m)
    H, W = m.shape[:2]
    if abs(dx) >= W or abs(dy) >= H:
        return o
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    o[yd, xd] = m[ys, xs]
    return o


def edge(m):
    """Pixels of mask m that touch a non-m 4-neighbour (inner outline)."""
    return m & ~(shift(m, 1, 0) & shift(m, -1, 0) & shift(m, 0, 1) & shift(m, 0, -1))


def outer(m):
    """Pixels just outside mask m (4-neighbour ring)."""
    return (shift(m, 1, 0) | shift(m, -1, 0) | shift(m, 0, 1) | shift(m, 0, -1)) & ~m


def dilate(m, r):
    o = m.copy()
    for k in range(1, r + 1):
        o |= shift(m, k, 0) | shift(m, -k, 0)
    p = o.copy()
    for k in range(1, r + 1):
        p |= shift(o, 0, k) | shift(o, 0, -k)
    return p


def erode(m, r):
    return ~dilate(~m, r)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)
        self.yy, self.xx = np.mgrid[0:h, 0:w]

    def fill(self, mask, c, alpha=255):
        self.a[mask, :3] = c
        self.a[mask, 3] = alpha

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x, :3] = c
            self.a[y, x, 3] = 255

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1, :3] = c
            self.a[y0:y1, x0:x1, 3] = 255

    def rmask(self, x, y, w, h):
        return (self.xx >= x) & (self.xx < x + w) & (self.yy >= y) & (self.yy < y + h)

    def disk(self, cx, cy, r):
        return (self.xx - cx) ** 2 + (self.yy - cy) ** 2 <= r * r

    def ellipse(self, cx, cy, rx, ry):
        return ((self.xx - cx) / rx) ** 2 + ((self.yy - cy) / ry) ** 2 <= 1

    def darken(self, mask, k):
        self.a[mask, :3] = (self.a[mask, :3] * k).astype(np.uint8)

    def outline(self, c, src=None):
        """Draw a 1px outline around the opaque pixels (or a given mask)."""
        m = self.a[..., 3] > 0 if src is None else src
        self.fill(outer(m), c)

    def paste(self, other, x, y):
        """Alpha-over paste of another Canvas/array at (x, y)."""
        arr = other.a if isinstance(other, Canvas) else other
        h, w = arr.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        src = arr[y0 - y:y1 - y, x0 - x:x1 - x]
        dst = self.a[y0:y1, x0:x1]
        al = src[..., 3:4].astype(np.float32) / 255
        dst[..., :3] = (src[..., :3] * al + dst[..., :3] * (1 - al)).astype(np.uint8)
        dst[..., 3] = np.maximum(dst[..., 3], src[..., 3])


def h32(*a):
    import hashlib
    return int(hashlib.md5(repr(a).encode()).hexdigest()[:8], 16)
