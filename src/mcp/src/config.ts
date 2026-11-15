import { join, resolve } from 'node:path';
import process from 'node:process';
import { parseArgs } from 'node:util';

/** Where the installation lives and which workspace it serves. */
export interface Configuration {
  installRoot: string;
  workspace: string;
  /** Local release-manifest path; the installer never downloads from a caller-supplied URL. */
  candidateManifest: string | null;
}

/** `%LOCALAPPDATA%\AstroPhotoFlow` on Windows; the installer owns everything below it. */
export function defaultInstallRoot(env: NodeJS.ProcessEnv = process.env): string {
  const localAppData = env.LOCALAPPDATA;
  if (!localAppData) {
    throw new Error('LOCALAPPDATA is not set; pass --install-root instead.');
  }
  return join(localAppData, 'AstroPhotoFlow');
}

/** The single workspace this MCP instance manages by default. */
export function defaultWorkspace(installRoot: string): string {
  return join(installRoot, 'workspace');
}

/**
 * Parse the MCP launch arguments. Only fixed directories and a local manifest
 * path are accepted: no url, command or pid may arrive from a tool call.
 */
export function parseConfiguration(argv: string[], env: NodeJS.ProcessEnv = process.env): Configuration {
  const { values } = parseArgs({
    args: argv,
    options: {
      'install-root': { type: 'string' },
      workspace: { type: 'string' },
      'candidate-manifest': { type: 'string' },
    },
    strict: true,
    allowPositionals: false,
  });
  const installRoot = resolve(values['install-root'] ?? defaultInstallRoot(env));
  return {
    installRoot,
    workspace: resolve(values.workspace ?? defaultWorkspace(installRoot)),
    candidateManifest: values['candidate-manifest'] ? resolve(values['candidate-manifest']) : null,
  };
}

/** Path comparison that matches Windows case-insensitive identity. */
export function pathIdentity(path: string): string {
  const normalized = resolve(path).replace(/[\\/]+$/, '');
  return process.platform === 'win32' ? normalized.toLowerCase() : normalized;
}
