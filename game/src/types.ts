export interface Zone { name: string; x: number; y: number; w: number; h: number; p: number }

export interface PropFrame { x: number; y: number; w: number; h: number; ax: number; ay: number; cw: number; ch: number }

/** An animated sprite strip in public/props/<key>.png (frames laid out horizontally). */
export interface AnimDef { w: number; h: number; frames: number; fps: number }

/** Written by tools/v3/build_map.py next to the Tiled map (maps/main.meta.json). */
export interface MapMeta {
  width: number; height: number;
  props: { f: string; x: number; y: number }[];
  frames: Record<string, PropFrame>;
  /** living-world animations: flags, palms, tree belt, flowers, tall grass, grass rustle */
  anims: Record<string, AnimDef>;
  /** placed animated props: top-left x/y; depth = base y (upright props) or -0.5 (ground overlays) */
  animProps: { k: string; x: number; y: number; depth: number }[];
  /** rects (x0, y0, x1, y1) where walking plays the grass rustle */
  tallgrass: [number, number, number, number][];
  collision: { cell: number; w: number; h: number; data: string };
  zones: Zone[];
  spawn: { x: number; y: number };
}
