# Agent Note: The MCP surface is a task client, not a second backend

Status: proposed

English | [中文](2026-11-14-node-mcp-for-the-tool-surface.zh.md)

## Problem

The old MCP server exposed 126 tools generated from the same service catalog as the CLI. Its domain operations were already HTTP calls, but the process also read workspace configuration, the service token, and the process file, and it could start the workbench. That shape encouraged two mistakes: treating every HTTP route as an agent tool, and letting the MCP process become a second place that knows how to write the library. The new repository needs a small, task-shaped surface that helps an agent find images, prepare an import, assemble a graph, and read a receipt, without giving it a database handle, unrestricted process control, or a second implementation of the domain.

## Proposal

The MCP server uses `@prefecthq/fastmcp-ts` and Zod 4 in the Node package `src/mcp`, installed through the root pnpm workspace. Node's HTTP client calls the workbench APIs. FastMCP TS handles tool registration, validation and stdio; the package owns no database, SQLite file, retrieval engine or library write path. Its catalog is task-shaped, not one tool per route.

The [single-MCP installation and control proposal](../feature/2026-11-14-mcp-install-start-stop-workbench.md) owns lifecycle installation, startup and shutdown. It partially supersedes this note's former externally installed, start-only lifecycle and no-stop policy; the business catalog and HTTP ownership below remain active.

### Runtime and transport

The server runs on the same Node line as the frontend (`>=26.8.2 <27`), over stdio. It is started by the MCP client, not by the workbench. Connection arguments select the installation root and workspace and have Windows defaults. Connection does not require an existing installation receipt: init creates it, status distinguishes installation progress from runtime state, and start checks live identity after initialization. Business clients read the bearer token at the configured data directory's derived `service.token` path. MCP never opens the SQLite database.

The token is the only secret. It is never logged, never returned in a tool result, and never accepted as a tool argument.

### Tools

The surface is grouped by the task the agent is doing:

- **Find**: `assets_find`, `assets_get`, `datasets_find`, `datasets_get`, `calibration_find`, `nodes_find`, `nodes_get`. Results carry stable ids, compact facts, and a cursor; they do not dump whole tables.
- **Prepare an import**: `imports_inspect`, `imports_preflight`, `imports_submit`. Inspection and preflight are read-only and return a `review_token`; submit requires that token and a caller-supplied `request_id`.
- **Watch work**: `tasks_status`, `tasks_wait`. Both accept a task id or a request id and return per-stage progress, not a raw log.
- **Assemble a graph**: `canvas_get`, `canvas_add_data`, `canvas_edit`. They require the page id, workflow id, graph id, and content token; the edit tool also requires an `operation_id`. The [native page bridge](2026-11-14-native-canvas-and-service-receipts.md) applies edits and preserves native saving and undo; these tools do not submit whole graphs for execution.
- **Read the result**: `receipts_get`. A receipt is addressed by `operation_id` or `request_id` and includes the outcome, the affected ids, and the errors.
- **Workbench**: `workbench_init`, `workbench_start`, `workbench_stop`, `workbench_status`. Init downloads and initializes the matching workbench through a fixed installation worker; status observes its durable result and the runtime. Start starts or reuses the initialized workbench and returns its verified `web_url`. Stop terminates only verified owned workspace processes and preserves installation and data. The lifecycle proposal owns concurrency, busy-state refusal and unknown results.

There is no `restart`, arbitrary settings write, database query, arbitrary file read or shell tool. Init and stop are explicit, scoped lifecycle capabilities rather than general process or filesystem tools.

### Contract and errors

The FastAPI service's OpenAPI document is the schema source. A checked-in snapshot and `@hey-api/openapi-ts` produce TypeScript clients and Zod validators for separate frontend and MCP consumers; MCP never imports the UI package. A contract test fails when the snapshot and the running service disagree. Hand-written Zod schemas are allowed only where the generator cannot express a constraint, and those schemas still participate in the drift check.

Every business tool calls the HTTP API with a request id. A service error becomes a structured tool error with the service's code, message, field paths, and request id. A stopped service returns `WORKBENCH_NOT_RUNNING` with a hint to call `workbench_start`; it does not auto-start. A timeout returns `TRANSPORT_TIMEOUT`; a connection failure returns `SERVICE_UNAVAILABLE`. Unknown results are queried by the same `operation_id` or `request_id`, never retried with a new one.

### What stays local

Only the fixed lifecycle bootstrap adapter may launch the packaged PowerShell installation worker or invoke the installed uv executable with a fixed controller action. Init must work before Python or the business service exists. The adapter takes no executable, script, URL or PID from tool arguments and imports no backend module. The Python controller owns process identity, concurrency, readiness and shutdown; business tools use HTTP. Installation may create a new workspace configuration, but it must preserve existing configuration and data. This is the proposed expansion of the [current delivery implementation](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.md), not a claim that its installer or start adapter already provides init and stop.

The local reference corpus is a separate read-only module, not another domain path; [its note](../feature/2026-11-14-agent-knowledge-base-rag.md) specifies how the agent retrieves and cites it.

### CLI

The CLI remains a human and operations surface. It calls the same HTTP API and the same controller; it is not generated one-command-per-tool, and it is not the source of the MCP catalog. A script that needs the task workflow can use the CLI, but the MCP tool list is the agent contract.

## Alternatives considered

**Keep the Python MCP server and prune the catalog.** Rejected: it would keep a second Python process with its own dependency set and its own copy of the config/token logic. The frontend already runs Node, and a small HTTP client is cheaper to keep honest.

**Expose every service route as a tool.** Rejected: 60+ routes produce a catalog an agent cannot choose from, and many routes are UI plumbing (paging tokens, preview leases, directory pickers). Task tools compose those routes behind one intent.

**Let MCP read SQLite directly.** Rejected: it would bypass revision checks, value provenance, and the single-writer rule, and a schema change would break the agent silently. HTTP is the only domain path.

**Auto-start the workbench on the first business call.** Rejected: a read-only query should not launch two processes, and a start failure in the middle of a tool call is hard to explain. `workbench_start` is explicit.

**Expose stop and restart for symmetry.** The earlier proposal rejected both to avoid an agent shutting down a human's workbench. The explicit init/start/stop requirement now supersedes the no-stop restriction through the [scoped lifecycle proposal](../feature/2026-11-14-mcp-install-start-stop-workbench.md); busy-state and process-identity checks retain the protection against unrelated shutdowns. Restart remains outside the MCP catalog.

**Generate a CLI command per tool, as before.** Rejected: it duplicates the catalog, and the generated commands were a thin wrapper over the same HTTP calls. The CLI can expose the few operations humans actually script.

## Acceptance criteria

- The MCP server opens no SQLite database and contains no library write path.
- The tool list is task-shaped, includes the scoped init/start/stop/status lifecycle and contains no restart, arbitrary settings-write, arbitrary-file or shell tool.
- MCP connects before installation; init downloads and initializes one workbench without installing a second MCP, and status distinguishes acceptance from completion.
- Business tools return `WORKBENCH_NOT_RUNNING` when the service is stopped; `workbench_start` is the only auto-start path.
- The token is read from the derived path, never logged, and never accepted as a tool argument.
- A contract test fails when the checked-in schema snapshot and the running service disagree.
- Errors preserve the service code, message, field paths, and request id.
- Unknown results are queried by the same operation or request id, not retried with a new one.
- Stop preserves the workspace and leaves MCP callable; another start can return a verified webpage.
- `workbench_status` works while the service is stopped and reports managed, unconfirmed, exited, and not-managed states.
- The server runs on the frontend's Node line over stdio.

## Risks

- Contract drift is the main failure mode. A snapshot test catches schema changes, but it must run in the same gate as the service tests, or the MCP will lag silently.
- Starting the workbench from an MCP tool can race with a human start. The controller's identity and readiness checks must make the second start a reuse or a clear refusal, not a duplicate.
- A token file with wrong permissions is a security bug. The server should refuse to read a token that is not owner-only rather than proceed.
- Task tools can still grow into route proxies. Each new tool needs a named task and acceptance criteria, not a one-to-one mapping to an endpoint.
- Node 26 is newer than many MCP clients assume; the package must declare the engine and fail with a clear message on an older runtime.
