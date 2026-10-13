import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  // API_TARGET from the shell or the repository's .env, documented in .env.example.
  const env = loadEnv(mode, path.resolve(import.meta.dirname, '..'), '');
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { '@': path.resolve(import.meta.dirname, './src') },
    },
    server: {
      // The prod API sends no CORS headers: the dev server forwards /api/* to it, so the app
      // calls /api/v1/... on its own origin, like in prod. API_TARGET points it elsewhere while
      // main is ahead of prod, e.g. at the backend from docker compose up.
      proxy: {
        '/api': { target: env.API_TARGET || 'https://app.candlestack.tech', changeOrigin: true },
      },
    },
  };
});
