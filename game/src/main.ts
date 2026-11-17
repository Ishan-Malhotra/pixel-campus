import Phaser from 'phaser';
import './style.css';
import { BootScene } from './scenes/BootScene';
import { WorldScene } from './scenes/WorldScene';
import { pixelZoom, screenSize } from './view';

const s = screenSize();
const game = new Phaser.Game({
  type: Phaser.WEBGL,
  parent: 'game',
  width: s.w,
  height: s.h,
  zoom: 1 / s.dpr, // CSS size = window size; the backing canvas keeps every device pixel
  pixelArt: true,
  roundPixels: true,
  backgroundColor: '#78d070',
  scale: { mode: Phaser.Scale.NONE },
  scene: [BootScene, WorldScene],
});

window.addEventListener('resize', () => {
  const n = screenSize();
  game.scale.resize(n.w, n.h);
  game.scale.setZoom(1 / n.dpr);
  game.events.emit('pixelzoom', pixelZoom());
});

// expose for automated playtests in dev builds only
if (import.meta.env.DEV) (window as unknown as { __game: Phaser.Game }).__game = game;
