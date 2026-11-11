"""Build the playable map directly from the user's source art (art/reference_main.png).

The source is cleaned into GBA-style pixel art (fixed palette, no dithering, baked-in people painted out),
sliced into deduplicated 16x16 tiles (Tiled JSON), and paired with the collision/zones measured in
tools/v2/map_main.py (data/layout_ref.json, same reference-tile coordinates).

Usage (from repo root):
    python3 tools/v2/map_main.py      # writes data/layout_ref.json (collision measured on the reference grid)
    python3 tools/v2/from_ref.py      # writes game/public/maps + tiles from the source art
"""
import json, math, os
import numpy as np
from PIL import Image

T = 16
SRC = 'art/composite_main_fd2.png'   # main map + FD2 extension (tools/v3/compose_fd2.py)
COLORS_NOTE = 'palette shared across the composite'
OUT = 'game/public'
COLORS = 128

im = Image.open(SRC).convert('RGB')
a = np.array(im)
# pad to a whole number of tiles
th, tw = math.ceil(a.shape[0] / T), math.ceil(a.shape[1] / T)
pad = np.zeros((th * T, tw * T, 3), np.uint8)
pad[:a.shape[0], :a.shape[1]] = a
pad[a.shape[0]:, :a.shape[1]] = a[-1:, :]
a = pad

# paint out the people baked into the source (patch = copy from a clean neighbouring area)
for (x0, y0, x1, y1, dx, dy) in [(626, 329, 643, 358, 18, 0), (210, 440, 228, 471, -20, 0), (1005, 398, 1024, 427, -22, 0)]:
    a[y0:y1, x0:x1] = a[y0 + dy:y1 + dy, x0 + dx:x1 + dx]

# GBA-style cleanup: fixed palette, no dithering (kills the soft AI gradients / noise)
q = Image.fromarray(a).quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB')
a = np.array(q)
Image.fromarray(a).save('art/map_main_clean.png')

# tiles
tiles, index, data = [], {}, []
for ty in range(th):
    for tx in range(tw):
        tile = a[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]
        key = tile.tobytes()
        if key not in index:
            index[key] = len(tiles)
            tiles.append(tile)
        data.append(index[key] + 1)
COLS = 32
rows = math.ceil(len(tiles) / COLS)
ts = np.zeros((rows * T, COLS * T, 4), np.uint8)
for i, tl in enumerate(tiles):
    ts[(i // COLS) * T:(i // COLS + 1) * T, (i % COLS) * T:(i % COLS + 1) * T, :3] = tl
    ts[(i // COLS) * T:(i // COLS + 1) * T, (i % COLS) * T:(i % COLS + 1) * T, 3] = 255
Image.fromarray(ts).save(f'{OUT}/tiles/campus.png')

lay = json.load(open('data/layout_ref.json'))
json.dump({
    'type': 'map', 'version': '1.10', 'tiledversion': '1.10.2', 'orientation': 'orthogonal', 'renderorder': 'right-down',
    'infinite': False, 'width': tw, 'height': th, 'tilewidth': T, 'tileheight': T, 'nextlayerid': 2, 'nextobjectid': 1,
    'layers': [{'id': 1, 'name': 'ground', 'type': 'tilelayer', 'x': 0, 'y': 0, 'width': tw, 'height': th,
                'opacity': 1, 'visible': True, 'data': data}],
    'tilesets': [{'firstgid': 1, 'name': 'campus', 'image': '../tiles/campus.png', 'imagewidth': COLS * T,
                  'imageheight': rows * T, 'tilewidth': T, 'tileheight': T, 'tilecount': len(tiles),
                  'columns': COLS, 'margin': 0, 'spacing': 0}],
}, open(f'{OUT}/maps/main.json', 'w'))

# collision = measured walls (buildings, rotunda gallery/rim, seating walls) + greenery detected from the art
cw, ch = tw * 2, th * 2
grid = np.zeros((ch, cw), bool)
src = np.array([c == '1' for c in lay['data']]).reshape(lay['h'], lay['w'])
grid[:min(ch, lay['h']), :min(cw, lay['w'])] = src[:ch, :cw]
# FD2 extension walls (tools/v3/compose_fd2.py)
ext = json.load(open('data/extension_fd2.json'))
for x0, y0, x1, y1 in ext['solid_rects']:
    grid[y0 // 8:(y1 + 7) // 8, x0 // 8:(x1 + 7) // 8] = True
gy, gx = np.mgrid[0:ch, 0:cw]
for cx, cy, rx, ry in ext['solid_ellipses']:
    grid |= (((gx * 8 + 4 - cx) / rx) ** 2 + ((gy * 8 + 4 - cy) / ry) ** 2) <= 1
r, g_, b = (a[..., k].astype(int) for k in range(3))
dark_green = (g_ > r + 25) & (g_ > b + 15) & (g_ < 150)          # hedge/tree/bush shading + outlines
cells = dark_green.reshape(ch, 8, cw, 8).mean(axis=(1, 3))
green = cells > 0.22
# close small holes so hedge tops (lighter) count as solid too
nb = sum(np.roll(np.roll(green, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
green = green | (nb >= 5)
# tall-grass patches stay walkable (reference tiles -> 8 px cells)
for x0, y0, x1, y1 in ((6.0, 12.0, 12.9, 17.9), (2.0, 24.2, 6.4, 28.4)):
    green[int(y0 * 2):int(y1 * 2), int(x0 * 2):int(x1 * 2)] = False
grid |= green
grid[:, 0] = grid[:, -1] = True
grid[0, :] = grid[-1, :] = True
json.dump({'props': [], 'frames': {}, 'collision': {'cell': 8, 'w': cw, 'h': ch, 'data': ''.join('1' if v else '0' for v in grid.ravel())},
           'zones': lay['zones'] + ext['zones'], 'spawn': lay['spawn'], 'width': tw * T, 'height': th * T},
          open(f'{OUT}/maps/main.meta.json', 'w'))
Image.fromarray(a).resize((tw * T // 5, th * T // 5), Image.BOX).save(f'{OUT}/maps/minimap.png')
# collision overlay for checking
dbg = a.copy()
big = np.kron(grid, np.ones((8, 8), bool))[:dbg.shape[0], :dbg.shape[1]]
dbg[big] = (dbg[big] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)
Image.fromarray(dbg).save('data/debug/from_ref_collision.png')
print(f'{tw}x{th} tiles, {len(tiles)} unique tiles, {COLORS} colours')
