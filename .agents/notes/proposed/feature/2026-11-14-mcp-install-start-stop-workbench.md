# Agent Note: One MCP installs and controls the workbench

Status: proposed

English | [中文](2026-11-14-mcp-install-start-stop-workbench.zh.md)

## Problem

The agent must download and initialize the workbench through workbench_init, start it through workbench_start and stop it through workbench_stop. Requiring a pre-existing installation receipt before MCP connects, or making the installer install MCP after the workbench, reverses that required flow. The current no-stop restriction also prevents the requested lifecycle.

## Proposal

One TypeScript FastMCP TS server owns the user-facing lifecycle tools. The host supplies Node; the npm package carries its fixed PowerShell installation worker. Init downloads the matching published workbench and prepares uv, Python, locked dependencies and the workspace. It returns a persistent installation operation and status observes completion. The worker never installs a second MCP or downloads a replacement for its running Node host.

Start and stop invoke the fixed installed Python controller. The controller shares its real implementation with typed FastAPI lifecycle routes and owns process identity, concurrency, readiness and shutdown. FastAPI registers native node queries through HTTPX; business tools use those HTTP interfaces. The native editor retains graph saving, undo and execution.

Installation and runtime state remain distinct. Repeated initialization preserves workspace data; repeated start reuses the instance; stop retains installation and data and leaves MCP connected. Busy or unknown process state is refused rather than forced. Only the lifecycle bootstrap adapter may create the fixed installation/controller processes; tools accept no arbitrary command, URL or PID.

Windows candidate packaging verifies the actual sequence MCP → init → start → node query → stop → start. Candidate snapshots are installable locally but cannot be publicly published. Formal releases retain clean tagged source, asset checksums, native Windows verification and manual publication of the same bytes.

### Scope and related records

This proposal owns the expanded lifecycle in the [task-client proposal](../architecture/2026-11-14-node-mcp-for-the-tool-surface.md), replacing its externally installed, start-only and no-stop restrictions. Its business HTTP boundary, generated contracts and prohibition on whole-graph execution remain in force. Native graph ownership stays with the [canvas proposal](../architecture/2026-11-14-native-canvas-and-service-receipts.md).

The [implemented delivery record](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.md) describes the installer, the shipped lifecycle tools and the verification evidence. This proposal owns the lifecycle scope and acceptance; a passing candidate does not verify its remaining branches. That record's checksum, artifact-identity and reviewed-publication rationale remains active.

### Current implementation state

Part of this lifecycle shipped on Windows x64. Shipped: `workbench_init`, `workbench_start`, `workbench_status` and `workbench_stop` in the npm package; the PowerShell installer behind the fixed detached Node worker; the Python controller that owns process identity, startup and stop; node queries over HTTP; and a local candidate that runs the real MCP, installer, controller, service and engine through install, init, start, node queries, stop and restart.

Unverified: browser rendering, canvas interaction and JavaScript errors; stop refusal while the queue is busy or a prompt is being validated; concurrent installation and recovery from an abnormal installer exit; and first installation from a public GitHub Release or npm, which used a local candidate manifest instead. The candidate is `publishable: false`, and no tag, npm publication, GitHub release or repository visibility change happened. These open branches keep this record proposed rather than implemented.

The implementation phase covers lifecycle control and native node queries on Windows x64, using the existing uv/Python 3.12 environment and declared FastAPI, Pydantic, SQLAlchemy, Alembic, HTTPX and psutil dependencies. Asset management, calibration, bundles, remote canvas editing, retrieval and benchmark implementation remain separate capabilities. The existing frontend and native execution engine are reused.

## Alternatives considered

**Install the workbench before MCP.** Rejected because init must perform the download and initialization through the already-connected MCP.

**Require every lifecycle call to go through FastAPI.** Rejected because an uninstalled or stopped service cannot install or cold-start itself. The fixed local adapter handles those operations; business queries remain HTTP.

**Keep stop unavailable to MCP.** Rejected by the explicit lifecycle requirement. Scope and process identity constrain the tool to its configured workspace.

**Keep init as one unbounded blocking tool call.** Rejected because runtime and dependency downloads can exceed client request timeouts. A durable installation operation makes progress and interrupted outcomes observable.

## Acceptance criteria

- One MCP can connect before a workbench is installed and complete init, start and stop.
- Init downloads and initializes real software; status distinguishes acceptance from completion and permits interrupted retries without losing data.
- Start returns the verified native web URL; node queries return the real engine catalog through FastAPI.
- Stop affects only verified owned processes, preserves workspace content and leaves MCP usable for another start.
- The local Windows candidate passes the same meaningful installation/lifecycle checks, and the public publisher refuses candidates or incomplete reports.

## Risks

The host must supply a supported Node runtime before it can run MCP. Installation requires network access on a clean machine. Transient installation workers and service shutdown need durable state to distinguish failure from unknown outcomes. The existing installer, receipt, lifecycle permissions and verification order must be changed together; changing only the tool names would leave the bootstrap cycle unresolved.
