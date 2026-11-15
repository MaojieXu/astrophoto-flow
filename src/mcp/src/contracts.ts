import { z } from 'zod';

// Bootstrap contracts: installation receipts and install-operation progress.
// Online API shapes (ready state, nodes, errors) come from the generated client.

export const pathSchema = z.string().min(1);
export const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);
export const commitSchema = z.string().regex(/^[0-9a-f]{40}$/);

export const PUBLICATION = z.enum(['published', 'candidate']);
export const SOURCE = z.enum(['release', 'candidate']);

export const INSTALL_PHASES = z.enum([
  'accepted',
  'preparing',
  'downloading',
  'verifying',
  'extracting',
  'runtime',
  'dependencies',
  'workspace',
  'installed',
  'failed',
]);

export const INSTALL_STATUSES = z.enum(['accepted', 'running', 'succeeded', 'failed', 'unknown']);

/** Written by the installer once, at the end of a successful installation. */
export const installationSchema = z.strictObject({
  schema_version: z.literal(1),
  version: z.string().min(1),
  commit: commitSchema.nullable(),
  install_root: pathSchema,
  workspace: pathSchema,
  source: SOURCE,
  publication: PUBLICATION,
  installed_at: z.string().min(1),
  workbench_sha256: sha256Schema,
  runtime: z.strictObject({
    uv: z.string().min(1),
    python: z.string().min(1),
  }),
});

export type InstallationRecord = z.infer<typeof installationSchema>;

/** The persistent install task the installer rewrites as it makes progress. */
export const installOperationSchema = z.strictObject({
  schema_version: z.literal(1),
  operation_id: z.string().min(1).max(64),
  action: z.literal('init'),
  status: INSTALL_STATUSES,
  phase: INSTALL_PHASES,
  version: z.string().min(1),
  install_root: pathSchema,
  workspace: pathSchema,
  source: SOURCE,
  publication: PUBLICATION,
  started_at: z.string().min(1),
  updated_at: z.string().min(1),
  message: z.string().nullable().optional(),
  log: pathSchema.nullable().optional(),
});

export type InstallOperation = z.infer<typeof installOperationSchema>;

export const processIdentitySchema = z.strictObject({
  pid: z.number().int().positive(),
  create_time: z.number(),
  exe: z.string(),
  cmdline: z.array(z.string()),
  cwd: z.string(),
});

export const readySnapshotSchema = z.strictObject({
  status: z.literal('ready'),
  version: z.string().min(1),
  workspace: pathSchema,
  service_url: z.string().min(1),
  web_url: z.string().min(1),
  reused: z.boolean(),
});

/** The controller's process record; the MCP only reads it, never writes it. */
export const processRecordSchema = z.strictObject({
  schema_version: z.literal(1),
  workspace: pathSchema,
  version: z.string().min(1),
  operation_id: z.string().min(1),
  phase: z.enum(['starting', 'stopping', 'ready', 'stopped', 'failed', 'unknown']),
  started_at: z.string().min(1),
  service: processIdentitySchema,
  engine: processIdentitySchema,
  client: readySnapshotSchema.nullable(),
  message: z.string().nullable(),
});

export type ProcessRecord = z.infer<typeof processRecordSchema>;

/** A distinguishable tool failure: callers branch on `code`, never on prose. */
export interface ToolFailure {
  error: {
    code: string;
    message: string;
    operation_id?: string;
  };
}

export function toolFailure(code: string, message: string, operationId?: string): ToolFailure {
  return { error: operationId ? { code, message, operation_id: operationId } : { code, message } };
}

export class LifecycleError extends Error {
  readonly code: string;
  readonly operationId: string | undefined;

  constructor(code: string, message: string, operationId?: string) {
    super(message);
    this.name = 'LifecycleError';
    this.code = code;
    this.operationId = operationId;
  }

  toFailure(): ToolFailure & { isError: true } {
    return { ...toolFailure(this.code, this.message, this.operationId), isError: true };
  }
}

/** The controller's stop outcome; also returned by the service's async stop worker. */
export const stopResultSchema = z.strictObject({
  status: z.enum(['stopped', 'not_running']),
  version: z.string().min(1),
  workspace: pathSchema,
  operation_id: z.string().nullable().optional(),
  service_stopped: z.boolean(),
  engine_stopped: z.boolean(),
  message: z.string().nullable().optional(),
});

export type StopResult = z.infer<typeof stopResultSchema>;
