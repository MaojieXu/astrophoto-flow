# Agent Note: A canvas edit is an operation with a receipt

Status: rejected — Superseded by [native graph ownership and service receipts](../../proposed/architecture/2026-11-14-native-canvas-and-service-receipts.md).

English | [中文](2026-11-14-canvas-graphs-and-operation-receipts.zh.md)

## Problem

The old canvas identified a graph by a page id, a workflow id, a graph id, and a content token, and every edit carried an operation id. That was not ceremony: the engine can hold a live graph while the user edits, a second browser can save the same page, and a call can be interrupted after it started. Without a content token, a stale save overwrites a newer graph; without an operation id, an interrupted call is retried and produces a duplicate result. The new repository has a native canvas and an engine queue, but no contract for the saved graph, the edit, the call snapshot, or the receipt.

## Proposal

The service owns the saved graph and its receipt. The engine owns the live editing session and executes the graph. Every edit and every call is an operation with an id and a receipt.

### The canvas document

A canvas page has a `page_id`, a `workflow_id`, a `graph_id`, a revision, a content hash, and an ownership marker. A workflow can contain several pages; a page has one current graph. The graph JSON contains nodes, edges, positions, and parameter values; it does not contain file paths, tokens, or executable commands.

Saving a graph requires the base revision or content token. A save against a stale token returns `409 CONTENT_CONFLICT` and leaves the stored graph unchanged. The response returns the new token and a diff summary. There is no silent merge and no last-write-wins.

The service stores the saved graph; the engine's live graph is a working copy. On open, the service returns the saved graph and its token; the frontend loads it into the engine. On save, the service validates node types against the installed catalogs, writes the graph atomically, and records the ownership marker. The engine never writes the service database.

### Edits

An edit names the page, graph, base content token, and an `operation_id`, and contains one or more mutations: add a node, remove a node, connect ports, disconnect, set a parameter, move a node, or add a data source.

`canvas_add_data` is the only path that turns a library asset or dataset into a graph input. It records the asset id or dataset id, expands a dataset into its ordered members, and creates source nodes without copying files. The expansion is frozen at the moment of the operation; a later dataset edit does not rewrite the graph.

An edit is idempotent by `operation_id`. Repeating the same operation returns the original receipt. A stale content token returns `409`; a node type that is not installed returns a validation error naming the node; a parameter outside its schema returns a field path.

### Calls and snapshots

A call names the page, graph content token, the selected output nodes, and the caller's `request_id`. Before the engine is asked to run, the service writes a call record and a receipt in `pending` state. The record freezes:

- the graph content hash and revision;
- every input asset id and dataset id, with the dataset member order;
- every parameter value and the node type/version;
- the output node ids and the expected result kinds.

The service then resolves the input files. For a managed asset, it verifies the recorded hash and reads the library copy; if the hash changed, the call fails with `SOURCE_CHANGED` before the engine starts. If the call needs an isolated input directory, it pins the bytes there; a hardlink is not a pin because an in-place write would change both names.

The engine receives the graph and the resolved paths, not a database handle. Its prompt id is recorded on the call. A call that cannot be started is marked failed; it is not left pending.

### Tasks

A task has a `task_id`, the `request_id` and `operation_id` that created it, a state (`queued`, `running`, `succeeded`, `failed`, `cancelled`, `unknown`), per-node or per-item progress, timings, and errors.

`tasks_status` and `tasks_wait` return the state and progress. `tasks_wait` has a bounded timeout and returns the current state rather than blocking indefinitely. Cancellation is explicit and best-effort; a cancelled engine prompt may still produce a partial output, which the receipt records. Retry creates a new `operation_id` linked to the old one; it never reuses the old id, because the old outcome may be unknown.

An outcome is `unknown` when the service cannot confirm whether the engine started or finished. The caller must query by the same `operation_id`; starting a new call is a user decision, not an automatic retry.

### Receipts

A receipt records the operation id, kind (`canvas_edit`, `software_call`, `graph_call`, `import`, `export`), state, timings, the affected page/graph/node/asset ids, the input hash, the graph hash, the engine prompt id where applicable, and a list of errors with codes and field paths.

Receipts are append-only. A state change adds a new revision of the receipt rather than rewriting history. A receipt is readable after the engine stops; it is the record of what was attempted, not a live log.

## Alternatives considered

**Let the engine's database own the saved graph.** Rejected: the engine would become a second writer of registered graphs, and its schema is not the product contract. The service stores the graph; the engine holds a working copy.

**Autosave with last-write-wins.** Rejected: two browser tabs or an agent and a human would silently overwrite each other. The content token makes the conflict visible and recoverable.

**Fire-and-forget calls.** Rejected: an interrupted HTTP request would leave no record, and the caller would not know whether to retry. The pending receipt and the prompt id make the outcome queryable.

**Retry automatically on timeout.** Rejected: the first call may still be running. A new id would duplicate the result; the same id with a new attempt needs an explicit retry record.

**Store the graph only as a ComfyUI JSON file.** Rejected: a file has no revision, ownership, or receipt, and concurrent saves would corrupt it. The file can be an export, not the authority.

**Pin inputs by hardlink.** Rejected: an in-place write to the library copy would change the pinned name too. A copy or a reflink is a real pin; a hash check alone detects a change but does not prevent it.

## Acceptance criteria

- A saved graph has a page id, workflow id, graph id, revision, content token, and ownership marker.
- A stale graph save returns `409 CONTENT_CONFLICT` and does not change the stored graph.
- An edit is idempotent by `operation_id` and rejects an uninstalled node type or an out-of-schema parameter.
- Adding a dataset to the canvas records its ordered members and does not copy files.
- A call freezes the graph hash, input ids, member order, parameters, and node versions before the engine starts.
- A changed input hash fails the call with `SOURCE_CHANGED` before execution.
- A task reports `unknown` when the outcome cannot be confirmed, and the caller can query it by the same operation id.
- Retry uses a new operation id linked to the old one; it never reuses the old id.
- A receipt survives an engine restart and records the engine prompt id.
- The engine never writes the service database.

## Risks

- Two sources of graph state (service and engine) can drift. The content token and the save path must be the only way to persist, and the engine must reload after a save.
- A long-running call can outlive the browser session; the receipt and task must be durable before the engine is asked to run.
- Cancellation can leave a partial output. The receipt must say whether the output is complete, partial, or unknown.
- Pinning large datasets can double disk usage. The call record must report the pinned bytes and clean them after the receipt is closed.
- The engine queue can report a prompt id after the HTTP request returns; the service must reconcile by prompt id without creating a second call.
