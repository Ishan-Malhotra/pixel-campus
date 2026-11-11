"""Main Building + Rotunda map, laid out to match art/reference_main.png tile-for-tile.

All positions below are in REFERENCE TILE coordinates: the reference image is 1024x687 px = 64 x 43 tiles
of 16 px. (0,0) is the reference's top-left. The playable map adds a margin around that frame
(OX/OY tiles) so the edges and the Rotunda's south side can be completed.

Everything static is painted into one ground image, then sliced into deduplicated 16x16 tiles
(tileset + Tiled JSON). Props are depth-sorted sprites. Collision is an 8 px grid.

Usage (from repo root):  python3 tools/v2/map_main.py
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from px import Canvas, T, shift, edge, outer, dilate, erode, h32
import pal2 as P
import props as PR

OX, OY = 4, 3                       # margin (tiles) left/top of the reference frame
MW, MH = 64 + 2 * OX, 43 + OY + 9   # 72 x 55 tiles
W, H = MW * T, MH * T
OUT_GAME = 'game/public'
DEBUG = 'data/debug'
os.makedirs(f'{OUT_GAME}/maps', exist_ok=True)
os.makedirs(f'{OUT_GAME}/tiles', exist_ok=True)
os.makedirs(DEBUG, exist_ok=True)

g = Canvas(W, H)
xx, yy = g.xx, g.yy
solid = np.zeros((H, W), bool)
props, zones = [], []


def X(v):
    """reference tile x -> map px"""
    return int(round((v + OX) * T))


def Y(v):
    return int(round((v + OY) * T))


def L(v):
    """length in tiles -> px"""
    return int(round(v * T))


def R(x0, y0, x1, y1):
    """mask of a rectangle given in reference tiles"""
    return (xx >= X(x0)) & (xx < X(x1)) & (yy >= Y(y0)) & (yy < Y(y1))


def poly_mask(points, width_t):
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    pts = [(X(a), Y(b)) for a, b in points]
    w = L(width_t)
    d.line(pts, fill=255, width=w, joint='curve')
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=255)
    return np.array(im) > 0


def blob(circles):
    m = np.zeros((H, W), bool)
    for cx, cy, r in circles:
        m |= ((xx - X(cx)) ** 2 + (yy - Y(cy)) ** 2) <= L(r) ** 2
    return m


def smooth(points, n=6):
    """Catmull-Rom through points (reference tiles)."""
    out = []
    p = [points[0]] + list(points) + [points[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(2)))
    out.append(points[-1])
    return out


def offset(points, d):
    """offset a polyline (reference tiles) by d tiles along its left normal"""
    out = []
    for i, (x, y) in enumerate(points):
        a = points[max(0, i - 1)]; b = points[min(len(points) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        out.append((x + dy / n * d, y - dx / n * d))
    return out


def put(name, x, y):
    """place a prop at reference tile coordinates (base point)"""
    props.append((name, X(x), Y(y)))


# ===================================================================== painters
def paint_grass(mask, pal):
    g.fill(mask, pal['base'])
    for ty in range(MH):
        for tx in range(MW):
            v = h32('tuft', tx, ty) % 100
            if v > 45:
                continue
            x0, y0 = tx * T + 2 + v % 10, ty * T + 3 + (v * 7) % 9
            pts = [(0, 1, 'sh'), (1, 0, 'hi'), (2, 1, 'sh'), (3, 0, 'hi'), (4, 1, 'sh')] if v < 25 else [(0, 0, 'hi'), (1, 1, 'sh')]
            for dx, dy, k in pts:
                Xp, Yp = x0 + dx, y0 + dy
                if 0 <= Xp < W and 0 <= Yp < H and mask[Yp, Xp]:
                    g.a[Yp, Xp, :3] = pal[k]


def paint_bordered(mask, pal, speck=True):
    g.fill(mask, pal['base'])
    if speck:
        g.fill(mask & (((xx * 7 + yy * 13) % 29) == 0), pal['sh'])
        g.fill(mask & (((xx * 5 + yy * 11) % 31) == 0), pal['hi'])
    e = edge(mask)
    g.fill(edge(mask & ~e) & mask, pal['sh'])
    g.fill(e, pal['ol'])


def paint_tall(mask):
    g.fill(mask, P.TALL['base'])
    g.fill(mask & (((xx % 6) == 2) & ((yy % 5) < 2)), P.TALL['hi'])
    g.fill(mask & (((xx % 6) == 3) & ((yy % 5) == 2)), P.TALL['sh'])
    g.fill(mask & (((xx + yy * 3) % 11) == 0), P.TALL['dk'])
    g.fill(mask & (((xx * 3 + yy) % 19) == 0), (232, 232, 120))
    g.fill(edge(mask), P.TALL['ol'])
    g.fill(shift(edge(mask), 0, 1) & ~mask, P.LAWN['dk'])


def paint_plants(x0, y0, x1, y1, dx=1.0, dy=1.0):
    """rows of leafy vegetable plants (ground decals with outline)"""
    m = np.zeros((H, W), bool)
    lit = np.zeros((H, W), bool)
    for py in np.arange(y0 + 0.5, y1, dy):
        for px_ in np.arange(x0 + 0.5, x1, dx):
            cx, cy = X(px_), Y(py)
            leaf = ((np.abs(xx - cx) + np.abs(yy - cy) * 1.3) <= 6) | (((xx - cx + 3) ** 2 + (yy - cy - 1) ** 2) <= 9) | (((xx - cx - 3) ** 2 + (yy - cy - 1) ** 2) <= 9)
            m |= leaf
            lit |= leaf & (yy < cy) & (xx <= cx)
    g.fill(m, P.LEAF['base'])
    g.fill(lit, P.LEAF['hi'])
    g.fill(m & shift(~m, 0, -1) & ~lit, P.LEAF['dk'])
    g.fill(outer(m), P.LEAF['ol'])
    return m


def paint_hedges(hm):
    H_FRONT = 5
    front = np.zeros_like(hm)
    for k in range(1, H_FRONT + 1):
        front |= shift(hm, 0, k)
    front &= ~hm
    g.fill(front, P.HEDGE['front'])
    g.fill(front & ~shift(front, 0, 1), P.HEDGE['dk'])
    g.fill(hm, P.HEDGE['base'])
    g.fill(hm & ~shift(hm, 0, 2), P.HEDGE['hi'])
    g.fill(hm & (((xx * 5 + yy * 3) % 13) == 0), P.HEDGE['hi'])
    g.fill(hm & (((xx * 7 + yy * 5) % 17) == 0), P.HEDGE['sh'])
    g.fill(outer(hm | front), P.HEDGE['ol'])
    solid[hm | front] = True


# ===================================================================== ground
paint_grass(np.ones((H, W), bool), P.GRASS)

# --- roads, measured from the reference: an outer lane all the way round, a second (inner) lane on the
#     west side separated by a slim hedge median, and a forecourt under the porch
RCX, RCY = 32.0, 33.0                      # rotunda centre (reference tiles)
RX, RY = 15.0, 11.4                        # rotunda outer ellipse radii (tiles) - drawn in perspective
ex, ey = (xx - X(RCX)) / L(1), (yy - Y(RCY)) / L(1)
s_rot = np.sqrt((ex / RX) ** 2 + (ey / RY) ** 2)
theta = (np.degrees(np.arctan2(ey / RY, ex / RX)) + 360) % 360     # 270 = north, 90 = south
R1 = smooth([(-6, 33.5), (0, 31.2), (5, 28.3), (9, 25.6), (13, 22.6), (17, 20.0), (21, 18.4), (25, 17.6), (29, 17.4),
             (32, 17.4), (36, 17.5), (40, 18.2), (44, 19.6), (48, 21.3), (52, 23.2), (56, 25.0), (60, 25.9), (70, 26.1)])
R2 = smooth([(30, 20.4), (26, 21.0), (22, 22.6), (18, 24.8), (14, 27.6), (10.6, 29.8), (5, 32.6), (0, 34.6), (-6, 36.5)])
outer_lane = poly_mask(R1, 3.0)
inner_lane = poly_mask(R2, 2.8)
road = outer_lane | inner_lane
road |= poly_mask(smooth([(-6, 35.0), (0, 33.0), (5, 30.6), (10.6, 27.2)]), 3.0)   # lanes merge west of the median
road |= R(26, 16.3, 38, 20.2)                                                      # forecourt under the porch
road = erode(dilate(road, 3), 3)
road &= ~(s_rot <= 1.0)
median = poly_mask(smooth([(10.8, 26.8), (14, 25.2), (18, 22.6), (22, 20.6), (26, 19.4), (28.2, 19.1)]), 0.8) & ~road

# --- lawns (teal) in front of the wings, the small west lawn, the right garden lawn
lawn = (R(4.7, 12.0, 24.0, 23) | R(39.6, 12.0, 59.2, 23) | R(1.6, 23.6, 8.0, 29.6)) & ~dilate(road, L(1.0))
lawn &= ~R(24, 12, 40, 23)
r1_xs = np.array([p[0] for p in R1]); r1_ys = np.array([p[1] for p in R1])
lane_y = np.interp(np.arange(W) / T - OX, r1_xs, r1_ys)          # outer-lane centre (ref tiles) per column
lawn &= yy < ((lane_y[None, :] + OY - 1.5) * T)
lawn = erode(lawn, 2)
paint_grass(lawn, P.LAWN)
g.fill(edge(lawn), P.LAWN['ol'])

# --- courtyards behind the building
court_l = R(11.6, -3, 24.2, 4)
court_r = R(39.6, -3, 60.4, 4)
paint_grass(court_r, P.LAWN)
g.fill(edge(court_r), P.LAWN['ol'])

# --- dirt paths and patches
dirt = poly_mask(smooth([(14.85, 12.6), (15.0, 15.6), (14.0, 17.2), (11.0, 18.0), (9.8, 19.4), (9.6, 21.6)]), 1.7)
dirt |= poly_mask(smooth([(19.6, -3), (19.0, 0.6), (16.6, 1.8), (15.6, 4)]), 1.5)
dirt |= R(51.0, 0.8, 54.6, 4) | R(52.0, -1.2, 54.6, 1)
dirt |= R(49.6, 12.9, 54.8, 19.2)                                   # right garden plot
dirt |= blob([(13.0, 38.0, 1.4), (15.0, 38.8, 1.2), (12.4, 39.6, 1.0)])
dirt |= R(4.0, 38.0, 7.8, 46.0) | blob([(5.9, 38.0, 1.9)])
dirt |= R(62.0, 31.8, 69, 46.0)
dirt |= R(-1.0, 24.0, 2.6, 27.4)
dirt |= poly_mask(smooth([(21.0, 41.5), (19.5, 45.5), (18.5, 51)]), 2.0)  # path south from the rotunda ramp
dirt &= ~road
paint_bordered(dirt, P.DIRT)

# --- tall grass patches
tall = blob([(7.6, 13.6, 1.6), (9.5, 13.4, 1.7), (11.3, 13.8, 1.4), (7.4, 15.4, 1.5), (9.2, 15.6, 1.8), (11.6, 15.6, 1.1), (8.0, 16.9, 1.0)])
tall |= blob([(3.4, 25.4, 1.3), (5.0, 25.2, 1.2), (3.6, 26.9, 1.2), (5.2, 26.8, 1.1)])
tall &= lawn
paint_tall(tall)

# --- vegetable plants (on dirt plots / beds)
plants = paint_plants(50.4, 13.4, 54.2, 18.8, 1.0, 1.05)
plants |= paint_plants(44.4, 0.3, 49.8, 4.0, 1.0, 1.0)
plants |= paint_plants(11.4, 35.4, 15.6, 37.8, 0.95, 1.0)
solid |= plants

# --- road surface
g.fill(road, P.ROAD['base'])
g.fill(road & (((xx * 7 + yy * 3) % 37) == 0), P.ROAD['sh'])
g.fill(road & (((xx * 3 + yy * 11) % 41) == 0), P.ROAD['hi'])
r1 = edge(road); r2 = edge(road & ~r1) & road; r3 = edge(road & ~r1 & ~r2) & road
g.fill(r1, P.ROAD['ol']); g.fill(r2, P.ROAD['kerb']); g.fill(r3, P.ROAD['sh'])
# sandy verge outside the kerb (as in the reference)
verge = dilate(road, 3) & ~road & ~lawn & ~dirt & ~dilate(median, 8)
g.fill(verge, P.DIRT['hi'])

# ===================================================================== rotunda (elliptical, in perspective)
print('rotunda...')
# SE fan of seating steps (outside the ellipse)
seat = (s_rot >= 1.0) & (s_rot < 1.56) & ((theta >= 352) | (theta <= 80))
band = ((s_rot - 1.0) / 0.052).astype(int)
fr = ((s_rot - 1.0) / 0.052) % 1
g.fill(seat, P.STEP['base'])
g.fill(seat & (fr < 0.28), P.STEP['hi'])
g.fill(seat & (fr > 0.86), P.STEP['ol'])
g.fill(seat & (band % 3 == 1) & (fr >= 0.28) & (fr <= 0.86), P.GRASS['sh'])
seat_wall = seat & ((s_rot >= 1.52) | (theta > 77) & (theta <= 80) | ((theta >= 352) & (theta < 355)))
g.fill(seat_wall, P.SALMON['base'])
g.fill(edge(seat | seat_wall) & ~(s_rot < 1.02), P.SALMON['ol'])
solid |= seat_wall

# floor ellipse (slightly lower centre than the gallery: perspective)
FCY = RCY + 0.9
FRX, FRY = 13.8, 9.8
fx, fy = (xx - X(RCX)) / L(1), (yy - Y(FCY)) / L(1)
u = np.sqrt((fx / FRX) ** 2 + (fy / FRY) ** 2)
ph = np.degrees(np.arctan2(fy / FRY, fx / FRX))
floor = u < 1.0
apron = (s_rot < 1.0) & ~floor
g.fill(apron, P.STONE['hi'])
g.fill(apron & (((xx + yy) % 9) == 0), P.STONE['base'])
g.fill(floor, P.TERRA['base'])
g.fill(floor & (u >= 0.91), P.STONE['hi'])
g.fill(floor & (u >= 0.89) & (u < 0.91), P.PLAZA_GREY['base'])

def fpt(r, a):
    return (X(RCX) + r * math.cos(math.radians(a)) * L(FRX), Y(FCY) + r * math.sin(math.radians(a)) * L(FRY))

def chord_mask(n, step, r, width, rot=0.0):
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    for i in range(n):
        a0 = rot + i * 360 / n; a1 = rot + (i + step) * 360 / n
        d.line([fpt(r, a0), fpt(r, a1)], fill=255, width=width)
    return np.array(im) > 0

zone = floor & (u >= 0.48) & (u < 0.89)
star = chord_mask(16, 5, 0.89, 9) & zone                    # {16/5} star polygon -> bold rhombus lattice
g.fill(star, P.PLAZA_GREY['base'])
g.fill(star & ~edge(star), P.PLAZA_GREY['hi'])
g.fill(edge(star), P.PLAZA_GREY['sh'])
g.fill(floor & (u >= 0.46) & (u < 0.50), P.STONE['hi'])
g.fill(floor & (np.abs(u - 0.48) < 0.006), P.PLAZA_GREY['base'])
inner = floor & (u < 0.46)
g.fill(inner, P.TERRA['hi'])
# 8-petal flower drawn as outlined pointed petals (like the reference), plus 8 smaller in-between petals
petal = inner & (u < 0.34 * np.abs(np.cos(np.radians(ph) * 4)) ** 1.2 + 0.03)
petal2 = inner & (u < 0.22 * np.abs(np.cos(np.radians(ph + 22.5) * 4)) ** 1.2 + 0.02)
g.fill(petal2, P.TERRA['base'])
g.fill(edge(petal2), P.PLAZA_GREY['base'])
g.fill(petal & ~petal2, P.PLAZA_GREY['hi'])
g.fill(edge(petal), P.PLAZA_GREY['sh'])
g.fill(inner & (u < 0.07), P.STONE['hi'])
g.fill(edge(inner & (u < 0.07)), P.PLAZA_GREY['sh'])
# central hedge arcs (broken ring) like the reference
hedge_ring = floor & (u >= 0.40) & (u < 0.45) & ~(np.abs(((ph + 22.5) % 90) - 45) < 12)

# north gallery (curved arcade facing south into the bowl)
GAL = (theta >= 196) & (theta <= 344)
gal_roof = (s_rot >= 0.93) & (s_rot < 1.0) & GAL
g.fill(gal_roof, P.GALLERY['base'])
g.fill(gal_roof & (s_rot >= 0.985), P.SALMON['base'])
g.fill(gal_roof & (s_rot < 0.945), P.GALLERY['hi'])
g.fill(edge(gal_roof), P.SALMON['ol'])
GW = 40                                       # gallery wall height (px)
rin_x, rin_y = 0.93 * RX, 0.93 * RY
ytop = Y(RCY) - np.sqrt(np.maximum(1 - ((xx - X(RCX)) / L(rin_x)) ** 2, 0)) * L(rin_y)
hb = yy - ytop
gal_wall = (hb >= 0) & (hb < GW) & (s_rot < 0.93) & (theta >= 200) & (theta <= 340) & (ey < 0)
g.fill(gal_wall, P.GALLERY['base'])
g.fill(gal_wall & (hb < 3), P.GALLERY['sh'])
k = (xx - X(RCX) + 13) % 26
arch = gal_wall & (k >= 6) & (k < 20) & (hb >= 8) & (hb < GW - 4)
arch &= ~((hb < 15) & (np.abs(k - 12.5) > (hb - 7) * 1.1))
g.fill(arch, P.GALLERY['arch'])
g.fill(arch & (hb < 18), P.GALLERY['arch_dk'])
g.fill(gal_wall & (k >= 21) & (k < 23) & (hb >= 8) & (hb < GW - 4), P.GALLERY['hi'])
g.fill(gal_wall & (hb >= GW - 3), P.SALMON['base'])
g.fill(gal_wall & (hb == GW - 1), P.SALMON['ol'])
# planter strip at the foot of the gallery
planter = (hb >= GW) & (hb < GW + 7) & (s_rot < 0.93) & (theta >= 204) & (theta <= 336) & (ey < 0)
solid |= gal_roof | gal_wall
# medallion on the gallery roof
mx, my = X(32.6), Y(22.1)
med = g.disk(mx, my, 10)
g.fill(med, P.STONE['hi']); g.fill(edge(med), P.STONE['ol'])
g.fill(g.disk(mx, my, 6) & ~g.disk(mx, my, 3), P.STONE['sh'])
for a in range(0, 360, 45):
    g.px(mx + 8 * math.cos(math.radians(a)), my + 8 * math.sin(math.radians(a)), P.STONE['sh'])
# rim wall around the bowl on the west/south (opening to the seating and the SW ramp)
rim = (s_rot >= 0.955) & (s_rot < 1.0) & ~GAL & ~((theta >= 352) | (theta <= 80)) & ~((theta >= 112) & (theta <= 128))
g.fill(rim, P.SALMON['base'])
g.fill(rim & (s_rot >= 0.985), P.SALMON['hi'])
g.fill(edge(rim), P.SALMON['ol'])
solid |= rim
# SW ramp
ramp = (s_rot >= 0.95) & (s_rot < 1.12) & (theta >= 112) & (theta <= 128)
g.fill(ramp, P.STONE['base'])
g.fill(ramp & ((yy % 5) == 0), P.STONE['sh'])
g.fill(outer(ramp) & ~(s_rot < 0.95) & ~seat, P.STONE['ol'])
# wooden bench by the west wall
bx0, by0 = X(14.8), Y(32.1)
g.rect(bx0, by0, L(1.6), 6, P.TRUNK['hi']); g.rect(bx0, by0 + 6, L(1.6), 6, P.TRUNK['base'])
g.fill(outer(g.rmask(bx0, by0, L(1.6), 12)), P.TRUNK['ol'])
solid[by0:by0 + 12, bx0:bx0 + L(1.6)] = True

# ===================================================================== hedges
hedges = median | hedge_ring | planter
def lane_hedge(x0, x1, d=2.25):
    pts = [p for p in offset(R1, d) if x0 <= p[0] <= x1]
    return poly_mask(pts, 0.8) if len(pts) > 1 else np.zeros((H, W), bool)
hedges |= lane_hedge(10.4, 23.2) | lane_hedge(2.4, 7.8) | lane_hedge(36.8, 46.0) | lane_hedge(47.6, 55.4)
hedges |= poly_mask(smooth([(-6, 40.3), (0, 38.4), (6, 35.8), (12, 33.0), (16.6, 31.0)]), 0.8)
hedges |= poly_mask(smooth([(17.9, 29.2), (17.6, 31.0), (17.9, 32.8)]), 0.9)          # planter west of rotunda
hedges |= R(56.0, 30.4, 69, 31.3)
hedges |= R(59.8, 34.4, 61.8, 46)
hedges &= ~road & ~dirt
paint_hedges(hedges)

# ===================================================================== building kit
bld_mask = np.zeros((H, W), bool)


def drop_shadow(m, d=6):
    s = shift(m, d, d // 2) & ~m & ~bld_mask
    g.darken(s, P.SHADOW_K)


def flat_roof(m):
    """beige terrace roof with salmon parapet for an arbitrary mask"""
    g.fill(m, P.ROOF['base'])
    g.fill(m & (((xx * 3 + yy * 7) % 23) == 0), P.ROOF['sh'])
    g.fill(m & (((xx * 5 + yy * 3) % 29) == 0), P.ROOF['hi'])
    e1 = edge(m); e2 = edge(m & ~e1) & m; e3 = edge(m & ~e1 & ~e2) & m; e4 = edge(m & ~e1 & ~e2 & ~e3) & m
    e5 = edge(m & ~e1 & ~e2 & ~e3 & ~e4) & m
    g.fill(e2 | e3, P.SALMON['base'])
    g.fill(e2 & ~shift(m, 0, 2), P.SALMON['hi'])
    g.fill(e4, P.LINE)
    inner = m & ~e1 & ~e2 & ~e3 & ~e4
    g.fill(e5 | (inner & ~shift(inner, 0, 4)) | (inner & ~shift(inner, 4, 0)), P.ROOF['sh'])
    g.fill(e1, P.SALMON['ol'])
    bld_mask[m] = True


def wall(x0, y0, x1, y1, kind='arcade', door_at=None):
    """south-facing facade between reference-tile coords"""
    m = R(x0, y0, x1, y1)
    xa, ya, xb, yb = X(x0), Y(y0), X(x1), Y(y1)
    g.fill(m, P.CREAM['base'])
    g.fill(m & (xx < xa + 3), P.CREAM['hi'])
    g.fill(m & (xx >= xb - 3), P.CREAM['sh'])
    hgt = yb - ya
    if kind == 'arcade':
        fr_ = m & (yy >= ya + 3) & (yy < ya + 10)
        g.fill(fr_ & (((xx - xa) % 11) >= 3), P.WIN['base'])
        g.fill(fr_ & (((xx - xa) % 11) >= 3) & (yy == ya + 3), P.WIN['hi'])
        g.fill(m & (yy == ya + 11), P.SALMON['base'])
        g.fill(m & (yy == ya + 12), P.SALMON['sh'])
        kk = (xx - xa - 4) % 18
        ar = m & (kk >= 5) & (kk < 14) & (yy >= ya + 18) & (yy < yb - 7)
        ar &= ~((yy < ya + 21) & (np.abs(kk - 9.5) > (yy - ya - 17) * 1.6 + 1))
        g.fill(ar, P.WIN['base'])
        g.fill(ar & (yy < ya + 22) & (np.abs(kk - 9.5) < 2), P.WIN['hi'])
        g.fill(m & (yy == yb - 7) & (kk >= 4) & (kk < 15), P.WIN['sill'])
    elif kind == 'windows':
        for ry in range(ya + 4, yb - 8, 16):
            g.fill(m & (yy >= ry) & (yy < ry + 2), P.WIN['sill'])
            g.fill(m & (yy == ry + 2), P.CREAM['dk'])
            kk = (xx - xa - 5) % 15
            wn = m & (kk < 10) & (yy >= ry + 5) & (yy < ry + 11)
            g.fill(wn, P.WIN['base'])
            g.fill(wn & (yy == ry + 5), P.WIN['hi'])
    elif kind == 'balcony':
        for ry in range(ya + 2, yb - 8, 14):
            band = m & (yy >= ry) & (yy < ry + 3)
            g.fill(band, P.WIN['sill'])
            g.fill(m & (yy == ry + 3), P.CREAM['dk'])
            kk = (xx - xa - 4) % 16
            wn = m & (kk < 11) & (yy >= ry + 6) & (yy < ry + 12)
            g.fill(wn, P.WIN['base'])
            g.fill(m & (kk >= 11) & (kk < 13) & (yy >= ry + 6) & (yy < ry + 12), P.CREAM['sh'])
    elif kind == 'plain':
        kk = (xx - xa - 6) % 22
        wn = m & (kk < 7) & (yy >= ya + 6) & (yy < ya + 16)
        g.fill(wn, P.WIN['base'])
    g.fill(m & (yy >= yb - 4), P.SALMON['base'])
    g.fill(m & (yy == yb - 4), P.SALMON['hi'])
    g.fill(m & (yy >= yb - 1), P.SALMON['ol'])
    g.fill(edge(m) & ((xx == xa) | (xx == xb - 1)), P.SALMON['ol'])
    bld_mask[m] = True
    solid[m] = True
    if door_at is not None:
        door(X(door_at), yb)


def door(cx, yb, dw=22, dh=20):
    x0 = cx - dw // 2
    g.rect(x0 - 3, yb - dh - 3, dw + 6, dh + 3, P.SALMON['base'])
    g.rect(x0 - 3, yb - dh - 3, dw + 6, 1, P.SALMON['ol'])
    g.rect(x0, yb - dh, dw, dh, P.WIN['base'])
    g.rect(x0, yb - dh, dw, 2, P.WIN['hi'])
    for i in range(3):
        g.rect(x0 - 2 + i, yb + i * 3, dw + 4 - 2 * i, 3, P.STEP['hi'] if i % 2 == 0 else P.STEP['base'])
    g.rect(x0, yb + 9, dw, 1, P.STEP['ol'])


def block(x0, y0, x1, y1, wall_t, kind='plain', door_at=None):
    """building block in reference tiles: flat roof on top, facade of wall_t tiles at the bottom"""
    m = R(x0, y0, x1, y1)
    drop_shadow(m)
    if wall_t < (y1 - y0):
        flat_roof(R(x0, y0, x1, y1 - wall_t))
    if wall_t > 0:
        wall(x0, y1 - wall_t, x1, y1, kind, door_at)
    solid[m] = True
    bld_mask[m] = True


def rooftop_box(x0, y0, x1, y1):
    m = R(x0, y0, x1, y1)
    g.darken(shift(m, 5, 3) & ~m, 0.84)
    roof_m = R(x0, y0, x1, y1 - 1.1)
    g.fill(roof_m, P.ROOF['hi'])
    g.fill(edge(roof_m & ~edge(roof_m)) & roof_m, P.SALMON['base'])
    g.fill(edge(roof_m), P.SALMON['ol'])
    wm = R(x0, y1 - 1.1, x1, y1)
    g.fill(wm, P.CREAM['base']); g.fill(edge(wm), P.SALMON['ol'])
    cx = (X(x0) + X(x1)) // 2
    g.rect(cx - 4, Y(y1) - 13, 8, 12, P.WIN['base'])
    g.rect(X(x1) - 8, Y(y1) - 15, 2, 9, P.WIN['base'])


def hip_roof(x0, y0, x1, y1):
    m = R(x0, y0, x1, y1)
    drop_shadow(m, 8)
    xa, ya, xb, yb = X(x0), Y(y0), X(x1), Y(y1)
    w, h = xb - xa, yb - ya
    lx, ly = xx - xa, yy - ya
    ridge = h * 0.35
    left_f = m & (lx < ly - ridge + h * 0.65) & (lx < w * 0.5) & (lx < (h - ly) + w * 0.0 + 60)
    left_f = m & (lx < 60) & (lx < (ly - 10) * 1.2 + 20)
    right_f = m & ((w - 1 - lx) < 60) & ((w - 1 - lx) < (ly - 10) * 1.2 + 20)
    south = m & ~left_f & ~right_f & (ly >= ridge)
    north = m & ~left_f & ~right_f & ~south
    g.fill(north, P.SLATE['hi']); g.fill(south, P.SLATE['base'])
    g.fill(left_f, P.SLATE['hi']); g.fill(right_f, P.SLATE['sh'])
    g.fill(m & ((yy - ya) % 4 == 0) & (south | north), P.SLATE['sh'])
    g.fill(m & ((xx - xa) % 4 == 0) & (left_f | right_f), P.SLATE['ol'])
    g.fill(edge(left_f) | edge(right_f) | edge(m), P.SLATE['ol'])
    g.rect(xa - 2, yb - 4, w + 4, 6, P.CREAM['base']); g.rect(xa - 2, yb + 1, w + 4, 1, P.SALMON['ol'])
    for cxr in (28.9, 35.1):
        dx0 = X(cxr) - 10
        g.rect(dx0, yb - 16, 20, 12, P.CREAM['base'])
        g.rect(dx0, yb - 17, 20, 2, P.SALMON['base'])
        g.rect(dx0 + 4, yb - 12, 12, 6, P.WIN['base'])
        g.fill(outer(g.rmask(dx0, yb - 17, 20, 13)) & m, P.SLATE['ol'])
    solid[m] = True
    bld_mask[m] = True


def clock_tower(cx, y_top, y_bot, sw):
    """Art Deco tower elevation: finial, stepped pediment, arched-window stage, clock stage, slit shaft, fins."""
    x0 = cx - sw // 2
    g.darken(g.rmask(x0 + sw, y_top + 30, 10, y_bot - y_top - 30) & bld_mask, 0.84)

    def box(x, y, w, h):
        m = g.rmask(x, y, w, h)
        g.fill(m, P.CREAM['base'])
        g.fill(m & (xx < x + 3), P.CREAM['hi'])
        g.fill(m & (xx >= x + w - 3), P.CREAM['sh'])
        g.fill(edge(m), P.SALMON['ol'])
        return m
    shaft_top = y_top + 78
    for sgn in (-1, 1):                         # stepped fins with slit windows
        fx = cx + sgn * (sw // 2 + 6) - 7
        box(fx, y_bot - 76, 14, 76)
        for k in range(4):
            g.rect(fx + 4, y_bot - 70 + k * 16, 6, 3, P.WIN['base'])
    box(x0, shaft_top, sw, y_bot - shaft_top)
    for i in range(3):
        sx = x0 + 14 + i * 14
        for ty in range(shaft_top + 10, y_bot - 26, 26):
            g.rect(sx, ty, 6, 20, P.WIN['base'])
            g.rect(sx, ty, 6, 2, P.WIN['hi'])
    for ty in range(shaft_top + 6, y_bot - 20, 26):
        g.rect(x0 + 3, ty, sw - 6, 1, P.CREAM['dk'])
    # balcony band at the foot of the shaft
    g.rect(x0 - 8, y_bot - 22, sw + 16, 5, P.WIN['sill'])
    g.rect(x0 - 8, y_bot - 17, sw + 16, 1, P.SALMON['base'])
    g.fill(outer(g.rmask(x0 - 8, y_bot - 22, sw + 16, 6)), P.SALMON['ol'])
    g.rect(x0 - 2, shaft_top, sw + 4, 4, P.SALMON['base'])
    g.rect(x0 - 2, shaft_top, sw + 4, 1, P.SALMON['hi'])
    # clock stage (wider, salmon framed)
    cs_w, cs_h = sw + 6, 42
    cs_x, cs_y = cx - cs_w // 2, shaft_top - cs_h
    box(cs_x, cs_y, cs_w, cs_h)
    g.fill(g.rmask(cs_x + 3, cs_y + 3, cs_w - 6, cs_h - 6) & ~g.rmask(cs_x + 6, cs_y + 6, cs_w - 12, cs_h - 12), P.SALMON['base'])
    ccx, ccy, r = cx - 0.5, cs_y + cs_h / 2, 14
    face = g.disk(ccx, ccy, r)
    g.fill(face, P.CLOCK['face'])
    g.fill(face & ~g.disk(ccx, ccy, r - 2), P.CLOCK['tick'])
    for a in range(0, 360, 30):
        g.px(ccx + math.cos(math.radians(a)) * (r - 4), ccy + math.sin(math.radians(a)) * (r - 4), P.CLOCK['tick'])
    for i in range(9):
        g.px(ccx, ccy - i, P.CLOCK['hand'])
    for i in range(7):
        g.px(ccx + i * 0.7, ccy + i * 0.7, P.CLOCK['hand'])
    g.fill(outer(face), P.SALMON['ol'])
    # arched window stage
    aw_w, aw_h = sw - 6, 32
    ax_, ay_ = cx - aw_w // 2, cs_y - aw_h
    box(ax_, ay_, aw_w, aw_h)
    g.rect(ax_ + 2, ay_ + 2, aw_w - 4, 3, P.SALMON['base'])
    win = g.rmask(cx - 8, ay_ + 9, 16, 19) & ~((yy < ay_ + 15) & (np.abs(xx - cx + 0.5) > (yy - ay_ - 6) * 1.5))
    g.fill(win, P.GLASS_G['base'])
    g.fill(win & (np.abs(xx - cx + 0.5) < 1), P.CREAM['base'])
    g.fill(outer(win), P.SALMON['base'])
    # stepped pediment + finial
    for i, (pw, phh) in enumerate(((aw_w + 4, 5), (aw_w - 12, 5), (aw_w - 26, 5))):
        py = ay_ - 5 * (i + 1)
        m = g.rmask(cx - pw // 2, py, pw, phh)
        g.fill(m, P.SALMON['base'] if i == 0 else P.CREAM['base'])
        g.fill(edge(m), P.SALMON['ol'])
    g.rect(cx - 1, ay_ - 26, 2, 11, P.SALMON['ol'])
    g.rect(cx - 1, ay_ - 26, 1, 11, P.GOLD['base'])
    bld_mask[ay_ - 26:y_bot, x0 - 20:x0 + sw + 20] |= True


# ===================================================================== main building (reference tiles)
print('buildings...')
# rear range + courtyard frame + slate hall
for x0, x1 in ((0.5, 11.6), (24.2, 26.6), (37.4, 39.6), (60.4, 63.7)):
    block(x0, -4, x1, 4.2, 0)
for x0, x1 in ((11.6, 24.2), (39.6, 60.4)):
    block(x0, -4, x1, -2.4, 0)
paint_grass(court_l & ~bld_mask, P.GRASS)
hip_roof(26.6, -4, 37.4, 4.2)
# the big U-shaped roof (main range + outer legs)
U = R(0.5, 4.0, 63.7, 8.2) | R(0.5, 4.0, 4.7, 16.6) | R(59.2, 4.0, 63.7, 17.2) | R(0.5, -1, 11.6, 4.2) | R(60.4, -1, 63.7, 4.2)
drop_shadow(U)
flat_roof(U)
solid |= U
rooftop_box(2.0, 3.3, 5.1, 6.4)
rooftop_box(57.8, 3.3, 62.0, 6.4)
# front wings (arcade) with doors
block(4.7, 8.0, 24.7, 12.0, 3.0, 'arcade', door_at=14.85)
block(39.1, 8.0, 59.2, 12.0, 3.0, 'arcade', door_at=52.45)
# raised blocks next to the centre
block(20.0, 9.4, 24.4, 13.8, 2.0, 'windows')
block(39.6, 9.4, 44.0, 13.8, 2.0, 'windows')
# stepped blocks with white balcony bands
block(24.0, 11.9, 28.7, 16.2, 3.0, 'balcony')
block(35.3, 11.9, 40.0, 16.2, 3.0, 'balcony')
block(24.4, 8.0, 28.4, 12.0, 0)
block(35.6, 8.0, 39.6, 12.0, 0)
# clock tower and porch (porte-cochere over the forecourt)
block(28.2, 6.0, 35.8, 13.6, 0)
clock_tower(X(32), Y(1.9), Y(13.4), L(4.0))
block(29.6, 13.4, 34.4, 18.8, 2.7, 'plain')
g.rect(X(30.6), Y(16.9), X(33.4) - X(30.6), Y(18.8) - Y(16.9) - 1, P.WIN['base'])
g.rect(X(30.6), Y(16.9), X(33.4) - X(30.6), 2, P.WIN['hi'])
# west/east pavilions at the ends of the legs
block(-0.2, 16.5, 6.0, 20.3, 2.0, 'windows')
block(0.0, 20.2, 5.0, 24.2, 2.2, 'plain', door_at=2.0)
block(57.6, 17.0, 64.0, 21.0, 2.0, 'windows')
block(61.2, 20.4, 66.4, 24.6, 2.2, 'plain', door_at=62.4)

zones += [
    {'name': 'Main Building', 'x': X(0), 'y': Y(-4), 'w': L(64), 'h': L(21), 'p': 2},
    {'name': 'Clock Tower', 'x': X(27), 'y': Y(13), 'w': L(10), 'h': L(9), 'p': 0},
    {'name': 'Rotunda', 'x': X(RCX - RX), 'y': Y(RCY - RY), 'w': L(2 * RX), 'h': L(2 * RY + 1), 'p': 0},
    {'name': 'Rotunda Steps', 'x': X(46), 'y': Y(30), 'w': L(10), 'h': L(16), 'p': 1},
    {'name': 'Front Lawns', 'x': X(4), 'y': Y(12), 'w': L(56), 'h': L(10), 'p': 1},
    {'name': 'Courtyard Garden', 'x': X(11), 'y': Y(-3), 'w': L(50), 'h': L(7), 'p': 1},
]

# ===================================================================== props (reference tiles)
for x, y in ((17.6, 14.8), (47.5, 16.4), (42.5, 15.6), (8.6, 37.9), (10.6, 36.4), (49.6, 31.3), (54.6, 30.5),
             (39.4, 41.8), (24.0, 44.6), (19.6, 44.0), (8.5, 47.5), (56.5, 47.6), (34.0, 47.0)):
    put(f'palm{h32(x, y) % 3}', x, y)
flag_spots = [(16.4, 17.0, 0), (10.9, 20.4, 1), (8.4, 23.4, 0), (6.6, 27.7, 1), (9.5, 34.0, 0), (3.3, 36.5, 4),
              (16.7, 27.1, 2), (14.5, 30.4, 4), (43.6, 17.0, 2), (49.1, 18.8, 0), (45.3, 22.6, 2), (53.4, 23.4, 1)]
for x, y, c in flag_spots:
    put(f'flag{c}', x, y)
for x, y in ((2.4, 29.2), (7.8, 24.5), (52.2, 24.8)):
    put('lamp', x, y)
put('sign', 55.3, 23.7)
# flowering bush clusters (SW of the rotunda, NE of the seating, right lawn rows)
for i, (x, y) in enumerate([(14.6, 34.6), (15.8, 34.9), (17.0, 35.2), (15.2, 36.2), (16.6, 36.6), (17.8, 36.4),
                            (16.0, 37.8), (17.4, 38.2), (15.2, 39.4), (16.8, 39.8), (13.2, 41.0), (14.6, 41.4)]):
    put(['bush_pink', 'bush_purple', 'bush_pink', 'bush_white'][i % 4], x, y)
for i, (x, y) in enumerate([(49.6, 26.8), (50.8, 27.0), (52.0, 27.4), (49.8, 28.2), (51.0, 28.6), (52.4, 28.9),
                            (50.4, 29.8), (51.8, 30.2)]):
    put(['bush_pink', 'bush_purple', 'bush_yellow'][i % 3], x, y)
for i, x in enumerate(np.arange(55.8, 64.5, 1.2)):
    put('bush_pink' if x < 58.5 else 'bush_yellow', x, 29.6)
for x, y, k in ((19.6, 14.8, 'green'), (40.6, 15.8, 'green'), (44.5, 15.7, 'green'), (55.6, 15.0, 'pink'),
                (55.6, 16.6, 'pink'), (56.4, 13.8, 'green'), (55.8, 18.4, 'yellow'), (6.0, 40.5, 'green'),
                (1.0, 38.6, 'green'), (2.6, 39.2, 'green'), (12.8, 2.0, 'pink'), (20.0, 2.6, 'pink'),
                (22.5, 1.0, 'green'), (23.0, 3.0, 'green'), (41.0, 1.2, 'green'), (58.6, 0.4, 'pink'),
                (54.6, 21.6, 'green'), (55.8, 22.0, 'green')):
    put(f'bush_{k}', x, y)
for i, y in enumerate(np.arange(32.6, 45, 1.3)):
    put('bush_green' if i % 3 else 'tree0', 57.4 + (i % 2) * 1.2, y)
# forests behind the building (top-left / top-right) and around the map edge
for y in np.arange(-3.6, 2.7, 1.5):
    for x in np.arange(-3.5, 11.6, 1.9):
        if x > 0.5 and y > 4.0:
            continue
        put(f'tree{h32(x, y) % 3}', x + (h32(y, x) % 5) / 10, y + 1.2)
for y in np.arange(-3.6, 2.7, 1.5):
    for x in np.arange(63.8, 68.4, 1.9):
        put(f'tree{h32(x, y) % 3}', x, y + 1.2)
for y in np.arange(4.4, 52, 2.0):
    for x in (-3.4, 67.4):
        if not road[min(H - 1, Y(y)), max(0, min(W - 1, X(x)))]:
            put(f'conifer{h32(x, y) % 3}', x, y)
for x in np.arange(-3.6, 68.4, 1.6):
    put(f'conifer{h32(x) % 3}', x, 51.4 + (h32(x, 1) % 5) / 10)

# ===================================================================== export
print('exporting...')
pr = PR.build_all()
order = list(pr.keys())
sheet = Canvas(sum(pr[n][0].w for n in order), max(pr[n][0].h for n in order))
frames, xo = {}, 0
for n in order:
    c, ax, ay, (cw, ch) = pr[n]
    sheet.paste(c, xo, 0)
    frames[n] = {'x': xo, 'y': 0, 'w': c.w, 'h': c.h, 'ax': ax, 'ay': ay, 'cw': cw, 'ch': ch}
    xo += c.w
Image.fromarray(sheet.a).save(f'{OUT_GAME}/tiles/props.png')

for n, x, y in props:
    f = frames[n]
    solid[max(0, y - f['ch']):y + 1, max(0, x - f['cw'] // 2):x + f['cw'] // 2 + 1] = True
solid[:, :L(1.2)] = True; solid[:, W - L(1.2):] = True
solid[:L(0.5), :] = True; solid[H - L(1.5):, :] = True

C = 8
cw_, ch_ = W // C, H // C
grid = solid.reshape(ch_, C, cw_, C).mean(axis=(1, 3)) > 0.4
coll = ''.join('1' if v else '0' for v in grid.ravel())

ground = g.a.copy()
ground[..., 3] = 255
tiles, index, data = [], {}, []
for ty in range(MH):
    for tx in range(MW):
        tile = ground[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]
        key = tile.tobytes()
        if key not in index:
            index[key] = len(tiles)
            tiles.append(tile)
        data.append(index[key] + 1)
COLS = 32
rows = math.ceil(len(tiles) / COLS)
ts = np.zeros((rows * T, COLS * T, 4), np.uint8)
for i, tl in enumerate(tiles):
    ts[(i // COLS) * T:(i // COLS + 1) * T, (i % COLS) * T:(i % COLS + 1) * T] = tl
Image.fromarray(ts).save(f'{OUT_GAME}/tiles/campus.png')

spawn = {'x': X(32.4), 'y': Y(20.4)}
tiled = {
    'type': 'map', 'version': '1.10', 'tiledversion': '1.10.2', 'orientation': 'orthogonal', 'renderorder': 'right-down',
    'infinite': False, 'width': MW, 'height': MH, 'tilewidth': T, 'tileheight': T, 'nextlayerid': 2, 'nextobjectid': 1,
    'layers': [{'id': 1, 'name': 'ground', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': MW, 'height': MH,
                'opacity': 1, 'visible': True, 'data': data}],
    'tilesets': [{'firstgid': 1, 'name': 'campus', 'image': '../tiles/campus.png', 'imagewidth': COLS * T,
                  'imageheight': rows * T, 'tilewidth': T, 'tileheight': T, 'tilecount': len(tiles),
                  'columns': COLS, 'margin': 0, 'spacing': 0}],
}
json.dump(tiled, open(f'{OUT_GAME}/maps/main.json', 'w'))
json.dump({'props': [{'f': n, 'x': x, 'y': y} for n, x, y in props], 'frames': frames,
           'collision': {'cell': C, 'w': cw_, 'h': ch_, 'data': coll}, 'zones': zones, 'spawn': spawn,
           'width': W, 'height': H}, open(f'{OUT_GAME}/maps/main.meta.json', 'w'))

# collision + zones in reference-frame coordinates (used by tools/v2/from_ref.py)
struct = bld_mask | gal_roof | gal_wall | rim | seat_wall          # walls only; greenery is detected from the art
sgrid = struct.reshape(ch_, C, cw_, C).mean(axis=(1, 3)) > 0.4
ref_grid = sgrid[OY * 2:(OY + 43) * 2, OX * 2:(OX + 64) * 2]
json.dump({'cell': C, 'w': ref_grid.shape[1], 'h': ref_grid.shape[0],
           'data': ''.join('1' if v else '0' for v in ref_grid.ravel()),
           'zones': [dict(z, x=z['x'] - X(0), y=z['y'] - Y(0)) for z in zones],
           'spawn': {'x': spawn['x'] - X(0), 'y': spawn['y'] - Y(0)}}, open('data/layout_ref.json', 'w'))
prev = Canvas(W, H)
prev.a[:] = ground
for n, x, y in sorted(props, key=lambda p: p[2]):
    f = frames[n]
    prev.paste(pr[n][0], x - f['ax'], y - f['ay'])
Image.fromarray(prev.a[..., :3]).save(f'{DEBUG}/map_main.png')
Image.fromarray(prev.a[..., :3]).resize((W // 6, H // 6), Image.BOX).save(f'{OUT_GAME}/maps/minimap.png')
# same framing as the reference, side by side for comparison
frame = Image.fromarray(prev.a[Y(0):Y(43), X(0):X(64), :3])
frame.save(f'{DEBUG}/map_ref_frame.png')
ref = Image.open('art/reference_main.png').convert('RGB')
sbs = Image.new('RGB', (ref.width + frame.width + 8, max(ref.height, frame.height)), (24, 24, 32))
sbs.paste(ref, (0, 0)); sbs.paste(frame, (ref.width + 8, 0))
sbs.save(f'{DEBUG}/compare_ref.png')
print(f'{MW}x{MH} tiles, {len(tiles)} unique tiles, {len(props)} props')
