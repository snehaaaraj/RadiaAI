import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';
export { loadRadiaViteEnv } from './src/viteEnv';
import { loadRadiaViteEnv } from './src/viteEnv';

const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url));
// Single source of truth for the release version, shared with the backend.
const APP_VERSION = fs
  .readFileSync(path.resolve(FRONTEND_ROOT, '../backend/app/VERSION'), 'utf8')
  .trim();

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadRadiaViteEnv(mode);
  const devProxyTarget = env.VITE_DEV_PROXY_TARGET?.trim();

  return {
    plugins: [react()],
    define: {
      __APP_VERSION__: JSON.stringify(APP_VERSION),
    },
    resolve: {
      alias: {
        '@': path.resolve(FRONTEND_ROOT, './src'),
      },
    },
    server: {
      port: 5173,
      // Proxy API calls to the backend during local development.
      // Configure the target in VITE_DEV_PROXY_TARGET.
      proxy: devProxyTarget
        ? {
            '/api': {
              target: devProxyTarget,
              changeOrigin: true,
            },
          }
        : undefined,
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
      // Raise the warning threshold - MUI bundles are large by nature
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          // Split vendor chunks for better caching
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'mui-vendor': ['@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled'],
            'query-vendor': ['@tanstack/react-query'],
          },
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
      },
    },
  };
});
