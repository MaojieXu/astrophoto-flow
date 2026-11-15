import { execFile, spawn, type ChildProcess } from 'node:child_process';
import { closeSync, openSync } from 'node:fs';
import { mkdir, mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { z } from 'zod';

import type { Configuration } from '../config.js';
import { LifecycleError, type InstallOperation } from '../contracts.js';
import { readInstallation, readInstallOperation } from '../installation.js';

/**
 * The fixed lifecycle bootstrap.
 *
 * This is the only module allowed to create a process: it launches the pinned
 * installer script and the installed controller's CLI. No caller-supplied
 * command, URL, script path or pid ever reaches `spawn` or `execFile`.
 */

const execFileAsync = promisify(execFile);

const INSTALLER_SCRIPT = fileURLToPath(new URL('../installer/install.ps1', import.meta.url));
const PRODUCT_FILE = fileURLToPath(new URL('../../package.json', import.meta.url));
const WORKSPACE_PRODUCT_FILE = fileURLToPath(new URL('../../../../package.json', import.meta.url));

const CONTROLLER_TIMEOUT_MS = 15 * 60_000;
const OPERATION_WAIT_MS = 30_000;
const POLL_INTERVAL_MS = 250;
const MAX_OUTPUT_BYTES = 16 * 1024 * 1024;
const workerInput = z.strictObject({
  installRoot: z.string().min(1),
  workspace: z.string().min(1),
  candidateManifest: z.string().min(1).nullable(),
  operationId: z.string().regex(/^init-[a-f0-9]{32}$/),
  logPath: z.string().min(1),
});
type InstallerInput = z.infer<typeof workerInput>;

export type ControllerAction = 'init' | 'start' | 'status' | 'stop';

export interface ControllerOptions {
  operationId?: string;
}

interface ExecFailure {
  code?: number | string;
  stdout?: string;
  stderr?: string;
  message?: string;
}

/** The version this MCP ships with; the installer downloads exactly this version. */
export async function readProductVersion(): Promise<string> {
  for (const candidate of [PRODUCT_FILE, WORKSPACE_PRODUCT_FILE]) {
    const version = await readVersion(candidate);
    if (version) {
      return version;
    }
  }
  throw new LifecycleError('PRODUCT_IDENTITY_MISSING', 'The MCP package has no usable version field.');
}

async function readVersion(path: string): Promise<string | null> {
  let text: string;
  try {
    text = await readFile(path, 'utf8');
  } catch {
    return null;
  }
  const version = (JSON.parse(text) as { version?: unknown }).version;
  return typeof version === 'string' && version.length > 0 ? version : null;
}

/**
 * Start the pinned installer for one operation and return its initial progress.
 *
 * The installer has independent stdio so a slow download outlives the tool call; progress
 * is read back from the operation file the installer owns.
 */
export async function launchInstaller(config: Configuration, operationId: string): Promise<InstallOperation> {
  await mkdir(config.installRoot, { recursive: true });
  const logDirectory = await mkdtemp(join(tmpdir(), 'astrophotoflow-init-'));
  const logPath = join(logDirectory, 'install.log');
  const launcherLogPath = join(logDirectory, 'launcher.log');
  const input = workerInput.parse({ ...config, operationId, logPath });
  const child = await spawnInstaller(input, launcherLogPath);
  return waitForOperation(config, operationId, child, launcherLogPath);
}

async function runInstallerWorker(input: InstallerInput): Promise<void> {
  const version = await readProductVersion();
  const args = [
    '-NoProfile',
    '-NonInteractive',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    INSTALLER_SCRIPT,
    '-Version',
    version,
    '-InstallRoot',
    input.installRoot,
    '-Workspace',
    input.workspace,
    '-OperationId',
    input.operationId,
    '-LogPath',
    input.logPath,
    '-Json',
  ];
  if (input.candidateManifest) {
    args.push('-ManifestPath', input.candidateManifest);
  }
  // PowerShell needs a live console owner on Windows. This detached Node worker
  // owns it until installation finishes, even after the MCP disconnects.
  await new Promise<void>((done, fail) => {
    const child = spawn('powershell.exe', args, {
      windowsHide: true,
      stdio: ['ignore', 'inherit', 'inherit'],
    });
    child.once('error', fail);
    child.once('exit', (code) => { process.exitCode = code ?? 1; done(); });
  });
}

/** Run one controller command through the installed runtime, never the host Python. */
export async function invokeController<T>(
  config: Configuration,
  action: ControllerAction,
  options: ControllerOptions = {},
): Promise<T> {
  const installation = await readInstallation(config);
  const args = [
    'run',
    '--locked',
    '--no-sync',
    '--project',
    installation.backend,
    '--directory',
    installation.backend,
    'python',
    '-m',
    'astrophotoflow.cli',
    action,
    '--workspace',
    config.workspace,
    '--json',
  ];
  if (options.operationId) {
    args.push('--operation-id', options.operationId);
  }
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    PYTHONUTF8: '1',
    PYTHONDONTWRITEBYTECODE: '1',
    UV_PROJECT_ENVIRONMENT: join(installation.backend, '.venv'),
    UV_PYTHON_INSTALL_DIR: join(installation.install_root, 'runtimes', 'python'),
    UV_CACHE_DIR: join(installation.install_root, 'cache', 'uv'),
    UV_PYTHON_DOWNLOADS: 'never',
  };
  let stdout: string;
  try {
    const result = await execFileAsync(installation.uv, args, {
      cwd: installation.backend,
      env,
      timeout: CONTROLLER_TIMEOUT_MS,
      maxBuffer: MAX_OUTPUT_BYTES,
      windowsHide: true,
      encoding: 'utf8',
    });
    stdout = result.stdout;
  } catch (error) {
    throw controllerFailure(error as ExecFailure, action, options.operationId);
  }
  return parseControllerOutput<T>(stdout, action);
}

async function spawnInstaller(
  input: InstallerInput,
  launcherLogPath: string,
): Promise<ChildProcess> {
  // Windows PowerShell 5.1 can exit before -File runs with DETACHED_PROCESS;
  // detach a fixed Node worker instead, with no pipes attached to this MCP.
  // Keep this descriptor separate from the log PowerShell opens for appending.
  const output = openSync(launcherLogPath, 'a');
  return new Promise<ChildProcess>((resolve, reject) => {
    const child = spawn(process.execPath, [fileURLToPath(import.meta.url), '--installer-worker', JSON.stringify(input)], {
      detached: true,
      stdio: ['ignore', output, output],
      windowsHide: true,
    });
    child.once('error', (error: Error) => {
      closeSync(output);
      reject(new LifecycleError('INSTALLER_UNAVAILABLE', `Cannot launch the installer worker: ${error.message}`));
    });
    child.once('spawn', () => {
      child.unref();
      closeSync(output);
      resolve(child);
    });
  });
}

async function waitForOperation(
  config: Configuration,
  operationId: string,
  child: ChildProcess,
  logPath: string,
): Promise<InstallOperation> {
  const deadline = Date.now() + OPERATION_WAIT_MS;
  while (Date.now() < deadline) {
    const operation = await readInstallOperation(config);
    if (operation && operation.operation_id === operationId) {
      return operation;
    }
    if (child.exitCode !== null || child.signalCode !== null) {
      const diagnostic = (await readFile(logPath, 'utf8')).trim().slice(-1600);
      throw new LifecycleError(
        'INSTALLER_UNAVAILABLE',
        `The installer exited (${child.exitCode ?? child.signalCode}) before recording ${operationId}; inspect ${logPath}. ${diagnostic}`,
        operationId,
      );
    }
    await sleep(POLL_INTERVAL_MS);
  }
  throw new LifecycleError(
    'INSTALLER_UNAVAILABLE',
    `The installer did not record operation ${operationId}; inspect ${logPath}.`,
    operationId,
  );
}

function parseControllerOutput<T>(stdout: string, action: ControllerAction): T {
  const text = stdout.trim();
  if (text.length === 0) {
    throw new LifecycleError('CONTROLLER_PROTOCOL_ERROR', `The controller returned no output for ${action}.`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new LifecycleError(
      'CONTROLLER_PROTOCOL_ERROR',
      `The controller returned output that is not JSON: ${text.slice(0, 400)}`,
    );
  }
}

function controllerFailure(error: ExecFailure, action: ControllerAction, operationId?: string): LifecycleError {
  const stderr = (error.stderr ?? '').trim();
  const envelope = parseEnvelope(stderr);
  if (envelope) {
    return new LifecycleError(envelope.code, envelope.message, envelope.operationId ?? operationId);
  }
  const detail = stderr.length > 0 ? stderr.slice(-800) : (error.message ?? 'no diagnostic output');
  return new LifecycleError('CONTROLLER_FAILED', `The controller failed to ${action}: ${detail}`, operationId);
}

function parseEnvelope(stderr: string): { code: string; message: string; operationId?: string } | null {
  for (const line of stderr.split(/\r?\n/).reverse()) {
    const candidate = line.trim();
    if (!candidate.startsWith('{') || !candidate.endsWith('}')) {
      continue;
    }
    try {
      const parsed = JSON.parse(candidate) as { error?: { code?: unknown; message?: unknown; fields?: unknown } };
      const code = parsed.error?.code;
      if (typeof code === 'string') {
        const message = typeof parsed.error?.message === 'string' ? parsed.error.message : code;
        const fields = parsed.error?.fields as { operation_id?: unknown } | undefined;
        const operationId = typeof fields?.operation_id === 'string' ? fields.operation_id : undefined;
        return { code, message, operationId };
      }
    } catch {
      continue;
    }
  }
  return null;
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url) && process.argv[2] === '--installer-worker') {
  try {
    await runInstallerWorker(workerInput.parse(JSON.parse(process.argv[3] ?? 'null')));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
