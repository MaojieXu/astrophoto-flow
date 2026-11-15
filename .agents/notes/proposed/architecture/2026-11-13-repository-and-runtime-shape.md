# Agent Note: One repository, one runtime environment

Status: proposed

English | [中文](2026-11-13-repository-and-runtime-shape.zh.md)

## Problem

The previous layout split the product three ways: a Python service in `src/astrophotoflow`, a full ComfyUI copy under `engine/`, and a full ComfyUI_frontend copy under `frontend/`, wired by build scripts and a second runtime virtualenv. Every consequence of that split was maintenance: a wheel that carried an engine archive, a console script, a bootstrap tool that owned a runtime fingerprint, a generated CLI, and two environments to keep in step. For a product that one person runs on one machine, the structure should answer two questions on sight: which code is mine, and which environment installs it.

## Proposal

Three runtime directories under `src/`: one backend uv environment, a frontend pnpm workspace, and an MCP package in the root pnpm workspace:

```text
src/workbench/backend/     # uv environment
    main.py, comfy/, nodes.py …     ComfyUI source
    astrophotoflow/                 our service package, importable without installing
    custom_nodes/astrophotoflow/    one registration file that points at the package
    web/                            frontend build output, git-ignored
    pyproject.toml, uv.lock
src/workbench/frontend/    # pnpm environment
    upstream source plus src/platform/astrophotoflow/
    packages/astrophotoflow-ui/     private business UI package
src/mcp/                   # root pnpm workspace, Node, HTTP plus fixed lifecycle actions
```

Our package sits inside the engine tree and is never installed: the engine runs from `backend/`, so `import astrophotoflow` resolves by directory position, and the service starts with `python -m astrophotoflow`. No wheel, no console script, no runtime fingerprint.

The directory keeps the name `workbench`; the product name stays AstroPhotoFlow, so a directory rename never touches what the product is called.

The engine and our FastAPI service are separate processes in one Python 3.12 environment. ComfyUI owns graph files, drafts, saving, undo, queue, progress and cancellation; the service owns assets, datasets, command admission and receipts. HTTPX calls the engine's aiohttp bridge and WebSocket delivers edits to the native page, following the [native-canvas proposal](2026-11-14-native-canvas-and-service-receipts.md). An engine crash does not take the receipt API down with it.

The [knowledge process](../feature/2026-11-14-agent-knowledge-base-rag.md) belongs to the same uv environment but remains a separate capability outside the first lifecycle-and-node-query implementation. Its code belongs under `backend/astrophotoflow/knowledge/`, while its corpus, indexes and model caches have a separate data directory. The controller owns Python process management. MCP business tools remain HTTP clients; its fixed lifecycle adapter follows the [installation and control proposal](../feature/2026-11-14-mcp-install-start-stop-workbench.md). Node 26 and pnpm 11.28.5 serve both Node workspaces. Declared dependencies and installation are described in the [development reference](../../../../docs/development.md).

The [agent delivery record](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.md) describes the current Windows archive and installer without a Python wheel or embedded virtualenv. The [single-MCP proposal](../feature/2026-11-14-mcp-install-start-stop-workbench.md) replaces its intended workbench-before-MCP installation order: the host provides Node and connects MCP first, init installs the workbench, and start/stop invoke its controller. The frontend fork remains [frozen](../simplification/2026-11-14-freeze-the-frontend-fork.md); business tools remain [HTTP clients](2026-11-14-node-mcp-for-the-tool-surface.md).

## Data ownership

`backend/astrophotoflow/interfaces/http` is the only entry point that writes registered assets, datasets or business receipts. Native graph persistence stays with ComfyUI. These boundaries must be explicit:

- ComfyUI upload routes own temporary inputs and outputs, not library registration. Graph saving and undo stay native; registering a scientific output goes through the business API.
- A call snapshot records file content, not a path. If the original is replaced between planning and execution, the recorded input no longer matches what runs; the snapshot either pins the bytes into a run directory or the call aborts on a changed digest.
- A receipt is persisted before the external call starts, so a restart still leaves an identifier to query.

## Alternatives considered

**Wheel with two runtime virtualenvs.** This was the previous design: a prepared runtime environment with its own fingerprint file, a development environment without torch. Rejected because both environments consume the same dependency set, so the second one buys only a faster `uv sync` at the cost of a fingerprint, a prepare step, and a class of "which environment am I in" failures.

**A separate `upstream/` tree for the two forks.** Rejected: a directory boundary does not change what we are allowed to edit, and it lengthens every packaging path. The distinction that matters, "is this our code", is answered by the package layout, not by a parent folder.

**One process: register our routes on the engine's aiohttp server.** Technically available once custom nodes load, and it removes a port and a startup order. Rejected for the first version because it couples our availability to the engine's, so a crashed engine also loses the receipt endpoints.

**Pull upstream through submodules or subtrees.** Rejected for now: neither fork is tracking upstream, so the machinery would exist without a user. A pinned commit plus a recorded modification list is enough to reconstruct either tree.

## Acceptance criteria

- A fresh clone with the locked Python and Node dependencies lets the controller start the service and engine and complete a real Siril call from the native page.
- `uv run pytest` and `uv run python main.py` both run from `backend/` with the same import paths.
- `import astrophotoflow` succeeds without any install step.
- Product code stays under its service package, private UI package and host integration directory, except for the single custom-node registration file.

## Risks

- The engine reads `requirements.txt` at runtime to report package versions. Deleting it in favour of `pyproject.toml` alone would make those reads return `None` and some callers still call `.get()` on the result, so the file stays as a compatibility input until every reader migrates.
- torch lives in the development environment, so the first install is minutes and gigabytes rather than seconds.
- Engine, business service and retrieval process share one environment, so dependency conflicts affect all three.
- The engine's own upload routes can quietly become a second data path unless the boundary above is enforced by a test.
