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
