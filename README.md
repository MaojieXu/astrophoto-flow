# AstroPhotoFlow

English | [中文](README.zh.md)

AstroPhotoFlow is a local astronomy imaging workbench driven from the browser: it keeps image assets and datasets, registers real astronomy software as canvas nodes, and lets you assemble, run, inspect, and save results on a native canvas. People work in the web app, scripts drive the CLI, and external agents use the platform MCP server, which orchestrates and queries but never executes a graph.

The repository contains the image-only ComfyUI engine and frontend forks, dependency configurations, MCP lifecycle tools and Windows delivery scripts. Business-service and retrieval integration are specified by the active proposals. Release verification requires their real entry points before it accepts an installable workbench.

## What is here

- [Architecture](docs/architecture.md) — dependency owners, native canvas ownership and communication boundaries.
- [Development](docs/development.md) — runtimes, dependency installation and environment isolation.
- [Windows delivery](docs/release.md) — agent installation, MCP startup and reviewed publication.
- [Agent Notes](.agents/notes/README.md) — proposals, implemented decisions and frozen history.
- [Documentation rules](docs/AGENTS.md) — document placement and bilingual maintenance.

## Dependencies

Use Node 26 and pnpm 11.28.5 from the repository root:

```sh
pnpm install --frozen-lockfile --ignore-scripts
```

The [development reference](docs/development.md) covers the separate frontend workspace and the uv-managed Python environment. Verification follows the scope requested for the task.
