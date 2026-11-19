# Work log

Every agent logs its work here (rule in `CLAUDE.md`). Newest entry at the bottom. Append only: don't edit or
delete older entries; correct them with a new one. `HANDOFF.md` has the current state; this file has the history.

Entry format:

```
## YYYY-MM-DD HH:MM · short title
**Asked:** the user's request, in their words where it matters.
**Did:** what changed and why.
**Files:** the files touched.
**Commands:** what was run.
**Checked:** how the result was verified, and what was seen.
**Left:** what is undone, undecided, or needs the user.
```

Work before 2026-11-11 20:44 was not logged here. Its summary is in `HANDOFF.md` §2, §2b and §6.

---

## 2026-11-11 20:44 · Pushed the project to GitHub
**Asked:** "push this to github as a new project titled pixel-campus".
**Did:** Committed everything as one initial commit (`d40102e`) and pushed it to a new public repo,
[Ishan-Malhotra/pixel-campus](https://github.com/Ishan-Malhotra/pixel-campus), branch `main`. Added `.DS_Store`
to `.gitignore`. Noted the repo link at the top of `HANDOFF.md`.
**Files:** `.gitignore`, `HANDOFF.md`.
**Commands:** git and the `gh` CLI (this entry was written afterwards; the exact commands were not recorded).
**Left:** nothing.

## 2026-11-11 20:50 · Read HANDOFF.md and listed the next steps
**Asked:** "read HANDOFF.md, what is to be done next".
**Did:** Answered from HANDOFF §7 and §8: scale decision, `rotunda.png`, then bhawan, mess and NAB pieces, the piece
loader, flags and tall grass, chunky roads. No files changed.

## 2026-11-11 21:25 · Logging rule, closer camera, front garden of the Main Building
**Asked:** (with a reference picture of the garden) "make it a rule to log everything you do for future agents.
lets zoom in a bit, so as it matches the shown visual. before we move to the rotunda, lets fix the garden area in
front of the clock tower".

### 1. Logging rule
**Did:** Added the hard rule to `CLAUDE.md` and created this file. `HANDOFF.md` points here.

### 2. Zoom
**Did:** The game's view went from 1024×576 to 800×450 map pixels (50×28 tiles), set by `VIEW_W`/`VIEW_H` in
`game/src/main.ts`. The canvas still fills the window, so everything is drawn about 1.28× larger. Reason for the
number: in the user's picture one FD quad is about 36% of the picture's width; the quad is 291 px wide, and
291 / 800 = 36%. The loading bar in `BootScene.ts` is now centred from the camera instead of fixed numbers.
**Not done:** the map scale (`M_PER_TILE = 5`) is unchanged. This is a camera zoom only, so buildings are still
small next to the player and props. The scale decision in HANDOFF §7 is still open.
**Files:** `game/src/main.ts`, `game/src/scenes/BootScene.ts`.

### 3. Front garden
**Before:** the OSM driveway in front of the porch was painted with road Wang tiles and merged with the Rotunda loop
into a grey blob. There were no hedges, flags or plants.
**Did, in `tools/v4/blueprint.py` (section "front garden"):**
- The OSM driveway way `w285869287` is skipped in the road loop and redrawn as a smooth road 2 tiles wide. Its line
  is lowered near the porch so the kerb meets the porch steps, and smoothed (`chaikin()`).
- Hedges follow the drive's north side, 5 px outside the kerb, with gaps at the porch and at the west path. They are
  **polyline objects** of class `hedge` on the `props` layer, not tiles, so they can run diagonally.
- West lawn: dirt path from the west wing door to the drive, a tall-grass patch, palm, shrub, red and white flowers.
- East lawn: vegetable bed (dirt rectangle with 3×2 `crop` props) joined to the east wing door by a path, palm,
  sign, pink flower bush, red and white flowers.
- Four flags standing in the hedge line and two lamps at the hedge ends.
- All positions are computed from the Main Building stamp (porch, recess and wing door steps are found from its
  alpha), so they follow the building if it moves.
- The `props` layer of the generated map now has these objects. Before, it was empty.

**Did, in `tools/v4/tiled_kit.py`:**
- New props, appended so existing ids keep their numbers: `shrub`, `flowers_red`, `flowers_white`, `flowers_pink`,
  `sign`, `crop`. All are cut from `art/reference_main.png` with the new `key_cut()` (removes the lawn colour
  around an object; the older `flood_cut()` ate green objects on green lawn).
- Tile properties on props: `solid_base` (blocks the player at its base), optional `base_w`/`base_h` (size of that
  base as a fraction of the image), `flat` (drawn into the ground, walkable).
- New `paint(kind, img, d, x, y, top)`: one recipe each for road, path, hedge and garden lawn, shared by the Wang
  tiles and the converter. `terrain.png` came out pixel-identical after the refactor.
- New object class `hedge` (member `width`, default 14) in `campus.tiled-project`.

**Did, in `tools/v4/tiled_to_game.py`:**
- **Smoothing pass, whole map.** Terrain-brush tiles are no longer copied as tiles. Their corners are collected per
  terrain, turned into a smooth outline (upsample, blur by `SMOOTH = 7` px, threshold) and repainted with
  `tiled_kit.paint()`. Paths are joined to roads without a grass gap. This removes the stair-steps on every road and
  path on the map, not only in the garden. `SMOOTH = 0` gives the old tile-exact look.
- Hedge polylines are drawn as an even tube (a disc every pixel), shaded light on top and dark below, and block the
  player.
- Upright props (palm, lamp, shrub, sign, pink flowers) are now depth-sorted sprites, so the player can walk behind
  them. They reuse the `animProps` list with a single frame; the game code needed no change. `flat` props are baked
  into the ground.
- New debug picture `data/debug/game_render.png`: the map as the game draws it.

**Failed or dropped on the way:**
- A big bougainvillea prop (`flower_bush`) cut badly and did not fit; removed (it was my own generated file).
- `crop` as a keyed cut-out came out as a green square, because in the art crops stand on green patches. It is now a
  plain 18×18 art cell; cells side by side on dirt make the bed.
- Hedge shading flickered on steep segments, and the tube had notches at polyline joints. Fixed by picking the
  shading axis per long run (`across()`) and by drawing discs instead of a wide line.

**Files:** `tools/v4/blueprint.py`, `tools/v4/tiled_kit.py`, `tools/v4/tiled_to_game.py`, `CLAUDE.md`, `HANDOFF.md`,
`WORKLOG.md`, `README.md`, `tiled/GUIDE.md`; generated: `tiled/maps/phase1.generated.tmj`,
`tiled/campus.tiled-project`, `tiled/tilesets/props.tsj`, `tiled/props/{crop,flowers_pink,flowers_red,flowers_white,shrub,sign}.png`,
`tiled/underlay/phase1_blueprint.png`, `game/public/{maps,tiles,props}/*`.
**Commands:**
```
python3 tools/v4/blueprint.py phase1                              # no --force: wrote phase1.generated.tmj
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.generated.tmj
cd game && npx tsc --noEmit -p .
cd /tmp/campus-check && node garden.mjs                           # headless playtest, dev server on :5179
```
**Checked:**
- Type-check passes.
- Headless playtest at 800×450, 0 console errors: spawn at the porch (830, 687); walking west along the drive works;
  walking south from the west lawn stops at the hedge (y 663); the west path leads through the hedge gap to the
  drive and on; tall grass does not block; the vegetable bed is walkable; the player is hidden behind the palm.
- Looked at `data/debug/game_render.png` and three game screenshots (`data/debug/garden_*.png`).

**Left:**
- **`tiled/maps/phase1.tmj` is still the old map.** The new one is `phase1.generated.tmj`, and the game runs from
  it. `phase1.tmj` was byte-identical to the generator's output before this work (the user never saved it), but the
  rule says to ask before `--force`. The user was asked at the end of this session; see the next entry or HANDOFF
  for the answer.
- The old Rotunda stamp has stray specks and two tiny flags that now sit beside the drive. It is the user's file
  (`art/stamps/rotunda.png`), so it was left alone. It goes away when `rotunda.png` arrives (next step).
- The tall-grass patch is square-edged (Emerald-style tiles).
- Nothing from this entry is committed or pushed to GitHub; the user has not asked for that.

## 2026-11-11 21:32 · Replaced phase1.tmj with the garden map (user agreed)
**Asked:** I asked the user whether to replace `tiled/maps/phase1.tmj` with the new map. Answer: yes, back it up and
replace it.
**Did:** Copied the old map to `tiled/maps/phase1.backup-2130.tmj`, regenerated with `--force`, confirmed the result
is byte-identical to the `phase1.generated.tmj` that had been playtested, deleted `phase1.generated.tmj`, and
converted the game from `phase1.tmj`. Removed `game/public/props/flag_4.png`, an unreferenced, untracked leftover
from an earlier converter run in this session. Updated `HANDOFF.md` (§2c, §4, §8) to say `phase1.tmj` is current.
**Files:** `tiled/maps/phase1.tmj`, `tiled/maps/phase1.backup-2130.tmj` (new), `tiled/maps/phase1.generated.tmj`
(deleted), `game/public/*` (regenerated), `HANDOFF.md`.
**Commands:**
```
cp -p tiled/maps/phase1.tmj tiled/maps/phase1.backup-2130.tmj
python3 tools/v4/blueprint.py phase1 --force
cmp tiled/maps/phase1.tmj tiled/maps/phase1.generated.tmj      # identical
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj
cd /tmp/campus-check && node garden.mjs
```
**Checked:** the playtest gives the same results as before the replacement, 0 console errors.
**Left:** scale decision (HANDOFF §7); Rotunda piece (next step); nothing is committed or pushed.

## 2026-11-11 22:40 · Map scale 3 m/tile, garden redone after the art, gap between porch and Rotunda
**Asked:** (with the art picture, two photos of the drive and a satellite view) "the greenery is not looking good ->
try to match it to this reference image. there is space between the clock tower and rotunda as seen in the
satellite view".

**History of this request:** a first attempt (from 21:43) did most of the work below, then stopped at a usage limit
before it could log anything. The request was sent again at 22:12; the second attempt reviewed the first's edits,
kept them, and finished the work. Both are in this entry.

**Decision by the user:** asked whether to make the map bigger or shrink the plants, the user chose **"make the
whole map about 1.7x bigger"**. This settles the scale question that was open in HANDOFF §7.

**Did:**
- **Scale:** `M_PER_TILE` 5 → **3** (`blueprint.py`). One map pixel is now one pixel of `art/reference_main.png`, so
  plants and props cut from the art are at the buildings' scale. The map is now 187×230 tiles (2992×3680 px), was
  112×138. The porch now stands `PORCH_SOUTH_M = 20` m south of the OSM Clock Tower point (from the satellite view;
  it was 80 px = 25 m).
- **Rotunda:** new stamp `rotunda_art`, the art's Rotunda at the art's own size (loose flags and plants dropped with
  `big_parts()`), placed on the porch's axis. The old half-size `rotunda` stamp is still built but no longer placed.
  `make_stamp` seeded `art/stamps/rotunda_art.png` and `rotunda_art_collision.png` (new files, made by the first
  attempt; the user has not edited them).
- **Gap before the Rotunda (satellite):** read off `art/satellite/main_rotunda.jpg`: porch steps, the drive (a
  drop-off lane and the two-lane road, about 13 m), a paved terrace (about 7 m), then the arcade. Now
  `DRIVE_W = 76` px and `TERRACE = 40` px. The Rotunda is placed below both, and the terrace is painted as path
  (tan) around its north half. Measured result: porch to arcade 128 px, terrace 48 px; the Rotunda's centre is
  306 px south of the porch.
- **Drive:** one circular arc from the west circle, just under the porch steps, to the east circle. Median hedges
  split off the drop-off lane on both sides of the porch (as in the satellite view and the photos).
- **Hedges:** drawn like the art's: a dark top line, a sunlit band, a shaded band under a ragged leaf line, and a
  ground shadow (`draw_hedge()` in `tiled_to_game.py`, 17 px wide; medians 13 px). Along the drive's outer kerb
  with a gap at the west path; planters on the terrace edge, open in front of the arcade.
- **New props** cut from the art (`tiled_kit.py`, `key_cut()` gained `erase`, `largest`, `inner`): `thicket` and
  `thicket_tall` (the art's tall-grass patch, walkable, rustles), `veg_bed` (the whole vegetable bed), `palm_small`,
  `conifer`, `bush_big`, `bougainvillea`.
- **Plants** placed like the art: west lawn (grass patch, palm, shrubs, flowers, dirt path from the wing door), east
  lawn (vegetable bed, palms, conifers, bushes, sign), flags in the hedge lines, lamps at hedge ends. New in the
  second attempt: bougainvillea against the Rotunda's arcade wall on both sides (the stamp still had leftover
  bougainvillea leaves on the west wall; the new props cover them and match the art), plus palms, bushes and
  flowers on the Rotunda's flanks, each placed only where its base is clear of roads, paths, walls, hedges and
  other plants (`plant_free()`).
- Flat props marked `tallgrass` rustle underfoot (`grass_rects` in the converter).
- Saved the user's references: `art/satellite/main_rotunda.jpg`, `art/photos/clock_tower_drive_{1,2}.jpg` (local
  references, not shipped).
- After asking (answer: yes), replaced `tiled/maps/phase1.tmj` with the new map. The old one is
  `phase1.backup-2233.tmj`. Removed five untracked, unreferenced prop images from `game/public/props/` left by
  earlier converter runs.

**Failed or dropped on the way (first attempt):** a separate west "lane" hedge layout was replaced by the medians;
the first `veg_bed` cut lost the crops' light greens (keyed too loosely) and was redone; a `thicket_small` cut was
dropped. Second attempt: the first terrace was a few px too narrow and left ragged lawn blobs between it and the
drive; it is now a tile wider, and lawn under a tile wide between them is paved.

**Files:** `tools/v4/blueprint.py`, `tools/v4/tiled_kit.py`, `tools/v4/tiled_to_game.py`, `WORKLOG.md`, `HANDOFF.md`;
new `art/stamps/rotunda_art.png`, `art/stamps/rotunda_art_collision.png`, `art/stamps/_source/rotunda_art_full.png`,
`art/satellite/main_rotunda.jpg`, `art/photos/*`, `tiled/props/{thicket,thicket_tall,veg_bed,palm_small,conifer,bush_big,bougainvillea}.png`,
`tiled/maps/phase1.backup-2233.tmj`; regenerated `tiled/maps/phase1.tmj`, `tiled/tilesets/*`, `tiled/stamps/*`,
`tiled/campus.world`, `data/phase1_slots.json`, `game/public/*`.
**Commands:**
```
python3 tools/v4/blueprint.py phase1                               # ~60 s at the new scale
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.generated.tmj
cp -p tiled/maps/phase1.tmj tiled/maps/phase1.backup-2233.tmj && python3 tools/v4/blueprint.py phase1 --force
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj
cd game && npx tsc --noEmit -p .
cd /tmp/campus-check && node garden.mjs                            # coordinates updated for the new scale
```
**Checked:** side-by-side of the art and `data/debug/game_render.png` at the same scale; game screenshots
`data/debug/garden_{spawn,west,east,sw}.png`. Playtest, 0 console errors: spawn at the porch (1382, 1122); from the
porch south over the drive and terrace to the arcade (stops at y 1223); hedges block (west lawn stops at y 1104,
east lawn at y 1136); the west path leads through the hedge gap to the drive; the grass patch and the vegetable bed
are walkable. Type-check passes.
**Left:**
- The Rotunda stamp's bottom is still cut flat (the art ends there). It overlaps the tops of the two NAB
  placeholder blocks, and the amphitheatre steps are cut off. Both get fixed when the user sends `rotunda.png`.
- The art's Rotunda is about 1.5 times its real size next to the Main Building. It was kept because its width
  relative to the FD wings matches the satellite view.
- The terrace is drawn with the tan path tiles. In the satellite view it is paler paving; a separate terrain would
  be needed to match that.
- A few small lawn tufts remain where the terrace meets the flank lawns.
- Only the area between the FD wings has plants; the rest of the map has none.
- Nothing is committed or pushed.

## 2026-11-12 10:48 · Pushed the work to a new GitHub branch
**Asked:** "push all this to a new branch in github".
**Did:** Created branch `garden-3m-scale` from `main`, committed all uncommitted work from 2026-11-11 (logging rule,
800×450 view, 3 m/tile scale, front garden, terrace before the Rotunda, new props, regenerated map and game files,
saved references) as one commit, and pushed it to `origin`. `main` is unchanged.
**Commands:** `git checkout -b garden-3m-scale`, `git add -A`, `git commit`, `git push -u origin garden-3m-scale`.
**Left:** merging into `main` (or opening a pull request) is up to the user.

## 2026-11-16 21:05 · Opened the game on localhost
**Asked:** "open this in localhost".
**Did:** Started the Vite dev server (`cd game && npx vite --port 5179 --strictPort --host 127.0.0.1`) and opened http://127.0.0.1:5179/ in the browser.
**Left:** the server is still running in the background.

## 2026-11-16 21:30 · Smoother movement and camera (part 1 of "front of the Clock Tower + smoother animation")
**Asked:** "we need to edit the area in front of the clock tower joining to the rotunda. i have the satellite view,
how can we smoothen the animation and add more things to the map? help me". Taken as: (1) make walking/scrolling
smooth, (2) redo the porch→Rotunda area after the satellite view already saved (`art/satellite/main_rotunda.jpg`),
(3) add more plants/details there. The user was not asked which animation they meant; walking/scrolling judder was the
measurable problem (flags and grass were not touched).
**Cause found:** the 800×450 canvas was stretched to the window by a non-whole factor (e.g. ×3.6 on a 1440-wide
retina screen), so map pixels were 3 or 4 screen pixels wide and the pattern crawled while scrolling; and the camera
rounded its scroll to whole map pixels while the player moved in fractions, so the player wobbled against the ground.
**Did:**
- New `game/src/view.ts`: `VIEW_W = 800`, `screenSize()`, `pixelZoom()` = the whole-number zoom closest to 800 map px across.
- `game/src/main.ts`: canvas at device-pixel size (`zoom: 1/dpr`, `Scale.NONE`), resizes with the window and emits `pixelzoom`.
- `game/src/scenes/WorldScene.ts`: exact float position `pos`; `place()` draws the player and centres the camera at
  that position snapped to 1/zoom map px (= one screen pixel); no `startFollow`; camera `setRoundPixels(false)`.
  The walk cycle's speed now follows the distance actually covered (legs stop when pushing into a wall).
- View is now 720×450 map px on a 1440×900 retina screen (zoom 4), 960×540 on 1920×1080 (zoom 2), 640×360 on 1280×720.
**Checked:** `npx tsc --noEmit -p .` OK. Headless (`/tmp/campus-check/smooth.mjs`, playwright-core reinstalled since
/tmp was wiped): at all three sizes the player's offset from the camera centre is 0 in every frame while walking
(before the camera fix it varied 0–3 screen px), 0 console errors; screenshot shows no tile seams.
**Left:** the map work (next entry).

## 2026-11-16 22:20 · Porch→Rotunda area redone after the satellite view (part 2 of the same request)
**Asked:** see the 21:30 entry. Reference: `art/satellite/main_rotunda.jpg` (already saved; no new image was given).
**Compared with the satellite, the old area had:** a ragged tan path-tile blob as the terrace; three rows of hedges
each side (outer, median, and planters on the Rotunda side; the satellite has no planters there); small scattered
plants instead of the big red bougainvillea beds on the Rotunda's flanks; no centre line on the drive.
**Did:**
- **Converter (`tiled_to_game.py`), three new object kinds on the `props` layer**, all editable in Tiled:
  - `paving` polygon: pale stone slabs (colours from the art's Rotunda floor, warmed toward the satellite), white
    kerb + grey rim, walkable. Properties `cx`,`cy` lay the slabs in rings around that point. `road_inset` (px): the
    polygon's outer band is drawn as asphalt **only where it is beside a road**, so the kerb is an exact arc even though
    the smoothed road outline wobbles. Drawn after the terrain, before beds/lines/hedges.
  - `flowerbed` polygon: bougainvillea bed (leaf base, red/magenta/pink bract clumps on a jittered grid, stone kerb),
    solid.
  - `roadline` polyline: dashed white centre line (8 on / 8 off, 2 px).
- **Blueprint (`blueprint.py`, section "front garden"):**
  - Terrace = one `paving` polygon: the drive's inner kerb circle (centre (1381,1545), radius R−DRIVE_W/2+18, i.e. 18 px
    under the road, `road_inset` 19) closed level with `TER_END = rcy − 30`; slabs ring the Rotunda centre (1380,1405).
    It is no longer painted as path tiles, so **in Tiled the terrace shows as the polygon object over grass tiles**.
    The old disc-grow terrace and the "sliver" fix are removed.
  - Beds: traced row by row from the Rotunda's wall outwards to the first road/path/occupied pixel (stamp alpha
    `rot_left`/`rot_right`), smoothed with `chaikin`, plus two `bougainvillea` props standing in each bed when it is
    wide enough. West bed is narrow (3253 px) because an OSM footpath runs between it and the road; it was **not**
    paved over. East bed 9159 px.
  - Removed the Rotunda-side planter hedges (`west_in`/`east_in`) and the old flank plant list (palms, bushes, flowers
    beside the Rotunda); the beds replace them.
  - Tree row: conifers/bushes/shrubs at OUT+34 px outside the outer hedges, via `plant_free` (only 3 fit; the lawns
    are already full of the art's plants).
  - Dashed `roadline` along the two-lane part of the drive (between the medians and the terrace), clipped off other roads.
  - Preview render draws the new shapes; new shapes are written as polygon/polyline objects with typed properties.
- **`tiled_kit.py`:** project classes `paving`, `flowerbed`, `roadline` added to `campus.tiled-project`.
**Failed on the way:** first bed tracer walked the wrong way (into the Rotunda: 70k px beds, bougainvillea in the
Rotunda's centre); tree rows first placed 0 (footprint overlapped the hedge clearance; moved 8 px out); `int64` in JSON;
leaf colour index out of range; asphalt band first ran along the terrace's lawn edge too; paving drawn under the road
left the road's wavy kerb visible (replaced by `road_inset`); two lawn specks remained at inset 12 (fixed at 19).
**Commands:**
```
python3 tools/v4/blueprint.py phase1                                 # writes phase1.generated.tmj (phase1.tmj untouched)
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.generated.tmj
cd /tmp/campus-check && node walk.mjs && node smooth.mjs
```
**Checked:** `data/debug/game_render.png` vs the satellite; collision image (terrace and line walkable; hedges, beds,
Rotunda walls solid); playtest at 1280×720: porch → south stops at the arcade y 1223 (as before), west along the terrace
to x 1157 freely, 0 console errors; smoothness test still 0 px offset at all sizes.
**Left / undecided:**
- **The game now runs the converted `phase1.generated.tmj`; `phase1.tmj` is unchanged.** Replacing it needs
  `blueprint.py phase1 --force` → asked the user (CLAUDE.md rule). Map unchanged since generated on 11-11 (mtime 22:34).
- West bed narrow (OSM footpath); amphitheatre/bottom of Rotunda still cut flat (needs `rotunda.png`).
- Lawn rows have few trees because the lawns are full; more variety needs more prop cut-outs.
- Not committed or pushed.

## 2026-11-16 22:55 · New Rotunda art (Part A of "replace the rotunda art… fix the roads and extra spaces")
**Asked:** (with a complete Rotunda image and 5 aerial photos, two of them identical) "replace the rotunda art with
this, additionally i am adding more satellite images of the entire campus, fix the roads and extra spaces
accordingly, so that only the buildings are left to be added".
**Answers to my questions:** scope = **Phase 1 area first**; satellite = **"I'll add top-down ones"** (into
`art/satellite/`); replacing `phase1.tmj` = **"avoid wasting effort on tiled"** (taken as: replace freely after a
backup, no effort on Tiled-side polish). Plan approved: `~/.claude/plans/adaptive-finding-quilt.md` (Parts A, B, C).
**Did (Part A):**
- Saved the user's images (they were only in a temp folder): `art/pieces/_raw/rotunda_raw.png` (1024×572, black
  background, "ENT"/"EXIT" labels, ✦ watermark), `art/photos/aerial_{rotunda_east,rotunda_west,nab_corridor_to_clock_tower,nab_to_saraswati}.png`.
- `blueprint.py` → new `prep_rotunda()` (+ `_flood`, `_close`): makes **once**, then never overwrites,
  - `art/pieces/rotunda.png`: background flooded away from the border (sum < 60), loose parts < 1500 px dropped (the
    watermark), the three labels painted out (onion-peel median fill; text boxes measured at (312,318,329,325),
    (740,259,761,266), (504,439,520,446));
  - `art/pieces/rotunda_collision.png` (painted = wall): south half by colour (flood from the plaza centre over floor
    colours with 2 px gap closing; blocked islands < 700 px become floor); north half by geometry (band between the
    plaza ellipse (512,266; 211×164) and the outer ellipse (512,255; 258×236), north of the line (300,330)–(760,262));
    green inside the plaza = hedge arcs; the west landing + stepped ramp opened by hand (polygon in the code).
- Stamp `rotunda_piece` = the piece × `ROT_SCALE = 0.70`, own 128-colour palette, placed with its axis on the porch
  and its apron 36 px (TERRACE) below the drive. Old `rotunda` / `rotunda_art` cuts are no longer built; their files
  in `art/stamps/` are untouched (that is why the new stamp is not called `rotunda`).
- **Deviation from the plan, told to the user:** scale 0.70 instead of "same width as the old stamp". At 1:1 the
  piece (1024 px wide with its stair path) lay on top of the west road; the satellite gives a plaza ≈ 61 m (443 px in
  the piece → 0.73) and porch→plaza centre ≈ 51 m (map now 53 m).
- NAB slots trimmed to start below the amphitheatre. South stub joined to the snake path and the west stair path to
  the west road by `join()` (short footpaths). Terrace = paving from the drive's kerb to the stamp, ending in a
  straight edge at `rcy − 20`. Bougainvillea bed tracer and its props removed (the piece has its own beds).
- `tiled_to_game.py`: collision grid **4 px cells, solid from 25 % covered** (was 8 px / 40 %): 2–3 px walls always
  block and the 24 px stair path stays open. `main.meta.json` is now ~690 KB.
- Tiled: backed up `phase1.tmj` → `phase1.backup-1116-2250.tmj`, `blueprint.py phase1 --force`, removed
  `phase1.generated.tmj`; the game is converted from `phase1.tmj` again.
**Failed on the way:** first collision seed had holes (east arcade wall, hedges walkable) that I misread as solid in
the first overlay → north half made geometric; the stair path dead-ended at the landing until the ramp was opened;
terrace tried as a thin band around the arcade (showed the road's wavy edge) → back to the full crescent; a width
check on the 8 px grid wrongly failed the stair path → replaced by a search with the game's exact `canStand` rule.
**Commands:** `python3 tools/v4/blueprint.py phase1 --force`, `python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj`,
`python3 /tmp/rot/routes.py`, `cd /tmp/campus-check && node rot.mjs && node smooth.mjs`, `npx tsc --noEmit -p .`
**Checked:** render vs the user's image (no black, labels or watermark); mask overlay; route search with the game's
hitbox, foot and bike: west stair path → ramp → plaza/steps/east stairs ✓, south entrance from the snake path ✓,
arcade blocks from the terrace ✓, all reachable from the porch ✓; in-game walk into the plaza, 0 console errors;
smoothness still 0 px offset; type-check OK.
**Left:** the west stair path lies on the east edge of the 12 m-wide west road ("drive over buildings: 770 px" in
the blueprint print) → Part C road widths. No door through the arcade from the terrace (the art has none). East
stairs end in a closed corner. Parts B and C. Not committed.

## 2026-11-16 23:15 · Satellite alignment tool (Part B) and the OSM audit; stopped before Part C
**Did:**
- `blueprint.py` now writes `data/<area>_frame.json` (rotation, origin, px per metre, size). Written for phase1 by
  the same maths without a full run (values: θ −8.75°, 2992×3680).
- New `tools/v4/sat_register.py`: for each image in `art/satellite/`, finds metres-per-pixel and position by
  FFT-correlating its bright-roof mask with the OSM building raster (coarse pass at 2 m over scales 0.10–1.20 m/px,
  fine pass at 0.25 m, ±2 % scale, ±6 m). Saves `art/satellite/registration.json`; an entry with `points` is fitted
  from control points instead; an entry with `m_per_px` is reused. Outputs the mosaic and overlays (see HANDOFF §2f).
  Runs in ~15 s.
- Results: `central_strip.png` 0.369 m/px, `fd2_area.png` 0.184 m/px (both automatic; roofs sit on their slots and
  roads coincide in the overlay). `main_rotunda.jpg` was placed wrongly by the automatic match (few roofs in it) →
  entered by hand: 0.1845 m/px (same zoom as fd2_area), plaza centre px (462, 658) on the OSM Rotunda point.
- The overlay confirms the new Rotunda's size and position (plaza on the satellite's plaza).
- OSM audit of the Phase 1 box: every highway is drawn (22 service, 1 unclassified, 15 footway, 4 steps); nothing
  is filtered out. Missing lanes are missing from OSM itself.
- `art/pieces/README.md`: Rotunda marked done.
**Not done (Part C), and why:** the user said they will add top-down screenshots; the plan says to stop and ask
when they have not arrived. Existing coverage is 61 % of the map.
**Left:** Part C once the screenshots are in `art/satellite/` (run `sat_register.py`, then road widths, missing
lanes via `data/phase1_corrections.json`, tree/bare-ground areas, NAB corridor). Nothing committed or pushed.
**Note:** the first FFT version would have taken minutes per image and the fine pass hours (pixel loops); rewritten
before running.

## 2026-11-17 · Hostel piece on every bhawan
**Asked:** (with a hostel image) "here is a hostel. add this to the map. this can be vk, bhagirath, krishna, gandhi,
shankar, vyas. mirror this for ram, budh, malviya. vk has a lawn in front of it, ensure you lay down enough space for
the lawn. mirror the image for ranapratap and ashok as well."
**Asked back:** VK's lawn side → "West, at the gate"; size → "Not sure, use satellite" (VK is not covered by any
screenshot yet) → reserved 30 m.
**Did:**
- Saved the image as `art/pieces/_raw/bhawan_raw.png` (765×1024, white background, a watermark on the bottom-right
  colonnade).
- `blueprint.py`: `prep_bhawan()` makes once `art/pieces/bhawan.png` (white flooded off from the border; watermark
  patched from two colonnade bays to the left, bay = 54.5 px, checked seamless) and `art/pieces/bhawan_collision.png`
  (all walls except the gate's stone landing, piece px (4, 488)–(37, 586)). Stamps `bhawan` / `bhawan_m` (mirrored),
  cropped to the building and resized to 21×32 tiles (63×96 m, the usual OSM footprint; the art is 0.76 wide:tall,
  so it is squeezed 13 % horizontally), 96-colour palette.
- Placement after the Main Building slot: name lists `BHAWAN_AS_DRAWN` / `BHAWAN_MIRRORED` (Malviya written as
  Malviya-A, Malviya-B and Malviya Bhawan, because OSM has "Malviya-A" and "Malviya-B"); centred on the OSM footprint;
  `gate_path()` = straight footpath from the gate to the first road/path pixel; `LAWNS` keeps metres clear in front of
  the gate and removes small slots under a hostel or on its lawn (2 removed under Ram Bhawan).
- In Phase 1: Ram, Budh, Malviya-A (gate east); Krishna, Gandhi, Shankar, Vishwakarma, Bhagirath (gate west). Vyas,
  Rana Pratap, Ashok, Malviya-B are outside this map area; they are in the lists for later areas.
- Backed up `phase1.tmj` → `phase1.backup-1117-hostels.tmj`, regenerated with `--force`, converted.
**Checked:** full render; all 8 gates reachable on foot from the porch (search with the game's hitbox); in-game walk
across VK's lawn to its gate (stops on the landing at x 2454), zone banner "Vishwakarma Bhawan", 0 console errors.
VK's gap to the road was already ~30 m (path from the gate is 163 px long), so VK did not move.
**Not done / notes:** Bhagirath's and VK's real OSM outlines are not double-courtyard (Bhagirath is E-shaped); the
user asked for this art on them anyway. Courtyards are not walkable (no way in through the gatehouse). VK lawn depth
is a guess until a satellite screenshot. Nothing committed.

## 2026-11-17 · Green courtyards; street-side strip (footpath, kerb, hedge, trees) for Krishna Bhawan only
**Asked:** (with 3 Street View screenshots and a pasted task spec) courtyards a different colour from the grass outside
→ make consistent; the outer garden + hedge "wall" between road and hostel is missing; roads look bland, more
greenery (more screenshots to come). "do it first for krishna bhawan". The pasted spec: palette-only 16 px tiles,
`tools/v4/exterior.py`, new assets only under `tiled/generated/` + `tiled/tilesets/`, 3-tile hedge gap at the door,
work on crops, STOP for approval after one hostel.
**Answers to my questions:** courtyards → "make them green lawn"; street trees → canopy "from your hostel art".
Plan approved: `~/.claude/plans/adaptive-finding-quilt.md` (overwritten for this task).
**Did:**
- `blueprint.py: prep_bhawan()`: courtyard earth → the map's grass tile, tree shadows → darker palette green, decided
  on the resized art, painted on the stamp (`BHAWAN_COURTS`); `art/pieces/bhawan.png` untouched. Applies to every
  hostel (one shared stamp). Hostel slots now carry `gate: [x, y, side]` (in `data/phase1_slots.json`).
- New `tools/v4/exterior.py`: `make_assets()` → `tiled/generated/exterior_tiles.png` (+ `.json`; 23 tiles: 3 pavers,
  4 kerbs + 4 corners, hedge v/h + 4 corners + 4 ends, 2 fence posts), `tree_whitewashed.png`, `tree_plain.png`
  (32×45; canopy cut from the hostel art's round courtyard tree, trunk/band/ring added), `tiled/tilesets/exterior.tsj`
  (hedge tiles `solid`; edge-type terrain sets "Paver path" and "Hedge") and `exterior_props.tsj`. `layout()` lays
  road | kerb | paver | hedge for one slot on `decor`, trees on `props`, rectangles on `collision` (all named
  `ext:<slot>`), re-runnable; `validate()` re-opens the map. Approved slots are kept in `data/phase1_exterior.json`.
- `tiled_to_game.py`: only corner-type terrain sets are smoothed terrain; decor tiles are drawn after the terrain
  repaint (so the kerb covers the road's mid-tile edge).
- Ran for **Krishna Bhawan only**: rows 103–136, kerb columns 110/111 (the road jogs a tile below the gate), gap rows
  119–121, 103 tiles, 31 hedge tiles, 4 trees. Backup `phase1.backup-1117-exterior.tmj`.
**Deviations from the pasted spec (told to the user):** palette = `tiled_kit.PAL_IMG` (same 128 colours, same
nearest-colour rule as v3 `to_palette`); gate position instead of door objects (none exist); trees 32×45 with the
canopy from the user's art instead of script-drawn 16×32; own tileset instead of appending to the ground tileset;
zone rectangles (name banners) are not treated as blocking events, only spawn/door objects.
**Fixed on the way:** red band on the trunk too close to the brown (→ (185,125,104)); wedge of verge at the road's
jog (the footpath now takes a partly-road tile beside the kerb); stray kerb wrapped around the strip's ends.
**Commands:** `python3 tools/v4/blueprint.py phase1 --force` → `python3 tools/v4/exterior.py phase1 "Krishna Bhawan"`
→ `python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj`. **New pipeline order: blueprint → `exterior.py phase1
--approved` → converter** (a blueprint regenerate wipes decor).
**Checked:** asserts (palette-only pixels, no tile on a building/slot/spawn/collision, no hedge in the gap); map
re-opened and valid (5 tilesets, 113 objects); 4× crops of top/middle/bottom; route search with the game's hitbox:
road → gap → gate ✓ (foot and bike), hedge blocks north and south of the gap ✓, footpath walkable end to end ✓, tree
base blocks ✓; in-game walk to the gate landing (1846, 1932), hedge stop at x 1786, 0 console errors; type-check OK.
`data/debug/exterior_krishna.png` = before | after.
**Left (waiting for the user's approval):** the other hostels, the messes and library (they have no gate data yet),
roadside greenery on the main road (user will send more screenshots). The kerb column narrows the road by half a
tile along the strip. Pavers are grey-beige with salmon accents (the palette has no true pink-grey). Not committed.

## 2026-11-17 (later) · Streets restyled after the user's street reference; laid on six hostels; road centre lines
**Asked:** (with a pixel-art street image and 4 street photos taken in front of Krishna Bhawan; two were the same
file) "use the attached image as reference to draw the roads and greenery around campus".
**Read as:** the Krishna sample's style was not the target; the reference is. No separate approval of the first
sample was given; this message replaced the "stop and wait" step, so the new style was laid on every hostel it fits.
**Did:**
- Saved `art/reference_street.png` (the reference) and `art/photos/street_krishna_{12,13,14,15}.png`.
- `exterior.py` restyled: grey **herringbone** pavers (8×4 slabs, 16 px period), **black/white striped kerb** (4 px,
  8 px blocks), `tree_pit`, `zebra_v/h` tiles (new tiles appended; ids of the old 23 unchanged). Trees are now
  `tree_street_a/b` (81×86, b = mirrored), **cut from the reference's top-right tree**: lawn + shadow flooded away,
  canopy = left half mirrored about the trunk inside a scalloped outline (it runs off the picture / into the next
  tree), leaf pixels kept to the palette's greens. The trunk is red-brown with a white band above, as in the photos
  (the first sample had it the wrong way round). `tree_whitewashed/plain.png` removed (generated files).
- `layout()` rewritten: near side (kerb, paver, hedge with posts, 3-tile paved gap, dropped kerb) + **far side of
  the road** (kerb, paver, trees) + **zebra crossing** on the two rows at the gate + trees in pits every 9 tiles
  (far side staggered) + **shrubs** (existing props from the main art) on the lawn behind the hedge. Other slots'
  props count as occupied. `exterior_props.tsj` is added before `exterior.tsj` so the latter can grow.
- `blueprint.py`: dashed **centre lines** (`roadline`) on straight stretches of 4-tile and named roads, none inside
  junctions (10 stretches).
- Ran on all 8 hostels: laid on Krishna, Gandhi, Shankar, Ram, Budh, Malviya-A; **skipped Vishwakarma and Bhagirath**
  ("no road within 6 tiles on the gate side": VK has its lawn there). `data/phase1_exterior.json` lists the six.
**Checked:** palette asserts; map valid (253 objects); 3× crops of Krishna; contact sheet of the others; every
hostel gate reachable from the porch; in-game walk to Krishna's gate over the zebra, hedge stops the player,
0 console errors; type-check OK. `data/debug/exterior_krishna.png` updated (before | after).
**Left / known:** trees are tall (86 px): the player is hidden while passing behind a canopy. Roads are a tile
narrower between the two kerbs. Some older shrub cut-outs carry stray dark specks. Far-side strip breaks where a
side path meets the road. VK/Bhagirath, messes, library, roads away from hostels, people/bicycles from the reference:
not done. Not committed.

## 2026-11-17 (evening) · Part A: tree sheet sliced into registered sprites (map untouched); stopped for approval
**Asked:** two-part task; Part A = slice `art/new/trees_sheet.png` (4×3 sprites on purple) into registered sprites by
colour key, remove the watermark, find the art's pixel size, downsample, scale to tiles, snap to the palette, split
trees into canopy / trunk base with split row + collision footprint, hold the palm and grass tuft, register in a
"collection of images" tileset; then STOP. (The message ended mid-sentence at step 7, and Part B's details were
not included.)
**Did:** saved the sheet from the chat to `art/new/trees_sheet.png` (new file). New `tools/v4/slice_trees.py`
(deterministic; reruns give byte-identical files) → `tiled/generated/trees/` (10 sprites, + `_canopy` / `_trunk` for
the 7 trees, `_contact_sheet.png`, `trees.json`) and `tiled/tilesets/trees.tsj` (24 images; properties: kind,
tiles_w/h, split_row, collision_x/y/w/h, canopy_layer `above`, trunk_layer `props`).
- Background: the corner pixel is the darker frame/gutter purple (157,51,123); the cells are (194,90,158) → keyed on
  both, tolerance 60, plus any purple-ish pixel. No flood fill. Watermark right of the grass tuft removed (8 px).
- Art pixel = 2.91 screen px (Fourier peak of edge positions, same in x and y); sampled once per art pixel.
- Scale (nearest): row 1 canopy 3 tiles, row 2 → 2 tiles, row 3 → 1 tile. **Deviations:** never above 1.0 (column
  36 px and cypress 20 px keep their own size; forcing 3 / 2 tiles made them 7 / 6 tiles tall); umbrella 4 tiles and
  twin 5 tiles (3 would crush them).
- Palette: leaves (and the deep shade under crowns) snap to the palette's greens only; the red trunks come out
  brown (the palette has no saturated red). Split at 27.5 % of each sprite's height (pixel row, not a tile boundary).
- Held: `palm`, `grass_tuft` (not cut, not registered).
**Checked:** asserts (palette only, alpha 0/255, no purple); looked at the contact sheet twice (fixed: near-black
canopy shade, footprints spanning the crown, twin footprint, oversized canvases, grid finder missing the last
row/column); rerun identical; tileset images exist with the stated sizes.
**Left:** Part B (not started, needs the user's approval and its instructions). Note for Part B: the map's `above`
layer is a tile layer and the converter depth-sorts upright props; placing canopy images above the player needs an
object layer or a converter change. Not committed.

## 2026-11-17 (evening) · Part A steps 8–10: contact sheets, defects found and fixed; stopped for approval
**Asked:** steps 8–10 of Part A (contact sheets at 4x on the real grass tile and on a hostel roof tile, look, report
and fix purple edges / holes / clipped canopies, save to `data/debug/`, STOP), plus the full text of Part B (not
started; it needs approval of Part A first).
**Did (`tools/v4/slice_trees.py`):** `data/debug/trees_on_grass.png` (terrain tile 64) and `trees_on_roof.png` (a
plain roof patch of `tiled/stamps/bhawan.png`); per-sprite defect numbers in `tiled/generated/trees/trees.json`
(purple px, enclosed holes, margin to the sheet cell, fringe px repainted).
**Found and fixed:**
- The purple rule (r and b above g) also deleted crimson flowers in `shrub_red` and red trunk shading → now needs
  blue far above green and close to red (b > g+45, r > g+30, r−b < 60). Holes: shrub_red 13 → 2 px, twin 6 → 0.
- Rim pixels were blends of outline and purple (grey / pink / brown once keyed), a broken outline on every sprite →
  every non-green rim pixel is repainted as outline (dark green beside leaves or crown shade, dark brown beside
  trunk): 90–292 px per sprite at art resolution.
- No canopy is clipped (smallest margin to the cell edge: 1 art pixel). Remaining holes are the umbrella's real gaps
  (25 px) and 1–2 single pixels.
**Checked:** looked at both sheets and 4x zooms before and after; asserts pass; rerun byte-identical; map and game
files untouched.
**Left:** Part B waits for approval. Notes for it: no `data/reference/street_mood.png` exists (the mood image is
`art/reference_street.png`); the task says `trees.tsx`, the file is `tiled/tilesets/trees.tsj`; a `shadows` layer and
above-player canopies need converter + game support (alpha layers); current `exterior.py` strips would be replaced
by `beautify.py` in the test area. Not committed.

## 2026-11-17 (night) · Part B on the test area only: tools/v4/beautify.py; stopped for approval
**Asked:** Part B (full spec in the user's message): beautify streets on ONE test area (beside Krishna Bhawan, porch to
the crossing south of it), mood after `art/reference_street.png`; STOP after showing before/after. Answers given:
mood file = `art/reference_street.png`; umbrella/twin: "shrink" for streets, full size for lawns; replace the old
strip in the test area; converter/game changes allowed.
**Test area:** rows 119–160 (gate crossing at 119–121 → the crossing where the NAB footpath meets the road at
158–159), cols 102–137 (street + the lawns beside it). Asphalt fixed at cols 107–109 for the whole area (the north
alignment): matches the existing street at the north end and lets the 3-tile footpath pass the Warden's Residence.
**Did:**
- `slice_trees.py` (Part A outputs, ids of the first 24 unchanged): street copies `tree_umbrella_road`,
  `tree_twin_road` (canopy 3 tiles); `<tree>_canopy_cell.png` (rows above the trunk tile, for `above`); trunk tiles'
  collision relative to the trunk image. trees.tsj now 39 images.
- New `tools/v4/beautify.py` (SEED 20261117, stable crc32 sub-seeds): assets `tiled/generated/street/` →
  `street.tsj` (52 tiles: asphalt ×3 + cracks/worn/manhole/dash/zebra, 4 pavers, kerbs, ramps, corners, dirt-spill
  and dirt-end pavers, tree pit, 3 grass + tufts/flowers/dirt, hedge pieces) and `street_objects.tsj` (street lamp =
  the art's lamp with its lawn specks removed; dustbin, bench, bike rack, barricade drawn small in the palette).
  Layout: kerb + 3 pavers each side; zebra + ramps at both crossings; paved 3-tile corridor to Krishna's gate;
  hedge with wire posts on the building side (gaps at the door, stops at the residence); shrub clusters (3–5) on the
  NAB verge and behind the hedge; trees every 5–9 tiles jittered with skips, trunk in a pit on the outer column,
  canopy on `above`, shadow 25 % + 7–11 dapples 12 % on `shadows`; two full-size lawn trees (twin, umbrella);
  per 20 rows 2 lamps / bin / bench-or-rack / maybe a manhole and barricade; ground variety on the lawns; ends join
  the neighbouring footpath or fade into earth, the kerb turns the corner. Blueprint's dashed line cut out of the area.
  Writes only decor / props / above / shadows (+ `data/phase1_beautify.json`: area box and its canopy anchors).
- `tiled_to_game.py`: tiles taller than the grid anchored bottom-left (Tiled's rule); `shadows` object layer
  (ellipses, `opacity`, darkened then snapped to the palette); `collision_x/y/w/h` tile properties used as exact
  collision boxes (flip-aware).
- `exterior.py`: leaves beautify areas alone (cells blocked, rows dropped from its edges, no crowns reaching in).
- Pipeline: `blueprint.py phase1 --force` → `exterior.py phase1 --approved` → `beautify.py phase1 krishna_test` →
  `tiled_to_game.py`. Backup `phase1.backup-1117-beautify.tmj`.
**Iterations vs the mood (5 differences each, all fixed):** (1) pale-box tree pits → dark soil + stone rim; cracks
looked like letters → subtle zigzags, fewer; bright unbroken paving → more dapples; Gandhi's street tree hid the south
crossing → exterior keeps crowns out; stray kerb bar at the north join → exterior drops the area's rows. (2) bench
hidden under a crown → details avoid crowns; bare lawn behind the hedge → shrub clusters there; no lawn trees →
twin + umbrella full size on the lawn; (small crowns = the user's 3/2-tile cap, kept). (3) dark grass tiles formed a
dot grid → removed, darker patches are irregular faint ovals on `shadows`; perfect ovals → 3–5 overlapping; dirt
dots beside lawn trunks → removed.
**Bugs found on the way:** `hash()` of strings (salted per process) made the layout and the grass tiles change per
run → crc32; a wide far-side tree anchored its canopy one column outside the box, so a rerun tripped the overlap
check → anchors recorded and cleared; bike rack collision 20 px spilled into the next footpath column → 16 px.
**Checked:** asserts in beautify (widths 3/3 every row, kerb every row with ramps exactly at crossings, nothing on a
door approach / crossing / ramp, nothing on buildings / events / collision, canopy overhang into the road 0 px and
never over a crossing or door row, canopy ≤ 3/2 tiles); rendered street area 0 colours outside the palette; map
re-opened valid; content identical on rerun and on a fresh pipeline (only Tiled object ids grow); game walk: crossing
→ gate landing (1847, 1930), near footpath south under crowns to y 2246 unobstructed; trunk/hedge/lamp block,
pavers beside them walkable; 0 console errors; tsc OK. Before/after: `data/debug/beautify_test.png`.
**Left (needs approval):** rollout to every road + `--seed` flag + report of skipped segments. Seam at the south edge:
the untouched road below steps one tile east (both kerbs jog at row 161). twin_road unused on footpaths (two trunks
need 3 tiles). Palm / grass tuft still held. Not committed.

## 2026-11-17 (night, later) · Test area: soil pits removed, denser trees, hedge on both sides; crown/trunk gap fixed
**Asked:** "remove the dark soil pit beneath the trees, it is overlapping with the trunks and make it more dense.
there are a lot of trees irl in the road borders"; then, mid-turn: "keep the hedge on both sides of the road".
**Did:**
- `beautify.py`: no `tree_pit` / dirt-spill tiles under street trees (trunks stand on the pavers; the tiles stay in
  the atlas, unused, so ids do not move). `TREE_GAP` 5–9 → **3–5**, `TREE_SKIP` 0.15 → 0.05 (about 18 street trees
  in 42 rows instead of 7). Hedge (with posts) on **both** sides; gaps only at Krishna's door corridor and where a
  path meets it (the NAB side path at rows 158–159). The NAB-side shrub clusters gave way to the hedge (no lawn
  behind it there); shrubs behind the Krishna-side hedge stay.
- **Bug found while checking the flat-bottomed crowns:** on trees whose split row lies inside the trunk's tile (lime,
  ball, cypress, …) the canopy cell ended at the top of the trunk tile but the trunk piece only started at the split
  row: 5 pixel rows were in neither piece. `slice_trees.py`: the trunk piece now starts at min(split row, top of the
  trunk tile) (`trunk_from_row` in trees.json); its collision box moved to match. Tileset ids unchanged.
**Checked:** looked at 3× crops of both halves; beautify's asserts pass (widths, kerbs, ramps, nothing on crossings
or door rows, canopy limits); 0 colours outside the palette in the street; game walk crossing → gate and along the
footpath unobstructed, 0 console errors. `data/debug/beautify_test.png` updated.
**Left:** still the test area only, waiting for the user's approval before the rollout to every road.

## 2026-11-17 (late night) · Rollout: every road around the hostels, laid out like the approved test area
**Asked:** "cool, make all the roads surrounding the hostels this consistent." (= approval of the test area.)
**Did:**
- `blueprint.py` writes `data/phase1_roads.json`: every drawn road's centre line (map px) and width, the drive's two
  ends. (Noticed, not changed: blueprint never draws roundabouts: the `continue` for roundabout lines in the
  highway branch also skips the roundabout block below it. Fixing it would change the junctions; left for the user.)
- `beautify.py` rewritten from the hand-set test area to `layout_network()` (area `hostels`: all bhawans, margin 10):
  - straight pieces from the OSM lines (vertical / horizontal stretches; a way's kinks merged; position = weighted
    median, so the jog at Krishna's gate is straightened); diagonal stretches left as drawn with a clear zone round
    them; the front garden's drive ends kept clear (7 tiles);
  - each piece nudged by up to 2 tiles where that keeps the footpaths off buildings, and lined up with the road
    continuing from its end (no stepped junctions); collinear ends a few tiles apart joined (the Gandhi Marg gap);
    ends run on while the ground is road; at a clipped end the road goes on untouched;
  - rings by distance from the asphalt (8-neighbour): 1 kerb (strip facing the road; corners; inner corner blocks),
    2–4 pavers, 5 hedge with wire posts and corner pieces, 6 shrub clusters; junction corners pave themselves;
  - every path that meets the hedge ring → a 3-wide paved gap, the way through kept clear, and a zebra + ramps across
    the road; crossings within 4 tiles merge, hostel gates first;
  - trees 3–5 tiles apart on each piece's outer line (crown never over a crossing, a building or more than one tile
    of road; trunks of crossing roads ≥ 2 apart); 23 full-size lawn trees on open lawns; details per 20 tiles with
    spacing (lamps 4, bins / benches 6, barricades 12); `bench_h` for east-west footpaths; ground variety on every
    lawn of the region; footpaths fade into earth where they stop at a cleared zone.
  - new tiles `asphalt_dash_h`, `asphalt_zebra_h`, `kerb_inner_*`, `hedge_corner_*`; new prop `bench_h`.
  - `--areas-only` writes the region box for exterior.py; `--seed N` rerolls the planting.
- `exterior.py`: clamps beautify boxes at the map edge (a negative column made the slice empty). With the hostels
  region in `data/phase1_beautify.json`, exterior.py lays nothing for the hostels now (all its strips skipped).
- Pipeline: `beautify.py phase1 hostels --areas-only` (once) → `blueprint.py phase1 --force` → `exterior.py phase1
  --approved` → `beautify.py phase1 hostels` → `tiled_to_game.py tiled/maps/phase1.tmj`. Backup
  `phase1.backup-1117-rollout.tmj`.
**Result:** 17 road pieces, 250 street trees, 23 lawn trees, 237 shrubs, 69 lamps, 35 bins, 11 benches, 6 bike racks,
13 barricades, 10 crossings, ~7000 lawn cells varied. Skipped: the bend of `w312156566` (diagonal, north-west of
Malviya). 453 footpath lines narrower than 3 tiles where a building stands closer to the road (Ram and Malviya-A on
the 2-lane west road, placeholders by Krishna Marg, the Rotunda's stair path) — they narrow, nothing is drawn on a
building.
**Fixed on the way:** asphalt over the front garden's props near Ram Marg's top (asphalt now avoids blocked cells);
Krishna Marg north / south pieces at different columns (collinear line-up); a paved strip cutting Gandhi Marg (gap
join); doubled lamps / bins at corners and overlapping trunks (spacing); two zebras a row apart at Ram (merge); a bin
in Krishna's gate corridor after the merge (corridors always kept clear, gates first).
**Checked:** asserts (nothing on buildings / events / cleared zones, no object on a crossing or corridor); every
rendered pixel of the 15.5k beautified cells is in the palette except building art drawn over them (Rotunda, gatehouse
edges); map valid; rerun gives identical content; all 8 hostel gates reachable from the porch; game walks to
Krishna's and Ram's gates, along Krishna Marg and Gandhi Marg, bike down Krishna Marg at full speed, 0 console errors;
tsc OK. Overview: `data/debug/beautify_hostels.png`.
**Left:** roundabout bug in blueprint (above); roads outside the hostel district (Main Building side) untouched;
palm / grass tuft still held; nothing committed.

## 2026-11-17 (late night) · HANDOFF.md rewritten; summary of the 2026-11-16/17 sessions; corrections
**Asked:** "write the logs and handoff well".
**Did:**
- **HANDOFF.md rewritten from scratch** as a description of the current state (it had grown into §2–§2j update
  sections, several contradicting each other). New layout: state now · pipeline · tools table · buildings · streets
  · front garden · waiting on the user · known issues · preferences · how to check work · legacy · next steps.
  Facts re-checked before writing (git log/status, `tools/v4/` listing, map backups, playtest scripts, art folders).
- This entry (WORKLOG stays append-only; older entries untouched).
- Updated the auto-memory note `campus-game-project.md` (it still said 5 m/tile and Tiled as the editing tool).

**Summary of 2026-11-16/17 (detail in the entries above):**
| when | what | entry |
|---|---|---|
| 11-16 21:30 | smooth movement: whole-number zoom, player + camera snapped (`game/src/view.ts`, `WorldScene.place()`) | "Smoother movement and camera" |
| 11-16 22:20 | porch → Rotunda after the satellite: paving terrace, beds, centre line | "Porch→Rotunda area redone" |
| 11-16 22:55 | the user's complete Rotunda (`prep_rotunda()`, scale 0.70); collision grid 4 px | "New Rotunda art" |
| 11-16 23:15 | `sat_register.py` (satellite ↔ map); OSM road audit | "Satellite alignment tool" |
| 11-17 | one hostel image on all 8 bhawans, mirrored by gate side; VK lawn | "Hostel piece on every bhawan" |
| 11-17 | green courtyards; first street strips (`exterior.py`), then restyled after the street reference | "Green courtyards…", "Streets restyled…" |
| 11-17 eve | tree sheet sliced (`slice_trees.py`, Part A) | "Part A…" (two entries) |
| 11-17 night | `beautify.py` on a test street (Part B), then no pits / denser / hedge both sides | "Part B…", "Test area: soil pits removed…" |
| 11-17 late | rollout to every road around the hostels (`layout_network()`) | "Rollout: every road around the hostels" |

**Corrections to older entries (they were right when written, now superseded):**
- "Streets restyled… laid on six hostels" (11-17 later) and "Hostel piece…" mention `exterior.py` strips on the
  hostels: since the rollout `exterior.py` lays **nothing** for the hostels (it skips beautify's region); the streets
  are `beautify.py`'s.
- "Part B on the test area only" describes tree pits, `TREE_GAP` 5–9, shrub clusters on the NAB verge and the
  hand-set `krishna_test` area: pits were removed, the gap is 3–5, the verge has a hedge, and `krishna_test` no longer
  exists (replaced by `hostels`).
- 11-16 22:20: "the game now runs `phase1.generated.tmj`": superseded the same night; `phase1.tmj` is current.
- 11-16 23:15: Part C (roads after the satellite) was never done as planned; the roads around the hostels were done
  from OSM by `beautify.py` instead. The satellite screenshots are still wanted for VK's lawn and the missing lanes.
**Files:** `HANDOFF.md`, `WORKLOG.md`, `~/.claude/projects/-Users-ishanmalhotra-Documents-campus/memory/campus-game-project.md`.
**Left:** nothing new; open items are in HANDOFF §8–§9.

## 2026-11-17 18:05 · Pushed "added roads" update to GitHub
**Asked:** "push this to github with new update: added roads".
**Did:** Committed all uncommitted work on `garden-3m-scale` (hostel-district roads from `beautify.py`, street
tiles/props, Rotunda and bhawan pieces, regenerated map/game assets, photos and docs) and pushed to
`origin/garden-3m-scale`. `main` is unchanged.
**Left:** merge into `main` / PR is up to the user.

## 2026-11-20 03:00 · Launched the game on localhost
**Asked:** "launch this on localhost".
**Did:** Started the Vite dev server on port 5179 (`cd game && npx vite --port 5179 --strictPort --host 127.0.0.1`)
and opened http://127.0.0.1:5179/ in the browser. The earlier server had stopped, so this is a new one.
**Left:** the server runs in the background until it is stopped.

## 2026-11-20 · Avatar request: Pokémon sprites declined, code-drawn editor abandoned
**Asked:** "add sprites from all editions of pokemon games (Brendan, May etc) and add an option to edit your avatar as
settings in the map". Then the user sent ripped Brendan and May overworld sheets and said "do not build it yourself.
use these".
**Did:**
- Declined to add the official Pokémon trainer sprites (Brendan, May or any others). They're Nintendo/Game Freak's
  copyrighted characters and art, and this repo is public.
- Began an original avatar system: `tools/draw_player.py` rewritten to draw 48 styles (hair × headwear × bottoms) in
  key colours for recolouring at runtime. The user stopped it before it ran ("do not build it yourself"), so it was
  reverted with `git checkout -- tools/draw_player.py`. No sprites were written; `game/public/sprites/player.png` is
  unchanged.
**Left:** the avatar settings panel has not been built. Offered instead: the user makes their own original character
sheets (same free image tool as the buildings), and Claude slices them and adds an avatar picker to the game.

## 2026-11-20 · Gandhi statue roundabout, Stage 1 (diagnose + plan); stopped for approval
**Asked:** rebuild the Ram Marg / Gandhi Marg crossroads (Gandhi statue) as a real roundabout in 3 approved stages
(diagnose → island stamp → build). Stage 1 only; nothing in the map was changed.
**Found:**
- Junction centre: OSM statue `n3404339402` maps to tile (63.4, 201.4); OSM roundabout `w375917303` (centre-line ring
  ≈ 7.5 tiles across) is **not drawn**, because of the blueprint bug in HANDOFF §9 (`junction=roundabout` skipped).
  `data/phase1_roads.json` has `roundabouts: []`, so `beautify.py` treats it as a plain cross.
- Arms (from the `decor` layer): N = Ram Marg `w31175178`, asphalt cols 63–65 (3), dash col 64, toward NAB;
  E = Gandhi Marg `w285871639`, rows 200–202 (3), dash row 201; W = service `w312156567`, rows 200–201 (2), no
  centre line, toward SAC; S = service `w312156569`, cols 63–64 (2), no centre line, runs off the map edge (row 229).
  W and S are each ½ tile off the N/E axis.
- Defects in cells (62–64, 200–202): a `paver_2` tile at (63,201) in the middle of the carriageway; kerb pieces
  (`kerb_l` col 62 rows 200–201, `kerb_b`/`kerb_corner_se` row 202, `kerb_t`/`kerb_corner_ne` row 200, `kerb_inner_nw`)
  running across the junction, which cut the W and S arms off from the N/E asphalt; the N and E dashes stop short.
- Scale: the map is **3 m/tile** (not 5), so a real ~20 m island ≈ 7 tiles. The user's statue art (pasted image 5)
  has a ~5 px native grid: at 1:1 the platform ≈ 123 px ≈ 7.7 tiles and the statue ≈ 37 px tall (player frame 32 px),
  so a 10-tile island fits the art at 1:1.
- Constraint: Budh Bhawan's visible SE corner (≈ tile 55.6, 193.8) is 11.8 tiles from the centre. Plan A (island 10,
  ring 4 → asphalt r 9, kerb r 9–10, footpath r 10–13) overlaps it by ~1.2 tiles; plan B (ring 3, matching the arm
  asphalt → footpath r 9–12) by ~0.2.
- Displaced within r 13 (all `beautify.py` output): 14 street trees, 15 shrubs, 3 lamps, 1 bin, 2 barricades, the
  four corner hedges and ~180 shadow ellipses.
- `art/new/gandhi_island.png` does not exist yet (only `trees_sheet.png` in `art/new/`). Pasted image 5 has a white
  background and no lawn circle, unlike the Stage 2 description (magenta, with circle).
- The photos face west (SAC ahead, NAB right, "Ganga" left): in map terms SAC is the **W** arm, NAB the **N** arm, and
  the mural wall sits in the **SW** quadrant, not NW.
**Proposed:** centre (64.5, 201.5) (aligned with the N and E arms); W/S arms stay where they are (their ½-tile offset
vanishes where they flare into the ring). Build as a new step `tools/v4/roundabout.py` run after `beautify.py`, so a
pipeline rerun doesn't wipe it (hand edits to decor/props would be lost on the next beautify/blueprint run).
**Files:** new `data/debug/roundabout_before_4x.png`, `data/debug/roundabout_plan_4x.png` (sketch: red = asphalt edge
r 9, black = kerb r 10, blue = footpath edge r 13, orange dashed = plan B, yellow = zebras, magenta = Budh corner).
**Commands:** python one-liners reading `tiled/maps/phase1.tmj`, `data/campus_full.features.json`,
`data/phase1_frame.json`, cropping `data/debug/game_render.png` (rendered 2026-11-17 17:42, same as the map).
**Left:** waiting for approval of the size (plan A vs B) and for `art/new/gandhi_island.png`.

## 2026-11-20 · Gandhi statue roundabout, Stage 2 (island stamp); stopped for approval
**Asked:** "go plan a" (island 10 tiles, ring 4) and the statue art (a front/top view of the statue on its platform,
white background, no lawn): "you'll have to add the green circle underneath it yourself".
**Did:**
- Saved the art as `art/new/gandhi_statue_topdown.png` (new file; nothing overwritten). Camera: straight top-down /
  front view with horizontal and vertical edges, not isometric.
- New `tools/v4/statue_island.py` (deterministic, ~2 s): white background keyed by flood fill (tol 30), largest piece
  kept (0 specks; no watermark/sparkle in this image), native grid measured 5.12 px (1024/200, offset 4.1/4.15) → art
  120 × 163 px at 1:1; island drawn round it: map grass tiles, 1 px dark outline, 3 px white kerb, 1 px grey inner
  edge, 16 px stone path to the north (hidden behind the statue) and south; platform centred on the circle (its
  corners 73.8 px from the centre, inside the 75 px kerb).
- Canvas 11 × 13 tiles (176 × 208): circle Ø160 centred on a tile centre, 2 tiles above it for the statue. Split
  row 77 (the platform's top edge): statue + upper pedestal → `gandhi_island_top.png` (176 × 80, for `above`), the
  whole island → `gandhi_island_base.png`. Collision: 40 rectangles on the game's 4 px cells inside the kerb circle,
  also as `gandhi_island_collision.png` (the mask format `tiled_to_game.py` reads for `buildings` objects).
- `tiled/tilesets/statues.tsj` (collection of images, 2 tiles, bottom-left aligned) with name, footprint_w/h,
  split_row, collision (+ collision_rects). **JSON `.tsj`, not `.tsx` as asked:** `tiled_to_game.py` loads every
  tileset with `json.load`, and all the others are `.tsj`.
- Checks: 0 off-palette colours, alpha only 0/255, no pale fringe; renders `data/debug/statue_island_{asphalt,grass,
  collision}_4x.png` (with a stand-in player north of the island: it is hidden behind the statue as intended).
**Failed attempts (all fixed, in order):**
1. plain palette snap → camouflage blotches on the bronze (no dark olives in the locked palette: shades jumped
   between a grey, a green and a brown) → bronze mapped by brightness onto one ramp `BRONZE_RAMP` (khaki ×2, sage,
   olive-green, near-black teal, near-black).
2. the bronze test also caught beige shadow lines and the brown plaque → limited to the art above the platform top.
3. sampler "most common colour of the middle 3 × 3" broke outlines and the plaque (dotted edges) → tried closing line
   gaps and despeckling, which thickened lines and erased the plaque → reverted; replaced by a dark-priority sampler
   (centre pixel, or the darkest if ≥ 30 % of the cell is line). Compared the 3 samplers side by side first.
4. enclosed white background between the legs/staff showed as white blocks → near-white art pixels made clear (55 px).
5. platform grain → stone flattened to 14 colours, the light faces to their 3 main colours, then lone pixels
   (≤ 1 same-colour neighbour) recoloured (258 px). 8 colours was flat but lost the plaque, so not used.
**Placement for Stage 3:** base object top-left at tile (59, 194) → circle centre (64.5, 201.5); top image in the
`above` layer at cell (59, 198) (bottom-left anchor).
**Files:** `art/new/gandhi_statue_topdown.png` (new), `tools/v4/statue_island.py` (new), `tiled/generated/statues/*`,
`tiled/tilesets/statues.tsj`, `data/debug/statue_island_*_4x.png`. Map not touched.
**Command:** `python3 tools/v4/statue_island.py`.
**Left:** Stage 3 (build the roundabout) after the user approves the stamp.

## 2026-11-20 · Gandhi statue roundabout, Stage 3 (built); stopped for approval
**Asked:** "go for it, ensure the island grass green colour matches the grass colour from the rest of the map, and the
roads have enough space for a full proper crossing".
**Did:**
- Backup: `tiled/maps/phase1.backup-1120-roundabout.tmj` (the map as `beautify.py` left it, 2026-11-17).
- New `tools/v4/roundabout.py` (deterministic, ~2 s), a new pipeline step **after `beautify.py`, before
  `tiled_to_game.py`**. Centre tile (64.5, 201.5); island r 80 px; ring asphalt to r 144 (4 tiles); fillets 40 px
  (smooth minimum of distances). Everything in cells 47–82 × 184–219 is generated pixel by pixel from the distance to
  the asphalt, with the same bands as `beautify.py` (kerb 0–4 px in 8 px stripes, shade line, pavers to 64, hedge
  66–78 with `exterior.hedge()`'s colouring), then cut into 16 px tiles: cells with the same layout as before keep their
  tile (742), the others (554) take the generated pixels: existing street tile if identical, else one of 250 new tiles
  in `tiled/generated/roundabout/roundabout_tiles.png` + `tiled/tilesets/roundabout.tsj` (firstgid 237; `statues.tsj` is
  235). Kerb ring = generated tiles (16 px kerb tiles can't curve), as the request allowed.
- Crossings: zebra 2 tiles long over the full asphalt width + ramp tiles on both kerbs, on the first straight stretch
  past each fillet: N rows 188–189, E cols 76–77, W cols 51–52, S rows 213–214. Ring footpath (3 tiles + kerb) all round;
  dashed centre lines on Ram Marg and Gandhi Marg up to the ring (the service roads have none anywhere, so none added);
  a dashed lane circle at r 112 px.
- Island stamp on `buildings` (object `rb:gandhi_island`, gid 235, x 944, y 3312), its top on `above` at cell (59, 198).
  Collision layer: 40 `rb:island` rectangles + 152 `rb:hedge` rectangles (4 px cells of the new curved hedge; the
  hedges are solid everywhere else too). Zone event "Gandhi Statue" (888, 3080, 288 × 288) = the ring.
- Removed `beautify.py`'s objects within 16.5 tiles: 23 trees (trunks + canopies), 18 shrubs, 5 lamps, 3 bins,
  3 barricades, 212 shadows. Listed in `data/phase1_roundabout.json`.
- Grass: island lawn = the street grass tiles = the map lawn: (110, 213, 149) base, (89, 184, 121) and (113, 214, 153);
  checked by pixel counts on the render.
**Failed attempts (fixed):**
1. The "same layout as before → keep the tile" test modelled E and W as one road running through, so two stubs of the
   W arm's straight hedge (cells 53–55 × 206, 69 × 210–212) stayed on the new footpath → model = four arms each ending at
   the centre; rerun from the backup.
2. Kerb stripes on the curve by angle × radius left a 21–24 px block at each straight/curve join; per-quadrant phase
   fit by angle still did, because next to the arms the kerb runs almost radially → the kerb line is now traced (rays
   + bisection) and stripes follow its true length, stretched 0.99–1.03 per quadrant so they run on into the next
   arm's straight kerb.
**Checks:** render crops at 2x and 4x (`data/debug/game_render.png`); collision crop (`game_collision.png`); flood fill
over `main.meta.json` collision with a 12 × 8 px feet box from the N arm: ring all round (450/450 points), every arm's
far end, every zebra, all four footpath corners and the spawn porch reachable; island 0/249 standable. Off-palette
colours 0 in all new images. The game data has the "Gandhi Statue" zone.
**Outside the junction:** 117 cells changed beyond 13 tiles from the centre (cols 49–82, rows 184–216): the fillets,
footpath corners and curved hedges where they rejoin the straight streets; no building, door, gate path or event touched.
**Doesn't fit:** Budh Bhawan's SE corner covers the outer ~1.2 tiles of the NW ring footpath (cols 53.9–55.5,
rows 192–194; ≥ 44 px of footpath stays clear by the kerb) and that quadrant's hedge passes under it (hidden).
**Left / not done:** one stray dark kerb pixel where a straight kerb hands over to a curve (cosmetic); the mural wall
(held); trees/lamps round the roundabout (to come from a beautify pass that knows about it); a rerun of `beautify.py`
must be followed by `roundabout.py`; blueprint's roundabout bug (HANDOFF §9) still unfixed (the Patel roundabout by
Gandhi Bhawan is untouched). No headless browser playtest this time (collision flood fill only).
**Files:** `tools/v4/roundabout.py` (new), `tiled/maps/phase1.tmj`, `tiled/maps/phase1.backup-1120-roundabout.tmj`,
`tiled/generated/roundabout/*`, `tiled/tilesets/roundabout.tsj`, `data/phase1_roundabout.json`, game outputs from
`tiled_to_game.py` (`game/public/*`, `data/debug/game_*.png`), `data/debug/roundabout.png` (before | after, 4x).
**Commands:** `python3 tools/v4/roundabout.py`; `python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj`.

## 2026-11-20 · Roundabout: dashed lane circle removed; rest approved
**Asked:** "remove the dashed lane circle, rest looks good".
**Did:** `tools/v4/roundabout.py`: new switch `LANE_CIRCLE = False` (the code stays, off). Reran from the backup:
`cp -p tiled/maps/phase1.backup-1120-roundabout.tmj tiled/maps/phase1.tmj && python3 tools/v4/roundabout.py &&
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj`. 554 cells changed as before; new tiles 250 → 202 (the
circle's dashes made many ring tiles unique). Rebuilt `data/debug/roundabout.png` (before | after).
**Checked:** 4x crop of the ring: plain asphalt, centre lines on Ram Marg / Gandhi Marg still end at the ring.
**Left:** Stage 3 approved by the user. Still held: the mural wall, trees / lamps round the roundabout. Nothing committed.

## 2026-11-20 · Patel statue roundabout (Krishna Marg × Gandhi Marg), built like the Gandhi one
**Asked:** the Patel statue art (same layout as Gandhi's: front/top view on the same platform, white background),
"similarly place the patel statue".
**Found:** OSM statue `n3404339403` → tile (110.0, 201.6); OSM roundabout `w285871636` not drawn (blueprint bug). The
junction in `decor` is a clean cross of four 3-tile arms: Krishna Marg cols 107–109 (dash col 108), Gandhi Marg rows
200–202 (dash row 201) → centre (108.5, 201.5). Nearest building art: Gandhi Bhawan SW corner 11.8 tiles, Shankar
Bhawan NW corner 11.3 (Budh was 11.8 at the Gandhi roundabout) → same plan A.
**Did:**
- Art saved as `art/new/patel_statue_topdown.png` (new file).
- `tools/v4/statue_island.py` → `STATUES` list (gandhi, patel); one `build()` per statue; `statues.tsj` has 2 tiles per
  statue (Gandhi ids 0/1 unchanged, Patel 2/3) with a `statue` property. Gandhi stamp byte-identical after the change.
  Patel: grid 5.12 px, 120 × 163 art px, same platform, split row 77, 0 off-palette. Debug renders renamed
  `data/debug/statue_island_<key>_{asphalt,grass,collision}_4x.png`.
- `tools/v4/roundabout.py` → `ROUNDABOUTS` list (centre, zone, arms, statue key, banner name); `build_cells()` /
  `place()` per roundabout; new tiles shared in one atlas (262); both tilesets dropped and re-added with fresh first
  gids every run (statues 235, roundabout 239), with a check that no decor cell is left on an old gid; old statue tops
  cleared from `above`; zones marked `source = rb:roundabout.py`.
- Patel: 559 cells changed, 737 kept; zebras + ramps N rows 188–189, E cols 120–121, W cols 95–96, S rows 213–214; dashed
  centre lines on all four arms (all Krishna / Gandhi Marg) up to the ring; island at (1648, 3312), top at cell
  (103, 198); 40 island + 144 hedge collision rects; zone "Patel Statue" (1592, 3080, 288 × 288). Removed 52 props
  (trees, shrubs, lamps, bins, barricades), 24 canopies, 215 shadows within 16.5 tiles.
**Checked:** Gandhi area of the render pixel-identical to the approved one (0 px differ). Patel at 2x and 4x (kerb
joins continuous, stretch 0.98–1.02). Flood fill from the spawn porch: both rings 270/270, all 8 arm ends, all 8
footpath corners reachable; both islands 0 standable. Both zones in `main.meta.json`.
**Doesn't fit:** Gandhi Bhawan's SW corner covers cols 117.4–119.1 × rows 192.1–193.9 of the NE footpath (≥ 44 px clear
by the kerb); Shankar Bhawan's NW corner covers cols 117.4–119.8 × rows 208.2–210.9 of the SE footpath (≥ 36.7 px ≈ 2.3
tiles clear). The hedges of those quadrants run hidden under the corners. 126 cells changed beyond 13 tiles from the
Patel centre (fillets, footpath corners, curved hedges rejoining the streets).
**Files:** `art/new/patel_statue_topdown.png`, `tools/v4/statue_island.py`, `tools/v4/roundabout.py`,
`tiled/generated/statues/patel_island_*`, `tiled/tilesets/statues.tsj`, `tiled/generated/roundabout/*`,
`tiled/tilesets/roundabout.tsj`, `tiled/maps/phase1.tmj`, `data/phase1_roundabout.json` (now one entry per
roundabout), game outputs, `data/debug/roundabout_patel.png` (before | after; the "before" rendered from the backup
map, then the current map converted again and checked byte-identical).
**Commands:** `python3 tools/v4/statue_island.py`; `cp -p tiled/maps/phase1.backup-1120-roundabout.tmj tiled/maps/phase1.tmj
&& python3 tools/v4/roundabout.py && python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj`.
**Left:** approval; trees / lamps round both roundabouts; nothing committed.
