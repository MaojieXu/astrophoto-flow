# Agent Note: Windows agent installation and reviewed delivery

Status: implemented

English | [中文](2026-11-14-windows-agent-installation-and-delivery.zh.md)

## Problem

An agent needs to install the local workbench, connect MCP, request startup and return a working browser URL. A checkout with dependency instructions does not supply that path. The earlier [no-distribution proposal](../../rejected/simplification/2026-11-14-no-distribution-engineering.md) avoided maintenance for a single-developer checkout, but the requested agent installation needs a versioned archive, installer and release checks.

Pure HTTP MCP cannot cold-start a stopped service without an already-running control daemon. Introducing another permanent service just for that bootstrap would increase the lifecycle burden. The alternative needs a tightly bounded local execution path.

## Decision

The delivery scripts target Windows x64. GitHub Releases carries a ZIP, corresponding source, installer, manifest, checksums and native verification report; npm carries the compiled MCP package. The root package version is authoritative. Development tags use `X.Y.Z-dev.N` and npm `next`. Fork versions stay independent. WSL release artifacts and configuration are excluded.

The PowerShell installer manages application-local uv, Python and Node, installs the backend from its lockfile and installs the exact MCP tarball. Partial downloads and package caches survive retries. Code is extracted to a version directory before creating a virtualenv there, so no populated environment is relocated. Workspace data is separate and preserved. Failed installs do not change the active receipt; a recorded running workspace prevents an automatic cross-version switch.

The npm package exposes `workbench_init`, `workbench_start`, `workbench_status` and `workbench_stop`, plus the node queries served over HTTP. Only `src/mcp/src/lifecycle/bootstrap.ts` imports process creation. It launches the pinned `installer/install.ps1` and the installed controller CLI, with executables and arguments derived from the pinned product version, the installer receipt and the fixed controller entry, never from tool arguments. Installation runs inside a detached Node worker that owns the PowerShell console: Windows PowerShell 5.1 can exit 0 before `-File` runs under a directly detached process, and the worker keeps the installer alive past an MCP disconnect without gaining a command or script surface. Launcher output and the installer's own log are separate files, so the appending log is not also the process's stderr. The installer decides Windows x64 from the runtime platform rather than the filtered `OS` environment variable, writes the receipt only after confirming the target directory is its own, and exposes progress through the operation file that `workbench_status` polls as `installing`. The controller owns child-process identity, startup and shutdown in one implementation shared with the typed FastAPI lifecycle routes. MCP verifies recorded version/workspace identity, service health and the HTML endpoint before returning the loopback URL. Unknown state blocks blind startup retries.

Tag builds validate source preconditions, build frontend and MCP, assemble assets and run native Windows verification before creating a draft. Manual publication reuses those bytes, checks their version, commit, checksums and complete verification report, publishes npm first and exposes GitHub second. Existing npm versions require matching tarball integrity. OIDC publishing and repository visibility are maintainer setup, not installer actions.

## Alternatives considered

**Keep checkout-only distribution.** Rejected for this requirement: it leaves each agent to reconstruct toolchain setup and startup. The earlier proposal remains a guardrail against adding unrelated packaging infrastructure.

**Restore the Python wheel and npm Python bootstrap.** Rejected: the archive already contains the engine tree and built page. uv installs dependencies in one environment; npm does not install or embed the Python application.

**Launch the installer as a directly detached PowerShell process.** Rejected: under `DETACHED_PROCESS`, Windows PowerShell 5.1 exits 0 without running `-File`, and changing `windowsHide` or `InputFormat` does not help; a non-detached child dies with its Node parent instead. A detached Node worker keeps a console owner while the fixed installer stays the only script that runs.

**Keep MCP pure HTTP by installing a permanent bootstrap service.** Rejected: it adds another process to configure and maintain before the workbench can start. One fixed startup adapter is the explicit exception; arbitrary shell execution remains unavailable.

**Ship an installed virtualenv or a Windows setup wizard.** Rejected: rebuilding from pinned platform wheels avoids path-dependent environment relocation, while the agent already provides the installation UI.

**Rebuild during publication or publish automatically on a tag.** Rejected: the reviewer must approve the same bytes that passed verification. Tags produce drafts; public publication requires a separate manual action.

## Consequences

Dependency downloads remain necessary on a clean machine; the installer retains caches and verifies pinned runtime archives. The two registries are not transactional: an npm success followed by a GitHub failure is recovered by checking matching npm integrity and retrying GitHub publication. First-time scope ownership and trusted-publisher setup remain external prerequisites.

The MCP build and review tarball are executable packaging paths. Native PowerShell failure scenarios verify checksum rejection, archive traversal rejection and refusal to activate a controller-less payload. Focused boundary coverage checks the startup exception without admitting backend imports. The Windows candidate adds an end-to-end run of the real MCP, installer, controller, service and engine; install, init, start, node queries, stop and restart pass its 30 platform checks.

The controller ships in `src/workbench/backend/astrophotoflow` and the installer installs it with uv, so preflight no longer finds controller files missing. Candidate builds declare `publication: candidate` and `publishable: false`: the verified candidate came from a dirty working tree and cannot be published. Its passing checks still verify no browser, so rendering, canvas interaction and JavaScript errors remain unproven, as do stop refusal while the queue is busy or a prompt is being validated, concurrent installation, recovery from an installer that exits abnormally, and first installation from a public GitHub Release or npm, which used a local candidate manifest instead. Adding these scripts performs no tag, npm publication, GitHub release or repository visibility change.

## Related

The proposed [single-MCP installation and control flow](../../proposed/feature/2026-11-14-mcp-install-start-stop-workbench.md) owns the lifecycle scope this record reports: MCP-first installation order, stop permission, and refusal of busy or unknown process state. It stays proposed because its acceptance criteria are not verified end to end. This record states what ships and keeps the artifact verification and reviewed-publication rationale; a passing candidate is not evidence that the proposal's unverified branches hold.
