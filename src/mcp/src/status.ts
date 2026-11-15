import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { pathIdentity, type Configuration } from './config.js';
import { LifecycleError, processRecordSchema, type ProcessRecord } from './contracts.js';
import {
  assertCompatibleInstallation,
  readInstallOperation,
  tryReadInstallation,
  type Installation,
} from './installation.js';

/** The packaged frontend entry; a page without it is not the native canvas. */
export const WEB_PAGE_MARKER = 'id="splash-loader"';

const PROBE_TIMEOUT_MS = 2_000;

export interface ServiceHealth {
  version?: string;
  workspace?: string;
  database?: string;
}

export interface ReadyRuntime {
  record: ProcessRecord;
  installation: Installation;
  serviceUrl: string;
  webUrl: string;
}

export type StatusName =
  | 'not_installed'
  | 'installing'
  | 'install_failed'
  | 'stopped'
  | 'starting'
  | 'stopping'
  | 'ready'
  | 'unknown';

export interface StatusReport {
  status: StatusName;
  workspace: string;
  install_root: string;
  version: string | null;
  source: 'release' | 'candidate' | null;
  publication: 'published' | 'candidate' | null;
  installed: boolean;
  ready: boolean;
  operation_id: string | null;
  phase: string | null;
  message: string | null;
  service_url: string | null;
  web_url: string | null;
  log: string | null;
}

/** The controller's process record; `null` when nothing was started here. */
export async function readRuntimeRecord(config: Configuration): Promise<ProcessRecord | null> {
  const path = join(config.workspace, 'run', 'processes.json');
  let text: string;
  try {
    text = await readFile(path, 'utf8');
  } catch (error) {
    if (isMissingFile(error)) {
      return null;
    }
    throw error;
  }
  return processRecordSchema.parse(JSON.parse(text));
}

/** `null` when the service is not answering, never a thrown network error. */
export async function probeService(baseUrl: string): Promise<ServiceHealth | null> {
  try {
    const response = await fetch(`${baseUrl}/health`, {
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
      redirect: 'error',
    });
    if (!response.ok) {
      return null;
    }
    const body = (await response.json()) as ServiceHealth;
    return typeof body === 'object' && body !== null ? body : null;
  } catch {
    return null;
  }
}

/** The engine serves the native canvas; only a page carrying its marker counts. */
export async function probeEnginePage(webUrl: string): Promise<boolean> {
  try {
    const response = await fetch(webUrl, { signal: AbortSignal.timeout(PROBE_TIMEOUT_MS), redirect: 'error' });
    if (!response.ok) {
      return false;
    }
    const body = await response.text();
    return body.includes(WEB_PAGE_MARKER);
  } catch {
    return false;
  }
}

/** Verify both halves of a running pair against the workspace it claims to serve. */
export async function verifyReadyRuntime(record: ProcessRecord, config: Configuration): Promise<boolean> {
  if (!record.client) {
    return false;
  }
  const health = await probeService(record.client.service_url);
  if (!health || typeof health.workspace !== 'string') {
    return false;
  }
  if (pathIdentity(health.workspace) !== pathIdentity(config.workspace)) {
    return false;
  }
  return probeEnginePage(record.client.web_url);
}

/** Require a verified pair; node queries must never invent a URL. */
export async function requireReadyRuntime(config: Configuration): Promise<ReadyRuntime> {
  const installation = await tryReadInstallation(config);
  if (!installation) {
    throw new LifecycleError(
      'WORKBENCH_NOT_INSTALLED',
      'No installation receipt exists; call workbench_init first.',
    );
  }
  assertCompatibleInstallation(config, installation);
  const record = await readRuntimeRecord(config);
  if (!record || !record.client) {
    throw new LifecycleError('WORKBENCH_NOT_RUNNING', 'The workbench is not running; call workbench_start first.');
  }
  if (pathIdentity(record.workspace) !== pathIdentity(config.workspace)) {
    throw new LifecycleError(
      'WORKBENCH_WORKSPACE_MISMATCH',
      'The running workbench belongs to another workspace.',
    );
  }
  if (!(await verifyReadyRuntime(record, config))) {
    throw new LifecycleError('WORKBENCH_UNVERIFIED', 'The running workbench did not answer a readiness probe.');
  }
  return { record, installation, serviceUrl: record.client.service_url, webUrl: record.client.web_url };
}

/** Installation progress first, then the running pair, then the stopped state. */
export async function getWorkbenchStatus(config: Configuration): Promise<StatusReport> {
  const report: StatusReport = {
    status: 'not_installed',
    workspace: config.workspace,
    install_root: config.installRoot,
    version: null,
    source: null,
    publication: null,
    installed: false,
    ready: false,
    operation_id: null,
    phase: null,
    message: null,
    service_url: null,
    web_url: null,
    log: null,
  };

  const operation = await readInstallOperation(config);
  if (operation && (operation.status === 'accepted' || operation.status === 'running')) {
    return {
      ...report,
      status: 'installing',
      version: operation.version,
      source: operation.source,
      publication: operation.publication,
      operation_id: operation.operation_id,
      phase: operation.phase,
      message: operation.message ?? null,
      log: operation.log ?? null,
    };
  }

  const installation = await tryReadInstallation(config);
  if (!installation) {
    if (operation && operation.status === 'failed') {
      return {
        ...report,
        status: 'install_failed',
        version: operation.version,
        source: operation.source,
        publication: operation.publication,
        operation_id: operation.operation_id,
        phase: operation.phase,
        message: operation.message ?? null,
        log: operation.log ?? null,
      };
    }
    return report;
  }

  report.version = installation.version;
  report.source = installation.source;
  report.publication = installation.publication;
  report.installed = true;

  const record = await readRuntimeRecord(config);
  if (!record) {
    return {
      ...report,
      status: operation && operation.status === 'failed' ? 'install_failed' : 'stopped',
      operation_id: operation?.operation_id ?? null,
      phase: operation?.phase ?? null,
      message: operation?.status === 'failed' ? (operation.message ?? null) : null,
      log: operation?.status === 'failed' ? (operation.log ?? null) : null,
    };
  }

  if (pathIdentity(record.workspace) !== pathIdentity(config.workspace)) {
    return {
      ...report,
      status: 'unknown',
      operation_id: record.operation_id,
      phase: record.phase,
      message: 'The process record belongs to another workspace.',
    };
  }

  const serviceUrl = record.client?.service_url ?? null;
  const webUrl = record.client?.web_url ?? null;
  if (record.phase === 'starting' || record.phase === 'stopping') {
    return {
      ...report,
      status: record.phase,
      operation_id: record.operation_id,
      phase: record.phase,
      message: record.message,
      service_url: serviceUrl,
      web_url: webUrl,
    };
  }
  if (record.phase !== 'ready') {
    return {
      ...report,
      status: 'unknown',
      operation_id: record.operation_id,
      phase: record.phase,
      message: record.message ?? 'The process record is in an unexpected phase.',
    };
  }

  const verified = await verifyReadyRuntime(record, config);
  return {
    ...report,
    status: verified ? 'ready' : 'unknown',
    ready: verified,
    operation_id: record.operation_id,
    phase: record.phase,
    message: verified ? null : 'The process record claims ready, but the service or engine did not answer.',
    service_url: serviceUrl,
    web_url: webUrl,
  };
}

function isMissingFile(error: unknown): boolean {
  return typeof error === 'object' && error !== null && 'code' in error && (error as { code: string }).code === 'ENOENT';
}
