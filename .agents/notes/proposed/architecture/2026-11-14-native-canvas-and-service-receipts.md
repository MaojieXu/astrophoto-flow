# Agent Note: Native graphs, service receipts

Status: proposed

English | [中文](2026-11-14-native-canvas-and-service-receipts.zh.md)

## Problem

The native workbench already owns graph files, autosave, drafts, undo, subgraphs and execution. Making FastAPI store another editable graph would require two save paths, conflict reconciliation and another revision history. The [service-owned graph proposal](../../rejected/feature/2026-11-14-canvas-graphs-and-operation-receipts.md) protects useful operation and input guarantees, but its graph ownership would duplicate the editor that the product is retaining.

The Windows reference checkout provides a narrower integration: FastAPI calls an authenticated aiohttp bridge through HTTPX, and the bridge sends commands over the native WebSocket to a selected browser page. The page applies native graph operations. This proposal adopts that boundary without treating the reference checkout as code already shipped here.

## Proposal

ComfyUI owns the editable graph and its persistence. FastAPI owns business data, command admission, input preparation and durable operation receipts. This proposal replaces service-owned graph storage while preserving the earlier proposal's input snapshots, idempotency and unknown-outcome rules.

### Dependencies and ownership

The workbench uses the declared Python 3.12 uv environment. FastAPI, Pydantic 2 and Uvicorn serve the business API; SQLAlchemy 2 accesses SQLite and Alembic manages its schema. These are business dependencies, not a restored engine asset database. HTTPX calls the retained aiohttp engine routes.

The frontend keeps Vue, TypeScript, Vite, Tailwind CSS and its existing component system. Pinia owns native and local UI state; TanStack Vue Query owns business-service data and cache. The private UI package takes host controls and emits events. It does not import native singletons. The native LiteGraph fork remains the canvas.

FastMCP TS exposes task tools and calls HTTP. The service OpenAPI document generates TypeScript clients and Zod validators for frontend and MCP consumers; neither consumer owns a second domain implementation.

### Canvas operations

An edit names `page_id`, `workflow_id`, `graph_id`, a content token and `operation_id`. The token describes the current native graph content; it is not a service-owned save revision. FastAPI validates business references and node parameters, records a pending receipt and forwards the command through HTTPX to the engine bridge. The bridge addresses the selected page over WebSocket.

The page checks its graph identity and content again immediately before editing. It applies node creation, deletion, parameter or connection changes through native graph APIs and native change events, preserving undo, drafts and save behavior. A stale token or offline page fails explicitly. There is no FastAPI graph-save endpoint or automatic reload from a service graph copy.

`canvas_add_data` resolves asset or dataset references into prepared source nodes. Dataset members and their order are frozen for the operation without copying the files. A later dataset edit does not rewrite the inserted inputs.

The same operation id and payload return the existing receipt. Reusing an id with a different payload is a conflict. A timeout, page disconnect or engine restart can leave the result unknown; query the same id before deciding on a new explicit attempt. A receipt must not claim success merely because a command was sent.

### Calls and evidence

Users submit whole graphs through the native prompt and queue path. External MCP agents inspect and edit graphs but do not execute whole graphs. The engine owns scheduling, progress, cancellation and native execution history.

Before an external software call starts, its business receipt freezes input asset and dataset ids, member order, parameters, node and bundle versions, output targets and a graph hash or snapshot where relevant. A snapshot is immutable evidence, not another editable graph. Record the native prompt id when available. A call that cannot start is failed rather than left pending.

The service verifies managed input hashes before scientific reads. Changed bytes fail with `SOURCE_CHANGED`. When an invocation needs fixed bytes, copy or reflink them into its run directory; hardlinks do not prevent in-place mutation. The engine receives resolved paths and snapshots, never a database handle.

Tasks retain bounded status and wait operations, progress, errors and explicit best-effort cancellation. Unknown is a real outcome. An explicit retry gets a new operation id linked to its predecessor. Partial outputs after cancellation remain identifiable.

Receipts persist operation kind, affected ids, hashes, timing, errors and native prompt ids independently of engine availability. State changes append receipt revisions. Receipt persistence does not duplicate native workflow storage or native execution history.

### Native workflow references

Bundle removal checks references in native saved workflows through a read-only adapter, plus active calls and nonterminal receipts. Any derived reference index is rebuildable and cannot save graphs. If native references cannot be checked, destructive bundle operations are refused. Reinstalling an exact pinned bundle can restore a native workflow's availability.

## Alternatives considered

**Store editable graphs in FastAPI.** Rejected: it duplicates native saving, drafts and undo, and requires conflict synchronization between two authorities. Durable operation receipts provide evidence without taking graph ownership.

**Replace the canvas framework.** Rejected: a second editor would require rebuilding nodes, subgraphs, widgets, conversion and native execution integration. The retained fork already provides those capabilities.

**Treat `/prompt` as a canvas-edit API.** Rejected: submitting an executable graph does not edit the user's open browser graph or participate in its undo history. Live edits require the page bridge.

**Retry a timed-out command automatically.** Rejected: the page may already have applied it. Query the existing operation id; a new attempt requires an explicit decision.

**Keep operation receipts only in the engine.** Rejected: an engine restart would erase the evidence needed to distinguish failure from an unknown result. The business service persists its receipts without copying the native execution ledger.

## Acceptance criteria

- Native graph saving, drafts and undo remain the only editable-graph persistence mechanism.
- A bridged edit appears on the selected page and can be undone natively; stale targets are refused.
- Repeated ids are idempotent, conflicting payloads fail, and interrupted results remain queryable as unknown.
- Dataset input order, software parameters and versions are frozen before calls; changed input hashes fail before execution.
- Receipts remain readable after an engine restart without becoming another graph store.
- Bundle reference checks use native saved workflows and fail closed when references cannot be verified.
- MCP exposes task tools over HTTP and provides no whole-graph execution tool.

## Risks

- Live editing requires a connected, editable browser page. Headless graph-file editing is not supplied by the bridge.
- Native save and undo semantics are tied to the pinned frontend; bridge changes must be checked against that version.
- A browser can disappear after applying an edit but before acknowledging it. Durable receipts preserve uncertainty but cannot invent an acknowledgment.
- Shared Python dependencies couple installation failures across the engine, business service and retrieval process. Isolated lockfile imports must be checked before replacing an environment.
- The new checkout still needs the service, bridge and MCP implementations. Dependency manifests and this proposal do not make them available.
