"""Tiled map -> playable game. Reads the Tiled JSON only; never modifies any art or map file.

What it reads (tiled/maps/<area>.tmj):
  ground, decor (tile layers)   painted tiles; tile property `solid` blocks, `tallgrass` rustles + sways
  above (tile layer)            drawn OVER the player (tree canopies, roof edges)
  buildings (objects)           building stamps (blocked where opaque); `slot` rectangles become placeholder blocks
  props (objects)               flags (wave), lamps, palms, bushes, trees (base blocks)
  collision (objects)           any rectangle = blocked
  events (objects)              `zone` rectangles = area-name banners, a point named `spawn` = start position
Writes game/public/maps/main.json (+ main.meta.json, minimap.png), game/public/tiles/campus.png, game/public/props/*.png
Usage (repo root): python3 tools/v4/tiled_to_game.py [tiled/maps/phase1.tmj]
"""
import json, math, os, sys
import numpy as np
from PIL import Image

T = 16
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
    entry = {'first': ref['firstgid'], 'ts': ts, 'props': {}, 'anim': {}, 'images': {}}
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
C = 8
solid = np.zeros((H, W), bool)
base = np.zeros((H, W, 4), np.uint8); base[..., 3] = 255
above = np.zeros((H, W, 4), np.uint8)
tall_tiles = []

# ---------------------------------------------------------------- tile layers
for lname, target in (('ground', base), ('decor', base), ('above', above)):
    L = layers.get(lname)
    if not L or L.get('type') != 'tilelayer':
        continue
    for i, gid in enumerate(L['data']):
        if not gid:
            continue
        tx, ty = i % MW, i // MW
        blend(target, tile_rgba(gid), tx * T, ty * T)
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
drawables = []                                   # (sort key, rgba, x, y)
for lname in ('buildings', 'props'):
    L = layers.get(lname)
    if not L:
        continue
    for o in L.get('objects', []):
        if not o.get('visible', True):
            continue
        if 'gid' in o:
            img = tile_rgba(o['gid'])
            w, h = int(round(o.get('width') or img.shape[1])), int(round(o.get('height') or img.shape[0]))
            if (w, h) != (img.shape[1], img.shape[0]):
                img = np.array(Image.fromarray(img).resize((w, h), Image.NEAREST))
            x, y = int(round(o['x'])), int(round(o['y'])) - h      # tile objects are anchored bottom-left
            pr = props_of(o['gid'])
            if pr.get('anim') == 'flag':
                anim_flags.append((img, x, y))
            else:
                key = (0, len(drawables)) if L.get('draworder') == 'index' else (1, y + h)
                drawables.append((key, img, x, y))
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
            elif pr.get('solid_base') or pr.get('anim') == 'flag':
                bw = max(4, w // 3)
                solid[max(0, y + h - 6):y + h, max(0, x + w // 2 - bw // 2):x + w // 2 + bw // 2] = True
        elif obj_kind(o) == 'slot' or lname == 'buildings':
            x, y, w, h = (int(round(o[k])) for k in ('x', 'y', 'width', 'height'))
            kind = next((p['value'] for p in o.get('properties', []) if p['name'] == 'type'), 'small')
            drawables.append(((0, -1e9 + y + h), placeholder(w, h, kind), x, y))
            solid[max(0, y):y + h, max(0, x):x + w] = True
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


anims, anim_props = {}, []


def save_anim(key, frames, fps):
    h = max(f.shape[0] for f in frames); w = max(f.shape[1] for f in frames)
    strip = np.zeros((h, w * len(frames), 4), np.uint8)
    for i, f in enumerate(frames):
        strip[:f.shape[0], i * w:i * w + f.shape[1]] = f
    Image.fromarray(strip).save(f'{OUT}/props/{key}.png')
    anims[key] = {'w': w, 'h': h, 'frames': len(frames), 'fps': fps}


for i, (img, x, y) in enumerate(anim_flags):
    save_anim(f'flag_{i}', flag_frames(img), 8)
    anim_props.append({'k': f'flag_{i}', 'x': x, 'y': y, 'depth': y + img.shape[0]})
tall_rects = []
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
grid = solid.reshape(H // C, C, W // C, C).mean(axis=(1, 3)) > 0.4
sx, sy = spawn['x'] // C, spawn['y'] // C
if grid[min(sy, grid.shape[0] - 1), min(sx, grid.shape[1] - 1)]:
    free = np.argwhere(~grid)
    j = np.argmin(((free[:, 0] - sy) ** 2 + (free[:, 1] - sx) ** 2))
    spawn = {'x': int(free[j][1] * C + C // 2), 'y': int(free[j][0] * C + C - 1)}
    print('note: spawn was inside a wall; moved to the nearest free spot', spawn)
json.dump({'props': [], 'frames': {}, 'anims': anims, 'animProps': anim_props, 'tallgrass': tall_rects,
           'collision': {'cell': C, 'w': W // C, 'h': H // C, 'data': ''.join('1' if v else '0' for v in grid.ravel())},
           'zones': zones, 'spawn': spawn, 'width': W, 'height': H}, open(f'{OUT}/maps/main.meta.json', 'w'))
Image.fromarray(base[..., :3]).resize((W // 8, H // 8), Image.BOX).save(f'{OUT}/maps/minimap.png')
dbg = base[..., :3].copy()
big = np.kron(grid, np.ones((C, C), bool))
dbg[big] = (dbg[big] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)
os.makedirs('data/debug', exist_ok=True)
Image.fromarray(dbg).save('data/debug/game_collision.png')
print(f'{MW}x{MH} tiles -> {len(tiles)} unique game tiles; {len(anim_flags)} flags, {len(tall_tiles)} tall-grass tiles, '
      f'{len(zones)} zones, above layer: {bool(has_above)}, spawn {spawn}')
