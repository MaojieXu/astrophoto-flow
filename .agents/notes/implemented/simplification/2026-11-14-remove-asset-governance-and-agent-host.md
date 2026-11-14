# Agent Note: Delete the engine's asset database, governance gate and agent host

Status: implemented

English | [中文](2026-11-14-remove-asset-governance-and-agent-host.zh.md)

## Problem

The vendored engine ships three subsystems that we either already own or can never use. `app/assets` with `app/database` and `alembic_db` is a second ledger for image files: it hashes content, scans directories on a timer, and writes back what it finds, which is exactly the write path our own asset ledger forbids because the ledger has to hold frame class, dataset positions, calibration links and original-file protection. `app/governance` is a third-party pack gate keyed on signed policy documents for a pack format we do not have. `app/agent_host` mounts `/api/agent` and `/api/workflows` so a hosted agent can drive the engine, which is the role our MCP tool surface plays against our own HTTP API instead.

Keeping them was not free even when switched off. They owned 195 call sites outside their own directories, they turned `--enable-assets` into a mode every reader had to reason about, and the seeder could still mutate a library behind a workspace boundary we are responsible for. Deletion is the only state where a reader cannot accidentally build on them.

## Decision

Delete `comfy_api_nodes/` (101 files, 63,829 lines), `app/assets/` (37 files), `app/database/` (2 files), `alembic_db/` (12 files), `app/asset_export.py`, `app/governance.py`, `app/agent_host.py`, `comfy_execution/asset_enrichment.py`, `comfy_execution/media_enrichment.py`, `script_examples/`, and the `tests/inference` and `tests/compare` suites that need multi-gigabyte checkpoints.

Then strip the couplings instead of stubbing them: `main.py` loses the database startup, the startup-refusal messages, the scanner pause around each prompt, and the agent host's start and stop; `server.py` loses the asset route registration, the export manager, the upload-time registration and hash resolution; `execution.py` loses the `asset_manager` argument and the output enrichment; `nodes.py` loses the pack gate; `comfy/cli_args.py` loses five switches; `comfy_api/feature_flags.py` reports `"assets": False`. `SERVER_FEATURE_FLAGS` therefore no longer depends on `main.py` rewriting it at startup.

Twenty-two engine tests referenced the removed modules and went with them, along with 129 stale `__pycache__` directories. `tests-unit/app_test` was restored from the reference checkout minus the tests for the asset scanner and the prompt worker's pause behaviour, so the tests for the model, node and custom-node managers still run. `alembic`, `SQLAlchemy` and `alembic.ini` left `requirements.txt` because nothing else imports them.

## Behaviour that changed

`/upload/image` and `/upload/mask` still store the file but answer without an `asset` object, and `/view` answers `404` for a `blake3:` name because no code registers content hashes any more. Clients that read `resp["asset"]` must stop. The asset sidebar tab and the blake3 widget values it introduces are dead code on the frontend side.

## Alternatives considered

Keep the modules and disable them at startup: every reader still meets the flags, and the seeder's write path stays one configuration mistake away. Keep only the scanner and drop the database: the scanner exists to feed the database, and its deduplication is the one part we do not want. Adopt the engine's ledger and extend it: it has no notion of frame class, dataset position, calibration, or an original file that must survive being processed. Write to both ledgers: two writers to one library, with the seeder's findings arriving asynchronously after our snapshot. Delete only the three hooks that call into these modules: the hooks are cheap to remove, but then the modules stay as dead weight with live imports.

## Consequences

The engine is now 700 Python files and 231,614 lines, and an eighth of that Python was a single directory: `comfy_api_nodes` alone was 63,829 lines. Nothing here was verified at runtime: this machine has no torch, so the receipts are `python3 -m compileall` returning zero, an empty residual-reference grep for every removed symbol, and a real import of `comfy.cli_args` and `comfy_api.feature_flags` that reports the assets flag as `False` and no asset, agent or database switch. The first start with dependencies installed is the remaining proof.

Two deletions are still open. The model zoo (`comfy/ldm` and the model loaders around it) is 97,000 lines that stay until the node classes that use them are cut in the same change. The upload and view routes stay for now: they are the only path a browser has for dropping a local file into a graph, and whether that path survives belongs to the frontend cleanup, not to this one.
