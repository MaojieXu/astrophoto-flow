# Agent Note: One config file, one workspace, explicit restart

Status: proposed

English | [中文](2026-11-14-workbench-settings-and-lifecycle.zh.md)

## Problem

The old workbench split configuration across a workspace `config.toml`, a user-level pointer file, a runtime `processes.json`, and environment overrides. It worked, but it made "what is actually running" a question with several answers, and a settings save could not be applied without a restart. The new repository runs from a clone with one Python environment and no installer; it needs a smaller contract: one user-edited file, one workspace, and a restart that is explicit rather than inferred.

## Proposal

One workspace has exactly one user-edited `config.toml`. Runtime state files record what the controller started, but they are not configuration and are never hand-edited.

### Location and schema

The config path comes from `--workspace` or `ASTROPHOTOFLOW_CONFIG`; there is no user-level default-workspace pointer. A workspace is the directory that contains `config.toml`; running two workspaces means running two processes with different paths, not switching a global default.

The file has a strict, closed schema:

```toml
[server]
host = "127.0.0.1"
port = 8190

[storage]
data_dir = "data"

[comfyui]
allowed_origins = ["http://127.0.0.1:8188"]

[ingestion]
file_workers = 2
preview_workers = 1
```

There are no logging, language, engine-path, token, database, runtime, queue, or import-root keys. `host` must be a loopback IP literal; `port` is an integer from 1 to 65535; `data_dir` is non-empty and resolved relative to the config file; `allowed_origins` is a non-empty list of loopback HTTP origins with explicit ports; the two worker counts are integers of at least one. An unknown top-level table or an unknown key is a validation error, not a silently ignored setting.

Derived paths are `data_dir/astrophotoflow.sqlite3`, `data_dir/service.token`, and `data_dir/.database.lock`. The data directory is created with owner-only permissions; the token is 32 random bytes written once with owner-only permissions. Logs go to `logs/`, not into the config.

The workspace layout is `config.toml`, `data/`, `input/`, `output/`, `logs/`, `context/`, `comfyui-user/`, `comfyui-data/`, `run/`, and `web/`. `web/` is the built frontend served by the engine; it is not a second configuration source.

### Processes and ports

The controller starts two processes from the same environment: our HTTP service and the engine. The service serves the API and the library; the engine serves the canvas and executes graphs. Both bind loopback only.

The configured service port and the first allowed origin port are preferences, not guarantees. If a port is occupied, the controller takes the next free port and rewrites the allowed origins to the actual engine port for that run. The actual ports are recorded in `run/processes.json` with the workspace path, config path, effective settings, and process identities. A second start on the same workspace reuses a ready process; a partial or unknown state is refused rather than duplicated.

### Lifecycle

`start` prepares the workspace if needed, starts the service, waits for its health endpoint, starts the engine, and waits for readiness. `status` reports each process as managed, unconfirmed, exited, or not managed, and reports ports as managed, available, or occupied-unverified. `stop` stops only processes whose pid, creation time, executable, command line, and workspace marker all match the recorded identity; if the marker differs, it refuses. The service is asked to drain before it is terminated.

`restart` runs out of process and records an operation id. The controller writes a receipt before it exits; a caller that loses the connection queries the receipt by operation id instead of starting a second restart. Restart is refused while a native queue item, a software call, a bundle preview, or an unknown operation is active.

`start` and `status` are available to the MCP surface. `stop`, `restart`, and configuration writes are not: an external agent may prepare and start a workbench, but it may not take one down or change its settings.

### Settings and save semantics

The settings API reads the saved file and the effective runtime values separately. `GET /api/v1/settings/workbench` returns both, the config path, the workspace path, the derived addresses, and a `config_token` computed from the config path and bytes. `PATCH` requires that token; a mismatch returns `409 CONFIGURATION_CONFLICT`; invalid values return `422 INVALID_CONFIGURATION` with field paths; a partial write returns `503 CONFIGURATION_PARTIALLY_SAVED` and the old file remains recoverable.

A save never restarts anything. `restart_required` is true when the saved values differ from the running values. The settings surface shows "saved" and "effective" separately and disables the restart action while the form has unsaved changes. The restart endpoint applies the saved values and returns an operation id.

The first version exposes only the worker counts, data directory, host, service port, and allowed origins. Selecting a directory uses a native picker where the platform provides one; elsewhere the field accepts a typed path. The UI is implemented in our platform layer, not by editing the frozen upstream settings panel.

### Language and diagnostics

Language is not a config key. The single source is `Comfy.Locale` in the workspace's `comfyui-user/default/comfy.settings.json`. When the engine is running, the service posts the setting to the engine; when it is stopped, it rewrites the file atomically while preserving other keys. The UI reloads to apply the change.

`doctor` checks the interpreter, the workspace, the config, the last recorded ports, and the engine import. It does not install anything and does not repair a workspace automatically. Its output names the failing check and the command that would fix it.

## Alternatives considered

**Split config into server, storage, and engine files.** Rejected: three files can disagree, and a partial save becomes a multi-file transaction. One file with a strict schema keeps the commit atomic and the diff readable.

**Keep a user-level default-workspace pointer.** Rejected: it is a second config file and makes "which workspace am I editing" depend on hidden state. `--workspace` and the environment variable are explicit.

**Hot-reload settings.** Rejected: workers, the database path, and the engine's bind address cannot change safely under a live process. A restart is honest and testable.

**Restart automatically after save.** Rejected: a save may be exploratory, may happen while a job is running, and may change the port the browser is using. The user chooses when to restart.

**Put settings in the database.** Rejected: the database lives inside the data directory the settings choose, and a corrupt database would take the settings with it. The config file must be readable and editable without the service.

**Let the UI edit the upstream settings panel.** Rejected: the frontend fork is frozen. Our panel is an extension point; upstream files stay unchanged.

## Acceptance criteria

- A workspace has one `config.toml`; no second user-level config or default-workspace pointer is read.
- Unknown top-level tables or keys are rejected with a field path.
- A save is atomic, token-checked, and reports `restart_required` without restarting.
- Port fallback records actual ports and rewrites allowed origins for the run.
- `status` distinguishes managed, unconfirmed, exited, and not-managed processes.
- `stop` refuses a process whose workspace marker does not match.
- `restart` is refused while a queue item, software call, or unknown operation is active, and its receipt is queryable by operation id.
- MCP can start and inspect the workbench but cannot stop, restart, or write configuration.
- Language changes go through `Comfy.Locale`, not a config key.
- Settings UI changes live in our platform layer; no upstream settings file is edited.

## Risks

- Windows atomic replace can fail while another process holds the file; the save path needs a retry and a visible failure, not a truncated config.
- Port fallback can race with another process taking the port between probe and bind; the controller must retry and report the final ports.
- A workspace is a directory, so moving it changes relative paths; the config must be resolved from its own location, never the current directory.
- Busy detection can miss an engine request that is between states; an unknown state must block restart rather than guess.
- One workspace per process is simpler but less convenient for users with several projects; the CLI can still run several processes explicitly.
