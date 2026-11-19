"""Roundabout islands: the user's statue art (Gandhi, Patel: STATUES) on a round lawn with a white kerb, as stamps.

  python3 tools/v4/statue_island.py          (repo root; deterministic)

Reads art/new/<key>_statue_topdown.png only (the user's art: never written). Writes, per statue <key>
  tiled/generated/statues/<key>_island_base.png       the island (kerb, lawn, paths, platform, pedestal, statue), 11 x 13 tiles
  tiled/generated/statues/<key>_island_top.png        the statue figure + upper pedestal, for the `above` layer
  tiled/generated/statues/<key>_island_collision.png  the solid part: 4 px cells inside the kerb circle
  tiled/generated/statues/<key>_island.json           every measurement
  tiled/tilesets/statues.tsj                           "collection of images" tileset (JSON, like every other tileset here)
  data/debug/statue_island_<key>_{asphalt,grass,collision}_4x.png      checks

How (Stage 2 of the roundabout request, 2026-11-20):
  1. the art is a straight top-down / front view (horizontal and vertical edges), not isometric;
  2. the white background is keyed by flood fill from the border (distance <= KEY_TOL to the corner colour), then only
     the largest piece is kept (a stray speck or a generator sparkle is dropped);
  3. the art's own pixel is 1024 / 200 = 5.12 px (measured from where its edges fall); it is sampled once per art
     pixel (centre pixel, or the darkest pixel if the cell is mostly line), alpha 0 or 255, at 1:1 (the platform is
     then 120 px = 7.5 tiles and the statue ~ 1.2x the player); white pockets enclosed by the figure become clear;
     the bronze is mapped by brightness onto one palette ramp (BRONZE_RAMP), the stone flattened and de-grained, and
     every silhouette pixel gets the art's outline colour;
  4. the island is drawn round it: lawn from the map's own grass tiles, a 1 px dark outline, a 3 px white kerb, a 1 px
     grey inner edge, stone paths to the north and south; everything snapped to the locked palette;
  5. the platform is centred on the circle; the canvas is 11 tiles wide (the circle, 160 px, is centred on a tile
     centre) and 2 tiles taller than the circle's 11 for the statue rising above it.
"""
import json, math, os, sys
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tiled_kit

# (key, the user's art, banner name). Ids in statues.tsj: 2 per statue in this order (Gandhi = 0, 1 stays fixed)
STATUES = [('gandhi', 'art/new/gandhi_statue_topdown.png', 'Gandhi Statue'),
           ('patel', 'art/new/patel_statue_topdown.png', 'Patel Statue')]
OUT = 'tiled/generated/statues'
T = 16
KEY_TOL = 30            # |r g b| sum distance to the corner white that still counts as background
D = 160                 # island diameter in px (10 tiles), outer edge of the kerb
CANVAS_W = 11 * T       # circle centred on a tile centre -> odd number of tiles
TOP = 2 * T             # canvas rows above the circle's own 11-tile square (the statue rises above the island)
CANVAS_H = TOP + CANVAS_W
CX, CY = CANVAS_W / 2, TOP + CANVAS_W / 2      # circle centre (px, may be .0 only: 88, 120)
PATH_W = 16             # stone path width
# the bronze, light to dark, all from the locked palette: khaki highlights, sage and olive-green patina, near-black
BRONZE_RAMP = [[156, 149, 119], [133, 124, 97], [91, 121, 98], [69, 90, 61], [26, 42, 40], [20, 15, 16]]
FACE_SHARE = 0.08       # see the light stone faces in cut_art
STONE_COLOURS = 14      # the platform / pedestal / plaque are flattened to this many colours before the palette snap
OUTLINE = (20, 15, 16)  # the art's outline colour (palette)
DARK_SHARE = 0.3       # a sampled cell this much covered by line pixels (luma < 90) takes the line colour
POCKET_SUM = 740        # r+g+b at or above this inside the art = enclosed white background (the stone tops out ~717)
BRONZE_BELOW_TOP = 1    # bronze may reach this many art rows below the platform's top edge (the plate under the feet)
PATH_STONE, PATH_LINE = (216, 212, 210), (185, 180, 161)    # the platform's own face and inset-line colours

PAL = np.array(tiled_kit.PAL_IMG.getpalette()[:384], np.int32).reshape(-1, 3)
PAL_SET = {tuple(int(v) for v in c) for c in PAL}


def nearest(rgb):
    flat = rgb.reshape(-1, 3).astype(np.int32)
    out = PAL[np.argmin(((flat[:, None, :] - PAL[None, :, :]) ** 2).sum(axis=2), axis=1)]
    return out.reshape(rgb.shape).astype(np.uint8)


def grid_phase(profile, per):
    xs = np.arange(len(profile))
    c = ((profile - profile.mean()) * np.exp(-2j * np.pi * xs / per)).sum()
    return (-np.angle(c) / (2 * np.pi) * per) % per


def flood_bg(src, tol):
    h, w = src.shape[:2]
    near = np.abs(src - src[0, 0]).sum(axis=2) <= tol
    bg = np.zeros((h, w), bool)
    st = [(y, x) for y in range(h) for x in (0, w - 1) if near[y, x]] + [(y, x) for x in range(w) for y in (0, h - 1) if near[y, x]]
    for p in st:
        bg[p] = True
    while st:
        y, x = st.pop()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < h and 0 <= xx < w and not bg[yy, xx] and near[yy, xx]:
                bg[yy, xx] = True; st.append((yy, xx))
    return bg


def components(m):
    """label 4-connected pieces; returns (labels, sizes)"""
    lab = np.zeros(m.shape, np.int32); sizes = [0]
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        n = len(sizes); lab[y0, x0] = n; st = [(y0, x0)]; c = 0
        while st:
            y, x = st.pop(); c += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; st.append((yy, xx))
        sizes.append(c)
    return lab, sizes


def cut_art(rep, art_path):
    src = np.array(Image.open(art_path).convert('RGB')).astype(np.int32)
    H, W = src.shape[:2]
    bg = flood_bg(src, KEY_TOL)
    fg = ~bg
    # the art's pixel grid
    ex = (np.abs(np.diff(src, axis=1)).sum(axis=2) * fg[:, 1:]).sum(axis=0).astype(float)
    ey = (np.abs(np.diff(src, axis=0)).sum(axis=2) * fg[1:, :]).sum(axis=1).astype(float)
    score = lambda p_: (abs(((ex - ex.mean()) * np.exp(-2j * np.pi * np.arange(len(ex)) / p_)).sum())
                        + abs(((ey - ey.mean()) * np.exp(-2j * np.pi * np.arange(len(ey)) / p_)).sum()))
    per = float(max(np.arange(3.0, 12.0, 0.005), key=score))
    px, py = grid_phase(ex, per), grid_phase(ey, per)
    # sample once per art pixel. The art's lines are thinner than its pixel (it is generated, not hand-pixelled), so a
    # cell that is >= DARK_SHARE line takes its darkest pixel; any other cell takes its centre pixel. (A 3 x 3 'most
    # common colour' broke the outlines and the plaque on this art's noise; tried first, 2026-11-20.)
    sx = np.arange(px + per / 2, W, per); sy = np.arange(py + per / 2, H, per)
    nh, nw = len(sy), len(sx)
    rgb = np.zeros((nh, nw, 3), np.int32); a = np.zeros((nh, nw), bool)
    LW = np.array([299, 587, 114]) / 1000
    for j, yc in enumerate(sy):
        for i, xc in enumerate(sx):
            y, x = min(H - 1, int(round(yc))), min(W - 1, int(round(xc)))
            if not fg[y, x]:
                continue
            y0, y1 = max(0, int(yc - per / 2) + 1), min(H, int(yc + per / 2))
            x0, x1 = max(0, int(xc - per / 2) + 1), min(W, int(xc + per / 2))
            cell = src[y0:y1, x0:x1].reshape(-1, 3); cf = fg[y0:y1, x0:x1].ravel()
            cell = cell[cf]; l = cell @ LW
            rgb[j, i] = cell[np.argmin(l)] if (l < 90).mean() >= DARK_SHARE else src[y, x]
            a[j, i] = True
    # pockets of the white background enclosed by the figure (between the legs, staff and robe): flood fill from the
    # border cannot reach them, so near-white art pixels become transparent
    pocket = a & (rgb.sum(axis=2) >= POCKET_SUM)
    a &= ~pocket
    # keep only the largest piece (drops specks / a generator sparkle)
    lab, sizes = components(a)
    keep = int(np.argmax(sizes))
    dropped = int(a.sum() - sizes[keep])
    a = lab == keep
    ys, xs = np.nonzero(a)
    rgb, a = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1], a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # fringing: an edge pixel lighter than the background-blend threshold (pale halo from the white background)
    pa = np.pad(a, 1)
    edge = a & ~(pa[:-2, 1:-1] & pa[2:, 1:-1] & pa[1:-1, :-2] & pa[1:-1, 2:])
    pale = edge & (rgb.sum(axis=2) > 700)
    # colours. The locked palette has no dark olives: snapping the bronze colour by colour lands on a grey, a green and a
    # brown in turn (camouflage blotches). So the bronze is mapped by brightness onto ONE ramp of palette colours.
    r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    bronze = a & (g_ - b_ >= 12) & (np.abs(r_ - g_) < 30) & (rgb.sum(axis=2) < 480)
    # only the figure and the bronze plate it stands on: the art above the platform's top edge (the platform is the
    # widest band of rows); the beige shadow lines and the plaque on the stone stay stone
    row_w = a.sum(axis=1)
    p_top = int(np.nonzero(row_w >= row_w.max() - 2)[0].min())
    bronze[p_top + BRONZE_BELOW_TOP:] = False
    lum = 0.299 * r_ + 0.587 * g_ + 0.114 * b_
    ramp = np.array(BRONZE_RAMP, np.int32)
    ramp_l = 0.299 * ramp[:, 0] + 0.587 * ramp[:, 1] + 0.114 * ramp[:, 2]
    src_l = lum[bronze]
    lo, hi = np.percentile(src_l, 2), np.percentile(src_l, 98)
    t = np.clip((src_l - lo) / max(1, hi - lo), 0, 1) * (ramp_l.max() - ramp_l.min()) + ramp_l.min()   # stretch onto the ramp
    out = rgb.copy()
    out[bronze] = ramp[np.argmin(np.abs(t[:, None] - ramp_l[None, :]), axis=1)]
    # the stone: the art's faint noise would snap to two near colours (speckle) -> flatten to a few colours first
    stone = a & ~bronze
    q = Image.fromarray(rgb.astype(np.uint8)[stone][None]).quantize(colors=STONE_COLOURS, method=Image.Quantize.MEDIANCUT,
                                                                    dither=Image.Dither.NONE).convert('RGB')
    out[stone] = nearest(np.array(q)[0][None])[0]
    # the light stone faces keep a faint grain even so: there, only the main colours (>= FACE_SHARE of the light
    # pixels each) are kept and every other light pixel takes the nearest of them; the dark details are untouched
    lum_o = out.astype(np.int32) @ np.array([299, 587, 114]) / 1000
    light = stone & ~edge & (lum_o >= 185)
    cols, cnt = np.unique(out[light], axis=0, return_counts=True)
    main = cols[cnt >= FACE_SHARE * cnt.sum()].astype(np.int32)
    lp = out[light].astype(np.int32)
    out[light] = main[np.argmin(((lp[:, None, :] - main[None, :, :]) ** 2).sum(axis=2), axis=1)]
    # then grain: a light pixel with at most 1 of its 8 neighbours in its colour, and >= 5 in another light colour,
    # takes that colour (a 1 px highlight line has 2 along itself, so it stays)
    grain = 0
    for _ in range(3):
        prev = out.copy()
        for y, x in zip(*np.nonzero(light)):
            nb = [tuple(prev[yy, xx]) for yy in (y - 1, y, y + 1) for xx in (x - 1, x, x + 1)
                  if (yy, xx) != (y, x) and 0 <= yy < a.shape[0] and 0 <= xx < a.shape[1] and light[yy, xx]]
            if not nb:
                continue
            c, n = Counter(nb).most_common(1)[0]
            if nb.count(tuple(prev[y, x])) <= 1 and n >= 5:
                out[y, x] = c; grain += 1
    # (no line closing / despeckling: with the dark-priority sampler above the art's lines come out whole)
    # the art's dark outline is ~1.2 art px wide, so sampling misses it in some rows: every silhouette pixel gets it
    out[edge] = OUTLINE
    rgb = out
    rep.update({'bronze_px': int(bronze.sum()), 'bronze_ramp': BRONZE_RAMP, 'stone_colours': STONE_COLOURS,
                'outline_px_set': int(edge.sum()), 'white_pockets_px': int(pocket.sum()), 'face_colours': main.tolist(), 'grain_px_fixed': grain})
    rep.update({'art': art_path, 'art_px': [W, H], 'native_px': round(per, 3), 'grid_offset': [round(px, 2), round(py, 2)],
                'native_size': [int(a.shape[1]), int(a.shape[0])], 'background_corner': src[0, 0].tolist(),
                'key_tolerance': KEY_TOL, 'specks_dropped_px': dropped, 'pale_edge_px': int(pale.sum())})
    a[pale] = False
    return rgb.astype(np.uint8), a


def tile_from_atlas(name):
    st = json.load(open('tiled/tilesets/street.tsj'))
    atlas = np.array(Image.open(os.path.join('tiled/tilesets', st['image'])).convert('RGB'))
    tid = next(t['id'] for t in st['tiles'] if t['type'] == name)
    c = st['columns']
    return atlas[(tid // c) * T:(tid // c + 1) * T, (tid % c) * T:(tid % c + 1) * T]


def build(key, art_path, label, first_id):
    """one statue's island; returns its two tileset entries (base, top)"""
    rep = {}
    art, art_a = cut_art(rep, art_path)
    ah, aw = art_a.shape
    # the platform: the widest run of rows (its outer rectangle); its bounding rows
    row_w = art_a.sum(axis=1)
    plat_rows = np.nonzero(row_w >= row_w.max() - 2)[0]
    p_top, p_bot = int(plat_rows.min()), int(plat_rows.max())
    plat_cols = np.nonzero(art_a[p_top:p_bot + 1].any(axis=0))[0]
    p_left, p_right = int(plat_cols.min()), int(plat_cols.max())
    # the pedestal + statue: everything above the platform, and its column span
    upper = art_a[:p_top]
    up_cols = np.nonzero(upper.any(axis=0))[0]
    rep.update({'platform_art': [p_left, p_top, p_right, p_bot], 'statue_cols_art': [int(up_cols.min()), int(up_cols.max())]})

    # ---- the island
    yy, xx = np.mgrid[0:CANVAS_H, 0:CANVAS_W]
    d = np.hypot(xx + 0.5 - CX, yy + 0.5 - CY)
    R = D / 2
    out = np.zeros((CANVAS_H, CANVAS_W, 3), np.uint8); alpha = np.zeros((CANVAS_H, CANVAS_W), bool)
    grass = [tile_from_atlas(f'grass_{i}') for i in range(3)]
    # the map's grass tiles, in the map's own tile grid (the canvas is tile-aligned), varied by a fixed pattern
    for ty in range(CANVAS_H // T):
        for tx in range(CANVAS_W // T):
            out[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T] = grass[(tx * 7 + ty * 3) % 3]
    outline, kerb, kerb_in = d >= R - 1, (d >= R - 4) & (d < R - 1), (d >= R - 5) & (d < R - 4)
    inside = d < R
    # stone paths north and south, platform edge to kerb
    art_x0 = int(CX - (p_left + p_right + 1) / 2)          # place the art so the platform is centred on the circle
    art_y0 = int(CY - (p_top + p_bot + 1) / 2)
    path = (np.abs(xx + 0.5 - CX) < PATH_W / 2) & inside & ~kerb & ~outline & ~kerb_in
    out[path] = PATH_STONE
    out[path & (np.abs(xx + 0.5 - CX) > PATH_W / 2 - 1)] = PATH_LINE                  # slab edges
    out[path & ((yy - int(CY)) % 6 == 0)] = PATH_LINE                                 # joints
    out[kerb] = (238, 236, 228); out[kerb_in] = (200, 198, 190); out[outline & inside] = (96, 98, 100)
    alpha |= inside
    # the art (platform, pedestal, statue) on top
    sub = (slice(art_y0, art_y0 + ah), slice(art_x0, art_x0 + aw))
    out[sub][art_a] = art[art_a]
    alpha[sub] |= art_a
    out = nearest(out)
    out_rgba = np.dstack([out, alpha.astype(np.uint8) * 255])

    # ---- split: the statue + upper pedestal (everything of the art above the platform's top edge) goes on `above`
    top_mask = np.zeros_like(alpha)
    top_mask[sub][:p_top] = art_a[:p_top]
    split_row = art_y0 + p_top                 # canvas row: above this, the statue/pedestal pixels are on `above`
    top_h = int(math.ceil(split_row / T) * T)
    top_rgba = np.zeros((top_h, CANVAS_W, 4), np.uint8)
    top_rgba[:top_h][top_mask[:top_h]] = out_rgba[:top_h][top_mask[:top_h]]

    # ---- collision: the kerb circle on the game's 4 px collision cells (cell centre inside the circle)
    C = 4
    cy_, cx_ = np.mgrid[0:CANVAS_H // C, 0:CANVAS_W // C]
    cell = np.hypot(cx_ * C + C / 2 - CX, cy_ * C + C / 2 - CY) < R - 1
    coll = np.kron(cell, np.ones((C, C), bool))
    rects = []                                  # one rectangle per 4 px row band: (x, y, w, h) in canvas px
    for r in range(cell.shape[0]):
        cs = np.nonzero(cell[r])[0]
        if len(cs):
            rects.append([int(cs.min() * C), int(r * C), int((cs.max() - cs.min() + 1) * C), C])

    # ---- checks
    used = {tuple(int(v) for v in c) for c in out[alpha]}
    off_pal = len(used - PAL_SET)
    alpha_vals = sorted(set(np.unique(out_rgba[..., 3]).tolist()))
    rep.update({'canvas_px': [CANVAS_W, CANVAS_H], 'canvas_tiles': [CANVAS_W // T, CANVAS_H // T], 'circle_centre_px': [CX, CY],
                'island_diameter_px': D, 'art_at_px': [art_x0, art_y0], 'split_row': split_row, 'top_png_h': top_h,
                'collision_rects': len(rects), 'colours_used': len(used), 'off_palette_colours': off_pal, 'alpha_values': alpha_vals,
                'platform_corner_dist_px': round(math.hypot((p_right - p_left + 1) / 2, (p_bot - p_top + 1) / 2), 1)})
    Image.fromarray(out_rgba).save(f'{OUT}/{key}_island_base.png')
    Image.fromarray(top_rgba).save(f'{OUT}/{key}_island_top.png')
    Image.fromarray(np.dstack([np.zeros_like(out), coll.astype(np.uint8) * 255])).save(f'{OUT}/{key}_island_collision.png')
    json.dump(rep, open(f'{OUT}/{key}_island.json', 'w'), indent=1)

    def prop(n, v):
        t = 'int' if isinstance(v, int) else 'string'
        return {'name': n, 'type': t, 'value': v}
    common = [prop('footprint_w', CANVAS_W // T), prop('footprint_h', CANVAS_W // T), prop('split_row', split_row),
              prop('collision', f'../generated/statues/{key}_island_collision.png'),
              prop('collision_rects', json.dumps(rects))]
    tiles = [{'id': first_id, 'type': 'statue_base', 'image': f'../generated/statues/{key}_island_base.png',
                     'imagewidth': CANVAS_W, 'imageheight': CANVAS_H,
                     'properties': [prop('name', label), prop('statue', key), prop('part', 'base'), prop('layer', 'buildings')] + common},
                    {'id': first_id + 1, 'type': 'statue_top', 'image': f'../generated/statues/{key}_island_top.png',
                     'imagewidth': CANVAS_W, 'imageheight': top_h,
                     'properties': [prop('name', label), prop('statue', key), prop('part', 'top'), prop('layer', 'above'),
                                    prop('footprint_w', CANVAS_W // T), prop('footprint_h', top_h // T), prop('split_row', split_row)]}]

    # ---- check renders, 4x: on asphalt and on grass, with a stand-in player behind the statue (north side)
    player = np.array(Image.open('game/public/sprites/player.png').convert('RGBA'))[:, :32]
    for name, bgtile in (('asphalt', tile_from_atlas('asphalt_0')), ('grass', tile_from_atlas('grass_0'))):
        pad = 2 * T
        bgim = np.tile(bgtile, ((CANVAS_H + 2 * pad) // T, (CANVAS_W + 2 * pad) // T, 1))
        img = Image.fromarray(bgim).convert('RGBA')
        img.alpha_composite(Image.fromarray(out_rgba), (pad, pad))
        img.alpha_composite(Image.fromarray(player), (pad + int(CX) - 4, pad + int(CY - R) - 34))   # feet just north of the kerb
        img.alpha_composite(Image.fromarray(top_rgba), (pad, pad))
        im4 = img.resize((img.width * 4, img.height * 4), Image.NEAREST)
        dr = ImageDraw.Draw(im4)
        y = (pad + split_row) * 4; dr.line([(0, y), (im4.width, y)], fill=(255, 0, 255), width=2)
        im4.save(f'data/debug/statue_island_{key}_{name}_4x.png')
    # collision overlay (1x -> 4x)
    img = Image.fromarray(np.tile(tile_from_atlas('asphalt_0'), (CANVAS_H // T, CANVAS_W // T, 1))).convert('RGBA')
    img.alpha_composite(Image.fromarray(out_rgba))
    ov = np.zeros((CANVAS_H, CANVAS_W, 4), np.uint8); ov[coll] = (255, 0, 0, 110)
    img.alpha_composite(Image.fromarray(ov))
    img.resize((CANVAS_W * 4, CANVAS_H * 4), Image.NEAREST).save(f'data/debug/statue_island_{key}_collision_4x.png')
    print(key, json.dumps({k: rep[k] for k in ('native_px', 'native_size', 'platform_art', 'split_row', 'bronze_px',
                                                'white_pockets_px', 'off_palette_colours', 'alpha_values')}))
    return tiles


def main():
    os.makedirs(OUT, exist_ok=True)
    tiles = []
    for i, (key, art_path, label) in enumerate(STATUES):
        tiles += build(key, art_path, label, 2 * i)
    ts = {'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'statues', 'tilewidth': CANVAS_W,
          'tileheight': CANVAS_H, 'tilecount': len(tiles), 'columns': 0, 'margin': 0, 'spacing': 0, 'objectalignment': 'bottomleft',
          'grid': {'orientation': 'orthogonal', 'width': 1, 'height': 1}, 'tiles': tiles}
    json.dump(ts, open('tiled/tilesets/statues.tsj', 'w'), indent=1)


if __name__ == '__main__':
    main()
