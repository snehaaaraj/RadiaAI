import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_ROOT = path.resolve(FRONTEND_ROOT, '..');

type ViteEnvOptions = {
  frontendRoot?: string;
  workspaceRoot?: string;
  env?: NodeJS.ProcessEnv;
};

export function loadRadiaViteEnv(mode: string, options: ViteEnvOptions = {}) {
  const frontendRoot = options.frontendRoot ?? FRONTEND_ROOT;
  const workspaceRoot = options.workspaceRoot ?? WORKSPACE_ROOT;
  const processEnv = options.env ?? process.env;

  const workspaceEnv = loadEnv(mode, workspaceRoot, '');
  const frontendEnv = loadEnv(mode, frontendRoot, '');

  return {
    ...workspaceEnv,
    ...frontendEnv,
    ...processEnv,
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadRadiaViteEnv(mode);
  const devProxyTarget = env.VITE_DEV_PROXY_TARGET?.trim();

  return {
    plugins: [react()],
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
      // Raise the warning threshold — MUI bundles are large by nature
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
