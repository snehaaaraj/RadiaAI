'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createRequire } = require('node:module');
const { test } = require('node:test');
const { promisify } = require('node:util');
const vm = require('node:vm');

const connection = require('../out/connection');
const { stageServer } = require('../scripts/stage-server.cjs');

test('display names change without changing extension, command or provider identities', () => {
  const manifest = require('../package.json');
  assert.equal(manifest.displayName, 'Radia MCP');
  assert.equal(manifest.name, 'radia-jama');
  assert.equal(manifest.publisher, 'radiaai');
  assert.equal(manifest.contributes.mcpServerDefinitionProviders[0].id, 'radia-jama');
  assert.equal(manifest.contributes.mcpServerDefinitionProviders[0].label, 'Radia MCP');
  assert.equal(manifest.contributes.commands[0].command, 'radiaJama.configure');
  assert.equal(manifest.contributes.commands[0].title, 'Radia MCP: Connect or Update Account');
});

function harness(options = {}) {
  const commands = new Map();
  const secrets = new Map();
  const messages = [];
  const inputOptions = [];
  const events = [];
  let provider;
  let inputIndex = 0;
  let listener;
  const context = {
    subscriptions: [],
    globalStorageUri: { fsPath: path.join(os.tmpdir(), 'radia-test-storage') },
    extension: { packageJSON: { version: '0.1.0' } },
    asAbsolutePath: (relative) => path.join(os.tmpdir(), 'extension with spaces', relative),
    secrets: {
      get: async (key) => {
        if (options.storageFailure) throw new Error('test-secret-storage-error');
        return secrets.get(key);
      },
      store: async (key, value) => {
        if (options.storageFailure) throw new Error('test-secret-storage-error');
        secrets.set(key, value);
        listener({ key });
      },
      delete: async (key) => {
        secrets.delete(key);
        listener({ key });
      },
      onDidChange: (callback) => {
        listener = callback;
        return { dispose() {} };
      },
    },
  };
  const vscode = {
    EventEmitter: class {
      event = () => ({ dispose() {} });
      fire() { events.push('changed'); }
      dispose() {}
    },
    commands: {
      registerCommand: (id, command) => {
        commands.set(id, command);
        return { dispose() {} };
      },
    },
    workspace: { getConfiguration: () => ({ get: () => 'uv' }) },
    window: {
      showInputBox: async (config) => {
        inputOptions.push(config);
        return options.inputs?.[inputIndex++];
      },
      showInformationMessage: async (message) => messages.push(message),
      showErrorMessage: async (message) => messages.push(message),
      showWarningMessage: async () => options.removeConfirmed ? 'Remove account' : undefined,
    },
    lm: {
      registerMcpServerDefinitionProvider: (id, value) => {
        assert.equal(id, 'radia-jama');
        provider = value;
        return { dispose() {} };
      },
    },
    McpStdioServerDefinition: class {
      constructor(label, command, args, env, version) {
        Object.assign(this, { label, command, args, env, version });
      }
    },
  };
  const file = path.resolve(__dirname, '../out/extension.js');
  const localRequire = createRequire(file);
  const exports = {};
  const wrappedRequire = (name) => {
    if (name === 'vscode') return vscode;
    if (name === './connection') return {
      ...connection,
      findUv: async () => {
        if (options.uvFailure) throw new Error('Install UV first.');
        return path.join(os.homedir(), '.local', 'bin', 'uv');
      },
    };
    return localRequire(name);
  };
  vm.runInNewContext(
    '(function(require, exports) {' + fs.readFileSync(file, 'utf8') + '\n})',
    {},
    { filename: file },
  )(wrappedRequire, exports);
  exports.activate(context);
  return { commands, secrets, messages, inputOptions, events, provider, context };
}

test('discovery never prompts and publishes nothing before explicit setup', async () => {
  const app = harness();
  assert.equal((await app.provider.provideMcpServerDefinitions()).length, 0);
  assert.equal(app.inputOptions.length, 0);
  assert.equal(app.messages.length, 0);
});

test('setup masks credentials and publishes a complete repo-free definition', async () => {
  const app = harness({
    inputs: ['https://EXAMPLE.jamacloud.com/', 'test-personal-client', 'test-personal-secret'],
  });
  await app.commands.get('radiaJama.configure')();
  assert.equal(app.secrets.size, 1);
  assert.equal(app.inputOptions[1].password, true);
  assert.equal(app.inputOptions[2].password, true);
  assert.equal(app.events.length, 1);
  const [definition] = await app.provider.provideMcpServerDefinitions();
  assert.equal(definition.label, 'Radia MCP');
  assert.equal(definition.env.JAMA_BASE_URL, 'https://example.jamacloud.com');
  assert.equal(definition.env.JAMA_CLIENT_ID, 'test-personal-client');
  assert.equal(definition.env.JAMA_CLIENT_SECRET, 'test-personal-secret');
  assert.equal(
    definition.env.UV_PROJECT_ENVIRONMENT,
    path.join(app.context.globalStorageUri.fsPath, 'runtime-venv'),
  );
  assert.ok(definition.args.includes('--locked'));
  assert.ok(definition.args.includes('--no-dev'));
  assert.ok(definition.args.includes(app.context.asAbsolutePath('server')));
  assert.ok(!JSON.stringify(definition.args).includes('test-personal-secret'));
  assert.ok(!definition.version.includes('test-personal'));
  assert.ok(!JSON.stringify(app.messages).includes('test-personal'));
  assert.ok(!JSON.stringify(definition).includes('${input:'));
  assert.ok(!JSON.stringify(definition).includes('${command:'));
});

for (const inputs of [
  [],
  ['https://example.jamacloud.com'],
  ['https://example.jamacloud.com', 'client'],
]) {
  test(`cancelling step ${inputs.length + 1} never changes saved credentials`, async () => {
    const app = harness({ inputs });
    const existing = JSON.stringify(connection.createConnection('https://old.example.com', 'old', 'old', 'uv'));
    app.secrets.set('radiaJama.connection', existing);
    await app.commands.get('radiaJama.configure')();
    assert.equal(app.secrets.get('radiaJama.connection'), existing);
    assert.equal(app.events.length, 0);
  });
}

test('missing UV is actionable and does not request credentials', async () => {
  const app = harness({ uvFailure: true });
  await app.commands.get('radiaJama.configure')();
  assert.equal(app.inputOptions.length, 0);
  assert.match(app.messages[0], /UV/);
});

test('storage failure surfaces without a plaintext fallback or secret in errors', async () => {
  const app = harness({
    storageFailure: true,
    inputs: ['https://example.jamacloud.com', 'client', 'test-private-secret'],
  });
  await app.commands.get('radiaJama.configure')();
  assert.equal(app.secrets.size, 0);
  assert.match(app.messages[0], /No plaintext fallback/);
  await assert.rejects(app.provider.provideMcpServerDefinitions(), /could not be loaded/);
  assert.ok(!JSON.stringify(app.messages).includes('test-private-secret'));
});

test('removing an account requires approval and withdraws its server definition', async () => {
  const app = harness({ removeConfirmed: true });
  app.secrets.set('radiaJama.connection', JSON.stringify(
    connection.createConnection('https://example.com', 'client', 'secret', 'uv'),
  ));
  await app.commands.get('radiaJama.disconnect')();
  assert.equal(app.secrets.size, 0);
  assert.equal((await app.provider.provideMcpServerDefinitions()).length, 0);
  assert.match(app.messages[0], /Stop any running/);
});

test('dismissed removal leaves the account intact', async () => {
  const app = harness();
  app.secrets.set('radiaJama.connection', 'saved');
  await app.commands.get('radiaJama.disconnect')();
  assert.equal(app.secrets.size, 1);
});

test('credential rotation changes definition version without embedding secrets', async () => {
  const app = harness({ inputs: [
    'https://example.com', 'first', 'secret-one',
    'https://example.com', 'second', 'secret-two',
  ] });
  await app.commands.get('radiaJama.configure')();
  const [before] = await app.provider.provideMcpServerDefinitions();
  await app.commands.get('radiaJama.configure')();
  const [after] = await app.provider.provideMcpServerDefinitions();
  assert.notEqual(before.version, after.version);
  assert.equal(after.env.JAMA_CLIENT_ID, 'second');
});

test('Jama URL validation rejects HTTP, embedded credentials, paths and parameters', () => {
  for (const url of [
    '', 'http://example.com', 'https://user:pass@example.com',
    'https://example.com/rest', 'https://example.com?token=secret',
    'https://example.com#fragment', 'https://example .com', 'https://example.com:0',
    'https://example.com\\rest',
  ]) {
    assert.ok(connection.validateJamaUrl(url), url);
  }
  assert.equal(connection.validateJamaUrl('https://example.com/'), undefined);
});

test('invalid saved data reports a redacted error rather than publishing a broken definition', () => {
  assert.equal(connection.readConnection(undefined), undefined);
  for (const value of ['test-private-secret', '{}', 'null', '{"url":"http://example.com"}']) {
    assert.throws(() => connection.readConnection(value), (error) => {
      assert.match(error.message, /Saved Radia MCP account/);
      assert.ok(!error.message.includes('test-private-secret'));
      return true;
    });
  }
});

test('staging allowlist excludes environments, tests and arbitrary developer files', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'radia-vsix-stage-'));
  try {
    const project = path.join(root, 'project');
    const destination = path.join(root, 'server');
    for (const name of [
      'pyproject.toml', 'uv.lock', 'desktop/server.py', 'mcp_radia/__init__.py',
      'mcp_radia/tools/jama.py', '.env', '.venv/private.py', 'tests/private.py',
      'mcp_radia/.env', 'mcp_radia/__pycache__/private.pyc',
    ]) {
      const file = path.join(project, name);
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, name.endsWith('.py') ? '# example' : 'developer-only');
    }
    fs.writeFileSync(path.join(project, 'manifest.json'), '{"version":"0.1.0"}');
    const files = stageServer(project, destination);
    assert.equal(files.length, 5);
    assert.ok(!fs.existsSync(path.join(destination, '.env')));
    assert.ok(!fs.existsSync(path.join(destination, '.venv')));
    assert.ok(!fs.existsSync(path.join(destination, 'tests')));
    assert.ok(!fs.existsSync(path.join(destination, 'mcp_radia', '.env')));
    fs.writeFileSync(path.join(destination, 'stale.txt'), 'stale');
    stageServer(project, destination);
    assert.ok(!fs.existsSync(path.join(destination, 'stale.txt')));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('staging refuses source/root-like destinations and mismatched versions', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'radia-vsix-guard-'));
  try {
    assert.throws(() => stageServer(root, root), /dedicated server directory/);
    assert.throws(() => stageServer(root, path.parse(root).root), /dedicated server directory/);
    const project = path.join(root, 'project');
    fs.mkdirSync(project);
    fs.writeFileSync(path.join(project, 'manifest.json'), '{"version":"99.0.0"}');
    assert.throws(
      () => stageServer(project, path.join(root, 'server')),
      /version must match/,
    );
    assert.ok(!fs.existsSync(path.join(root, 'server')));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('UV validation does not execute a shell and requires a UV version response', async () => {
  const file = path.resolve(__dirname, '../out/connection.js');
  const localRequire = createRequire(file);
  const calls = [];
  const exports = {};
  const fakeExec = (command, args, options, callback) => {
    calls.push({ command, args, options });
    if (command === 'missing-uv') {
      callback(Object.assign(new Error('not found'), { code: 'ENOENT' }));
    } else {
      callback(null, command === 'good-uv' ? 'uv 0.11.28\n' : 'different program', '');
    }
  };
  fakeExec[promisify.custom] = (command, args, options) => new Promise((resolve, reject) => {
    fakeExec(command, args, options, (error, stdout, stderr) => {
      if (error) reject(error);
      else resolve({ stdout, stderr });
    });
  });
  vm.runInNewContext(
    '(function(require, exports, process) {' + fs.readFileSync(file, 'utf8') + '\n})',
    {},
    { filename: file },
  )(
    (name) => name === 'node:child_process' ? { execFile: fakeExec } : localRequire(name),
    exports,
    process,
  );
  assert.equal(await exports.findUv('good-uv'), 'good-uv');
  assert.equal(calls[0].args[0], '--version');
  assert.equal(calls[0].options.shell, undefined);
  assert.equal(calls[0].options.timeout, 5000);
  await assert.rejects(exports.findUv('missing-uv'), /UV was not found/);
  await assert.rejects(exports.findUv('wrong-program'), /UV was not found/);
});
