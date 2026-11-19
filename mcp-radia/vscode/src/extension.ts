import * as path from 'node:path';
import * as vscode from 'vscode';

import { createConnection, findUv, readConnection, validateJamaUrl } from './connection';

const SECRET_KEY = 'radiaJama.connection';

export function activate(context: vscode.ExtensionContext): void {
  const changed = new vscode.EventEmitter<void>();
  const reportFailure = async (): Promise<void> => {
    await vscode.window.showErrorMessage(
      'Radia MCP could not access saved account settings. Run Connect or Update Account again. ' +
      'If secure storage is unavailable, check your OS keychain. No plaintext fallback is used.',
    );
  };
  let configuring = false;

  context.subscriptions.push(
    changed,
    context.secrets.onDidChange((event) => {
      if (event.key === SECRET_KEY) {
        changed.fire();
      }
    }),
    vscode.commands.registerCommand('radiaJama.configure', async () => {
      if (configuring) {
        return;
      }
      configuring = true;
      try {
        let uvCommand: string;
        try {
          uvCommand = await findUv(
            vscode.workspace.getConfiguration('radiaJama').get<string>('uvPath', 'uv'),
          );
        } catch (error) {
          await vscode.window.showErrorMessage(
            error instanceof Error ? error.message : 'UV setup failed. Check your UV installation.',
          );
          return;
        }
        const url = await vscode.window.showInputBox({
          title: 'Radia MCP: 1 of 3 - Jama URL',
          prompt: 'Enter your HTTPS Jama instance root, not an item URL.',
          placeHolder: 'https://yourorg.jamacloud.com',
          ignoreFocusOut: true,
          validateInput: validateJamaUrl,
        });
        if (url === undefined) {
          return;
        }
        const clientId = await vscode.window.showInputBox({
          title: 'Radia MCP: 2 of 3 - Your OAuth client ID',
          prompt: 'Your personal Jama API client ID, not your email address.',
          password: true,
          ignoreFocusOut: true,
          validateInput: (value) => value.trim() ? undefined : 'Client ID is required.',
        });
        if (clientId === undefined) {
          return;
        }
        const clientSecret = await vscode.window.showInputBox({
          title: 'Radia MCP: 3 of 3 - Your OAuth client secret',
          prompt: 'Your personal Jama API client secret, not your login password.',
          password: true,
          ignoreFocusOut: true,
          validateInput: (value) => value.trim() ? undefined : 'Client secret is required.',
        });
        if (clientSecret === undefined) {
          return;
        }
        const connection = createConnection(url, clientId, clientSecret, uvCommand);
        await context.secrets.store(SECRET_KEY, JSON.stringify(connection));
        await vscode.window.showInformationMessage(
          'Radia MCP account saved securely. Start or restart Radia MCP in MCP: List Servers, ' +
          'then ask Copilot Agent to list your Jama projects. First launch downloads Python and dependencies.',
        );
      } catch {
        await reportFailure();
      } finally {
        configuring = false;
      }
    }),
    vscode.commands.registerCommand('radiaJama.disconnect', async () => {
      const decision = await vscode.window.showWarningMessage(
        'Remove the saved Jama account? Stop Radia MCP in MCP: List Servers first; ' +
        'removing credentials does not revoke tokens held by an already running process.',
        { modal: true },
        'Remove account',
      );
      if (decision !== 'Remove account') {
        return;
      }
      try {
        await context.secrets.delete(SECRET_KEY);
        await vscode.window.showInformationMessage(
          'Saved Jama account removed. Stop any running Radia MCP server; revoke credentials in Jama if required.',
        );
      } catch {
        await reportFailure();
      }
    }),
    vscode.lm.registerMcpServerDefinitionProvider('radia-jama', {
      onDidChangeMcpServerDefinitions: changed.event,
      provideMcpServerDefinitions: async () => {
        let connection;
        try {
          connection = readConnection(await context.secrets.get(SECRET_KEY));
        } catch {
          throw new Error(
            'Radia MCP account settings could not be loaded. Run Radia MCP: Connect or Update Account.',
          );
        }
        if (!connection) {
          return [];
        }
        const runtime = context.asAbsolutePath('server');
        return [new vscode.McpStdioServerDefinition(
          'Radia MCP',
          connection.uvCommand,
          ['run', '--directory', runtime, '--python', '3.13', '--locked', '--no-dev', 'desktop/server.py'],
          {
            JAMA_BASE_URL: connection.url,
            JAMA_CLIENT_ID: connection.clientId,
            JAMA_CLIENT_SECRET: connection.clientSecret,
            UV_PROJECT_ENVIRONMENT: path.join(context.globalStorageUri.fsPath, 'runtime-venv'),
          },
          `${context.extension.packageJSON.version}:${connection.revision}`,
        )];
      },
    }),
  );
}
