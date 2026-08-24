import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { loadRadiaViteEnv } from './vite.config';

describe('loadRadiaViteEnv', () => {
  const tempDirs: string[] = [];

  afterEach(() => {
    for (const tempDir of tempDirs.splice(0)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('loads workspace env values when the frontend directory does not define them', () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'radia-vite-env-'));
    const workspaceRoot = path.join(tempDir, 'workspace');
    const frontendRoot = path.join(workspaceRoot, 'frontend');
    tempDirs.push(tempDir);

    fs.mkdirSync(frontendRoot, { recursive: true });
    fs.writeFileSync(path.join(workspaceRoot, '.env'), 'VITE_DEV_PROXY_TARGET=http://localhost:8000\n');
    fs.writeFileSync(path.join(frontendRoot, '.env'), 'VITE_API_BASE_URL=/api/v1\n');

    const env = loadRadiaViteEnv('development', {
      frontendRoot,
      workspaceRoot,
      env: {},
    });

    expect(env.VITE_DEV_PROXY_TARGET).toBe('http://localhost:8000');
    expect(env.VITE_API_BASE_URL).toBe('/api/v1');
  });

  it('prefers frontend env values over workspace defaults', () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'radia-vite-env-'));
    const workspaceRoot = path.join(tempDir, 'workspace');
    const frontendRoot = path.join(workspaceRoot, 'frontend');
    tempDirs.push(tempDir);

    fs.mkdirSync(frontendRoot, { recursive: true });
    fs.writeFileSync(path.join(workspaceRoot, '.env'), 'VITE_DEV_PROXY_TARGET=http://localhost:8000\n');
    fs.writeFileSync(path.join(frontendRoot, '.env'), 'VITE_DEV_PROXY_TARGET=http://localhost:9000\n');

    const env = loadRadiaViteEnv('development', {
      frontendRoot,
      workspaceRoot,
      env: {},
    });

    expect(env.VITE_DEV_PROXY_TARGET).toBe('http://localhost:9000');
  });
});
