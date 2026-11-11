"""Parse an OSM XML extract into projected features (metres, origin = bbox SW corner, y grows south).

Usage: python3 -I tools/osm_parse.py data/osm/slice_main.osm data/slice_main.features.json
"""
import json, math, sys
import xml.etree.ElementTree as ET

src, dst = sys.argv[1], sys.argv[2]
root = ET.parse(src).getroot()
b = root.find('bounds')
minlat, minlon = float(b.get('minlat')), float(b.get('minlon'))
maxlat, maxlon = float(b.get('maxlat')), float(b.get('maxlon'))
R = 6378137.0
kx = math.radians(1) * R * math.cos(math.radians((minlat + maxlat) / 2))
ky = math.radians(1) * R
W, H = (maxlon - minlon) * kx, (maxlat - minlat) * ky

def proj(lat, lon):
    return [round((lon - minlon) * kx, 2), round((maxlat - lat) * ky, 2)]

nodes, node_tags = {}, {}
for n in root.iter('node'):
    nodes[n.get('id')] = proj(float(n.get('lat')), float(n.get('lon')))
    t = {g.get('k'): g.get('v') for g in n.iter('tag')}
    if t: node_tags[n.get('id')] = t
ways = {}
for w in root.iter('way'):
    ways[w.get('id')] = ([nodes[r.get('ref')] for r in w.iter('nd') if r.get('ref') in nodes],
                         {g.get('k'): g.get('v') for g in w.iter('tag')})

def stitch(segs):
    """Join open way segments into closed rings."""
    rings, segs = [], [list(s) for s in segs if len(s) > 1]
    while segs:
        ring = segs.pop(0)
        changed = True
        while ring[0] != ring[-1] and changed:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == ring[-1]: ring += s[1:]
                elif s[-1] == ring[-1]: ring += s[::-1][1:]
                elif s[-1] == ring[0]: ring = s[:-1] + ring
                elif s[0] == ring[0]: ring = s[::-1][:-1] + ring
                else: continue
                segs.pop(i); changed = True; break
        rings.append(ring)
    return rings

feats = []
used_in_rel = set()
for r in root.iter('relation'):
    t = {g.get('k'): g.get('v') for g in r.iter('tag')}
    if t.get('type') != 'multipolygon': continue
    outer, inner = [], []
    for m in r.iter('member'):
        if m.get('type') != 'way' or m.get('ref') not in ways: continue
        (outer if m.get('role') != 'inner' else inner).append(ways[m.get('ref')][0])
        used_in_rel.add(m.get('ref'))
    if outer:
        feats.append({'id': 'r' + r.get('id'), 'kind': 'area', 'tags': t,
                      'outer': stitch(outer), 'inner': stitch(inner)})
for wid, (pts, t) in ways.items():
    if not t or len(pts) < 2: continue
    closed = pts[0] == pts[-1] and len(pts) > 3
    is_area = closed and t.get('area') != 'no' and 'highway' not in t or ('highway' in t and t.get('area') == 'yes')
    if is_area:
        feats.append({'id': 'w' + wid, 'kind': 'area', 'tags': t, 'outer': [pts], 'inner': []})
    else:
        feats.append({'id': 'w' + wid, 'kind': 'line', 'tags': t, 'pts': pts})
for nid, t in node_tags.items():
    feats.append({'id': 'n' + nid, 'kind': 'point', 'tags': t, 'pt': nodes[nid]})

json.dump({'width_m': round(W, 1), 'height_m': round(H, 1),
           'bbox': [minlat, minlon, maxlat, maxlon], 'features': feats}, open(dst, 'w'))
print(f'{W:.0f}m x {H:.0f}m, {len(feats)} features')
for f in feats:
    t = f['tags']
    if 'building' in t or 'name' in t or 'highway' in t and f['kind'] == 'line' and t['highway'] not in ('footway',):
        loc = f.get('pt') or (f['outer'][0][0] if f['kind'] == 'area' else f['pts'][0])
        print(f"{f['id']:>12} {f['kind']:5} {t.get('name','-')[:28]:28} b={t.get('building','')[:10]:10} lv={t.get('building:levels','')} hw={t.get('highway','')} @{loc}")
