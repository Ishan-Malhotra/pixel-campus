import Phaser from 'phaser';
import type { MapMeta } from '../types';

export class BootScene extends Phaser.Scene {
  constructor() { super('boot'); }

  preload() {
    const bar = this.add.rectangle(412, 288, 0, 8, 0xf8f8f8).setOrigin(0, 0.5);
    this.add.rectangle(512, 288, 204, 12).setStrokeStyle(2, 0x283048);
    this.load.on('progress', (p: number) => (bar.width = 200 * p));
    this.load.tilemapTiledJSON('map', 'maps/main.json');
    this.load.json('meta', 'maps/main.meta.json');
    this.load.image('campus', 'tiles/campus.png');
    this.load.spritesheet('player', 'sprites/player.png', { frameWidth: 32, frameHeight: 32 });
  }

  create() {
    // second pass: the animated prop strips listed in the map meta
    const meta = this.cache.json.get('meta') as MapMeta;
    for (const [key, a] of Object.entries(meta.anims ?? {})) {
      this.load.spritesheet(`anim_${key}`, `props/${key}.png`, { frameWidth: a.w, frameHeight: a.h });
    }
    this.load.once('complete', () => this.scene.start('world'));
    this.load.start();
  }
}
