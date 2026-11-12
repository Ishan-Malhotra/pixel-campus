import Phaser from 'phaser';
import './style.css';
import { BootScene } from './scenes/BootScene';
import { WorldScene } from './scenes/WorldScene';

// How much of the map is on screen, in map pixels (16 px tiles). The canvas is scaled up to fill the window, so a
// smaller view = more zoomed in. 800 x 450 (50 x 28 tiles) frames the buildings like the user's reference picture:
// one FD quad is about a third of the screen wide. (1024 x 576 showed the whole Main Building at once.)
const VIEW_W = 800;
const VIEW_H = 450;

const game = new Phaser.Game({
  type: Phaser.WEBGL,
  parent: 'game',
  width: VIEW_W,
  height: VIEW_H,
  pixelArt: true,
  roundPixels: true,
  backgroundColor: '#78d070',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: [BootScene, WorldScene],
});

// expose for automated playtests in dev builds only
if (import.meta.env.DEV) (window as unknown as { __game: Phaser.Game }).__game = game;
