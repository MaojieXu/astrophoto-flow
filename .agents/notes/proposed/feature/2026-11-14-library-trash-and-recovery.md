# Agent Note: Trash separates removal from deletion

Status: proposed

English | [中文](2026-11-14-library-trash-and-recovery.zh.md)

## Problem

The old library had no soft-delete flag. Removing an entry created a trash row that remembered the entry type, the dataset it came from, its members, the files still to clean, and what had already been cleaned. That row is what made restore, impact preview, and partial purge failure possible. A boolean on the asset cannot answer "which dataset membership was removed", "which files are already gone", or "which item failed"; immediate deletion gives the user no recovery path and no way to see what a purge would cost.

## Proposal

Removal and deletion are separate operations. Removing an asset or dataset creates a trash entry and hides it from the active library; restoring returns the same identities; purging deletes the managed copies and closes the entry.

### The trash entry

A trash entry records:

- `entry_type`: `asset` or `dataset`;
- the removed `asset_id` or `dataset_id`;
- for a dataset, the ordered `member_asset_ids` and the dataset name;
- `pending_paths` and `cleaned_paths`;
- `cleaned_asset_ids`;
- `cleanup_status`: `pending`, `partial`, `completed`, or `failed`;
- `removed_at`, the actor, and a revision.

The entry is the trash. There is no `in_trash` boolean on the asset. An asset is in trash when an active entry names it, and the library query excludes those ids.

### Removal

Removing a standalone asset creates an asset entry. Removing a dataset creates a dataset entry and includes its members; the dataset row and its membership rows are removed from the active library, but the assets are not independently removable while the dataset entry owns them.

Removal is revisioned. A stale removal returns `409 REVISION_CONFLICT`. A dataset removal captures the member order and calibration bindings in the entry so restore can rebuild them; it does not leave the dataset half-removed.

### Restore

Restore recreates the asset or dataset with the same ids, names, metadata, member order, and calibration bindings. It fails with a conflict if an id has been reused, a member is already active in another dataset, or a calibration target is no longer available. The response names the conflicting item; it does not partially restore and then report success.

### Purge

Purge is a two-step operation. A preview returns the assets, managed files, total bytes, and blocking references, plus a short-lived `preview_fingerprint`. Purge requires that fingerprint and each entry's current revision. If the selection or any reference changed, the request returns `409 TRASH_STATE_CONFLICT` and requires a new preview.

Purge is blocked while any of the following still references an item: a project, a calibration binding, an active or queued call, a running export, or a dataset manifest that has not been rebuilt. The preview lists every blocker; the user must remove the reference first. Purging a dataset entry deletes its member copies and the dataset manifest, then the entry.

Purge deletes only managed library copies. It never deletes a source file outside the library, because the library never owns one. Each item is processed independently: a locked file marks that item failed, the entry becomes `partial`, and a retry targets only the failed items. A purge never leaves an asset row pointing at a deleted file; the row is closed only after its file is gone.

### Identity

A restored entry keeps its id. A purged id is retired and never reused. A re-import of the same source file after a purge is a new asset with a new id, because the old asset's history is closed.

## Alternatives considered

**Add a soft-delete boolean to the asset.** Rejected: it cannot record dataset membership, file cleanup progress, or per-item failure, and every query would need to remember the flag. The trash ledger is the record, not a filter on the asset.

**Delete immediately and rely on the operating system's recycle bin.** Rejected: the library cannot preview impact, cannot block purge while a project references the asset, and cannot report which file failed. It also makes restore platform-dependent.

**Cascade-delete a dataset and all its members.** Rejected: deleting a dataset should not silently delete masters or assets that a project still references. The trash entry makes the member set explicit and lets the user restore it as a unit.

**Hide entries from the library without a trash row.** Rejected: hidden is not recoverable, and a later cleanup cannot tell which files belong to the hidden entry. The explicit row is what makes the two-step purge safe.

## Acceptance criteria

- Removing an asset or dataset creates a trash entry and excludes it from the active library, without deleting its managed files.
- Restoring returns the same asset and dataset ids, member order, and calibration bindings.
- A purge preview reports assets, files, bytes, and every blocking reference; purge without the current fingerprint is rejected.
- Purge is blocked while a project, calibration binding, active call, running export, or stale manifest references an item.
- A locked file produces a `partial` entry, and retry processes only the failed items.
- A purged id is never reused; re-importing the same source creates a new id.
- No purge deletes a file outside the managed library.

## Risks

- Purge deletes data permanently. The preview, fingerprint, and explicit confirmation must be hard to skip in both the web UI and the CLI.
- A long purge can fail halfway; the entry must remain inspectable and retryable rather than disappearing with the files.
- Projects and calibration bindings can be added between preview and purge; the revision and fingerprint check must cover both.
- Trash can grow without a retention policy. The first version needs a visible size and a manual purge, not an automatic timer that surprises users.
