# Agent Note: The asset ledger is the only record of an original

Status: proposed

English | [中文](2026-11-14-managed-asset-ledger.zh.md)

## Problem

The old repository kept an asset table, a dataset membership table, a trash ledger, and a content hash, but it also kept `storage_mode: reference|managed`. A referenced asset was a path plus a promise: the file could move, be overwritten, or live on a disconnected drive. The new repository removes the engine's own asset ledger and makes the HTTP service the only writer, so the remaining ledger has to say what it owns. Without that decision, "import" can mean three different things: copy a file, register a path, or hand the file to the engine and hope its upload route does not create a second record.

## Proposal

Every imported original is copied into the library before it becomes a usable asset. There is no reference mode, no external-path asset, and no `storage_mode` column. The source path is kept as provenance text, never as a read location. A registered asset owns exactly one library copy.

### The record

The asset row carries:

- a stable `asset_id` assigned at registration;
- `name`, `original_filename`, and the source path as audit text;
- `storage_location`, relative to the workspace data directory;
- `content_hash` in `blake3:<hex>` form and `byte_size`;
- `availability` as `available`, `changed`, or `missing`;
- `revision`, starting at 1 and incremented on every accepted mutation;
- capture metadata: camera, optical system, filter, ISO or gain, offset, exposure, integration time, sensor temperature, binning, CFA pattern, and frame classification;
- `value_sources`, recording `manual`, `file`, `equipment`, or `unknown` per metadata field;
- a frozen `equipment_snapshot` and capture snapshot;
- `calibration_status` (`UnCalibrated`, `Calibrated`, `Unknown`) and calibration evidence;
- `status` (`active` or `archived`), notes, and timestamps.

Dataset membership lives in a separate row, not in the asset. There is no file table and no version table: reprocessing an original creates a new asset rather than a second version of the old one.

### Identity and content

The `asset_id` is the identity. Renaming the asset, editing metadata, moving its library copy, or adding it to a dataset never changes it. A second import of the same source file is a second asset; the ledger does not deduplicate by hash, because two imports can carry different classification, ownership, or dataset intent.

The library copy is written through a staging file, hashed while it streams, and moved into place atomically. A hash mismatch or a failed copy leaves no published asset. Before any scientific read, the service re-hashes the library copy and compares it with `content_hash`; a mismatch marks the asset `changed` and the read fails with `SOURCE_CHANGED`. An asset that is `changed` or `missing` remains visible and repairable, but it cannot enter a new run.

### Metadata and snapshots

Metadata edits are optimistic: every mutation carries the revision the user saw, and a stale revision returns `409 REVISION_CONFLICT` rather than overwriting another edit. A field records where its value came from. `unknown` is a value, not a zero, and an absent numeric field is not stored as `0`.

Equipment is joined by id at import and frozen into the asset. Later edits to a camera, telescope, filter, or setup never rewrite the asset's capture history. The snapshot is the record of what the image says it used, not a live view of the equipment library.

Calibration status is declared by the user or by an import preset; it is not derived from whether a master is bound. Binding a master and executing a calibration are different events. The asset records the declared status and its evidence, while the dataset records the current binding.

### Input consistency

A scientific call declares `input_mode`:

- `reproducible`: the service verifies every selected asset's hash immediately before the call and aborts on a mismatch. If the call needs a stronger guarantee, it pins the selected bytes into the run directory by copy or reflink and gives the engine that path.
- `reference`: the service verifies that the library copy exists and reads it in place. This mode is explicit: it does not promise that the bytes are unchanged after the check.

Because every asset is managed, the old "materialize an external reference file" step disappears. `reproducible` is a verification guarantee first and a pinning option second; it is never an unconditional promise that the engine cannot read a file changed by another process.

### What the engine may not do

The engine's upload and save routes may stage bytes for a graph, but they may not create, rename, move, or delete a registered asset, dataset member, or receipt. The HTTP service is the only writer of the ledger. An engine route that needs a library file receives a path selected by the service and a call snapshot; it does not receive the workspace database.

## Alternatives considered

**Keep reference mode and register external paths.** Rejected: it saves one copy of the file, but it gives up the two properties the library exists for — the original cannot be protected from external edits, and the library cannot be backed up or moved as a unit. It also reintroduces missing drives, path permissions, and a repair workflow for every consumer.

**Use a content-addressed store keyed by hash.** Rejected: content addressing is a good integrity mechanism, not an identity. Renaming or reclassifying an asset must not change its id, and two imports of the same bytes can legitimately be two assets with different dataset intent. Hash keys also make deletion and reference counting harder, not easier.

**Allow multiple originals or versions under one asset.** Rejected: one asset means one registered original. A changed file is a new import with a new id; a processed result is a new asset. Multiple originals would force every dataset, calibration binding, and receipt to name which version it meant.

**Keep the engine's asset ledger and upload route.** Rejected: the new repository removed that ledger on purpose. Two writers over the same library cannot be made safe by discipline, and an engine upload route that registers assets would bypass revision checks and trash state.

**Use a soft-delete flag instead of a trash ledger.** Rejected: a boolean on the asset cannot record which dataset membership was removed, which files were already cleaned, or which items failed. Trash needs its own row and its own lifecycle.

## Acceptance criteria

- Importing a file copies it into the library, records its BLAKE3 hash and byte size, and leaves the source file untouched.
- After a successful import, deleting the source file does not affect the asset; renaming the asset does not change its `asset_id`.
- Editing a library file directly marks the asset `changed` on the next check, and a scientific read fails with `SOURCE_CHANGED` instead of using the new bytes.
- A stale metadata edit returns `409 REVISION_CONFLICT` and does not overwrite the newer revision.
- `unknown` metadata is distinguishable from a numeric zero in the API and the library view.
- No engine route can create or mutate an asset, dataset membership, or receipt.
- Removing an asset to trash does not delete its library copy; restoring it returns the same `asset_id`.

## Risks

- Managed copies double disk usage for large captures and add copy time to every import. The library must report bytes copied and free space before a batch starts.
- BLAKE3 is fast, but hashing every scientific read adds latency to large datasets; the service needs a cache keyed by path, size, and modification time, invalidated on any write.
- Windows path length, permissions, and antivirus locks make atomic moves less reliable than on Linux; the staging and rename path needs a retry policy and a clear failure state.
- Users who expect "import" to mean "index my existing folder" will be surprised. The import dialog and the CLI must state that a copy will be made and where it goes.
