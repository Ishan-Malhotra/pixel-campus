"""Tiled painting kit, generated in the style of the user's approved art.

  tiled/tilesets/terrain.png + terrain.tsj   16 px tiles with Wang (terrain) sets so roads, dirt paths, hedges and
                                             garden lawn draw their own kerbs/edges/corners while you paint:
                                               ids  0-15 Road   (grass <-> asphalt, kerbs + verge)
                                               ids 16-31 Path   (grass <-> dirt)
                                               ids 32-47 Hedge  (grass <-> hedge, solid)
                                               ids 48-63 Garden (grass <-> darker garden lawn)
                                               ids 64-67 grass variants, 68-69 tall grass (animated, rustles),
                                               70-71 flowerbed (solid)
  tiled/tilesets/props.tsj + tiled/props/*.png  flags (wave in game), palm, lamp, bush, tree, shrub, flowers, sign, crop:
                                             all cut from the user's art
  tiled/campus.tiled-project                 object classes: zone, spawn, slot, collision, door, hedge (a polyline that the
                                             game draws as a smooth hedge)

Used by tools/v4/blueprint.py (to pre-paint the ground from OpenStreetMap) and tools/v4/tiled_to_game.py.
"""
import json, os
import numpy as np
from PIL import Image

T = 16
os.makedirs('tiled/tilesets', exist_ok=True)
os.makedirs('tiled/props', exist_ok=True)

ART = np.array(Image.open('art/reference_main.png').convert('RGB'))
NEW = np.array(Image.open('art/reference_fd2.png').convert('RGB'))
NEW[466:500, 918:952] = NEW[466:500, 880:914]
PAL_IMG = Image.fromarray(ART).quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def patch(a, test, size=32):
    best, bx, by = 1e18, 0, 0
    for y in range(0, a.shape[0] - size, 4):
        for x in range(0, a.shape[1] - size, 4):
            p = a[y:y + size, x:x + size].astype(int)
            if not test(p).all():
                continue
            v = p.std(axis=(0, 1)).sum()
            if v < best:
                best, bx, by = v, x, y
    return a[by:by + size, bx:bx + size].astype(np.uint8)


GRASS = patch(ART, lambda p: (p[..., 1] > p[..., 0] + 40) & (p[..., 1] > 170))
GARDEN = ART[668:684, 32:64].astype(np.uint8)            # smooth teal garden lawn (measured spot)
DIRT = patch(ART, lambda p: (p[..., 0] > 200) & (p[..., 1] > 170) & (p[..., 2] < 170) & (p[..., 0] > p[..., 2] + 50), 16)
ROADX = ART[396:469, 960]
ASPHALT, EDGE_DARK, EDGE_MID, VERGE = ROADX[len(ROADX) // 2], ART[402, 960], ART[403, 960], ART[399, 960]
SPECK = ART[430, 940]
HEDGE_BASE, HEDGE_HI, HEDGE_DK, HEDGE_OL = np.array([92, 188, 72]), np.array([144, 220, 96]), np.array([48, 128, 56]), np.array([22, 70, 38])
# two-tone hedge tube, measured on the hedges of art/reference_main.png (sunlit top, shaded lower part)
HEDGE_LIT, HEDGE_LIT_HI, HEDGE_LIT_DK = np.array([122, 212, 64]), np.array([150, 228, 96]), np.array([98, 190, 56])
HEDGE_SHADE, HEDGE_SHADE_HI, HEDGE_OL_TOP = np.array([26, 108, 9]), np.array([40, 133, 4]), np.array([40, 128, 10])
HEDGE_OL_DARK = np.array([18, 58, 14])                 # the near-black line along the top of the art's hedges
PATH_RIM = np.array([184, 148, 104])
GARDEN_OL = np.array([44, 116, 80])
TALL = ART[200:216, 120:136].copy()                    # a 16x16 sample of the tall-grass patch
FLOWERS = ART[560:576, 262:278].copy()                 # a 16x16 sample of a flowerbed / flower cluster

# corner order used for tile ids inside each Wang set: bits (TL, TR, BL, BR) -> id 0..15
CORNERS = [((i >> 3) & 1, (i >> 2) & 1, (i >> 1) & 1, i & 1) for i in range(16)]


def membership(tl, tr, bl, br):
    """signed distance (px, + inside the B terrain) for each pixel of a corner-Wang tile (bilinear corner blend)"""
    v, u = np.mgrid[0:T, 0:T]
    u = (u + 0.5) / T; v = (v + 0.5) / T
    b = tl * (1 - u) * (1 - v) + tr * u * (1 - v) + bl * (1 - u) * v + br * u * v
    du = (-tl * (1 - v) + tr * (1 - v) - bl * v + br * v) / T
    dv = (-tl * (1 - u) - tr * u + bl * (1 - u) + br * u) / T
    g = np.sqrt(du ** 2 + dv ** 2) + 1e-6
    return (b - 0.5) / g, b


def grass_tile(seed=0):
    oy, ox = (seed // 2) * 16, (seed % 2) * 16
    return GRASS[oy:oy + 16, ox:ox + 16].copy()


def paint(kind, img, d, x, y, top=None):
    """paint terrain `kind` into the RGB array `img` (in place).
    d = signed distance in px to the terrain's outline (+ inside), x / y = pixel coordinates (texture phase).
    top (hedges only) = 0 at the hedge's sunlit edge .. 1 at its shaded edge: gives the two-tone tube of the art.
    Shared by the 16 Wang tiles below (what Tiled shows) and by tiled_to_game.py, which repaints every terrain on
    smoothed outlines, so the game and Tiled use the same colours."""
    inside = d > 0
    if kind == 'road':
        img[inside] = ASPHALT
        img[inside & (((x * 7 + y * 3) % 37) == 0)] = SPECK
        img[inside & (d < 2.5)] = EDGE_MID
        img[inside & (d < 1.2)] = EDGE_DARK
        img[~inside & (d > -2.2)] = VERGE
    elif kind == 'path':
        img[inside] = DIRT[y[inside] % DIRT.shape[0], x[inside] % DIRT.shape[1]]
        img[inside & (d < 1.2)] = PATH_RIM
    elif kind == 'hedge' and top is not None:
        lit = inside & (top < 0.42)
        img[inside] = HEDGE_SHADE
        img[inside & ~lit & (((x * 7 + y * 5) % 17) == 0)] = HEDGE_SHADE_HI
        img[lit] = HEDGE_LIT
        img[lit & (((x * 5 + y * 3) % 13) == 0)] = HEDGE_LIT_HI
        img[lit & (((x * 3 + y * 7) % 19) == 0)] = HEDGE_LIT_DK
        img[inside & (d < 1.2)] = HEDGE_OL
        img[lit & (d < 1.2)] = HEDGE_OL_TOP
    elif kind == 'hedge':
        img[inside] = HEDGE_BASE
        img[inside & (((x * 5 + y * 3) % 13) == 0)] = HEDGE_HI
        img[inside & (((x * 7 + y * 5) % 17) == 0)] = HEDGE_DK
        img[inside & (d < 3) & (d >= 1.2)] = HEDGE_DK
        img[inside & (d < 1.2)] = HEDGE_OL
    elif kind == 'garden':
        img[inside] = GARDEN[y[inside] % GARDEN.shape[0], x[inside] % GARDEN.shape[1]]
        img[inside & (d < 1.2)] = GARDEN_OL
    return img


def wang_tiles(kind):
    out = []
    for tl, tr, bl, br in CORNERS:
        d, b = membership(tl, tr, bl, br)
        y, x = np.mgrid[0:T, 0:T]
        tile = paint(kind, grass_tile().astype(int), d, x, y)
        out.append((tile.clip(0, 255).astype(np.uint8), float((b > 0.5).mean())))
    return out


def build():
    tiles, props_ = [], {}
    sets = []
    for si, kind in enumerate(('road', 'path', 'hedge', 'garden')):
        wt = wang_tiles(kind)
        sets.append(kind)
        for i, (tile, cover) in enumerate(wt):
            tiles.append(tile)
            if kind == 'hedge' and cover >= 0.5:
                props_[si * 16 + i] = [{'name': 'solid', 'type': 'bool', 'value': True}]
    for s in range(4):
        tiles.append(grass_tile(s))
    t0 = TALL.copy()
    t1 = TALL.copy()
    lum = t0.astype(int).sum(axis=2)
    tips = lum > np.percentile(lum, 80)
    t1[np.roll(tips, 1, axis=1)] = t0[tips].mean(axis=0).astype(np.uint8)
    tiles += [t0, t1]
    props_[68] = [{'name': 'tallgrass', 'type': 'bool', 'value': True}]
    props_[69] = [{'name': 'tallgrass', 'type': 'bool', 'value': True}]
    tiles += [FLOWERS, FLOWERS[:, ::-1].copy()]
    props_[70] = [{'name': 'solid', 'type': 'bool', 'value': True}]
    props_[71] = [{'name': 'solid', 'type': 'bool', 'value': True}]
    COLS = 16
    rows = (len(tiles) + COLS - 1) // COLS
    sheet = np.zeros((rows * T, COLS * T, 3), np.uint8)
    for i, tl in enumerate(tiles):
        sheet[(i // COLS) * T:(i // COLS + 1) * T, (i % COLS) * T:(i % COLS + 1) * T] = tl
    img = Image.fromarray(sheet).quantize(palette=PAL_IMG, dither=Image.Dither.NONE).convert('RGB')
    img.save('tiled/tilesets/terrain.png')
    names = {'road': ('Grass', 'Road', '#5fbf5f', '#8a8fa3'), 'path': ('Grass', 'Dirt path', '#5fbf5f', '#e2c48c'),
             'hedge': ('Grass', 'Hedge', '#5fbf5f', '#2f7a32'), 'garden': ('Grass', 'Garden lawn', '#5fbf5f', '#3f9e6a')}
    wangsets = []
    for si, kind in enumerate(sets):
        a, b, ca, cb = names[kind]
        wtiles = []
        for i, (tl, tr, bl, br) in enumerate(CORNERS):
            # Tiled corner wangid: [top, top-right, right, bottom-right, bottom, bottom-left, left, top-left]
            wtiles.append({'tileid': si * 16 + i, 'wangid': [0, tr + 1, 0, br + 1, 0, bl + 1, 0, tl + 1]})
        wangsets.append({'name': kind.capitalize() if kind != 'garden' else 'Garden lawn', 'type': 'corner', 'tile': si * 16 + 15,
                         'colors': [{'name': a, 'color': ca, 'tile': 64, 'probability': 1},
                                    {'name': b, 'color': cb, 'tile': si * 16 + 15, 'probability': 1}],
                         'wangtiles': wtiles})
    tile_meta = [{'id': i, 'properties': p} for i, p in sorted(props_.items())]
    for m in tile_meta:
        if m['id'] == 68:
            m['animation'] = [{'tileid': 68, 'duration': 450}, {'tileid': 69, 'duration': 450}]
    for i in range(64, 68):
        tile_meta.append({'id': i, 'probability': 1 if i == 64 else 0.35})
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'terrain', 'image': 'terrain.png',
               'imagewidth': COLS * T, 'imageheight': rows * T, 'tilewidth': T, 'tileheight': T, 'tilecount': len(tiles),
               'columns': COLS, 'margin': 0, 'spacing': 0, 'tiles': sorted(tile_meta, key=lambda m: m['id']), 'wangsets': wangsets},
              open('tiled/tilesets/terrain.tsj', 'w'), indent=1)
    return len(tiles)


def flood_cut(src, box, bg_ref=None, tol=24):
    x0, y0, x1, y1 = box
    crop = src[y0:y1, x0:x1].astype(int)
    h, w = crop.shape[:2]
    border = np.unique(np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]]), axis=0) if bg_ref is None else bg_ref
    d = np.min(np.abs(crop.reshape(-1, 1, 3) - border[None]).sum(axis=2), axis=1).reshape(h, w)
    ok = d < tol
    bg = np.zeros((h, w), bool)
    st = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while st:
        y, x = st.pop()
        if 0 <= y < h and 0 <= x < w and not bg[y, x] and ok[y, x]:
            bg[y, x] = True
            st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    rgba = np.dstack([crop.astype(np.uint8), np.where(bg, 0, 255).astype(np.uint8)])
    ys, xs = np.nonzero(rgba[..., 3])
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(xs) else rgba


LAWN_KEY = np.median(GRASS.reshape(-1, 3), axis=0).astype(int)
SHADE_KEYS = np.array([[70, 170, 120], [84, 160, 116], [96, 196, 140]])        # darker lawn in the buildings' shadow


# more background colours of the art, for cutting pieces that stand next to shade, roads, dirt or the Rotunda's apron
LAWNS = np.vstack([LAWN_KEY, SHADE_KEYS, [[80, 156, 118], [95, 183, 129], [86, 156, 124], [116, 196, 96], [120, 190, 76]]])
ROAD_KEYS = np.array([[143, 150, 166], [149, 149, 157]])
APRON_KEY = np.array([[218, 203, 177]])
DIRT_KEY = np.array([[222, 198, 132]])


def key_cut(src, box, refs=LAWN_KEY, tol=80, min_blob=10, erase=(), largest=False, inner=True):
    """cut one object standing on lawn out of the art. Background = pixels within `tol` of the `refs` colours, flood-filled
    from the box border, plus any lawn showing through inside the object. Specks smaller than `min_blob` px are dropped.
    erase = boxes (x0, y0, x1, y1, inside the cut) to blank first: neighbours that are not part of the object.
    largest = keep only the biggest connected part. inner=False keeps lawn-coloured pixels inside the object (palm fronds)."""
    x0, y0, x1, y1 = box
    crop = src[y0:y1, x0:x1].astype(int)
    h, w = crop.shape[:2]
    refs = np.atleast_2d(refs)
    ok = np.min(np.abs(crop[:, :, None, :] - refs[None, None]).sum(axis=3), axis=2) < tol
    gone = np.zeros((h, w), bool)
    for ex0, ey0, ex1, ey1 in erase:
        gone[ey0:ey1, ex0:ex1] = True
    ok |= gone
    bg = np.zeros((h, w), bool)
    st = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while st:
        y, x = st.pop()
        if 0 <= y < h and 0 <= x < w and not bg[y, x] and ok[y, x]:
            bg[y, x] = True
            st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    if inner:
        bg |= (crop[..., 1] > 185) & (crop[..., 2] > 105) & (crop[..., 0] < 150)
    keep = ~bg & ~gone
    seen = np.zeros((h, w), bool)
    blobs = []
    for sy, sx in zip(*np.nonzero(keep)):                  # drop specks
        if seen[sy, sx]:
            continue
        blob, st = [], [(sy, sx)]
        while st:
            y, x = st.pop()
            if 0 <= y < h and 0 <= x < w and keep[y, x] and not seen[y, x]:
                seen[y, x] = True
                blob.append((y, x))
                st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1), (y + 1, x + 1), (y - 1, x - 1), (y + 1, x - 1), (y - 1, x + 1)]
        blobs.append(blob)
    big = max(len(b) for b in blobs)
    for blob in blobs:
        if len(blob) < (big if largest else min_blob):
            for y, x in blob:
                keep[y, x] = False
    rgba = np.dstack([crop.astype(np.uint8), np.where(keep, 255, 0).astype(np.uint8)])
    ys, xs = np.nonzero(keep)
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def build_props():
    """props as an image-collection tileset (cut from the user's art)"""
    items = []
    for i in range(6):                                     # true-colour flag cut-outs (tools/v3/props_extract.py strips, 4 frames)
        path = f'art/props/flag{i}.png'
        if os.path.exists(path):
            strip = np.array(Image.open(path).convert('RGBA'))
            items.append((f'flag{i}', strip[:, :strip.shape[1] // 4], [{'name': 'anim', 'type': 'string', 'value': 'flag'}]))
    if os.path.exists('art/props/palm0.png'):
        pal = np.array(Image.open('art/props/palm0.png').convert('RGBA'))
        items.append(('palm', pal[:, :pal.shape[1] // 4], [{'name': 'solid_base', 'type': 'bool', 'value': True}]))
    items.append(('lamp', flood_cut(ART, (26, 422, 50, 472), tol=30), [{'name': 'solid_base', 'type': 'bool', 'value': True}]))
    items.append(('bush', flood_cut(ART, (301, 219, 327, 247), tol=14), [{'name': 'solid_base', 'type': 'bool', 'value': True}]))
    lawn_ref = np.unique(NEW[420:452, 700:732].reshape(-1, 3).astype(int), axis=0)
    items.append(('tree_cluster', flood_cut(NEW, (640, 470, 716, 552), bg_ref=lawn_ref, tol=18), [{'name': 'solid_base', 'type': 'bool', 'value': True}]))
    # garden pieces from the beds in front of the Main Building (art/reference_main.png). New props go at the END so
    # the tile ids of the ones above never change.
    solid = [{'name': 'solid_base', 'type': 'bool', 'value': True}]
    flat = [{'name': 'flat', 'type': 'bool', 'value': True}]            # lies on the ground: drawn under the player, walkable
    wide = solid + [{'name': 'base_w', 'type': 'float', 'value': 0.8}, {'name': 'base_h', 'type': 'float', 'value': 0.5}]
    items.append(('shrub', key_cut(ART, (904, 235, 922, 259)), solid))
    items.append(('flowers_red', key_cut(ART, (873, 240, 891, 258)), flat))
    items.append(('flowers_white', key_cut(ART, (856, 295, 874, 312)), flat))
    items.append(('flowers_pink', key_cut(ART, (893, 466, 960, 497)), wide))
    items.append(('sign', key_cut(ART, (912, 367, 938, 394), np.vstack([LAWN_KEY, SHADE_KEYS])), solid))
    # one cell of the art's vegetable bed (a plant on its green patch): cells laid side by side on dirt make a bed
    items.append(('crop', np.dstack([ART[241:259, 804:822], np.full((18, 18), 255, np.uint8)]), flat))
    # bigger garden pieces, used at the art's own size (the map is at the art's scale)
    grassy = flat + [{'name': 'tallgrass', 'type': 'bool', 'value': True}]     # walkable, rustles like tall grass
    thicket = key_cut(ART, (96, 188, 208, 292), np.vstack([LAWNS, DIRT_KEY, [[88, 128, 100]]]), largest=True)
    items.append(('thicket', thicket, grassy))
    items.append(('thicket_tall', np.ascontiguousarray(thicket.transpose(1, 0, 2)), grassy))    # the same patch, turned to fit narrow corners
    items.append(('veg_bed', key_cut(ART, (766, 206, 906, 330), min_blob=30,
                                     erase=[(0, 74, 25, 124), (0, 106, 44, 124), (118, 8, 140, 44)]), flat))
    items.append(('palm_small', key_cut(ART, (647, 224, 676, 258), LAWNS, tol=50, largest=True, inner=False), solid))
    items.append(('conifer', key_cut(ART, (903, 334, 922, 363), LAWNS, tol=50, largest=True, inner=False), solid))
    items.append(('bush_big', key_cut(ART, (717, 387, 738, 409), LAWNS, tol=50, largest=True, inner=False), solid))
    items.append(('bougainvillea', key_cut(ART, (766, 425, 856, 506), np.vstack([LAWNS, ROAD_KEYS]), erase=[(0, 0, 4, 81)],
                                           largest=True), wide))
    tiles = []
    for i, (name, rgba, props) in enumerate(items):
        Image.fromarray(rgba).save(f'tiled/props/{name}.png')
        tiles.append({'id': i, 'image': f'../props/{name}.png', 'imagewidth': int(rgba.shape[1]), 'imageheight': int(rgba.shape[0]),
                      'properties': [{'name': 'prop', 'type': 'string', 'value': name}] + props})
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'props',
               'tilewidth': max(t['imagewidth'] for t in tiles), 'tileheight': max(t['imageheight'] for t in tiles),
               'tilecount': len(tiles), 'columns': 0, 'margin': 0, 'spacing': 0,
               'grid': {'orientation': 'orthogonal', 'width': 1, 'height': 1}, 'tiles': tiles},
              open('tiled/tilesets/props.tsj', 'w'), indent=1)
    return [n for n, _, _ in items]


def build_project():
    json.dump({
        'automappingRulesFile': '', 'commands': [], 'extensionsPath': 'extensions', 'folders': ['.'],
        'propertyTypes': [
            {'id': 1, 'name': 'zone', 'type': 'class', 'useAs': ['object'], 'color': '#ff4fc3f7', 'drawFill': True, 'members': []},
            {'id': 2, 'name': 'spawn', 'type': 'class', 'useAs': ['object'], 'color': '#ffffd54f', 'drawFill': True, 'members': []},
            {'id': 3, 'name': 'slot', 'type': 'class', 'useAs': ['object'], 'color': '#ffef9a9a', 'drawFill': True,
             'members': [{'name': 'type', 'type': 'string', 'value': 'small'}]},
            {'id': 4, 'name': 'collision', 'type': 'class', 'useAs': ['object'], 'color': '#ffff0000', 'drawFill': True, 'members': []},
            {'id': 5, 'name': 'door', 'type': 'class', 'useAs': ['object'], 'color': '#ff7e57c2', 'drawFill': True,
             'members': [{'name': 'target', 'type': 'string', 'value': ''}]},
            {'id': 6, 'name': 'hedge', 'type': 'class', 'useAs': ['object'], 'color': '#ff2e7d32', 'drawFill': False,
             'members': [{'name': 'width', 'type': 'int', 'value': 14}]},
        ],
    }, open('tiled/campus.tiled-project', 'w'), indent=1)


if __name__ == '__main__':
    n = build()
    p = build_props()
    build_project()
    print(f'terrain tiles: {n}, props: {p}')
