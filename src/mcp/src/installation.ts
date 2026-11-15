import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { pathIdentity, type Configuration } from './config.js';
import {
  LifecycleError,
  installOperationSchema,
  installationSchema,
  type InstallOperation,
  type InstallationRecord,
} from './contracts.js';

/** An installation receipt with the paths derived from it. */
export interface Installation extends InstallationRecord {
  backend: string;
  uv: string;
}

const INSTALLATION_FILE = 'installation.json';
const OPERATION_FILE = 'install-operation.json';

/** `null` when the workspace has never been initialized; never a connection error. */
export async function tryReadInstallation(config: Configuration): Promise<Installation | null> {
  const text = await readOptionalFile(join(config.installRoot, INSTALLATION_FILE));
  if (text === null) {
    return null;
  }
  const record = installationSchema.parse(JSON.parse(text));
  return {
    ...record,
    backend: join(record.install_root, 'versions', record.version, 'workbench', 'backend'),
    uv: join(record.install_root, 'runtimes', 'uv', record.runtime.uv, 'uv.exe'),
  };
}

/** Require an installation this MCP instance may use. */
export async function readInstallation(config: Configuration): Promise<Installation> {
  const installation = await tryReadInstallation(config);
  if (!installation) {
    throw new LifecycleError(
      'WORKBENCH_NOT_INSTALLED',
      'No installation receipt exists; call workbench_init first.',
    );
  }
  assertCompatibleInstallation(config, installation);
  return installation;
}

/** The persistent install task, so status can answer while init is still running. */
export async function readInstallOperation(config: Configuration): Promise<InstallOperation | null> {
  const text = await readOptionalFile(join(config.installRoot, OPERATION_FILE));
  if (text === null) {
    return null;
  }
  return installOperationSchema.parse(JSON.parse(text));
}

/** Refuse a receipt that belongs to another root or workspace. */
export function assertCompatibleInstallation(config: Configuration, installation: Installation): void {
  if (pathIdentity(installation.install_root) !== pathIdentity(config.installRoot)) {
    throw new LifecycleError('INSTALLATION_MOVED', 'The installation receipt belongs to another install root.');
  }
  if (pathIdentity(installation.workspace) !== pathIdentity(config.workspace)) {
    throw new LifecycleError(
      'WORKBENCH_WORKSPACE_MISMATCH',
      'The installation receipt was created for another workspace.',
    );
  }
}

async function readOptionalFile(path: string): Promise<string | null> {
  try {
    return await readFile(path, 'utf8');
  } catch (error) {
    if (isMissingFile(error)) {
      return null;
    }
    throw error;
  }
}

function isMissingFile(error: unknown): boolean {
  return typeof error === 'object' && error !== null && 'code' in error && (error as { code: string }).code === 'ENOENT';
}
