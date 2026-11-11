import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// two pages: the game (index.html) and the god-mode map editor (editor.html)
export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        editor: resolve(__dirname, 'editor.html'),
      },
    },
  },
});
