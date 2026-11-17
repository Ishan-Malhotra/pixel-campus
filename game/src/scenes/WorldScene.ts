import Phaser from 'phaser';
import type { MapMeta, Zone } from '../types';
import { pixelZoom } from '../view';

const DIRS = ['down', 'left', 'right', 'up'] as const;
type Dir = (typeof DIRS)[number];
const SPEED = { walk: 64, run: 104, bike: 144 }; // px/s (16 px tiles)

export class WorldScene extends Phaser.Scene {
  private w!: MapMeta;
  private player!: Phaser.GameObjects.Sprite;
  private blocked!: Uint8Array;
  private keys!: Record<string, Phaser.Input.Keyboard.Key>;
  private dir: Dir = 'up';
  private onBike = false;
  private zoneName = '';
  private bannerTimer?: number;
  private miniDot!: HTMLElement;
  /** the player's exact position; the sprite and the camera are drawn at it snapped to whole screen pixels */
  private pos = { x: 0, y: 0 };
  private zoom = 1;

  constructor() { super('world'); }

  create() {
    this.w = this.cache.json.get('meta') as MapMeta;
    const w = this.w;

    // static ground: Tiled-format tilemap (buildings, rotunda, hedges, paths are all baked into tiles)
    const map = this.make.tilemap({ key: 'map' });
    const tileset = map.addTilesetImage('campus', 'campus')!;
    map.createLayer('ground', tileset, 0, 0)!.setDepth(-1);
    // tiles painted on the Tiled 'above' layer (tree canopies, roof edges) draw over the player
    if (map.getLayerIndex('above') !== null) map.createLayer('above', tileset, 0, 0)!.setDepth(1e6);

    // living world: flags wave, palms and trees sway, tall grass moves, flowers shimmer.
    // Upright props are depth-sorted by their base y (walk behind them); ground overlays sit just above the tiles.
    for (const [key, a] of Object.entries(w.anims ?? {})) {
      this.anims.create({
        key: `anim_${key}`,
        frames: this.anims.generateFrameNumbers(`anim_${key}`, { start: 0, end: a.frames - 1 }),
        frameRate: a.fps,
        repeat: key === 'rustle' ? 0 : -1,
      });
    }
    for (const p of w.animProps ?? []) {
      const s = this.add.sprite(p.x, p.y, `anim_${p.k}`, 0).setOrigin(0).setDepth(p.depth);
      s.play({ key: `anim_${p.k}`, startFrame: Math.floor(Math.random() * w.anims[p.k].frames) });
    }

    // collision grid (8 px cells)
    const col = w.collision;
    this.blocked = new Uint8Array(col.w * col.h);
    for (let i = 0; i < col.data.length; i++) this.blocked[i] = col.data.charCodeAt(i) === 49 ? 1 : 0;

    // player
    this.player = this.add.sprite(w.spawn.x, w.spawn.y, 'player', 9).setOrigin(0.5, 30 / 32);
    for (const [row, mode] of [[0, 'walk'], [1, 'bike']] as const) {
      DIRS.forEach((d, i) => {
        const b = row * 12 + i * 3;
        this.anims.create({
          key: `${mode}-${d}`,
          frames: this.anims.generateFrameNumbers('player', { frames: [b + 1, b, b + 2, b] }),
          frameRate: mode === 'bike' ? 10 : 8,
          repeat: -1,
        });
      });
    }

    // camera: no startFollow. It is centred on the player in update(), after the move, using the same snapped
    // position as the sprite, so player and ground can never be a pixel apart (that 1 px wobble was the jitter).
    this.pos = { x: w.spawn.x, y: w.spawn.y };
    const cam = this.cameras.main;
    cam.setBounds(0, 0, w.width, w.height);
    // place() already snaps everything to whole screen pixels; the camera's own rounding (to whole MAP pixels)
    // would pull the ground up to 3 screen px away from the player at zoom 4
    cam.setRoundPixels(false);
    const applyZoom = (z: number) => { this.zoom = z; cam.setZoom(z); this.place(); };
    applyZoom(pixelZoom());
    this.game.events.on('pixelzoom', applyZoom);
    this.events.once('shutdown', () => this.game.events.off('pixelzoom', applyZoom));

    const kb = this.input.keyboard!;
    this.keys = kb.addKeys('W,A,S,D,UP,DOWN,LEFT,RIGHT,SHIFT,B,SPACE,M') as Record<string, Phaser.Input.Keyboard.Key>;
    // raw keydown events so even very short taps register
    kb.on('keydown-B', () => this.toggleBike());
    kb.on('keydown-SPACE', () => this.toggleBike());
    kb.on('keydown-M', () => document.getElementById('minimap')!.classList.toggle('hidden'));

    this.setupHud();
    this.showBanner('BITS Pilani — Clock Tower');
  }

  private toggleBike() {
    this.onBike = !this.onBike;
    this.player.anims.stop();
    this.player.setFrame((this.onBike ? 12 : 0) + DIRS.indexOf(this.dir) * 3);
  }

  private isBlocked(x: number, y: number) {
    const c = this.w.collision;
    const cx = Math.floor(x / c.cell), cy = Math.floor(y / c.cell);
    if (cx < 0 || cy < 0 || cx >= c.w || cy >= c.h) return true;
    return this.blocked[cy * c.w + cx] === 1;
  }

  /** feet hitbox: 10 x 5 px just above the feet anchor */
  private canStand(x: number, y: number) {
    const hw = this.onBike ? 6 : 5;
    return !(
      this.isBlocked(x - hw, y - 5) || this.isBlocked(x + hw, y - 5) ||
      this.isBlocked(x - hw, y) || this.isBlocked(x + hw, y)
    );
  }

  update(_t: number, dtMs: number) {
    const k = this.keys;
    const dt = Math.min(dtMs, 50) / 1000;
    let vx = 0, vy = 0;
    if (k.LEFT.isDown || k.A.isDown) vx -= 1;
    if (k.RIGHT.isDown || k.D.isDown) vx += 1;
    if (k.UP.isDown || k.W.isDown) vy -= 1;
    if (k.DOWN.isDown || k.S.isDown) vy += 1;

    const mode = this.onBike ? 'bike' : 'walk';
    if (vx || vy) {
      // face the most recently relevant axis; prefer horizontal when both are held
      this.dir = vx < 0 ? 'left' : vx > 0 ? 'right' : vy < 0 ? 'up' : 'down';
      const len = Math.hypot(vx, vy);
      const sp = this.onBike ? SPEED.bike : k.SHIFT.isDown ? SPEED.run : SPEED.walk;
      const dx = (vx / len) * sp * dt, dy = (vy / len) * sp * dt;
      const p = this.pos, x0 = p.x, y0 = p.y;
      if (this.canStand(p.x + dx, p.y)) p.x += dx;
      if (this.canStand(p.x, p.y + dy)) p.y += dy;
      // the legs keep pace with the ground actually covered: full speed when free, slower when sliding along a
      // wall, standing still when pushing straight into one
      const moved = Math.hypot(p.x - x0, p.y - y0) / (sp * dt);
      if (moved < 0.05) {
        this.player.anims.stop();
        this.player.setFrame((this.onBike ? 12 : 0) + DIRS.indexOf(this.dir) * 3);
      } else {
        this.player.anims.play(`${mode}-${this.dir}`, true);
        this.player.anims.timeScale = (!this.onBike && k.SHIFT.isDown ? 1.6 : 1) * moved;
      }
    } else {
      this.player.anims.stop();
      this.player.setFrame((this.onBike ? 12 : 0) + DIRS.indexOf(this.dir) * 3);
    }
    this.place();
    if (vx || vy) this.maybeRustle();
    this.updateZone();
    this.miniDot.style.left = `${(this.player.x / this.w.width) * 100}%`;
    this.miniDot.style.top = `${(this.player.y / this.w.height) * 100}%`;
  }

  /** draw the player and centre the camera at the exact position snapped to whole screen pixels (1 / zoom map px) */
  private place() {
    const z = this.zoom, x = Math.round(this.pos.x * z) / z, y = Math.round(this.pos.y * z) / z;
    this.player.setPosition(x, y).setDepth(y);
    this.cameras.main.centerOn(x, y);
    const c = this.cameras.main;
    c.setScroll(Math.round(c.scrollX * z) / z, Math.round(c.scrollY * z) / z);
  }

  private lastRustle = { x: -999, y: -999 };

  /** Emerald-style: grass blades flick around the feet when stepping through tall grass */
  private maybeRustle() {
    const { x, y } = this.player;
    if (Math.abs(x - this.lastRustle.x) + Math.abs(y - this.lastRustle.y) < 12) return;
    const inGrass = (this.w.tallgrass ?? []).some(([x0, y0, x1, y1]) => x >= x0 && x <= x1 && y >= y0 && y <= y1);
    if (!inGrass) return;
    this.lastRustle = { x, y };
    const r = this.add.sprite(x - 9, y - 10, 'anim_rustle', 0).setOrigin(0).setDepth(y + 1);
    r.play('anim_rustle');
    r.once('animationcomplete', () => r.destroy());
  }

  private updateZone() {
    const { x, y } = this.player;
    let best: Zone | null = null;
    for (const z of this.w.zones) {
      if (x < z.x || y < z.y || x > z.x + z.w || y > z.y + z.h) continue;
      if (!best || z.p < best.p || (z.p === best.p && z.w * z.h < best.w * best.h)) best = z;
    }
    const name = best?.name ?? '';
    if (name && name !== this.zoneName) this.showBanner(name);
    this.zoneName = name;
  }

  private setupHud() {
    const hud = document.getElementById('hud')!;
    hud.innerHTML = `
      <div id="banner" class="gba-box"></div>
      <div id="minimap" class="gba-box"><div class="mm"><img src="maps/minimap.png" alt="map"/><i id="dot"></i></div></div>
      <div id="help" class="gba-box">Arrows/WASD move · Shift run · B bike · M map</div>`;
    this.miniDot = document.getElementById('dot')!;
  }

  private showBanner(text: string) {
    const el = document.getElementById('banner')!;
    el.textContent = text;
    el.classList.add('show');
    window.clearTimeout(this.bannerTimer);
    this.bannerTimer = window.setTimeout(() => el.classList.remove('show'), 2600);
  }
}
