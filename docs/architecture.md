# Architecture

English | [中文](architecture.zh.md)

The backend dependency manifest combines the image engine, business API and retrieval libraries in one uv project. The frontend and MCP have separate pnpm workspaces. MCP provides Windows lifecycle tools; business-service and retrieval integration is defined by the [runtime proposal](../.agents/notes/proposed/architecture/2026-11-13-repository-and-runtime-shape.md).

## Dependency owners

| Owner | Declared stack | Responsibility |
|---|---|---|
| `src/workbench/backend/` | Python 3.12, uv, CPU PyTorch, aiohttp | Image nodes and native graph execution |
| Backend business dependencies | FastAPI, Pydantic 2, Uvicorn, SQLAlchemy 2, Alembic, SQLite | Business HTTP API, validation, persistence and migrations |
| Backend retrieval dependencies | LangGraph, NumPy | Local retrieval workflow; corpus and indexes are separate from image assets |
| `src/workbench/frontend/` | Vue 3, TypeScript, Vite, Tailwind CSS 4, PrimeVue | Native workbench and host component system |
| Private UI package | TanStack Vue Query, Zod 4, OpenAPI generator | Service data, validation and generated clients |
| `src/mcp/` | Node 26, FastMCP TS, Zod 4 | Task tools over stdio and HTTP clients |

The [development reference](development.md) owns installation commands and environment locations. Manifests and lockfiles own exact dependency versions.

## Native canvas and business API

ComfyUI owns editable graphs, workflow files, drafts, saving, undo, subgraphs, the execution queue, progress and cancellation. Pinia holds native and local UI state; Vue Query holds service data and its cache. The private UI package receives host controls and emits events instead of importing native singletons.

The FastAPI boundary owns assets, datasets, equipment, calibration, business tasks and operation receipts. SQLAlchemy accesses its SQLite database and Alembic manages schema migrations. Scientific files live outside the database. The engine has no second asset ledger.

Canvas commands follow the [native-canvas proposal](../.agents/notes/proposed/architecture/2026-11-14-native-canvas-and-service-receipts.md): the business API validates and prepares an operation, HTTPX calls an authenticated aiohttp bridge, and the bridge sends a WebSocket command to the selected browser page. That page uses native graph operations and returns a receipt. Whole-graph execution remains on the native prompt and queue path.

## MCP and knowledge

The [MCP proposal](../.agents/notes/proposed/architecture/2026-11-14-node-mcp-for-the-tool-surface.md) keeps FastMCP TS responsible for tool registration and protocol handling. Business tools call HTTP APIs. The service OpenAPI document is the source for generated TypeScript clients and Zod validators; MCP does not import the UI package.

The fixed lifecycle bootstrap is the sole process-creation exception. It invokes the installed controller, then verifies the service identity and HTML endpoint before returning a local URL. The [Windows delivery reference](release.md) owns installation, the controller contract and the two-stage publication flow.

The [knowledge proposal](../.agents/notes/proposed/feature/2026-11-14-agent-knowledge-base-rag.md) places retrieval code inside the workbench backend. The controller starts a separate Python retrieval process using the backend environment. MCP exposes search and fetch tools; retrieval returns cited passages for the external agent to use. Corpus, indexes and model caches have their own data directory.

## Boundaries

The business service is the only writer of its domain database. Native graph files remain under ComfyUI ownership; an input or graph snapshot in a receipt is evidence, not another editable graph. Unknown outcomes are queried by their existing operation id before any explicit retry.

The [module-boundary rules](../scripts/verify-module-boundaries.ts) constrain source imports. The [Agent Notes](../.agents/notes/README.md) own decision rationale and unbuilt behavior; this reference does not turn those proposals into runnable interfaces.
