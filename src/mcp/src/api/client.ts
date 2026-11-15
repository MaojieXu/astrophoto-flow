import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import type { Configuration } from '../config.js';
import { LifecycleError } from '../contracts.js';
import { createClient, createConfig, type Client } from '../generated/api/client/index.js';
import { requireReadyRuntime, type ReadyRuntime } from '../status.js';

const TOKEN_PATTERN = /^[0-9a-f]{64}$/;

/** A client bound to one verified running pair. */
export interface WorkbenchApi {
  client: Client;
  runtime: ReadyRuntime;
  token: string;
}

/**
 * Open an authenticated client for the verified pair.
 *
 * The URL comes from the controller's own record and the token from the
 * workspace file: neither is ever supplied by a tool caller.
 */
export async function openWorkbenchApi(config: Configuration): Promise<WorkbenchApi> {
  const runtime = await requireReadyRuntime(config);
  const token = await readServiceToken(config);
  const client = createClient(
    createConfig({
      baseUrl: runtime.serviceUrl,
      headers: { Authorization: `Bearer ${token}` },
      throwOnError: false,
    }),
  );
  return { client, runtime, token };
}

/** A client for a pair whose readiness was already verified by the caller. */
export async function clientForRuntime(runtime: ReadyRuntime, token: string): Promise<Client> {
  return createClient(
    createConfig({
      baseUrl: runtime.serviceUrl,
      headers: { Authorization: `Bearer ${token}` },
      throwOnError: false,
    }),
  );
}

async function readServiceToken(config: Configuration): Promise<string> {
  const path = join(config.workspace, 'data', 'service.token');
  let token: string;
  try {
    token = (await readFile(path, 'utf8')).trim();
  } catch (error) {
    if (typeof error === 'object' && error !== null && 'code' in error && (error as { code: string }).code === 'ENOENT') {
      throw new LifecycleError('WORKSPACE_NOT_INITIALIZED', 'The workspace has no service token; run workbench_init first.');
    }
    throw error;
  }
  if (!TOKEN_PATTERN.test(token)) {
    throw new LifecycleError('STATE_FILE_INVALID', 'The service token file is not a 32-byte hex token.');
  }
  return token;
}
