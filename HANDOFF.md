# Handoff log: BITS Pilani Campus Explorer
_Last updated: 2026-11-11, 22:40 (map scale now 3 m/tile; front garden redone after the art; paved terrace between the drive and the Rotunda). Read this first, then the latest entries of `WORKLOG.md`, then `SPEC.md` (partly outdated, see §6) and `tiled/GUIDE.md`._

**GitHub:** [Ishan-Malhotra/pixel-campus](https://github.com/Ishan-Malhotra/pixel-campus) (public). Only the
initial commit is there; the work in §2c is not committed (the user has not asked).

**Logging rule (from the user):** every agent logs everything it does in `WORKLOG.md` (what, why, files, commands,
checks, what is left). This file is the summary of the current state; `WORKLOG.md` is the history.

**Newest status is §2d**, then §2c. §2 and §2b are older and partly superseded (sizes there are at the old 5 m scale).

## 1. What the project is
A browser game in the style of Pokémon Emerald: a top-down, pixel-art version of the **BITS Pilani (Pilani)
campus** that you can walk and cycle around. v1 is outdoors only. The user (Ishan) is a student there and is not a
pixel artist. They generate art with an image model and want the layout to match the **satellite view**.

## 2. Where we are right now
**Current approach (v4):** this is the Emerald hybrid of tile-based ground plus building "stamps". The user picked
it after big stitched AI images kept failing (seams, overlaps, scale and colour mismatches). There are three steps:

1. **Blueprint from OpenStreetMap:**
   - `tools/v4/blueprint.py phase1` reads `data/campus_full.features.json`, the whole-campus OSM extract
     (659 buildings, 269 roads, all key names verified).
   - It rotates the campus by -8.75° so the street grid is axis-aligned, at **1 tile = 16 px = 3 m** (5 m until §2d), and writes
     the Tiled project in `tiled/`.
   - Ground is painted with the Wang terrain tiles from `tools/v4/tiled_kit.py` (road, path, hedge, garden lawn,
     tall grass, flowerbed).
   - Buildings are stamp objects placed into OSM footprints ("slots").
2. **Tiled:** the user can edit `tiled/maps/phase1.tmj` (project `tiled/campus.tiled-project`). Guide: `tiled/GUIDE.md`.
   Tiled is installed, and a session file exists from 17:51. The map has **not** been edited or saved by the user yet;
   it's still identical to the last generated version.
3. **To game:** `tools/v4/tiled_to_game.py tiled/maps/phase1.tmj` writes `game/public/maps/main.json` and
   `main.meta.json`, `game/public/tiles/campus.png` and `game/public/props/*`. The game currently runs this
   converted Phase 1 map, and a headless playtest passed (spawn at porch, riding works, 0 console errors).

**Phase 1 area:** Main Building + FD2 + Rotunda, NAB/Snake Path, Krishna & Gandhi Bhawans, KG mess, down to the
Gandhi Marg circle. The rotated box also includes Ram, Budh, Shankar, Vishwakarma and Bhagirath. The map is
187×230 tiles at 3 m/tile (112×138 at the old 5 m).

**Stamps with real art (3):**

| stamp | source | notes |
|---|---|---|
| `main_west` | `art/reference_main.png` crop x 8–634, y 0–390, cut by measured rects `MAIN_RECTS` in blueprint.py | anchored on the OSM **Clock Tower point** (art tower centre x = 512, base y = 214) |
| `fd2` | `art/reference_fd2.png` (FD2 quad) | placed directly east of main_west, 1 tile overlap |
| `rotunda` | `art/reference_main.png`, scaled to exactly ½ (the art draws it ~2× real size) | centred on the OSM Rotunda point; drawn on top of the NAB ends |

**Stamp files are user-owned:**
- `art/stamps/<name>.png` (look) and `art/stamps/<name>_collision.png` (any painted pixel = wall) are seeded once
  and **never overwritten**. The build reads them.
- `art/stamps/_source/<name>_full.png` is the uncut crop, for restoring pixels.
- Generated copies go to `tiled/stamps/`.

**Slots waiting for art:**
- 7 bhawans, 3 messes, 2 NAB blocks, ~29 small buildings. They render as neutral placeholder blocks.
- The user is to generate **one** image each for Bhawan, mess and NAB (prompts in `art/prompts/stamps_phase1.md`).
- Then the next step: `tools/v4/stamp_prep.py` + `fill_slots.py` (**not written yet**) clean each image, size it to
  the slot footprint and fill every matching slot.

## 2b. Update (2026-11-11, evening): Main Building now built from the user's Figma pieces
- The user exported clean pieces to `art/pieces/`: `clock tower body.png` (1179×491) and `fd.png` (725×690),
  both with transparent backgrounds.
  - Their Figma layout screenshot is `art/pieces/_figma_layout.png`.
  - Positions were matched by template search and saved in native piece pixels to
    `art/pieces/main_building_layout.json`: FD at x −665 and x 1119, y 115, drawn over the body (equal 60 px wing overlap).
- `blueprint.py` → `compose_pieces()` assembles them and scales to the real OSM width of "FD-2 & FD-3" (1008 px =
  63 tiles), palette 96 colours. The result is the stamp `main_building`, placed with the body's porch 80 px (25 m)
  south of the OSM Clock Tower point.
  - It is **always rebuilt from `art/pieces`** (not seeded).
  - Collision override goes in `art/pieces/main_building_collision.png`; otherwise it comes from the alpha.
  - The old `main_west`/`fd2` cut-outs are no longer placed.
- `tiled/maps/phase1.tmj` was regenerated: the user had never saved it. The previous version is in
  `phase1.backup-1747.tmj`.
- The game was converted and playtested: spawn at the porch, 0 errors.
- **New issue:** the composite is scaled down about 0.41× to fit the real width, so its detail is finer than the
  Rotunda's (from the old art at ½). The Rotunda now looks large and in a different style beside it. Fix: get a
  Rotunda piece from the user, and decide the building-vs-player scale (see the chat for options).
- **Preferred workflow from now on:** the user designs structures as separate pieces in Figma and exports
  transparent PNGs to `art/pieces/` (plus a layout screenshot when pieces combine). Prefer this over cutting
  buildings out of scene images.

## 2c. Update (2026-11-11, 21:30): front garden, closer camera, smooth roads
Full detail is in `WORKLOG.md` (entry "Logging rule, closer camera, front garden").

**Which map is current:** `tiled/maps/phase1.tmj` is the new map with the garden, and the game is converted from
it. The user agreed to the replacement (`--force`) after being asked; they had never saved edits in the old one.
The old map is `phase1.backup-2130.tmj`. There is no `phase1.generated.tmj` any more.

**Camera:** the view is 800×450 map pixels (was 1024×576), `VIEW_W`/`VIEW_H` in `game/src/main.ts`. It matches the
user's reference picture: one FD quad is about 36% of the screen width. This is a camera zoom only. (The map scale
was changed separately afterwards, see §2d; the view stayed 800×450.)

**Front garden (between the Main Building's wings, north of the Rotunda), generated in `blueprint.py`, section
"front garden":**
- The OSM driveway `w285869287` is redrawn as a smooth road 2 tiles wide whose kerb meets the porch steps.
- Hedges run along the drive's north side with gaps at the porch and the west path. They are **polyline objects of
  class `hedge`** on the `props` layer (property `width`, default 14 px), so they can run at any angle.
- West lawn: path from the wing door, tall grass, palm, shrub, flowers. East lawn: vegetable bed, sign, palm, pink
  flower bush, flowers. Four flags in the hedge line, two lamps.
- Every position is computed from the Main Building stamp's alpha (porch, recess, wing door steps).
- To move or remove one thing by hand, edit the `props` layer in Tiled. To change the design, edit the section.

**Props (`tiled_kit.py`):** new `shrub`, `flowers_red`, `flowers_white`, `flowers_pink`, `sign`, `crop`, cut from
`art/reference_main.png` with `key_cut()`. Tile properties: `solid_base` (blocks at the base), `base_w`/`base_h`
(base size as a fraction of the image), `flat` (baked into the ground, walkable).

**Converter (`tiled_to_game.py`):**
- **Smoothing pass over the whole map:** terrain-brush tiles (road, path, hedge, garden lawn) are repainted from a
  smooth outline instead of being copied as tiles. Set `SMOOTH = 0` at the top of the file for the old tile-exact
  look. Tiled itself still shows the stepped tiles; only the game is smooth.
- Upright props are depth-sorted sprites (the player walks behind palms and lamps); they ride in the `animProps`
  list with one frame.
- `data/debug/game_render.png` shows the whole map as the game draws it.

**Known leftovers:**
- The old Rotunda stamp has stray specks and two tiny flags beside the drive. It is the user's file, so it was
  left; it goes when `rotunda.png` arrives.
- The tall-grass patch is square-edged.
- ~~Props and the player are large next to the real-scale buildings.~~ Fixed by the 3 m/tile scale (§2d).

## 2d. Update (2026-11-11, 22:40): 3 m per tile, garden after the art, gap before the Rotunda
Full detail: `WORKLOG.md`, entry "Map scale 3 m/tile, garden redone after the art…".

- **Scale decided by the user: the bigger map.** `M_PER_TILE = 3` in `blueprint.py` (was 5). One map pixel = one
  pixel of `art/reference_main.png`, so props cut from the art fit the buildings. Map: **187×230 tiles
  (2992×3680 px)**. Blueprint takes about 60 s now. The Main Building is still fitted to its real OSM width; its porch
  is `PORCH_SOUTH_M = 20` m south of the OSM Clock Tower point.
- **Current map:** `tiled/maps/phase1.tmj` (replaced with the user's OK; previous map in `phase1.backup-2233.tmj`).
  The game is converted from it. Spawn (1382, 1122).
- **Rotunda:** stamp `rotunda_art` = the art's Rotunda at the art's size (`art/stamps/rotunda_art.png`, seeded, now
  user-owned like every stamp). The old half-size `rotunda` stamp is no longer placed.
- **Layout south of the porch, from the satellite view (`art/satellite/main_rotunda.jpg`):** porch steps, the drive
  (`DRIVE_W = 76` px: a drop-off lane and the two-lane road, split by median hedges on both sides of the porch),
  a paved terrace (`TERRACE = 40` px, painted with path tiles around the Rotunda's north half), then the arcade.
- **Garden, laid out like the art** (`blueprint.py`, section "front garden"): hedges drawn like the art's
  (`draw_hedge()` in the converter); west lawn with the art's tall-grass patch (`thicket`, walkable, rustles),
  palm, shrubs, flowers and the path from the wing door; east lawn with the art's whole vegetable bed (`veg_bed`),
  palms, conifers, bushes and sign; flags and lamps on the hedges; bougainvillea against the Rotunda's arcade and
  plants on its flanks, placed by `plant_free()` only where they fit.
- Photos of the real drive are in `art/photos/` (hedge islands with white kerbs, an "Only for bicycle" sign).
- **Known leftovers:**
  - The Rotunda stamp is cut flat at the bottom, overlaps the two NAB placeholders, and is missing its
    amphitheatre steps. All of this goes when `rotunda.png` arrives.
  - The art's Rotunda is about 1.5× its real size. It was kept because its width relative to the FD wings matches
    the satellite view.
  - The terrace uses the tan path colour; the real one is paler paving.
  - Plants exist only between the FD wings.

## 3. Open problems (what the user is unhappy about / unfinished)
1. ~~**The Main Building stamp looks "wrong" to the user.**~~ (SUPERSEDED by the Figma pieces above; kept for history) They said "the base of the clock tower is a bit ruined",
   then "still not correct" after the fix.
   - Fixes so far: added the side blocks flanking the porch `(28.55, 13.4, 35.45, 16.8)`, porch trimmed to
     `(29.75, 13.4, 34.2, 18.3)`, balcony blocks to y 16.05 (all in `MAIN_RECTS`).
   - **The exact remaining defect was never specified.** Ask the user for a circled screenshot.
   - Verified at session end: `art/stamps/main_west.png` matches the current `MAIN_RECTS` cut exactly (0 differing
     alpha pixels), so it isn't a stale seed. The remaining problem is in the cut or the art itself. Seeded files are
     never overwritten: to apply new `MAIN_RECTS`, the seed must be removed first, so **ask the user** in case they
     edited it.
   - Rect cutting from measured boxes is fragile. A per-pixel mask the user paints, or a cleaner regenerated
     isolated Main Building image, may be better.
2. **The Rotunda stamp's bottom is cut flat:** the source image ends at y = 687. It needs a complete Rotunda image or a manual edit.
3. ~~**Roads look chunky:** corner Wang tiles turn OSM curves into stair-steps, and the loop around the Rotunda forms
   grey blobs.~~ Fixed in the game by the converter's smoothing pass and the redrawn driveway (§2c). Still true
   inside Tiled, and the kerb look is still weaker than the art's road.
4. **Main Building depth:** the art compresses the building north–south compared with OSM, leaving lawn where the
   real north wings are.
5. A stray placeholder slot (a small OSM building) sits on the lawn west of the Main Building. The user may delete it in Tiled.
6. **Not built yet:**
   - `stamp_prep.py` (pixel-grid detection → 1 px downsample, background removal, palette lock, fit to slot
     footprint) and `fill_slots.py`;
   - flags and tall grass outside the front garden (the garden has them since §2c; the rest of the map has none);
   - multi-area world beyond Phase 1.
7. The `above` layer works in the converter and the game but is unused.

## 4. How to run things (always from the repo root `/Users/ishanmalhotra/Documents/campus`)
```
python3 tools/v4/blueprint.py phase1            # regenerate kit + blueprint; writes phase1.generated.tmj if phase1.tmj exists
python3 tools/v4/blueprint.py phase1 --force    # overwrite phase1.tmj (destroys user's Tiled edits! ask first)
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj   # Tiled -> game
cd game && npx vite --port 5179 --strictPort    # dev server (game at /, old editor at /editor.html)
cd game && npx tsc --noEmit -p .                # type-check
```
- **Headless playtests:** Playwright-core is installed in `/tmp/campus-check` (scripts `tiled.mjs`, `live.mjs`,
  `editor.mjs`, and `garden.mjs` for the front garden). They use the system Chrome with `--use-angle=swiftshader`.
  - `window.__game` is exposed in dev; `scene('world')` has `player`, `onBike`, `zoneName`.
  - `/tmp` may be wiped between sessions. Recreate with `npm i playwright-core` in a temp dir.
- **Python gotcha:** Pillow and numpy are in the *user* site-packages, so `python3 -I` fails to import PIL.
  Run the repo's own scripts with plain `python3`.
- Debug renders go to `data/debug/`: `phase1_render.png`, `phase1_check.png` (cyan = OSM outlines,
  yellow = road centre lines), `compare_satellite.png`, `game_collision.png`, `game_render.png` (the map as the
  game draws it, the best one to look at).

## 5. User preferences / rules (hard-won, respect them)
- **As cheap as possible:** free tools only; flag any paid step first. The user generates images themselves in a
  free tool; Claude cannot generate raster images.
- **The user's own generated images are the art standard.** They rejected code-drawn art as "AI-looking". Don't
  redraw buildings procedurally; cut them from the user's images.
- **Never stitch whole scene images together.** Never overwrite the user's art or their edited Tiled map.
- **Animations: only flags waving and grass** (tall-grass sway + rustle). No clouds, no palm or tree sway (user's request).
- **Accuracy vs the satellite view matters.** Geometry comes from OSM; satellite screenshots live in
  `art/satellite/` as local references only, never shipped.
- Work in **phases**. Phase 1 is above. Later: the west side (FD3 = FD2 mirrored, Ram/Budh, SAC…), then south, then the
  whole campus (`art/prompts/image_requirements.md` lists about 17–18 images in total).
- The user is not a Tiled or image-editing expert. Give click-by-click steps, and offer to do edits for them.

## 6. Legacy / superseded (don't build on these)
- **v1:** OSM-extruded procedural map; files deleted.
- **v2 (`tools/v2/`):** code-drawn hand-built map (`map_main.py`), rejected. It is **still used** only to measure
  the reference-art walls: `data/layout_ref.json`, and `MAIN_RECTS`/props coordinates came from it.
  `from_ref.py` = source-image-as-map.
- **v3 (`tools/v3/`):** compositing FD2 onto the main image (`compose_fd2.py`, `build_map.py`), rejected as an
  "unnatural" seam. `props_extract.py` produced the true-colour flag/palm cut-outs in `art/props/` that
  `tiled_kit.py` reuses.
- **Web "god mode" editor** (`game/editor.html`, `game/src/editor/`): built and working, but superseded by Tiled.
- **`SPEC.md`** describes the editor/Figma export-package workflow (`art/export/`, `tools/v4/build_from_export.py`),
  which was **never built**. The Tiled workflow replaced it. Update SPEC.md if you change direction again.

## 7. Roadmap agreed with the user: how the rest of the map gets built
**The per-structure loop (repeat for every building):**
1. The user designs the structure as a separate piece in **Figma**, using the existing art as the style reference,
   with the entrance facing down unless the real building faces elsewhere.
2. They export a **transparent PNG at 1x** into `art/pieces/`. **The file name decides placement:**
   - a *type* name fills every slot of that type: `bhawan.png` → all bhawans, `mess.png` → all messes,
     `nab.png` → both NAB blocks (the second mirrored);
   - a *building's own name* fills only that one: `rotunda.png`, `fd1.png`, `sac.png`, …
   - If pieces combine into one building, the user also sends a layout screenshot. We match positions into a
     `<name>_layout.json`, the same way `main_building_layout.json` was made.
   - Optional `<file>_collision.png`: painted = wall. Default: the whole outline blocks except the entrance steps.
3. The user says **"add the new pieces"**. Claude sizes each piece to its real OSM footprint (only the aspect ratio
   has to be right), places it in every matching slot, regenerates the Tiled map and the game, and shows a
   satellite side-by-side.
   - **Never `--force` over a `phase1.tmj` the user has saved in Tiled.** Check its mtime and diff it first; write
     the `.generated.tmj` instead and merge by hand if needed.
4. The user checks it and either asks for fixes or fixes it themselves (re-export the piece, or drag it in Tiled).

The checklist the user follows is `art/pieces/README.md` (file names, shapes, real sizes).

**Phase 1 order (current map), with slot footprints at 5 m/tile:**

| # | file | fills | shape (w:h) | slot size |
|---|---|---|---|---|
| ✅ | `clock tower body.png` + `fd.png` | Main Building (FD3 + tower + FD2) | — | 63 × 20 tiles |
| 1 | `rotunda.png` | Rotunda (complete, round). Fixes the style clash with the new Main Building | ~3:2 | 17 × 12 |
| 2 | `bhawan.png` | Ram, Budh, Krishna, Gandhi, Shankar, Vishwakarma, Bhagirath (7 now; Vyas, Rana Pratap, Ashok later) | 2:3 | ~13 × 19 |
| 3 | `mess.png` | Ram-Budh, KG, VKB (3 now; Shankar-Vyas, RP later) | 1:1 | 8 × 7–8 |
| 4 | `nab.png` | New Academic Block + NAB (mirrored) | 1:6 | 7–8 × 49 |
| 5 | `fd1.png`, `sac.png` (optional) | FD 1, Student Activity Centre | ~1:1, ~5:9 | 23 × 21, 15 × 27 |

The remaining ~29 small slots stay as placeholder blocks until an optional `small_house.png` is supplied.

**After Phase 1:** go west (Malviya, Birla Museum, FD3 side), east (Library + LTC, Workshop, Gymkhana, pool),
south (Shiv Ganga, Saraswati Temple, Meera Bhawan, Med-C, C'not), then the main gate. Each needs a new
`AREAS` entry in `blueprint.py` and its own map in `campus.world`.

**~~Pending user decision~~ DECIDED 2026-11-11: the bigger map, 3 m/tile (§2d).** Slot sizes in the table above
are still in 5 m tiles; multiply by 5/3 for the current map. Kept for history:
- **Scale:** at real 5 m/tile, pieces are shrunk to about 41% and look small next to the player. The options are:
  - keep the real scale (current);
  - make the whole map about 1.7× bigger (about 3 m/tile), so buildings feel Emerald-grand but walking takes longer.
- If they choose bigger: change `M_PER_TILE` in `blueprint.py`, regenerate, and re-check the stamp anchors
  (porch offset 80 px = 25 m scales too).

**Not built yet, needed as soon as the first type piece arrives:**
- Generic "piece → every slot of a type" filling. The plan named this `stamp_prep.py` + `fill_slots.py`; it can also
  be a piece loader inside `blueprint.py` like `compose_pieces()`. It needs to:
  - fit the piece to each slot (keep the aspect ratio, centre it, bottom-align to the entrance side);
  - mirror NAB #2;
  - palette-lock;
  - build a collision mask from alpha (with the steps walkable) or from the user's `_collision.png`.

## 8. Suggested next steps
1. **Rotunda** (the user named it as the next piece of work). When `rotunda.png` or any type piece arrives,
   implement the piece loader (§7), fill the slots, convert, and playtest (`/tmp/campus-check/garden.mjs`). Send the
   user `data/debug/compare_satellite.png`. Check the garden's drive and hedges against the new Rotunda's outline.
2. Flags, tall grass and plants for the rest of the map, the way the front garden does it (§2d).
3. Kerb look of the roads closer to the art (`tiled_kit.paint('road', …)`).
