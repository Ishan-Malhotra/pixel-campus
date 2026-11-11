# Building images to generate for Phase 1: each one ONCE, reused everywhere

Each image becomes a **stamp**. The script cleans it, sizes it to the real footprint from OpenStreetMap, and places it
into every matching slot on the map. You never place these yourself.

## Rules for every image
- Attach **both** style references: `art/reference_main.png` and `art/reference_fd2.png`.
- **One building only**, centred, on **plain flat grass** with nothing touching the image edges.
- Top-down 3/4 view like the references, **entrance facing DOWN** (south).
- No people, text, watermark, shadows of other things, or roads.
- Pixel art, crisp, no blur or gradients. The aspect ratio matters most. Any resolution is fine; the script downsizes it.

## 1. Bhawan (standard hostel): used 10× across campus
**Aspect: about 2 wide : 3 tall** (the real footprint is about 13 × 20 tiles = 65 × 100 m).
> Top-down pixel art of a single three-storey university hostel in the exact style, palette and 3/4 view of the
> attached images (Pokémon Emerald / GBA look). A rectangular quadrangle, taller than wide, with an open grass
> courtyard and a couple of trees in the middle; cream walls with salmon/terracotta trim bands; flat beige roof with
> parapet; rows of small dark windows on every floor. Entrance on the bottom side: a central arched gate with steps
> and a blank light name board above it. Plain grass all around. No people, no text.

## 2. Mess: used 5×
**Aspect: about square** (8 × 8 tiles = 40 × 40 m).
> Same style. A single-storey dining hall (mess) building, square, cream walls with salmon trim, flat roof with a few
> rooftop water tanks, wide doorway with steps on the bottom side, small windows. Plain grass around. No people, no text.

## 3. NAB block: used 2× (mirrored)
**Aspect: tall and thin, about 1 wide : 3 tall.** The real block is 8 × 49 tiles; the script repeats the middle
section to reach the full length.
> Same style. A long two-storey academic block seen from above, much taller than wide: flat beige roof with salmon
> parapet, a long facade on the RIGHT side with a row of dark windows and a couple of entrances with steps, cream
> walls. Plain grass around. No people, no text.

## What I already have (no new images needed)
- Main Building (Clock Tower) and the Rotunda: cut from `art/reference_main.png`.
- FD2: cut from `art/reference_fd2.png`.
- Roads, lawns, paths, circles: generated from the map data in the reference style.

**Optional:** a **complete Rotunda** image (round, with the steps on all sides). The current one comes from your
first image, where its bottom edge runs off the picture.
