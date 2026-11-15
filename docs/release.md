# Windows delivery

English | [中文](release.zh.md)

The Windows x64 delivery flow packages the workbench for an agent to install, then exposes startup and status through the npm MCP package. GitHub Releases carries workstation assets; npm carries `@xu016/astrophoto-flow`. Source and runtime prerequisites are enforced by the [release assembler](../scripts/release/package.py).

## Version and assets

The root `package.json` owns the product version. `vX.Y.Z-dev.N` tags produce development releases and npm's `next` tag; stable versions use `latest`. Fork versions are independent. The MCP build records the product version inside its output, and the release packer supplies public npm metadata in a staging directory. The source MCP package remains private to prevent publishing it directly.

Each draft contains a Windows ZIP, matching source archive, `install.ps1`, MCP tarball, `release-manifest.json`, `SHA256SUMS` and a Windows verification report. The ZIP contains backend sources, locked dependencies, the built frontend and licenses. Virtualenvs, user files, model weights and frontend build dependencies are not included. Runtime downloads are pinned in [runtime.json](../scripts/release/runtime.json).

## Local entry points

From the repository root:

```sh
pnpm release:preflight
pnpm --filter @xu016/astrophoto-flow build
python scripts/release/package.py --mcp-only --output .artifacts/mcp-review
```

Preflight rejects missing controller files, mismatched versions and a dirty checkout. The MCP-only command produces a review tarball, not a validated workstation release. The Windows build entry is `scripts/release/build.ps1`; it requires a clean tagged checkout and builds the frontend and MCP before assembling assets. Its counterpart `scripts/release/verify.ps1` installs into a temporary workspace and produces the report required for publication.

## Agent installation and startup

The installer accepts `-Version`, `-InstallRoot` and `-Workspace`. It defaults to `%LOCALAPPDATA%\AstroPhotoFlow`, rejects nonempty directories it does not own, uses private version/runtime/cache directories and installs Python dependencies with uv. The workspace is outside replaceable version directories. Downloads retain partial files for resumption and are SHA-256 checked. A populated Python environment stays at its final path.

The installer emits one JSON result with installation paths, active version, `restart_required`, and MCP connection `command` and `args`. Logs use stderr. Candidate verification supplies a local `-ManifestPath`; normal installation fetches the published version and the matching npm package. Reinstallation preserves workspace content. Preparing another version while a process record exists leaves the active version unchanged and reports that a restart is required.

The stdio MCP entry takes `--install-root` and `--workspace`. `workbench_start` alone can launch the fixed controller; status and future business tools do not accept executable commands. The startup result exposes a verified loopback `web_url`, the selected version/workspace and whether the instance was reused. Unknown results must be investigated before another start.

## Controller contract

The backend provides `python -m astrophotoflow.cli init|start|stop --workspace <path> --json`. Init preserves an existing configuration. Start persists `run/processes.json` before launching children; its `client` object becomes ready only after health checks. Stop checks process identity, confirms shutdown and removes the stopped record. Unknown records remain for investigation.

The ready object contains `status: "ready"`, `version`, `workspace`, `service_url`, `web_url` and `reused`. Start prints that object on stdout; diagnostics go to stderr. `GET /health` on the service returns `status: "ok"`, `version` and `workspace`. The deployed product version and commit come from generated `astrophotoflow/release-version.json`, not the engine's project version. MCP checks both live identity and the HTML endpoint. The engine must serve the packaged `web` directory explicitly, not the frontend installed by pip. Missing knowledge indexes do not block the canvas.

## Draft and public publication

The tag workflow builds from a commit on `main`, verifies a clean Windows installation and creates a draft. Verification covers spaces in paths, interrupted downloads, checksum failure, preserved workspace content, occupied default ports, repeated startup and the web page surviving MCP disconnection. The report binds all asset hashes to the version and commit. Missing entry points or failed verification block the draft.

The manual `publish.yml` workflow validates the existing draft assets without rebuilding. It publishes the exact MCP tarball through npm OIDC, then makes the GitHub release public. An existing npm version is reused only when its integrity matches. A failed npm publish leaves the GitHub draft intact. The first public release requires the maintainer to make the corresponding source repository public and establish npm scope ownership and its trusted publisher; the workflows do not change repository visibility.

The [delivery decision](../.agents/notes/implemented/process/2026-11-14-windows-agent-installation-and-delivery.md) records the trade-offs and verification limits. WSL release support is outside this first delivery.
