import Phaser from 'phaser';
import './style.css';
import { BootScene } from './scenes/BootScene';
import { WorldScene } from './scenes/WorldScene';

// 64 x 36 tiles visible (16 px tiles): whole Main Building + Rotunda fit on screen, like art/reference_main.png
const game = new Phaser.Game({
  type: Phaser.WEBGL,
  parent: 'game',
  width: 1024,
  height: 576,
  pixelArt: true,
  roundPixels: true,
  backgroundColor: '#78d070',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: [BootScene, WorldScene],
});

// expose for automated playtests in dev builds only
if (import.meta.env.DEV) (window as unknown as { __game: Phaser.Game }).__game = game;
