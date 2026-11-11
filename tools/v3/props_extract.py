"""Living-world props: cut animated elements out of the user's source art and generate their frames.

- flags: 4-frame cloth wave         - palms: 4-frame frond sway
- flowers: 2-frame shimmer (tile)   - tall grass: 3-frame rustle sprite (drawn from the patch's own colours)
- ambient: drifting cloud shadows, a bird crossing

Writes art/props/*.png sprite strips and data/debug/anim_sampler.gif (preview for approval).
Usage (from repo root): python3 tools/v3/props_extract.py
"""
import math, os
import numpy as np
from PIL import Image

SRC = 'art/reference_main.png'
COLORS = 128
os.makedirs('art/props', exist_ok=True)
os.makedirs('data/debug', exist_ok=True)

# ---------------------------------------------------------------- base art (same cleanup as from_ref.py)
a = np.array(Image.open(SRC).convert('RGB'))
for (x0, y0, x1, y1, dx, dy) in [(626, 329, 643, 358, 18, 0), (210, 440, 228, 471, -20, 0), (1005, 398, 1024, 427, -22, 0)]:
    a[y0:y1, x0:x1] = a[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
q = Image.fromarray(a).quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
PALETTE = q.getpalette()[:COLORS * 3]
Q = np.array(q.convert('RGB'))
SRCA = a.copy()
H, W = Q.shape[:2]


def flood_bg(crop, tol=34):
    """background = pixels connected to the crop border whose colour is close to some border colour"""
    h, w = crop.shape[:2]
    c = crop.reshape(-1, 3).astype(int)
    border = np.unique(np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]]).astype(int), axis=0)
    d = np.min(np.abs(c[:, None, :] - border[None, :, :]).sum(axis=2), axis=1).reshape(h, w)
    ok = d < tol
    bg = np.zeros((h, w), bool)
    stack = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < h and 0 <= x < w and not bg[y, x] and ok[y, x]:
            bg[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return bg, ok


def keep_big(fg, min_px=30):
    """drop tiny foreground specks (texture noise that survived the colour test)"""
    h, w = fg.shape
    seen = np.zeros_like(fg); out = np.zeros_like(fg)
    for y0 in range(h):
        for x0 in range(w):
            if fg[y0, x0] and not seen[y0, x0]:
                comp, st = [], [(y0, x0)]
                seen[y0, x0] = True
                while st:
                    y, x = st.pop(); comp.append((y, x))
                    for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= yy < h and 0 <= xx < w and fg[yy, xx] and not seen[yy, xx]:
                            seen[yy, xx] = True; st.append((yy, xx))
                if len(comp) >= min_px:
                    for y, x in comp: out[y, x] = True
    return out


def cutout(box, tol=34):
    x0, y0, x1, y1 = box
    crop = SRCA[y0:y1, x0:x1]            # cut from the full-colour source (keeps flag colours)
    bg, ok = flood_bg(crop, tol)
    bg = ~keep_big(~bg)
    rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    rgba[..., :3] = crop
    rgba[..., 3] = np.where(bg, 0, 255)
    return rgba, ~bg


props_mask = np.zeros((H, W), bool)
PROPS = {}


def register(name, box, kind, tol=20):
    rgba, m = cutout(box, tol)
    PROPS[name] = dict(box=box, rgba=rgba, mask=m, kind=kind)
    x0, y0, x1, y1 = box
    props_mask[y0:y1, x0:x1] |= m


# measured on the reference grid (see data/debug/props_sw.png / props_area.png)
for i, box in enumerate([(129, 338, 149, 384), (97, 405, 121, 452), (260, 380, 285, 435),
                         (226, 438, 251, 497), (147, 493, 171, 545), (47, 543, 71, 595)]):
    register(f'flag{i}', box, 'flag')
register('palm0', (258, 189, 313, 244), 'palm', tol=12)


def inpaint(img, mask):
    """fill masked pixels by copying unmasked texture from horizontal neighbours (keeps the grass pattern)"""
    out = img.copy()
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        for d in range(6, 80):
            for xx in (x - d, x + d):
                if 0 <= xx < W and not mask[y, xx]:
                    out[y, x] = img[y, xx]
                    break
            else:
                continue
            break
    return out


BASE = inpaint(Q, props_mask)
Image.fromarray(BASE).save('art/map_main_base_noprops.png')


# ---------------------------------------------------------------- frame generators
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
            if dy > 0:
                fr[dy:, c] = col[:-dy]
            elif dy < 0:
                fr[:dy, c] = col[-dy:]
            else:
                fr[:, c] = col
        frames.append(fr)
    return frames


def palm_frames(rgba, n=4):
    h, w = rgba.shape[:2]
    a_ = rgba[..., 3] > 0
    rows = np.nonzero(a_.any(axis=1))[0]
    top, bot = rows.min(), rows.max()
    pivot = top + int((bot - top) * 0.55)          # fronds above this row sway
    frames = []
    for f in range(n):
        amp = [0, 1.6, 0, -1.6][f % 4]
        fr = np.zeros_like(rgba)
        for y in range(h):
            k = max(0.0, (pivot - y) / max(1, pivot - top))
            dx = int(round(amp * k))
            row = rgba[y]
            if dx > 0:
                fr[y, dx:] = row[:-dx]
            elif dx < 0:
                fr[y, :dx] = row[-dx:]
            else:
                fr[y] = row
        frames.append(fr)
    return frames


def flower_frames(img, box):
    """2-frame shimmer: saturated pink/purple/red/orange pixels alternate brightness on a 2x2 checker"""
    x0, y0, x1, y1 = box
    region = img[y0:y1, x0:x1].astype(int)
    r, g, b = region[..., 0], region[..., 1], region[..., 2]
    petal = (r > g + 40) & ((r > 150) | (b > 150))
    yy, xx = np.mgrid[0:y1 - y0, 0:x1 - x0]
    chk = ((xx // 2 + yy // 2) % 2) == 0
    f0 = region.copy()
    f1 = region.copy()
    f1[petal & chk] = np.clip(region[petal & chk] * 1.18 + 10, 0, 255)
    f1[petal & ~chk] = np.clip(region[petal & ~chk] * 0.86, 0, 255)
    return [f0.astype(np.uint8), f1.astype(np.uint8)], petal


def grass_rustle(sample_box):
    """3-frame rustle sprite (Emerald-style), using the tall-grass patch's own dark/light colours"""
    x0, y0, x1, y1 = sample_box
    px = Q[y0:y1, x0:x1].reshape(-1, 3).astype(int)
    green = px[(px[:, 1] > px[:, 0] + 20)]
    lum = green.sum(axis=1)
    dark = tuple(np.percentile(green[lum < np.percentile(lum, 25)], 50, axis=0).astype(int))
    light = tuple(np.percentile(green[lum > np.percentile(lum, 75)], 50, axis=0).astype(int))
    frames = []
    for spread in (0, 2, 1):
        fr = np.zeros((12, 18, 4), np.uint8)
        for bx, lean in ((4, -1), (9, 0), (14, 1)):
            for t in range(7):
                x = int(round(bx + lean * spread * t / 6))
                y = 11 - t
                for xx_, c in ((x, light), (x + 1, dark)):
                    if 0 <= xx_ < 18:
                        fr[y, xx_, :3] = c
                        fr[y, xx_, 3] = 255
        frames.append(fr)
    return frames


def bird_frames():
    up = ["#...#", ".#.#.", "..#.."]
    down = [".....", "##.##", "..#.."]
    out = []
    for pat in (up, down):
        fr = np.zeros((3, 5, 4), np.uint8)
        for y, row in enumerate(pat):
            for x, ch in enumerate(row):
                if ch == '#':
                    fr[y, x] = (52, 52, 72, 255)
        out.append(fr)
    return out


def cloud_tile(w, h, period):
    """periodic soft cloud-shadow alpha field (0..1), repeats every `period` px horizontally"""
    yy, xx = np.mgrid[0:h, 0:w]
    f = np.zeros((h, w))
    rng = np.random.default_rng(3)
    for _ in range(5):
        cx, cy = rng.uniform(0, period), rng.uniform(0, h)
        rx, ry = rng.uniform(40, 70), rng.uniform(20, 34)
        for k in (-1, 0, 1):
            d = ((xx - cx - k * period) / rx) ** 2 + ((yy - cy) / ry) ** 2
            f = np.maximum(f, np.clip(1.2 - d, 0, 1))
    return np.round(f * 3) / 3        # posterised: stays pixel-art (3 steps)


# ---------------------------------------------------------------- build strips
def save_strip(name, frames):
    h = max(fr.shape[0] for fr in frames); w = sum(fr.shape[1] for fr in frames)
    strip = np.zeros((h, w, 4), np.uint8); x = 0
    for fr in frames:
        strip[:fr.shape[0], x:x + fr.shape[1]] = fr; x += fr.shape[1]
    Image.fromarray(strip).save(f'art/props/{name}.png')

anim = {}
for name, p in PROPS.items():
    anim[name] = flag_frames(p['rgba']) if p['kind'] == 'flag' else palm_frames(p['rgba'])
    save_strip(name, anim[name])
FLOWER_BOX = (243, 536, 318, 631)
flowers, petal_mask = flower_frames(BASE, FLOWER_BOX)
rustle = grass_rustle((40, 395, 95, 445))
birds = bird_frames()
save_strip('grass_rustle', rustle)
save_strip('bird', birds)

# ---------------------------------------------------------------- sampler GIF
CROP = (0, 180, 330, 640)
cx0, cy0, cx1, cy1 = CROP
cw, ch = cx1 - cx0, cy1 - cy0
N = 48
clouds = cloud_tile(cw, ch, 96)
gif = []
for t in range(N):
    fr = BASE[cy0:cy1, cx0:cx1].copy()
    fb = flowers[(t // 4) % 2]
    fx0, fy0, fx1, fy1 = FLOWER_BOX
    fr[fy0 - cy0:fy1 - cy0, fx0 - cx0:fx1 - cx0] = fb
    for name, p in PROPS.items():
        frames = anim[name]
        idx = (t // 2) % 4 if p['kind'] == 'flag' else (t // 3) % 4
        spr = frames[idx]
        x0, y0, x1, y1 = p['box']
        sub = fr[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0]
        al = spr[..., 3:4] > 0
        sub[:] = np.where(al, spr[..., :3], sub)
    # tall-grass rustle loops at one spot in the patch
    rs = rustle[(t // 2) % 3]
    gx, gy = 60 - cx0, 420 - cy0
    sub = fr[gy:gy + 12, gx:gx + 18]
    sub[:] = np.where(rs[..., 3:4] > 0, rs[..., :3], sub)
    # bird crossing
    bx = int(-10 + t * (cw + 20) / N); by = 60 + int(4 * math.sin(t / 3))
    b = birds[(t // 2) % 2]
    for yy in range(3):
        for xx in range(5):
            X, Y = bx + xx, by + yy
            if b[yy, xx, 3] and 0 <= X < cw and 0 <= Y < ch:
                fr[Y, X] = b[yy, xx, :3]
    # drifting cloud shadow (periodic -> seamless loop), slight blue tint like GBA shading
    sh = np.roll(clouds, shift=t * 2, axis=1)[..., None]
    fr = (fr * (1 - 0.09 * sh) + np.array([30, 40, 70]) * 0.09 * sh * 0.4).astype(np.uint8)
    gif.append(Image.fromarray(fr).resize((cw * 2, ch * 2), Image.NEAREST))
gif[0].save('data/debug/anim_sampler.gif', save_all=True, append_images=gif[1:], duration=125, loop=0)
# a static sheet of frames for quick review
sheet = Image.new('RGB', (cw * 2 * 2 + 8, ch * 2), (20, 20, 28))
sheet.paste(gif[0], (0, 0)); sheet.paste(gif[5], (cw * 2 + 8, 0))
sheet.save('data/debug/anim_sampler_frames.png')
print('props:', list(PROPS), '| sampler: data/debug/anim_sampler.gif')
