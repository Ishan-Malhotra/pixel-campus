"""Blueprint: OpenStreetMap -> accurate, grid-locked campus map (Emerald-style: tile ground + building stamps).

Geometry (where every road and building is) comes ONLY from OpenStreetMap, rotated ~8 deg so the campus street grid is
axis-aligned, at 1 tile = 16 px = 5 m (same scale as the approved art). Looks come from the user's approved images:
  - ground (lawn, roads with kerbs, paths) is painted with textures/colours sampled from the approved art,
  - buildings are STAMPS placed into their real OSM footprints (slots):
      main_west : Clock Tower + west part of the Main Building, cut from art/reference_main.png
      fd2       : FD2 quad, cut from art/reference_fd2.png
      rotunda   : the Rotunda, cut from art/reference_main.png at 1/2 scale (the art draws it ~2x real size)
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
from PIL import Image, ImageDraw, ImageFont

T, M_PER_TILE = 16, 5.0
PPM = T / M_PER_TILE                       # px per metre (3.2)
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


slots = []
for f in F:
    t = f['tags']
    if f['kind'] == 'line' and 'highway' in t:
        pts = [P(p) for p in f['pts']]
        hw = t['highway']
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


def make_stamp(name, src, box, tol=40, green_only=True, half=False, rects=None):
    x0, y0, x1, y1 = box
    crop = src[y0:y1, x0:x1].copy()
    if rects is not None:                                   # exact building outline (measured rects, in px of src)
        fg = np.zeros(crop.shape[:2], bool)
        for rx0, ry0, rx1, ry1 in rects:
            fg[max(0, ry0 - y0):max(0, ry1 - y0), max(0, rx0 - x0):max(0, rx1 - x0)] = True
    else:
        fg = ~flood_bg(crop, tol, green_only)
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
# Tower point, with the porch ~25 m (80 px) south of the tower point -- as in the real campus
for s_ in [s_ for s_ in slots if s_['name'] == 'FD-2 & FD-3']:
    slots.remove(s_)
    tx_, ty_ = P(next(f['pt'] for f in F if f['tags'].get('name') == 'BITS Clock Tower'))
    mh, mw = MB_STAMP.shape[0] // T, MB_STAMP.shape[1] // T
    slots.append({'name': 'Main Building', 'type': 'stamp:main_building', 'x': round((tx_ - MB_PORCH_X) / T),
                  'y': round((ty_ + 80 - MB_PORCH_Y) / T), 'w': mw, 'h': mh, 'outline': s_['outline']})
# the Rotunda is a point in OSM: centre its stamp on it, just south of the Main Building
rx, ry = P(next(f['pt'] for f in F if f['tags'].get('name') == 'Rotunda'))
rw, rh = STAMPS['rotunda'].shape[1] // T, STAMPS['rotunda'].shape[0] // T
slots.append({'name': 'Rotunda', 'type': 'stamp:rotunda', 'x': round(rx / T - rw / 2), 'y': round(ry / T - rh / 2),
              'w': rw, 'h': rh, 'outline': [], 'on_top': True})

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
        if nm == 'rotunda':                                   # only the arched gallery (north third) blocks; the floor is walkable
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
        {'id': 5, 'name': 'props', 'type': 'objectgroup', 'draworder': 'topdown', 'x': 0, 'y': 0, 'opacity': 1, 'visible': True, 'objects': []},
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
