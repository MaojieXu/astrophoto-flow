import { LifecycleError, toolFailure } from './contracts.js';

/**
 * Run one tool body and turn expected failures into MCP tool errors.
 *
 * The transport only reports `isError` for a thrown exception, so a failure is
 * raised with its machine-readable envelope in the message: the text starts
 * with `{"error":{"code":…,"message":…}}` and the client sees `isError: true`.
 */
export async function guard<T>(work: () => Promise<T>): Promise<T> {
  try {
    return await work();
  } catch (error) {
    const failure =
      error instanceof LifecycleError
        ? error.toFailure()
        : toolFailure('INTERNAL_ERROR', error instanceof Error ? error.message : String(error));
    throw new Error(JSON.stringify({ error: failure.error }));
  }
}
