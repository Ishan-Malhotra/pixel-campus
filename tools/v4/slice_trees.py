"""Slice the user's tree sheet (art/new/trees_sheet.png, a 4 x 3 grid on purple) into registered sprites.

  python3 tools/v4/slice_trees.py          (repo root; deterministic, no randomness)

Reads the sheet only; writes
  tiled/generated/trees/<name>.png             the whole sprite, on a canvas of whole 16 px tiles, trunk in the middle tile
  tiled/generated/trees/<name>_canopy.png      trees only: everything above the split row (goes on / above the player)
  tiled/generated/trees/<name>_trunk.png       trees only: the trunk base below the split row (the player walks behind it)
  tiled/generated/trees/_contact_sheet.png     all sprites on grass, with the split row and the collision footprint drawn
  tiled/generated/trees/trees.json             every measurement (sizes, scale, split row, footprint, held sprites)
  tiled/tilesets/trees.tsj                     "collection of images" tileset; each sprite carries its properties

How (the user's Part A, 2026-11-17):
  1. background = the colour of a corner pixel AND the sheet's most common colour (the corner is the darker frame /
     gutter purple, the cells are a lighter purple). Sprites are cut by COLOUR KEY (distance <= KEY_TOL to either), not
     by flood fill, so the holes in the umbrella tree's canopy open up; leftover purple-ish pixels are removed too.
  2. the generator's sparkle watermark (right of the grass tuft) is removed explicitly.
  3. the art's own pixel is ~2.92 screen px (measured from where the edges fall); the sheet is sampled once per art
     pixel (nearest neighbour), then each sprite is scaled, nearest neighbour, so its canopy is 3 tiles (row 1),
     2 tiles (row 2) or 1 tile (row 3) wide.
  4. every pixel is snapped to the locked palette (tiled_kit.PAL_IMG, the rule of tools/v3/build_map.py: to_palette);
     leaf pixels only to the palette's greens (its nearest colour to a deep leaf green is a grey). Alpha is 0 or 255.
  5. trees are split at a tile boundary 25-30 % up from the bottom: trunk base below, canopy above.
  6. the palm and the grass tuft are HELD: not cut, not registered.
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tiled_kit

SHEET = 'art/new/trees_sheet.png'
OUT = 'tiled/generated/trees'
T = 16
KEY_TOL = 60                 # colour distance (sum of |r g b| differences) to a background colour that still counts as background
NATIVE = 2.92                # screen px per art pixel (see docstring); refined below from the sheet itself
CANOPY_TILES = {0: 3, 1: 2, 2: 1}                      # sheet row -> canopy width in tiles
CANOPY_OVERRIDE = {'tree_twin': 5, 'tree_umbrella': 4}   # two trees side by side / a naturally wide crown: 3 tiles would crush them
MAX_SCALE = 1.0              # never enlarge the art: the narrow trees (column, cypress) stay at their own size
OUTLINE_LEAF, OUTLINE_WOOD = (20, 62, 30), (62, 38, 34)     # clean outline colours (snapped to the palette later)
ROADSIDE = {'tree_umbrella': 3, 'tree_twin': 3}   # street copies: canopy at most 3 tiles (user, 2026-11-17); the full size stays for lawns
TRUNK_BASE = 0.275           # the trunk base is this share of the sprite's height (25-30 % asked)
NAMES = [['tree_round_big', 'tree_umbrella', 'tree_column', 'tree_twin'],
         ['tree_ball', 'tree_lime', 'tree_cypress', 'palm'],
         ['shrub_red', 'shrub_yellow', 'shrub_green', 'grass_tuft']]
HELD = {'palm', 'grass_tuft'}

PAL = np.array(tiled_kit.PAL_IMG.getpalette()[:384], np.int32).reshape(-1, 3)
PAL_SET = {tuple(int(v) for v in c) for c in PAL}
PAL_GREEN = PAL[(PAL[:, 1] > PAL[:, 0] + 8) & (PAL[:, 1] > PAL[:, 2] + 8)]


def nearest(px, pal):
    return pal[np.argmin(((px[:, None, :].astype(np.int32) - pal[None, :, :]) ** 2).sum(axis=2), axis=1)]


def snap(rgb):
    """locked palette; leaves (green is the strongest channel) only to the palette's greens"""
    flat = rgb.reshape(-1, 3).astype(np.int32)
    out = nearest(flat, PAL)
    leafy = (flat[:, 1] > flat[:, 0] + 6) & (flat[:, 1] > flat[:, 2] + 6)
    # the deep shade under a crown is a very dark green-grey in the art: it belongs to the leaves too
    leafy |= (flat.sum(axis=1) < 215) & (flat[:, 1] >= flat[:, 0] - 4) & (flat[:, 0] - flat[:, 2] < 25)
    bad = leafy & ~((out[:, 1] > out[:, 0] + 8) & (out[:, 1] > out[:, 2] + 8))
    if bad.any():
        out[bad] = nearest(flat[bad], PAL_GREEN)
    return out.reshape(rgb.shape).astype(np.uint8)


def purple(a):
    """background-purple-ish: blue far above green and close to red, as in both background purples (frame 157/51/123,
    cells 194/90/158). Crimson flowers and red trunk shades have far less blue, so they stay."""
    r, g, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    return (b > g + 45) & (r > g + 30) & (r - b < 60)


def grid_phase(profile, per):
    """offset (0..per) of the art's pixel grid: where the edge strength peaks, from its Fourier component"""
    xs = np.arange(len(profile))
    c = ((profile - profile.mean()) * np.exp(-2j * np.pi * xs / per)).sum()
    return (-np.angle(c) / (2 * np.pi) * per) % per


def main():
    os.makedirs(OUT, exist_ok=True)
    src = np.array(Image.open(SHEET).convert('RGB')).astype(np.int32)
    H, W = src.shape[:2]
    corner = src[0, 0]
    vals, counts = np.unique(src.reshape(-1, 3) // 4 * 4, axis=0, return_counts=True)
    common = vals[np.argmax(counts)] + 2
    bgs = np.array([corner, common])
    dist = np.min(np.abs(src[:, :, None, :] - bgs[None, None, :, :]).sum(axis=3), axis=2)
    is_bg = (dist <= KEY_TOL) | purple(src)
    # the cell grid: gutters = the columns / rows that are frame-coloured almost end to end
    frame = np.abs(src - corner).sum(axis=2) <= 30
    gx = np.nonzero(frame.mean(axis=0) > 0.9)[0]; gy = np.nonzero(frame.mean(axis=1) > 0.9)[0]

    def bands(idx, size):
        """the stretches between gutter runs (and before the first / after the last) -> cell ranges"""
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        edges = [(-1, -1)] + [(int(r[0]), int(r[-1])) for r in runs] + [(size, size)]
        return [(a[1] + 1, b[0]) for a, b in zip(edges, edges[1:]) if b[0] - a[1] - 1 > 8]
    cols, rows = bands(gx, W), bands(gy, H)
    assert len(cols) == 4 and len(rows) == 3, f'expected a 4 x 3 grid, found {len(cols)} x {len(rows)}: {cols} {rows}'
    # the art's pixel grid
    fg = ~is_bg
    ex = (np.abs(np.diff(src, axis=1)).sum(axis=2) * fg[:, 1:]).sum(axis=0).astype(float)
    ey = (np.abs(np.diff(src, axis=0)).sum(axis=2) * fg[1:, :]).sum(axis=1).astype(float)
    per = max(np.arange(2.6, 3.4, 0.005), key=lambda p_: abs(((ex - ex.mean()) * np.exp(-2j * np.pi * np.arange(len(ex)) / p_)).sum())
              + abs(((ey - ey.mean()) * np.exp(-2j * np.pi * np.arange(len(ey)) / p_)).sum()))
    per = float(per)
    px, py = grid_phase(ex, per), grid_phase(ey, per)

    report = {'sheet': SHEET, 'background': {'corner_frame': corner.tolist(), 'cell': common.tolist(), 'key_tolerance': KEY_TOL},
              'cells_x': cols, 'cells_y': rows, 'native_px': round(per, 3), 'grid_offset': [round(px, 2), round(py, 2)],
              'sprites': {}, 'held': sorted(HELD), 'watermark_removed_px': 0}
    tiles, sheet_items, extra_tiles = [], [], []
    for r, (y0, y1) in enumerate(rows):
        for c, (x0, x1) in enumerate(cols):
            name = NAMES[r][c]
            cell_fg = fg[y0:y1, x0:x1].copy()
            if name == 'grass_tuft':                   # the sparkle watermark: pale, unsaturated, right of the tuft
                cs = src[y0:y1, x0:x1]
                green = (cs[..., 1] > cs[..., 0] + 10) | ((cs[..., 0] > cs[..., 2] + 40) & (cs[..., 1] > cs[..., 2] + 20))    # blades, straw
                tuft_cols = np.nonzero((cell_fg & green).any(axis=0))[0]
                mark = cell_fg & ~green
                mark[:, :tuft_cols.max() + 1] &= False
                report['watermark_removed_px'] = int(mark.sum() + (cell_fg[:, tuft_cols.max() + 1:] & ~mark[:, tuft_cols.max() + 1:]).sum())
                ys_, xs_ = np.nonzero(cell_fg[:, tuft_cols.max() + 1:])
                if len(xs_):
                    report['watermark_box'] = [int(x0 + tuft_cols.max() + 1 + xs_.min()), int(y0 + ys_.min()),
                                               int(x0 + tuft_cols.max() + 1 + xs_.max()), int(y0 + ys_.max())]
                fg[y0:y1, x0 + tuft_cols.max() + 1:x1] = False
            if name in HELD:
                continue
            # sample once per art pixel, at the pixel centres (nearest neighbour)
            sx = np.arange(px + per / 2 + math.ceil((x0 - px) / per) * per, x1, per)
            sy = np.arange(py + per / 2 + math.ceil((y0 - py) / per) * per, y1, per)
            ix, iy = np.clip(np.round(sx).astype(int), 0, W - 1), np.clip(np.round(sy).astype(int), 0, H - 1)
            rgb = src[np.ix_(iy, ix)].astype(np.uint8)
            al = fg[np.ix_(iy, ix)]
            # drop specks and a 1 px purple-tinted rim, keep the sprite
            lab = np.zeros(al.shape, int); sizes = {}; n = 0
            for sy_, sx_ in zip(*np.nonzero(al)):
                if lab[sy_, sx_]: continue
                n += 1; st = [(sy_, sx_)]; lab[sy_, sx_] = n; k = 0
                while st:
                    y, x = st.pop(); k += 1
                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1), (y + 1, x + 1), (y - 1, x - 1), (y + 1, x - 1), (y - 1, x + 1)):
                        if 0 <= ny < al.shape[0] and 0 <= nx < al.shape[1] and al[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = n; st.append((ny, nx))
                sizes[n] = k
            al = np.isin(lab, [k_ for k_, v in sizes.items() if v >= 12])
            # de-fringe: the sheet's outline pixels are blended with the purple behind them (greys, pinks, browns once
            # keyed). Every rim pixel that is not a clean leaf green becomes the outline colour: dark green where it
            # borders leaves, dark brown where it borders only trunk.
            pa = np.pad(al, 1)
            rim = al & ~(pa[:-2, 1:-1] & pa[2:, 1:-1] & pa[1:-1, :-2] & pa[1:-1, 2:])
            ci = rgb.astype(int)
            green_px = al & (ci[..., 1] > ci[..., 0] + 12) & (ci[..., 1] > ci[..., 2] + 12)
            shade = al & (ci.sum(axis=2) < 215) & (ci[..., 1] >= ci[..., 0] - 4) & (ci[..., 0] - ci[..., 2] < 25)   # deep shade under a crown
            pg = np.pad((green_px | shade) & ~rim, 1)
            by_leaf = np.zeros(al.shape, bool)
            for dy in (0, 1, 2):
                for dx in (0, 1, 2):
                    by_leaf |= pg[dy:dy + al.shape[0], dx:dx + al.shape[1]]
            fix = rim & ~green_px
            rgb[fix & by_leaf] = OUTLINE_LEAF
            rgb[fix & ~by_leaf] = OUTLINE_WOOD
            n_fringe = int(fix.sum())
            ys, xs = np.nonzero(al)
            clip_margin = int(min(ys.min(), xs.min(), al.shape[0] - 1 - ys.max(), al.shape[1] - 1 - xs.max()))   # art px to the cell's edge
            rgb, al = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1], al[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            base_name = name
            variants = [(name, CANOPY_OVERRIDE.get(name, CANOPY_TILES[r]), False)]
            if name in ROADSIDE:                           # a smaller copy for streets (canopy at most ROADSIDE tiles)
                variants.append((name + '_road', ROADSIDE[name], True))
            rgb_nat, al_nat = rgb, al
            for name, ctiles, is_extra in variants:
                rgb, al = rgb_nat.copy(), al_nat.copy()
                nat_h, nat_w = al.shape
                is_tree = r < 2
                # canopy width: the widest row of the upper 70 % (trees) / of the whole sprite (shrubs)
                upper = al[:int(nat_h * 0.7)] if is_tree else al
                canopy_w = int(max(np.ptp(np.nonzero(row_)[0]) + 1 for row_ in upper if row_.any()))
                scale = min(MAX_SCALE, ctiles * T / canopy_w)
                w2, h2 = max(1, round(nat_w * scale)), max(1, round(nat_h * scale))
                rgb2 = np.array(Image.fromarray(rgb).resize((w2, h2), Image.NEAREST))
                al2 = np.array(Image.fromarray((al * 255).astype(np.uint8)).resize((w2, h2), Image.NEAREST)) > 0
                rgb2 = snap(rgb2)
                # canvas of whole tiles: an odd number of tiles wide, the trunk (the sprite's lowest rows) centred on the middle tile
                foot = al2[max(0, h2 - 3):]
                fxs = np.nonzero(foot.any(axis=0))[0]
                foot_c = (fxs.min() + fxs.max() + 1) / 2 if is_tree else w2 / 2
                half = max(foot_c, w2 - foot_c)
                wt = max(1, math.ceil(2 * half / T))
                if is_tree: wt += (wt % 2 == 0)             # trees: an odd number of tiles, the trunk in the middle one
                ht = math.ceil(h2 / T)
                cw, ch = wt * T, ht * T
                ox, oy = round(cw / 2 - foot_c), ch - h2
                canvas = np.zeros((ch, cw, 4), np.uint8)
                canvas[oy:oy + h2, ox:ox + w2, :3] = rgb2; canvas[oy:oy + h2, ox:ox + w2, 3] = np.where(al2, 255, 0)
                canvas[canvas[..., 3] == 0] = 0
                # checks: palette only, hard alpha, no purple left
                op = canvas[canvas[..., 3] > 0][:, :3]
                cols_used = {tuple(int(v) for v in p_) for p_ in op}
                assert cols_used <= PAL_SET, f'{name}: colours outside the palette'
                assert set(np.unique(canvas[..., 3])) <= {0, 255}, f'{name}: soft alpha'
                assert not purple(op[None]).any(), f'{name}: purple fringe left'
                Image.fromarray(canvas).save(f'{OUT}/{name}.png')
                info = {'file': f'{name}.png', 'kind': 'tree' if is_tree else 'shrub', 'sheet_cell': [r, c], 'native_size': [nat_w, nat_h],
                        'roadside_copy_of': base_name if is_extra else None,
                        'scale': round(scale, 3), 'size_px': [cw, ch], 'size_tiles': [wt, ht], 'canopy_px': round(canopy_w * scale),
                        'colours': len(cols_used), 'margin_to_cell_edge': clip_margin, 'fringe_px_repainted': n_fringe}
                props = [('kind', 'string', info['kind']), ('tiles_w', 'int', wt), ('tiles_h', 'int', ht)]
                if is_tree:
                    split = ch - max(4, round(TRUNK_BASE * h2))            # trunk base: 25-30 % of the sprite's own height
                    bz = canvas[split:].astype(int)                         # where the trunk(s) stand: the non-green pixels of the base
                    wood = (bz[..., 3] > 0) & ~((bz[..., 1] > bz[..., 0] + 8) & (bz[..., 1] > bz[..., 2] + 8))
                    wood[:, wood.sum(axis=0) < 3] = False
                    opaque_base = np.nonzero(wood.any(axis=0))[0] if wood.any() else np.nonzero(canvas[ch - 3:, :, 3].any(axis=0))[0]
                    # collision footprint: the trunk's tile(s) in the bottom tile row (one tile; two for the twin trunk)
                    fx0 = int(opaque_base.min() // T); fx1 = int(opaque_base.max() // T)
                    foot_rect = [fx0 * T, ch - T, (fx1 - fx0 + 1) * T, T]
                    can_img = canvas.copy(); can_img[split:] = 0
                    # the trunk piece starts at the split row, or where the canopy cell (every row above the trunk's
                    # tile) ends if that is higher, so the two pieces always meet with no row lost between them
                    tsplit = min(split, ch - T)
                    trk_img = canvas.copy(); trk_img[:tsplit] = 0
                    Image.fromarray(can_img[:split]).save(f'{OUT}/{name}_canopy.png')
                    Image.fromarray(trk_img[tsplit:]).save(f'{OUT}/{name}_trunk.png')
                    # the canopy as the `above` layer needs it: every row above the trunk's tile, rows from the split row
                    # down transparent. Placed in the cell straight above the trunk tile (bottom-left anchored), it sits
                    # exactly where the whole sprite would
                    cell_img = canvas[:ch - T].copy(); cell_img[tsplit:] = 0
                    Image.fromarray(cell_img).save(f'{OUT}/{name}_canopy_cell.png')
                    info.update(split_row=int(split), trunk_from_row=int(tsplit), trunk_base_pct=round(100 * (ch - split) / h2, 1), collision=foot_rect,
                                canopy_file=f'{name}_canopy.png', trunk_file=f'{name}_trunk.png')
                    props += [('split_row', 'int', int(split)), ('collision_x', 'int', foot_rect[0]), ('collision_y', 'int', foot_rect[1]),
                              ('collision_w', 'int', foot_rect[2]), ('collision_h', 'int', foot_rect[3]),
                              ('canopy_layer', 'string', 'above'), ('trunk_layer', 'string', 'props')]
                else:
                    foot_rect = [0, ch - T, cw, T]
                    info.update(collision=foot_rect)
                    props += [('collision_x', 'int', 0), ('collision_y', 'int', ch - T), ('collision_w', 'int', cw), ('collision_h', 'int', T)]
                report['sprites'][name] = info
                def tile(fname, img_wh, part, extra=()):
                    (extra_tiles if is_extra or part == 'canopy_cell' else tiles).append({'id': None, 'type': part, 'image': f'../generated/trees/{fname}', 'imagewidth': img_wh[0], 'imageheight': img_wh[1],
                                  'properties': [{'name': 'prop', 'type': 'string', 'value': os.path.splitext(fname)[0]}, {'name': 'sprite', 'type': 'string', 'value': name},
                                                 {'name': 'part', 'type': 'string', 'value': part}]
                                                + [{'name': n_, 'type': t_, 'value': v_} for n_, t_, v_ in props] + list(extra)})
                tile(f'{name}.png', (cw, ch), 'whole')
                if is_tree:
                    tile(f'{name}_canopy.png', (cw, info['split_row']), 'canopy')
                    # the trunk image starts at the split row: its collision box is moved up by that much
                    trunk_props = [p_ for p_ in props if p_[0] != 'collision_y'] + [('collision_y', 'int', foot_rect[1] - info['trunk_from_row'])]
                    props, saved = trunk_props, props
                    tile(f'{name}_trunk.png', (cw, ch - info['trunk_from_row']), 'trunk', [{'name': 'solid_base', 'type': 'bool', 'value': True}])
                    props = [p_ for p_ in saved if not p_[0].startswith('collision')]
                    tile(f'{name}_canopy_cell.png', (cw, ch - T), 'canopy_cell', [{'name': 'trunk_cell_offset_x', 'type': 'int', 'value': wt // 2}])
                    props = saved
                sheet_items.append((name, canvas, info))

    tiles += extra_tiles                                # appended: the ids of the original sprites never change
    for i_, t_ in enumerate(tiles):
        t_['id'] = i_
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'trees',
               'tilewidth': max(t['imagewidth'] for t in tiles), 'tileheight': max(t['imageheight'] for t in tiles),
               'tilecount': len(tiles), 'columns': 0, 'margin': 0, 'spacing': 0, 'objectalignment': 'bottomleft',
               'grid': {'orientation': 'orthogonal', 'width': 1, 'height': 1}, 'tiles': tiles}, open('tiled/tilesets/trees.tsj', 'w'), indent=1)
    json.dump(report, open(f'{OUT}/trees.json', 'w'), indent=1)

    # contact sheets at 4x: on the real grass tile of the ground tileset, and on a hostel roof tile (a pale ground shows
    # up dark fringes, a green one pale fringes). Tile grid, split row (yellow), collision footprint (red).
    terr = np.array(Image.open('tiled/tilesets/terrain.png').convert('RGB'))
    grass = terr[4 * T:5 * T, 0:T]                                      # terrain tile 64: plain grass
    roof = np.array(Image.open('tiled/stamps/bhawan.png').convert('RGB'))[24:24 + T, 150:150 + T]    # a plain roof patch of the hostel stamp
    Z, pad = 4, 12
    Wc = sum(i[1].shape[1] + pad for i in sheet_items) + pad
    Hc = max(i[1].shape[0] for i in sheet_items) + 2 * pad
    for tile_bg, path in ((grass, 'trees_on_grass.png'), (roof, 'trees_on_roof.png')):
        base = np.tile(tile_bg, (Hc // T + 1, Wc // T + 1, 1))[:Hc, :Wc]
        im = Image.fromarray(base).convert('RGBA')
        x = pad; marks = []
        for name, canvas, info in sheet_items:
            y = Hc - pad - canvas.shape[0]
            im.alpha_composite(Image.fromarray(canvas), (x, y))
            marks.append((name, x, y, canvas.shape[1], canvas.shape[0], info))
            x += canvas.shape[1] + pad
        im = im.resize((Wc * Z, Hc * Z), Image.NEAREST); d = ImageDraw.Draw(im, 'RGBA')
        for name, x, y, w_, h_, info in marks:
            for tx in range(0, w_ + 1, T): d.line([((x + tx) * Z, y * Z), ((x + tx) * Z, (y + h_) * Z)], fill=(255, 255, 255, 60))
            for ty in range(0, h_ + 1, T): d.line([(x * Z, (y + ty) * Z), ((x + w_) * Z, (y + ty) * Z)], fill=(255, 255, 255, 60))
            if 'split_row' in info:
                d.line([(x * Z, (y + info['split_row']) * Z), ((x + w_) * Z, (y + info['split_row']) * Z)], fill=(255, 230, 0, 255), width=2)
            cx_, cy_, cw_, ch_ = info['collision']
            d.rectangle(((x + cx_) * Z, (y + cy_) * Z, (x + cx_ + cw_) * Z - 1, (y + cy_ + ch_) * Z - 1), outline=(255, 40, 40, 255), width=2)
        os.makedirs('data/debug', exist_ok=True)
        im.convert('RGB').save(f'data/debug/{path}')
        if path == 'trees_on_grass.png':
            im.convert('RGB').save(f'{OUT}/_contact_sheet.png')
    # defects report: purple pixels, enclosed holes (transparent pixels walled in by the sprite), clipping against the
    # sheet cell (a sprite touching its cell's edge was cut off by the sheet itself)
    for name, canvas, info in sheet_items:
        al = canvas[..., 3] > 0
        outside = np.zeros(al.shape, bool); st = [(0, x_) for x_ in range(al.shape[1])] + [(al.shape[0] - 1, x_) for x_ in range(al.shape[1])] \
            + [(y_, 0) for y_ in range(al.shape[0])] + [(y_, al.shape[1] - 1) for y_ in range(al.shape[0])]
        while st:
            y_, x_ = st.pop()
            if 0 <= y_ < al.shape[0] and 0 <= x_ < al.shape[1] and not al[y_, x_] and not outside[y_, x_]:
                outside[y_, x_] = True; st += [(y_ + 1, x_), (y_ - 1, x_), (y_, x_ + 1), (y_, x_ - 1)]
        info['holes_px'] = int((~al & ~outside).sum())
        info['purple_px'] = int(purple(canvas[al][:, :3][None]).sum())
    json.dump(report, open(f'{OUT}/trees.json', 'w'), indent=1)
    print(f'native pixel {per:.3f} px, grid offset ({px:.2f}, {py:.2f}); cells x {cols} y {rows}')
    print(f'background: frame {corner.tolist()}, cells {common.tolist()}, tolerance {KEY_TOL}; watermark: {report["watermark_removed_px"]} px removed, box {report.get("watermark_box")}')
    for n_, i in report['sprites'].items():
        print(f'  {n_:16s} {i["kind"]:5s} native {i["native_size"][0]}x{i["native_size"][1]} x{i["scale"]:<5} -> {i["size_tiles"][0]}x{i["size_tiles"][1]} tiles, canopy {i["canopy_px"]} px, '
              f'{i["colours"]} colours' + (f', split row {i["split_row"]} ({i["trunk_base_pct"]} % base), footprint {i["collision"]}' if 'split_row' in i else f', footprint {i["collision"]}'))
    print('defects: ' + '; '.join(f'{n_}: purple {i["purple_px"]}, holes {i["holes_px"]} px, margin {i["margin_to_cell_edge"]}' for n_, i in report['sprites'].items()))
    print(f'held (not cut, not registered): {sorted(HELD)}')
    print(f'registered {len(tiles)} images in tiled/tilesets/trees.tsj; all palette colours, hard alpha, no purple left')


if __name__ == '__main__':
    main()
