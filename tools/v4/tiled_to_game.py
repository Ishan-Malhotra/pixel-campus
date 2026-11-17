"""Tiled map -> playable game. Reads the Tiled JSON only; never modifies any art or map file.

What it reads (tiled/maps/<area>.tmj):
  ground, decor (tile layers)   painted tiles; tile property `solid` blocks, `tallgrass` rustles + sways. Decor tiles
                                are drawn after the smoothed terrain, so they cover it (tools/v4/exterior.py's kerbs).
                                Terrain-brush tiles (road, dirt path, hedge, garden lawn) are repainted on SMOOTHED
                                outlines, so stair-stepped diagonals in Tiled come out as clean curves in the game.
  above (tile layer)            drawn OVER the player (tree canopies, roof edges)
  buildings (objects)           building stamps (blocked where opaque); `slot` rectangles become placeholder blocks
  props (objects)               flags (wave); lamps, palms, bushes, signs (upright: the player walks behind them, their
                                base blocks); props with the tile property `flat` (flowers, crops) lie on the ground;
                                `hedge` polylines are drawn as smooth hedges `width` px wide (solid)
                                `paving` polygons: pale stone paving (walkable); with properties `cx`, `cy` the slabs
                                run in rings around that point, otherwise in a square grid; `road_inset` = that many px
                                along the outline are asphalt (the polygon reaches under a road; its kerb stays exact)
                                `flowerbed` polygons: a bougainvillea bed with a stone kerb (solid)
                                `roadline` polylines: a dashed white centre line on a road (walkable)
  shadows (objects)             ellipses with an `opacity` property darken the ground (palette-snapped): tree shadows
  collision (objects)           any rectangle = blocked
  events (objects)              `zone` rectangles = area-name banners, a point named `spawn` = start position
Writes game/public/maps/main.json (+ main.meta.json, minimap.png), game/public/tiles/campus.png, game/public/props/*.png
and data/debug/game_render.png (the whole map as the game draws it), game_collision.png (red = blocked).
Usage (repo root): python3 tools/v4/tiled_to_game.py [tiled/maps/phase1.tmj]
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tiled_kit                                   # terrain colours + paint(), shared with the Tiled tiles

T = 16
SMOOTH = 7                                         # px: how strongly terrain outlines are rounded (0 = exactly as in Tiled)
SRC = sys.argv[1] if len(sys.argv) > 1 else 'tiled/maps/phase1.tmj'
OUT = 'game/public'
os.makedirs(f'{OUT}/props', exist_ok=True)
FLIP_H, FLIP_V, FLIP_D = 0x80000000, 0x40000000, 0x20000000

M = json.load(open(SRC))
base_dir = os.path.dirname(SRC)
MW, MH = M['width'], M['height']
W, H = MW * T, MH * T

# ---------------------------------------------------------------- tilesets
tilesets = []
for ref in M['tilesets']:
    ts = json.load(open(os.path.join(base_dir, ref['source']))) if 'source' in ref else ref
    ts_dir = os.path.dirname(os.path.join(base_dir, ref['source'])) if 'source' in ref else base_dir
    entry = {'first': ref['firstgid'], 'ts': ts, 'props': {}, 'anim': {}, 'images': {}, 'wang': {}}
    for ws in ts.get('wangsets', []):                  # terrain brushes: tile id -> (kind, TL, TR, BL, BR corner is terrain)
        if ws.get('type', 'corner') != 'corner':       # edge sets (exterior.tsj: pavers, hedge pieces) are ordinary tiles
            continue
        kind = ws['name'].split(' ')[0].lower()        # Road, Path, Hedge, Garden lawn
        entry['grass'] = ws['colors'][0]['tile']
        for wt in ws['wangtiles']:                     # wangid = [top, top-right, right, bottom-right, bottom, bottom-left, left, top-left]
            wid = wt['wangid']
            entry['wang'][wt['tileid']] = (kind, wid[7] == 2, wid[1] == 2, wid[5] == 2, wid[3] == 2)
    for t in ts.get('tiles', []):
        entry['props'][t['id']] = {p['name']: p['value'] for p in t.get('properties', [])}
        if 'animation' in t:
            entry['anim'][t['id']] = [a['tileid'] for a in t['animation']]
        if 'image' in t:
            entry['images'][t['id']] = np.array(Image.open(os.path.join(ts_dir, t['image'])).convert('RGBA'))
    if 'image' in ts:
        entry['atlas'] = np.array(Image.open(os.path.join(ts_dir, ts['image'])).convert('RGBA'))
    tilesets.append(entry)
tilesets.sort(key=lambda e: e['first'])


def lookup(gid):
    g = gid & 0x1FFFFFFF
    e = None
    for cand in tilesets:
        if cand['first'] <= g:
            e = cand
    return e, g - e['first']


def tile_rgba(gid):
    e, tid = lookup(gid)
    if 'atlas' in e:
        cols = e['ts']['columns']
        a = e['atlas'][(tid // cols) * T:(tid // cols + 1) * T, (tid % cols) * T:(tid % cols + 1) * T].copy()
    else:
        a = e['images'][tid].copy()
    if gid & FLIP_D: a = a.transpose(1, 0, 2)
    if gid & FLIP_H: a = a[:, ::-1]
    if gid & FLIP_V: a = a[::-1]
    return a


def props_of(gid):
    e, tid = lookup(gid)
    return e['props'].get(tid, {})


def blend(dst, src, x, y):
    h, w = src.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    al = s[..., 3:4] > 0
    dst[y0:y1, x0:x1, :3] = np.where(al, s[..., :3], dst[y0:y1, x0:x1, :3])
    if dst.shape[2] == 4:
        dst[y0:y1, x0:x1, 3] = np.where(al[..., 0], 255, dst[y0:y1, x0:x1, 3])


layers = {l['name'].split(' ')[0]: l for l in M['layers']}
C = 4
solid = np.zeros((H, W), bool)
base = np.zeros((H, W, 4), np.uint8); base[..., 3] = 255
above = np.zeros((H, W, 4), np.uint8)
tall_tiles = []
late_tiles = []                                  # decor tiles: drawn after the terrain is repainted (a kerb covers the road's edge)
corners = {}                                     # terrain kind -> which tile corners it covers, bool (MH + 1, MW + 1)

# ---------------------------------------------------------------- tile layers
for lname, target in (('ground', base), ('decor', base), ('above', above)):
    L = layers.get(lname)
    if not L or L.get('type') != 'tilelayer':
        continue
    for i, gid in enumerate(L['data']):
        if not gid:
            continue
        tx, ty = i % MW, i // MW
        e, tid = lookup(gid)
        if SMOOTH and lname != 'above' and gid < FLIP_D and tid in e['wang']:
            # a terrain-brush tile: note its corners and lay plain grass; the terrain is painted on smoothed outlines below
            kind, tl, tr, bl, br = e['wang'][tid]
            c = corners.setdefault(kind, np.zeros((MH + 1, MW + 1), bool))
            c[ty, tx] |= tl; c[ty, tx + 1] |= tr; c[ty + 1, tx] |= bl; c[ty + 1, tx + 1] |= br
            blend(target, tile_rgba(e['first'] + e['grass']), tx * T, ty * T)
            continue
        if lname == 'decor':
            late_tiles.append((gid, tx, ty))
        else:
            img_ = tile_rgba(gid)                      # tiles taller than the grid (tree canopies) are anchored bottom-left, as in Tiled
            blend(target, img_, tx * T, (ty + 1) * T - img_.shape[0])
        pr = props_of(gid)
        if lname != 'above' and pr.get('solid'):
            solid[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T] = True
        if pr.get('tallgrass'):
            tall_tiles.append((tx, ty, gid))


# ---------------------------------------------------------------- object layers
def placeholder(w, h, kind):
    a = np.zeros((h, w, 4), np.uint8)
    a[..., :3] = {'bhawan': (214, 196, 160), 'mess': (206, 190, 170), 'nab': (210, 204, 170)}.get(kind, (200, 196, 184)); a[..., 3] = 255
    a[:3], a[-3:], a[:, :3], a[:, -3:] = (212, 142, 110, 255), (212, 142, 110, 255), (212, 142, 110, 255), (212, 142, 110, 255)
    wall = min(32, h // 3)
    a[-wall:-3, 3:-3, :3] = (238, 229, 182)
    for x in range(8, w - 8, 12):
        a[-wall + 8:-wall + 18, x:x + 6, :3] = (48, 46, 72)
    return a


def obj_kind(o):
    return o.get('class') or o.get('type') or ''


anim_flags = []
upright = []                                     # (prop name, rgba, x, y): sprites the player can walk behind
drawables = []                                   # (sort key, rgba, x, y)
hedges = []                                      # (points, width in px): hedge polylines
shapes = []                                      # (class, points, properties): paving / flowerbed polygons, roadline polylines
grass_rects = []                                 # [x0, y0, x1, y1]: ground that rustles underfoot (flat props marked `tallgrass`)
for lname in ('buildings', 'props'):
    L = layers.get(lname)
    if not L:
        continue
    for o in L.get('objects', []):
        if not o.get('visible', True):
            continue
        if 'polyline' in o and obj_kind(o) == 'hedge':
            pts = [(o['x'] + p['x'], o['y'] + p['y']) for p in o['polyline']]
            hedges.append((pts, next((p['value'] for p in o.get('properties', []) if p['name'] == 'width'), 17)))
        elif obj_kind(o) in ('paving', 'flowerbed', 'roadline') and ('polygon' in o or 'polyline' in o):
            pts = [(o['x'] + p['x'], o['y'] + p['y']) for p in o.get('polygon') or o['polyline']]
            shapes.append((obj_kind(o), pts, {p['name']: p['value'] for p in o.get('properties', [])}))
        elif 'gid' in o:
            img = tile_rgba(o['gid'])
            w, h = int(round(o.get('width') or img.shape[1])), int(round(o.get('height') or img.shape[0]))
            if (w, h) != (img.shape[1], img.shape[0]):
                img = np.array(Image.fromarray(img).resize((w, h), Image.NEAREST))
            x, y = int(round(o['x'])), int(round(o['y'])) - h      # tile objects are anchored bottom-left
            pr = props_of(o['gid'])
            if pr.get('anim') == 'flag':
                anim_flags.append((img, x, y))
            elif lname == 'props' and not pr.get('flat'):
                upright.append((pr.get('prop', 'prop'), img, x, y))
            else:
                key = (0, len(drawables)) if L.get('draworder') == 'index' else (1, y + h)
                drawables.append((key, img, x, y))
                if pr.get('tallgrass'):                      # a grass patch: every tile-sized cell it mostly covers rustles
                    for by in range(0, h, T):
                        for bx in range(0, w, T):
                            if (img[by:by + T, bx:bx + T, 3] > 0).mean() > 0.5:
                                grass_rects.append([x + bx, y + by, x + min(bx + T, w), y + min(by + T, h)])
            if lname == 'buildings':
                e_, tid_ = lookup(o['gid'])
                cpath = e_['props'].get(tid_, {}).get('collision')
                if cpath:
                    ts_dir = os.path.dirname(os.path.join(base_dir, next(r['source'] for r in M['tilesets'] if r['firstgid'] == e_['first'])))
                    cm = np.array(Image.open(os.path.normpath(os.path.join(ts_dir, cpath))).convert('RGBA'))[..., 3] > 0
                    if cm.shape != img.shape[:2]:
                        cm = np.array(Image.fromarray(cm).resize((img.shape[1], img.shape[0]), Image.NEAREST))
                    if o['gid'] & FLIP_H: cm = cm[:, ::-1]
                    if o['gid'] & FLIP_V: cm = cm[::-1]
                    m = cm
                else:
                    m = img[..., 3] > 0
                ys, xs = np.nonzero(m)
                sub = solid[max(0, y):y + h, max(0, x):x + w]
                mm = m[max(0, -y):max(0, -y) + sub.shape[0], max(0, -x):max(0, -x) + sub.shape[1]]
                sub |= mm
            elif 'collision_w' in pr:                    # an exact collision box in the tile's properties (trees.tsj, street props)
                cx_, cy_, cw_, ch_ = (int(pr.get(k_, 0)) for k_ in ('collision_x', 'collision_y', 'collision_w', 'collision_h'))
                if o['gid'] & FLIP_H:
                    cx_ = img.shape[1] - cx_ - cw_
                solid[max(0, y + cy_):max(0, y + cy_ + ch_), max(0, x + cx_):max(0, x + cx_ + cw_)] = True
            elif pr.get('solid_base') or pr.get('anim') == 'flag':
                # the base blocks: a third of the width and 6 px deep, or the tile's base_w / base_h fractions (wide bushes)
                bw, bh = max(4, int(w * pr.get('base_w', 1 / 3))), max(6, int(h * pr.get('base_h', 0)))
                solid[max(0, y + h - bh):y + h, max(0, x + w // 2 - bw // 2):x + w // 2 + bw // 2] = True
        elif obj_kind(o) == 'slot' or lname == 'buildings':
            x, y, w, h = (int(round(o[k])) for k in ('x', 'y', 'width', 'height'))
            kind = next((p['value'] for p in o.get('properties', []) if p['name'] == 'type'), 'small')
            drawables.append(((0, -1e9 + y + h), placeholder(w, h, kind), x, y))
            solid[max(0, y):y + h, max(0, x):x + w] = True


# ---------------------------------------------------------------- terrain, repainted on smoothed outlines
def outline(c):
    """tile-corner grid -> pixel mask: the shapes the terrain tiles draw in Tiled, with their outline rounded by SMOOTH px"""
    up = np.array(Image.fromarray(c.astype(np.uint8) * 255).resize(((MW + 1) * T, (MH + 1) * T), Image.BILINEAR))
    m = Image.fromarray((up[T // 2:T // 2 + H, T // 2:T // 2 + W] > 127).astype(np.uint8) * 255)
    return np.array(m.filter(ImageFilter.GaussianBlur(SMOOTH))) > 127


def edge_dist(m, n_in=3, n_out=2):
    """signed distance to the outline in px (+ inside); exact for the first few px, which is all the kerb/rim rings use"""
    def shrink(a):
        p = np.pad(a, 1, mode='edge')
        return a & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    d = np.where(m, 99.0, -99.0).astype(np.float32)
    for sign, cur, n in ((1, m, n_in), (-1, ~m, n_out)):
        for k in range(n):
            nxt = shrink(cur)
            d[cur & ~nxt] = sign * (k + 0.5)
            cur = nxt
    return d


def across(m):
    """for each hedge pixel: 0 on the hedge's sunlit side .. 1 on its shaded side. Measured top-down, or left-right
    where the hedge runs north-south (a vertical run of more than 30 px)"""
    def run(a):                                    # position in the vertical run of set pixels, and the run's length
        up, dn = np.zeros(a.shape, np.int32), np.zeros(a.shape, np.int32)
        up[0], dn[-1] = a[0], a[-1]
        for y in range(1, a.shape[0]):
            up[y] = (up[y - 1] + 1) * a[y]
        for y in range(a.shape[0] - 2, -1, -1):
            dn[y] = (dn[y + 1] + 1) * a[y]
        n = up + dn - 1
        return (up - 0.5) / np.maximum(n, 1), n
    fv, nv = run(m)
    fh, _ = run(m.T)
    return np.where(nv > 30, fh.T, fv)


def draw_hedge(rgb, pts, width):
    """one hedge polyline, drawn like the hedges of the user's art: a dark line along the top, a sunlit band, a shaded
    band under a ragged leaf line, and a soft shadow on the ground below. Returns (mask of the hedge, its y0, x0)."""
    r = width / 2
    P_ = np.array(pts, float)
    x0, y0 = max(0, int(P_[:, 0].min() - r - 4)), max(0, int(P_[:, 1].min() - r - 4))
    x1, y1 = min(W, int(P_[:, 0].max() + r + 5)), min(H, int(P_[:, 1].max() + r + 5))
    py, px = np.mgrid[y0:y1, x0:x1] + 0.5
    seg = np.diff(P_, axis=0)
    seg_len = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0], np.cumsum(seg_len)])
    # the sunlit side is the one facing up (and a little left, for hedges that run north-south)
    nx, ny = (seg[:, 1] / seg_len * seg_len).sum(), (-seg[:, 0] / seg_len * seg_len).sum()
    flip = 1.0 if nx * -0.35 + ny * -1.0 > 0 else -1.0
    best = np.full(px.shape, 1e9); off = np.zeros(px.shape); s = np.zeros(px.shape)
    for i, ((ax, ay), (dx, dy), L) in enumerate(zip(P_[:-1], seg, seg_len)):
        if L == 0:
            continue
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / (L * L), 0, 1)
        d = np.hypot(px - ax - t * dx, py - ay - t * dy)
        near = d < best
        best[near] = d[near]
        off[near] = (((px - ax) * dy - (py - ay) * dx) / L)[near]         # + towards the left of the direction of travel
        s[near] = (cum[i] + t * L)[near]
    v = r - flip * off                                                    # 0 at the sunlit edge .. width at the shaded edge
    si = s.astype(int)
    notch = ((si // 2 * 7 + si // 5 * 3) % 9 == 0) & (v < r)              # a few 1 px dents along the top: leaves, not a pipe
    inside = best <= r - np.where(notch, 1.0, 0.0)
    tooth = np.abs((s % 5) - 2.5) - 1 + ((si // 3 * 5) % 3 == 0)          # the ragged line between light and shade
    lit = inside & (v < 0.56 * width + tooth)
    hsh = si * 7 + v.astype(int) * 13
    out = rgb[y0:y1, x0:x1]
    shadow = ~inside & (best <= r + 2.5) & (v > width - 2)                 # ground just below the hedge
    out[shadow] = (out[shadow] * 0.8).astype(np.uint8)
    out[inside] = tiled_kit.HEDGE_SHADE
    out[inside & ~lit & (hsh % 11 == 0)] = tiled_kit.HEDGE_SHADE_HI
    out[lit] = tiled_kit.HEDGE_LIT
    out[lit & (hsh % 13 == 0)] = tiled_kit.HEDGE_LIT_HI
    out[lit & (hsh % 17 == 3)] = tiled_kit.HEDGE_LIT_DK
    out[inside & (best > r - 1.3) & (v >= r)] = tiled_kit.HEDGE_OL        # lower rim
    out[inside & (best > r - 1.3) & (v < r)] = tiled_kit.HEDGE_OL_DARK    # the dark line along the top
    return inside, y0, x0


# ---------------------------------------------------------------- paving, flower beds, road markings
PAVE = np.array([230, 206, 182]); PAVE_LT = np.array([238, 218, 196]); PAVE_JOINT = np.array([206, 196, 190])
PAVE_RIM = np.array([168, 172, 178]); KERB_W = np.array([238, 236, 228])
LEAF = np.array([[47, 96, 30], [76, 130, 46], [110, 168, 60]])
BLOOM = np.array([[200, 44, 72], [170, 60, 130], [214, 104, 168], [226, 70, 96]])
BLOOM_HI = np.array([244, 170, 204])


def poly_mask(pts):
    x0, y0 = max(0, int(min(p[0] for p in pts)) - 4), max(0, int(min(p[1] for p in pts)) - 4)
    x1, y1 = min(W, int(max(p[0] for p in pts)) + 5), min(H, int(max(p[1] for p in pts)) + 5)
    im = Image.new('L', (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in pts], fill=255)
    return np.array(im) > 0, y0, x0


def hash2(a, b, k=0):
    """deterministic per-cell noise in 0..1"""
    return ((a * 73856093 ^ b * 19349663 ^ k * 83492791) & 0xFFFF) / 65535.0


def draw_paving(rgb, pts, props, road=None):
    m, y0, x0 = poly_mask(pts)
    h, w = m.shape
    yy_, xx_ = np.mgrid[y0:y0 + h, x0:x0 + w]
    if 'cx' in props and 'cy' in props:                # slabs in rings around the Rotunda, like its own floor
        dx, dy = xx_ - props['cx'], yy_ - props['cy']
        r = np.hypot(dx, dy); ring = (r // 12).astype(int)
        seg = ((np.arctan2(dy, dx) + math.pi) * (r + 1e-6) // 14).astype(int)
        joint = (r % 12 < 1) | (((np.arctan2(dy, dx) + math.pi) * r) % 14 < 1)
    else:
        ring, seg = yy_ // 12, (xx_ + 6 * ((yy_ // 12) % 2)) // 14
        joint = (yy_ % 12 == 0) | ((xx_ + 6 * ((yy_ // 12) % 2)) % 14 == 0)
    tone = hash2(ring, seg, 7) < 0.18                 # a few lighter slabs, scattered
    out = rgb[y0:y0 + h, x0:x0 + w]
    inset = int(props.get('road_inset', 0))
    if inset:                                          # the polygon's outer `road_inset` px are asphalt: a clean kerb line
        core = np.array(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(2 * inset + 1))) > 0
        band = m & ~core                               # wherever the smoothed road outline falls short of it
        if road is not None:                           # ... only beside a road; elsewhere the paving keeps its edge
            near = np.array(Image.fromarray(road[y0:y0 + h, x0:x0 + w].astype(np.uint8) * 255)
                            .filter(ImageFilter.MaxFilter(2 * inset + 7))) > 0
            core |= band & ~near
            band &= near
        asph = out.copy()
        tiled_kit.paint('road', asph, np.full(m.shape, 99.0), xx_, yy_)
        out[band] = asph[band]
        m = core
    d = edge_dist(m)
    out[m] = PAVE
    out[m & tone] = PAVE_LT
    out[m & joint] = PAVE_JOINT
    out[m & (d < 2.2)] = KERB_W                          # a white stone kerb all round, with a grey line inside it
    out[m & (d < 1.2)] = PAVE_RIM


def draw_flowerbed(rgb, pts):
    """a bed packed with bougainvillea: dark leaves, clumps of red / magenta / pink bracts, inside a stone kerb"""
    m, y0, x0 = poly_mask(pts)
    h, w = m.shape
    yy_, xx_ = np.mgrid[y0:y0 + h, x0:x0 + w]
    d = edge_dist(m, n_in=5)
    out = rgb[y0:y0 + h, x0:x0 + w]
    leaf = LEAF[np.where((xx_ * 5 + yy_ * 3) % 7 == 0, 2, ((xx_ * 3 + yy_ * 7) % 11 == 0).astype(int))]
    col = leaf.copy()
    # bloom clumps on a jittered 6 px grid: radius 2-3 px, each in one colour with a highlight at its top-left
    gx, gy = xx_ // 6, yy_ // 6
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx_, cy_ = gx + ox, gy + oy
            px = cx_ * 6 + (hash2(cx_, cy_, 1) * 6).astype(int)
            py = cy_ * 6 + (hash2(cx_, cy_, 2) * 6).astype(int)
            rr = 2 + (hash2(cx_, cy_, 3) > 0.45)
            on = ((xx_ - px) ** 2 + (yy_ - py) ** 2 <= rr * rr) & (hash2(cx_, cy_, 4) < 0.85)
            k = (hash2(cx_, cy_, 5) * len(BLOOM)).astype(int)
            col[on] = BLOOM[k[on]]
            hi = on & (xx_ - px == -1) & (yy_ - py == -1)
            col[hi] = BLOOM_HI
    out[m] = col[m]
    out[m & (d < 4.2) & (d >= 2.2)] = LEAF[0]            # the leaves darken towards the kerb
    out[m & (d < 2.2)] = KERB_W
    out[m & (d < 1.2)] = PAVE_RIM
    return m, y0, x0


def draw_roadline(rgb, pts, dash=8, gap=8):
    """dashed centre line, 2 px wide, dashes measured along the line"""
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    run, on = 0.0, True
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L_ = math.hypot(bx - ax, by - ay); t = 0.0
        while t < L_:
            step = min((dash if on else gap) - run, L_ - t)
            if on:
                f0, f1 = t / L_, (t + step) / L_
                dr.line([(ax + (bx - ax) * f0, ay + (by - ay) * f0), (ax + (bx - ax) * f1, ay + (by - ay) * f1)], fill=255, width=2)
            t += step; run += step
            if run >= (dash if on else gap) - 1e-6:
                run, on = 0.0, not on
    m = np.array(im) > 0
    rgb[m] = KERB_W


if corners or hedges or shapes:
    rgb = base[..., :3]
    yy, xx = np.mgrid[0:H, 0:W] % T                # texture phase repeats per tile, as in the Tiled tiles
    none = np.zeros((MH + 1, MW + 1), bool)
    masks = {}
    for kind in ('garden', 'road', 'path', 'hedge'):
        c = corners.get(kind, none)
        if kind == 'path':                         # paths run on under the road, so they meet it without a gap
            c = c | corners.get('road', none)
        m = outline(c) if c.any() else np.zeros((H, W), bool)
        masks[kind] = m
        if not m.any():
            continue
        if kind == 'path':
            layer = rgb.copy()
            tiled_kit.paint(kind, layer, edge_dist(m), xx, yy)
            keep = m & ~masks['road']
            rgb[keep] = layer[keep]
        else:
            tiled_kit.paint(kind, rgb, edge_dist(m), xx, yy, top=across(m) if kind == 'hedge' else None)
    solid |= masks['hedge']
    for kind, pts, props in shapes:                    # paving, then the beds, then the markings
        if kind == 'paving':
            draw_paving(rgb, pts, props, masks['road'])
    for kind, pts, props in shapes:
        if kind == 'flowerbed':
            m, by_, bx_ = draw_flowerbed(rgb, pts)
            solid[by_:by_ + m.shape[0], bx_:bx_ + m.shape[1]] |= m
    for kind, pts, props in shapes:
        if kind == 'roadline':
            draw_roadline(rgb, pts)
    for pts, width in hedges:
        m, hy, hx = draw_hedge(rgb, pts, width)
        solid[hy:hy + m.shape[0], hx:hx + m.shape[1]] |= m
    base[..., :3] = np.array(Image.fromarray(rgb).quantize(palette=tiled_kit.PAL_IMG, dither=Image.Dither.NONE).convert('RGB'))

for gid, tx, ty in late_tiles:                    # painted decor (footpaths, kerbs, hedge tiles) lies on top of the terrain
    img_ = tile_rgba(gid)
    blend(base, img_, tx * T, (ty + 1) * T - img_.shape[0])

# shadows layer (tools/v4/beautify.py): ellipse objects with an `opacity` property darken the ground under them (tree
# shadows, dappled shade, darker grass patches). Overlaps add up; every darkened pixel is snapped back to the locked
# palette, so the map stays palette-only. Hard edges, no anti-aliasing.
L_sh = layers.get('shadows')
if L_sh and L_sh.get('objects'):
    keep_dark = np.ones((H, W), np.float32)
    for o in L_sh['objects']:
        if not o.get('visible', True):
            continue
        op = float(next((p_['value'] for p_ in o.get('properties', []) if p_['name'] == 'opacity'), 0.25))
        x0_, y0_ = int(round(o['x'])), int(round(o['y']))
        w_, h_ = max(1, int(round(o['width']))), max(1, int(round(o['height'])))
        m_ = Image.new('L', (w_, h_), 0)
        ImageDraw.Draw(m_).ellipse((0, 0, w_ - 1, h_ - 1), fill=255)
        m_ = np.array(m_) > 0
        sub = keep_dark[max(0, y0_):y0_ + h_, max(0, x0_):x0_ + w_]
        mm = m_[max(0, -y0_):max(0, -y0_) + sub.shape[0], max(0, -x0_):max(0, -x0_) + sub.shape[1]]
        sub[mm] *= (1 - op)
    dk = keep_dark < 0.999
    if dk.any():
        pal_ = np.array(tiled_kit.PAL_IMG.getpalette()[:384], np.int32).reshape(-1, 3)
        want = (base[..., :3][dk].astype(np.float32) * keep_dark[dk][:, None]).round().astype(np.int32)
        uq, inv = np.unique(want, axis=0, return_inverse=True)
        snapped = pal_[np.argmin(((uq[:, None, :] - pal_[None, :, :]) ** 2).sum(axis=2), axis=1)]
        base[..., :3][dk] = snapped[inv.ravel()].astype(np.uint8)
for _, img, x, y in sorted(drawables, key=lambda d: d[0]):
    blend(base, img, x, y)

L = layers.get('collision')
for o in (L or {}).get('objects', []):
    x, y, w, h = (int(round(o.get(k, 0))) for k in ('x', 'y', 'width', 'height'))
    solid[max(0, y):y + h, max(0, x):x + w] = True

zones, spawn = [], {'x': W // 2, 'y': H // 2}
for o in (layers.get('events') or {}).get('objects', []):
    k = obj_kind(o)
    if o.get('name') == 'spawn' or k == 'spawn':
        spawn = {'x': int(o['x']), 'y': int(o['y'])}
    elif k == 'zone' and o.get('name'):
        zones.append({'name': o['name'], 'x': int(o['x']), 'y': int(o['y']), 'w': int(o['width']), 'h': int(o['height']),
                      'p': 0 if o['width'] * o['height'] < 40000 else 1})


# ---------------------------------------------------------------- animations (flags wave, tall grass sways)
def flag_frames(rgba, n=4):
    h, w = rgba.shape[:2]
    a_ = rgba[..., 3] > 0
    rgb = rgba[..., :3].astype(int)
    grey = (np.abs(rgb[..., 0] - rgb[..., 1]) < 18) & (np.abs(rgb[..., 1] - rgb[..., 2]) < 22)
    pole_x = int(np.argmax((a_ & grey).sum(axis=0)))
    out = []
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
        out.append(fr)
    return out


anims, anim_props, first_frame = {}, [], {}


def save_anim(key, frames, fps):
    h = max(f.shape[0] for f in frames); w = max(f.shape[1] for f in frames)
    strip = np.zeros((h, w * len(frames), 4), np.uint8)
    for i, f in enumerate(frames):
        strip[:f.shape[0], i * w:i * w + f.shape[1]] = f
    Image.fromarray(strip).save(f'{OUT}/props/{key}.png')
    anims[key] = {'w': w, 'h': h, 'frames': len(frames), 'fps': fps}
    first_frame[key] = frames[0]


for i, (img, x, y) in enumerate(anim_flags):
    save_anim(f'flag_{i}', flag_frames(img), 8)
    anim_props.append({'k': f'flag_{i}', 'x': x, 'y': y, 'depth': y + img.shape[0]})
sprite_keys = {}                                 # upright props: one single-frame sprite per distinct image, sorted by base y
for name, img, x, y in upright:
    key = sprite_keys.setdefault((img.shape, img.tobytes()), f'{name}_{len(sprite_keys)}')
    if key not in anims:
        save_anim(key, [img], 1)
    anim_props.append({'k': key, 'x': x, 'y': y, 'depth': y + img.shape[0]})
tall_rects = list(grass_rects)
if tall_tiles:
    e, tid = lookup(tall_tiles[0][2])
    frames_ids = e['anim'].get(tid, [tid])
    frames = [tile_rgba(e['first'] + f) for f in frames_ids]
    save_anim('tallgrass', frames, 2)
    for tx, ty, _ in tall_tiles:
        anim_props.append({'k': 'tallgrass', 'x': tx * T, 'y': ty * T, 'depth': -0.5})
        tall_rects.append([tx * T, ty * T, tx * T + T, ty * T + T])
# rustle sprite (blades flick around the feet)
rustle = []
for spread in (0, 2, 1):
    fr = np.zeros((12, 18, 4), np.uint8)
    for bx, lean in ((4, -1), (9, 0), (14, 1)):
        for t_ in range(7):
            xx = int(round(bx + lean * spread * t_ / 6)); yy = 11 - t_
            for x2, c in ((xx, (168, 224, 96)), (xx + 1, (60, 140, 60))):
                if 0 <= x2 < 18: fr[yy, x2] = (*c, 255)
    rustle.append(fr)
save_anim('rustle', rustle, 10)

# ---------------------------------------------------------------- tiles + Tiled-format game map
tiles, index = [], {}
def tile_id(px):
    key = px.tobytes()
    if key not in index:
        index[key] = len(tiles); tiles.append(px)
    return index[key] + 1
g_data = [tile_id(base[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]) for ty in range(MH) for tx in range(MW)]
a_data = []
has_above = above[..., 3].any()
if has_above:
    for ty in range(MH):
        for tx in range(MW):
            px = above[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]
            a_data.append(tile_id(px) if px[..., 3].any() else 0)
COLS = 32
rows = math.ceil(len(tiles) / COLS)
sheet = np.zeros((rows * T, COLS * T, 4), np.uint8)
for i, tl in enumerate(tiles):
    sheet[(i // COLS) * T:(i // COLS + 1) * T, (i % COLS) * T:(i % COLS + 1) * T] = tl
Image.fromarray(sheet).save(f'{OUT}/tiles/campus.png')
game_layers = [{'id': 1, 'name': 'ground', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': MW, 'height': MH, 'opacity': 1, 'visible': True, 'data': g_data}]
if has_above:
    game_layers.append({'id': 2, 'name': 'above', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': MW, 'height': MH, 'opacity': 1, 'visible': True, 'data': a_data})
json.dump({'type': 'map', 'version': '1.10', 'tiledversion': '1.10.2', 'orientation': 'orthogonal', 'renderorder': 'right-down',
           'infinite': False, 'width': MW, 'height': MH, 'tilewidth': T, 'tileheight': T, 'nextlayerid': 3, 'nextobjectid': 1,
           'layers': game_layers,
           'tilesets': [{'firstgid': 1, 'name': 'campus', 'image': '../tiles/campus.png', 'imagewidth': COLS * T, 'imageheight': rows * T,
                         'tilewidth': T, 'tileheight': T, 'tilecount': len(tiles), 'columns': COLS, 'margin': 0, 'spacing': 0}]},
          open(f'{OUT}/maps/main.json', 'w'))
solid[:, :T // 2] = solid[:, -T // 2:] = True
solid[:T // 2, :] = solid[-T // 2:, :] = True
grid = solid.reshape(H // C, C, W // C, C).mean(axis=(1, 3)) > 0.2     # 4 px cells: solid from a quarter covered, so
# 2-3 px walls (the Rotunda's low walls at 0.7 scale) always block, yet a 24 px stair path between two of them stays open
sx, sy = spawn['x'] // C, spawn['y'] // C
if grid[min(sy, grid.shape[0] - 1), min(sx, grid.shape[1] - 1)]:
    free = np.argwhere(~grid)
    j = np.argmin(((free[:, 0] - sy) ** 2 + (free[:, 1] - sx) ** 2))
    spawn = {'x': int(free[j][1] * C + C // 2), 'y': int(free[j][0] * C + C - 1)}
    print('note: spawn was inside a wall; moved to the nearest free spot', spawn)
json.dump({'props': [], 'frames': {}, 'anims': anims, 'animProps': anim_props, 'tallgrass': tall_rects,
           'collision': {'cell': C, 'w': W // C, 'h': H // C, 'data': ''.join('1' if v else '0' for v in grid.ravel())},
           'zones': zones, 'spawn': spawn, 'width': W, 'height': H}, open(f'{OUT}/maps/main.meta.json', 'w'))
full = base.copy()                               # the map as the game draws it: ground + sprites (first frames) + above layer
for p in sorted(anim_props, key=lambda p: p['depth']):
    blend(full, first_frame[p['k']], p['x'], p['y'])
blend(full, above, 0, 0)
Image.fromarray(full[..., :3]).resize((W // 8, H // 8), Image.BOX).save(f'{OUT}/maps/minimap.png')
os.makedirs('data/debug', exist_ok=True)
Image.fromarray(full[..., :3]).save('data/debug/game_render.png')
dbg = full[..., :3].copy()
big = np.kron(grid, np.ones((C, C), bool))
dbg[big] = (dbg[big] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)
Image.fromarray(dbg).save('data/debug/game_collision.png')
print(f'{MW}x{MH} tiles -> {len(tiles)} unique game tiles; {len(anim_flags)} flags, {len(upright)} upright props, '
      f'{len(hedges)} hedges, {len(shapes)} paving/bed/line shapes, {len(tall_tiles)} tall-grass tiles + {len(grass_rects)} grass-patch cells, {len(zones)} zones, above layer: {bool(has_above)}, spawn {spawn}')
