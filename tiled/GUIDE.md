# Building the campus in Tiled

## 1. Install Tiled (free, once)
Download from https://www.mapeditor.org, or in Terminal: `brew install --cask tiled`

## 2. Open the project
In Tiled: **File → Open File or Project… → `tiled/campus.tiled-project`**, then open **`tiled/maps/phase1.tmj`**.
The map is already laid out from real campus data. Roads, buildings and spots are where OpenStreetMap puts them.

## 3. Layers (Layers panel, top right)
| Layer | What it is | What you do with it |
|---|---|---|
| `underlay (blueprint…)` | hidden reference picture | toggle on to compare; never exported |
| `ground` | grass, roads, dirt paths, hedges, garden lawn | paint with the **Terrain** brush |
| `decor` | extra tiles on top of the ground (tall grass, flowerbeds) | paint with the **Stamp** brush |
| `buildings` | building stamps + red-outlined **slots** waiting for art | drag to move, Delete to remove, flip with **X / Y** |
| `props` | flags, lamps, palms, bushes, trees | **Insert Tile** (T), then click to place from the `props` tileset |
| `above` | tiles drawn **over** the player (tree tops, roof edges) | paint with the Stamp brush |
| `collision` | extra walls | draw rectangles (R) where the player must not walk |
| `events` | area names (`zone` rectangles) + `spawn` point | rename a zone to change its banner text |

## 4. Painting roads, paths, hedges, garden lawn
1. Select the `ground` layer.
2. Open **View → Views and Toolbars → Terrain Sets**.
3. Pick a set (**Road**, **Path**, **Hedge**, **Garden lawn**), click its colour, then paint with the **Terrain Brush** (T).
   Kerbs, edges and corners draw themselves. Paint the **Grass** colour to erase.

Tall grass (rustles when walked through) and flowerbeds are on the bottom row of the `terrain` tileset.
Paint them with the **Stamp Brush** (B) on `decor`.

## 5. Buildings
- **Move:** select the `buildings` layer, use **Select Objects** (S), and drag.
- **Mirror:** select, then press **X** (mirror) or **Y** (flip).
- **Slots** are the red-outlined rectangles, e.g. "Krishna Bhawan". When you send me the Bhawan / mess / NAB image, every
  matching slot gets the real building automatically.
- **How a building looks:** edit `art/stamps/<name>.png` in any image editor.
  **What blocks the player:** edit `art/stamps/<name>_collision.png`, where any painted pixel = wall.
  The build never overwrites these files.

## 6. See it in the game
Save in Tiled (⌘S), then run from the project folder:
```
python3 tools/v4/tiled_to_game.py tiled/maps/phase1.tmj
```
and refresh http://localhost:5179 (dev server: `cd game && npm run dev`). Or just tell Claude "convert the map".

**Good to know:** re-running `tools/v4/blueprint.py` never overwrites your edited `phase1.tmj`. It writes
`phase1.generated.tmj` instead, unless you add `--force`.
