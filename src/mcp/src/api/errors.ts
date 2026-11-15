import { LifecycleError } from '../contracts.js';

interface EnvelopeBody {
  error?: { code?: unknown; message?: unknown; fields?: unknown };
}

/**
 * Translate a service error envelope into a tool-facing failure.
 *
 * The envelope is the only contract the MCP relies on; the HTTP status merely
 * decides whether a body is an error at all.
 */
export function serviceFailure(body: unknown, fallbackCode: string, fallbackMessage: string): LifecycleError {
  if (body && typeof body === 'object') {
    const detail = (body as EnvelopeBody).error;
    if (detail && typeof detail.code === 'string') {
      const message = typeof detail.message === 'string' ? detail.message : fallbackMessage;
      const fields = detail.fields && typeof detail.fields === 'object' ? JSON.stringify(detail.fields) : '';
      return new LifecycleError(detail.code, fields ? `${message} ${fields}` : message);
    }
  }
  return new LifecycleError(fallbackCode, fallbackMessage);
}
