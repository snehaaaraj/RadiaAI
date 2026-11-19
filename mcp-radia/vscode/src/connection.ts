import { execFile } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { homedir } from 'node:os';
import * as path from 'node:path';
import { promisify } from 'node:util';

const execute = promisify(execFile);

export interface Connection {
  url: string;
  clientId: string;
  clientSecret: string;
  uvCommand: string;
  revision: string;
}

export function validateJamaUrl(value: string): string | undefined {
  try {
    const url = new URL(value.trim());
    if (
      url.protocol === 'https:' && url.hostname && !url.username && !url.password &&
      url.pathname === '/' && !url.search && !url.hash && url.port !== '0' &&
      !/\s/.test(value.trim()) && !value.includes('\\')
    ) {
      return undefined;
    }
  } catch {
    // URL syntax errors have the same actionable validation message as invalid roots.
  }
  return 'Enter an HTTPS Jama instance root, e.g. https://yourorg.jamacloud.com (no /rest or item URL).';
}

export function createConnection(
  url: string, clientId: string, clientSecret: string, uvCommand: string,
): Connection {
  const validation = validateJamaUrl(url);
  if (validation) {
    throw new Error(validation);
  }
  if (!clientId.trim() || !clientSecret.trim() || !uvCommand.trim()) {
    throw new Error('Jama OAuth client ID, secret and UV executable are required.');
  }
  return {
    url: new URL(url.trim()).origin,
    clientId: clientId.trim(),
    clientSecret: clientSecret.trim(),
    uvCommand,
    revision: randomUUID(),
  };
}

export function readConnection(value: string | undefined): Connection | undefined {
  if (value === undefined) {
    return undefined;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error('Saved Radia MCP account is unreadable. Run Radia MCP: Connect or Update Account.');
  }
  if (
    typeof parsed !== 'object' || parsed === null ||
    !('url' in parsed) || typeof parsed.url !== 'string' || validateJamaUrl(parsed.url) ||
    !('clientId' in parsed) || typeof parsed.clientId !== 'string' || !parsed.clientId.trim() ||
    !('clientSecret' in parsed) || typeof parsed.clientSecret !== 'string' || !parsed.clientSecret.trim() ||
    !('uvCommand' in parsed) || typeof parsed.uvCommand !== 'string' || !parsed.uvCommand.trim() ||
    !('revision' in parsed) || typeof parsed.revision !== 'string' || !parsed.revision
  ) {
    throw new Error('Saved Radia MCP account is invalid. Run Radia MCP: Connect or Update Account.');
  }
  return {
    url: parsed.url, clientId: parsed.clientId, clientSecret: parsed.clientSecret,
    uvCommand: parsed.uvCommand, revision: parsed.revision,
  };
}

export async function findUv(configured: string): Promise<string> {
  const executable = process.platform === 'win32' ? 'uv.exe' : 'uv';
  const candidates = configured !== 'uv'
    ? [configured]
    : ['uv', path.join(homedir(), '.local', 'bin', executable)];
  for (const candidate of candidates) {
    try {
      const result = await execute(candidate, ['--version'], { timeout: 5000, windowsHide: true });
      if (/^uv \d+\./.test(result.stdout.trim())) {
        return candidate;
      }
    } catch (error) {
      if (
        typeof error === 'object' && error !== null && 'code' in error &&
        (error.code === 'ENOENT' || error.code === 'EACCES')
      ) {
        continue;
      }
      throw new Error('UV could not run. Check Radia MCP: UV Path in settings and restart setup.');
    }
  }
  throw new Error(
    'UV was not found. Install UV from https://docs.astral.sh/uv/getting-started/installation/, ' +
    'restart VS Code, and run Radia MCP: Connect or Update Account again. ' +
    'For a custom installation, set Radia MCP: UV Path.',
  );
}
