# Agent Note: A dataset is an ordered set of subframes

Status: proposed

English | [中文](2026-11-14-datasets-and-member-order.zh.md)

## Problem

The old repository treated a dataset as an ordered subframe group, and `dataset_member.asset_id` was unique: one subframe belonged to at most one dataset. That constraint is what made calibration, exposure totals, trash references, and directory manifests unambiguous. The new repository has no dataset contract. An unordered set would lose the acquisition order that stacking depends on; a many-to-many membership would make "which calibration applies to this frame" a per-project question; and a manifest treated as a second source of truth would drift from the ledger.

## Proposal

A dataset is a named, revisioned, ordered list of subframe assets. It is the unit of calibration and the unit a project references. An asset belongs to zero or one dataset; removing it from a dataset does not delete the asset.

### The dataset record

A dataset carries an id, name, optional library directory, status, notes, revision, and a manifest state (`pending`, `ready`, `failed`). It is a shared library object by default; a project references it rather than copying it. The dataset row exposes member count, cumulative exposure over the full member list, input readiness, referencing projects, and the current calibration per purpose.

Members are subframes only. A master frame is a standalone asset and never a dataset member. A dataset normally shares one frame purpose; mixed-purpose membership is allowed but is shown as mixed, and dataset-level calibration is unavailable until the members agree. The purpose is never inferred from the first member.

### Order

The submitted member list is authoritative. Creating or replacing members deletes and reinserts the rows with `position = 0..n-1` in the submitted order. Appending adds new members after the existing last position and never reorders the existing list. Replacing with the same ids and bindings is a no-op and does not bump the revision.

The order is part of the dataset identity for processing. Two datasets with the same members in a different order are different inputs. The API returns members in position order and rejects duplicate ids in one request.

### One dataset per asset

A subframe asset belongs to at most one dataset. Adding it to a second dataset returns `409 ASSET_DATASET_OWNERSHIP` and names the current owner. The user must remove it from the current dataset first. The asset row shows its dataset id and name; a standalone subframe shows neither.

This is a deliberate limit, not an implementation shortcut. Calibration status and evidence are stored on the asset, and a dataset has one current binding per purpose. If one frame belonged to two datasets with different dark masters, the asset's calibration status would have two answers. Projects that need the same frames share the dataset; they do not clone membership.

### Exposure and summaries

Cumulative exposure sums the exposure of every current member, not just the visible page. A missing or unknown exposure contributes nothing to the sum but increments an unknown count; it is never treated as zero. The dataset row shows member count, total exposure, and calibration counts without loading member details.

### Manifest

`dataset.json` is a generated manifest for external tools: dataset id, name, purpose, ordered members with relative paths and hashes, and the current calibration bindings. The database is authoritative; the manifest is rebuilt from it and marked `pending`, `ready`, or `failed`. A manifest write never creates, renames, or reorders a member. If the file is edited by hand, the next rebuild overwrites it and reports the difference.

### Directory organization

The library can place a dataset's files into a predictable directory. An organization request produces a plan: current path, target path, asset id, hash, and the operation that would move it. The user confirms the plan with a fingerprint; execution writes a receipt per file and reports `completed`, `partial`, or `failed`. A moved file updates `storage_location` in the same transaction as the move. A failure leaves the asset at its old path and records the reason; it never leaves the database pointing at a file that was not moved.

Opening the dataset directory is a read-only convenience. It never changes membership or calibration.

## Alternatives considered

**Use an unordered set.** Rejected: stacking and calibration recipes depend on member order. Sorting by filename or capture time at read time guesses an order the user may have deliberately changed.

**Allow many-to-many membership.** Rejected by the one-dataset decision: calibration status, evidence, exposure totals, and trash references would all need a membership key. Sharing a dataset across projects already covers the legitimate reuse case.

**Treat the manifest as the source of truth.** Rejected: external tools can edit JSON, and a hand-edited manifest cannot enforce revision checks, ownership, or trash state. The manifest is a projection, not a ledger.

**Keep masters inside datasets.** Rejected: a master is a reusable calibration asset, not a subframe of one capture. Mixing them would make dataset exposure and member order meaningless and force a master to belong to one dataset.

**Use virtual folders instead of moving files.** Rejected for the first version: virtual folders avoid file moves, but they do not give external tools a stable path or let a user inspect the library in a file manager. The plan-and-receipt organization flow keeps the database authoritative while still producing real paths.

## Acceptance criteria

- Creating a dataset with members stores exactly the submitted order, and reading it returns the same order.
- Appending members preserves the existing positions; replacing with a reordered list rewrites positions and bumps the revision once.
- Adding an asset to a second dataset returns `409 ASSET_DATASET_OWNERSHIP` and does not change either dataset.
- A master frame cannot be added as a dataset member.
- Cumulative exposure covers the full member list and distinguishes unknown exposure from zero.
- `dataset.json` can be deleted and rebuilt from the database without changing membership or order.
- An organization plan is required before moving files; execution reports per-file outcomes and never leaves a stale `storage_location`.
- Removing a member keeps the asset and makes it available to another dataset.

## Risks

- Replacing a large member list rewrites every position row; the transaction must be fast enough not to block library reads, or use a staging table.
- A generated manifest can still drift between rebuilds; the UI must show its state and the last error, not imply it is live.
- Moving files on Windows can fail on open handles or long paths; the receipt and old-path fallback are part of the feature, not an error path.
- The one-dataset rule will frustrate users who think in "same lights, two projects". The UI must explain sharing a dataset rather than duplicating it.
