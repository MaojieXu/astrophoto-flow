# Agent Note: The CLI is a thin operator surface, not a second API

Status: proposed

English | [中文](2026-11-14-cli-as-thin-operator-surface.zh.md)

## Problem

The old CLI had two halves: a hand-written local app for workspace and process operations, and a generated business app with one command per MCP tool. The generated half duplicated the catalog, produced 126 commands, and drifted whenever a tool changed. The new repository still needs a scriptable path for initialization, start and stop, diagnostics, and a few library tasks, but it does not need a second implementation of the domain or a command for every route.

## Proposal

The CLI is a thin client over the same HTTP API and the same local controller. It has a small, task-shaped command set, stable JSON output, and documented exit codes.

### Entry point and workspace

The CLI runs as `python -m astrophotoflow.cli` from the same environment as the service; it is not installed as a console script. The workspace comes from `--workspace` or `ASTROPHOTOFLOW_CONFIG`, exactly like the service. Every command that talks to a running workbench reads the token from the derived path and refuses a token that is not owner-only.

### Local commands

`init` creates a workspace with a strict default `config.toml` and the directory layout. `status` reports the service and engine as managed, unconfirmed, exited, or not managed, plus the saved and effective ports. `start` and `stop` drive the controller; `restart` returns an operation id and can be queried. `doctor` runs the local checks and prints one line per check. `mcp-config` prints a ready-to-paste MCP client entry with the workspace path and the Node server command; it does not edit the user's client configuration.

`config get` prints the saved config and the effective runtime values. `config set` accepts only the keys the settings API accepts, preserves the rest of the file, and reports `restart_required`; it never restarts. `language get|set` uses the same `Comfy.Locale` path as the web UI.

### Domain commands

Domain commands are grouped by task, not by route: `library search`, `library show`, `library import`, `dataset show`, `dataset members`, `calibration check`, `task status`, `task wait`, `graph show`, and `receipt show`. Each accepts ids or a request id, and each prints a compact table by default or the full response with `--json`.

The CLI does not expose install, uninstall, or bundle preparation; those require the native web confirmation. It does expose the read-only bundle catalog. It does not expose direct SQLite access, arbitrary HTTP paths, or a generic `call` command that bypasses the task schemas.

### Output and errors

`--json` prints one JSON object to stdout with the same fields as the HTTP response, including the request id. Human output goes to stdout; diagnostics go to stderr. A successful command exits 0; usage errors exit 2; a conflict exits 3; an unavailable service exits 4; an unknown outcome exits 5; an internal error exits 1. The exact code is also present in the JSON error envelope.

The CLI never prompts interactively for a destructive operation. `library trash purge` requires an explicit `--fingerprint` and `--yes`; `stop` requires no confirmation but refuses an unverified process. A script can therefore run every command non-interactively.

### Relationship to MCP

The CLI and MCP call the same HTTP endpoints but have different jobs. MCP is the agent surface with structured tool results; the CLI is the human and script surface with tables, exit codes, and local lifecycle commands. Neither owns a private domain path, and neither is generated from the other.

## Alternatives considered

**Generate one command per MCP tool, as before.** Rejected: it duplicates the catalog, makes every tool rename a CLI break, and produces commands that are only a flag parser around one HTTP call. Task-shaped commands are fewer and more stable.

**Make the CLI the only surface and drop MCP.** Rejected: agents need structured tool schemas, not shell parsing. The two surfaces share the API, not their presentation.

**Let the CLI import the Python service in-process.** Rejected: it would bypass the single-writer HTTP boundary and make the CLI a second process that opens the database. The CLI is a client even on the same machine.

**Put lifecycle commands behind MCP only.** Rejected: a human operator needs `start`, `stop`, and `doctor` without an agent, and an MCP server should not be the only way to recover a stopped workbench.

**Keep a generic `call <tool> --json` escape hatch.** Rejected: it recreates the generated catalog under another name and gives scripts an untyped path that the contract test does not cover.

## Acceptance criteria

- The CLI runs from the same environment as the service and resolves the workspace the same way.
- Local commands cover init, status, start, stop, restart, doctor, mcp-config, config get/set, and language get/set.
- Domain commands are task-shaped and do not include a generic call command.
- `--json` returns the same fields as the HTTP response, including the request id.
- Exit codes distinguish success, usage, conflict, unavailable, unknown, and internal errors.
- Destructive commands are non-interactive and require explicit fingerprints.
- The CLI reads the token from the derived path and refuses a non-owner-only token.
- The CLI does not open SQLite or write the library directly.

## Risks

- A small command set can still drift from the API. Each command needs a contract test against the same schema snapshot the MCP uses.
- JSON output is a scripting interface; changing a field is a breaking change. The note should name the stable fields and version them with the API.
- Exit code 5 for unknown is easy to confuse with a generic failure; the JSON envelope must carry the precise state.
- `config set` can lose comments if it rewrites the file. The first version should preserve them or state that comments are not retained.
- The CLI is not installed, so every invocation needs the environment and module path. The README must show the exact command for the supported platform.
