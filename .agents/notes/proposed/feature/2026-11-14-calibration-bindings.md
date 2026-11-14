# Agent Note: Calibration is a binding, not a claim about the pixels

Status: proposed

English | [中文](2026-11-14-calibration-bindings.zh.md)

## Problem

The old repository stored one calibration row per dataset and frame purpose, allowed every slot to be empty, and kept the asset's calibration status separate from whether a master was bound. That separation is easy to lose: a picker that auto-selects the "best" dark, a dataset status derived from the presence of a binding, or a save that quietly runs the calibration would all collapse "what the user chose" into "what the pixels went through". The new repository has no calibration contract, and the engine's processing nodes must not become a second place where calibration relations live.

## Proposal

Calibration is a relation between a dataset and a master asset, one row per purpose, plus a declared status on the assets. Saving a relation never executes anything.

### The binding

A dataset has at most one current binding for each purpose: `bias`, `dark`, `flat`, and `dark_flat`. A binding is either disabled or points to one masterframe asset of the matching purpose. All four slots are optional; a light dataset may bind only a dark, a flat dataset may bind only a bias, and an empty slot is different from an explicit "not used".

The target must be an available, active masterframe asset with the matching frame type. It cannot be a raw calibration group or a subframe. A master may be bound to many datasets; the binding does not copy or move it.

Saving bindings is revisioned against the dataset. A stale save returns `409 REVISION_CONFLICT`; a target that is unavailable, trashed, or the wrong purpose returns a validation error naming the slot. The save records who changed the relation and when, and emits a receipt with the before and after binding.

### Status and evidence

Each asset carries a declared `calibration_status`: `UnCalibrated`, `Calibrated`, or `Unknown`. Import defaults to `Unknown`. The status is a statement the user or an import preset makes, backed by evidence; it is not derived from a binding, a file header, or a processing history.

Binding a master does not change any asset's status. Executing a calibration creates a new asset that records its actual inputs, the master asset ids, the parameters, and the call receipt; that new asset's status is `Calibrated` unless the operation explicitly preserves the input status. Operations that cannot establish their processing semantics leave the status `Unknown`.

A dataset's aggregate status is the uniform member status when all members agree, and `Unknown` with counts of each status when they do not. The aggregate never hides a mixed state behind a single label.

### Candidates and checks

A calibration target search filters by purpose, availability, equipment compatibility, and capture similarity. The result carries evidence, not just a name: matching and conflicting fields, unknown fields, and the reason a candidate is offered. The user chooses; the service never auto-selects a master.

A check endpoint evaluates a proposed binding without saving it. It returns conflicts such as a master with a different camera, binning, or temperature beyond tolerance, and it distinguishes "no conflict found" from "insufficient evidence". A batch plan can evaluate many datasets read-only and return a per-dataset recommendation, but binding still requires an explicit confirmation per dataset.

### Batch binding

A batch bind request names the datasets, the purpose-to-master map, and each dataset's expected revision. The response reports per-dataset success, conflict, or validation failure. A failure on one dataset does not roll back the others unless the caller asked for an all-or-nothing transaction; the receipt records which mode was used.

### Execution boundary

The service records the binding and the operation receipt; the engine performs the calibration. The engine receives the selected master paths and the dataset member paths in a call snapshot, not a database handle. The service never infers that a calibration ran because a graph containing a calibration node was saved.

## Alternatives considered

**Auto-select the best master.** Rejected: "best" depends on camera, filter, binning, temperature, and the user's judgment about a particular night. A recommendation with evidence is useful; an automatic choice that silently changes a dataset is not.

**Derive dataset status from the binding.** Rejected: a bound master is a plan, not a processed result. Deriving `Calibrated` from a non-empty slot would claim the pixels changed when they did not.

**Store calibration on the asset only.** Rejected: the same light frame can be processed with different masters in different projects. The dataset is the unit the user edits; the asset keeps the declared status and the processed result.

**Require all four purposes.** Rejected: many workflows use only a dark, or only a flat plus bias. An empty slot is a valid decision, not an incomplete form.

**Bind at project level.** Rejected for the first version: projects reference datasets, and a per-project binding would make the same dataset mean different calibration in different projects. A project that needs different calibration needs a different dataset.

**Execute on save.** Rejected: a binding edit is cheap and reversible; executing is expensive and creates a new asset. Mixing them makes an accidental click produce data.

## Acceptance criteria

- A dataset can save zero to four bindings, one per purpose, and an empty slot is distinguishable from a disabled slot.
- A binding target must be an available masterframe of the matching purpose; a raw group, subframe, or trashed asset is rejected.
- Saving a binding does not change any asset's `calibration_status` and does not create a processed asset.
- A dataset with uniform member status reports that status; a mixed dataset reports `Unknown` plus per-status counts.
- A stale binding save returns `409 REVISION_CONFLICT` and leaves the previous binding intact.
- A check response distinguishes "no conflict found" from "insufficient evidence".
- A batch bind reports per-dataset outcomes and records whether it was all-or-nothing.
- A processed result records its input asset ids, master asset ids, parameters, and operation receipt.

## Risks

- Evidence is often incomplete; a check that treats missing metadata as a conflict will block legitimate bindings, while one that ignores it will overstate confidence. The response must show both.
- A master can be moved to trash while still bound; purge must be blocked until the binding is removed, and the dataset must show the missing target.
- Batch binding across hundreds of datasets can produce a long receipt; the API needs paging and a stable operation id.
- Users may read "Calibrated" as "scientifically validated". The status means the declared processing relation, not a quality judgment.
