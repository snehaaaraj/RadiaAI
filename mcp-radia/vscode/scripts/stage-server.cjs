'use strict';

const fs = require('node:fs');
const path = require('node:path');

function stageServer(project, destination) {
  project = path.resolve(project);
  destination = path.resolve(destination);
  if (
    path.basename(destination) !== 'server' || destination === project ||
    project.startsWith(destination + path.sep) ||
    (fs.existsSync(destination) && fs.lstatSync(destination).isSymbolicLink())
  ) {
    throw new Error('Runtime staging must use a dedicated server directory outside the source package.');
  }
  const projectVersion = JSON.parse(fs.readFileSync(path.join(project, 'manifest.json'), 'utf8')).version;
  const extensionVersion = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8')).version;
  if (projectVersion !== extensionVersion) {
    throw new Error('VS Code extension version must match the MCP desktop manifest.');
  }
  const files = ['pyproject.toml', 'uv.lock', path.join('desktop', 'server.py')];
  const collect = (directory) => {
    for (const entry of fs.readdirSync(path.join(project, directory), { withFileTypes: true })) {
      const relative = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) {
        throw new Error(`Refusing symbolic link in runtime source: ${relative}`);
      }
      if (entry.isDirectory() && entry.name !== '__pycache__') {
        collect(relative);
      } else if (entry.isFile() && entry.name.endsWith('.py')) {
        files.push(relative);
      }
    }
  };
  collect('mcp_radia');
  for (const relative of files) {
    const source = path.join(project, relative);
    if (!fs.lstatSync(source).isFile() || !fs.realpathSync(source).startsWith(fs.realpathSync(project) + path.sep)) {
      throw new Error(`Missing or unsafe runtime input: ${relative}`);
    }
  }
  fs.mkdirSync(destination, { recursive: true });
  // Only the generated staging directory is replaced, never the source package.
  for (const entry of fs.readdirSync(destination)) {
    fs.rmSync(path.join(destination, entry), { recursive: true, force: true });
  }
  for (const relative of files) {
    const target = path.join(destination, relative);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(path.join(project, relative), target);
  }
  return files;
}

if (require.main === module) {
  const project = path.resolve(__dirname, '..', '..');
  const destination = path.resolve(__dirname, '..', 'server');
  console.log(`Staged ${stageServer(project, destination).length} runtime files.`);
}

module.exports = { stageServer };
