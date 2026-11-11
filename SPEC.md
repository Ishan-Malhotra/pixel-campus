# BITS Pilani Campus Explorer: Build Spec

## 1. What we're building
A browser game in the style of Pokémon Emerald: a top-down, pixel-art version of the **BITS Pilani (Pilani campus)**
that you can walk and cycle around. Version 1 covers **outdoor areas only**. Building interiors come later.

**Goals**
- The whole campus is explorable on foot or by bicycle.
- Landmarks are recognisable (Clock Tower, Rotunda, FD1/FD2/FD3, Bhawans, NAB, Library, temple and so on).
- The layout follows the satellite view: what is next to what, which way buildings face, and where roads run.
- Flags wave and grass moves, so the map feels alive.
- Cheap: free tools only, and as little AI generation as possible.

**Not in v1:** interiors, NPCs, quests, sound, mobile controls, clouds, swaying trees or palms.

## 2. Who does what
| Step | Owner | Tool |
|---|---|---|
| Generate building/area images in the reference style | **You** | Your image tool (prompts in `art/prompts/`) |
| Assemble the full campus map (place, crop, layer pieces) | **You** | **Figma** *or* the built-in editor (`/editor.html`) |
| Export the map + collision + animation markers | **You** | Figma / editor export |
| Turn the exports into the game (tiles, collision, animations, area names) | **Claude** | `tools/v4/build_from_export.py` (to be built) |
| Game engine, movement, bike, banners, minimap | **Claude** | Phaser 3 (`game/`) |

## 3. Art rules
- **Style standard:** `art/reference_main.png` (Main Building + Rotunda) and `art/reference_fd2.png` (FD2).
  Every new image is generated with both attached as style references.
- **Grid:** 16 px = 1 tile. Map dimensions are multiples of 16.
- **Pixel-perfect:**
  - Images stay at 100% or whole multiples (200%, 300%), never in-between sizes.
  - Positions are whole pixels.
  - Export as PNG at 1x with no smoothing.
- **No people, text or watermarks** in images. The game has its own player.
- **Reuse:** one Bhawan design for all standard hostels; FD3 is a mirror of FD2; one mess design; one NAB design (mirrored).
  The full list is in `art/prompts/image_requirements.md`.

## 4. The export package
Put these in `art/export/`. All PNGs must be **exactly the same size**, and that size must be a multiple of 16.

| File | Required | What it is |
|---|---|---|
| `campus_map.png` | ✅ | The finished map exactly as it should look in game, one flat image |
| `collision.png` | ✅ | Same frame, transparent background. **Pure red `#FF0000`** wherever the player must not walk (buildings, hedges, tree trunks, walls, water). Everything else transparent. |
| `anim.png` | optional | Same frame, transparent background. Animation markers (filled boxes):<br>• **Blue `#0000FF`**: one box around each flag (pole + cloth)<br>• **Green `#00FF00`**: one box over each tall-grass patch |
| `zones.json` | optional | Area names for the pop-up banner, as rectangles in **tiles**:<br>`[{"name": "FD2", "x": 64, "y": 0, "w": 28, "h": 24}, …]` |
| `spawn.json` | optional | Start position in tiles: `{"x": 32, "y": 20}`. Default is in front of the Clock Tower. |
| `campus_layout.json` | optional | The editor's layout export, kept for reference |

**Making the layers in Figma:**
- Keep three top-level layers in the map frame: `art`, `collision`, `anim`.
- To export each one, hide the other two and export the frame as PNG at 1x.

**In the editor:** "Export map PNG" gives `campus_map.png`. Draw collision and markers in Figma, or ask Claude to add a
paint mode to the editor.

## 5. Build pipeline (Claude)
`python3 tools/v4/build_from_export.py` reads `art/export/` and writes into `game/public/`:
1. **Check:**
   - all PNGs are the same size and a multiple of 16;
   - the colours in `collision.png` and `anim.png` are exact (only the colours above, or transparent);
   - every flag and grass marker sits inside the map.
2. **Tiles:** slice `campus_map.png` into 16×16 tiles and drop duplicates.
   Output: `tiles/campus.png` plus `maps/main.json` (Tiled format).
3. **Collision:** reduce `collision.png` to an 8 px grid (a cell is blocked if ≥40% red). The map border is always blocked.
4. **Animations:**
   - **Flags:** cut out the flag inside each blue box (background removed) and generate a 4-frame cloth wave (8 fps).
     The flag becomes a sprite that is depth-sorted, so the player walks behind it.
   - **Tall grass:** the patch under each green box gets a 4-frame wind ripple (3 fps). Walking through it plays the
     Emerald-style rustle under the player's feet.
   - Under each flag, the base art is filled with neighbouring ground pixels.
5. **Meta:** `maps/main.meta.json` holds collision, animated props, tall-grass rects, zones, spawn and size.
   `maps/minimap.png` is a reduced copy of the map.
6. **Preview:** `data/debug/` gets the map with props and a collision overlay (red = blocked) for review.

Logic is reused from `tools/v3/build_map.py`: flag cut-out and wave, grass ripple, rustle sprite, tile slicing,
and the meta format.

## 6. Game (runtime)
- **Engine:** Phaser 3 + TypeScript + Vite (`game/`). Dev server: `cd game && npm run dev`, which serves the game at `/`
  and the editor at `/editor.html`.
- **View:** 1024×576 (64×36 tiles visible), integer-friendly scaling, pixelated rendering.
- **Player:**
  - chibi student sprite (`tools/draw_player.py`), 4 directions, walk/bike animations;
  - speeds: walk 64, run 104 (Shift), bike 144 px/s (B or Space toggles the bike).
- **Collision:** 8 px grid from the meta, with a box around the feet.
- **Depth:** the player and upright props are sorted by their base y. Ground overlays (grass ripple) sit under everything.
- **UI:**
  - an area-name banner when you enter a zone;
  - a minimap (M toggles it) with a blinking dot for the player;
  - a controls hint.

## 7. Phases
| Phase | Scope | Images needed (`art/prompts/image_requirements.md`) |
|---|---|---|
| **1 (now)** | Main Building + Rotunda ✅, FD2 ✅ art, south along Krishna Marg: NAB + Snake Path, Krishna & Gandhi Bhawans, KG mess, down to the Gandhi Marg circle | Bhawan, mess, NAB north half, NAB south half |
| 2 | West side mirror: FD3, Ram/Budh, Malviya, SAC, Birla Museum | Malviya, SAC, Birla Museum |
| 3 | East: FD1, Library + LTC, Workshop, Vishwakarma/RP/Bhagirath/Ashok, Gymkhana, pool | Library+LTC, Workshop, Gymkhana, pool |
| 4 | South and north: Shankar/Vyas, Saraswati Temple, Shiv Ganga, Meera, Med-C + C'not, SR Hostel, main gate | Temple, Shiv Ganga, Meera, Med-C/C'not, SR Hostel, gate |
| Later | Interiors (door warps), NPCs, sound | — |

Each phase ends with you exporting the updated full map. Claude then rebuilds and plays it.

## 8. Done checklist (each export)
- [ ] Build script passes all checks (sizes, colours, markers).
- [ ] Game loads with **zero console errors**.
- [ ] Headless playtest walks and cycles through every new area. The player can't pass red areas and doesn't get stuck on open ground.
- [ ] Every flag waves, every tall-grass patch moves, and walking through grass shows the rustle.
- [ ] Area banners appear with the right names.
- [ ] Map art in game is pixel-identical to `campus_map.png` (no blur or colour shift).

## 9. Repo map
```
art/            reference images, prompts, exports (art/export/)
data/           OpenStreetMap extracts, debug previews
tools/          build scripts (v2 = measurements, v3 = current build, v4 = export-driven build)
game/           Phaser game + editor (src/scenes, src/editor, public/{maps,tiles,props,sprites})
SPEC.md         this document
```

## 10. Cost
- **Tools:** free (Figma free plan, Phaser, Vite, Python/Pillow, GitHub Pages for hosting).
- **Image generation:** about 17–18 images for the whole campus, from your image tool's free tier.
- **Claude:** only the build pipeline, engine features, and one rebuild per export.
