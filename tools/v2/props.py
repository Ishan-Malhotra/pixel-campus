"""Prop sprites (depth-sorted objects): palms, trees, conifers, bushes, lamps, flags, benches.
Each prop: Canvas + anchor (base point, used for depth) + collision box (w, h) centred on the anchor."""
import math
import numpy as np
from px import Canvas, outer
import pal2 as P


def _shadow(c, cx, cy, rx, ry=3):
    m = c.ellipse(cx, cy, rx, ry)
    c.a[m] = (0, 0, 0, 60)


def _finish(c, ol):
    body = c.a[..., 3] > 100
    c.fill(outer(body) & (c.a[..., 3] < 100), ol)


def palm(variant=0):
    W, H = 44, 56
    c = Canvas(W, H)
    bx, by = 22, 53
    _shadow(c, bx + 3, by, 11)
    # curved segmented trunk
    lean = [-1, 1, 0][variant % 3]
    pts = []
    for i in range(30):
        t = i / 29
        pts.append((bx + lean * 4 * t * t + 0.5, by - 2 - t * 30))
    for i, (x, y) in enumerate(pts):
        col = P.TRUNK['base'] if (i // 3) % 2 == 0 else P.TRUNK['sh']
        for dx in range(-2, 2):
            cc = P.TRUNK['hi'] if dx == -2 and (i // 3) % 2 == 0 else col
            c.px(x + dx, y, cc)
    trunk = c.a[..., 3] > 100
    c.fill(outer(trunk) & (c.a[..., 3] < 100), P.TRUNK['ol'])
    crown = (pts[-1][0], pts[-1][1] - 1)
    leaves = Canvas(W, H)
    angles = [200, 235, 270, 305, 340, 160, 20]
    for k, a in enumerate(angles):
        a = math.radians(a + variant * 7)
        L = 17 if k < 5 else 13
        for i in range(0, 60):
            t = i / 59
            x = crown[0] + math.cos(a) * L * t
            y = crown[1] + math.sin(a) * L * t + (t * t) * 9  # droop
            w = 2.6 * (1 - t) + 0.6
            for oy in range(-3, 4):
                for ox in range(-3, 4):
                    if ox * ox + oy * oy <= w * w:
                        X, Y = int(x + ox), int(y + oy)
                        top = oy < 0
                        col = P.PALM['hi'] if top and t < 0.8 else P.PALM['base'] if oy <= 1 else P.PALM['sh']
                        leaves.px(X, Y, col)
    _finish(leaves, P.PALM['ol'])
    # leaf midribs & coconuts
    for k in range(3):
        leaves.px(crown[0] - 1 + k, crown[1] + 1, P.TRUNK['sh'])
    c.paste(leaves, 0, 0)
    for dx, dy in ((-2, 2), (1, 2), (-1, 3)):
        c.px(crown[0] + dx, crown[1] + dy, (120, 80, 40))
    return c, bx, by, (8, 5)


def round_tree(variant=0):
    W, H = 44, 52
    c = Canvas(W, H)
    bx, by = 22, 49
    _shadow(c, bx + 3, by, 14)
    for y in range(by - 14, by + 1):
        for x in range(bx - 3, bx + 3):
            c.px(x, y, P.TRUNK['hi'] if x == bx - 3 else P.TRUNK['base'] if x < bx + 1 else P.TRUNK['sh'])
    c.fill(outer(c.a[..., 3] > 100) & (c.a[..., 3] < 100) & (c.yy < by - 2), P.TRUNK['ol'])
    can = Canvas(W, H)
    rnd = np.random.default_rng(variant + 11)
    cx, cy = bx, by - 28
    blobs = [(cx + rnd.integers(-8, 9), cy + rnd.integers(-7, 6), rnd.integers(8, 11)) for _ in range(6)] + [(cx, cy, 14)]
    m = np.zeros((H, W), bool)
    for x, y, r in blobs:
        m |= can.disk(x, y, r)
    lit = -(can.xx - cx) - (can.yy - cy) * 1.2
    can.fill(m & (lit <= -10), P.LEAF['sh'])
    can.fill(m & (lit > -10), P.LEAF['base'])
    can.fill(m & (lit > 10), P.LEAF['hi'])
    # leaf clumps
    for x, y, r in blobs[:-1]:
        arc = can.disk(x, y, r) & ~can.disk(x - 1, y - 2, r - 1) & m
        can.fill(arc & (lit < 6), P.LEAF['dk'])
    spk = m & (((can.xx * 3 + can.yy * 7) % 17) == 0) & (lit > -4)
    can.fill(spk, P.LEAF['hi'])
    _finish(can, P.LEAF['ol'])
    c.paste(can, 0, 0)
    return c, bx, by, (8, 5)


def conifer(variant=0):
    W, H = 32, 50
    c = Canvas(W, H)
    bx, by = 16, 47
    _shadow(c, bx + 2, by, 10)
    c.rect(bx - 2, by - 6, 4, 6, P.TRUNK['base'])
    top = by - 46 + variant
    for y in range(top, by - 5):
        t = (y - top) / (by - 5 - top)
        half = 2 + t * 12 + (1.5 if (y - top) % 10 >= 6 else 0) * t
        for x in range(W):
            dx = x - bx + 0.5
            if abs(dx) > half:
                continue
            col = P.CONIFER['base']
            if dx < -half * 0.3:
                col = P.CONIFER['hi']
            if dx > half * 0.45:
                col = P.CONIFER['sh']
            if (y - top) % 10 >= 8 and abs(dx) < half - 1:
                col = P.CONIFER['dk']
            c.px(x, y, col)
    _finish(c, P.CONIFER['ol'])
    return c, bx, by, (8, 5)


def bush(kind='green', variant=0):
    W, H = 20, 18
    c = Canvas(W, H)
    bx, by = 10, 16
    _shadow(c, bx + 2, by, 8, 2)
    m = c.ellipse(bx, by - 6, 8, 6.5) | c.disk(bx - 3, by - 9, 4.5) | c.disk(bx + 3, by - 9, 4.5)
    lit = -(c.xx - bx) - (c.yy - (by - 7)) * 1.3
    c.fill(m, P.LEAF['base'])
    c.fill(m & (lit > 4), P.LEAF['hi'])
    c.fill(m & (lit < -6), P.LEAF['sh'])
    if kind != 'green':
        col = {'pink': P.FLOWERS[0], 'purple': P.FLOWERS[3], 'yellow': P.FLOWERS[1], 'white': P.FLOWERS[2]}[kind]
        dots = m & (((c.xx * 5 + c.yy * 3 + variant) % 7) == 0)
        c.fill(dots, col)
        c.fill(shift_down(dots) & m & ~dots, P.LEAF['dk'])
    _finish(c, P.LEAF['ol'])
    return c, bx, by, (10, 4)


def shift_down(m):
    o = np.zeros_like(m)
    o[1:] = m[:-1]
    return o


def lamp():
    W, H = 12, 34
    c = Canvas(W, H)
    bx, by = 6, 32
    _shadow(c, bx + 2, by, 4, 1.5)
    c.rect(bx - 2, by - 3, 4, 3, P.METAL['sh'])
    c.rect(bx - 1, by - 24, 2, 21, P.METAL['base'])
    c.rect(bx - 1, by - 24, 1, 21, P.METAL['hi'])
    m = c.disk(bx - 0.5, by - 27, 3.6)
    c.fill(m, (252, 252, 236))
    c.fill(m & (c.xx > bx) & (c.yy > by - 27), (220, 220, 200))
    c.rect(bx - 3, by - 23, 6, 1, P.METAL['sh'])
    _finish(c, P.METAL['ol'])
    return c, bx, by, (4, 3)


def flag(color_i=0):
    W, H = 18, 36
    c = Canvas(W, H)
    bx, by = 4, 34
    _shadow(c, bx + 2, by, 3, 1.5)
    c.rect(bx - 1, by - 30, 2, 30, P.METAL['base'])
    c.rect(bx - 1, by - 30, 1, 30, P.METAL['hi'])
    c.px(bx - 1, by - 32, P.METAL['hi']); c.px(bx, by - 32, P.METAL['base'])
    col = P.FLAGS[color_i % len(P.FLAGS)]
    sh = tuple(int(v * 0.78) for v in col)
    for x in range(10):
        wave = int(round(math.sin(x / 2.2) * 1))
        for y in range(7):
            c.px(bx + 1 + x, by - 30 + y + wave, col if y < 5 else sh)
    _finish(c, P.METAL['ol'])
    return c, bx, by, (3, 3)


def bench():
    W, H = 22, 14
    c = Canvas(W, H)
    bx, by = 11, 12
    _shadow(c, bx + 2, by, 9, 2)
    c.rect(2, 3, 18, 3, P.TRUNK['hi'])
    c.rect(2, 6, 18, 2, P.TRUNK['base'])
    c.rect(2, 8, 18, 1, P.TRUNK['sh'])
    c.rect(3, 9, 2, 3, P.METAL['sh']); c.rect(17, 9, 2, 3, P.METAL['sh'])
    _finish(c, P.TRUNK['ol'])
    return c, bx, by, (16, 4)


def sign():
    W, H = 22, 22
    c = Canvas(W, H)
    bx, by = 11, 20
    _shadow(c, bx + 2, by, 8, 2)
    c.rect(4, 15, 2, 5, P.TRUNK['sh']); c.rect(16, 15, 2, 5, P.TRUNK['sh'])
    c.rect(2, 4, 18, 11, P.TRUNK['base'])
    c.rect(2, 4, 18, 2, P.TRUNK['hi'])
    c.rect(4, 7, 14, 6, (244, 236, 208))
    for y in (8, 10):
        c.rect(6, y, 10, 1, (150, 140, 120))
    _finish(c, P.TRUNK['ol'])
    return c, bx, by, (14, 4)


def build_all():
    """name -> (Canvas, ax, ay, (cw, ch))"""
    out = {}
    for v in range(3):
        out[f'palm{v}'] = palm(v)
        out[f'tree{v}'] = round_tree(v)
        out[f'conifer{v}'] = conifer(v)
    for k in ('green', 'pink', 'purple', 'yellow', 'white'):
        out[f'bush_{k}'] = bush(k)
    out['lamp'] = lamp()
    for i in range(len(P.FLAGS)):
        out[f'flag{i}'] = flag(i)
    out['bench'] = bench()
    out['sign'] = sign()
    return out
