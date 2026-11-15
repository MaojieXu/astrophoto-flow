# Development environment

English | [中文](development.zh.md)

This reference covers dependency installation from the repository root. The MCP package builds a stdio lifecycle entry point; the business API and retrieval service require their own integration under the [architecture](architecture.md). Agent installation and public artifacts follow [Windows delivery](release.md).

## Runtimes and lockfiles

Use Python 3.12, Node `>=26.8.2 <27`, pnpm 11.28.5 and uv. The root `.node-version` selects Node 26.13.1; the backend `.python-version` selects Python 3.12. Keep dependency versions in manifests and resolve them into lockfiles.

The root pnpm workspace owns repository tooling and `src/mcp`. The frontend owns its separate pnpm workspace and lockfile, including the private UI package. The backend owns one uv project and lockfile for the image engine, business libraries and retrieval libraries. CPU PyTorch comes from the explicit CPU index in its manifest.

## Install dependencies

Run these commands from the repository root with the required tools on `PATH`:

```sh
uv sync --project src/workbench/backend --locked
pnpm install --frozen-lockfile --ignore-scripts
pnpm --dir src/workbench/frontend install --frozen-lockfile --ignore-scripts
```

Successful installation exits with code zero and creates the project environments. The pnpm commands suppress lifecycle scripts, so they do not install hooks or change Git configuration. They install dependencies only; native tools that require their own setup need that setup before use.

uv normally manages `src/workbench/backend/.venv`. For isolated verification, set `UV_PROJECT_ENVIRONMENT` to an absolute disposable directory before running the same sync command. Keep an existing environment until its replacement has been verified. Do not rely on inherited system packages to prove that the lockfile is complete.

LangGraph is a library dependency. Installing it does not build a reference corpus, select embedding or reranker models, or download their weights. The [knowledge proposal](../.agents/notes/proposed/feature/2026-11-14-agent-knowledge-base-rag.md) owns that workflow.

## Configuration and verification

The root `.env.example` describes translation-tool credentials, not workbench settings or model credentials. The [workspace proposal](../.agents/notes/proposed/feature/2026-11-14-workbench-settings-and-lifecycle.md) defines the separate workbench configuration. Keep tokens, databases, caches, model files and generated output out of version control.

Environment verification checks locked dependency resolution and imports in an isolated environment. Windows lockfile compatibility is not proof of Windows-native startup; verify platform-specific commands in a Windows shell before publishing them as working instructions.

Follow the task's requested verification scope. Do not add a test directory or run repository-wide static checks, builds or tests for an environment or prose update unless requested. Documentation edits still update the bilingual counterpart and re-record the exact pair under the [pairing contract](i18n/README.md).
