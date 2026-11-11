"""Build the playable map piece by piece (Emerald-style): the approved Main Building map as the base, then separate
pieces joined to it with roads painted in the base map's own style.

  base   : art/reference_main.png (approved), baked-in people painted out
  pieces : FD2 building, FD2 circle island, M Lawns tree belt, all cut from art/reference_fd2.png and recoloured
           to the base palette
  joins  : the base road continued east, a circle junction, Krishna Marg south, a lane between Main Building and FD2
  life   : flags wave, palms + tree belt sway, tall grass moves, flowers shimmer, grass rustles under the player

Writes game/public/maps/main.json (Tiled format), main.meta.json, game/public/tiles/campus.png,
game/public/props/*.png and data/debug previews.
Usage (from repo root):  python3 tools/v2/map_main.py >/dev/null   # (re)measures base collision -> data/layout_ref.json
                         python3 tools/v3/build_map.py
"""
import json, math, os
import numpy as np
from PIL import Image

T = 16
OUT = 'game/public'
os.makedirs(f'{OUT}/props', exist_ok=True)
os.makedirs(f'{OUT}/maps', exist_ok=True)
os.makedirs(f'{OUT}/tiles', exist_ok=True)
os.makedirs('data/debug', exist_ok=True)

# ===================================================================== base + palette
BASE = np.array(Image.open('art/reference_main.png').convert('RGB'))
for (x0, y0, x1, y1, dx, dy) in [(626, 329, 643, 358, 18, 0), (210, 440, 228, 471, -20, 0), (1005, 398, 1024, 427, -22, 0)]:
    BASE[y0:y1, x0:x1] = BASE[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
PAL_IMG = Image.fromarray(BASE).quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
PAL = np.array(PAL_IMG.getpalette()[:128 * 3]).reshape(-1, 3)


def to_palette(rgb):
    """map RGB pixels to the base palette (keeps every piece in the same 128 colours)"""
    flat = rgb.reshape(-1, 3).astype(np.int32)
    out = np.empty_like(flat)
    for i in range(0, len(flat), 65536):
        c = flat[i:i + 65536]
        d = ((c[:, None, :] - PAL[None, :, :]) ** 2).sum(axis=2)
        out[i:i + 65536] = PAL[np.argmin(d, axis=1)]
    return out.reshape(rgb.shape).astype(np.uint8)


NEW = np.array(Image.open('art/reference_fd2.png').convert('RGB'))
NEW[466:500, 918:952] = NEW[466:500, 880:914]          # generator watermark on the lawn

BW, BH = BASE.shape[1], 43 * T                          # base 1024 x 688
W, H = 93 * T, 43 * T                                   # map 1488 x 688
img = np.zeros((H, W, 3), np.uint8)
img[:BASE.shape[0], :BW] = BASE
img[BASE.shape[0]:, :BW] = BASE[-1:, :]


# ===================================================================== cut-out helpers
def flood_bg(crop, tol, green_only=False, bg_ref=None):
    h, w = crop.shape[:2]
    c = crop.reshape(-1, 3).astype(int)
    border = np.unique(np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]]).astype(int), axis=0)
    if bg_ref is not None:
        border = bg_ref
    d = np.min(np.abs(c[:, None, :] - border[None, :, :]).sum(axis=2), axis=1).reshape(h, w)
    ok = d < tol
    if green_only:
        cc = crop.astype(int)
        ok &= (cc[..., 1] > cc[..., 0] + 12) | (cc.sum(axis=2) < 120)
    bg = np.zeros((h, w), bool)
    st = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while st:
        y, x = st.pop()
        if 0 <= y < h and 0 <= x < w and not bg[y, x] and ok[y, x]:
            bg[y, x] = True
            st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return bg


def keep_big(fg, min_px=30):
    h, w = fg.shape
    seen = np.zeros_like(fg); out = np.zeros_like(fg)
    for y0 in range(h):
        for x0 in range(w):
            if fg[y0, x0] and not seen[y0, x0]:
                comp, st = [], [(y0, x0)]; seen[y0, x0] = True
                while st:
                    y, x = st.pop(); comp.append((y, x))
                    for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= yy < h and 0 <= xx < w and fg[yy, xx] and not seen[yy, xx]:
                            seen[yy, xx] = True; st.append((yy, xx))
                if len(comp) >= min_px:
                    for y, x in comp: out[y, x] = True
    return out


def cutout(src, box, tol=20, open_bottom=False, green_only=False, bg_ref=None):
    x0, y0, x1, y1 = box
    crop = src[y0:y1, x0:x1].copy()
    if open_bottom:                                        # piece runs off the source edge: don't treat bottom as border
        crop = np.concatenate([crop, np.repeat(crop[:1, :1], 1, axis=0).repeat(crop.shape[1], axis=1)], axis=0)
    fg = ~flood_bg(crop, tol, green_only, bg_ref)
    fg = keep_big(fg)
    if open_bottom:
        crop, fg = crop[:-1], fg[:-1]
    rgba = np.zeros(crop.shape[:2] + (4,), np.uint8)
    rgba[..., :3] = crop
    rgba[..., 3] = np.where(fg, 255, 0)
    return rgba


def paste(dst, rgba, x, y):
    h, w = rgba.shape[:2]
    al = rgba[..., 3:4] > 0
    sub = dst[y:y + h, x:x + w]
    sub[:] = np.where(al[:sub.shape[0], :sub.shape[1]], rgba[:sub.shape[0], :sub.shape[1], :3], sub)


# ===================================================================== pieces + joins (east side)
# 1) close the cut outline of the base map's east-end pavilion (mirror of its left edge around the door axis)
def find_lawn_patch(a, size=32):
    best, bx, by = 1e9, 0, 0
    for y in range(0, a.shape[0] - size, 8):
        for x in range(0, a.shape[1] - size, 8):
            p = a[y:y + size, x:x + size].astype(int)
            if not ((p[..., 1] > p[..., 0] + 40) & (p[..., 1] > 170)).all():
                continue
            v = p.std(axis=(0, 1)).sum()
            if v < best: best, bx, by = v, x, y
    return a[by:by + size, bx:bx + size]
lawn = find_lawn_patch(BASE)                             # plainest bright-lawn patch in the base map
for y in range(H):
    for x in range(BW, W):
        img[y, x] = lawn[y % 32, x % 32]
for k in range(4):                                        # close the east-end pavilion's cut outline
    img[267:397, BW + k] = img[267:397, 2 * 1001 - (BW + k)]
# 3) the base road continues east (exact cross-section of the base road near its east end)
ROAD = BASE[396:469, 960].copy()                        # y 396..468: verge, kerb, edge, asphalt, edge, kerb, verge
RY0 = 396
for x in range(BW, W):
    img[RY0:RY0 + len(ROAD), x] = ROAD
road_top, road_bot = 401, 464                           # kerb lines
# 4) circle junction with the FD2 island, Krishna Marg south, a lane north between Main Building and FD2
CX, CY = 1100, 432
yy, xx = np.mgrid[0:H, 0:W]
asphalt = ROAD[len(ROAD) // 2]
kerb = BASE[401, 960]; edge_dark = BASE[402, 960]; verge = BASE[399, 960]
def road_mask_vertical(x0, x1, y0, y1):
    return (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
circle = (((xx - CX) / 74.0) ** 2 + ((yy - CY) / 60.0) ** 2) <= 1
km = road_mask_vertical(CX - 32, CX + 32, CY, H)        # Krishna Marg (64 px like the base road)
lane = road_mask_vertical(1030, 1058, 0, road_top + 2)  # narrow lane north (separates Main Building and FD2)
paved = circle | km | lane | ((yy >= road_top + 1) & (yy < road_bot) & (xx >= BW))
img[paved] = asphalt
# asphalt speckle like the base road
spk = paved & (((xx * 7 + yy * 3) % 37) == 0)
img[spk] = BASE[430, 940]
# kerb ring: 1 px light kerb + 1 px dark edge just inside
def ring(m):
    inner = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m & ~inner
e1 = ring(paved); img[e1 & (xx >= BW)] = kerb
e2 = ring(paved & ~e1); img[e2 & (xx >= BW)] = edge_dark
outer_v = ring(np.roll(paved, 1, 0) | np.roll(paved, -1, 0) | np.roll(paved, 1, 1) | np.roll(paved, -1, 1)) & ~paved
img[outer_v & (xx >= BW)] = verge
# island stamp (white-kerbed round lawn with topiary + bougainvillea), cut from the new image
isl = NEW[357:439, 538:643].copy()
iy, ix = np.mgrid[0:isl.shape[0], 0:isl.shape[1]]
imask = (((ix - 52) / 51.0) ** 2 + ((iy - 40) / 39.0) ** 2) <= 1
island = np.zeros(isl.shape[:2] + (4,), np.uint8)
island[..., :3] = to_palette(isl); island[..., 3] = np.where(imask, 255, 0)
paste(img, island, CX - 52, CY - 40)
# 5) FD2 building piece (building only) north of the road, east of the lane
fd2 = cutout(NEW, (596, 6, 1010, 374), tol=40, green_only=True)
fd2[..., :3] = to_palette(fd2[..., :3])
_c = fd2[..., :3].astype(int)                             # drop the bit of the new image's ring road at the SW corner
_grey = (np.abs(_c[..., 0] - _c[..., 2]) < 30) & (np.abs(_c[..., 1] - _c[..., 2]) < 26) & (_c.sum(axis=2) > 330) & (_c.sum(axis=2) < 520)
_grey[:320] = False; _grey[:, 34:] = False
fd2[_grey, 3] = 0
FD2_X, FD2_Y = 1066, 10
paste(img, fd2, FD2_X, FD2_Y)

# ===================================================================== living props
props, anim_defs = [], {}
solid_extra = []                                          # (x0,y0,x1,y1) px


def register_anim(key, frames, fps):
    h = max(f.shape[0] for f in frames); w = max(f.shape[1] for f in frames)
    strip = np.zeros((h, w * len(frames), 4), np.uint8)
    for i, f in enumerate(frames):
        strip[:f.shape[0], i * w:i * w + f.shape[1]] = f
    strip[..., :3] = to_palette(strip[..., :3])
    Image.fromarray(strip).save(f'{OUT}/props/{key}.png')
    anim_defs[key] = {'w': w, 'h': h, 'frames': len(frames), 'fps': fps}


def shear_frames(rgba, amps, pivot_frac=0.55):
    """sway: rows above the pivot shift sideways, more at the top (trees, palms, grass blades)"""
    h = rgba.shape[0]
    rows = np.nonzero((rgba[..., 3] > 0).any(axis=1))[0]
    top, bot = (rows.min(), rows.max()) if len(rows) else (0, h - 1)
    pivot = top + int((bot - top) * pivot_frac)
    out = []
    for amp in amps:
        fr = np.zeros_like(rgba)
        for y in range(h):
            dx = int(round(amp * max(0.0, (pivot - y) / max(1, pivot - top))))
            row = rgba[y]
            if dx > 0: fr[y, dx:] = row[:-dx]
            elif dx < 0: fr[y, :dx] = row[-dx:]
            else: fr[y] = row
        out.append(fr)
    return out


def flag_frames(rgba, n=4):
    h, w = rgba.shape[:2]
    a_ = rgba[..., 3] > 0
    rgb = rgba[..., :3].astype(int)
    grey = (np.abs(rgb[..., 0] - rgb[..., 1]) < 18) & (np.abs(rgb[..., 1] - rgb[..., 2]) < 22)
    pole_x = int(np.argmax((a_ & grey).sum(axis=0)))
    frames = []
    for f in range(n):
        fr = np.zeros_like(rgba)
        fr[:, :pole_x + 2] = rgba[:, :pole_x + 2]
        for c in range(pole_x + 2, w):
            k = c - pole_x
            dy = int(round(1.4 * math.sin(2 * math.pi * (k / 7.0 - f / n)) * min(1.0, k / 4)))
            col = rgba[:, c]
            if dy > 0: fr[dy:, c] = col[:-dy]
            elif dy < 0: fr[:dy, c] = col[-dy:]
            else: fr[:, c] = col
        frames.append(fr)
    return frames, pole_x


remove = np.zeros((H, W), bool)                          # base pixels to inpaint (prop now a sprite)


def add_prop(key, rgba, x, y, frames, fps, base_y=None, ground=False, collide=None, from_base=True):
    register_anim(key, frames, fps)
    if from_base:
        h, w = rgba.shape[:2]
        remove[y:y + h, x:x + w] |= rgba[..., 3] > 0
    props.append({'k': key, 'x': int(x), 'y': int(y), 'depth': -0.5 if ground else int(base_y if base_y is not None else y + rgba.shape[0])})
    if collide:
        solid_extra.append(collide)


# flags on the base map (pole base boxes measured on the reference grid)
FLAGS = [(129, 338, 149, 384), (97, 405, 121, 452), (260, 380, 285, 435), (226, 438, 251, 497), (147, 493, 171, 545),
         (47, 543, 71, 595)]
for i, box in enumerate(FLAGS):
    rg = cutout(BASE, box, tol=20)
    frs, px_ = flag_frames(rg)
    x0, y0, x1, y1 = box
    add_prop(f'flag{i}', rg, x0, y0, frs, 8, base_y=y1, collide=(x0 + px_ - 2, y1 - 6, x0 + px_ + 4, y1))
# palms on the base map
PALMS = []                                                 # palms stay static for now (only grass + flags animate)
for i, box in enumerate(PALMS):
    rg = cutout(BASE, box, tol=12)
    x0, y0, x1, y1 = box
    add_prop(f'palm{i}', rg, x0, y0, shear_frames(rg, [0, 1.6, 0, -1.6]), 3, base_y=y1 - 6,
             collide=((x0 + x1) // 2 - 5, y1 - 14, (x0 + x1) // 2 + 5, y1 - 6))
# M Lawns tree belt (from the new image), sways gently; its lower part blocks
LAWN_REF = np.unique(NEW[420:452, 700:732].reshape(-1, 3).astype(int), axis=0)   # the new image's plain lawn colours
belt = cutout(NEW, (690, 455, 1024, 572), tol=18, open_bottom=True, bg_ref=LAWN_REF)
belt[..., :3] = to_palette(belt[..., :3])
BX, BY = W - belt.shape[1], H - belt.shape[0]
paste(img, belt, BX, BY)                                  # static (only grass + flags animate for now)
solid_extra.append((BX + 10, BY + 40, W, H))
# flowers shimmer (ground overlays)
FLOWER_BOXES = []                                          # no flower shimmer for now
for i, (x0, y0, x1, y1) in enumerate(FLOWER_BOXES):
    reg = img[y0:y1, x0:x1].astype(int)
    r, g_, b = reg[..., 0], reg[..., 1], reg[..., 2]
    petal = (r > g_ + 40) & ((r > 150) | (b > 150))
    ky, kx = np.mgrid[0:y1 - y0, 0:x1 - x0]
    chk = ((kx // 2 + ky // 2) % 2) == 0
    f1 = reg.copy()
    f1[petal & chk] = np.clip(reg[petal & chk] * 1.18 + 10, 0, 255)
    f1[petal & ~chk] = np.clip(reg[petal & ~chk] * 0.86, 0, 255)
    fr0 = np.dstack([reg, np.where(petal, 255, 0)]).astype(np.uint8)
    fr1 = np.dstack([f1, np.where(petal, 255, 0)]).astype(np.uint8)
    add_prop(f'flowers{i}', fr0, x0, y0, [fr0, fr1], 2, ground=True, from_base=False)
# tall grass moves in the wind (ground overlays: light blade tips lean one way, then the other)
TALL = [(100, 195, 206, 282), (33, 391, 97, 449)]
for i, (x0, y0, x1, y1) in enumerate(TALL):
    reg = img[y0:y1, x0:x1].astype(int)
    lum = reg.sum(axis=2)
    gr = (reg[..., 1] > reg[..., 0] + 20)
    tips = gr & (lum > np.percentile(lum[gr], 80))
    frames = []
    for dx in (0, 1, 0, -1):
        fr = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
        sh = np.roll(tips, dx, axis=1) & gr
        fr[sh, :3] = reg[tips].mean(axis=0).astype(np.uint8) if tips.any() else (200, 230, 120)
        fr[sh, 3] = 255
        under = tips & ~sh                                   # where a tip moved away, show the darker blade colour
        fr[under, :3] = np.percentile(reg[gr], 35, axis=0).astype(np.uint8)
        fr[under, 3] = 255
        frames.append(fr)
    add_prop(f'tallgrass{i}', frames[0], x0, y0, frames, 3, ground=True, from_base=False)
TALLGRASS_RECTS = [list(b) for b in TALL]
# rustle sprite (plays under the player in tall grass)
gpx = img[395:445, 40:95].reshape(-1, 3).astype(int)
gr = gpx[gpx[:, 1] > gpx[:, 0] + 20]
lum = gr.sum(axis=1)
dark = np.percentile(gr[lum < np.percentile(lum, 25)], 50, axis=0).astype(np.uint8)
light = np.percentile(gr[lum > np.percentile(lum, 75)], 50, axis=0).astype(np.uint8)
rustle = []
for spread in (0, 2, 1):
    fr = np.zeros((12, 18, 4), np.uint8)
    for bx, lean in ((4, -1), (9, 0), (14, 1)):
        for t_ in range(7):
            x = int(round(bx + lean * spread * t_ / 6)); y = 11 - t_
            for xx_, c in ((x, light), (x + 1, dark)):
                if 0 <= xx_ < 18: fr[y, xx_, :3] = c; fr[y, xx_, 3] = 255
    rustle.append(fr)
register_anim('rustle', rustle, 10)


# inpaint where props were lifted off the base (copy horizontal neighbour texture)
def inpaint(a, mask):
    out = a.copy()
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        for d in range(6, 90):
            for x2 in (x - d, x + d):
                if 0 <= x2 < a.shape[1] and not mask[y, x2]:
                    out[y, x] = a[y, x2]; break
            else:
                continue
            break
    return out


img = inpaint(img, remove)
img = np.array(Image.fromarray(img).quantize(palette=PAL_IMG, dither=Image.Dither.NONE).convert('RGB'))
Image.fromarray(img).save('art/map_base_v3.png')

# ===================================================================== collision
lay = json.load(open('data/layout_ref.json'))
C = 8
cw, ch = W // C, H // C
grid = np.zeros((ch, cw), bool)
src = np.array([c == '1' for c in lay['data']]).reshape(lay['h'], lay['w'])
grid[:min(ch, lay['h']), :min(cw, lay['w'])] = src[:ch, :min(cw, lay['w'])]
r, g_, b = (img[..., k].astype(int) for k in range(3))
dark_green = (g_ > r + 25) & (g_ > b + 15) & (g_ < 150)
green = dark_green.reshape(ch, C, cw, C).mean(axis=(1, 3)) > 0.22
nb = sum(np.roll(np.roll(green, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
green |= nb >= 5
for x0, y0, x1, y1 in TALL:
    green[y0 // C:y1 // C + 1, x0 // C:x1 // C + 1] = False
grid |= green
fd2_solid = fd2[..., 3] > 0                               # FD2 footprint from its own alpha (steps stay walkable)
fd2_solid[-12:] = False
fs = np.zeros((H, W), bool)
fs[FD2_Y:FD2_Y + fd2.shape[0], FD2_X:FD2_X + fd2.shape[1]] = fd2_solid[:H - FD2_Y, :W - FD2_X]
grid |= fs.reshape(ch, C, cw, C).mean(axis=(1, 3)) > 0.4
isl_m = (((xx - CX) / 50.0) ** 2 + ((yy - CY) / 38.0) ** 2) <= 1
grid |= isl_m.reshape(ch, C, cw, C).mean(axis=(1, 3)) > 0.4
for x0, y0, x1, y1 in solid_extra:
    grid[max(0, y0) // C:(y1 + C - 1) // C, max(0, x0) // C:(x1 + C - 1) // C] = True
grid[:, 0] = grid[:, -1] = True
grid[0, :] = grid[-1, :] = True

# ===================================================================== tiles + Tiled map + meta
tw, th = W // T, H // T
tiles, index, data = [], {}, []
for ty in range(th):
    for tx in range(tw):
        tile = img[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]
        key = tile.tobytes()
        if key not in index:
            index[key] = len(tiles); tiles.append(tile)
        data.append(index[key] + 1)
COLS = 32
rows = math.ceil(len(tiles) / COLS)
ts = np.zeros((rows * T, COLS * T, 4), np.uint8)
for i, tl in enumerate(tiles):
    ts[(i // COLS) * T:(i // COLS + 1) * T, (i % COLS) * T:(i % COLS + 1) * T, :3] = tl
    ts[(i // COLS) * T:(i // COLS + 1) * T, (i % COLS) * T:(i % COLS + 1) * T, 3] = 255
Image.fromarray(ts).save(f'{OUT}/tiles/campus.png')
json.dump({
    'type': 'map', 'version': '1.10', 'tiledversion': '1.10.2', 'orientation': 'orthogonal', 'renderorder': 'right-down',
    'infinite': False, 'width': tw, 'height': th, 'tilewidth': T, 'tileheight': T, 'nextlayerid': 2, 'nextobjectid': 1,
    'layers': [{'id': 1, 'name': 'ground', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': tw, 'height': th,
                'opacity': 1, 'visible': True, 'data': data}],
    'tilesets': [{'firstgid': 1, 'name': 'campus', 'image': '../tiles/campus.png', 'imagewidth': COLS * T,
                  'imageheight': rows * T, 'tilewidth': T, 'tileheight': T, 'tilecount': len(tiles),
                  'columns': COLS, 'margin': 0, 'spacing': 0}],
}, open(f'{OUT}/maps/main.json', 'w'))
zones = lay['zones'] + [
    {'name': 'FD2', 'x': FD2_X - 16, 'y': 0, 'w': fd2.shape[1] + 32, 'h': 390, 'p': 1},
    {'name': 'FD2 Circle', 'x': CX - 80, 'y': CY - 64, 'w': 160, 'h': 128, 'p': 0},
    {'name': 'M Lawns', 'x': CX + 40, 'y': 470, 'w': W - CX - 40, 'h': H - 470, 'p': 1},
    {'name': 'Krishna Marg', 'x': CX - 40, 'y': 495, 'w': 80, 'h': H - 495, 'p': 0},
]
json.dump({'props': [], 'frames': {}, 'anims': anim_defs, 'animProps': props, 'tallgrass': TALLGRASS_RECTS,
           'collision': {'cell': C, 'w': cw, 'h': ch, 'data': ''.join('1' if v else '0' for v in grid.ravel())},
           'zones': zones, 'spawn': lay['spawn'], 'width': W, 'height': H},
          open(f'{OUT}/maps/main.meta.json', 'w'))
Image.fromarray(img).resize((W // 6, H // 6), Image.BOX).save(f'{OUT}/maps/minimap.png')

# previews: map with props (frame 0) + collision overlay
prev = img.copy()
for p in sorted(props, key=lambda p: p['depth']):
    spr = np.array(Image.open(f"{OUT}/props/{p['k']}.png"))[:, :anim_defs[p['k']]['w']]
    sub = prev[p['y']:p['y'] + spr.shape[0], p['x']:p['x'] + spr.shape[1]]
    al = spr[:sub.shape[0], :sub.shape[1], 3:4] > 0
    sub[:] = np.where(al, spr[:sub.shape[0], :sub.shape[1], :3], sub)
Image.fromarray(prev).save('data/debug/map_v3.png')
dbg = prev.copy()
big = np.kron(grid, np.ones((C, C), bool))
dbg[big] = (dbg[big] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)
Image.fromarray(dbg).save('data/debug/map_v3_collision.png')
print(f'{tw}x{th} tiles, {len(tiles)} unique tiles, {len(props)} animated props, {len(anim_defs)} animations')
