# AGENTS.md

AstroPhotoFlow is a local astronomy imaging workbench. Read the [architecture](docs/architecture.md) before source changes and the [development reference](docs/development.md) before environment changes.

ComfyUI owns graphs, drafts, saving, undo and execution. FastAPI owns business data and operation receipts; canvas commands use the native bridge. Follow the [ownership proposal](.agents/notes/proposed/architecture/2026-11-14-native-canvas-and-service-receipts.md).

MCP uses FastMCP TS. Only its fixed lifecycle bootstrap may launch the workbench controller; business tools use HTTP. Database writes, retrieval and process ownership remain in the workbench; external agents do not execute whole graphs.

Follow [Windows delivery](docs/release.md): tags produce verified drafts; public publication is a separate manual workflow. Do not change repository visibility or publish packages as part of implementation.

Preserve original files, stable asset identity, dataset order and equipment snapshots. Query unknown operation outcomes before retrying.

Use the declared uv and pnpm environments. Follow the requested verification scope; do not run repository-wide static checks, builds or tests unless requested.

Documentation follows [docs/AGENTS.md](docs/AGENTS.md); decision records follow the [Agent Note rules](.agents/notes/README.md). Update bilingual pairs together.
