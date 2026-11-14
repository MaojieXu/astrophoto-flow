# Agent Note: Equipment is a snapshot, not a live lookup

Status: proposed

English | [中文](2026-11-14-equipment-and-setups.zh.md)

## Problem

The old library let a user register cameras, telescopes, filters, and mounts, combine them into setups, and apply a setup to an imported image. The image then kept a frozen equipment snapshot. That freeze is the point: editing a camera's pixel size or deleting a filter must not rewrite what an earlier image was captured with. The new repository has no equipment contract, and a live foreign-key lookup would quietly change history, misstate effective focal length, and make a deleted device break an old dataset.

## Proposal

Equipment records are reusable definitions. A setup is a named combination of definitions. An asset keeps a frozen snapshot of both, plus optional ids for navigation.

### Definitions

A device has an id, a name, a kind, optional notes, an `active` or `archived` status, a revision, and kind-specific specs:

- `camera`: pixel size in micrometres, sensor width and height in pixels, pixel array (`mono`, a specific Bayer or X-Trans pattern, or `unknown`), and optional bit depth. An unspecified array is `unknown`, never assumed mono.
- `telescope`: native focal length in millimetres, aperture in millimetres, and optional optical design. Accessories are part of a setup, not baked into the telescope.
- `filter`: the label printed on the filter, an optional channel name, and an optional bandwidth in nanometres. The channel is free text; the service does not guess a wavelength or a band from the label.
- `mount`: name, model, and notes. There is no control channel and no driver connection.

Names are labels, not identities. Renaming a device keeps its id and does not change any snapshot. Archiving removes a device from new selections but leaves existing references and snapshots intact.

### Setups

A setup has an id, a name, an optional imaging camera, an optional guide camera, an optional telescope, an optional mount, an ordered list of filters, an ordered list of optical accessories, optional software notes, a revision, and a status.

An optical accessory has a name and a positive multiplier. The setup's effective focal length is the selected telescope's native focal length multiplied by the selected accessory's multiplier. The computed value is shown with its inputs; it is not stored as an independent editable number.

Every member must be an active device of the matching kind. A setup does not create devices implicitly, and removing a device from a setup does not reorder or replace the remaining members.

### The asset snapshot

When an import or an explicit apply binds equipment to an asset, the asset stores a JSON snapshot containing the setup composition and each device's name, kind, and specs, plus the selected ids and the effective focal length inputs. Metadata fields that came from equipment are marked `equipment` in `value_sources`; a manual edit replaces that source with `manual`.

Later edits, archival, or deletion of a device or setup do not rewrite the snapshot. The asset detail can still link to the current definition, but the displayed capture facts come from the snapshot. A missing current definition is shown as unavailable, not as a changed capture.

### Import defaults

A preflight may propose a setup and its devices for a batch. The proposal is a default, not a prerequisite: a user can import with no equipment, with a partial setup, or with per-file overrides. Precedence is manual, then a file-observed value, then the frozen setup default, then unknown. An equipment default never overrides an exposure, gain, offset, or measured temperature recorded for the individual frame.

### Deletion and archival

Deleting a device or setup requires a preflight that reports the assets, setups, and calibration relations that reference it, plus a fingerprint of that impact. Confirmation must use the same selection and fingerprint; a changed impact returns `409` and requires a new preview.

Deleting a device removes it from current setups while preserving the other members' ids and order; it does not choose a replacement. Deleting a setup removes the combination only; it does not delete devices, images, or originals. An asset snapshot survives either deletion.

## Alternatives considered

**Join assets to live equipment rows.** Rejected: editing a camera would change the meaning of every old image, and deleting a filter would break them. The snapshot is the historical fact; the row is the current definition.

**Keep equipment as free-text metadata only.** Rejected: it loses reuse, setup composition, and the ability to check compatibility during calibration or import. Free text also cannot express pixel size or accessory multipliers reliably.

**Require a setup for every import.** Rejected: many users import a single file with no registered equipment, and the setup is a convenience rather than a gate. Unknown equipment is a valid state.

**Cascade-delete devices and dependent assets.** Rejected: deleting a camera must not delete the images taken with it. The preflight shows impact and requires an explicit decision.

**Add shooting presets separate from setups.** Rejected for the first version: a setup already describes the optical train, and a second preset layer would create two sources of truth for the same defaults. Presets can be added later without changing the snapshot format.

**Replace a deleted device in every setup automatically.** Rejected: the replacement may have different specs, silently changing effective focal length and compatibility. The setup shows the missing member and asks the user.

## Acceptance criteria

- A device can be created, edited, archived, and deleted with a revision check; archiving hides it from new selections without changing existing snapshots.
- A setup accepts only active devices of the matching kind, preserves member order, and computes effective focal length from the telescope and accessory multiplier.
- Applying a setup stores a snapshot on the asset and marks equipment-derived fields with `value_sources=equipment`.
- Editing or deleting a device or setup does not change any asset snapshot.
- Import works with no equipment, a partial setup, or per-file overrides; manual values win over equipment defaults.
- Deleting a device removes it from current setups without reordering or replacing other members.
- A delete preflight reports affected assets and setups and rejects a stale confirmation.
- No service exposes mount control, camera control, or a hardware driver.

## Risks

- Snapshots duplicate data and can drift from current definitions; the UI must label which values are historical and which are current.
- Filter labels are user text, so two identical filters may have different names. Matching must use the label plus optional channel, never a guessed wavelength.
- Deleting a device can affect many setups; the preflight must page large impact lists and remain readable.
- Users may expect an edited device to update old images. The asset detail must explain the freeze at the point of confusion.
