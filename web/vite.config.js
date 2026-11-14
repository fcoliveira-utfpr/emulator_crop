import { defineConfig } from 'vite';

// Relative base: the built site works from any folder (GitHub Pages project page, Vercel, a local server).
export default defineConfig({
  base: './',
  build: { chunkSizeWarningLimit: 1500 },
});
