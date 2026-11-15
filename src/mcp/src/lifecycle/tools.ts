import { randomUUID } from 'node:crypto';

import type { FastMCP } from '@prefecthq/fastmcp-ts/server';
import { z } from 'zod';

import { openWorkbenchApi } from '../api/client.js';
import { serviceFailure } from '../api/errors.js';
import { pathIdentity, type Configuration } from '../config.js';
import { LifecycleError, stopResultSchema, type InstallOperation } from '../contracts.js';
import { stopWorkbench } from '../generated/api/sdk.gen.js';
import { zInitResult, zReadyResult } from '../generated/api/zod.gen.js';
import { guard } from '../guard.js';
import { assertCompatibleInstallation, readInstallation, readInstallOperation, tryReadInstallation } from '../installation.js';
import {
  getWorkbenchStatus,
  probeEnginePage,
  probeService,
  readRuntimeRecord,
  type StatusReport,
} from '../status.js';
import { invokeController, launchInstaller } from './bootstrap.js';

const STOP_TIMEOUT_MS = 120_000;
const POLL_INTERVAL_MS = 500;

export interface InitReport {
  status: 'initialized' | 'reused' | 'accepted' | 'running' | 'succeeded' | 'failed' | 'unknown';
  version: string;
  workspace: string;
  database_revision: string | null;
  operation_id: string | null;
  source: 'release' | 'candidate';
  publication: 'published' | 'candidate';
  phase: string;
  message: string | null;
  log: string | null;
}

export interface StartReport {
  status: 'ready';
  version: string;
  workspace: string;
  service_url: string;
  web_url: string;
  reused: boolean;
  database: string | null;
  verified: true;
}

export interface StopReport {
  status: 'stopped' | 'not_running';
  mode: 'service' | 'controller' | 'none';
  version: string | null;
  workspace: string;
  operation_id: string | null;
  service_stopped: boolean;
  engine_stopped: boolean;
  message: string | null;
  verified: true;
}

const workspaceInput = z.strictObject({});

/**
 * Register the lifecycle tools.
 *
 * Init and start/stop run through the fixed bootstrap against the pinned
 * installation; status only reads receipts and probes the recorded URLs.
 */
export function registerLifecycleTools(server: FastMCP, config: Configuration): void {
  server.tool(
    {
      name: 'workbench_init',
      title: 'Initialize the AstroPhotoFlow workbench',
      description:
        'Download the workbench version matching this MCP from the fixed release source, then create the runtime, dependencies and workspace. Safe to repeat: an existing workspace keeps its data. Returns immediately with an operation id when an install has to run; poll workbench_status until it is no longer installing.',
      input: workspaceInput,
    },
    () => guard(() => initialize(config)),
  );

  server.tool(
    {
      name: 'workbench_start',
      title: 'Start the AstroPhotoFlow workbench',
      description:
        'Start the installed workbench for this workspace, or reuse the running pair, and return the verified service and web URLs once both answer. Requires workbench_init.',
      input: workspaceInput,
    },
    () => guard(() => start(config)),
  );

  server.tool(
    {
      name: 'workbench_stop',
      title: 'Stop the AstroPhotoFlow workbench',
      description:
        'Stop the managed service and engine owned by this workspace after verifying process identity. Installation, configuration, database, assets and workflows are kept. A busy or unrecognised state is refused instead of force-killed.',
      input: workspaceInput,
    },
    () => guard(() => stop(config)),
  );

  server.tool(
    {
      name: 'workbench_status',
      title: 'Report installation and run status',
      description:
        'Report install progress (with operation id) and runtime state without starting anything. Probes the recorded URLs, so "ready" means the service and the native canvas both answered.',
      input: workspaceInput,
    },
    () => guard((): Promise<StatusReport> => getWorkbenchStatus(config)),
  );
}

async function initialize(config: Configuration): Promise<InitReport> {
  const installation = await tryReadInstallation(config);
  if (installation) {
    assertCompatibleInstallation(config, installation);
    const result = zInitResult.parse(await invokeController<unknown>(config, 'init'));
    return {
      status: result.status,
      version: result.version,
      workspace: result.workspace,
      database_revision: result.database_revision ?? null,
      operation_id: null,
      source: installation.source,
      publication: installation.publication,
      phase: 'installed',
      message: null,
      log: null,
    };
  }

  const operation = await readInstallOperation(config);
  if (operation && (operation.status === 'accepted' || operation.status === 'running')) {
    return reportFromOperation(operation);
  }

  const operationId = `init-${randomUUID().replace(/-/g, '')}`;
  return reportFromOperation(await launchInstaller(config, operationId));
}

async function start(config: Configuration): Promise<StartReport> {
  await readInstallation(config);
  const ready = zReadyResult.parse(await invokeController<unknown>(config, 'start'));
  const health = await probeService(ready.service_url);
  if (!health || typeof health.workspace !== 'string' || pathIdentity(health.workspace) !== pathIdentity(config.workspace)) {
    throw new LifecycleError(
      'WORKBENCH_UNVERIFIED',
      `The controller reported ready, but ${ready.service_url}/health did not answer for this workspace.`,
    );
  }
  if (!(await probeEnginePage(ready.web_url))) {
    throw new LifecycleError(
      'WORKBENCH_UNVERIFIED',
      `The controller reported ready, but ${ready.web_url} did not serve the native canvas.`,
    );
  }
  return {
    ...ready,
    database: typeof health.database === 'string' ? health.database : null,
    verified: true,
  };
}

async function stop(config: Configuration): Promise<StopReport> {
  const installation = await tryReadInstallation(config);
  if (installation) {
    assertCompatibleInstallation(config, installation);
  }
  const record = await readRuntimeRecord(config);
  if (!record) {
    return {
      status: 'not_running',
      mode: 'none',
      version: installation?.version ?? null,
      workspace: config.workspace,
      operation_id: null,
      service_stopped: false,
      engine_stopped: false,
      message: 'No managed process record exists for this workspace.',
      verified: true,
    };
  }

  const serviceAlive =
    record.phase === 'ready' && record.client !== null && (await probeService(record.client.service_url)) !== null;
  if (serviceAlive) {
    return stopThroughService(config, record.client!.service_url, record.client!.web_url);
  }
  return stopThroughController(config);
}

async function stopThroughService(
  config: Configuration,
  serviceUrl: string,
  webUrl: string,
): Promise<StopReport> {
  const api = await openWorkbenchApi(config);
  const { data, error } = await stopWorkbench({ client: api.client });
  if (error || !data) {
    throw serviceFailure(error, 'STOP_REJECTED', 'The workbench refused the stop request.');
  }
  const operationId = data.operation_id;
  const deadline = Date.now() + STOP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const record = await readRuntimeRecord(config);
    const health = await probeService(serviceUrl);
    const page = await probeEnginePage(webUrl);
    if (record === null && health === null && !page) {
      return {
        status: 'stopped',
        mode: 'service',
        version: api.runtime.installation.version,
        workspace: config.workspace,
        operation_id: operationId,
        service_stopped: true,
        engine_stopped: true,
        message: null,
        verified: true,
      };
    }
    await sleep(POLL_INTERVAL_MS);
  }
  throw new LifecycleError(
    'STOP_TIMEOUT',
    'The workbench accepted the stop request but its processes did not exit in time.',
    operationId,
  );
}

async function stopThroughController(config: Configuration): Promise<StopReport> {
  const installation = await readInstallation(config);
  const result = stopResultSchema.parse(await invokeController<unknown>(config, 'stop'));
  const record = await readRuntimeRecord(config);
  if (record !== null && record.phase !== 'stopped') {
    throw new LifecycleError(
      'STOP_INCOMPLETE',
      'The controller reported a stop, but a process record still exists for this workspace.',
      result.operation_id ?? undefined,
    );
  }
  return {
    status: result.status,
    mode: 'controller',
    version: result.version || installation.version,
    workspace: config.workspace,
    operation_id: result.operation_id ?? null,
    service_stopped: result.service_stopped,
    engine_stopped: result.engine_stopped,
    message: result.message ?? null,
    verified: true,
  };
}

function reportFromOperation(operation: InstallOperation): InitReport {
  return {
    status: operation.status,
    version: operation.version,
    workspace: operation.workspace,
    database_revision: null,
    operation_id: operation.operation_id,
    source: operation.source,
    publication: operation.publication,
    phase: operation.phase,
    message: operation.message ?? null,
    log: operation.log ?? null,
  };
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}
