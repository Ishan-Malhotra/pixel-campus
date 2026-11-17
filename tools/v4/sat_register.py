"""Line the satellite screenshots in art/satellite/ up with the map, so roads and open ground can be checked against them.

Every straight-down, north-up screenshot (Google Maps satellite view; any size, any zoom) is placed automatically:
its bright roofs are matched against the OpenStreetMap building outlines to find the image's scale (metres per
pixel) and position. The result is saved in art/satellite/registration.json and reused on later runs; delete an
image's entry to place it again. If the automatic match is wrong for an image, give it control points by hand:

    "some_image.png": {"points": [[px, py, osm_x, osm_y], ...]}      (2 or more; image pixel <-> OSM metres)

and the scale and position are fitted to those instead.

Writes (map pixels, the frame of data/<area>_frame.json written by blueprint.py):
  data/debug/sat_onmap.png        all screenshots mosaicked onto the map area (later / sharper images on top)
  data/debug/sat_overlay.png      the game's render at 50 % over that mosaic, OSM road centre lines in yellow
  data/debug/sat_side.png         mosaic | render side by side at 1/2 size
  tiled/underlay/<area>_satellite.png   the mosaic at full map size
Nothing here is shipped with the game: the screenshots are local references only.

Usage (repo root): python3 tools/v4/sat_register.py [area]        (default area: phase1)
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

AREA = sys.argv[1] if len(sys.argv) > 1 else 'phase1'
SAT_DIR, REG = 'art/satellite', 'art/satellite/registration.json'
FR = json.load(open(f'data/{AREA}_frame.json'))
F = json.load(open('data/campus_full.features.json'))['features']
PHI = math.radians(-FR['theta_deg'])


def to_map(x, y):
    """OSM metres -> map px (float)"""
    dx, dy = x - FR['cx0'], y - FR['cy0']
    return ((dx * math.cos(PHI) - dy * math.sin(PHI) - FR['rx0']) * FR['ppm'],
            (dx * math.sin(PHI) + dy * math.cos(PHI) - FR['ry0']) * FR['ppm'])


# ------------------------------------------------------------------ OSM buildings as a raster, 1 px = 1 m
rings = [f['outer'][0] for f in F if f['kind'] == 'area' and 'building' in f['tags']]
BX0 = math.floor(min(p[0] for r in rings for p in r)) - 50
BY0 = math.floor(min(p[1] for r in rings for p in r)) - 50
BW = math.ceil(max(p[0] for r in rings for p in r)) + 50 - BX0
BH = math.ceil(max(p[1] for r in rings for p in r)) + 50 - BY0


def osm_mask(px_per_m=1.0, box=None):
    x0, y0, w, h = box or (BX0, BY0, BW, BH)
    im = Image.new('L', (round(w * px_per_m), round(h * px_per_m)), 0)
    d = ImageDraw.Draw(im)
    for r in rings:
        d.polygon([((x - x0) * px_per_m, (y - y0) * px_per_m) for x, y in r], fill=255)
    return np.array(im, np.float32) / 255


def roof_mask(img):
    """bright, unsaturated pixels: the cream / grey flat roofs of the campus buildings"""
    a = np.array(img.convert('RGB')).astype(int)
    return ((a.min(axis=2) > 140) & (a.max(axis=2) - a.min(axis=2) < 50)).astype(np.float32)


def _corr(big, small):
    """valid cross-correlation of `small` (zero-mean) inside `big`, by FFT; index [dy, dx] = offset of small in big"""
    sh = (big.shape[0], big.shape[1])
    cc = np.fft.irfft2(np.fft.rfft2(big, s=sh) * np.conj(np.fft.rfft2(small, s=sh)), s=sh)
    return cc[:big.shape[0] - small.shape[0] + 1, :big.shape[1] - small.shape[1] + 1]


def register(img):
    """-> (metres per image px, OSM x of the image's left edge, OSM y of its top edge, score)"""
    roofs = Image.fromarray((roof_mask(img) * 255).astype(np.uint8))

    def roofs_at(w, h):
        r = np.array(roofs.resize((w, h), Image.BILINEAR), np.float32) / 255
        r -= r.mean()
        return r, float(np.sqrt((r * r).sum()) * math.sqrt(w * h) + 1e-6)

    PC = 0.5                                              # coarse: 1 px = 2 m, every scale
    osm = osm_mask(PC); osm -= osm.mean()
    best = (-1, None)
    for mpp in np.arange(0.10, 1.21, 0.01):
        w, h = round(img.width * mpp * PC), round(img.height * mpp * PC)
        if w < 40 or h < 40 or w > osm.shape[1] or h > osm.shape[0]:
            continue
        r, nrm = roofs_at(w, h)
        cc = _corr(osm, r)
        k = np.unravel_index(np.argmax(cc), cc.shape)
        if cc[k] / nrm > best[0]:
            best = (cc[k] / nrm, (float(mpp), BX0 + k[1] / PC, BY0 + k[0] / PC))
    mpp, x0, y0 = best[1]
    PF, pad = 4, 6                                        # fine: 4 px per metre, scale within +-2 %, position within +-6 m
    fine = (-1, None)
    for m2 in mpp * np.arange(0.98, 1.0201, 0.0025):
        w, h = round(img.width * m2 * PF), round(img.height * m2 * PF)
        r, nrm = roofs_at(w, h)
        o = osm_mask(PF, (x0 - pad, y0 - pad, w / PF + 2 * pad, h / PF + 2 * pad))
        if o.shape[0] < h or o.shape[1] < w:
            continue
        cc = _corr(o - o.mean(), r)
        k = np.unravel_index(np.argmax(cc), cc.shape)
        if cc[k] / nrm > fine[0]:
            fine = (float(cc[k] / nrm), (float(m2), x0 - pad + k[1] / PF, y0 - pad + k[0] / PF))
    return (*fine[1], fine[0])


def fit_points(pts):
    """scale + shift (north-up, no rotation) through control points [px, py, osm_x, osm_y], least squares"""
    p = np.array(pts, float)
    A = np.zeros((2 * len(p), 3)); b = np.zeros(2 * len(p))
    A[0::2, 0] = p[:, 0]; A[0::2, 1] = 1; b[0::2] = p[:, 2]
    A[1::2, 0] = p[:, 1]; A[1::2, 2] = 1; b[1::2] = p[:, 3]
    (mpp, x0, y0), *_ = np.linalg.lstsq(A, b, rcond=None)
    err = np.abs(A @ np.array([mpp, x0, y0]) - b).reshape(-1, 2).max(axis=1)
    return float(mpp), float(x0), float(y0), [round(float(e), 1) for e in err]


# ------------------------------------------------------------------ place every screenshot
reg = json.load(open(REG)) if os.path.exists(REG) else {}
files = sorted(f for f in os.listdir(SAT_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')))
for name in files:
    img = Image.open(os.path.join(SAT_DIR, name))
    e = reg.get(name, {})
    if 'points' in e and len(e['points']) >= 2:
        mpp, x0, y0, err = fit_points(e['points'])
        e.update(m_per_px=mpp, x0=x0, y0=y0, how='points', error_m=err)
    elif 'm_per_px' not in e:
        mpp, x0, y0, score = register(img)
        e.update(m_per_px=round(mpp, 4), x0=round(x0, 2), y0=round(y0, 2), how='auto', score=round(score, 3))
    reg[name] = e
    print(f'{name}: {img.width}x{img.height}, {e["m_per_px"]:.3f} m/px, top-left at OSM ({e["x0"]:.1f}, {e["y0"]:.1f}), '
          f'{e["how"]}' + (f', score {e["score"]}' if 'score' in e else f', errors {e.get("error_m")} m'))
json.dump(reg, open(REG, 'w'), indent=1)

# ------------------------------------------------------------------ mosaic in map pixels
W, H = FR['w'], FR['h']
mosaic = Image.new('RGB', (W, H), (24, 24, 30))
cover = Image.new('L', (W, H), 0)
c, s_ = math.cos(-PHI), math.sin(-PHI)                    # map px -> OSM metres: un-rotate
for name in sorted(files, key=lambda n: -reg[n]['m_per_px']):      # coarsest first, sharpest on top
    e = reg[name]
    img = Image.open(os.path.join(SAT_DIR, name)).convert('RGB')
    k = 1 / FR['ppm']
    # OSM x = cx0 + c * (X k + rx0) - s_ * (Y k + ry0);  y likewise; then image px = (osm - x0) / mpp
    ax, bx = c * k, -s_ * k
    cx = FR['cx0'] + c * FR['rx0'] - s_ * FR['ry0']
    ay, by = s_ * k, c * k
    cy = FR['cy0'] + s_ * FR['rx0'] + c * FR['ry0']
    m = e['m_per_px']
    coef = (ax / m, bx / m, (cx - e['x0']) / m, ay / m, by / m, (cy - e['y0']) / m)
    warped = img.transform((W, H), Image.AFFINE, coef, Image.BICUBIC)
    valid = Image.new('L', img.size, 255).transform((W, H), Image.AFFINE, coef, Image.NEAREST)
    mosaic.paste(warped, (0, 0), valid)
    cover.paste(255, (0, 0), valid)
    print(f'  {name}: covers {np.array(valid).mean() / 255:.0%} of the map')
print(f'satellite coverage of the {AREA} map: {np.array(cover).mean() / 255:.0%}')
mosaic.save('data/debug/sat_onmap.png')
os.makedirs('tiled/underlay', exist_ok=True)
mosaic.save(f'tiled/underlay/{AREA}_satellite.png')

render_path = 'data/debug/game_render.png'
if os.path.exists(render_path):
    render = Image.open(render_path).convert('RGB')
    if render.size == (W, H):
        ov = Image.blend(mosaic, render, 0.5)
        d = ImageDraw.Draw(ov)
        for f in F:
            if f['kind'] == 'line' and 'highway' in f['tags']:
                pts = [to_map(*p) for p in f['pts']]
                if any(0 <= x < W and 0 <= y < H for x, y in pts):
                    d.line(pts, fill=(255, 230, 0), width=2)
        ov.save('data/debug/sat_overlay.png')
        side = Image.new('RGB', (W + 8, H // 2), (0, 0, 0))
        side.paste(mosaic.resize((W // 2, H // 2)), (0, 0)); side.paste(render.resize((W // 2, H // 2)), (W // 2 + 8, 0))
        side.save('data/debug/sat_side.png')
