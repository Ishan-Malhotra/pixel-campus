"""Render a flat plan of the features file (2 px per metre) for sanity checking."""
import json, sys
from PIL import Image, ImageDraw
d = json.load(open(sys.argv[1])); S = 2
img = Image.new('RGB', (int(d['width_m'] * S), int(d['height_m'] * S)), (120, 190, 120))
dr = ImageDraw.Draw(img)
sc = lambda pts: [(x * S, y * S) for x, y in pts]
for f in d['features']:
    t = f['tags']
    if f['kind'] == 'area' and ('landuse' in t or 'leisure' in t):
        for r in f['outer']: dr.polygon(sc(r), fill=(90, 170, 90), outline=(40, 100, 40))
for f in d['features']:
    t = f['tags']
    if f['kind'] == 'line' and 'highway' in t:
        w = {'footway': 2, 'steps': 2, 'service': 5, 'residential': 7, 'unclassified': 7}.get(t['highway'], 4)
        dr.line(sc(f['pts']), fill=(200, 190, 160) if w <= 2 else (110, 110, 120), width=w * S)
for f in d['features']:
    t = f['tags']
    if f['kind'] == 'area' and 'building' in t:
        for r in f['outer']: dr.polygon(sc(r), fill=(220, 160, 150), outline=(80, 40, 40))
for f in d['features']:
    t = f['tags']; n = t.get('name')
    if not n: continue
    if f['kind'] == 'point': x, y = f['pt']; dr.ellipse((x*S-4, y*S-4, x*S+4, y*S+4), fill=(0, 0, 200))
    elif f['kind'] == 'area': xs, ys = zip(*f['outer'][0]); x, y = sum(xs)/len(xs), sum(ys)/len(ys)
    else: x, y = f['pts'][len(f['pts'])//2]
    dr.text((x * S + 5, y * S - 5), n[:22], fill=(0, 0, 0))
img.save(sys.argv[2]); print(img.size)
