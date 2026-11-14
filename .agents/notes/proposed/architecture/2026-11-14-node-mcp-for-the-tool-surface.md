# Agent Note: The MCP surface is a task client, not a second backend

Status: proposed

English | [中文](2026-11-14-node-mcp-for-the-tool-surface.zh.md)

## Problem

The old MCP server exposed 126 tools generated from the same service catalog as the CLI. Its domain operations were already HTTP calls, but the process also read workspace configuration, the service token, and the process file, and it could start the workbench. That shape encouraged two mistakes: treating every HTTP route as an agent tool, and letting the MCP process become a second place that knows how to write the library. The new repository needs a small, task-shaped surface that helps an agent find images, prepare an import, assemble a graph, and read a receipt, without giving it a database handle, a stop button, or a second implementation of the domain.

## Proposal

The MCP server is a Node process that speaks HTTP to the workbench service. It owns no database, no SQLite file, and no library write path. It exposes roughly fifteen task tools, not one tool per route.

### Runtime and transport

The server runs on the same Node line as the frontend (`>=26.8.2 <27`), over stdio. It is started by the MCP client, not by the workbench. It reads two local things: the workspace path (from its own configuration or an environment variable) and the bearer token at the derived `data/service.token` path. It reads `run/processes.json` to learn the actual service and engine ports for the current run; it never opens the SQLite database.

The token is the only secret. It is never logged, never returned in a tool result, and never accepted as a tool argument.

### Tools

The surface is grouped by the task the agent is doing:

- **Find**: `assets_find`, `assets_get`, `datasets_find`, `datasets_get`, `calibration_find`, `nodes_find`, `nodes_get`. Results carry stable ids, compact facts, and a cursor; they do not dump whole tables.
- **Prepare an import**: `imports_inspect`, `imports_preflight`, `imports_submit`. Inspection and preflight are read-only and return a `review_token`; submit requires that token and a caller-supplied `request_id`.
- **Watch work**: `tasks_status`, `tasks_wait`. Both accept a task id or a request id and return per-stage progress, not a raw log.
- **Assemble a graph**: `canvas_get`, `canvas_add_data`, `canvas_edit`. They require the page id, workflow id, graph id, and content token; the edit tool also requires an `operation_id`.
- **Read the result**: `receipts_get`. A receipt is addressed by `operation_id` or `request_id` and includes the outcome, the affected ids, and the errors.
- **Workbench**: `workbench_status`, `workbench_start`. Status works while the service is stopped. Start prepares and starts the workbench; it is the only lifecycle action exposed.

There is no `stop`, no `restart`, no settings write, no database query, no arbitrary file read, and no shell tool.

### Contract and errors

The service's OpenAPI document is the schema source. A checked-in snapshot and a generator produce the MCP validators; a contract test fails when the snapshot and the running service disagree. Hand-written Zod schemas are allowed only where the generator cannot express a constraint, and those schemas still participate in the drift check.

Every business tool calls the HTTP API with a request id. A service error becomes a structured tool error with the service's code, message, field paths, and request id. A stopped service returns `WORKBENCH_NOT_RUNNING` with a hint to call `workbench_start`; it does not auto-start. A timeout returns `TRANSPORT_TIMEOUT`; a connection failure returns `SERVICE_UNAVAILABLE`. Unknown results are queried by the same `operation_id` or `request_id`, never retried with a new one.

### What stays local

The MCP process may read the config to find the workspace and may read the process file to find the actual ports. It may start the workbench through the local controller. It may not write the config, stop a process, restart a process, or edit the library directly. If a future tool needs a local action, it goes through the service or the controller, not through a private code path.

The local reference corpus is a separate read-only module, not another domain path; [its note](../feature/2026-11-14-agent-knowledge-base-rag.md) specifies how the agent retrieves and cites it.

### CLI

The CLI remains a human and operations surface. It calls the same HTTP API and the same controller; it is not generated one-command-per-tool, and it is not the source of the MCP catalog. A script that needs the task workflow can use the CLI, but the MCP tool list is the agent contract.

## Alternatives considered

**Keep the Python MCP server and prune the catalog.** Rejected: it would keep a second Python process with its own dependency set and its own copy of the config/token logic. The frontend already runs Node, and a small HTTP client is cheaper to keep honest.

**Expose every service route as a tool.** Rejected: 60+ routes produce a catalog an agent cannot choose from, and many routes are UI plumbing (paging tokens, preview leases, directory pickers). Task tools compose those routes behind one intent.

**Let MCP read SQLite directly.** Rejected: it would bypass revision checks, value provenance, and the single-writer rule, and a schema change would break the agent silently. HTTP is the only domain path.

**Auto-start the workbench on the first business call.** Rejected: a read-only query should not launch two processes, and a start failure in the middle of a tool call is hard to explain. `workbench_start` is explicit.

**Expose stop and restart for symmetry.** Rejected: an external agent should not take down a workbench a human is using. Stop and restart stay on the CLI and the web surface.

**Generate a CLI command per tool, as before.** Rejected: it duplicates the catalog, and the generated commands were a thin wrapper over the same HTTP calls. The CLI can expose the few operations humans actually script.

## Acceptance criteria

- The MCP server opens no SQLite database and contains no library write path.
- The tool list is task-shaped and contains no stop, restart, settings-write, arbitrary-file, or shell tool.
- Business tools return `WORKBENCH_NOT_RUNNING` when the service is stopped; `workbench_start` is the only auto-start path.
- The token is read from the derived path, never logged, and never accepted as a tool argument.
- A contract test fails when the checked-in schema snapshot and the running service disagree.
- Errors preserve the service code, message, field paths, and request id.
- Unknown results are queried by the same operation or request id, not retried with a new one.
- `workbench_status` works while the service is stopped and reports managed, unconfirmed, exited, and not-managed states.
- The server runs on the frontend's Node line over stdio.

## Risks

- Contract drift is the main failure mode. A snapshot test catches schema changes, but it must run in the same gate as the service tests, or the MCP will lag silently.
- Starting the workbench from an MCP tool can race with a human start. The controller's identity and readiness checks must make the second start a reuse or a clear refusal, not a duplicate.
- A token file with wrong permissions is a security bug. The server should refuse to read a token that is not owner-only rather than proceed.
- Task tools can still grow into route proxies. Each new tool needs a named task and acceptance criteria, not a one-to-one mapping to an endpoint.
- Node 26 is newer than many MCP clients assume; the package must declare the engine and fail with a clear message on an older runtime.
