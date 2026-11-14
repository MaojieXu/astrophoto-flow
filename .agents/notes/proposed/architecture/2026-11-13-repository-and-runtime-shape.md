# Agent Note: One repository, one runtime environment

Status: proposed

English | [中文](2026-11-13-repository-and-runtime-shape.zh.md)

## Problem

The previous layout split the product three ways: a Python service in `src/astrophotoflow`, a full ComfyUI copy under `engine/`, and a full ComfyUI_frontend copy under `frontend/`, wired by build scripts and a second runtime virtualenv. Every consequence of that split was maintenance: a wheel that carried an engine archive, a console script, a bootstrap tool that owned a runtime fingerprint, a generated CLI, and two environments to keep in step. For a product that one person runs on one machine, the structure should answer two questions on sight: which code is mine, and which environment installs it.

## Proposal

Three directories under `src/`, one environment each:

```text
src/workbench/backend/     # uv environment
    main.py, comfy/, nodes.py …     ComfyUI source
    astrophotoflow/                 our service package, importable without installing
    custom_nodes/astrophotoflow/    one registration file that points at the package
    web/                            frontend build output, git-ignored
    pyproject.toml, uv.lock, tests/
src/workbench/frontend/    # pnpm environment
    upstream source plus src/platform/astrophotoflow/
src/mcp/                   # pnpm environment, Node, only talks HTTP
```

Our package sits inside the engine tree and is never installed: the engine runs from `backend/`, so `import astrophotoflow` resolves by directory position, and the service starts with `python -m astrophotoflow`. No wheel, no console script, no runtime fingerprint.

The directory keeps the name `workbench`; the product name stays AstroPhotoFlow, so a directory rename never touches what the product is called.

The engine and our HTTP service stay two processes in one environment. The engine owns graphs, queue, progress, and cancellation; our service owns assets, datasets, receipts, and the ownership rules for canvas edits. Keeping them apart means a crashed engine still leaves the workspace API able to answer questions about receipts.

Distribution is out of scope by [decision](../simplification/2026-11-14-no-distribution-engineering.md); the frontend fork is [frozen](../simplification/2026-11-14-freeze-the-frontend-fork.md); the tool surface is [a client](2026-11-14-node-mcp-for-the-tool-surface.md).

## Data ownership

`backend/astrophotoflow/interfaces/http` is the only entry point that writes registered assets, datasets, graphs, or receipts. Two engine behaviours must be made explicit rather than assumed away:

- ComfyUI ships its own upload and asset routes. They own temporary inputs and outputs; they must not become a second registration path, and the native save action has to pass through our ownership and revision rules.
- A call snapshot records file content, not a path. If the original is replaced between planning and execution, the recorded input no longer matches what runs; the snapshot either pins the bytes into a run directory or the call aborts on a changed digest.
- A receipt is persisted before the external call starts, so a restart still leaves an identifier to query.

## Alternatives considered

**Wheel with two runtime virtualenvs.** This was the previous design: a prepared runtime environment with its own fingerprint file, a development environment without torch. Rejected because both environments consume the same dependency set, so the second one buys only a faster `uv sync` at the cost of a fingerprint, a prepare step, and a class of "which environment am I in" failures.

**A separate `upstream/` tree for the two forks.** Rejected: a directory boundary does not change what we are allowed to edit, and it lengthens every packaging path. The distinction that matters, "is this our code", is answered by the package layout, not by a parent folder.

**One process: register our routes on the engine's aiohttp server.** Technically available once custom nodes load, and it removes a port and a startup order. Rejected for the first version because it couples our availability to the engine's, so a crashed engine also loses the receipt endpoints.

**Pull upstream through submodules or subtrees.** Rejected for now: neither fork is tracking upstream, so the machinery would exist without a user. A pinned commit plus a recorded modification list is enough to reconstruct either tree.

## Acceptance criteria

- A fresh clone, one `uv sync`, one frontend build, and `python main.py` produce a page that completes a real Siril call.
- `uv run pytest` and `uv run python main.py` both run from `backend/` with the same import paths.
- `import astrophotoflow` succeeds without any install step.
- No directory mixes our files with upstream files except `custom_nodes/astrophotoflow/`.

## Risks

- The engine reads `requirements.txt` at runtime to report package versions. Deleting it in favour of `pyproject.toml` alone would make those reads return `None` and some callers still call `.get()` on the result, so the file stays as a compatibility input until every reader migrates.
- torch lives in the development environment, so the first install is minutes and gigabytes rather than seconds.
- Two processes share one environment, so a dependency conflict is still a single-point failure for both.
- The engine's own upload routes can quietly become a second data path unless the boundary above is enforced by a test.
