"""Draw the original player character (chibi student) walking and cycling.

Sheet layout: 32x32 frames, 12 columns x 2 rows.
  row 0 = walk, row 1 = bike;  columns = [down0..2, left0..2, right0..2, up0..2]
  frame 0 = idle, 1 = step A, 2 = step B. Feet anchor at (16, 30).

Usage: python3 tools/draw_player.py game/public/sprites/player.png
"""
import os, sys
import numpy as np
from PIL import Image

OL = (40, 32, 56)
SKIN, SKIN_SH = (232, 176, 128), (200, 136, 104)
HAIR, HAIR_HI = (48, 40, 64), (88, 80, 120)
SHIRT, SHIRT_SH, SHIRT_HI = (232, 72, 72), (184, 48, 64), (248, 128, 112)
JEANS, JEANS_SH = (72, 104, 184), (48, 72, 144)
SHOE = (248, 248, 248)
BAG, BAG_SH = (72, 160, 120), (48, 120, 96)
EYE = (32, 32, 56)
FRAME, FRAME_SH = (40, 168, 216), (24, 112, 168)
TYRE, RIM = (56, 56, 72), (200, 200, 216)
FS = 32

def new():
    return np.zeros((FS, FS, 4), np.uint8)

def px(im, x, y, c):
    if 0 <= x < FS and 0 <= y < FS:
        im[y, x, :3] = c; im[y, x, 3] = 255

def rect(im, x0, y0, w, h, c):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w): px(im, x, y, c)

def outline(im):
    a = im[..., 3] > 0
    n = np.zeros_like(a)
    n[1:] |= a[:-1]; n[:-1] |= a[1:]; n[:, 1:] |= a[:, :-1]; n[:, :-1] |= a[:, 1:]
    for y, x in zip(*np.nonzero(n & ~a)):
        im[y, x, :3] = OL; im[y, x, 3] = 255

def head(im, d, cx, top):
    """12x10 head; d in down/left/right/up"""
    for y in range(10):
        for x in range(12):
            r = (x - 5.5) ** 2 / 36 + (y - 5) ** 2 / 30
            if r > 1.05: continue
            px(im, cx - 6 + x, top + y, SKIN)
    # hair
    for y in range(10):
        for x in range(12):
            r = (x - 5.5) ** 2 / 36 + (y - 5) ** 2 / 30
            if r > 1.05: continue
            hair = False
            if d == 'down': hair = y <= 3 or (y <= 5 and (x <= 1 or x >= 10))
            if d == 'up': hair = y <= 8
            if d == 'left': hair = y <= 3 or x >= 7
            if d == 'right': hair = y <= 3 or x <= 4
            if hair:
                px(im, cx - 6 + x, top + y, HAIR_HI if (y == 1 and 3 <= x <= 5) else HAIR)
    if d == 'down':
        px(im, cx - 3, top + 5, EYE); px(im, cx - 3, top + 6, EYE)
        px(im, cx + 2, top + 5, EYE); px(im, cx + 2, top + 6, EYE)
        px(im, cx - 5, top + 7, (240, 144, 136)); px(im, cx + 4, top + 7, (240, 144, 136))
    elif d == 'left':
        px(im, cx - 4, top + 5, EYE); px(im, cx - 4, top + 6, EYE)
    elif d == 'right':
        px(im, cx + 3, top + 5, EYE); px(im, cx + 3, top + 6, EYE)

def body(im, d, cx, top, step, sitting=False):
    # torso 10x7
    for y in range(7):
        for x in range(10):
            c = SHIRT
            if x >= 7: c = SHIRT_SH
            if x <= 1 and y < 3: c = SHIRT_HI
            px(im, cx - 5 + x, top + y, c)
    if d == 'up':  # backpack
        rect(im, cx - 4, top, 8, 6, BAG); rect(im, cx - 4, top + 4, 8, 2, BAG_SH)
    elif d == 'down':  # backpack straps
        px(im, cx - 3, top, BAG); px(im, cx - 3, top + 1, BAG); px(im, cx + 2, top, BAG); px(im, cx + 2, top + 1, BAG)
    elif d == 'left':
        rect(im, cx + 3, top, 3, 6, BAG)
    elif d == 'right':
        rect(im, cx - 6, top, 3, 6, BAG)
    # arms
    swing = [0, 1, -1][step]
    if d in ('down', 'up'):
        rect(im, cx - 6, top + 1 + max(0, swing), 1, 4, SKIN)
        rect(im, cx + 5, top + 1 + max(0, -swing), 1, 4, SKIN_SH)
    else:
        ax = cx + (swing * 2) - (0 if d == 'left' else 1)
        rect(im, ax, top + 2, 2, 4, SKIN if d == 'left' else SKIN_SH)
    if sitting: return
    # legs
    ly = top + 7
    if d in ('down', 'up'):
        lA = 4 if step != 1 else 3
        lB = 4 if step != 2 else 3
        rect(im, cx - 4, ly, 3, lA, JEANS); rect(im, cx + 1, ly, 3, lB, JEANS_SH)
        rect(im, cx - 4, ly + lA, 3, 1, SHOE); rect(im, cx + 1, ly + lB, 3, 1, SHOE)
    else:
        off = [0, 2, -2][step] * (1 if d == 'right' else -1)
        rect(im, cx - 2, ly, 4, 2, JEANS)
        rect(im, cx - 2 + off // 2, ly + 2, 3, 2, JEANS)
        rect(im, cx - 1 - off // 2, ly + 2, 3, 2, JEANS_SH)
        rect(im, cx - 2 + off // 2, ly + 4, 3, 1, SHOE)
        rect(im, cx - 1 - off // 2, ly + 4, 3, 1, SHOE)

def walk_frame(d, step):
    im = new()
    bob = 1 if step else 0
    cx = 16
    top = 30 - 21 + bob
    body(im, d, cx, top + 9, step)
    head(im, d, cx, top)
    outline(im)
    return im

def wheel_side(im, cx, cy, spin):
    for y in range(-6, 7):
        for x in range(-6, 7):
            r = (x * x + y * y) ** 0.5
            if 4.5 <= r <= 6.2: px(im, cx + x, cy + y, TYRE)
            elif r < 4.5 and ((x == 0 and spin == 0) or (y == 0 and spin == 1) or (abs(x) == abs(y) and spin == 2)):
                px(im, cx + x, cy + y, RIM)
    px(im, cx, cy, RIM)

def bike_frame(d, step):
    im = new()
    if d in ('left', 'right'):
        s = -1 if d == 'left' else 1
        wheel_side(im, 16 - 8 * s, 24, step % 3)
        wheel_side(im, 16 + 8 * s, 24, (step + 1) % 3)
        # frame: rear hub -> seat -> handlebar -> front hub
        for t in range(9):
            px(im, 16 - 8 * s + t * s, 24 - t // 2, FRAME)          # chain stay up to seat area
            px(im, 16 + t * s, 20 - (t // 3), FRAME)                # top tube
            px(im, 16 + 8 * s - (t // 3) * s, 24 - t, FRAME_SH)     # fork
        rect(im, 15 - s, 18, 3, 1, OL)                              # saddle
        px(im, 16 + 6 * s, 14, OL); px(im, 16 + 7 * s, 14, OL)     # handlebar
        # rider seated, leaning forward
        rimg = new()
        body(rimg, d, 16, 11, 0, sitting=True)
        head(rimg, d, 16 + s, 2)
        # pedalling leg
        k = [0, 2, -2][step]
        rect(rimg, 15, 18, 3, 2, JEANS)
        rect(rimg, 15 + s * 2, 20 + (1 if k > 0 else 0), 3, 3, JEANS_SH)
        rect(rimg, 15 + s * 2, 23 + (1 if k > 0 else 0), 3, 1, SHOE)
        outline(rimg)
        a = rimg[..., 3] > 0
        im[a] = rimg[a]
        outline(im)
        return im
    # front/back view: clearly visible bike - fat tyre, blue frame, wide bars with grips, basket/rack
    if d == 'down':
        rect(im, 14, 20, 4, 11, TYRE)                       # front tyre (closest to camera)
        rect(im, 15, 21 + (step * 3) % 8, 2, 2, RIM)        # spinning highlight
        rect(im, 15, 17, 2, 5, FRAME)                       # fork / head tube
        rect(im, 11, 22, 10, 6, (176, 120, 72))             # wicker basket
        rect(im, 11, 22, 10, 1, (216, 160, 104))
        for bx in range(12, 21, 3): rect(im, bx, 23, 1, 5, (136, 88, 56))
    else:
        rect(im, 14, 21, 4, 10, TYRE)                       # rear tyre
        rect(im, 15, 22 + (step * 3) % 8, 2, 2, RIM)
        rect(im, 12, 20, 8, 2, FRAME_SH)                    # rear rack
        rect(im, 15, 17, 2, 4, FRAME)
        px(im, 13, 24, (232, 56, 56)); px(im, 18, 24, (232, 56, 56))   # reflectors
    rimg = new()
    body(rimg, d, 16, 9, 0, sitting=True)
    head(rimg, d, 16, 0)
    lift = [0, 1, -1][step]
    rect(rimg, 11, 16 + max(0, lift), 3, 4, JEANS); rect(rimg, 18, 16 + max(0, -lift), 3, 4, JEANS_SH)
    rect(rimg, 11, 20 + max(0, lift), 3, 1, SHOE); rect(rimg, 18, 20 + max(0, -lift), 3, 1, SHOE)
    if d == 'up':
        rect(rimg, 11, 9, 10, 6, BAG); rect(rimg, 11, 13, 10, 2, BAG_SH)
    outline(rimg)
    a = rimg[..., 3] > 0
    if d == 'up':
        im[a] = rimg[a]
        rect(im, 8, 13, 16, 1, OL)                         # bars seen past the rider
        rect(im, 7, 13, 2, 2, (64, 64, 80)); rect(im, 23, 13, 2, 2, (64, 64, 80))
    else:
        # rider first, then bars + basket in front of the rider
        under = im.copy()
        im[a] = rimg[a]
        keep = under[..., 3] > 0
        im[20:31][keep[20:31]] = under[20:31][keep[20:31]]
        rect(im, 8, 18, 16, 2, OL)                         # handlebar
        rect(im, 9, 18, 14, 1, (200, 200, 216))
        rect(im, 6, 18, 3, 3, (64, 64, 80)); rect(im, 23, 18, 3, 3, (64, 64, 80))   # grips
    outline(im)
    return im

sheet = np.zeros((FS * 2, FS * 12, 4), np.uint8)
for di, d in enumerate(('down', 'left', 'right', 'up')):
    for st in range(3):
        sheet[0:FS, (di * 3 + st) * FS:(di * 3 + st + 1) * FS] = walk_frame(d, st)
        sheet[FS:2 * FS, (di * 3 + st) * FS:(di * 3 + st + 1) * FS] = bike_frame(d, st)
os.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)
Image.fromarray(sheet).save(sys.argv[1])
Image.fromarray(sheet).resize((FS * 12 * 4, FS * 2 * 4), Image.NEAREST).save('data/debug/player_4x.png')
print('ok')
