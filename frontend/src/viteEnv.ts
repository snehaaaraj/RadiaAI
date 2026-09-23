import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

type ViteEnvOptions = {
  frontendRoot?: string;
  workspaceRoot?: string;
  env?: NodeJS.ProcessEnv;
};

const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_ROOT = path.resolve(FRONTEND_ROOT, '..');

function unescapeQuotedValue(value: string) {
  return value
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\r')
    .replace(/\\t/g, '\t')
    .replace(/\\\\/g, '\\')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'");
}

function parseEnvFile(contents: string) {
  const parsed: Record<string, string> = {};

  for (const line of contents.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }

    const normalized = trimmed.startsWith('export ') ? trimmed.slice(7).trimStart() : trimmed;
    const equalsIndex = normalized.indexOf('=');
    if (equalsIndex < 0) {
      continue;
    }

    const key = normalized.slice(0, equalsIndex).trim();
    if (!key) {
      continue;
    }

    let value = normalized.slice(equalsIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = unescapeQuotedValue(value.slice(1, -1));
    }

    parsed[key] = value;
  }

  return parsed;
}

function readEnvFile(envRoot: string, filename: string) {
  const filePath = path.join(envRoot, filename);
  if (!fs.existsSync(filePath)) {
    return {};
  }

  return parseEnvFile(fs.readFileSync(filePath, 'utf8'));
}

function loadEnvFromRoot(root: string, mode: string) {
  return {
    ...readEnvFile(root, '.env'),
    ...readEnvFile(root, '.env.local'),
    ...readEnvFile(root, `.env.${mode}`),
    ...readEnvFile(root, `.env.${mode}.local`),
  };
}

export function loadRadiaViteEnv(mode: string, options: ViteEnvOptions = {}) {
  const frontendRoot = options.frontendRoot ?? FRONTEND_ROOT;
  const workspaceRoot = options.workspaceRoot ?? WORKSPACE_ROOT;
  const processEnv = options.env ?? process.env;

  return {
    ...loadEnvFromRoot(workspaceRoot, mode),
    ...loadEnvFromRoot(frontendRoot, mode),
    ...processEnv,
  };
}
