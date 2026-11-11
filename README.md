# BITS Pilani Campus Explorer: Main Building + Rotunda (v2)

GBA-style top-down pixel-art campus explorer. The look follows `art/reference_main.png`: hand-composed,
game-compressed layout, 16×16 tiles, everything drawn in code (no paid assets).

## Play
    cd game && npm install && npm run dev
Arrows/WASD move · Shift run · B (or Space) bike · M minimap

## Building the map in Tiled (current workflow)
See `tiled/GUIDE.md`. In short:
- `python3 tools/v4/blueprint.py phase1` generates `tiled/maps/phase1.tmj` from OpenStreetMap: terrain-tile ground,
  building stamps and slots, and zones. It never overwrites an edited map (use `--force` to replace it).
- Edit the map in Tiled (`tiled/campus.tiled-project`).
- `python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj` turns it into the game (`game/public/maps`).

## Map editor (god mode, superseded by Tiled)
Open http://localhost:5179/editor.html while `npm run dev` is running.
- **Library:** upload images, drag files in, or add the "Starter images". Click an image to place it as a piece.
- **Arrange:** drag pieces (they snap to the 16 px tile grid; hold Alt for free placement). Arrows nudge
  (Shift = 1 tile). `[` and `]` move a piece back/forward. Mirror/flip, lock, hide, duplicate (Ctrl/⌘+D), undo (Ctrl/⌘+Z).
- **Cut out:** "Drag to crop" keeps only part of an image. "Pick colour" removes the background around a building
  (tolerance slider; "only from the edges" keeps matching colours inside the building).
- **Save:** work autosaves in the browser. "Save project…" downloads everything (images included) as one file.
- **Export:** "Export map PNG" writes the whole assembled campus as one image. Hand that to the build step to
  add collision and animations.

## Regenerate the map
The map is built piece by piece, Emerald-style. The approved Main Building art (`art/reference_main.png`) is the base.
Separate pieces cut from `art/reference_fd2.png` (FD2 building, circle island, M Lawns trees) are recoloured to the
base palette and joined with roads painted in the base map's own style. Flags, palms and trees, tall grass and
flowers are lifted out as animated sprites.

    python3 tools/v2/map_main.py >/dev/null   # measures the base map's walls -> data/layout_ref.json
    python3 tools/v3/build_map.py             # composes pieces + animations -> game/public/{maps,tiles,props}
    python3 tools/draw_player.py game/public/sprites/player.png
Previews: `data/debug/map_v3.png`, `data/debug/map_v3_collision.png` (red = blocked).

## Layout
- `tools/v2/pal2.py`: palette sampled from the reference.
- `tools/v2/props.py`: palms, trees, conifers, bushes, lamps, flags, bench (depth-sorted sprites).
- `tools/v2/map_main.py`: terrain (lawns, dirt, road, hedges), building kit (flat roofs with salmon
  parapets, arcade and window facades, pavilions, slate hip roof), Art Deco clock tower, Rotunda
  amphitheatre. Bakes static art into deduplicated tiles and writes a Tiled map
  (`game/public/maps/main.json`) plus `main.meta.json` (props, collision, zones, spawn).
- `tools/osm_parse.py`, `tools/debug_plan.py`: OpenStreetMap extraction, used only as a layout guide.
- `game/`: Phaser 3 + Vite + TypeScript, 1024×576 view (64 tiles wide).

Map layout reference data © OpenStreetMap contributors (ODbL).
