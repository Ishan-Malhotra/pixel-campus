# Handoff: BITS Pilani Campus Explorer

_Last updated: 2026-11-20 (Gandhi statue roundabout). Rewritten from scratch as a description of the **current** state; the history
of how it got here is in `WORKLOG.md`, which is append-only._

**Read in this order:** this file → the last few entries of `WORKLOG.md` → `art/pieces/README.md` (the user's art
checklist). `SPEC.md` and `tiled/GUIDE.md` are partly outdated (see §10).

**Two rules from the user that apply to every session:**
- **Log everything in `WORKLOG.md`:** one entry per piece of work, written as you go. Each entry says what was asked, what changed and why, the files, the commands, how it was checked, and what is left (including failed attempts). Never edit or delete an old entry; correct it with a new one.
- **Update this file before you finish.** It must always describe the current state, not the history.

---

## 1. The project in one paragraph
A browser game in the style of Pokémon Emerald: a top-down pixel-art **BITS Pilani (Pilani) campus** you can walk
and cycle around (outdoors only for v1). The user, Ishan, is a student there and not a pixel artist. They generate
the art in a free image tool; Claude cannot generate raster images. The layout must match the real campus: geometry
comes from **OpenStreetMap**, and is checked against **satellite** screenshots and the user's street photos. The game
is Phaser 3 + TypeScript (`game/`); maps are built by Python scripts (`tools/v4/`) through Tiled JSON (`tiled/`).

## 2. State right now
- **Map:** `tiled/maps/phase1.tmj`, **187 × 230 tiles of 16 px**, **3 m per tile** (one map pixel = one pixel of the
  user's art). OSM is rotated **−8.75°** so the street grid is axis-aligned. Spawn at the Clock Tower porch
  (1382, 1122).
- **Phase 1 area:**
  - Main Building, Rotunda, NAB blocks and the Snake Path;
  - the hostels Ram, Budh, Krishna, Gandhi, Shankar, Vishwakarma (VK), Bhagirath and Malviya-A;
  - the messes;
  - down to Gandhi Marg and a little beyond.
- **Buildings with the user's art:**
  - Main Building (FD3 + Clock Tower + FD2);
  - the Rotunda with its amphitheatre;
  - all 8 hostels (one image, mirrored where the gate faces east).

  Everything else is a plain placeholder block: messes, NAB, the Warden's Residence, small buildings.
- **Ground:**
  - **Front garden:** the area between the FD wings and the Rotunda is hand-designed in `blueprint.py`.
  - **Hostel district roads:** every road around the hostels is laid out by `beautify.py` in the look the user approved:
    - striped kerbs and 3-tile herringbone footpaths;
    - hedges on both sides;
    - dense tree rows;
    - zebra crossings at every gate and path;
    - lamps, bins, benches, bike racks and shrubs;
    - lawn trees and grass variety.
  - **Rest of the map:** plain terrain.
- **Game:**
  - Movement is smooth: a whole-number camera zoom with the player and camera snapped together.
  - Bike on B; tree canopies draw above the player.
  - Collision uses 4 px cells.
  - Last checked: 0 console errors, all 8 hostel gates reachable from the porch, and `npx tsc` clean.
- **Git:**
  - Branch `garden-3m-scale`; the last commit is `67b309f` (2026-11-12, pushed to `origin`).
  - **Everything since then is uncommitted:** about 206 changed or new files. The user has not asked to commit.
  - The repo is public (github.com/Ishan-Malhotra/pixel-campus).
- **Dev server:** started on 2026-11-16 at http://127.0.0.1:5179 (`cd game && npx vite --port 5179 --strictPort --host 127.0.0.1`); it may still be running.

## 3. The pipeline (run from the repo root, in this order)
```
python3 tools/v4/blueprint.py phase1 --force     # OSM -> Tiled map, stamps, front garden; ~60 s
python3 tools/v4/exterior.py phase1 --approved   # legacy street strips; lays nothing inside beautify's area now
python3 tools/v4/beautify.py phase1 hostels      # roads, footpaths, trees, details round the hostels; ~10 s
python3 tools/v4/roundabout.py                   # the statue roundabouts (Gandhi, Patel) over beautify's crossings; ~3 s (always after beautify)
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj   # Tiled -> game/public/*; ~60 s
cd game && npx tsc --noEmit -p .                 # type-check (only needed if game/src changed)
```
- **Skipping a step** loses that step's work: a blueprint run wipes the decor/props it does not own, so always run
  the whole chain.
- **Tiled:** the user said "avoid wasting effort on tiled". `blueprint.py --force` may replace `phase1.tmj` freely,
  but **back it up first** (`cp -p tiled/maps/phase1.tmj tiled/maps/phase1.backup-<date>-<what>.tmj`). Backups so far:
  `phase1.backup-{1747,2130,2233,1116-2250,1117-hostels,1117-exterior,1117-beautify,1117-rollout,1120-roundabout}.tmj`. The user has
  never edited the map in Tiled; if they ever do, stop and ask before `--force`.
- **Plain `python3`, never `python3 -I`:** Pillow and numpy are in the user's site-packages.
- Every step is **deterministic:** reruns give the same map content; only Tiled object ids grow.

## 4. The tools (`tools/v4/`)
| script | does | writes |
|---|---|---|
| `blueprint.py` | OSM → rotated map; ground as Wang terrain tiles; building slots from OSM footprints; stamps (see §5); the front garden; dashed centre lines on big roads | `tiled/maps/phase1.tmj` (or `.generated.tmj` without `--force`), `tiled/tilesets/{terrain,buildings,props}.tsj`, `tiled/stamps/*`, `data/phase1_slots.json` (slots, hostel gates), `data/phase1_roads.json` (road centre lines, drive ends), `data/phase1_frame.json` (map frame), `data/debug/phase1_*.png` |
| `tiled_kit.py` | the terrain tiles and props cut from the user's art (`key_cut`, `flood_cut`); the locked 128-colour palette `PAL_IMG` | `tiled/tilesets/terrain.*`, `tiled/props/*` |
| `tiled_to_game.py` | Tiled → game. Smooths terrain outlines (`SMOOTH`); decor tiles drawn over the terrain; `paving` / `flowerbed` / `roadline` / `hedge` shapes; **`shadows`** layer (ellipses, `opacity`, darkened then snapped to the palette); tiles taller than the grid anchored bottom-left (canopies on `above`); `collision_x/y/w/h` tile properties as exact collision boxes; upright props depth-sorted against the player | `game/public/maps/main.json`, `main.meta.json`, `minimap.png`, `tiles/campus.png`, `props/*`, `data/debug/game_render.png`, `game_collision.png` |
| `slice_trees.py` | the user's tree sheet `art/new/trees_sheet.png` → sprites. Colour-keyed (two background purples), watermark removed, sampled on the art's own pixel grid (2.91 px), palette-snapped, rims cleaned. Trees: whole / canopy / trunk / `canopy_cell` (for `above`); `_road` copies of the umbrella and twin with 3-tile crowns. **Palm and grass tuft are held** (not cut) until the user decides | `tiled/generated/trees/*`, `tiled/tilesets/trees.tsj` (39 images, first 24 ids fixed), `data/debug/trees_on_{grass,roof}.png` |
| `beautify.py` | street layout for an area (`AREAS`, currently `hostels`). See §6 | `tiled/generated/street/*`, `tiled/tilesets/street.tsj` + `street_objects.tsj`, the map's `decor` / `props` / `above` / `shadows` layers, `data/phase1_beautify.json` |
| `statue_island.py` | the user's statue art (`STATUES`: `art/new/{gandhi,patel}_statue_topdown.png`) → roundabout island stamps (2 tiles each in `statues.tsj`): 10-tile lawn circle with a white kerb, statue at 1:1 (5.12 px art grid), bronze on one palette ramp, statue top split for `above`, collision | `tiled/generated/statues/*`, `tiled/tilesets/statues.tsj`, `data/debug/statue_island_*_4x.png` |
| `roundabout.py` | the statue roundabouts (`ROUNDABOUTS`): Gandhi at tile (64.5, 201.5), Patel at (108.5, 201.5); each: ring 4 tiles, curved striped kerbs, ring footpath, curved hedges, zebras + ramps on all four arms, no lane circle, island stamp, collision rects, "Gandhi Statue" zone; generated per pixel and cut into tiles (cells unchanged keep their tiles); removes beautify's props within 16.5 tiles | the map (`decor`, `buildings`, `above`, `props`, `shadows`, `collision`, `events`; objects `rb:*`), `tiled/generated/roundabout/*`, `tiled/tilesets/roundabout.tsj`, `data/phase1_roundabout.json` |
| `exterior.py` | the first, superseded street strips (2-tile footpath per hostel). Still in the pipeline but it skips every box listed in `data/phase1_beautify.json`, so it lays nothing for the hostels | `tiled/generated/exterior_tiles.*`, `tree_street_{a,b}.png`, `tiled/tilesets/exterior*.tsj`, `data/phase1_exterior.json` |
| `sat_register.py` | lines up every screenshot in `art/satellite/` with the map (roofs vs OSM buildings, or hand control points in `registration.json`) | `art/satellite/registration.json`, `data/debug/sat_{onmap,overlay,side}.png`, `tiled/underlay/phase1_satellite.png` |

## 5. Buildings
**User-owned files:** `art/pieces/*`, `art/stamps/*`, `art/reference_*`, `art/new/*` and `art/photos/*` are the user's. Never
overwrite them. Cleaned pieces and collision masks are made **once** from `art/pieces/_raw/` and are never
regenerated if they exist; the user may edit them.

| building | stamp | from | notes |
|---|---|---|---|
| Main Building (FD3 + tower + FD2) | `main_building` | `art/pieces/clock tower body.png` + `fd.png`, positions in `main_building_layout.json` (`compose_pieces()`) | rebuilt every run; fitted to the OSM width; porch 20 m south of the OSM Clock Tower point (`PORCH_SOUTH_M`) |
| Rotunda | `rotunda_piece` | `art/pieces/rotunda.png` + `rotunda_collision.png`, cleaned from `_raw/rotunda_raw.png` (`prep_rotunda()`) | `ROT_SCALE = 0.70` (plaza ≈ 61 m, checked on the satellite); enter by the west stair path or the south stub; the arcade blocks |
| 8 hostels | `bhawan` / `bhawan_m` (mirrored) | `art/pieces/bhawan.png` + `bhawan_collision.png` from `_raw/bhawan_raw.png` (`prep_bhawan()`) | always 21 × 32 tiles, centred on the OSM footprint; gate on the west wall as drawn (VK, Bhagirath, Krishna, Gandhi, Shankar, Vyas), east when mirrored (Ram, Budh, Malviya-A/-B, Rana Pratap, Ashok); courtyards repainted as lawn on the stamp; a dirt path runs from each gate to the road (`gate_path()`); VK keeps `LAWNS = 30` m clear in front of its gate (a guess until a satellite screenshot) |
| messes, NAB, warden's residence, FD1, SAC, ~29 small buildings | placeholder blocks | — | waiting for art (§8) |

Old cut-outs (`main_west`, `fd2`, `rotunda`, `rotunda_art` in `art/stamps/`) are no longer built or placed. Their
files are left alone because they're the user's.

## 6. Streets around the hostels (`beautify.py phase1 hostels`)
- **Area:** every road within 10 tiles of the bhawans (`AREAS['hostels']`, `margin=10`). The region box is in
  `data/phase1_beautify.json`, and `exterior.py` leaves that box alone. `--areas-only` rewrites the box without laying
  anything.
- **Roads:**
  - Straight pieces come from the OSM centre lines in `data/phase1_roads.json`. Kinks are merged and positioned by
    weighted median, so the jog at Krishna's gate is straightened.
  - Each piece shifts by up to 2 tiles to keep footpaths off buildings, and lines up with the road continuing from
    its end.
  - Collinear ends up to 8 tiles apart are joined (Gandhi Marg).
  - Diagonal stretches are left as drawn, and the two ends of the front garden's drive are kept clear (`DRIVE_CLEAR`).
  - Asphalt is 3 tiles on 4-tile roads (dashed centre line) and 2 tiles on service roads. It has subtle cracks, worn
    patches and manholes.
- **Rings by distance from the asphalt:** 1 = striped kerb (the strip faces the road; corner and inner-corner pieces);
  2–4 = herringbone pavers; 5 = hedge with wire posts and corner pieces; 6 = shrub clusters. Junction corners pave
  themselves.
- **Crossings:** every path that meets the hedge ring (every hostel gate has one) gets three things:
  - a 3-wide paved gap;
  - a clear way through;
  - a zebra crossing with tactile ramps.

  Crossings less than 4 tiles apart merge, and a hostel gate's crossing wins.
- **Trees (the user wanted dense rows, as on the real roads):**
  - Street trees stand 3–5 tiles apart (`TREE_GAP`, `TREE_SKIP = 0.05`) on the footpath's outer line, straight on the
    pavers (no soil pit; the user removed it).
  - Crowns are at most 3 tiles wide (large) or 2 (medium). They never cover a crossing or a building, and never hang
    more than 1 tile over the road.
  - Shadows are 25 %, with 12 % dappled patches.
  - Full-size umbrella, twin, round and column trees stand on open lawns (`LAWN_CELLS_PER_TREE`).
  - The street copy of the twin is never used on footpaths, because its two trunks need 3 tiles.
- **Details per 20 tiles:**
  - 2 lamps and 1 bin;
  - a bench or bike rack where a building is close; bike racks only go on north–south footpaths;
  - sometimes a barricade.

  Spacing rules prevent doubles at corners.
- **Lawns:** grass without the old dot grid, plus tufts, small flowers, earth near paths and trunks, and faint
  irregular darker patches.
- **Flags:**
  - `--seed N` rerolls all the planting and details (default `SEED = 20261117`);
  - `--assets` remakes only the tiles and props.
- **Last run:** 17 road pieces, 250 street trees, 23 lawn trees, 237 shrubs, 69 lamps, 35 bins, 11 benches, 6 racks,
  13 barricades, 10 crossings. Overview: `data/debug/beautify_hostels.png`; the approved test street:
  `data/debug/beautify_test.png`.

## 7. Front garden and Rotunda surroundings (`blueprint.py`, section "front garden")
- **The drive:** the OSM driveway `w285869287`, redrawn as one smooth arc past the porch. It has median hedges, a
  paved terrace up to the Rotunda (a `paving` polygon with slabs in rings), and a dashed centre line.
- **Hedges:** drawn as `hedge` polylines, in the style of the art.
- **Lawns:** both lawns are planted like `art/reference_main.png`: tall grass, palms, shrubs, the vegetable bed,
  conifers, flags and lamps.
- **Positions:** all of these are measured from the stamps' alpha, so they follow if a stamp changes.

## 8. Waiting on the user
1. **Satellite screenshots:** straight-down, north-up Google Maps screenshots of the strip north of the Main Building,
   the east strip, and the south edge, dropped into `art/satellite/`. Current coverage is 61 % of the map. They would
   give VK's real lawn depth, the lanes OSM lacks, and the tree and bare-ground areas.
2. **Art and entrance sides:**
   - Messes: `mess.png`, plus the entrance side.
   - NAB: `nab.png` (lawn roofs, as in the aerial photos), plus the entrance side.
   - Library: `library.png`, entrance on the left wall.
   - Optional: `fd1.png`, `sac.png`, `small_house.png`.

   The checklist with shapes and sizes is `art/pieces/README.md`. Buildings whose door is on a side wall: draw the
   door on the **left** and it gets mirrored where it faces east.
3. **Decisions not yet made:**
   - the palm and the grass tuft from the tree sheet (held);
   - a doorway through the Rotunda's arcade from the terrace (none now);
   - whether to keep the 7–9 MB aerial photos in `art/photos/` in the public repo;
   - whether to fix the roundabout bug (§9);
   - committing and pushing.
   - **Patel statue roundabout** (Krishna Marg × Gandhi Marg): built 2026-11-20, waiting for approval
     (`data/debug/roundabout_patel.png`).
   - **Gandhi statue roundabout:** built and approved 2026-11-20 (no lane circle: `LANE_CIRCLE = False`;
     `data/debug/roundabout.png`). Held for later: the mural wall (SW corner in map terms) and trees / lamps round it.

## 9. Known issues
- **Roundabout at the Gandhi statue:** done by `roundabout.py` (not by blueprint). Budh Bhawan's SE corner covers the
  outer ~1.2 tiles of its NW footpath; one stray dark kerb pixel at each straight/curve join. Rerunning `beautify.py`
  without `roundabout.py` after it brings back the old crossing.
- **Patel roundabout:** Gandhi Bhawan's SW and Shankar Bhawan's NW corners cover the outer edge of two footpath
  corners (≥ 2.3 tiles stay clear by the kerb).
- **Roundabouts are never drawn by blueprint** (existing blueprint bug); both statue roundabouts come from `roundabout.py`. In the highway branch, `if t.get('junction') ==
  'roundabout': continue` also skips the roundabout block below it. Fixing it changes junction shapes, so it's left
  for the user to decide.
- **Narrow footpaths:** 453 footpath lines are narrower than 3 tiles. These are places where a building stands closer
  to the road than the footpath needs (Ram and Malviya-A on the 2-lane west road, the placeholders by Krishna Marg,
  the Rotunda's stair path). The footpath narrows there; nothing is drawn on a building.
- **North-west bend:** the bend of the road north-west of Malviya (`w312156566`) is diagonal, so it's left as drawn,
  with faded footpath ends.
- **Roads outside the hostel district** (the Main Building side, the far east) still have the plain terrain look.
- **Rotunda:** its east stairs end in a closed corner, as in the art.
- **Main Building depth:** the art compresses the building north–south compared with OSM.
- **Stray slot:** a small OSM slot sits on the lawn west of the Main Building.
- **Tiled view:** in Tiled itself the roads still look stair-stepped; only the game smooths them.

## 10. User preferences (hard-won; follow them)
- **Free tools only;** flag any paid step first. The user's own generated images are the art standard. They rejected
  code-drawn buildings as "AI-looking": cut buildings from their images, never redraw them. Small props drawn in the
  palette (bin, bench, rack, barricade) have been accepted.
- **Never stitch whole scene images.** Buildings are stamps; the ground is tiles. Never overwrite the user's art.
  Use only the locked palette and nearest-neighbour scaling, with no anti-aliasing.
- **Animate only flags and grass.** No clouds, no swaying trees.
- **Accuracy against the satellite and photos matters.** Geometry comes from OSM. References stay local in
  `art/satellite/` and `art/photos/` and are never shipped.
- **For bigger changes the user often asks to do one area first, show it, and stop for approval.** Respect that.
  Always look at your own renders (crops, never the full map in one image) before reporting, and fix what's wrong
  first.
- **Not a Tiled or image-editing expert.** Give click-by-click steps if they must do something. Don't spend effort
  on Tiled-only polish.
- **Answer questions briefly; act when the request is clear.**

## 11. Checking your work
- **Renders** in `data/debug/`:
  - `game_render.png` is the map as the game draws it, the main one to look at. Crop it; don't view it whole.
  - `game_collision.png` shows blocked cells in red.
  - Street work: `beautify_hostels.png`, `beautify_test.png`.
  - Trees: `trees_on_grass.png`, `trees_on_roof.png`.
  - Satellite: `sat_overlay.png`.
- **Headless playtests:** scripts in `/tmp/campus-check/`, using the system Chrome with `--use-angle=swiftshader`.
  `/tmp` may be wiped; recreate with `npm i playwright-core` in a fresh dir.
  - `roll.mjs`: walks to Krishna's and Ram's gates and along Krishna Marg and Gandhi Marg; bikes down Krishna Marg.
  - `smooth.mjs`: camera and player offset at three screen sizes; should be 0 px.
  - `rot.mjs`: Rotunda entrances.
- **In the game:** `window.__game` is exposed in dev. `scene('world')` has `pos`, `player`, `onBike`,
  `toggleBike()` and `canStand(x, y)`.
- **Reachability check:** a flood fill over `game/public/maps/main.meta.json` collision with the game's hitbox
  (10 × 5 px feet). The code is in the WORKLOG entries for 2026-11-17; every hostel gate should be reachable from
  the spawn.

## 12. Legacy (don't build on these)
- **v1:** the OSM-extruded procedural map (deleted).
- **v2 (`tools/v2/`):** the code-drawn map, rejected; it's only used for old wall measurements.
- **v3 (`tools/v3/`):** stitched scene images, rejected. Its `props_extract.py` made the flag and palm cut-outs that
  `tiled_kit.py` still uses.
- **The web "god mode" editor** (`game/editor.html`): superseded by Tiled.
- **`SPEC.md`:** describes an export-package workflow that was never built.
- **`exterior.py`:** superseded by `beautify.py` for every hostel road. Kept because it's harmless and its tiles are
  reused.
- **The last plan file** (`~/.claude/plans/adaptive-finding-quilt.md`): the exterior-strip plan, now done and
  superseded.

## 13. Suggested next steps
1. When the satellite screenshots arrive: run `sat_register.py`, check `sat_overlay.png`, set VK's real lawn depth
   (`LAWNS` in `blueprint.py`), and add the lanes OSM lacks (planned as `data/phase1_corrections.json`).
2. When `mess.png`, `nab.png` or `library.png` arrive: add a loader like `prep_bhawan()` (clean once, size to the OSM
   footprint, mirror by entrance side, gate path). `beautify.py` picks up their gates and paths automatically.
3. If the user agrees: fix the roundabout bug, then extend `beautify.py` with a new `AREAS` entry for the Main
   Building side.
4. Commit and push when the user asks (branch `garden-3m-scale`).
