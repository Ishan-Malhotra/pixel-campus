"""Beautify streets: footpaths, kerbs, crossings, varied trees with shade, grouped planting, ground variety, street details.

  python3 tools/v4/beautify.py --assets                 only (re)make the tiles, props and tilesets
  python3 tools/v4/beautify.py phase1 krishna_test      lay out one area (see AREAS) into tiled/maps/phase1.tmj

The user's Part B (2026-11-17), mood after art/reference_street.png (feel only: lush, layered, dappled shade, chunky
varied trees). Deterministic: one SEED, so a rerun gives the same map.

Writes only: tiled/generated/street/*, tiled/tilesets/street.tsj (16 px tiles) + street_objects.tsj (props), and in the
map the layers `decor` (road surface, kerbs, pavers, hedge, ground), `props` (tree trunks, shrubs, lamps, bins, benches,
racks, barricades; trims the blueprint's dashed road line inside the area), `above` (tree canopies: the player walks
under them) and `shadows` (ellipses: tree shadows, dappled shade, darker grass; tools/v4/tiled_to_game.py darkens the
ground under them within the palette). Its objects are named `bty:<area>`; a rerun removes them first and clears the
area's decor / above cells. data/<area>_beautify.json lists the areas, and tools/v4/exterior.py leaves them alone.

Pipeline: blueprint.py -> exterior.py --approved -> beautify.py <area> <name> -> tiled_to_game.py.

Trees stand straight on the pavers (no pit). Trees come from the user's sheet (tools/v4/slice_trees.py -> tiled/tilesets/trees.tsj): trunk base as a depth-sorted
prop (only its tile blocks), canopy on `above`. Street copies of the umbrella and twin trees (canopy 3 tiles); the
full sizes are kept for lawns. A tree is only used where its whole collision footprint fits the footpath's outer
column, so the twin (two trunks, 3 tiles) is not used on footpaths.
"""
import json, math, os, sys, zlib
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tiled_kit
import exterior as EX

T = 16
SEED = 20261117
GEN = 'tiled/generated/street'
FLIP_H = 0x80000000
pal, to_palette, PAL, PAL_SET = EX.pal, EX.to_palette, EX.PAL, EX.PAL_SET
PAL_GREEN = PAL[(PAL[:, 1] > PAL[:, 0] + 8) & (PAL[:, 1] > PAL[:, 2] + 8)]

# (Until 2026-11-17 night there was a hand-set test area, Krishna Marg beside Krishna Bhawan, from its gate crossing south to the crossing
# where the NAB footpath meets the road. Read off the map: south of the gate the road's full-asphalt columns are
# 108-110 but north of it 107-109 (the road jogs at the gate); 107-109 is used for the whole area, so the north end
# meets the existing street exactly and the 3-tile footpath fits past the Warden's Residence (cols 114-119, rows
# 143-152). The east side (Krishna, the residence) gets the hedge; the west side (NAB) is a verge with shrub clusters.
AREAS = {
    # every road around the hostels (user 2026-11-17: "make all the roads surrounding the hostels this consistent")
    'hostels': dict(slots=['Ram Bhawan', 'Budh Bhawan', 'Krishna Bhawan', 'Gandhi Bhawan', 'Shankar Bhawan', 'Vishwakarma Bhawan',
                           'Bhagirath Bhawan', 'Malviya-A', 'Malviya-B', 'Vyas Bhawan', 'Rana Pratap Bhawan', 'Ashok bhawan'], margin=10),
}
DRIVE_CLEAR = 7               # tiles kept clear round the two ends of the front garden's drive
LAWN_CELLS_PER_TREE = 260     # one full-size lawn tree per this many open lawn cells
LAWN_TREE_SPACING = 9         # tiles between lawn trees
FOOTPATH = 3                  # tiles of pavers on each side, not counting the kerb
STRETCH = 20                  # tiles of road per set of street details (2 lamps, 1 bin, 1 bench or rack, maybe more)
TREE_GAP = (3, 5)             # tiles between street trees, jittered (user 2026-11-17: dense, as on the real roads)
TREE_SKIP = 0.05              # chance to leave a tree spot empty
POOL = {'large': [('tree_round_big', 3), ('tree_umbrella_road', 2), ('tree_column', 2), ('tree_twin_road', 1)],
        'medium': [('tree_ball', 2), ('tree_lime', 2), ('tree_cypress', 1)]}
CANOPY_MAX = {'large': 3 * T, 'medium': 2 * T}
SHRUBS = [('shrub_green', 5), ('shrub_red', 3), ('shrub_yellow', 2)]


def rng(*k):
    return np.random.default_rng([SEED] + [int(v) & 0xFFFFFFFF for v in k])


def P(c):
    return np.array(pal(tuple(int(round(v)) for v in c)), np.uint8)


def nearest_green(c):
    c = np.array(c, np.int32)
    return PAL_GREEN[np.argmin(((PAL_GREEN - c) ** 2).sum(axis=1))].astype(np.uint8)


# ===================================================================== colours (all from the locked palette)
ASPH = P(tiled_kit.ASPHALT); ASPH_DK = P(np.array(tiled_kit.ASPHALT) * 0.92); ASPH_LT = P(np.array(tiled_kit.ASPHALT) * 1.06)
SPECK = P(tiled_kit.SPECK); CRACK = P(np.array(tiled_kit.ASPHALT) * 0.80); PATCH = P((158, 162, 172))
MH_OL, MH_FILL, MH_LINE = P((73, 73, 69)), P((120, 124, 128)), P((95, 101, 110))
KERB, SHADE = EX.KERB, EX.KERB_SHADE
RAMP, RAMP_DOT = P((222, 216, 200)), P((187, 190, 187))
DIRT, DIRT_DK, DIRT_LT = P((171, 146, 110)), P((140, 118, 90)), P((196, 172, 130))
_terr = np.array(Image.open('tiled/tilesets/terrain.png').convert('RGB'))[4 * T:5 * T, 0:T].reshape(-1, 3)
_v, _c = np.unique(_terr, axis=0, return_counts=True)
GR = _v[np.argmax(_c)].astype(np.uint8)                                    # the lawn colour of the ground tiles
GR_LT, GR_DK = nearest_green(GR.astype(int) * 1.07 + 4), nearest_green(GR.astype(int) * 0.88)
GR_DK2 = nearest_green(GR.astype(int) * 0.74)
PIT_RIM, PIT_RIM_LT = P((151, 141, 128)), P((187, 190, 187))
PIT_SOIL, PIT_SOIL_LT, PIT_SOIL_DK = P((96, 74, 58)), P((124, 92, 70)), P((65, 41, 35))
FL_W, FL_Y, FL_P = P((246, 240, 219)), P((236, 206, 96)), P((226, 150, 170))
OL = P((40, 40, 40)); METAL, METAL_LT = P((110, 116, 126)), P((170, 176, 184))
WOOD, WOOD_LT, WOOD_DK = P((158, 104, 62)), P((190, 140, 86)), P((112, 72, 46))
BIN, BIN_LT, BIN_DK = P((52, 124, 74)), P((96, 168, 104)), P((30, 84, 50))
BIKE, BIKE_DK = P((219, 134, 109)), P((161, 112, 94))


def tile_of(c):
    a = np.zeros((T, T, 4), np.uint8); a[..., :3] = c; a[..., 3] = 255
    return a


def rot_side(a, side):
    """turn a tile so that `side` (of 'ltrb') is on the left; returns (turned tile, k) for np.rot90(.., -k) back"""
    k = {'l': 0, 't': 1, 'r': 2, 'b': 3}[side]
    return np.rot90(a, k).copy(), k


# ===================================================================== 16 px tiles
def asphalt(v, crack=False, worn=False, manhole=False, dash=False, zebra=False, horizontal=False):
    r = rng(1, v, crack, worn, manhole)
    a = tile_of(ASPH)
    m = r.random((T, T))
    a[m < .06, :3] = ASPH_DK; a[(m >= .06) & (m < .10), :3] = ASPH_LT; a[m > .985, :3] = SPECK
    yy, xx = np.mgrid[0:T, 0:T]
    if worn:                                           # a resurfaced patch: lighter, ragged rim
        cx, cy, rx, ry = 8 + r.integers(-1, 2), 8 + r.integers(-1, 2), r.integers(4, 7), r.integers(3, 6)
        e = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 + 0.3 * r.random((T, T))
        a[e < 1, :3] = PATCH; a[(e >= 1) & (e < 1.3), :3] = ASPH_DK
    if crack:                                          # a hairline crack, never touching the tile's edge (no seams)
        x, y = float(r.integers(3, 6)), float(r.integers(3, 6))
        ang = r.uniform(0.3, 1.2)
        for _ in range(14):
            xi, yi = int(round(x)), int(round(y))
            if not (1 <= xi < T - 1 and 1 <= yi < T - 1):
                break
            a[yi, xi, :3] = CRACK
            ang += r.uniform(-0.6, 0.6); x += math.cos(ang); y += math.sin(ang)
    if manhole:
        d = np.hypot(xx - 7.5, yy - 7.5)
        a[d <= 5.6, :3] = MH_FILL; a[(d > 4.6) & (d <= 5.6), :3] = MH_OL
        a[(d <= 4.6) & (yy % 3 == 0), :3] = MH_LINE
    if dash:
        if horizontal: a[7:9, 4:12, :3] = KERB
        else: a[4:12, 7:9, :3] = KERB
    if zebra:                                          # bars run along the road
        bars = [x for x in range(T) if x % 8 in (1, 2, 3, 4, 5)]
        if horizontal: a[bars, :, :3] = KERB
        else: a[:, bars, :3] = KERB
    return a


def kerb_inner(corner, v=0):
    """a footpath tile touching the road only at one corner (outside of a bend): a short striped kerb block there"""
    a = EX.paver(v)
    ys = slice(0, 4) if corner[0] == 'n' else slice(T - 4, T)
    xs = slice(0, 4) if corner[1] == 'w' else slice(T - 4, T)
    a[ys, xs, :3] = EX.KERB_DARK
    a[ys, xs, :3][::2, ::2] = KERB
    return a


def ramp(side, v=1):
    """the kerb lowered at a crossing: flush pale slabs with tactile dots instead of the black-and-white kerb"""
    a, k = rot_side(EX.paver(v), side)
    a[:, 0:4, :3] = RAMP
    for y in range(T):
        for x in range(4):
            if (x + y) % 3 == 0:
                a[y, x, :3] = RAMP_DOT
    a[:, 4, :3] = SHADE
    return np.rot90(a, -k).copy()


def kerb_corner(sides, v=0):
    return EX.kerb(sides, v)


def paver_dirt(side, v=2):
    """pavers with earth spilled from the tree pit on that side"""
    r = rng(3, ord(side), v)
    a, k = rot_side(EX.paver(v), side)
    for x in range(4):
        m = r.random(T) < 0.45 - 0.11 * x
        a[m, x, :3] = [DIRT, DIRT_DK, DIRT_LT][x % 3]
    return np.rot90(a, -k).copy()


def paver_end(side, v=3):
    """a footpath ending: pavers give way to trodden earth and then to grass towards that side"""
    r = rng(4, ord(side), v)
    a, k = rot_side(EX.paver(v), side)
    g = tile_of(GR)
    for y in range(T):
        dirt_to = 6 + int(r.integers(-1, 2)); grass_to = 2 + int(r.integers(-1, 2))
        for x in range(T):
            if x < grass_to:
                a[y, x, :3] = DIRT_LT if r.random() < .25 else g[y, x, :3]
            elif x < dirt_to and r.random() > .15:     # a few loose pavers stay in the earth
                a[y, x, :3] = [DIRT, DIRT_DK, DIRT_LT][int(r.integers(0, 3))] if r.random() < .3 else DIRT
    return np.rot90(a, -k).copy()


def grass(v, kind='plain'):
    """lawn without the repeating dot motif: a few small clusters of lighter / darker blades at random places"""
    r = rng(5, v, zlib.crc32(kind.encode()) & 0xFFFF)
    a = tile_of(GR)
    for _ in range(int(r.integers(7, 12))):
        x, y = int(r.integers(1, T - 1)), int(r.integers(1, T - 1))
        c = GR_LT if r.random() < .5 else GR_DK
        a[y, x, :3] = c
        if r.random() < .6: a[y - 1, x, :3] = c
        if r.random() < .3: a[y, x + (1 if r.random() < .5 else -1), :3] = c
    if kind == 'tuft':
        for _ in range(int(r.integers(2, 4))):
            x, y = int(r.integers(2, T - 2)), int(r.integers(3, T - 1))
            a[y, x, :3] = GR_DK2; a[y - 1, x - 1, :3] = GR_DK; a[y - 1, x + 1, :3] = GR_DK; a[y - 2, x, :3] = GR_LT
    if kind == 'flowers':
        for _ in range(int(r.integers(3, 6))):
            x, y = int(r.integers(1, T - 1)), int(r.integers(1, T - 2))
            a[y, x, :3] = [FL_W, FL_Y, FL_P][int(r.integers(0, 3))]; a[y + 1, x, :3] = GR_DK
    if kind in ('dirt', 'dark'):
        yy, xx = np.mgrid[0:T, 0:T]
        cx, cy, rx, ry = 8 + r.integers(-1, 2), 8 + r.integers(-1, 2), r.integers(4, 7), r.integers(3, 6)
        e = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 + 0.35 * r.random((T, T))
        inner, rim = e < 1, (e >= 1) & (e < 1.35) & ((xx + yy) % 2 == 0)      # dithered rim, hard pixels
        if kind == 'dirt':
            a[inner, :3] = DIRT; a[inner & (r.random((T, T)) < .3), :3] = DIRT_DK; a[inner & (r.random((T, T)) < .15), :3] = DIRT_LT
            a[rim, :3] = DIRT_LT
        else:
            a[inner | rim, :3] = GR_DK; a[inner & (r.random((T, T)) < .2), :3] = GR_DK2
    return a


def tree_pit():
    """the square of soil a street tree stands in (dark earth, a stone rim), set in the paving as in the reference"""
    r = rng(6)
    a = EX.paver(0)
    a[1:15, 1:15, :3] = PIT_RIM; a[2:14, 2:14, :3] = PIT_SOIL
    m = r.random((12, 12))
    a[2:14, 2:14][m < .18, :3] = PIT_SOIL_LT; a[2:14, 2:14][m > .9, :3] = PIT_SOIL_DK
    a[1, 1:15, :3] = PIT_RIM_LT; a[1:15, 1, :3] = PIT_RIM_LT                 # light on the top / left edge
    return a


def tile_table():
    t = {}
    for v in range(3):
        t[f'asphalt_{v}'] = asphalt(v)
    t['asphalt_crack_0'], t['asphalt_crack_1'] = asphalt(10, crack=True), asphalt(11, crack=True)
    t['asphalt_worn'] = asphalt(12, worn=True)
    t['asphalt_manhole'] = asphalt(13, manhole=True)
    t['asphalt_dash'] = asphalt(14, dash=True)
    t['asphalt_zebra'] = asphalt(15, zebra=True)
    for v in range(4):
        t[f'paver_{v}'] = EX.paver(v)
    for s in 'ltrb':
        t[f'kerb_{s}'] = EX.kerb(s, int(ord(s)) % 4)
        t[f'ramp_{s}'] = ramp(s)
        t[f'paver_dirt_{s}'] = paver_dirt(s)
        t[f'paver_end_{s}'] = paver_end(s)
    for n, sides in (('kerb_corner_nw', 'lt'), ('kerb_corner_ne', 'tr'), ('kerb_corner_sw', 'lb'), ('kerb_corner_se', 'rb')):
        t[n] = kerb_corner(sides)
    t['tree_pit'] = tree_pit()
    for v in range(3):
        t[f'grass_{v}'] = grass(v)
    t['grass_tuft_0'], t['grass_tuft_1'] = grass(3, 'tuft'), grass(4, 'tuft')
    t['grass_flowers_0'], t['grass_flowers_1'] = grass(5, 'flowers'), grass(6, 'flowers')
    t['grass_dirt_0'], t['grass_dirt_1'] = grass(7, 'dirt'), grass(8, 'dirt')
    t['grass_dark'] = grass(9, 'dark')
    t['asphalt_dash_h'] = asphalt(16, dash=True, horizontal=True)
    t['asphalt_zebra_h'] = asphalt(17, zebra=True, horizontal=True)
    for cn in ('nw', 'ne', 'sw', 'se'):
        t[f'kerb_inner_{cn}'] = kerb_inner(cn)
    for n, conn in (('hedge_corner_nw', 'es'), ('hedge_corner_ne', 'ws'), ('hedge_corner_sw', 'ne'), ('hedge_corner_se', 'nw')):
        t[n] = EX.hedge(conn)
    for n, conn, post in (('hedge_v', 'ns', False), ('hedge_post_v', 'ns', True), ('hedge_end_top', 's', False), ('hedge_end_bottom', 'n', False),
                          ('hedge_h', 'ew', False), ('hedge_post_h', 'ew', True), ('hedge_end_left', 'e', False), ('hedge_end_right', 'w', False)):
        t[n] = EX.hedge(conn, post)
    return t


SOLID_TILES = {'hedge_corner_nw', 'hedge_corner_ne', 'hedge_corner_sw', 'hedge_corner_se', 'hedge_v', 'hedge_post_v', 'hedge_end_top', 'hedge_end_bottom', 'hedge_h', 'hedge_post_h', 'hedge_end_left', 'hedge_end_right'}


# ===================================================================== props
def lamp():
    """the garden lamp of the user's art (tiled/props/lamp.png), its leftover lawn specks removed"""
    a = np.array(Image.open('tiled/props/lamp.png').convert('RGBA')).astype(int)
    g = (a[..., 1] > a[..., 0] + 12) & (a[..., 1] > a[..., 2] + 12)
    al = (a[..., 3] > 0) & ~g
    lab = np.zeros(al.shape, int); best = (0, 0); n = 0
    for sy, sx in zip(*np.nonzero(al)):
        if lab[sy, sx]: continue
        n += 1; st = [(sy, sx)]; lab[sy, sx] = n; k = 0
        while st:
            y, x = st.pop(); k += 1
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < al.shape[0] and 0 <= nx < al.shape[1] and al[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = n; st.append((ny, nx))
        best = max(best, (k, n))
    al = lab == best[1]
    ys, xs = np.nonzero(al)
    out = np.zeros(a.shape, np.uint8)
    out[..., :3] = to_palette(a[..., :3]); out[..., 3] = np.where(al, 255, 0)
    return out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def draw(w, h, fn):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); fn(ImageDraw.Draw(im))
    return np.array(im)


def C(c):
    return (*[int(v) for v in c], 255)


def dustbin():
    def f(d):
        d.rectangle((1, 3, 9, 13), fill=C(BIN), outline=C(OL))
        d.line((3, 5, 3, 11), fill=C(BIN_LT)); d.line((7, 5, 7, 11), fill=C(BIN_DK))
        d.rectangle((0, 1, 10, 3), fill=C(BIN_DK), outline=C(OL))
        d.line((4, 0, 6, 0), fill=C(OL))
    return draw(11, 14, f)


def bench():
    """a park bench along a north-south footpath: seat slats facing the road (west), backrest on the east"""
    def f(d):
        for y in (2, 26):
            d.rectangle((0, y, 11, y + 2), fill=C(METAL), outline=C(OL))
        d.rectangle((0, 0, 7, 29), fill=C(WOOD), outline=C(OL))
        d.line((2, 1, 2, 28), fill=C(WOOD_LT)); d.line((5, 1, 5, 28), fill=C(WOOD_DK))
        d.rectangle((8, 0, 11, 29), fill=C(WOOD_DK), outline=C(OL))
        d.line((9, 1, 9, 28), fill=C(WOOD))
    return draw(12, 30, f)


def bench_h():
    """the bench for an east-west footpath: seat facing the road (south side of a north footpath), backrest behind"""
    return np.ascontiguousarray(np.rot90(bench(), 1))


def bike_rack():
    """three bicycles parked side by side at a rack, seen from the side (as in the street photos)"""
    def f(d):
        d.rectangle((0, 1, 1, 27), fill=C(METAL), outline=C(OL))
        for i, y in enumerate((0, 9, 18)):
            for cx in (5, 15):
                d.ellipse((cx - 4, y + 2, cx + 4, y + 10), outline=C(OL))
                d.point((cx, y + 6), fill=C(METAL_LT))
            col = BIKE if i != 1 else BIN_LT
            d.line((5, y + 6, 9, y + 3), fill=C(col)); d.line((9, y + 3, 15, y + 6), fill=C(col))
            d.line((9, y + 3, 10, y + 6), fill=C(col)); d.line((5, y + 6, 10, y + 6), fill=C(col))
            d.line((8, y + 2, 10, y + 2), fill=C(OL)); d.line((14, y + 2, 15, y + 6), fill=C(BIKE_DK)); d.line((13, y + 1, 15, y + 1), fill=C(OL))
    return draw(20, 29, f)


def barricade():
    """a folding barricade sign (the street photos have one), small and plain"""
    def f(d):
        d.line((2, 7, 0, 13), fill=C(METAL_LT)); d.line((12, 7, 14, 13), fill=C(METAL_LT))
        d.line((3, 7, 4, 13), fill=C(METAL)); d.line((11, 7, 10, 13), fill=C(METAL))
        d.rectangle((1, 0, 13, 7), fill=C(KERB), outline=C(OL))
        d.line((3, 3, 11, 3), fill=C(P((190, 70, 70)))); d.line((3, 4, 11, 4), fill=C(P((190, 70, 70))))
    return draw(15, 14, f)


PROPS = {}


def make_assets():
    os.makedirs(GEN, exist_ok=True)
    tt = tile_table()
    names = list(tt)
    cols = 8
    sheet = np.zeros((math.ceil(len(names) / cols) * T, cols * T, 4), np.uint8)
    for i, n in enumerate(names):
        EX.assert_palette(n, tt[n])
        sheet[(i // cols) * T:(i // cols + 1) * T, (i % cols) * T:(i % cols + 1) * T] = tt[n]
    Image.fromarray(sheet).save(f'{GEN}/street_tiles.png')
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'street', 'image': '../generated/street/street_tiles.png',
               'imagewidth': sheet.shape[1], 'imageheight': sheet.shape[0], 'tilewidth': T, 'tileheight': T, 'tilecount': len(names),
               'columns': cols, 'margin': 0, 'spacing': 0,
               'tiles': [{'id': i, 'type': n, **({'properties': [{'name': 'solid', 'type': 'bool', 'value': True}]} if n in SOLID_TILES else {})}
                         for i, n in enumerate(names)]}, open('tiled/tilesets/street.tsj', 'w'), indent=1)
    items = []
    for name, img in (('street_lamp', lamp()), ('dustbin', dustbin()), ('bench', bench()), ('bike_rack', bike_rack()), ('barricade', barricade()),
                      ('bench_h', bench_h())):
        img[img[..., 3] > 0, 3] = 255; img[img[..., 3] == 0] = 0
        img[..., :3] = np.where(img[..., 3:4] > 0, to_palette(img[..., :3]), 0)
        EX.assert_palette(name, img)
        Image.fromarray(img).save(f'{GEN}/{name}.png')
        h, w = img.shape[:2]
        coll = {'street_lamp': (w // 2 - 8, h - 16, 16, 16), 'dustbin': (0, h - 8, w, 8), 'bench': (0, 0, w, h),
                'bike_rack': (w // 2 - 8, 2, 16, h - 4), 'barricade': (0, h - 6, w, 6), 'bench_h': (0, 0, w, h)}[name]
        items.append((name, w, h, coll))
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'street_objects',
               'tilewidth': max(i[1] for i in items), 'tileheight': max(i[2] for i in items), 'tilecount': len(items),
               'columns': 0, 'margin': 0, 'spacing': 0, 'grid': {'orientation': 'orthogonal', 'width': 1, 'height': 1},
               'tiles': [{'id': i, 'image': f'../generated/street/{n}.png', 'imagewidth': w, 'imageheight': h,
                          'properties': [{'name': 'prop', 'type': 'string', 'value': n}]
                          + [{'name': k, 'type': 'int', 'value': int(v)} for k, v in zip(('collision_x', 'collision_y', 'collision_w', 'collision_h'), coll)]}
                         for i, (n, w, h, coll) in enumerate(items)]}, open('tiled/tilesets/street_objects.tsj', 'w'), indent=1)
    return names


# ===================================================================== layout: every road around the hostels
def stamp_alpha(path):
    return np.array(Image.open(os.path.normpath(os.path.join('tiled/tilesets', path))).convert('RGBA'))[..., 3] > 0


def wmedian(vals, weights):
    o = np.argsort(vals); v, w = np.array(vals)[o], np.array(weights)[o]
    return float(v[np.searchsorted(np.cumsum(w), w.sum() / 2)])


def layout_network(area, aname, M, prev):
    """the roads around the hostels (AREAS[aname]['slots']), laid out the way the approved test area was"""
    A = AREAS[aname]
    MW, MH = M['width'], M['height']
    W, H = MW * T, MH * T
    L = {l['name'].split(' ')[0]: l for l in M['layers']}
    if 'shadows' not in L:
        sh = {'id': M['nextlayerid'], 'name': 'shadows', 'type': 'objectgroup', 'draworder': 'topdown', 'x': 0, 'y': 0, 'opacity': 1,
              'visible': True, 'objects': []}
        M['nextlayerid'] += 1
        M['layers'].insert(next(i for i, l in enumerate(M['layers']) if l['name'] == 'buildings'), sh)
        L['shadows'] = sh
    decor, above, ground = L['decor']['data'], L['above']['data'], L['ground']['data']
    tag = f'bty:{aname}'

    def first_of(src):
        return next((t['firstgid'] for t in M['tilesets'] if t.get('source', '').endswith('/' + src)), None)
    for src in ('trees.tsj', 'street_objects.tsj', 'street.tsj'):
        if first_of(src) is None:
            nxt = max(t['firstgid'] + json.load(open(os.path.join('tiled/maps', t['source'])))['tilecount'] for t in M['tilesets'])
            M['tilesets'].append({'firstgid': nxt, 'source': f'../tilesets/{src}'})
    TERR, TREES, SOBJ, STREET = first_of('terrain.tsj'), first_of('trees.tsj'), first_of('street_objects.tsj'), first_of('street.tsj')
    street_names = [t['type'] for t in json.load(open('tiled/tilesets/street.tsj'))['tiles']]
    assert STREET + len(street_names) <= max([t['firstgid'] for t in M['tilesets'] if t['firstgid'] > STREET] + [10 ** 9])
    sgid = {n: STREET + i for i, n in enumerate(street_names)}
    sobj = {next(p['value'] for p in t['properties'] if p['name'] == 'prop'): t for t in json.load(open('tiled/tilesets/street_objects.tsj'))['tiles']}
    trees_ts = json.load(open('tiled/tilesets/trees.tsj'))['tiles']
    tree_tile = {t['image'].split('/')[-1][:-4]: t for t in trees_ts}
    tree_info = json.load(open('tiled/generated/trees/trees.json'))['sprites']
    slots = json.load(open(f'data/{area}_slots.json'))
    roads = json.load(open(f'data/{area}_roads.json'))
    report = {}

    # ---- clear what beautify laid before (any area of it): its objects, its decor box, its canopy anchors
    for lname in ('props', 'shadows'):
        L[lname]['objects'] = [o for o in L[lname]['objects'] if not str(o.get('name', '')).startswith('bty:')]
    for ar in prev:
        c0, r0, c1, r1 = ar['box']
        for r in range(max(0, r0), min(MH, r1 + 1)):
            for c in range(max(0, c0), min(MW, c1 + 1)):
                if decor[r * MW + c] >= STREET:
                    decor[r * MW + c] = 0
                if TREES <= (above[r * MW + c] & 0x1FFFFFFF) < TREES + len(trees_ts):
                    above[r * MW + c] = 0
        for c, r in ar.get('above_cells', []):
            if 0 <= r < MH and 0 <= c < MW and TREES <= (above[r * MW + c] & 0x1FFFFFFF) < TREES + len(trees_ts):
                above[r * MW + c] = 0

    # ---- the region: the hostels and REGION_MARGIN tiles round them
    hostels = [s_ for s_ in slots if s_['name'] in A['slots'] and s_['type'].startswith('stamp:')]
    m = A['margin']
    rc0, rr0 = max(0, min(s_['x'] for s_ in hostels) - m), max(0, min(s_['y'] for s_ in hostels) - m)
    rc1, rr1 = min(MW - 1, max(s_['x'] + s_['w'] for s_ in hostels) + m), min(MH - 1, max(s_['y'] + s_['h'] for s_ in hostels) + m)
    inreg = lambda c, r: rc0 <= c <= rc1 and rr0 <= r <= rr1

    # ---- what may not be built on
    bpx = np.zeros((H, W), bool)
    bts = json.load(open('tiled/tilesets/buildings.tsj')); BFIRST = first_of('buildings.tsj')
    for o in L['buildings']['objects']:
        if 'gid' in o:
            al = stamp_alpha(bts['tiles'][(o['gid'] & 0x1FFFFFFF) - BFIRST]['image'])
            x, y = int(o['x']), int(o['y'] - o['height'])
            sub = bpx[max(0, y):y + al.shape[0], max(0, x):x + al.shape[1]]
            sub |= al[max(0, -y):max(0, -y) + sub.shape[0], max(0, -x):max(0, -x) + sub.shape[1]]
        else:
            bpx[int(o['y']):int(o['y'] + o['height']), int(o['x']):int(o['x'] + o['width'])] = True
    blocked = bpx.reshape(MH, T, MW, T).mean(axis=(1, 3)) > 0.15
    building = blocked.copy()
    for o in L['events']['objects']:
        if (o.get('type') or o.get('class')) in ('spawn', 'door') or o.get('name') == 'spawn':
            blocked[int(o['y'] // T), int(o['x'] // T)] = True
    for o in L['collision']['objects']:
        blocked[int(o['y'] // T):math.ceil((o['y'] + o['height']) / T), int(o['x'] // T):math.ceil((o['x'] + o['width']) / T)] = True
    shp = Image.new('L', (W, H), 0); dsh = ImageDraw.Draw(shp)          # the front garden's own drawings (hedges, terrace, beds)
    for o in L['props']['objects']:
        k = o.get('type') or o.get('class')
        if 'polyline' in o and k == 'hedge':
            dsh.line([(o['x'] + p_['x'], o['y'] + p_['y']) for p_ in o['polyline']], fill=255, width=24)
        elif 'polygon' in o:
            dsh.polygon([(o['x'] + p_['x'], o['y'] + p_['y']) for p_ in o['polygon']], fill=255)
        elif 'gid' in o:
            blocked[int((o['y'] - 4) // T), min(MW - 1, int((o['x'] + o['width'] / 2) // T))] = True
    blocked |= np.array(shp).reshape(MH, T, MW, T).max(axis=(1, 3)) > 0
    tid = lambda c, r: ground[r * MW + c] - TERR
    is_road = lambda c, r: 1 <= tid(c, r) <= 15
    is_grass = lambda c, r: 64 <= tid(c, r) <= 67
    is_path = lambda c, r: 16 <= tid(c, r) <= 31
    excluded = np.zeros((MH, MW), bool)
    for ex_, ey_ in roads.get('drive_ends', []):       # the front garden's drive meets the roads here: left as it is
        cx_, cy_ = ex_ // T, ey_ // T
        excluded[max(0, cy_ - DRIVE_CLEAR):cy_ + DRIVE_CLEAR + 1, max(0, cx_ - DRIVE_CLEAR):cx_ + DRIVE_CLEAR + 1] = True

    # ---- straight road pieces from the OSM centre lines, straightened, nudged clear of buildings, joined at junctions
    pieces, skipped = [], []
    for w_ in roads['ways']:
        pts, aw = w_['pts'], w_['w_tiles'] - 1
        runs = []
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            k = 'v' if abs(dx) <= .25 * abs(dy) else 'h' if abs(dy) <= .25 * abs(dx) else 'd'
            if runs and runs[-1][0] == k and k != 'd':
                runs[-1][1].append((ax, ay, bx, by))
            else:
                runs.append((k, [(ax, ay, bx, by)]))
        for k, segs in runs:
            xs = [v for s_ in segs for v in (s_[0], s_[2])]; ys = [v for s_ in segs for v in (s_[1], s_[3])]
            if k == 'd':                               # a bend: left as drawn, and nothing laid close to it
                if any(inreg(int(x // T), int(y // T)) for x, y in zip(xs, ys)):
                    skipped.append((w_['id'], w_['name'], 'diagonal stretch, left as drawn'))
                    for x, y in zip(xs, ys):
                        cx_, cy_ = int(x // T), int(y // T)
                        excluded[max(0, cy_ - 6):cy_ + 7, max(0, cx_ - 6):cx_ + 7] = True
                continue
            lens = [math.hypot(s_[2] - s_[0], s_[3] - s_[1]) for s_ in segs]
            if k == 'v':
                pos = wmedian([(s_[0] + s_[2]) / 2 for s_ in segs], lens); lo, hi = min(ys), max(ys)
            else:
                pos = wmedian([(s_[1] + s_[3]) / 2 for s_ in segs], lens); lo, hi = min(xs), max(xs)
            v0, v1 = int(lo // T), int(hi // T)
            a0 = int(round(pos / T - aw / 2))
            lim = MH - 1 if k == 'v' else MW - 1
            r_lo, r_hi = (rr0, rr1) if k == 'v' else (rc0, rc1)
            u_lo, u_hi = (rc0, rc1) if k == 'v' else (rr0, rr1)
            v0c, v1c = max(v0, r_lo, 0), min(v1, r_hi, lim)
            if v1c - v0c < 3 or not (u_lo - 2 <= a0 + aw // 2 <= u_hi + 2):
                continue
            pieces.append(dict(axis=k, a0=a0, aw=aw, v0=v0c, v1=v1c, way=w_['id'], name=w_['name'], clipped=(v0c > v0, v1c < v1)))

    def cell(pc, u, v):
        return (u, v) if pc['axis'] == 'v' else (v, u)

    def band_blocked(pc, a0):
        n = 0
        for v in range(pc['v0'], pc['v1'] + 1):
            for u in list(range(a0 - FOOTPATH - 1, a0)) + list(range(a0 + pc['aw'], a0 + pc['aw'] + FOOTPATH + 1)):
                c, r = cell(pc, u, v)
                if 0 <= c < MW and 0 <= r < MH and building[r, c]:
                    n += 1
        return n
    # nudge by a tile where that keeps the footpaths clear of buildings; a road lines up with the road that continues
    # from its end (same direction), so junctions do not step. Longest pieces first: the short ones follow them.
    done = []
    for pc in sorted(pieces, key=lambda p_: -(p_['v1'] - p_['v0'])):
        nbr = [q['a0'] for q in done if q['axis'] == pc['axis'] and abs(q['a0'] - pc['a0']) <= 2
               and (abs(q['v0'] - pc['v1']) <= 8 or abs(pc['v0'] - q['v1']) <= 8)]
        def cost(s_):
            return band_blocked(pc, pc['a0'] + s_) * 4 + abs(s_) + (3 if nbr and pc['a0'] + s_ not in nbr else 0)
        best = min((cost(s_), s_) for s_ in (0, -1, 1, -2, 2))
        pc['a0'] += best[1]; pc['a1'] = pc['a0'] + pc['aw'] - 1
        done.append(pc)
    asp = np.zeros((MH, MW), bool); owner = np.zeros((MH, MW), np.int16)
    for i, pc in enumerate(pieces):
        for v in range(pc['v0'], pc['v1'] + 1):
            for u in range(pc['a0'], pc['a1'] + 1):
                c, r = cell(pc, u, v)
                if 0 <= c < MW and 0 <= r < MH and not excluded[r, c] and not blocked[r, c]:
                    asp[r, c] = True; owner[r, c] += 1
    for p_ in pieces:                                  # two ends of one road a few tiles apart across a junction: one road
        for q in pieces:
            if p_ is q or p_['axis'] != q['axis'] or p_['a0'] != q['a0'] or p_['aw'] != q['aw']: continue
            gap = q['v0'] - p_['v1'] - 1
            if 0 < gap <= 8:
                for v in range(p_['v1'] + 1, q['v0']):
                    for u in range(p_['a0'], p_['a1'] + 1):
                        c, r = cell(p_, u, v)
                        if 0 <= c < MW and 0 <= r < MH and not excluded[r, c] and not blocked[r, c] and not asp[r, c]:
                            asp[r, c] = True; owner[r, c] += 1
    for pc in pieces:                                  # join the ends: run on while the ground is road (junction gaps)
        for end, step in ((pc['v0'], -1), (pc['v1'], 1)):
            v = end
            for _ in range(7):
                v2 = v + step
                cs = [cell(pc, u, v2) for u in range(pc['a0'], pc['a1'] + 1)]
                if not all(0 <= c < MW and 0 <= r < MH and not excluded[r, c] and not blocked[r, c] and (is_road(c, r) or asp[r, c]) for c, r in cs):
                    break
                if all(asp[r, c] for c, r in cs):
                    v = v2; break
                for c, r in cs:
                    if not asp[r, c]:
                        asp[r, c] = True; owner[r, c] += 1
                v = v2
                if not inreg(*cs[0]):
                    break
            if step < 0: pc['v0'] = min(pc['v0'], v)
            else: pc['v1'] = max(pc['v1'], v)
    junction = owner >= 2
    for pc in pieces:                                  # a clipped end: the road goes on unchanged; nothing is laid across it
        for clipped, end, step in ((pc['clipped'][0], pc['v0'], -1), (pc['clipped'][1], pc['v1'], 1)):
            if clipped:
                for d_ in range(1, 7):
                    for u in range(pc['a0'] - FOOTPATH - 2, pc['a1'] + FOOTPATH + 3):
                        c, r = cell(pc, u, end + step * d_)
                        if 0 <= c < MW and 0 <= r < MH and not asp[r, c]:
                            excluded[r, c] = True
    report['pieces'] = [(pc['name'] or pc['way'], pc['axis'], pc['a0'], pc['a1'], pc['v0'], pc['v1']) for pc in pieces]
    report['skipped'] = sorted(set(skipped))

    # ---- distance from the asphalt (8-neighbour steps): 1 kerb, 2-4 pavers, 5 hedge, 6 the lawn behind it
    dist = np.full((MH, MW), 99, np.int16); dist[asp] = 0
    for dd in range(1, 9):
        prevm = dist == dd - 1
        p_ = np.pad(prevm, 1)
        grow = np.zeros_like(prevm)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                grow |= p_[dy:dy + MH, dx:dx + MW]
        dist[grow & (dist == 99)] = dd
    ok = ~blocked & ~excluded
    for r in range(MH):
        for c in range(MW):
            if is_road(c, r) and not asp[r, c] and dist[r, c] > 2:
                ok[r, c] = False                       # somebody else's road
    out = {}
    R = rng(7, zlib.crc32(aname.encode()) & 0xFFFF)
    for r in range(MH):
        for c in range(MW):
            if not ok[r, c] or (dist[r, c] > 6 and not asp[r, c]):
                continue
            d = dist[r, c]
            if d == 1: out[(c, r)] = 'kerb'
            elif 2 <= d <= 4: out[(c, r)] = f'paver_{int(R.integers(0, 4))}'
            elif d == 5:
                out[(c, r)] = 'gap' if (is_path(c, r) or any(is_path(c + dx, r + dy) and dist[r + dy, c + dx] == 6
                                                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                                          if 0 <= c + dx < MW and 0 <= r + dy < MH)) else ('hedge' if is_grass(c, r) or is_path(c, r) else 'gap')

    # ---- gaps where paths come in: 3 wide, paved; a zebra crossing across the road in front of each
    gaps = {k for k, v in out.items() if v == 'gap'}
    wide = set(gaps)
    for c, r in gaps:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if out.get((c + dx, r + dy)) == 'hedge':
                wide.add((c + dx, r + dy))
    no_go = set()
    crossings = []
    seen = set()
    comps = []
    for g in sorted(wide):
        if g in seen: continue
        comp, st = [], [g]; seen.add(g)
        while st:
            c, r = st.pop(); comp.append((c, r))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                n_ = (c + dx, r + dy)
                if n_ in wide and n_ not in seen:
                    seen.add(n_); st.append(n_)
        comps.append(comp)
    gates = [(s_['gate'][0] // T, s_['gate'][1] // T) for s_ in slots if 'gate' in s_]
    comps.sort(key=lambda cm: (min((abs(c - a) + abs(r - b) for c, r in cm for a, b in gates), default=999), sorted(cm)[0]))
    for comp in comps:                                 # hostel gates first: their crossing wins where two paths come in close
        for c, r in comp:
            out[(c, r)] = f'paver_{int(R.integers(0, 4))}'; no_go.add((c, r))
        # which road is this gap on: walk from its middle towards the asphalt
        c, r = sorted(comp)[len(comp) // 2]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            hit = next(((c + dx * k, r + dy * k) for k in range(1, 7) if 0 <= c + dx * k < MW and 0 <= r + dy * k < MH and asp[r + dy * k, c + dx * k]), None)
            if hit is None: continue
            axis = 'v' if dx else 'h'                  # the road runs across the walking direction
            for cg, rg in comp:                        # the way through, gap -> kerb -> across -> far footpath, stays clear
                for k in range(0, 14):
                    n_ = (cg + dx * k, rg + dy * k)
                    if not (0 <= n_[0] < MW and 0 <= n_[1] < MH) or dist[n_[1], n_[0]] > FOOTPATH + 2: break
                    no_go.add(n_)
            lines = sorted({rr for _, rr in comp} if axis == 'v' else {cc for cc, _ in comp})
            cells_ = []
            for ln in lines:
                c_, r_ = (hit[0], ln) if axis == 'v' else (ln, hit[1])
                rowcells = []
                k_ = 0
                while True:                            # the whole width of the asphalt on that line
                    cc, rr = (c_ + dx * k_, r_) if axis == 'v' else (c_, r_ + dy * k_)
                    if not (0 <= cc < MW and 0 <= rr < MH and asp[rr, cc]): break
                    rowcells.append((cc, rr)); k_ += 1
                cells_ += rowcells
            near_other = any(ax2 == axis and any(abs(cc - c2) + abs(rr - r2) <= 4 for cc, rr in cells_ for c2, r2 in cl2[::3])
                             for ax2, cl2 in crossings)      # one crossing where two paths come in close together
            if cells_ and not near_other and not any(junction[rr, cc] for cc, rr in cells_):
                crossings.append((axis, cells_))
                for cc, rr in cells_:
                    no_go.add((cc, rr))
                    for e in (1, 2, 3, 4, 5):          # the far footpath in front of it stays clear too
                        for sgn in (1, -1):
                            n_ = (cc + sgn * e, rr) if axis == 'v' else (cc, rr + sgn * e)
                            if n_ in out: no_go.add(n_)
            break
    zebra = {}
    for axis, cells_ in crossings:
        for cc, rr in cells_:
            zebra[(cc, rr)] = axis
    ramp_cells = set()
    for (cc, rr), axis in zebra.items():
        for sgn in (1, -1):
            n_ = (cc + sgn, rr) if axis == 'v' else (cc, rr + sgn)
            if out.get(n_) == 'kerb': ramp_cells.add(n_)

    # ---- kerb pieces: the strip faces the asphalt; inner corner blocks on the outside of bends
    for (c, r), v in list(out.items()):
        if v != 'kerb': continue
        sides = ''.join(s_ for s_, (dx, dy) in (('l', (-1, 0)), ('r', (1, 0)), ('t', (0, -1)), ('b', (0, 1)))
                        if 0 <= c + dx < MW and 0 <= r + dy < MH and asp[r + dy, c + dx])
        key = ''.join(sorted(sides))
        if len(key) == 1:
            out[(c, r)] = ('ramp_' if (c, r) in ramp_cells else 'kerb_') + key
        elif key in ('lt', 'rt', 'bl', 'br'):
            out[(c, r)] = {'lt': 'kerb_corner_nw', 'rt': 'kerb_corner_ne', 'bl': 'kerb_corner_sw', 'br': 'kerb_corner_se'}[key]
        elif not key:
            diag = [cn for cn, (dx, dy) in (('nw', (-1, -1)), ('ne', (1, -1)), ('sw', (-1, 1)), ('se', (1, 1)))
                    if 0 <= c + dx < MW and 0 <= r + dy < MH and asp[r + dy, c + dx]]
            out[(c, r)] = f'kerb_inner_{diag[0]}' if diag else f'paver_{int(R.integers(0, 4))}'
        else:
            out[(c, r)] = 'kerb_' + key[0]
    # ---- road surface
    centre = {}
    for i, pc in enumerate(pieces):
        if pc['aw'] == 3:
            for v in range(pc['v0'], pc['v1'] + 1):
                centre[cell(pc, pc['a0'] + 1, v)] = pc['axis']
    for r in range(MH):
        for c in range(MW):
            if not asp[r, c] or excluded[r, c] or blocked[r, c]: continue
            if (c, r) in zebra:
                out[(c, r)] = 'asphalt_zebra' if zebra[(c, r)] == 'v' else 'asphalt_zebra_h'
            elif (c, r) in centre and not junction[r, c]:
                out[(c, r)] = 'asphalt_dash' if centre[(c, r)] == 'v' else 'asphalt_dash_h'
            else:
                v = R.random()
                out[(c, r)] = ('asphalt_crack_0' if v < .03 else 'asphalt_crack_1' if v < .05 else 'asphalt_worn' if v < .10
                               else 'asphalt_manhole' if v < .104 and not junction[r, c] else f'asphalt_{int(R.integers(0, 3))}')
    # ---- hedge pieces (4-neighbour joins), wire posts on straight runs
    hedge = {k for k, v in out.items() if v == 'hedge'}
    for c, r in hedge:
        conn = ''.join(s_ for s_, (dx, dy) in (('n', (0, -1)), ('s', (0, 1)), ('e', (1, 0)), ('w', (-1, 0))) if (c + dx, r + dy) in hedge)
        name = {'ns': 'hedge_v', 'ew': 'hedge_h', 'es': 'hedge_corner_nw', 'sw': 'hedge_corner_ne', 'ne': 'hedge_corner_sw', 'nw': 'hedge_corner_se',
                's': 'hedge_end_top', 'n': 'hedge_end_bottom', 'e': 'hedge_end_left', 'w': 'hedge_end_right'}.get(conn)
        if name is None:
            name = 'hedge_v' if ('n' in conn or 's' in conn) else 'hedge_h'
        if name in ('hedge_v', 'hedge_h') and ((c * 73856093 ^ r * 19349663 ^ SEED) & 0xFF) < 46:
            name = name.replace('hedge_', 'hedge_post_')
        out[(c, r)] = name

    # ---- street trees along each piece: trunk on the footpath's outer line, crown on `above`, shadow on `shadows`
    objs, shadows, above_cells = [], [], []
    asp_edge = asp & ~(np.pad(asp, 1)[:-2, 1:-1] & np.pad(asp, 1)[2:, 1:-1] & np.pad(asp, 1)[1:-1, :-2] & np.pad(asp, 1)[1:-1, 2:])
    crown_img = {}
    def crown(n, flip):
        if (n, flip) not in crown_img:
            img = stamp_alpha(tree_tile[f'{n}_canopy_cell']['image'])
            crown_img[(n, flip)] = img[:, ::-1] if flip else img
        return crown_img[(n, flip)]
    def crown_cells(n, c, r, flip):
        img = crown(n, flip); wt = tree_info[n]['size_tiles'][0]
        x0, y0 = (c - wt // 2) * T, r * T - img.shape[0]
        ys, xs = np.nonzero(img)
        return {(int((x0 + x) // T), int((y0 + y) // T)) for x, y in zip(xs[::5], ys[::5])}, (x0, y0, img)
    under_crown, taken, trunks = set(), set(), []
    def plant_tree(n, c, r, flip, cls, street=True):
        info = tree_info[n]; wt = info['size_tiles'][0]
        cells_, (x0, y0, img) = crown_cells(n, c, r, flip)
        if any(not (0 <= cc < MW and 0 <= rr < MH) for cc, rr in cells_): return False
        if cells_ & no_go: return False
        if any(asp[rr, cc] and not asp_edge[rr, cc] for cc, rr in cells_): return False        # at most one tile over the road
        sub = bpx[max(0, y0):y0 + img.shape[0], max(0, x0):x0 + img.shape[1]]
        if (sub & img[max(0, -y0):max(0, -y0) + sub.shape[0], max(0, -x0):max(0, -x0) + sub.shape[1]]).sum() > 0.04 * img.sum():
            return False                                                                        # not over a building
        if any(max(abs(c - a), abs(r - b)) < 2 for a, b in trunks):
            return False                                                                        # trunks of crossing roads too close
        anchor = (c - wt // 2, r - 1)
        if not (0 <= anchor[0] < MW) or above[anchor[1] * MW + anchor[0]] or anchor in above_cells_set: return False
        trunk = tree_tile[f'{n}_trunk']; cellt = tree_tile[f'{n}_canopy_cell']
        g_t, g_c = TREES + trunk['id'], TREES + cellt['id']
        if flip: g_t |= FLIP_H; g_c |= FLIP_H
        objs.append(dict(gid=g_t, x=(c - wt // 2) * T, y=(r + 1) * T, width=trunk['imagewidth'], height=trunk['imageheight']))
        above[anchor[1] * MW + anchor[0]] = g_c; above_cells.append(list(anchor)); above_cells_set.add(anchor)
        cpx = info['canopy_px']; tx = c * T + T // 2
        shadows.append((tx + 6 - cpx // 2, (r + 1) * T - 7, cpx, max(8, cpx // 2), 0.25))
        for _ in range(int(R.integers(6, 11)) if street else 3):
            dw, dh = int(R.integers(6, 17)), int(R.integers(3, 9))
            shadows.append((tx - cpx + int(R.integers(0, 2 * cpx)) - dw // 2, (r + 1) * T - 28 + int(R.integers(0, 40)), dw, dh, 0.12))
        under_crown.update(cells_); taken.add((c, r)); trunks.append((c, r))
        return True
    above_cells_set = set()
    weights = [(n, w, cls) for cls, lst in POOL.items() for n, w in lst]
    n_trees = 0
    for pc in pieces:
        for side in (+1, -1):
            u_out = pc['a1'] + FOOTPATH + 1 if side > 0 else pc['a0'] - FOOTPATH - 1
            v = pc['v0'] + int(R.integers(1, 4))
            while v <= pc['v1'] - 1:
                c, r = cell(pc, u_out, v)
                along = [cell(pc, u_out, v + dv) for dv in (-1, 1)]
                okc = (out.get((c, r), '').startswith('paver_') and (c, r) not in no_go and (c, r) not in taken
                       and all(out.get(a_, '').startswith(('paver_', 'hedge')) for a_ in along) and dist[r, c] == FOOTPATH + 1)
                placed = False
                if okc and R.random() >= TREE_SKIP:
                    for i in sorted(R.permutation(len(weights)), key=lambda i: -weights[i][1] * R.random()):
                        n, w, cls = weights[i]
                        info = tree_info[n]
                        if info['collision'][2] != T or info['canopy_px'] > CANOPY_MAX[cls]:
                            continue
                        if plant_tree(n, c, r, bool(R.random() < .5), cls):
                            placed = True; n_trees += 1; break
                v += int(R.integers(TREE_GAP[0], TREE_GAP[1] + 1)) if placed else 1
    report['street_trees'] = n_trees

    # ---- street details along each piece: per 20 tiles 2 lamps (kerb side, alternating), a bin, a bench or a bike
    # rack beside a building, now and then a barricade by the kerb
    def free(c, r):
        return (out.get((c, r), '').startswith('paver_') and not out[(c, r)].startswith('paver_end') and (c, r) not in no_go
                and (c, r) not in taken and (c, r) not in under_crown)
    placed_at = {}
    SPACING = {'street_lamp': 4, 'dustbin': 6, 'bench': 6, 'bike_rack': 6, 'bench_h': 6, 'barricade': 12}
    def spaced(name, c, r):
        return all(max(abs(c - a), abs(r - b)) >= SPACING[name] for a, b in placed_at.get(name, []))
    def place(name, c, r, flip=False, rows=1, horizontal=False):
        placed_at.setdefault(name, []).append((c, r))
        t = sobj[name]
        if horizontal:
            x, y = c * T + T - t['imagewidth'] // 2, (r + 1) * T - 1
        else:
            x, y = c * T + T // 2 - t['imagewidth'] // 2, (r + rows) * T - 1 - (1 if rows > 1 else 0)
        objs.append(dict(gid=(SOBJ + t['id']) | (FLIP_H if flip else 0), x=x, y=y, width=t['imagewidth'], height=t['imageheight']))
    details = []
    for pc in pieces:
        n_st = max(1, (pc['v1'] - pc['v0'] + 1) // STRETCH)
        for k in range(n_st):
            st = pc['v0'] + k * STRETCH; en = min(pc['v1'], st + STRETCH - 1)
            for j, off in enumerate((int(R.integers(2, 7)), int(R.integers(11, 16)))):
                side = (+1, -1)[(k + j) % 2]
                u = pc['a1'] + 2 if side > 0 else pc['a0'] - 2
                for dv in (0, 1, -1, 2, -2, 3):
                    c, r = cell(pc, u, st + off + dv)
                    if st <= st + off + dv <= en and free(c, r) and spaced('street_lamp', c, r):
                        place('street_lamp', c, r); taken.add((c, r)); details.append('street_lamp'); break
            for v in R.permutation(range(st, en + 1)):
                side = (+1, -1)[int(R.integers(0, 2))]
                c, r = cell(pc, pc['a1'] + FOOTPATH + 1 if side > 0 else pc['a0'] - FOOTPATH - 1, int(v))
                if free(c, r) and spaced('dustbin', c, r):
                    place('dustbin', c, r); taken.add((c, r)); details.append('dustbin'); break
            for v in R.permutation(range(st, en)):     # bench or rack, on the side with a building close behind the hedge
                v = int(v); done = False
                for side in (+1, -1):
                    uo = pc['a1'] + FOOTPATH + 1 if side > 0 else pc['a0'] - FOOTPATH - 1
                    near_b = any(building[rr, cc] for e in range(2, 7) for cc, rr in [cell(pc, uo + side * e, v)] if 0 <= cc < MW and 0 <= rr < MH)
                    c1, r1_ = cell(pc, uo, v); c2, r2 = cell(pc, uo, v + 1)
                    if near_b and free(c1, r1_) and free(c2, r2) and spaced('bench', c1, r1_) and spaced('bike_rack', c1, r1_) and spaced('bench_h', c1, r1_):
                        if pc['axis'] == 'v':
                            what = 'bench' if R.random() < .5 else 'bike_rack'
                            place(what, c1, r1_, flip=(side < 0), rows=2)
                        else:
                            what = 'bench_h'; place(what, c1, r1_, horizontal=True)
                        taken |= {(c1, r1_), (c2, r2)}; details.append(what); done = True; break
                if done: break
            if R.random() < .3:
                for v in R.permutation(range(st, en + 1)):
                    c, r = cell(pc, pc['a0'] if R.random() < .5 else pc['a1'], int(v))
                    if asp_edge[r, c] and not junction[r, c] and all(abs(c - a) + abs(r - b) > 4 for a, b in zebra) and spaced('barricade', c, r):
                        place('barricade', c, r); details.append('barricade'); break
    from collections import Counter
    report['details'] = dict(Counter(details))

    # ---- shrub clusters on the lawn just behind the hedges (2-4 mixed shrubs, bare grass between)
    sh_names = [n for n, w in SHRUBS for _ in range(w)]
    n_shrubs = 0
    for pc in pieces:
        for side in (+1, -1):
            u = pc['a1'] + FOOTPATH + 3 if side > 0 else pc['a0'] - FOOTPATH - 3
            v = pc['v0'] + int(R.integers(0, 3))
            while v <= pc['v1']:
                size = int(R.integers(2, 5))
                cl = [cell(pc, u, q) for q in range(v, min(pc['v1'], v + size - 1) + 1)]
                cl = [(c, r) for c, r in cl if 0 <= c < MW and 0 <= r < MH and ok[r, c] and is_grass(c, r) and dist[r, c] == FOOTPATH + 3
                      and (c, r) not in out and (c, r) not in under_crown and (c, r) not in no_go]
                if len(cl) >= 2:
                    for c, r in cl:
                        n = sh_names[int(R.integers(0, len(sh_names)))]; t = tree_tile[n]
                        objs.append(dict(gid=(TREES + t['id']) | (FLIP_H if R.random() < .5 else 0), x=c * T + int(R.integers(-2, 3)),
                                         y=(r + 1) * T + int(R.integers(-3, 1)), width=t['imagewidth'], height=t['imageheight']))
                        out[(c, r)] = f'grass_{int(R.integers(0, 3))}'; n_shrubs += 1
                v += size + int(R.integers(2, 6))
    report['shrubs'] = n_shrubs

    # ---- lawn trees: the full-size umbrella, twin and round trees on open lawns of the region
    lawn = [(c, r) for r in range(rr0, rr1 + 1) for c in range(rc0, rc1 + 1)
            if ok[r, c] and is_grass(c, r) and (c, r) not in out and dist[r, c] >= 8]
    n_lawn_max = len(lawn) // LAWN_CELLS_PER_TREE
    lawn_trees = []
    for i in R.permutation(len(lawn)):
        if len(lawn_trees) >= n_lawn_max: break
        c, r = lawn[int(i)]
        if any(abs(c - a) < LAWN_TREE_SPACING and abs(r - b) < LAWN_TREE_SPACING for a, b, _ in lawn_trees): continue
        n = ('tree_twin', 'tree_umbrella', 'tree_round_big', 'tree_column')[int(R.integers(0, 4))]
        wt = tree_info[n]['size_tiles'][0]
        foot = [(cc, rr) for cc in range(c - wt // 2, c + wt // 2 + 1) for rr in (r, r + 1)]
        if not all(0 <= cc < MW and 0 <= rr < MH and ok[rr, cc] and is_grass(cc, rr) and (cc, rr) not in out
                   and not any(is_path(cc + a, rr + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if 0 <= cc + a < MW and 0 <= rr + b < MH)
                   for cc, rr in foot):
            continue
        if plant_tree(n, c, r, bool(R.random() < .5), 'lawn', street=False):
            lawn_trees.append((c, r, n))
    report['lawn_trees'] = len(lawn_trees)

    # ---- ground variety on every lawn of the region; faint irregular darker patches on `shadows`
    def noise(c, r, scale):
        x, y = c / scale, r / scale
        x0_, y0_ = math.floor(x), math.floor(y)
        def h(i, j):
            return ((i * 73856093 ^ j * 19349663 ^ SEED) & 0xFFFF) / 65535.0
        fx, fy = x - x0_, y - y0_
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        return (h(x0_, y0_) * (1 - fx) + h(x0_ + 1, y0_) * fx) * (1 - fy) + (h(x0_, y0_ + 1) * (1 - fx) + h(x0_ + 1, y0_ + 1) * fx) * fy
    trunk_near = set()
    for t_ in taken:
        for dc in (-1, 0, 1):
            trunk_near.add((t_[0] + dc, t_[1] + 1))
    n_ground = 0
    for r in range(rr0, rr1 + 1):
        for c in range(rc0, rc1 + 1):
            if (c, r) in out or not ok[r, c] or not is_grass(c, r):
                continue
            by_path = any(is_path(c + dc, r + dr) for dc in (-1, 0, 1) for dr in (-1, 0, 1) if 0 <= c + dc < MW and 0 <= r + dr < MH)
            v = R.random()
            if (by_path and v < .3) or ((c, r) in trunk_near and v < .5) or v < .015:
                out[(c, r)] = f'grass_dirt_{int(R.integers(0, 2))}'
            elif v < .13: out[(c, r)] = f'grass_tuft_{int(R.integers(0, 2))}'
            elif v < .18: out[(c, r)] = f'grass_flowers_{int(R.integers(0, 2))}'
            else: out[(c, r)] = f'grass_{int(R.integers(0, 3))}'
            n_ground += 1
            if v > .994 and noise(c, r, 4.0) > .5:     # a darker patch: 3-5 overlapping faint ovals
                for _ in range(int(R.integers(3, 6))):
                    w_, h_ = int(R.integers(16, 44)), int(R.integers(10, 26))
                    shadows.append((c * T + 8 + int(R.integers(-24, 25)) - w_ // 2, r * T + 8 + int(R.integers(-14, 15)) - h_ // 2, w_, h_, 0.07))
    report['ground_cells'] = n_ground

    # ---- footpath ends: where the paving stops at nothing (a clipped road, a bend left as drawn), it fades into earth
    n_fade = 0
    for (c, r), v in list(out.items()):
        if not v.startswith('paver_') or not (2 <= dist[r, c] <= FOOTPATH + 1): continue
        for s_, (dx, dy) in (('l', (-1, 0)), ('r', (1, 0)), ('t', (0, -1)), ('b', (0, 1))):
            n_ = (c + dx, r + dy)
            if 0 <= n_[0] < MW and 0 <= n_[1] < MH and n_ not in out and excluded[n_[1], n_[0]] and not building[n_[1], n_[0]]:
                out[(c, r)] = f'paver_end_{s_}'; n_fade += 1; break
    report['footpath_ends_faded'] = n_fade

    # ---- checks
    for (c, r), nm in out.items():
        assert not blocked[r, c] and not excluded[r, c], f'{nm} on a building / event / excluded cell at {(c, r)}'
        assert nm in sgid, f'unknown tile {nm} at {(c, r)}'
    for o in objs:
        bc, br = int((o['x'] + o['width'] / 2) // T), int((o['y'] - 3) // T)
        assert (bc, br) not in no_go, f'object on a crossing / door approach at {(bc, br)}'
    narrow = 0
    for pc in pieces:
        for v in range(pc['v0'], pc['v1'] + 1):
            for side in (+1, -1):
                us = range(pc['a1'] + 2, pc['a1'] + FOOTPATH + 2) if side > 0 else range(pc['a0'] - FOOTPATH - 1, pc['a0'] - 1)
                cs = [cell(pc, u, v) for u in us]
                if any(junction[r, c] for c, r in [cell(pc, pc['a0'], v)] if 0 <= c < MW and 0 <= r < MH):
                    continue
                if sum(1 for c, r in cs if out.get((c, r), '').startswith(('paver', 'tree_pit'))) < FOOTPATH:
                    narrow += 1
    report['footpath_lines_narrowed_by_buildings_or_bends'] = narrow
    report['crossings'] = len(crossings)

    # ---- write
    for (c, r), nm in out.items():
        decor[r * MW + c] = sgid[nm]
    oid = M['nextobjectid']
    for o in objs:
        L['props']['objects'].append({'id': oid, 'name': tag, 'type': 'prop', 'rotation': 0, 'visible': True, **o}); oid += 1
    for x, y, w_, h_, op in shadows:
        L['shadows']['objects'].append({'id': oid, 'name': tag, 'type': 'shadow', 'ellipse': True, 'x': int(x), 'y': int(y),
                                        'width': int(w_), 'height': int(h_), 'rotation': 0, 'visible': True,
                                        'properties': [{'name': 'opacity', 'type': 'float', 'value': op}]}); oid += 1
    M['nextobjectid'] = oid
    cs_ = [c for c, _ in out]; rs_ = [r for _, r in out]
    report.update(box=[min(cs_), min(rs_), max(cs_), max(rs_)], above_cells=above_cells, tiles=len(out), objects=len(objs), shadows=len(shadows))
    return report


def region_box(area, aname):
    A = AREAS[aname]
    slots = json.load(open(f'data/{area}_slots.json'))
    hs = [s_ for s_ in slots if s_['name'] in A['slots']]
    m = A['margin'] + FOOTPATH + 4
    M = json.load(open(f'tiled/maps/{area}.tmj'))
    return [max(0, min(s_['x'] for s_ in hs) - m), max(0, min(s_['y'] for s_ in hs) - m),
            min(M['width'] - 1, max(s_['x'] + s_['w'] for s_ in hs) + m), min(M['height'] - 1, max(s_['y'] + s_['h'] for s_ in hs) + m)]


if __name__ == '__main__':
    names = make_assets()
    print(f'assets: {len(names)} street tiles, {len(json.load(open("tiled/tilesets/street_objects.tsj"))["tiles"])} props; all colours in the palette')
    if len(sys.argv) < 3 or sys.argv[1] == '--assets':
        sys.exit(0)
    area, aname = sys.argv[1], sys.argv[2]
    if '--seed' in sys.argv:
        SEED = int(sys.argv[sys.argv.index('--seed') + 1])
    listf = f'data/{area}_beautify.json'
    cur = json.load(open(listf)) if os.path.exists(listf) else {'seed': SEED, 'areas': []}
    if '--areas-only' in sys.argv:                     # only tell exterior.py which box to leave alone
        cur['areas'] = [{'name': aname, 'box': region_box(area, aname), 'above_cells': []}]
        json.dump(cur, open(listf, 'w'), indent=1); print('areas written'); sys.exit(0)
    path = f'tiled/maps/{area}.tmj'
    M = json.load(open(path))
    rep = layout_network(area, aname, M, cur['areas'])
    json.dump(M, open(path, 'w'))
    cur['seed'] = SEED
    cur['areas'] = [{'name': aname, 'box': rep['box'], 'above_cells': rep['above_cells']}]
    json.dump(cur, open(listf, 'w'), indent=1)
    for k, v in rep.items():
        if k not in ('above_cells',):
            print(f'  {k}: {v}')
    print(EX.validate(path))
