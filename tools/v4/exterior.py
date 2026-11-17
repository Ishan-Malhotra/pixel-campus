"""Street-side surroundings of a building, after the user's street reference (art/reference_street.png, 2026-11-17).

The look: along the road in front of every hostel runs a footpath of grey herringbone pavers behind a black-and-white
striped kerb; big trees with red-brown painted trunks and a white band stand in tree pits on it (cut from the
reference); behind the footpath a trimmed hedge (the "wall" between road and hostel) opens at the gate, with shrubs
on the lawn behind it; a zebra crossing lies at the gate; the far side of the road gets kerb, footpath and trees too.

  python3 tools/v4/exterior.py phase1 "Krishna Bhawan"      lay it out for one slot (and remember the slot as approved)
  python3 tools/v4/exterior.py phase1 --approved            ... for every slot in data/<area>_exterior.json
  python3 tools/v4/exterior.py --assets                     only (re)make the tiles, trees and tilesets

It edits tiled/maps/<area>.tmj in place: tiles on `decor`, trees and shrubs on `props`, blocked rectangles on
`collision`. Its own objects are named `ext:<slot>`; running it again for a slot first removes what it laid there
before. blueprint.py regenerates the map without these, so the order is:
blueprint.py -> exterior.py --approved -> tiled_to_game.py.

It writes only new files (tiled/generated/*, tiled/tilesets/exterior*.tsj, data/<area>_exterior.json): no art is touched.
Every colour comes from the locked 128-colour palette of the approved art (tiled_kit.PAL_IMG; the same nearest-colour
rule as to_palette() in tools/v3/build_map.py).

Layout across the road:   building | lawn + shrubs | hedge | paver | kerb | road | kerb | paver (far side)
  - a kerb column is the tile column a road edge runs through (the game draws decor tiles over the terrain, so the
    kerb meets the asphalt cleanly);
  - DOOR_GAP tiles of the hedge stay open at the gate, paved; the kerb is dropped there; the gate and the path from
    the gap to the gate are not touched;
  - a tile is only laid on plain grass (or, in the gap, on the gate's dirt path); never in a building or slot, on a
    spawn / door object, or on an existing collision rectangle.
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tiled_kit

T = 16
DOOR_GAP = 3                 # tiles of hedge left open at each gate (paved)
MAX_ROAD_DIST = 6            # tiles: no road this close on the gate side -> the slot is skipped
TREE_EVERY = 9               # tiles between street trees (8-10 asked)
MAX_ROAD_W = 8               # tiles: a wider 'road' is a junction; the far side is not laid there
SHRUB_EVERY = 2              # rows between shrubs on the lawn behind the hedge
POST_EVERY = 5               # a fence post in the hedge every so many tiles
GEN = 'tiled/generated'
PAL = np.array(tiled_kit.PAL_IMG.getpalette()[:384], np.int32).reshape(-1, 3)
PAL_SET = {tuple(int(v) for v in c) for c in PAL}


def to_palette(rgb):
    """nearest palette colour for every pixel (the rule of tools/v3/build_map.py: to_palette)"""
    flat = np.asarray(rgb, np.int32).reshape(-1, 3)
    d = ((flat[:, None, :] - PAL[None, :, :]) ** 2).sum(axis=2)
    return PAL[np.argmin(d, axis=1)].reshape(np.asarray(rgb).shape).astype(np.uint8)


def pal(c):
    return tuple(int(v) for v in to_palette(np.array([[c]]))[0, 0])


def h2(a, b, k=0):
    return ((a * 73856093 ^ b * 19349663 ^ k * 83492791) & 0xFFFF) / 65535.0


# ===================================================================== tiles
PAVER, PAVER_LT, JOINT = pal((214, 214, 206)), pal((226, 222, 209)), pal((173, 177, 180))
KERB, KERB_DARK, KERB_SHADE = pal((246, 240, 219)), pal((73, 73, 69)), pal((159, 144, 142))
PIT, PIT_DK, PIT_RIM = pal((156, 149, 119)), pal((133, 120, 96)), pal((159, 144, 142))
H_LIT, H_LIT_HI, H_LIT_DK = pal(tiled_kit.HEDGE_LIT), pal(tiled_kit.HEDGE_LIT_HI), pal(tiled_kit.HEDGE_LIT_DK)
H_SH, H_SH_HI = pal(tiled_kit.HEDGE_SHADE), pal(tiled_kit.HEDGE_SHADE_HI)
H_OL, H_OL_DARK = pal(tiled_kit.HEDGE_OL), pal(tiled_kit.HEDGE_OL_DARK)
POST, POST_TOP = pal((95, 107, 125)), pal((187, 190, 187))


def paver(variant):
    """grey herringbone: 8 x 4 px slabs, alternately lying and standing, with 1 px joints (as in the street
    reference). The pattern repeats every 16 px, so tiles join seamlessly; variants differ in a few lighter slabs."""
    a = np.zeros((T, T, 4), np.uint8); a[..., 3] = 255
    for y in range(T):
        for x in range(T):
            i, j = x // 4, y // 4
            k = (i - j) % 4                             # 0, 1 = a lying slab (left, right half); 3, 2 = a standing one (top, bottom)
            joint = (x % 4 == 0 and k != 1) or (y % 4 == 0 and k != 2)
            slab = (i - (k == 1), j - (k == 2))
            a[y, x, :3] = JOINT if joint else (PAVER_LT if h2(slab[0] % 4, slab[1] % 4, variant + 5) < 0.2 else PAVER)
    return a


def kerb(sides, variant=0):
    """a paver tile with the kerb on the given sides (of 'lrtb'): a 4 px strip painted in 8 px black and white blocks,
    a shade line on its footpath side"""
    a = paver(variant)
    idx = np.arange(T)
    stripe = np.where((idx // 8) % 2 == 0, 0, 1)        # 0 = white block, 1 = black block
    for s in sides:
        for n in range(T):
            c = KERB if stripe[n] == 0 else KERB_DARK
            if s == 'l': a[n, 0:4, :3] = c; a[n, 4, :3] = KERB_SHADE
            if s == 'r': a[n, T - 4:T, :3] = c; a[n, T - 5, :3] = KERB_SHADE
            if s == 't': a[0:4, n, :3] = c; a[4, n, :3] = KERB_SHADE
            if s == 'b': a[T - 4:T, n, :3] = c; a[T - 5, n, :3] = KERB_SHADE
    return a


def tree_pit():
    """the square of earth a street tree stands in, with a stone rim, set in the paving"""
    a = paver(0)
    a[1:15, 1:15, :3] = PIT_RIM
    a[2:14, 2:14, :3] = PIT
    for y in range(2, 14):
        for x in range(2, 14):
            if h2(x, y, 4) < 0.16:
                a[y, x, :3] = PIT_DK
    return a


def zebra(vertical_road):
    """zebra-crossing bars on the asphalt (transparent between them): for a north-south road the bars run along it"""
    a = np.zeros((T, T, 4), np.uint8)
    for n in range(T):
        if n % 8 in (1, 2, 3, 4, 5):
            if vertical_road: a[:, n] = (*KERB, 255)
            else: a[n, :] = (*KERB, 255)
    return a


def hedge(conn, post=False):
    """a hedge piece joining the given tile sides (of 'nsew'), drawn like the hedges in front of the Clock Tower: dark
    outline (darkest on the top / left), a sunlit band on the top / left, a shaded band on the bottom / right"""
    m = np.zeros((T + 2, T + 2), bool)                 # 1 px of padding: arms run on past the tile edge
    yy, xx = np.mgrid[-1:T + 1, -1:T + 1]
    m |= (xx - 7.5) ** 2 + (yy - 7.5) ** 2 <= 6.2 ** 2
    if 'n' in conn: m |= (xx >= 2) & (xx <= 13) & (yy <= 7)
    if 's' in conn: m |= (xx >= 2) & (xx <= 13) & (yy >= 8)
    if 'w' in conn: m |= (yy >= 2) & (yy <= 13) & (xx <= 7)
    if 'e' in conn: m |= (yy >= 2) & (yy <= 13) & (xx >= 8)
    vert = ('n' in conn or 's' in conn) and not ('e' in conn or 'w' in conn)
    a = np.zeros((T, T, 4), np.uint8)
    for y in range(T):
        for x in range(T):
            if not m[y + 1, x + 1]:
                continue
            up, dn, lf, rt = m[y, x + 1], m[y + 2, x + 1], m[y + 1, x], m[y + 1, x + 2]
            if not (up and lf):
                c = H_OL_DARK
            elif not (dn and rt):
                c = H_OL
            else:
                edge = 7 + (h2(x, y, 3) < 0.35)        # ragged leaf line between sun and shade
                lit = (x < edge) if vert else (y < edge)
                if lit:
                    v = h2(x, y, 1); c = H_LIT_HI if v < 0.10 else H_LIT_DK if v > 0.90 else H_LIT
                else:
                    c = H_SH_HI if h2(x, y, 2) < 0.10 else H_SH
            a[y, x] = (*c, 255)
    if post:                                           # a slim fence post standing in the hedge line
        a[2:12, 7:9] = (*POST, 255); a[1:3, 7:9] = (*POST_TOP, 255)
    return a


# name -> (rgba, solid, wang edges that continue [top, right, bottom, left] for the Tiled terrain sets)
def tile_table():
    t = {}
    for i, n in enumerate('abc'):
        t[f'paver_{n}'] = (paver(i), False, 'paver', 'trbl')

    for n, sides in (('kerb_left', 'l'), ('kerb_right', 'r'), ('kerb_top', 't'), ('kerb_bottom', 'b'),
                     ('kerb_corner_nw', 'lt'), ('kerb_corner_ne', 'tr'), ('kerb_corner_sw', 'lb'), ('kerb_corner_se', 'rb')):
        t[n] = (kerb(sides), False, 'paver', ''.join(s for s in 'trbl' if s not in sides))
    for n, conn in (('hedge_v', 'ns'), ('hedge_h', 'ew'), ('hedge_corner_nw', 'es'), ('hedge_corner_ne', 'ws'),
                    ('hedge_corner_sw', 'ne'), ('hedge_corner_se', 'nw'), ('hedge_end_top', 's'), ('hedge_end_bottom', 'n'),
                    ('hedge_end_left', 'e'), ('hedge_end_right', 'w')):
        t[n] = (hedge(conn), True, 'hedge', conn.translate(str.maketrans('nsew', 'tbrl')))
    t['fence_post_v'] = (hedge('ns', post=True), True, None, '')
    t['fence_post_h'] = (hedge('ew', post=True), True, None, '')
    t['tree_pit'] = (tree_pit(), False, None, '')       # new tiles go at the end: ids of the ones above never change
    t['zebra_v'] = (zebra(True), False, None, '')
    t['zebra_h'] = (zebra(False), False, None, '')
    return t


# ===================================================================== street trees (cut from the user's street reference)
TREE_SRC, TREE_BOX, TREE_AXIS, TREE_SCALE = 'art/reference_street.png', (866, 4, 1010, 200), 94, 0.44
PAL_GREEN = PAL[(PAL[:, 1] > PAL[:, 0] + 8) & (PAL[:, 1] > PAL[:, 2] + 8)]


def _flood(ok, seeds):
    h, w = ok.shape
    out = np.zeros((h, w), bool); st = list(seeds)
    while st:
        y, x = st.pop()
        if 0 <= y < h and 0 <= x < w and ok[y, x] and not out[y, x]:
            out[y, x] = True
            st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return out


def tree(flip=False):
    """the big tree in the top-right of the reference: red-brown painted trunk with a white band. The lawn and the
    tree's shadow are flooded away; its canopy runs off the picture on the right and into the next tree on the left,
    so the canopy is the left half mirrored about the trunk, inside a scalloped outline. Scaled to the map."""
    x0, y0, x1, y1 = TREE_BOX
    c = np.array(Image.open(TREE_SRC).convert('RGB')).astype(int)[y0:y1, x0:x1]
    h, w = c.shape[:2]
    seeds = [(150, 12), (185, 130), (150, 60), (190, 20), (120, 20), (190, 138), (140, 135)]       # lawn and shadow, crop (y, x)
    refs = np.array([c[y, x] for y, x in seeds])
    d = np.min(np.abs(c[:, :, None, :] - refs[None, None, :, :]).sum(axis=3), axis=2)
    bg = _flood((d < 40) & ~(c[..., 0] > c[..., 1] + 20), seeds)
    lab = _flood(~bg, [(150, TREE_AXIS)])
    AX = TREE_AXIS; CW = 2 * AX
    can = np.zeros((h, CW, 4), np.uint8)
    left = np.dstack([c[:, :AX], np.where(lab[:, :AX], 255, 0)]).astype(np.uint8)
    can[:, :AX] = left; can[:, AX:] = left[:, ::-1]
    yy, xx = np.mgrid[0:h, 0:CW]
    th = np.arctan2((yy - 54) / 56.0, (xx - AX) / 93.0)
    rr = np.hypot((yy - 54) / 56.0, (xx - AX) / 93.0)
    edge = 1.0 + 0.05 * np.sin(11 * th) + 0.03 * np.sin(5 * th + 1.3)
    rows = yy < 112
    can[rows & (rr > edge), 3] = 0
    can[rows & (rr <= edge) & (rr > edge - 0.045) & (can[..., 3] > 0)] = (20, 66, 48, 255)
    trunk = lab & ((yy[:, :w] >= 100) | (c[..., 0] > c[..., 1] + 20))
    trunk[:, :60] = False; trunk[:, 140:] = False
    can[:, :w][trunk] = np.dstack([c, np.full((h, w), 255)]).astype(np.uint8)[trunk]
    keep = np.zeros((h, CW), bool); keep[:, :w] = trunk
    can[(yy >= 112) & ~keep, 3] = 0
    ys, xs = np.nonzero(can[..., 3]); can = can[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    sw, sh = round(can.shape[1] * TREE_SCALE), round(can.shape[0] * TREE_SCALE)
    small = np.array(Image.fromarray(can).resize((sw, sh), Image.LANCZOS)).astype(int)
    rgb = to_palette(small[..., :3])
    # leaves stay green: the palette has no very dark green, and the nearest colour to the canopy's shade is a grey
    leafy = (small[..., 1] >= small[..., 0]) & (small[..., 1] >= small[..., 2])
    off = leafy & ~((rgb[..., 1].astype(int) > rgb[..., 0] + 8) & (rgb[..., 1].astype(int) > rgb[..., 2] + 8))
    px = small[..., :3][off]
    rgb[off] = PAL_GREEN[np.argmin(((px[:, None, :] - PAL_GREEN[None, :, :]) ** 2).sum(axis=2), axis=1)]
    out = np.dstack([rgb, np.where(small[..., 3] >= 128, 255, 0)]).astype(np.uint8)
    return out[:, ::-1].copy() if flip else out


def assert_palette(name, rgba):
    cols = {tuple(int(v) for v in c) for c in rgba[rgba[..., 3] > 0][:, :3]}
    assert cols <= PAL_SET, f'{name}: colours outside the palette: {sorted(cols - PAL_SET)[:5]}'
    assert set(np.unique(rgba[..., 3])) <= {0, 255}, f'{name}: soft alpha'


def make_assets():
    os.makedirs(GEN, exist_ok=True)
    table = tile_table()
    names = list(table)
    cols = 8
    sheet = np.zeros((math.ceil(len(names) / cols) * T, cols * T, 4), np.uint8)
    for i, n in enumerate(names):
        assert_palette(n, table[n][0])
        sheet[(i // cols) * T:(i // cols + 1) * T, (i % cols) * T:(i % cols + 1) * T] = table[n][0]
    Image.fromarray(sheet).save(f'{GEN}/exterior_tiles.png')
    json.dump({n: i for i, n in enumerate(names)}, open(f'{GEN}/exterior_tiles.json', 'w'), indent=1)
    tiles = [{'id': i, 'type': n, **({'properties': [{'name': 'solid', 'type': 'bool', 'value': True}]} if table[n][1] else {})}
             for i, n in enumerate(names)]
    wangsets = []
    for set_name, kind, colour in (('Paver path', 'paver', '#d2c0b3'), ('Hedge', 'hedge', '#1a6c09')):
        wt = []
        for i, n in enumerate(names):
            if table[n][2] == kind:                    # edge set: 1 = the path / hedge continues through that side
                e = table[n][3]                        # wangid = [top, top-right, right, bottom-right, bottom, bottom-left, left, top-left]
                wt.append({'tileid': i, 'wangid': [int('t' in e), 0, int('r' in e), 0, int('b' in e), 0, int('l' in e), 0]})
        rep_tile = names.index('paver_a' if kind == 'paver' else 'hedge_v')
        wangsets.append({'name': set_name, 'type': 'edge', 'tile': rep_tile,
                         'colors': [{'name': set_name, 'color': colour, 'tile': rep_tile, 'probability': 1}], 'wangtiles': wt})
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'exterior',
               'image': '../generated/exterior_tiles.png', 'imagewidth': sheet.shape[1], 'imageheight': sheet.shape[0],
               'tilewidth': T, 'tileheight': T, 'tilecount': len(names), 'columns': cols, 'margin': 0, 'spacing': 0,
               'tiles': tiles, 'wangsets': wangsets}, open('tiled/tilesets/exterior.tsj', 'w'), indent=1)
    ptiles = []
    for i, (n, ww) in enumerate((('tree_street_a', False), ('tree_street_b', True))):       # b = a mirrored
        img = tree(ww)
        assert_palette(n, img)
        Image.fromarray(img).save(f'{GEN}/{n}.png')
        ptiles.append({'id': i, 'image': f'../generated/{n}.png', 'imagewidth': int(img.shape[1]), 'imageheight': int(img.shape[0]),
                       'properties': [{'name': 'prop', 'type': 'string', 'value': n},
                                      {'name': 'solid_base', 'type': 'bool', 'value': True},
                                      {'name': 'base_w', 'type': 'float', 'value': 0.2}]})
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'exterior_props',
               'tilewidth': max(t['imagewidth'] for t in ptiles), 'tileheight': max(t['imageheight'] for t in ptiles),
               'tilecount': len(ptiles), 'columns': 0, 'margin': 0, 'spacing': 0,
               'grid': {'orientation': 'orthogonal', 'width': 1, 'height': 1}, 'tiles': ptiles},
              open('tiled/tilesets/exterior_props.tsj', 'w'), indent=1)
    return names


# ===================================================================== layout for one slot
SHRUBS = ('bush', 'shrub', 'conifer', 'bush_big', 'shrub', 'flowers_red', 'bush', 'flowers_white')     # props cut from the main art


def layout(area, slot_name, M, names):
    """lays the strip for one slot into the map dict M. Returns a report dict (or {'skipped': reason})."""
    MW, MH = M['width'], M['height']
    L = {l['name'].split(' ')[0]: l for l in M['layers']}
    ground, decor = L['ground']['data'], L['decor']['data']
    slots = json.load(open(f'data/{area}_slots.json'))
    slot = next((s for s in slots if s['name'] == slot_name), None)
    if slot is None:
        return {'skipped': 'no such slot'}
    if 'gate' not in slot:
        return {'skipped': 'the slot has no gate (not a placed hostel yet)'}
    tag = f'ext:{slot_name}'

    def first_of(src):
        return next((t['firstgid'] for t in M['tilesets'] if t.get('source', '').endswith('/' + src)), None)
    for src in ('exterior_props.tsj', 'exterior.tsj'):       # exterior.tsj last: it may gain tiles later without colliding
        if first_of(src) is None:
            nxt = max(t['firstgid'] + json.load(open(os.path.join('tiled/maps', t['source'])))['tilecount'] for t in M['tilesets'])
            M['tilesets'].append({'firstgid': nxt, 'source': f'../tilesets/{src}'})
    EXT, EXTP, TERR, PROPS = first_of('exterior.tsj'), first_of('exterior_props.tsj'), first_of('terrain.tsj'), first_of('props.tsj')
    ext_n = json.load(open('tiled/tilesets/exterior.tsj'))['tilecount']
    assert EXT + ext_n <= EXTP or EXTP < EXT, 'exterior.tsj grew past the next tileset: regenerate the map with blueprint.py first'
    gid = {n: EXT + i for i, n in enumerate(names)}
    is_ext = lambda g: EXT <= g < EXT + ext_n
    prop_ts = {next(p_['value'] for p_ in t['properties'] if p_['name'] == 'prop'): t for t in json.load(open('tiled/tilesets/props.tsj'))['tiles']}
    tree_ts = json.load(open('tiled/tilesets/exterior_props.tsj'))['tiles']
    tid = lambda x, y: ground[y * MW + x] - TERR
    inb = lambda x, y: 0 <= x < MW and 0 <= y < MH
    road_at = lambda x, y: inb(x, y) and 1 <= tid(x, y) <= 15
    grass_at = lambda x, y: inb(x, y) and 64 <= tid(x, y) <= 67
    path_at = lambda x, y: inb(x, y) and 16 <= tid(x, y) <= 31

    for lname in ('props', 'collision'):               # a re-run starts clean
        L[lname]['objects'] = [o for o in L[lname]['objects'] if o.get('name') != tag]
    blocked = np.zeros((MH, MW), bool)                 # buildings, slots, spawn / door objects, existing collision, other props
    def block(x0, y0, x1, y1):
        blocked[max(0, int(y0 // T)):math.ceil(y1 / T), max(0, int(x0 // T)):math.ceil(x1 / T)] = True
    for o in L['buildings']['objects']:
        y0 = o['y'] - (o['height'] if 'gid' in o else 0)
        block(o['x'], y0, o['x'] + o['width'], y0 + o['height'])
    for o in L['events']['objects']:
        if (o.get('type') or o.get('class')) in ('spawn', 'door') or o.get('name') == 'spawn':
            block(o['x'], o['y'], o['x'] + 1, o['y'] + 1)
    for o in L['collision']['objects']:
        block(o['x'], o['y'], o['x'] + o['width'], o['y'] + o['height'])
    for o in L['props']['objects']:                    # someone else's props (the front garden's, another slot's strip)
        if 'gid' in o:
            block(o['x'] + o['width'] * 0.3, o['y'] - 8, o['x'] + o['width'] * 0.7, o['y'])

    bty = f'data/{area}_beautify.json'                 # streets redone by tools/v4/beautify.py are left to it
    if os.path.exists(bty):
        for ar in json.load(open(bty)).get('areas', []):
            c0, r0, c1, r1 = ar['box']
            blocked[max(0, r0):r1 + 1, max(0, c0):c1 + 1] = True
    gx, gy, d = slot['gate']                           # d = -1: the gate (and the road) is on the west side
    wall_col = slot['x'] if d < 0 else slot['x'] + slot['w'] - 1
    gate_row = gy // T
    gap_rows = set(range(gate_row - DOOR_GAP // 2, gate_row - DOOR_GAP // 2 + DOOR_GAP))
    zebra_rows = {gate_row - 1, gate_row}
    rows = range(max(0, slot['y'] - 1), min(MH, slot['y'] + slot['h'] + 1))

    # the road's two edge columns per row: the near one (first road tile from the wall), the far one (last road tile)
    near, far = {}, {}
    for y in rows:
        for k in range(1, MAX_ROAD_DIST + 1):
            x = wall_col + d * k
            if road_at(x, y):
                near[y] = x
                x2 = x
                while road_at(x2 + d, y) and abs(x2 + d - x) <= MAX_ROAD_W:
                    x2 += d
                if x2 != x and not road_at(x2 + d, y):
                    far[y] = x2
                break
    for y in [y for y in near if blocked[y, near[y]]]:  # rows inside a beautify area belong to it
        near.pop(y); far.pop(y, None)
    if not near:
        return {'skipped': f'no road within {MAX_ROAD_DIST} tiles on the gate side'}
    for y in rows:                                     # re-run: clear this strip's earlier tiles
        for k in range(0, MAX_ROAD_DIST + MAX_ROAD_W + 6):
            x = wall_col + d * k
            if inb(x, y) and is_ext(decor[y * MW + x]):
                decor[y * MW + x] = 0

    kerbs, pavers, hedges, skipped = {}, set(), set(), []          # kerbs: (x, y) -> (dropped, direction of the road)

    def side(edge, rd, with_hedge, dropped_rows, label):
        """one side of the road: rd = direction from the footpath to the road"""
        inward = -rd
        for y, x in edge.items():
            kx, px, hx = x, x + inward, x + 2 * inward
            in_gap = with_hedge and y in gap_rows
            ok_ground = lambda cx: grass_at(cx, y) or (in_gap and (path_at(cx, y) or road_at(cx, y)))
            if not inb(px, y) or blocked[y, kx] or decor[y * MW + kx]:
                skipped.append((label, y, 'kerb tile occupied')); continue
            if blocked[y, px] or decor[y * MW + px] or not ok_ground(px):
                skipped.append((label, y, 'paver tile occupied / not grass')); continue
            kerbs[(kx, y)] = (y in dropped_rows, rd)
            pavers.add((px, y))
            if not with_hedge:
                continue
            if (hx - wall_col) * inward >= 0:
                skipped.append((label, y, 'no room for the hedge')); continue
            if blocked[y, hx] or decor[y * MW + hx] or not ok_ground(hx):
                skipped.append((label, y, 'hedge tile occupied / not grass')); continue
            (pavers if in_gap else hedges).add((hx, y))
        # where the road's edge jogs, the smoothed road leaves a wedge of verge beside the kerb: if the tile on the
        # road side of a kerb is itself only partly road, the footpath takes that tile too (it becomes the kerb)
        for (x, y), (drop, r_) in list(kerbs.items()):
            o = (x + rd, y)
            if r_ == rd and road_at(*o) and tid(*o) != 15 and o not in kerbs and not blocked[y, x + rd] and not decor[y * MW + x + rd]:
                kerbs[o] = (drop, rd)
                del kerbs[(x, y)]; pavers.add((x, y))

    side(near, d, True, gap_rows, 'near')
    side({y: x for y, x in far.items() if (near[y], y) in kerbs or (near[y] + d, y) in kerbs}, -d, False, zebra_rows, 'far')
    # where the hedge line jogs by a column between two rows, it turns the corner through the tile beside it
    for (hx, y) in sorted(hedges):
        for dy in (-1, 1):
            for dx in (-1, 1):
                if (hx + dx, y + dy) in hedges and (hx, y + dy) not in hedges and (hx + dx, y) not in hedges:
                    link = (hx + dx, y) if dx == -d else (hx, y + dy)         # the linking tile lies on the building side
                    if grass_at(*link) and not blocked[link[1], link[0]] and link not in pavers and link not in kerbs:
                        hedges.add(link)

    foot = set(kerbs) | pavers
    out = {}
    pv = lambda x, y: gid['paver_' + 'abc'[int(h2(x, y, 9) * 3) % 3]]
    for (x, y) in pavers:
        out[(x, y)] = pv(x, y)
    for (x, y), (dropped, rd) in kerbs.items():
        if dropped:
            out[(x, y)] = pv(x, y); continue
        sides = ''
        for s_, (dx, dy) in (('l', (-1, 0)), ('r', (1, 0)), ('t', (0, -1)), ('b', (0, 1))):
            n_ = (x + dx, y + dy)
            # the road side always; top / bottom only at a jog inside the strip (not at the strip's two ends)
            if n_ not in foot and ((dx == rd and dy == 0) or (dx == 0 and road_at(*n_) and (y + dy) in near)):
                sides += s_
        key = ''.join(sorted(sides))
        out[(x, y)] = gid[{'l': 'kerb_left', 'r': 'kerb_right', 't': 'kerb_top', 'b': 'kerb_bottom', 'lt': 'kerb_corner_nw',
                           'rt': 'kerb_corner_ne', 'bl': 'kerb_corner_sw', 'br': 'kerb_corner_se'}.get(key, 'kerb_left' if rd < 0 else 'kerb_right')]
    run = 0
    for (x, y) in sorted(hedges):
        conn = ''.join(s_ for s_, (dx, dy) in (('n', (0, -1)), ('s', (0, 1)), ('e', (1, 0)), ('w', (-1, 0))) if (x + dx, y + dy) in hedges)
        name = {'ns': 'hedge_v', 'ew': 'hedge_h', 'se': 'hedge_corner_nw', 'sw': 'hedge_corner_ne', 'ne': 'hedge_corner_sw',
                'nw': 'hedge_corner_se', 's': 'hedge_end_top', 'n': 'hedge_end_bottom', 'e': 'hedge_end_left', 'w': 'hedge_end_right'}.get(conn, 'hedge_v')
        run += 1
        if name in ('hedge_v', 'hedge_h') and run % POST_EVERY == 0:
            name = 'fence_post_' + name[-1]
        out[(x, y)] = gid[name]
    # zebra crossing at the gate: bars on the asphalt between the two (dropped) kerbs
    zebra = []
    for y in sorted(zebra_rows):
        ks = sorted(x for (x, yy_) in kerbs if yy_ == y)
        if len(ks) == 2 and all(kerbs[(x, y)][0] for x in ks):
            for x in range(ks[0] + 1, ks[1]):
                if road_at(x, y) and not blocked[y, x] and not decor[y * MW + x] and (x, y) not in out:
                    out[(x, y)] = gid['zebra_v']; zebra.append((x, y))

    oid = M['nextobjectid']
    def obj(layer, o):
        nonlocal oid
        L[layer]['objects'].append({'id': oid, 'name': tag, 'rotation': 0, 'visible': True, **o}); oid += 1
    # street trees in pits on the paver columns: near side, then the far side half a spacing on
    trees = []
    def plant_trees(cells, start_off, k0):
        ys = sorted(y for (_, y) in cells)
        if not ys:
            return
        k = k0
        for (x, y) in sorted(cells, key=lambda c: c[1]):
            if (y - ys[0] - start_off) % TREE_EVERY or any(abs(y - g) <= 2 for g in gap_rows):
                continue
            if blocked[max(0, y - 6):y + 1, x].any():  # its crown would reach into a building / beautify area
                continue
            ts = tree_ts[k % 2]; k += 1
            w_, h_ = ts['imagewidth'], ts['imageheight']
            bx, by = x * T + T // 2 - w_ // 2, (y + 1) * T - 2
            out[(x, y)] = gid['tree_pit']
            obj('props', {'type': 'prop', 'gid': EXTP + ts['id'], 'x': bx, 'y': by, 'width': w_, 'height': h_})
            obj('collision', {'type': 'collision', 'x': x * T + 2, 'y': by - 8, 'width': 12, 'height': 8})
            trees.append((x, y))
    near_p = {(x, y) for (x, y) in pavers if y in near and x == near[y] - d and (x, y) not in hedges}
    far_p = {(x, y) for (x, y) in pavers if y in far and x == far[y] + d}
    plant_trees(near_p, 2, 0)
    plant_trees(far_p, 2 + TREE_EVERY // 2, 1)
    # shrubs on the lawn between the hedge and the building
    shrubs = []
    for y in sorted({y for (_, y) in hedges}):
        if (y - slot['y']) % SHRUB_EVERY or any(abs(y - g) <= 1 for g in gap_rows) or not (slot['y'] <= y < slot['y'] + slot['h']):
            continue
        hx = max(x for (x, yy_) in hedges if yy_ == y) if d < 0 else min(x for (x, yy_) in hedges if yy_ == y)
        lawn = [x for x in range(min(hx, wall_col) + 1, max(hx, wall_col)) if grass_at(x, y) and not blocked[y, x] and (x, y) not in out]
        if not lawn:
            continue
        x = lawn[int(h2(y, slot['x'], 6) * len(lawn)) % len(lawn)]
        name = SHRUBS[int(h2(y, x, 7) * len(SHRUBS)) % len(SHRUBS)]
        if name not in prop_ts:
            continue
        ts = prop_ts[name]
        obj('props', {'type': 'prop', 'gid': PROPS + ts['id'], 'x': x * T + T // 2 - ts['imagewidth'] // 2, 'y': (y + 1) * T - 3,
                      'width': ts['imagewidth'], 'height': ts['imageheight']})
        shrubs.append((x, y, name))

    # checks, then write
    for (x, y), g in out.items():
        assert not blocked[y, x], f'tile on a building / event / collision at {(x, y)}'
        assert decor[y * MW + x] == 0, f'decor already used at {(x, y)}'
    assert not any(y in gap_rows for (_, y) in hedges), 'hedge inside the door gap'
    for (x, y), g in out.items():
        decor[y * MW + x] = g
    for x in sorted({c[0] for c in hedges}):           # collision: hedge runs merged down each column
        ys = sorted(y for (hx, y) in hedges if hx == x)
        start = prev = ys[0]
        for y in ys[1:] + [None]:
            if y is None or y != prev + 1:
                obj('collision', {'type': 'collision', 'x': x * T, 'y': start * T, 'width': T, 'height': (prev - start + 1) * T})
                start = y
            prev = y
    M['nextobjectid'] = oid
    xs = [x for x, _ in out]
    return {'rows': [min(near), max(near)], 'near_kerb_cols': sorted(set(near.values())), 'far_kerb_cols': sorted(set(far.values())),
            'gap_rows': sorted(gap_rows), 'tiles': len(out), 'hedge_tiles': len(hedges), 'zebra_tiles': len(zebra), 'trees': len(trees),
            'shrubs': len(shrubs), 'skipped_rows': len(skipped), 'skipped_why': sorted({f'{a_}: {c_}' for a_, _, c_ in skipped}),
            'box_px': [(min(xs + [wall_col]) - 4) * T, (min(near) - 3) * T, (max(xs + [wall_col]) + 5) * T, (max(near) + 4) * T]}


def validate(path):
    """re-open the map the way Tiled would: sizes, tilesets present, every gid inside a tileset"""
    M = json.load(open(path))
    n = M['width'] * M['height']
    spans = []
    for t in M['tilesets']:
        f = os.path.normpath(os.path.join(os.path.dirname(path), t['source']))
        assert os.path.exists(f), f'missing tileset {f}'
        ts = json.load(open(f))
        if 'image' in ts:
            assert os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), ts['image']))), f'missing image of {f}'
        for tl in ts.get('tiles', []):
            if 'image' in tl:
                assert os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), tl['image']))), f'missing {tl["image"]}'
        spans.append((t['firstgid'], t['firstgid'] + ts['tilecount']))
    spans.sort()
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), f'tileset gid ranges overlap: {spans}'
    ok = lambda g: g == 0 or any(a <= (g & 0x1FFFFFFF) < b for a, b in spans)
    ids = set()
    for l in M['layers']:
        if l['type'] == 'tilelayer':
            assert len(l['data']) == n, f'layer {l["name"]}: {len(l["data"])} tiles, expected {n}'
            assert all(ok(g) for g in set(l['data'])), f'layer {l["name"]}: a gid outside every tileset'
        elif l['type'] == 'objectgroup':
            for o in l['objects']:
                assert o['id'] not in ids, f'duplicate object id {o["id"]}'
                ids.add(o['id'])
                assert 'gid' not in o or ok(o['gid']), f'object {o["id"]}: gid outside every tileset'
    assert M['nextobjectid'] > max(ids), 'nextobjectid too low'
    return f'{path}: valid ({len(M["layers"])} layers, {len(M["tilesets"])} tilesets, {len(ids)} objects)'


if __name__ == '__main__':
    names = make_assets()
    print(f'assets: {len(names)} tiles -> {GEN}/exterior_tiles.png, 2 trees; all colours in the palette')
    if '--assets' in sys.argv or len(sys.argv) < 3:
        sys.exit(0)
    area = sys.argv[1]
    listf = f'data/{area}_exterior.json'
    approved = json.load(open(listf))['slots'] if os.path.exists(listf) else []
    todo = approved if sys.argv[2] == '--approved' else [sys.argv[2]]
    path = f'tiled/maps/{area}.tmj'
    M = json.load(open(path))
    for name in todo:
        rep = layout(area, name, M, names)
        print(name, '->', json.dumps(rep))
        if 'skipped' not in rep and name not in approved:
            approved.append(name)
    json.dump(M, open(path, 'w'))
    json.dump({'slots': approved}, open(listf, 'w'), indent=1)
    print(validate(path))
