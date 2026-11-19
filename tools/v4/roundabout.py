"""The Gandhi statue roundabout (Ram Marg x Gandhi Marg): a round island, a ring road, curved kerbs, footpaths, hedges.

  python3 tools/v4/roundabout.py            (repo root; deterministic; run AFTER beautify.py, before tiled_to_game.py)

Pipeline: blueprint.py -> exterior.py --approved -> beautify.py phase1 hostels -> roundabout.py -> tiled_to_game.py

Approved plan (user, 2026-11-20, "plan A"): island 10 tiles across (the stamp from tools/v4/statue_island.py), a ring of
asphalt 4 tiles wide round it, the four arms at their own widths and positions. Centre: tile (64.5, 201.5), in line
with Ram Marg (N) and Gandhi Marg (E); the two service roads (W towards SAC, S) are 1/2 tile off and flare in.

How: kerbs made of 16 px tiles cannot curve, so the junction is generated pixel by pixel from a distance field (the
"signed distance" to the asphalt) and cut back into 16 px tiles:
  asphalt (d < 0) | striped kerb 0-4 px | shade line 4-5 | herringbone pavers 5-64 (3 tiles + the kerb tile) |
  hedge 66-78 | lawn
which are exactly the bands beautify.py lays along a straight road, so straight stretches come out like its tiles.
The arms join the ring with a smooth fillet (a smooth minimum of the distances, FILLET px). Textures are the street
tiles themselves (asphalt, pavers, grass), sampled in the map's tile grid; kerb stripes run in 8 px blocks (world
coordinates on the straight arms, arc length on the ring); hedges are coloured by the rule of exterior.hedge() (dark
outline, sunlit band on the upper / left side, shaded band below).

Per 16 px cell of the zone: a cell whose layout is the same as before (the straight roads) keeps its tile; any other
cell gets the generated pixels, reusing an existing street tile when identical, else a new tile in
tiled/generated/roundabout/roundabout_tiles.png (tileset tiled/tilesets/roundabout.tsj).

Also: zebra crossings (2 tiles) with kerb ramps on both sides on each arm, on the first straight stretch past the
fillet; dashed centre lines on Ram Marg and Gandhi Marg up to the ring (the service roads have none elsewhere either);
no lane circle on the ring (LANE_CIRCLE, removed at the user's request); the island stamp (buildings layer + its top on `above`); collision rectangles for the
island and the new hedge; a "Gandhi Statue" zone for the name banner. beautify.py's trees, shrubs, lamps, bins,
barricades and shadows inside CLEAR_R are removed (the user: no props in the roundabout for now).
Writes only tiled/maps/phase1.tmj (layers decor, buildings, props, above, shadows, collision, events; its tileset
list), tiled/generated/roundabout/*, tiled/tilesets/roundabout.tsj, data/phase1_roundabout.json,
data/debug/roundabout_*.png. Reruns remove what it added before (objects named rb:*).
"""
import json, math, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exterior as EX

MAP = 'tiled/maps/phase1.tmj'
GEN = 'tiled/generated/roundabout'
T = 16
ISLAND_R = 80                           # the stamp's kerb circle
RING_R = ISLAND_R + 4 * T               # outer edge of the ring's asphalt (plan A: ring 4 tiles)
FILLET = 40                             # px: how far the arm-ring joins are rounded
KERB_W, SHADE_AT, PAVER_TO = 4, 4, 64   # bands from the asphalt edge (px), as beautify.py (kerb tile + 3 paver tiles)
HEDGE_FROM, HEDGE_TO = 66, 78           # the hedge in its 16 px band (exterior.hedge(): rows 2..13)
LANE_R = (ISLAND_R + RING_R) / 2        # the dashed lane circle
LANE_CIRCLE = False                     # user 2026-11-20: "remove the dashed lane circle"
CLEAR_R = 16.5 * T                      # beautify's props / shadows / canopies removed within this radius
SOURCE = 'rb:roundabout.py'             # marks this script's zone events (reruns remove them)


def arm(name, axis, c, hw, d, dash):
    """an arm: axis 'v' runs north-south; c = its centre line (tiles), hw = half its asphalt width (tiles), d = which
    way it leaves the centre (-1 north / west, +1 south / east), dash = it has a dashed centre line"""
    return dict(name=name, axis=axis, c=c * T, hw=hw * T, dir=d, dash=dash)


# every roundabout: centre (tiles), its statue (statues.tsj, tools/v4/statue_island.py), banner name, the cells
# generated [c0, r0, c1, r1) (centre +- 17.5 tiles), the arms (read off beautify's decor layer, 2026-11-20)
ROUNDABOUTS = [
    dict(key='gandhi', label='Gandhi Statue', centre=(64.5, 201.5), zone=(47, 184, 83, 220),
         arms=[arm('N Ram Marg', 'v', 64.5, 1.5, -1, True), arm('E Gandhi Marg', 'h', 201.5, 1.5, +1, True),
               arm('W service road (SAC)', 'h', 201.0, 1.0, -1, False), arm('S service road', 'v', 64.0, 1.0, +1, False)]),
    # user 2026-11-20: "similarly place the patel statue". Krishna Marg (N-S, cols 107-109) x Gandhi Marg (rows 200-202);
    # OSM: statue n3404339403 at tile (110.0, 201.6), roundabout w285871636 (not drawn by blueprint.py)
    dict(key='patel', label='Patel Statue', centre=(108.5, 201.5), zone=(91, 184, 127, 220),
         arms=[arm('N Krishna Marg', 'v', 108.5, 1.5, -1, True), arm('E Gandhi Marg', 'h', 201.5, 1.5, +1, True),
               arm('W Gandhi Marg', 'h', 201.5, 1.5, -1, True), arm('S Krishna Marg', 'v', 108.5, 1.5, +1, True)]),
]
CX = CY = 0.0; ARMS = []; ZONE = None   # the roundabout being built (set by use())


def use(rb):
    global CX, CY, ARMS, ZONE
    CX, CY = rb['centre'][0] * T, rb['centre'][1] * T
    ARMS, ZONE = rb['arms'], rb['zone']


KERB, KERB_DARK, SHADE = np.array(EX.KERB), np.array(EX.KERB_DARK), np.array(EX.KERB_SHADE)
H_OL, H_OL_DARK = np.array(EX.H_OL), np.array(EX.H_OL_DARK)
H_LIT, H_LIT_HI, H_LIT_DK, H_SH, H_SH_HI = (np.array(c) for c in (EX.H_LIT, EX.H_LIT_HI, EX.H_LIT_DK, EX.H_SH, EX.H_SH_HI))
AS, KB, SH, PV, HG, GR = range(6)       # pixel classes: asphalt, kerb stripe, shade line, paver, hedge, lawn


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def arm_sdf(arm, X, Y, through=False):
    """distance to the arm's asphalt strip (negative inside); through=True: the road runs on through the junction"""
    across, along = (X, Y) if arm['axis'] == 'v' else (Y, X)
    centre_along = CY if arm['axis'] == 'v' else CX
    e1 = np.abs(across - arm['c']) - arm['hw']
    if through:
        return e1
    e2 = -(along - centre_along) * arm['dir']           # > 0 on the wrong side of the centre
    q1, q2 = np.maximum(e1, 0), np.maximum(e2, 0)
    return np.hypot(q1, q2) + np.minimum(np.maximum(e1, e2), 0)


def dist(X, Y):
    """distance to the new asphalt (negative inside): the ring, the arms, joined by a smooth minimum (the fillets)"""
    d = np.hypot(X - CX, Y - CY) - RING_R
    for a in ARMS:
        d = smin(d, arm_sdf(a, X, Y), FILLET)
    return d


def layout(d, X, Y):
    """class of every pixel from its distance to the asphalt; plus the hedge mask"""
    cls = np.full(d.shape, GR, np.int8)
    cls[d < 0] = AS
    cls[(d >= 0) & (d < KERB_W)] = KB
    cls[(d >= SHADE_AT) & (d < SHADE_AT + 1)] = SH
    cls[(d >= SHADE_AT + 1) & (d < PAVER_TO)] = PV
    cls[(d >= HEDGE_FROM) & (d < HEDGE_TO)] = HG
    return cls


class Street:
    """the street tiles (street.tsj) and the map's other tilesets"""
    def __init__(self, M):
        self.refs = {os.path.basename(r['source']): r for r in M['tilesets']}
        self.first = self.refs['street.tsj']['firstgid']
        st = tsj(self.refs['street.tsj']['source'])
        self.atlas = np.array(Image.open(os.path.join('tiled/tilesets', st['image'])).convert('RGBA'))
        self.cols = st['columns']
        self.sid = {t['type']: t['id'] for t in st['tiles']}
        self.sname = {self.first + t['id']: t['type'] for t in st['tiles']}
        self.px_to_gid = {}
        for n, i in self.sid.items():
            t = self.tile(n)
            if t[..., 3].min() == 255:
                self.px_to_gid.setdefault(t[..., :3].tobytes(), self.first + i)

    def tile(self, name):
        i = self.sid[name]; c = self.cols
        return self.atlas[(i // c) * T:(i // c + 1) * T, (i % c) * T:(i % c + 1) * T]


def tsj(src):
    return json.load(open(os.path.join('tiled/maps', src)))


def build_cells(M, S, new_tiles, new_index):
    """the current roundabout (use()): generate its pixels and decide every cell of its zone"""
    MW = M['width']
    L = {l['name'].split(' ')[0]: l for l in M['layers']}
    stile, sid, st_first, px_to_gid = S.tile, S.sid, S.first, S.px_to_gid
    # ------------------------------------------------------------------ the distance field over the zone
    c0, r0, c1, r1 = ZONE
    ox, oy = c0 * T, r0 * T
    H, W = (r1 - r0) * T, (c1 - c0) * T
    Yi, Xi = np.mgrid[0:H, 0:W]
    X, Y = Xi + ox + 0.5, Yi + oy + 0.5
    rad = np.hypot(X - CX, Y - CY)
    arm_d = [arm_sdf(a, X, Y) for a in ARMS]
    d = dist(X, Y)
    cls = layout(d, X, Y)
    # the old layout (the crossing as beautify.py laid it: the four arms, each its own road, meeting square at the
    # centre) for keep / replace. (Not roads running through: W and E are different roads on different centre lines,
    # and treating E as running through kept two stubs of the W arm's hedge on the new footpath; fixed 2026-11-20.)
    d_old = np.minimum.reduce([arm_sdf(a, X, Y) for a in ARMS])
    cls_old = layout(d_old, X, Y)

    # ------------------------------------------------------------------ pixels
    def cell_variant(c, r, k, n):
        return int(EX.h2(c, r, k) * n) % n
    rgb = np.zeros((H, W, 3), np.uint8)
    cc_, rr_ = Xi // T + c0, Yi // T + r0                      # cell of every pixel
    lx, ly = Xi % T, Yi % T                                     # position inside its cell
    asph = [stile(f'asphalt_{i}')[..., :3] for i in range(3)]
    pav = [stile(f'paver_{i}')[..., :3] for i in range(4)]
    grs = [stile(f'grass_{i}')[..., :3] for i in range(3)]
    va = np.vectorize(lambda c, r: cell_variant(c, r, 11, 3))(cc_, rr_)
    vp = np.vectorize(lambda c, r: cell_variant(c, r, 12, 4))(cc_, rr_)
    vg = np.vectorize(lambda c, r: cell_variant(c, r, 13, 3))(cc_, rr_)
    for i in range(3):
        m = (cls == AS) & (va == i); rgb[m] = asph[i][ly[m], lx[m]]
        m = (cls == GR) & (vg == i); rgb[m] = grs[i][ly[m], lx[m]]
    for i in range(4):
        m = (cls == PV) & (vp == i); rgb[m] = pav[i][ly[m], lx[m]]
    # kerb stripes: 8 px blocks. On a straight arm, world coordinates (as the kerb tiles); on the ring, arc length
    straight = np.zeros(d.shape, bool); u = np.zeros(d.shape)
    for a, ad in zip(ARMS, arm_d):
        s = ad + FILLET <= rad - RING_R                          # this arm alone decides the distance here
        straight |= s
        u[s] = (Y if a['axis'] == 'v' else X)[s] - 0.5
    # on the curve the blocks follow the angle round the centre, stretched a little per quadrant so the pattern runs on
    # unbroken from one arm's straight kerb, round the curve, into the next arm's (a plain arc length left one block
    # 21-24 px long at each join; first try, 2026-11-20)
    theta = np.arctan2(Y - CY, X - CX) + math.pi                # 0 at the west; W, N, E, S arms at 0, pi/2, pi, 3pi/2
    rr = RING_R + KERB_W / 2
    ends = []                                                   # per arm, both kerb sides: (theta, u, sigma)
    for a in ARMS:
        across_c = CX if a['axis'] == 'v' else CY
        along_c = CY if a['axis'] == 'v' else CX
        sides = []
        for sd in (-1, 1):
            acr = a['c'] + sd * (a['hw'] + KERB_W / 2)          # the middle of the kerb strip
            off = acr - across_c
            al = along_c + a['dir'] * math.sqrt(max(0.0, (RING_R + FILLET + KERB_W / 2) ** 2 - off ** 2))
            px_, py_ = (acr, al) if a['axis'] == 'v' else (al, acr)
            th = math.atan2(py_ - CY, px_ - CX) + math.pi
            p2 = (px_, py_ + a['dir']) if a['axis'] == 'v' else (px_ + a['dir'], py_)
            th2 = math.atan2(p2[1] - CY, p2[0] - CX) + math.pi
            dth = (th2 - th + math.pi) % (2 * math.pi) - math.pi
            sigma = 1 if a['dir'] / dth > 0 else -1             # does u grow as theta grows, along this kerb?
            sides.append((th % (2 * math.pi), al - 0.5, sigma))
        ends.append(sides)
    idx = {a['name'][0]: i for i, a in enumerate(ARMS)}
    stripe_fit = []
    for qa, qb, lo in (('W', 'N', 0.0), ('N', 'E', math.pi / 2), ('E', 'S', math.pi), ('S', 'W', 1.5 * math.pi)):
        def facing(arm):                                        # the arm's kerb side that lies in this quadrant
            return next(s_ for s_ in ends[idx[arm]] if 0 < (s_[0] - lo) % (2 * math.pi) < math.pi / 2)
        thA, uA, sA = facing(qa)
        thB, uB, sB = facing(qb)
        span = (thB - thA) % (2 * math.pi)
        # trace the middle of the kerb strip (d = KERB_W / 2) along rays from the centre, thA -> thB, and measure it
        ths = thA + np.linspace(0, span, 4000)
        lo_r, hi_r = np.full(ths.shape, RING_R - 8.0), np.full(ths.shape, 600.0)
        cx_, cy_ = -np.cos(ths), -np.sin(ths)                    # theta is measured from the west (atan2 + pi)
        for _ in range(40):
            mid = (lo_r + hi_r) / 2
            inside_ = dist(CX + cx_ * mid, CY + cy_ * mid) < KERB_W / 2
            lo_r = np.where(inside_, mid, lo_r); hi_r = np.where(inside_, hi_r, mid)
        kx, ky = CX + cx_ * lo_r, CY + cy_ * lo_r
        sarc = np.concatenate([[0], np.cumsum(np.hypot(np.diff(kx), np.diff(ky)))])
        Lq = sarc[-1]
        phi = uA if sA > 0 else 8 - uA
        tgt = uB if sB > 0 else 8 - uB
        n = round((Lq - (tgt - phi)) / 16)
        k = (tgt - phi + 16 * n) / Lq
        rel = (theta - thA) % (2 * math.pi)
        m = ~straight & (rel <= span)
        u[m] = phi + k * np.interp(rel[m], ths - thA, sarc)
        stripe_fit.append({'quadrant': qa + qb, 'kerb_len_px': round(float(Lq), 1), 'stretch': round(float(k), 4)})
    block = (np.floor(u) % 16) // 8
    kb = cls == KB
    rgb[kb & (block == 0)] = KERB; rgb[kb & (block == 1)] = KERB_DARK
    rgb[cls == SH] = SHADE
    # hedges: exterior.hedge()'s rule on the curved band
    hm = cls == HG
    gy, gx = np.gradient(d)
    nrm = np.hypot(gx, gy) + 1e-9
    nx, ny = gx / nrm, gy / nrm
    p = np.pad(hm, 1)
    up, dn, lf, rt = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]
    t_ = np.where(-(nx + ny) > 0, (HEDGE_TO - 1) - d, d - HEDGE_FROM)   # depth from the sunlit (upper / left) side
    rag = np.vectorize(lambda x, y: EX.h2(x, y, 3) < 0.35)(lx, ly)
    hv1 = np.vectorize(lambda x, y: EX.h2(x, y, 1))(lx, ly)
    hv2 = np.vectorize(lambda x, y: EX.h2(x, y, 2))(lx, ly)
    lit = t_ < 5 + rag
    hc = np.where((hv2 < 0.10)[..., None], H_SH_HI, H_SH)
    hc = np.where(lit[..., None], np.where((hv1 < 0.10)[..., None], H_LIT_HI, np.where((hv1 > 0.90)[..., None], H_LIT_DK, H_LIT)), hc)
    hc = np.where((~(dn & rt))[..., None], H_OL, hc)
    hc = np.where((~(up & lf))[..., None], H_OL_DARK, hc)
    rgb[hm] = hc[hm]
    # the dashed lane circle on the ring (between the island and the outer edge)
    arc = (np.arctan2(Y - CY, X - CX) + math.pi) * LANE_R
    lane = (np.abs(rad - LANE_R) < 1) & ((np.floor(arc) % 16) < 8) & (cls == AS) & (rad > ISLAND_R + 2)
    if LANE_CIRCLE:
        rgb[lane] = KERB

    # ------------------------------------------------------------------ crossings: first straight 2 tiles past the fillet
    special = {}                                                # (c, r) -> street tile name (overrides)
    zebras = []
    for a in ARMS:
        start = RING_R + FILLET                                 # px from the centre along the arm: straight from here
        if a['axis'] == 'v':
            edge = CY + a['dir'] * start
            rows = [int(math.floor(edge / T)) - 2, int(math.floor(edge / T)) - 1] if a['dir'] < 0 else \
                   [int(math.ceil(edge / T)), int(math.ceil(edge / T)) + 1]
            cols = list(range(int((a['c'] - a['hw']) // T), int((a['c'] + a['hw']) // T)))
            for r in rows:
                for c in cols: special[(c, r)] = 'asphalt_zebra'
                special[(cols[0] - 1, r)] = 'ramp_r'; special[(cols[-1] + 1, r)] = 'ramp_l'
            zebras.append(dict(arm=a['name'], cols=cols, rows=rows))
        else:
            edge = CX + a['dir'] * start
            cols = [int(math.floor(edge / T)) - 2, int(math.floor(edge / T)) - 1] if a['dir'] < 0 else \
                   [int(math.ceil(edge / T)), int(math.ceil(edge / T)) + 1]
            rows = list(range(int((a['c'] - a['hw']) // T), int((a['c'] + a['hw']) // T)))
            for c in cols:
                for r in rows: special[(c, r)] = 'asphalt_zebra_h'
                special[(c, rows[0] - 1)] = 'ramp_b'; special[(c, rows[-1] + 1)] = 'ramp_t'
            zebras.append(dict(arm=a['name'], cols=cols, rows=rows))
    zebra_cells = {k for k, v in special.items() if v.startswith('asphalt_zebra')}
    # centre lines on the two marked roads: whole asphalt cells on the centre line, from the ring's edge outwards
    for a in ARMS:
        if not a['dash']:
            continue
        line = int(a['c'] // T)
        start = int((CY if a['axis'] == 'v' else CX) // T)       # the centre cell, then outwards one cell at a time
        for k in range(0, 30):
            along = start + a['dir'] * k
            cell = (line, along) if a['axis'] == 'v' else (along, line)
            ccx, ccy = (cell[0] + 0.5) * T, (cell[1] + 0.5) * T
            if math.hypot(ccx - CX, ccy - CY) < RING_R + T / 2 or cell in zebra_cells:
                continue
            if not (c0 <= cell[0] < c1 and r0 <= cell[1] < r1):
                break
            special.setdefault(cell, 'asphalt_dash' if a['axis'] == 'v' else 'asphalt_dash_h')

    # ------------------------------------------------------------------ cells -> tiles
    decor = L['decor']['data']
    changed, kept = {}, 0
    regen = np.zeros((H, W), bool)
    for r in range(r0, r1):
        for c in range(c0, c1):
            ys, xs = slice((r - r0) * T, (r - r0 + 1) * T), slice((c - c0) * T, (c - c0 + 1) * T)
            i = r * MW + c
            old = decor[i]
            near_ring = math.hypot((c + 0.5) * T - CX, (r + 0.5) * T - CY) < RING_R + T
            if (c, r) in special:
                g = st_first + sid[special[(c, r)]]
            elif not near_ring and np.array_equal(cls[ys, xs], cls_old[ys, xs]):
                kept += 1
                continue                                        # same layout as before: keep the tile
            else:
                b = rgb[ys, xs].tobytes()
                if b in px_to_gid:
                    g = px_to_gid[b]
                else:
                    if b not in new_index:
                        new_index[b] = len(new_tiles); new_tiles.append(rgb[ys, xs].copy())
                    g = ('new', new_index[b])
                regen[ys, xs] = True
            changed[(c, r)] = (old, g)

    return dict(changed=changed, kept=kept, regen=regen, hm=hm, ox=ox, oy=oy, H=H, W=W, zebras=zebras, stripe_fit=stripe_fit)


def place(M, S, rb, res, stat, stat_first, oid):
    """the current roundabout's objects: remove beautify's props in the circle, add the island, collision, zone"""
    MW, MH = M['width'], M['height']
    L = {l['name'].split(' ')[0]: l for l in M['layers']}
    refs = S.refs

    def inside(x, y, rr=CLEAR_R):
        return math.hypot(x - CX, y - CY) < rr
    removed = {'props': [], 'shadows': 0, 'above_cells': []}
    keep = []
    above = L['above']['data']
    for o in L['props']['objects']:
        nm = str(o.get('name', ''))
        if 'gid' in o and nm.startswith('bty:') and inside(o['x'] + o.get('width', 0) / 2, o['y'] - T / 2):
            removed['props'].append({'id': o['id'], 'gid': o['gid'], 'x': o['x'], 'y': o['y']})
            ac, ar = int(round(o['x'] / T)), int(round(o['y'] / T)) - 2          # a street tree's canopy cell
            if 0 <= ac < MW and 0 <= ar < MH and above[ar * MW + ac]:
                g = above[ar * MW + ac] & 0x1FFFFFFF
                if refs['trees.tsj']['firstgid'] <= g < refs['street_objects.tsj']['firstgid']:
                    above[ar * MW + ac] = 0; removed['above_cells'].append([ac, ar])
            continue
        keep.append(o)
    L['props']['objects'] = keep
    n0 = len(L['shadows']['objects'])
    L['shadows']['objects'] = [o for o in L['shadows']['objects']
                               if not inside(o['x'] + o.get('width', 0) / 2, o['y'] + o.get('height', 0) / 2)]
    removed['shadows'] = n0 - len(L['shadows']['objects'])

    def new_obj(layer, **kw):
        nonlocal oid
        o = dict(id=oid, rotation=0, visible=True, **kw); oid += 1
        L[layer]['objects'].append(o)
        return o
    # the island: base on `buildings` (bottom-left anchored tile object), its top on `above`
    def stile_of(part):
        return next(t for t in stat['tiles'] if t['type'] == part
                    and any(p_['name'] == 'statue' and p_['value'] == rb['key'] for p_ in t['properties']))
    base_t, top_t = stile_of('statue_base'), stile_of('statue_top')
    bx, by = int(CX - base_t['imagewidth'] / 2), int(CY + base_t['imagewidth'] / 2)      # circle centred in the lowest 11 x 11 tiles
    assert bx % T == 0 and by % T == 0
    new_obj('buildings', name=f'rb:{rb["key"]}_island', type='statue', gid=stat_first + base_t['id'], x=bx, y=by,
            width=base_t['imagewidth'], height=base_t['imageheight'])
    top_cell = (bx // T, (by - base_t['imageheight'] + top_t['imageheight']) // T - 1)
    prev_top = above[top_cell[1] * MW + top_cell[0]]
    above[top_cell[1] * MW + top_cell[0]] = stat_first + top_t['id']
    # collision: the island's rectangles + the new hedge (4 px cells mostly hedge), as rectangles
    props_ = {p_['name']: p_['value'] for p_ in base_t['properties']}
    top_y = by - base_t['imageheight']
    for x_, y_, w_, h_ in json.loads(props_['collision_rects']):
        new_obj('collision', name='rb:island', type='', x=bx + x_, y=top_y + y_, width=w_, height=h_)
    C = 4
    H, W, ox, oy = res['H'], res['W'], res['ox'], res['oy']
    hm_new = res['hm'] & res['regen']
    cellm = hm_new.reshape(H // C, C, W // C, C).mean(axis=(1, 3)) >= 0.5
    n_hedge = 0
    for rr in range(cellm.shape[0]):
        cs = np.nonzero(cellm[rr])[0]
        if not len(cs):
            continue
        for run in np.split(cs, np.nonzero(np.diff(cs) > 1)[0] + 1):
            new_obj('collision', name='rb:hedge', type='', x=ox + int(run[0]) * C, y=oy + rr * C,
                    width=(int(run[-1]) - int(run[0]) + 1) * C, height=C); n_hedge += 1
    # the name banner: a zone over the ring
    new_obj('events', name=rb['label'], type='zone', x=int(CX - RING_R), y=int(CY - RING_R), width=2 * RING_R, height=2 * RING_R,
            properties=[{'name': 'source', 'type': 'string', 'value': SOURCE}])
    kinds = {}
    for (c, r), (old, g) in res['changed'].items():
        k = S.sname.get(old, f'gid {old}').split('_')[0]
        kinds[k] = kinds.get(k, 0) + 1
    rep = {'key': rb['key'], 'centre_tiles': list(rb['centre']), 'ring_r_px': RING_R, 'island_r_px': ISLAND_R, 'fillet_px': FILLET,
           'zone': list(ZONE), 'cells_changed': len(res['changed']), 'cells_kept': res['kept'], 'old_tile_kinds_replaced': kinds,
           'zebras': res['zebras'], 'stripe_fit': res['stripe_fit'], 'island_object': [bx, by], 'top_cell': list(top_cell),
           'top_cell_had': prev_top, 'collision_rects': {'island': len(json.loads(props_['collision_rects'])), 'hedge': n_hedge},
           'removed': {'props': len(removed['props']), 'shadows': removed['shadows'], 'canopies': len(removed['above_cells'])},
           'removed_detail': removed,
           'changed_outside_junction': sorted([c, r] for (c, r) in res['changed']
                                              if math.hypot((c + .5) * T - CX, (r + .5) * T - CY) > RING_R + 4 * T)}
    return rep, oid


def main():
    M = json.load(open(MAP))
    MW = M['width']
    L = {l['name'].split(' ')[0]: l for l in M['layers']}
    # a rerun: take out what this script added before. Its two tilesets are dropped and re-added at the end with fresh
    # first gids (statues.tsj grew from 2 to 4 tiles with the Patel statue); every cell / object that used them is
    # rewritten below, so the old gids only need clearing from `above` (the statue tops)
    old = {os.path.basename(r['source']): r['firstgid'] for r in M['tilesets']}
    if 'statues.tsj' in old:
        lo = old['statues.tsj']
        above = L['above']['data']
        for i, g in enumerate(above):
            if g and lo <= (g & 0x1FFFFFFF) < old.get('roundabout.tsj', lo + 2):
                above[i] = 0
    M['tilesets'] = [r for r in M['tilesets'] if os.path.basename(r['source']) not in ('statues.tsj', 'roundabout.tsj')]
    for lname in ('buildings', 'props', 'collision', 'shadows'):
        L[lname]['objects'] = [o for o in L[lname]['objects'] if not str(o.get('name', '')).startswith('rb:')]
    L['events']['objects'] = [o for o in L['events']['objects']
                              if not any(p_.get('value') == SOURCE for p_ in o.get('properties', []))
                              and o.get('name') != 'Gandhi Statue']        # (the first version's zone had no source)
    S = Street(M)
    # ---- every roundabout's cells (new tiles shared, deduplicated)
    new_tiles, new_index, results = [], {}, []
    for rb in ROUNDABOUTS:
        use(rb)
        results.append(build_cells(M, S, new_tiles, new_index))
    # ---- tilesets
    os.makedirs(GEN, exist_ok=True)
    cols_ = 16
    rows_ = max(1, math.ceil(len(new_tiles) / cols_))
    atlas = np.zeros((rows_ * T, cols_ * T, 4), np.uint8)
    for k, tl in enumerate(new_tiles):
        atlas[(k // cols_) * T:(k // cols_ + 1) * T, (k % cols_) * T:(k % cols_ + 1) * T, :3] = tl
        atlas[(k // cols_) * T:(k // cols_ + 1) * T, (k % cols_) * T:(k % cols_ + 1) * T, 3] = 255
    Image.fromarray(atlas).save(f'{GEN}/roundabout_tiles.png')
    json.dump({'type': 'tileset', 'version': '1.10', 'tiledversion': '1.10.2', 'name': 'roundabout',
               'image': '../generated/roundabout/roundabout_tiles.png', 'imagewidth': cols_ * T, 'imageheight': rows_ * T,
               'tilewidth': T, 'tileheight': T, 'tilecount': len(new_tiles), 'columns': cols_, 'margin': 0, 'spacing': 0},
              open('tiled/tilesets/roundabout.tsj', 'w'), indent=1)

    def count(ref):
        t = tsj(ref['source']); return t.get('tilecount', len(t.get('tiles', [])))
    for name in ('statues.tsj', 'roundabout.tsj'):
        nxt = max(r_['firstgid'] + count(r_) for r_ in M['tilesets'])
        M['tilesets'].append({'firstgid': nxt, 'source': f'../tilesets/{name}'})
    S.refs = {os.path.basename(r['source']): r for r in M['tilesets']}
    rb_first, stat_first = S.refs['roundabout.tsj']['firstgid'], S.refs['statues.tsj']['firstgid']
    stat = tsj(S.refs['statues.tsj']['source'])
    decor = L['decor']['data']
    for res in results:
        for (c, r), (o_, g) in res['changed'].items():
            decor[r * MW + c] = rb_first + g[1] if isinstance(g, tuple) else g
    # any decor still pointing into the dropped tilesets' old range would now mean something else: must not happen
    lo_old = min(old.get('statues.tsj', 10 ** 9), old.get('roundabout.tsj', 10 ** 9))
    stale = [i for i, g in enumerate(decor) if g and lo_old <= g < stat_first and not any((i % MW, i // MW) in res['changed'] for res in results)]
    assert not stale, f'{len(stale)} decor cells still use the old roundabout tiles'
    # ---- objects
    oid = M['nextobjectid']; reps = []
    for rb, res in zip(ROUNDABOUTS, results):
        use(rb)
        rep, oid = place(M, S, rb, res, stat, stat_first, oid)
        reps.append(rep)
    M['nextobjectid'] = oid
    json.dump(M, open(MAP, 'w'))
    json.dump({'new_tiles': len(new_tiles), 'tilesets': {'statues': stat_first, 'roundabout': rb_first}, 'roundabouts': reps},
              open('data/phase1_roundabout.json', 'w'), indent=1)
    for rep in reps:
        print(json.dumps({k: v for k, v in rep.items() if k not in ('removed_detail', 'changed_outside_junction', 'old_tile_kinds_replaced')}))
        print(rep['key'], 'cells changed beyond 13 tiles:', len(rep['changed_outside_junction']))
    print('new tiles', len(new_tiles), 'statues firstgid', stat_first, 'roundabout firstgid', rb_first)


if __name__ == '__main__':
    main()
