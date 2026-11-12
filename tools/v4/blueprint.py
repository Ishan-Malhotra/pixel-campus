"""Blueprint: OpenStreetMap -> accurate, grid-locked campus map (Emerald-style: tile ground + building stamps).

Geometry (where every road and building is) comes ONLY from OpenStreetMap, rotated ~8 deg so the campus street grid is
axis-aligned, at 1 tile = 16 px = 3 m. At that scale one map pixel is one pixel of the user's art (art/reference_main.png),
so buildings, plants and the player keep the proportions of the art. Looks come from the user's approved images:
  - ground (lawn, roads with kerbs, paths) is painted with textures/colours sampled from the approved art,
  - buildings are STAMPS placed into their real OSM footprints (slots):
      main_building : FD3 + Clock Tower body + FD2, composed from the user's Figma pieces (art/pieces)
      rotunda_art   : the Rotunda, cut from art/reference_main.png at the art's own size
      (main_west, fd2, rotunda are older cut-outs; they are still built but no longer placed)
    Slots without art yet (bhawans, mess, NAB, small buildings) get a neutral placeholder block until the
    user's one-off image for that building type arrives (tools/v4/stamp_prep.py, next step).

Outputs
  tiled/maps/<area>.tmj, tiled/campus.world, tiled/tilesets/{ground.tsj,ground.png,buildings.tsj}, tiled/stamps/*.png,
  tiled/underlay/<area>_blueprint.png
  data/debug/<area>_render.png (what it looks like), <area>_check.png (+ OSM outlines), compare_satellite.png
Usage (repo root): python3 tools/v4/blueprint.py [area]      (default area: phase1)
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

T, M_PER_TILE = 16, 3.0                    # 3 m per tile: map px = art px (was 5 m until 2026-11-11; see WORKLOG.md)
PPM = T / M_PER_TILE                       # px per metre (5.33)
PORCH_SOUTH_M = 20                         # the porch front stands this far south of the OSM Clock Tower point (satellite)
AREA = sys.argv[1] if len(sys.argv) > 1 else 'phase1'
# area of interest in OSM metres (un-rotated frame of data/campus_full.features.json)
AREAS = {'phase1': (540, 560, 1010, 1185)}   # Main Building + FD2 + Rotunda, NAB/Snake Path, Krishna & Gandhi Bhawans, KG mess, Gandhi Marg circle
for d in ('tiled/maps', 'tiled/tilesets', 'tiled/stamps', 'tiled/underlay', 'data/debug'):
    os.makedirs(d, exist_ok=True)

sys.path.insert(0, os.path.dirname(__file__))
import tiled_kit
N_TERRAIN = tiled_kit.build(); PROP_NAMES = tiled_kit.build_props(); tiled_kit.build_project()
D = json.load(open('data/campus_full.features.json'))
F = D['features']


# ===================================================================== rotation (campus street grid -> axis aligned)
def dominant_angle(features, box):
    x0, y0, x1, y1 = box
    hist = np.zeros(180)
    for f in features:
        if f['kind'] != 'area' or 'building' not in f['tags']:
            continue
        for ring in f['outer']:
            if not all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in ring):
                continue
            for (ax, ay), (bx, by) in zip(ring, ring[1:]):
                L = math.hypot(bx - ax, by - ay)
                hist[int((math.degrees(math.atan2(by - ay, bx - ax)) % 90) * 2) % 180] += L
    sm = np.array([sum(hist[(i + k) % 180] for k in range(-3, 4)) for i in range(180)])
    a = np.argmax(sm) / 2 + 0.25
    return a - 90 if a > 45 else a


AX0, AY0, AX1, AY1 = AREAS[AREA]
THETA = dominant_angle(F, (AX0 - 200, AY0 - 200, AX1 + 200, AY1 + 200))
PHI = math.radians(-THETA)
CX0, CY0 = (AX0 + AX1) / 2, (AY0 + AY1) / 2


def rot(p):
    x, y = p[0] - CX0, p[1] - CY0
    return (x * math.cos(PHI) - y * math.sin(PHI), x * math.sin(PHI) + y * math.cos(PHI))


# area extent in the rotated frame (corners of the OSM box)
corners = [rot(c) for c in ((AX0, AY0), (AX1, AY0), (AX0, AY1), (AX1, AY1))]
RX0 = min(c[0] for c in corners); RY0 = min(c[1] for c in corners)
RX1 = max(c[0] for c in corners); RY1 = max(c[1] for c in corners)
MW = int(math.ceil((RX1 - RX0) * PPM / T)); MH = int(math.ceil((RY1 - RY0) * PPM / T))
W, H = MW * T, MH * T


def P(p):
    """OSM metres -> map px (rotated, snapped to 1 px)"""
    x, y = rot(p)
    return (round((x - RX0) * PPM), round((y - RY0) * PPM))


print(f'{AREA}: rotation {THETA:.2f} deg, {MW}x{MH} tiles ({W}x{H} px)')

# ===================================================================== palette + textures from the approved art
ART = np.array(Image.open('art/reference_main.png').convert('RGB'))
for (x0, y0, x1, y1, dx, dy) in [(626, 329, 643, 358, 18, 0), (210, 440, 228, 471, -20, 0), (1005, 398, 1024, 427, -22, 0)]:
    ART[y0:y1, x0:x1] = ART[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
PAL_IMG = Image.fromarray(ART).quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
NEW = np.array(Image.open('art/reference_fd2.png').convert('RGB'))
NEW[466:500, 918:952] = NEW[466:500, 880:914]          # generator watermark


def patch(a, test, size=32):
    best, bx, by = 1e18, 0, 0
    for y in range(0, a.shape[0] - size, 8):
        for x in range(0, a.shape[1] - size, 8):
            p = a[y:y + size, x:x + size].astype(int)
            if not test(p).all():
                continue
            v = p.std(axis=(0, 1)).sum()
            if v < best:
                best, bx, by = v, x, y
    return a[by:by + size, bx:bx + size]


LAWN = patch(ART, lambda p: (p[..., 1] > p[..., 0] + 40) & (p[..., 1] > 170))
DIRT = patch(ART, lambda p: (p[..., 0] > 200) & (p[..., 1] > 170) & (p[..., 2] < 170) & (p[..., 0] > p[..., 2] + 50), 16)
ROAD = ART[396:469, 960].copy()                         # base-road cross-section: verge, kerb, edges, asphalt
ASPHALT = ROAD[len(ROAD) // 2].astype(int)
VERGE, EDGE_DARK, EDGE_MID = ART[399, 960], ART[402, 960], ART[403, 960]
KERB_WHITE = np.array([238, 236, 228])

# ===================================================================== rasterise ground
def poly_im():
    return Image.new('L', (W, H), 0)


def to_np(im):
    return np.array(im) > 0


road_im, path_im, rbi_im = poly_im(), poly_im(), poly_im()
dr, dp, di = ImageDraw.Draw(road_im), ImageDraw.Draw(path_im), ImageDraw.Draw(rbi_im)
MAJOR = {'Krishna Marg', 'Gandhi Marg', 'Ram Marg', 'Bhagirath Marg', 'Rana Pratap Marg'}
ROAD_TILES = {'residential': 4, 'unclassified': 4, 'tertiary': 4, 'secondary': 4, 'service': 3}
PATH_TILES = {'footway': 1.5, 'steps': 1.5, 'path': 1.5, 'pedestrian': 2, 'cycleway': 1.5}


def thick(draw, pts, w):
    draw.line(pts, fill=255, width=int(w), joint='curve')
    r = w / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


DRIVEWAY = 'w285869287'    # OSM service road: west circle -> past the Clock Tower porch -> east circle
driveway = None
slots = []
for f in F:
    t = f['tags']
    if f['kind'] == 'line' and 'highway' in t:
        pts = [P(p) for p in f['pts']]
        hw = t['highway']
        if f['id'] == DRIVEWAY:                          # redrawn as a smooth drive in the front-garden section below
            driveway = pts
            continue
        if t.get('junction') == 'roundabout':
            continue
        if hw in ROAD_TILES:
            thick(dr, pts, (4 if t.get('name') in MAJOR else ROAD_TILES[hw]) * T)
        elif hw in PATH_TILES:
            thick(dp, pts, PATH_TILES[hw] * T)
    if t.get('junction') == 'roundabout':
        ring = f.get('pts') or f['outer'][0]
        pts = [P(p) for p in ring]
        cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
        r_in = max(math.hypot(p[0] - cx, p[1] - cy) for p in pts)
        R = r_in + 2 * T                                 # ring road 4 tiles wide around a ~2.5-tile island
        dr.ellipse((cx - R, cy - R, cx + R, cy + R), fill=255)
        di.ellipse((cx - r_in, cy - r_in, cx + r_in, cy + r_in), fill=255)
road, path, island = to_np(road_im), to_np(path_im), to_np(rbi_im)
road &= ~island
path &= ~road

yy, xx = np.mgrid[0:H, 0:W]
img = np.zeros((H, W, 3), np.uint8)
img[:] = LAWN[yy % 32, xx % 32]


def ring(m):
    inner = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m & ~inner


# footpaths (tan dirt with a darker rim, as in the art)
img[path] = DIRT[yy[path] % DIRT.shape[0], xx[path] % DIRT.shape[1]]
img[ring(path)] = (184, 148, 104)
# roads: asphalt + speckle, then kerb rings exactly like the art's road cross-section
img[road] = ASPHALT
img[road & (((xx * 7 + yy * 3) % 37) == 0)] = ART[430, 940]
e1 = ring(road); e2 = ring(road & ~e1); e3 = ring(road & ~e1 & ~e2)
img[e1] = EDGE_DARK; img[e2] = EDGE_MID
grown = np.roll(road, 1, 0) | np.roll(road, -1, 0) | np.roll(road, 1, 1) | np.roll(road, -1, 1)
verge = (grown | np.roll(grown, 1, 0) | np.roll(grown, 1, 1)) & ~road
img[verge] = VERGE
# roundabout islands: lawn with a white kerb
img[ring(island)] = KERB_WHITE
img[ring(island & ~ring(island))] = (200, 198, 190)
GROUND = img.copy()

# ===================================================================== stamps (building art), cut + palette-locked
def flood_bg(crop, tol, green_only):
    h, w = crop.shape[:2]
    c = crop.reshape(-1, 3).astype(int)
    border = np.unique(np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]]).astype(int), axis=0)
    d = np.min(np.abs(c[:, None, :] - border[None, :, :]).sum(axis=2), axis=1).reshape(h, w)
    ok = d < tol
    if green_only:
        cc = crop.astype(int)
        ok &= (cc[..., 1] > cc[..., 0] + 12) | (cc.sum(axis=2) < 120) | ((np.abs(cc[..., 0] - cc[..., 2]) < 30) & (cc.sum(axis=2) > 330) & (cc.sum(axis=2) < 520))
    bg = np.zeros((h, w), bool)
    st = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while st:
        y, x = st.pop()
        if 0 <= y < h and 0 <= x < w and not bg[y, x] and ok[y, x]:
            bg[y, x] = True
            st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return bg


def big_parts(fg, min_px):
    """keep only the connected parts of a mask that have at least min_px pixels (drops flags, plants, specks)"""
    keep = np.zeros(fg.shape, bool); seen = np.zeros(fg.shape, bool)
    h, w = fg.shape
    for sy, sx in zip(*np.nonzero(fg)):
        if seen[sy, sx]:
            continue
        blob, st = [], [(sy, sx)]
        seen[sy, sx] = True
        while st:
            y, x = st.pop()
            blob.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and fg[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    st.append((ny, nx))
        if len(blob) >= min_px:
            ys, xs = zip(*blob)
            keep[list(ys), list(xs)] = True
    return keep


def make_stamp(name, src, box, tol=40, green_only=True, half=False, rects=None, min_part=0):
    x0, y0, x1, y1 = box
    crop = src[y0:y1, x0:x1].copy()
    if rects is not None:                                   # exact building outline (measured rects, in px of src)
        fg = np.zeros(crop.shape[:2], bool)
        for rx0, ry0, rx1, ry1 in rects:
            fg[max(0, ry0 - y0):max(0, ry1 - y0), max(0, rx0 - x0):max(0, rx1 - x0)] = True
    else:
        fg = ~flood_bg(crop, tol, green_only)
        if min_part:
            fg = big_parts(fg, min_part)
    rgba = np.dstack([crop, np.where(fg, 255, 0)]).astype(np.uint8)
    im = Image.fromarray(rgba)
    full = Image.fromarray(np.dstack([crop, np.full(crop.shape[:2], 255, np.uint8)]).astype(np.uint8))
    if half:
        im = im.resize((im.width // 2, im.height // 2), Image.NEAREST)
        full = full.resize((full.width // 2, full.height // 2), Image.NEAREST)
    # user-editable stamps: art/stamps/<name>.png is YOURS. It is seeded once from the automatic cut-out and never
    # overwritten afterwards; art/stamps/_source/<name>_full.png is the uncut original (to restore erased pixels).
    os.makedirs('art/stamps/_source', exist_ok=True)
    full.save(f'art/stamps/_source/{name}_full.png')
    user_file = f'art/stamps/{name}.png'
    if os.path.exists(user_file):
        im = Image.open(user_file).convert('RGBA')
    else:
        im.save(user_file)
    # pad to whole tiles (stamps always occupy whole tiles)
    pw, ph = math.ceil(im.width / T) * T, math.ceil(im.height / T) * T
    canvas = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    canvas.paste(im, (0, ph - im.height))                 # anchor to the bottom (entrance side)
    rgb = canvas.convert('RGB').quantize(palette=PAL_IMG, dither=Image.Dither.NONE).convert('RGB')
    out = np.dstack([np.array(rgb), np.array(canvas)[..., 3]])
    Image.fromarray(out).save(f'tiled/stamps/{name}.png')
    return out


# measured building outline of the approved Main Building art (reference tiles; see tools/v2/map_main.py)
MAIN_RECTS = [
    (0.5, 4.3, 39.6, 8.2), (0.5, 4.3, 4.7, 16.6),            # main E-W roof band + west leg
    (2.0, 3.3, 5.1, 6.4),                                    # rooftop pavilion
    (4.7, 8.0, 24.7, 12.1), (13.8, 12.0, 15.9, 12.8),        # west front wing (arcade) + its door steps
    (20.0, 9.4, 24.4, 13.8), (24.0, 11.9, 28.7, 16.05), (35.3, 11.9, 39.6, 16.05),  # stepped blocks
    (24.4, 8.0, 39.6, 12.0), (28.2, 5.5, 35.8, 13.6),        # roof between blocks, tower block
    (26.6, 0.0, 37.4, 4.3), (29.6, 0.2, 34.6, 6.0),          # slate hall + tower top
    (28.55, 13.4, 35.45, 16.8),                              # side blocks flanking the porch (tower base)
    (29.75, 13.4, 34.2, 18.3),                               # porch
    (-0.2, 16.5, 6.0, 20.3), (0.0, 20.2, 5.0, 24.4),         # west pavilions
]
def compose_pieces(layout_file, target_w):
    """assemble the user's piece PNGs (art/pieces) per the layout JSON, then scale to target_w px wide"""
    lay = json.load(open(layout_file))
    imgs = [(Image.open(os.path.join('art/pieces', p['file'])).convert('RGBA'), p['x'], p['y']) for p in lay['pieces']]
    x0 = min(x for _, x, _ in imgs); y0 = min(y for _, _, y in imgs)
    x1 = max(x + im.width for im, x, _ in imgs); y1 = max(y + im.height for im, _, y in imgs)
    canvas = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for im, x, y in imgs:                                    # listed order = draw order (FDs over the body)
        canvas.alpha_composite(im, (x - x0, y - y0))
    bb = canvas.getbbox(); canvas = canvas.crop(bb)
    f = target_w / canvas.width
    small = canvas.resize((round(canvas.width * f), round(canvas.height * f)), Image.LANCZOS)
    a = np.array(small)
    alpha = a[..., 3] >= 128
    rgb = Image.fromarray(a[..., :3]).quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB')
    out = np.dstack([np.array(rgb), np.where(alpha, 255, 0).astype(np.uint8)])
    ph, pw = math.ceil(out.shape[0] / T) * T, math.ceil(out.shape[1] / T) * T
    padded = np.zeros((ph, pw, 4), np.uint8); padded[ph - out.shape[0]:, :out.shape[1]] = out
    Image.fromarray(padded).save('tiled/stamps/main_building.png')
    # where the body's porch (bottom centre of the body piece) lands inside the stamp, for anchoring on the map
    body = next(p for p in lay['pieces'] if 'clock' in p['file'])
    bim = Image.open(os.path.join('art/pieces', body['file']))
    porch_x = ((body['x'] - x0) + bim.width / 2 - bb[0]) * f
    porch_y = ((body['y'] - y0) + bim.height - bb[1]) * f + (ph - out.shape[0])
    return padded, porch_x, porch_y


_mb = next(f for f in F if f['tags'].get('name') == 'FD-2 & FD-3')
_mb_xs = [P(p)[0] for p in _mb['outer'][0]]
MAIN_W = max(_mb_xs) - min(_mb_xs)                           # real width of the Main Building complex (px)
MB_STAMP, MB_PORCH_X, MB_PORCH_Y = compose_pieces('art/pieces/main_building_layout.json', MAIN_W)

STAMPS = {
    'main_building': MB_STAMP,                                  # FD3 + clock tower body + FD2, from the user's Figma pieces
    # Clock Tower + west part of the Main Building (art x 0.5..39.6 tiles, from the courtyard roofs to the porch steps)
    'main_west': make_stamp('main_west', ART, (8, 0, 634, 390), rects=[[int(v * T) for v in r] for r in MAIN_RECTS]),
    # FD2 quad (building only)
    'fd2': make_stamp('fd2', NEW, (596, 6, 1010, 374)),
    # Rotunda: art draws it ~2x real size -> exact 1/2 (the art's rotunda runs off the image bottom: flat cut)
    'rotunda': make_stamp('rotunda', ART, (256, 330, 776, 687), tol=30, green_only=True, half=True),
    # the same cut at the art's own size (the map is at the art's scale now); loose flags and plants are dropped
    'rotunda_art': make_stamp('rotunda_art', ART, (256, 330, 776, 687), tol=30, green_only=True, min_part=1500),
}


def placeholder(name, wt, ht, kind):
    """neutral flat-roof block for slots whose art hasn't been generated yet"""
    w, h = wt * T, ht * T
    a = np.zeros((h, w, 4), np.uint8)
    roof = {'bhawan': (214, 196, 160), 'mess': (206, 190, 170), 'nab': (210, 204, 170)}.get(kind, (200, 196, 184))
    a[..., :3] = roof; a[..., 3] = 255
    a[:3, :, :3] = (212, 142, 110); a[-3:, :, :3] = (212, 142, 110); a[:, :3, :3] = (212, 142, 110); a[:, -3:, :3] = (212, 142, 110)
    a[0, :, :3] = a[-1, :, :3] = (112, 62, 54); a[:, 0, :3] = a[:, -1, :3] = (112, 62, 54)
    wall = min(32, h // 3)
    a[-wall:-3, 3:-3, :3] = (238, 229, 182)
    for x in range(8, w - 8, 12):
        a[-wall + 8:-wall + 18, x:x + 6, :3] = (48, 46, 72)
    if kind == 'bhawan':                                  # courtyard
        cw, chh = w // 3, h // 3
        a[chh:chh * 2, cw:cw * 2, :3] = LAWN[:chh, :cw] if chh <= 32 and cw <= 32 else (110, 200, 120)
        a[chh:chh * 2, cw:cw * 2, :3] = (110, 196, 116)
    return a


# ===================================================================== slots from OSM footprints
TYPE_BY_NAME = {
    'Krishna Bhawan': 'bhawan', 'Gandhi Bhawan': 'bhawan', 'Ram Bhawan': 'bhawan', 'Budh Bhawan': 'bhawan',
    'Shankar Bhawan': 'bhawan', 'Vyas Bhawan': 'bhawan', 'Vishwakarma Bhawan': 'bhawan', 'Bhagirath Bhawan': 'bhawan',
    'Rana Pratap Bhawan': 'bhawan', 'Ashok bhawan': 'bhawan',
    'KG mess': 'mess', 'Ram-Budh mess': 'mess', 'Shankar Vyas Mess': 'mess', 'VKB mess': 'mess', 'RP mess': 'mess',
    'NAB': 'nab', 'New Academic Block': 'nab', 'New Academic Building': 'nab',
}
taken = set()
for f in F:
    t = f['tags']
    if f['kind'] != 'area' or 'building' not in t:
        continue
    ring_ = f['outer'][0]
    cx = sum(p[0] for p in ring_) / len(ring_); cy = sum(p[1] for p in ring_) / len(ring_)
    if not (AX0 <= cx <= AX1 and AY0 <= cy <= AY1):
        continue
    name = t.get('name', '')
    if name == 'New Academic Building':                   # duplicate outline of 'New Academic Block'
        continue
    pts = [P(p) for p in ring_]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = round(min(xs) / T), round(min(ys) / T)
    x1, y1 = max(x0 + 1, round(max(xs) / T)), max(y0 + 1, round(max(ys) / T))
    slots.append({'name': name or 'building', 'osm': f['id'], 'type': TYPE_BY_NAME.get(name, 'small'),
                  'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0, 'outline': pts})

# the Main Building complex (FD3 + clock tower body + FD2) is ONE stamp from the user's pieces, centred on the OSM Clock
# Tower point, with the porch front PORCH_SOUTH_M south of the tower point -- as in the satellite view
for s_ in [s_ for s_ in slots if s_['name'] == 'FD-2 & FD-3']:
    slots.remove(s_)
    tx_, ty_ = P(next(f['pt'] for f in F if f['tags'].get('name') == 'BITS Clock Tower'))
    mh, mw = MB_STAMP.shape[0] // T, MB_STAMP.shape[1] // T
    slots.append({'name': 'Main Building', 'type': 'stamp:main_building', 'x': round((tx_ - MB_PORCH_X) / T),
                  'y': round((ty_ + PORCH_SOUTH_M * PPM - MB_PORCH_Y) / T), 'w': mw, 'h': mh, 'outline': s_['outline']})
# (the Rotunda is only a point in OSM; its stamp is placed in the front-garden section below, south of the drive)

# ===================================================================== front garden (Clock Tower porch <-> Rotunda)
# OSM has the drive past the porch only as a coarse line and nothing at all for the gardens. This section lays the
# area out the way the user's art (art/reference_main.png) and the satellite view show it:
#   - the drive is one wide arc from the west circle, past the porch steps, to the east circle;
#   - the Rotunda sits one drive-width south of the porch (its stamp is at the art's own size), with lawn around it;
#   - west of the porch a lane leaves the drive towards the building, with a hedge between lane and drive;
#   - hedges run along the drive, with flags and lamps; the lawns get the art's plants (cut out in tiled_kit.py).
# All sizes here are in art pixels: they assume the map is at the art's scale (M_PER_TILE = 3).
# It is all ordinary Tiled data (road / path tiles and objects on the `props` layer), so every piece can be moved or
# deleted in Tiled.
HEDGE_W = 17                                  # px, as thick as the art's hedges
KERB = 2                                      # px of kerb between asphalt and the porch steps / Rotunda apron / hedges
LANE_W, MED_W = 24, 13                        # the lane past the porch steps, and the median hedge between it and the road
DRIVE_W = 4 * T + 12                          # the whole drive, kerb to kerb (13 m in the satellite view)
TERRACE = 40                                  # paved terrace between the drive and the Rotunda (7 m in the satellite view)
ROT_AXIS = 260                                # column of the Rotunda's axis inside its stamp (art x 516 - crop x 256)
K = PPM / 3.2                                 # distances measured on the old 5 m map -> this map
garden_props, garden_hedges, tall_tiles = [], [], []   # (prop name, x of its base centre, y of its base), polylines, (tx, ty)


def circle3(a, b, c):
    """centre and radius of the circle through three points"""
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return ux, uy, math.hypot(ax - ux, ay - uy)


def chaikin(pts, n=3):
    """corner-cutting: a coarse polyline -> a smooth curve"""
    for _ in range(n):
        q = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            q += [(0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by), (0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by)]
        pts = q + [pts[-1]]
    return pts


if driveway:
    mb = next(s for s in slots if s['type'] == 'stamp:main_building')
    mbx, mby = mb['x'] * T, mb['y'] * T
    opaque = MB_STAMP[..., 3] > 0
    # per stamp column: map y just below the building (H where the column is empty)
    foot = np.where(opaque.any(axis=0), mby + opaque.shape[0] - np.argmax(opaque[::-1], axis=0), H)
    PX = round(mbx + MB_PORCH_X)                                         # centre of the porch steps
    PY = int(foot[PX - mbx])                                             # ... and their bottom edge
    recess = np.nonzero(foot < PY)[0]                                    # columns where the building stops north of the porch:
    gx0, gx1 = mbx + int(recess[0]), mbx + int(recess[-1])               # the lawns between the two FD quads

    def door_steps(x_from, x_to):
        """wing door steps = the columns between x_from and x_to that reach a few px below the wing wall.
        Returns the steps' centre x, their bottom y, and the y of the wing wall's foot."""
        cols = np.arange(x_from - mbx, x_to - mbx)
        wall = np.bincount(foot[cols]).argmax()
        s = cols[(foot[cols] > wall + 4 * K) & (foot[cols] < wall + 14 * K)]
        return round(s.mean() + mbx), int(foot[s].max()), int(wall)

    # --- the Rotunda: its axis on the porch's, its apron one drive-width south of the porch steps
    rot_st = STAMPS['rotunda_art']
    rot_op = rot_st[..., 3] > 0
    rot_top = int(np.argmax(rot_op[:, ROT_AXIS - 10:ROT_AXIS + 10].any(axis=1)))     # first row of the apron on the axis
    # satellite, on the porch's axis: porch steps, the drive (a drop-off lane + the two-lane road, ~13 m), a paved
    # terrace (~7 m), then the Rotunda's arcade
    rtx = round((PX - ROT_AXIS) / T)
    rty = round((PY + 2 * KERB + DRIVE_W + TERRACE - rot_top) / T)
    slots.append({'name': 'Rotunda', 'type': 'stamp:rotunda_art', 'x': rtx, 'y': rty, 'w': rot_st.shape[1] // T,
                  'h': rot_st.shape[0] // T, 'outline': [], 'on_top': True})
    rot_rows = np.nonzero(rot_op.any(axis=1))[0]
    rcx, rcy = rtx * T + ROT_AXIS, rty * T + (rot_rows.min() + rot_rows.max()) // 2   # the Rotunda's centre
    rot_hw = (np.ptp(np.nonzero(rot_op.any(axis=0))[0]) + 1) // 2                         # ... and half its width

    # --- the drive: a circular arc through the west circle, just south of the porch steps, and the east circle
    ends = sorted((driveway[0], driveway[-1]))
    ux, uy, R = circle3(ends[0], (PX, PY + KERB + DRIVE_W / 2), ends[1])
    aW = math.atan2(ends[0][1] - uy, ends[0][0] - ux)                    # angles on the arc, west end .. east end
    aE = math.atan2(ends[1][1] - uy, ends[1][0] - ux)                    # (the arc's top is at -pi / 2)

    def arc(off, a0, a1, step=3.0):
        """points along the drive, `off` px outside its centre line (a number, or a function of the angle)"""
        f = off if callable(off) else (lambda a: off)
        n = max(2, int(abs(a1 - a0) * R / step))
        return [(ux + (R + f(a)) * math.cos(a), uy + (R + f(a)) * math.sin(a))
                for a in (a0 + (a1 - a0) * i / n for i in range(n + 1))]

    def ang(x):
        """the angle at which the drive's centre line passes map x"""
        return -math.acos(max(-1.0, min(1.0, (x - ux) / R)))

    walls_im = Image.new('L', (W, H), 0)                                 # the Main Building and the Rotunda
    for st_, sx_, sy_ in ((MB_STAMP, mbx, mby), (rot_st, rtx * T, rty * T)):
        m_ = Image.fromarray(((st_[..., 3] > 0) * 255).astype(np.uint8))
        walls_im.paste(m_, (sx_, sy_), m_)
    walls = to_np(walls_im)

    def grown(im, r):
        return im.filter(ImageFilter.MaxFilter(2 * r + 1))

    busy_im = Image.fromarray(((road | path) * 255).astype(np.uint8))    # other roads and footpaths: hedges stop there too
    line = arc(0, aW, aE)
    drive_im = poly_im()
    thick(ImageDraw.Draw(drive_im), line, DRIVE_W)
    drive = to_np(drive_im)
    road |= drive

    def disc_grow(m, r):
        """grow a mask by r px with rounded corners (alternating 4- and 8-neighbour steps)"""
        for i in range(r):
            p = np.pad(m, 1)
            g = m | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
            if i % 2:
                g |= p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:]
            m = g
        return m

    # --- the paved terrace around the Rotunda's north half (path tiles); lawn too thin to draw between it and the
    # drive is paved too
    pad_ = TERRACE + 40
    ry0, rx0 = rty * T - pad_, rtx * T - pad_
    loc = np.zeros((rot_op.shape[0] + 2 * pad_, rot_op.shape[1] + 2 * pad_), bool)
    loc[pad_:pad_ + rot_op.shape[0], pad_:pad_ + rot_op.shape[1]] = rot_op
    ter_loc = disc_grow(loc, TERRACE + KERB + T) & ~loc                  # a tile wider: it reaches the drive's kerb
    terrace = np.zeros((H, W), bool)
    terrace[max(0, ry0):ry0 + loc.shape[0], max(0, rx0):rx0 + loc.shape[1]] = ter_loc[max(0, -ry0):, max(0, -rx0):][:H - max(0, ry0), :W - max(0, rx0)]
    terrace[rcy - 30:] = False                                            # the flanks further down stay lawn, for the beds
    terrace &= ~drive
    sliver = to_np(grown(drive_im, T)) & disc_grow(terrace, T) & ~drive & ~walls   # under a tile wide: blobs once smoothed
    sliver[:PY + KERB] = False
    terrace |= sliver
    path |= terrace

    def dirt(cx0, cy0, cx1, cy1):
        """dirt over the tile corners cx0..cx1 x cy0..cy1 (one column or row of corners = a 1-tile path)"""
        path[cy0 * T - 3:cy1 * T + 4, cx0 * T - 3:cx1 * T + 4] = True

    # --- hedges: polylines along the drive at a fixed distance from its centre line; they stop short of buildings
    busy = to_np(grown(busy_im, HEDGE_W // 2 + 2))
    near_wall = to_np(grown(walls_im, HEDGE_W // 2 + 4)) | busy
    OUT = DRIVE_W / 2 + KERB + 1 + HEDGE_W / 2                           # hedge centre line: just outside the drive's kerb
    MED_OFF = DRIVE_W / 2 - LANE_W - MED_W / 2                           # the median: LANE_W inside the drive's outer kerb

    def hedge(off, a0, a1, width=HEDGE_W, gaps=(), clear=None):
        """hedge runs along the drive between two angles; `gaps` = (x0, x1) openings; `clear` = mask the centre line
        must stay out of. Returns the runs, west to east."""
        clear = near_wall if clear is None else clear
        runs, run = [], []
        for x, y in arc(off, a0, a1, step=6.0):
            if 0 <= y < H and 0 <= x < W and not clear[int(y), int(x)] and not any(g0 <= x <= g1 for g0, g1 in gaps):
                run.append((round(x, 1), round(y, 1)))
            else:
                runs.append(run); run = []
        runs = [r for r in runs + [run] if len(r) >= 6]
        garden_hedges.extend((r, width) for r in runs)
        return runs

    def on_hedge(run, f):
        """the point a fraction f along a hedge run"""
        return run[min(len(run) - 1, int(f * len(run)))]

    wx, wy, wwall = door_steps(round(PX - 205 * K), round(PX - 115 * K))  # west wing door
    ex, ey, ewall = door_steps(round(PX + 115 * K), round(PX + 215 * K))  # east wing door
    a_top = -math.pi / 2
    west_out = hedge(OUT, ang(gx0 + 12), a_top, gaps=[(wx - 24, wx + 24)])    # FD3 corner -> porch, open at the door path
    east = hedge(OUT, a_top, ang(gx1 - 12))                                  # porch -> FD2 corner
    # the medians: a lower hedge inside the drive on either side of the porch. North of it is the lane that passes the
    # porch steps, south of it the through road (the satellite view shows both medians, the art the west one)
    med_w = hedge(MED_OFF, ang(PX - 0.74 * (PX - gx0)), ang(PX - 58), width=MED_W)
    med_e = hedge(MED_OFF, ang(PX + 58), ang(PX + 0.74 * (gx1 - PX)), width=MED_W)
    # Rotunda side of the drive: planters along the terrace's edge, open in front of the arcade (satellite)
    in_clear = to_np(grown(walls_im, HEDGE_W // 2 + 6)) | busy
    west_in = hedge(-OUT, aW + 0.06, ang(PX - 150), clear=in_clear)
    east_in = hedge(-OUT, ang(PX + 150), aE - 0.06, clear=in_clear)

    # --- west lawn: dirt path from the wing door down to the drive
    wc = round(wx / T)
    kerb_y = uy + (R + DRIVE_W / 2) * math.sin(ang(wx))
    dirt(wc, math.ceil((wy + 2) / T), wc, int(kerb_y // T) + 1)
    # --- along the hedges: flags standing in the hedge line, lamps where the hedges open or end
    for run, f, flag in ((west_out[0], 0.15, 'flag1'), (west_out[0], 0.92, 'flag0'), (west_out[-1], 0.5, 'flag4'),
                         (east[0], 0.14, 'flag2'), (east[0], 0.5, 'flag0'), (east[0], 0.86, 'flag1')) + \
                        (((west_in[0], 0.5, 'flag2'),) if west_in else ()):
        fx, fy = on_hedge(run, f)
        garden_props.append((flag, fx, fy - 2))
    garden_props += [('lamp', west_out[0][-1][0] - 2, west_out[0][-1][1] - 14), ('lamp', east[0][-1][0] + 6, east[0][-1][1] - 16)]

    # --- plants, cut from the art (tiled_kit.py). Positions are px from the porch (PX, PY), the wing doors and the
    # FD walls, laid out like the art: tall grass, palm and shrubs on the west lawn; the vegetable bed with its
    # flowers, palms and small trees on the east lawn.
    def plant(name, x, y):
        garden_props.append((name, round(x), round(y)))

    tw, th = Image.open('tiled/props/thicket_tall.png').size
    ty1 = wwall + 8 + th                                                 # west: tall grass in the corner by FD3
    plant('thicket_tall', gx0 + 8 + tw / 2, ty1)
    for name, dx, dy in (('shrub', 22, 30), ('flowers_red', 24, 50), ('shrub', 22, 72), ('bush', 62, 44), ('flowers_white', 60, 70)):
        plant(name, gx0 + dx, ty1 + dy)
    plant('palm', wx + 50, PY - 30); plant('bush', wx + 46, PY + 16)
    plant('shrub', PX - 150, PY - 10); plant('flowers_red', PX - 116, PY - 12)
    bw, bh = Image.open('tiled/props/veg_bed.png').size
    bx0, by1 = min(ex - 82, gx1 - 10 - bw), ey + 6 + bh                  # east: the bed below the wing door
    plant('veg_bed', bx0 + bw / 2, by1)
    plant('palm', bx0 - 34, PY + 10); plant('palm_small', PX + 142, PY - 6); plant('shrub', PX + 110, PY - 10)
    for name, dx, dy in (('flowers_white', 40, 18), ('bush_big', 70, 30), ('conifer', 100, 36), ('conifer', 124, 58)):
        plant(name, bx0 + dx, by1 + dy)
    plant('sign', east[0][-1][0] - 16, east[0][-1][1] - 22)

    # --- beside the Rotunda's south half: bougainvillea beds (red in the satellite view), palms and bushes, as in the
    # art. Each one goes where its base is clear of roads, paths, walls, hedges and other plants, nudged outwards.
    occ_im = Image.fromarray(((road | path | walls) * 255).astype(np.uint8)); do_ = ImageDraw.Draw(occ_im)
    for run, hw in garden_hedges:
        do_.line(run, fill=255, width=hw + 6)
    for s_ in slots:
        if not s_['type'].startswith('stamp:'):
            do_.rectangle((s_['x'] * T - 4, s_['y'] * T - 4, (s_['x'] + s_['w']) * T + 4, (s_['y'] + s_['h']) * T + 4), fill=255)
    occ = to_np(occ_im)
    for name, x, y in garden_props:
        w_, h_ = Image.open(f'tiled/props/{name}.png').size
        x, y = int(x), int(y)
        occ[max(0, y - h_ // 2):y + 2, max(0, x - w_ // 2):x + w_ // 2] = True

    def plant_free(name, x, y, side, force=False):
        w_, h_ = Image.open(f'tiled/props/{name}.png').size
        for step in [0] + [s * k for k in range(1, 9) for s in (1, -1)]:          # outwards first, then inwards
            cx_ = round(x + side * 6 * step)
            box = occ[max(0, y - h_ // 2):y + 3, max(0, cx_ - w_ // 2 - 2):cx_ + w_ // 2 + 2]
            if force or not box.any():
                plant(name, cx_, y)
                occ[max(0, y - h_ // 2):y + 3, max(0, cx_ - w_ // 2 - 2):cx_ + w_ // 2 + 2] = True
                return True
        return False

    # the art's bougainvillea against the Rotunda's arcade wall (the stamp still holds a few of its leaves there)
    for side, dx in ((-1, -232), (1, 236)):
        plant_free('bougainvillea', rcx + dx, rty * T + 318, side, force=True)
    for side in (-1, 1):
        for name, dx, dy in (('palm', 22, -40), ('bush_big', 18, 20), ('palm_small', 20, 175), ('flowers_pink', 10, 215),
                             ('bush', 14, 140), ('flowers_red', 24, 60), ('shrub', 12, 250)):
            plant_free(name, rcx + side * (rot_hw + dx), rcy + dy, side)
    path &= ~road
    print(f'front garden: porch ({PX}, {PY}), recess x {gx0}..{gx1}, drive {DRIVE_W} px wide, Rotunda centre ({rcx}, {rcy}), '
          f'terrace {rty * T + rot_top - PY - 2 * KERB - DRIVE_W} px, arc centre ({ux:.0f}, {uy:.0f}) '
          f'r {R:.0f}, west door ({wx}, {wy}, wall {wwall}), east door ({ex}, {ey}, wall {ewall}), '
          f'hedges {[len(r) for r, _ in garden_hedges]}, drive over buildings: {int((drive & walls).sum())} px')

# ===================================================================== ground as TERRAIN TILES (editable in Tiled)
TERR = np.array(Image.open('tiled/tilesets/terrain.png').convert('RGB'))
def terrain_tile(tid):
    c = 16
    return TERR[(tid // c) * T:(tid // c + 1) * T, (tid % c) * T:(tid % c + 1) * T]

def corner_kind(cx, cy):
    """terrain at a tile corner: road beats path beats grass (3x3 vote around the corner)"""
    x0, x1 = max(0, cx - 2), min(W, cx + 3); y0, y1 = max(0, cy - 2), min(H, cy + 3)
    if road[y0:y1, x0:x1].mean() >= 0.5: return 'R'
    if path[y0:y1, x0:x1].mean() >= 0.5: return 'P'
    return 'G'

corner = [[corner_kind(x * T, y * T) for x in range(MW + 1)] for y in range(MH + 1)]
ground_ids = np.zeros((MH, MW), int)
for ty in range(MH):
    for tx in range(MW):
        c = (corner[ty][tx], corner[ty][tx + 1], corner[ty + 1][tx], corner[ty + 1][tx + 1])   # TL TR BL BR
        if 'R' in c:
            bits = sum((1 << (3 - i)) for i, k in enumerate(c) if k == 'R'); ground_ids[ty, tx] = bits
        elif 'P' in c:
            bits = sum((1 << (3 - i)) for i, k in enumerate(c) if k == 'P'); ground_ids[ty, tx] = 16 + bits
        else:
            ground_ids[ty, tx] = 64 if (tx * 7 + ty * 13) % 11 else 64 + 1 + (tx + ty) % 3
for tx, ty in tall_tiles:
    if ground_ids[ty, tx] >= 64:
        ground_ids[ty, tx] = 68                              # tall grass (sways and rustles in the game)
GROUND = np.zeros((H, W, 3), np.uint8)
for ty in range(MH):
    for tx in range(MW):
        GROUND[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T] = terrain_tile(ground_ids[ty, tx])

# ===================================================================== render (ground + stamps / placeholders)
render = GROUND.copy()
for s in sorted(slots, key=lambda s: (s.get('on_top', False), s['y'] + s['h'])):
    st = STAMPS[s['type'][6:]] if s['type'].startswith('stamp:') else placeholder(s['name'], s['w'], s['h'], s['type'])
    x, y = s['x'] * T, s['y'] * T
    h, w = st.shape[:2]
    sub = render[max(0, y):y + h, max(0, x):x + w]
    stc = st[max(0, -y):max(0, -y) + sub.shape[0], max(0, -x):max(0, -x) + sub.shape[1]]
    sub[:] = np.where(stc[..., 3:4] > 0, stc[..., :3], sub)
PROP_IMG = {n: Image.open(f'tiled/props/{n}.png').convert('RGBA') for n in PROP_NAMES}
if garden_props or garden_hedges:                            # rough preview only: the game draws the hedges properly
    pre = Image.fromarray(render).convert('RGBA'); dpre = ImageDraw.Draw(pre)
    for run, hw in garden_hedges:
        dpre.line(run, fill=(92, 188, 72, 255), width=hw, joint='curve')
    for name, cx, by in sorted(garden_props, key=lambda g: g[2]):
        pre.alpha_composite(PROP_IMG[name], (round(cx - PROP_IMG[name].width / 2), round(by - PROP_IMG[name].height)))
    render = np.array(pre.convert('RGB'))
Image.fromarray(render).save(f'data/debug/{AREA}_render.png')
chk = Image.fromarray(render).convert('RGB'); dc = ImageDraw.Draw(chk)
for f in F:
    t = f['tags']
    if f['kind'] == 'area' and 'building' in t:
        pts = [P(p) for p in f['outer'][0]]
        if any(0 <= x < W and 0 <= y < H for x, y in pts): dc.line(pts + [pts[0]], fill=(0, 255, 255), width=1)
    if f['kind'] == 'line' and 'highway' in t:
        pts = [P(p) for p in f['pts']]
        if any(0 <= x < W and 0 <= y < H for x, y in pts): dc.line(pts, fill=(255, 230, 0), width=1)
for s in slots:
    if s['name'] != 'building': dc.text((s['x'] * T + 3, s['y'] * T + 3), s['name'][:24], fill=(255, 255, 255))
chk.save(f'data/debug/{AREA}_check.png')
sat = [Image.open(p).convert('RGB') for p in ('art/satellite/central_strip.png', 'art/satellite/fd2_area.png') if os.path.exists(p)]
if sat:
    hgt = 900
    parts = [s_.resize((int(s_.width * hgt / s_.height), hgt)) for s_ in sat] + [Image.fromarray(render).resize((int(W * hgt / H), hgt), Image.NEAREST)]
    cmp_ = Image.new('RGB', (sum(p_.width for p_ in parts) + 16 * len(parts), hgt), (20, 20, 28)); xo = 0
    for p_ in parts: cmp_.paste(p_, (xo, 0)); xo += p_.width + 16
    cmp_.save('data/debug/compare_satellite.png')
Image.fromarray(render).save(f'tiled/underlay/{AREA}_blueprint.png')

# ===================================================================== Tiled project
stamp_files = sorted({s_['type'][6:] for s_ in slots if s_['type'].startswith('stamp:')})
tiles_meta = []
for i, nm in enumerate(stamp_files):
    a = STAMPS[nm]
    from_pieces = nm == 'main_building'
    user_mask = 'art/pieces/main_building_collision.png' if from_pieces else f'art/stamps/{nm}_collision.png'
    if os.path.exists(user_mask):
        mask = np.array(Image.open(user_mask).convert('RGBA'))[..., 3] > 0
    else:
        mask = a[..., 3] > 0
        if nm.startswith('rotunda'):                           # only the arched gallery (north third) blocks; the floor is walkable
            rows_ = np.nonzero(mask.any(axis=1))[0]
            mask[rows_.min() + int((rows_.max() - rows_.min()) * 0.30):] = False
        if not from_pieces:                                  # seed once; yours to edit afterwards
            m_img = np.zeros(a.shape[:2] + (4,), np.uint8); m_img[mask] = (255, 0, 0, 160)
            Image.fromarray(m_img).save(user_mask)
    m_img = np.zeros(a.shape[:2] + (4,), np.uint8); m_img[mask] = (255, 0, 0, 160)
    Image.fromarray(m_img).save(f'tiled/stamps/{nm}_collision.png')
    tiles_meta.append({'id': i, 'image': f'../stamps/{nm}.png', 'imagewidth': int(a.shape[1]), 'imageheight': int(a.shape[0]),
                       'properties': [{'name': 'stamp', 'type': 'string', 'value': nm},
                                      {'name': 'collision', 'type': 'file', 'value': f'../stamps/{nm}_collision.png'}]})
json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'buildings',
           'tilewidth': max(t['imagewidth'] for t in tiles_meta), 'tileheight': max(t['imageheight'] for t in tiles_meta),
           'tilecount': len(tiles_meta), 'columns': 0, 'margin': 0, 'spacing': 0,
           'grid': {'orientation': 'orthogonal', 'width': 1, 'height': 1}, 'tiles': tiles_meta},
          open('tiled/tilesets/buildings.tsj', 'w'), indent=1)
TERRAIN_FIRST, BUILD_FIRST = 1, 1 + N_TERRAIN
PROPS_FIRST = BUILD_FIRST + len(stamp_files)
objs, oid = [], 1
for s in sorted(slots, key=lambda s: (s.get('on_top', False), s['y'] + s['h'])):
    props = [{'name': 'type', 'type': 'string', 'value': s['type']}, {'name': 'osm', 'type': 'string', 'value': str(s.get('osm', ''))}]
    if s['type'].startswith('stamp:'):
        a = STAMPS[s['type'][6:]]
        objs.append({'id': oid, 'name': s['name'], 'type': 'building', 'gid': BUILD_FIRST + stamp_files.index(s['type'][6:]),
                     'x': s['x'] * T, 'y': s['y'] * T + a.shape[0], 'width': int(a.shape[1]), 'height': int(a.shape[0]),
                     'rotation': 0, 'visible': True, 'properties': props})
    else:
        objs.append({'id': oid, 'name': s['name'], 'type': 'slot', 'x': s['x'] * T, 'y': s['y'] * T, 'width': s['w'] * T,
                     'height': s['h'] * T, 'rotation': 0, 'visible': True, 'properties': props})
    oid += 1
events = []
for s in slots:
    if s['name'] == 'building': continue
    events.append({'id': oid, 'name': s['name'], 'type': 'zone', 'x': s['x'] * T - T, 'y': s['y'] * T - T,
                   'width': (s['w'] + 2) * T, 'height': (s['h'] + 2) * T, 'rotation': 0, 'visible': True}); oid += 1
mw_slot = next(s for s in slots if s['type'] == 'stamp:main_building')
events.append({'id': oid, 'name': 'spawn', 'type': 'spawn', 'point': True, 'x': round(mw_slot['x'] * T + MB_PORCH_X),
               'y': round(mw_slot['y'] * T + MB_PORCH_Y + 18), 'width': 0, 'height': 0, 'rotation': 0, 'visible': True}); oid += 1
prop_objs = []
for name, cx, by in garden_props:                            # tile objects are anchored bottom-left; flags by their pole
    w_, h_ = PROP_IMG[name].size
    prop_objs.append({'id': oid, 'name': name, 'type': 'prop', 'gid': PROPS_FIRST + PROP_NAMES.index(name),
                      'x': round(cx - (3 if name.startswith('flag') else w_ / 2)), 'y': round(by), 'width': w_, 'height': h_,
                      'rotation': 0, 'visible': True}); oid += 1
for run, hw in garden_hedges:
    x0_, y0_ = run[0]
    prop_objs.append({'id': oid, 'name': 'hedge', 'type': 'hedge', 'x': x0_, 'y': y0_, 'width': 0, 'height': 0, 'rotation': 0,
                      'visible': True, 'polyline': [{'x': round(x - x0_, 1), 'y': round(y - y0_, 1)} for x, y in run],
                      'properties': [{'name': 'width', 'type': 'int', 'value': hw}]}); oid += 1
empty = [0] * (MW * MH)
tmj = {
    'type': 'map', 'version': '1.10', 'tiledversion': '1.10.2', 'orientation': 'orthogonal', 'renderorder': 'right-down',
    'infinite': False, 'width': MW, 'height': MH, 'tilewidth': T, 'tileheight': T, 'nextlayerid': 9, 'nextobjectid': oid,
    'properties': [{'name': 'rotation_deg', 'type': 'float', 'value': round(THETA, 2)},
                   {'name': 'metres_per_tile', 'type': 'float', 'value': M_PER_TILE}],
    'layers': [
        {'id': 1, 'name': 'underlay (blueprint, not exported)', 'type': 'imagelayer', 'image': f'../underlay/{AREA}_blueprint.png',
         'x': 0, 'y': 0, 'opacity': 0.5, 'visible': False},
        {'id': 2, 'name': 'ground', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': MW, 'height': MH, 'opacity': 1, 'visible': True,
         'data': [int(v) + TERRAIN_FIRST for v in ground_ids.ravel()]},
        {'id': 3, 'name': 'decor', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': MW, 'height': MH, 'opacity': 1, 'visible': True, 'data': empty},
        {'id': 4, 'name': 'buildings', 'type': 'objectgroup', 'draworder': 'index', 'x': 0, 'y': 0, 'opacity': 1, 'visible': True, 'objects': objs},
        {'id': 5, 'name': 'props', 'type': 'objectgroup', 'draworder': 'topdown', 'x': 0, 'y': 0, 'opacity': 1, 'visible': True, 'objects': prop_objs},
        {'id': 6, 'name': 'above', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': MW, 'height': MH, 'opacity': 1, 'visible': True, 'data': empty},
        {'id': 7, 'name': 'collision', 'type': 'objectgroup', 'draworder': 'topdown', 'x': 0, 'y': 0, 'opacity': 0.6, 'visible': True, 'objects': []},
        {'id': 8, 'name': 'events', 'type': 'objectgroup', 'draworder': 'topdown', 'x': 0, 'y': 0, 'opacity': 1, 'visible': True, 'objects': events},
    ],
    'tilesets': [{'firstgid': TERRAIN_FIRST, 'source': '../tilesets/terrain.tsj'},
                 {'firstgid': BUILD_FIRST, 'source': '../tilesets/buildings.tsj'},
                 {'firstgid': PROPS_FIRST, 'source': '../tilesets/props.tsj'}],
}
out_map = f'tiled/maps/{AREA}.tmj'
if os.path.exists(out_map) and '--force' not in sys.argv:
    out_map = f'tiled/maps/{AREA}.generated.tmj'           # never overwrite a map the user may have edited
    print(f'note: {AREA}.tmj exists (possibly edited in Tiled); wrote {out_map} instead. Use --force to replace.')
json.dump(tmj, open(out_map, 'w'))
json.dump({'type': 'world', 'maps': [{'fileName': f'maps/{AREA}.tmj', 'x': 0, 'y': 0, 'width': W, 'height': H}],
           'onlyShowAdjacentMaps': False}, open('tiled/campus.world', 'w'), indent=1)
json.dump([{k: v for k, v in s.items() if k != 'outline'} for s in slots], open(f'data/{AREA}_slots.json', 'w'), indent=1)
print(f'{len(slots)} slots ({sum(1 for s in slots if s["type"].startswith("stamp:"))} with art); ground painted with terrain tiles')
