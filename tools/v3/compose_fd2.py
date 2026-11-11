"""Attach FD2 (from art/reference_fd2.png) to the east of the approved Main Building map so the layout matches the
satellite view:
  - the existing loop road leaves the main map on the east and runs straight into the small roundabout at FD2's
    south-west corner (directly east of the Rotunda);
  - FD2's courtyard quad sits east of the main building; the main roof band is extended to join FD2's west wing;
  - Krishna Marg runs south from the roundabout, a road runs east along FD2's south face, M Lawns + big trees to the SE.

Only FD2, the roundabout, the roads and the trees are taken from the new image (its redrawn main building is ignored).
Writes art/composite_main_fd2.png (source for tools/v2/from_ref.py) and data/extension_fd2.json (walls + zones).
Usage (from repo root): python3 tools/v3/compose_fd2.py
"""
import json
import numpy as np
from PIL import Image

T = 16
MAIN = np.array(Image.open('art/reference_main.png').convert('RGB'))      # 1024 x 687 (approved map)
NEW = np.array(Image.open('art/reference_fd2.png').convert('RGB'))       # 1024 x 572 (generated FD2 scene)
MH, MW = MAIN.shape[:2]
DX, DY = 464, 28                     # new-image px -> composite px (roundabout lands on the main map's east road exit)
W = MW + (NEW.shape[1] - (MW - DX))  # 1488 px = 93 tiles
H = 43 * T                            # 688 px, same height as the main map
out = np.zeros((H, W, 3), np.uint8)
out[:MH, :MW] = MAIN
out[MH:, :MW] = MAIN[-1:, :]

# paint out the generator's sparkle watermark on the lawn (new-image coords)
NEW = NEW.copy()
NEW[466:500, 918:952] = NEW[466:500, 880:914]

# 1) everything east of the main map comes from the new image, shifted by (DX, DY)
for y in range(H):
    sy = y - DY
    if sy < 0:
        sy = y                                          # top strip: reuse the tree band above FD2
    elif sy >= NEW.shape[0]:
        sy = 500 + (sy - NEW.shape[0]) % 72             # bottom strip: repeat the tree/road band (tileable rows)
    out[y, MW:] = NEW[sy, MW - DX:]

# 2) the strip between the main building's east leg and FD2's west wing (new x < 602 north of the road) would show the
#    new image's redrawn main wing -> replace with lawn texture, and carry the main roof band across into FD2
GAP_X0, GAP_X1 = MW, 602 + DX                           # composite x range of the gap (1024..1066)
lawn_src = NEW[420:452, 700:732]                        # a plain patch of the new image's lawn
for y in range(0, 330 + DY):
    for x in range(GAP_X0, GAP_X1):
        out[y, x] = lawn_src[y % lawn_src.shape[0], x % lawn_src.shape[1]]
# roof band: copy one interior roof column of the main map's band (y 64..131) across the gap, keep its parapet rows
band = MAIN[60:136, 300:316]                            # interior of the main roof band
for x in range(GAP_X0 - 6, GAP_X1 + 2):
    out[60:136, x] = band[:, x % band.shape[1]]

Image.fromarray(out).save('art/composite_main_fd2.png')

# walls / zones for the extension (composite px)
fd2 = [602 + DX, 17 + DY, 1002 + DX, 361 + DY]           # FD2 footprint (entrance steps stay walkable)
ext = {
    'width': W, 'height': H,
    'solid_rects': [fd2, [GAP_X0 - 6, 60, GAP_X1 + 2, 136]],
    'solid_ellipses': [[590 + DX, 397 + DY, 46, 34]],      # roundabout island (cx, cy, rx, ry)
    'zones': [
        {'name': 'FD2', 'x': fd2[0] - 24, 'y': fd2[1] - 16, 'w': fd2[2] - fd2[0] + 48, 'h': fd2[3] - fd2[1] + 40, 'p': 1},
        {'name': 'FD2 Circle', 'x': 540 + DX, 'y': 350 + DY, 'w': 110, 'h': 95, 'p': 0},
        {'name': 'M Lawns', 'x': 640 + DX, 'y': 405 + DY, 'w': 384, 'h': 150, 'p': 1},
        {'name': 'Krishna Marg', 'x': 560 + DX, 'y': 445 + DY, 'w': 75, 'h': 200, 'p': 0},
    ],
}
json.dump(ext, open('data/extension_fd2.json', 'w'))
print(f'composite {W}x{H} px = {W // T}x{H // T} tiles')
