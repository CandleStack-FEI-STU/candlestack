import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    // The prod API sends no CORS headers: the dev server forwards /api/* to it, so the app
    // calls /api/v1/... on its own origin, like in prod. API_TARGET points it elsewhere while
    // main is ahead of prod: API_TARGET=http://localhost:8000 npm run dev (docker compose up).
    proxy: {
      '/api': { target: process.env.API_TARGET ?? 'https://app.candlestack.tech', changeOrigin: true },
    },
  },
});
