# Agent Note: Projects and exports reference the library, they do not own it

Status: proposed

English | [中文](2026-11-14-projects-references-and-exports.zh.md)

## Problem

The old workbench let a project reference shared datasets and assets, showed which projects would be affected by an edit, and ran exports as separate jobs with per-item results. The temptation in a new schema is to give each project its own copy of the images, or to treat an export as a new library asset. Both destroy the single-original rule: the same light frame would have several ids, edits would diverge, and deleting a project could delete data that another project still uses.

## Proposal

A project is a named workspace over library entries. It references assets and datasets by id; it never copies them. An export is a job that writes files outside the library and returns a receipt; it creates a library asset only when the user explicitly registers the result.

### Projects and references

A project has an id, a name, optional notes, a status, a revision, and ordered references. A reference names either an asset or a dataset, never both, and is unique per project and target. Reference order is the project's presentation order; it does not change dataset member order.

A dataset can be referenced by many projects. Its members, order, and calibration binding are shared: an edit in one project is visible in every project that references the dataset, and the dataset detail lists the affected projects before the edit is saved. A project that needs a different calibration or a different member order needs a different dataset.

An asset can be `shared` or owned by one project. A shared asset can be referenced by any project. A project-owned asset can be referenced only by its owner until it is explicitly moved to shared or reassigned. Ownership is a visibility rule, not a copy; the asset id and its file do not change.

Removing a reference does not delete the target. Deleting a project requires a disposition for its owned assets: move them to another project, make them shared, or move them to trash as one entry. The preflight lists every owned asset and every external reference; no asset is deleted implicitly.

### Exports

An export job records the caller's `request_id`, the ordered selection (assets or datasets), the output profile, the destination, the collision policy, and a status of `queued`, `running`, `completed`, `completed_with_errors`, `failed`, or `cancelled`. The selection is frozen when the job starts: later library edits do not change what the job reads.

The job writes one file per selected item, or one file per dataset when the profile says so. Each item records its source asset id, output path, bytes, hash, and status. A failed item does not discard successful items; the job ends as `completed_with_errors` and its receipt lists both.

The default collision policy is to fail rather than overwrite. Overwriting requires an explicit flag and a preview of the files that would be replaced. An export never writes into the managed library; it writes to the user-selected destination, and the receipt records that path.

An exported file is not a library asset by default. If the user asks to register it, the normal intake path assigns a new asset id and records the export receipt as provenance. Re-exporting the same selection creates a new job and new files; it does not silently replace the previous receipt.

### Results

An operation result that the user wants to keep in the library is registered as an asset with role `intermediate` or `final`, with provenance links to the operation receipt and the input asset ids. A result that is only downloaded is an export, not an asset. The two paths share the receipt format but not the identity rules: a result asset has a stable id; an export file has only its job item.

### Deletion and impact

Purging a referenced asset or dataset is blocked by the project reference until the reference is removed or the project is deleted. The purge preview lists the projects. Deleting a project does not delete shared targets, and its owned assets follow the disposition chosen in the preflight.

## Alternatives considered

**Copy assets into each project.** Rejected: the same frame would have multiple ids, edits and calibration would diverge, and storage would grow with every reference. References plus dataset sharing preserve one original per asset.

**Delete a project's assets with the project.** Rejected: a project may own images another project is about to reference, and deletion is not reversible without the trash flow. The preflight forces an explicit disposition.

**Treat every export as a library asset.** Rejected: exports are derivative copies with user-chosen formats and destinations; registering them automatically would pollute the library and create duplicate identities.

**Write exports into the managed library directory.** Rejected: the library owns its copies and tracks their hashes. An export into that tree would bypass intake and make the ledger wrong.

**Let a project override dataset order or calibration locally.** Rejected: a dataset is the unit of order and calibration; a local override would make the same dataset mean different things in different projects. Create a separate dataset instead.

## Acceptance criteria

- A project references assets and datasets by id and never copies their files.
- A dataset referenced by multiple projects reports the affected projects before a shared edit is saved.
- Removing a reference does not delete the target.
- Deleting a project requires an explicit disposition for owned assets; no asset is deleted implicitly.
- An export freezes its selection at start and reports per-item status.
- A failed export item does not discard successful items; the job ends as `completed_with_errors`.
- Overwriting an existing file requires an explicit flag and a preview.
- An export does not write into the managed library; registering a result goes through normal intake.

## Risks

- Project ownership adds a visibility rule that every library query must apply; a missed filter leaks a project-only asset.
- Shared edits can surprise another project. The affected-projects list must appear before save, not only in an audit log.
- Export receipts can be large; per-item results need paging and a stable job id.
- Users may expect an export to appear in the library. The UI must state that an export is a file, and offer registration as a separate action.
