# Agent Note: The library is one queryable list

Status: proposed

English | [中文](2026-11-14-library-browsing-and-editing.zh.md)

## Problem

The old workbench showed assets and datasets in one paged table with global filters, compact and detail columns, thumbnails, and inline metadata editing. The new repository has no library query or edit contract yet. Splitting assets and datasets into separate pages would duplicate the filter, paging, and calibration-status logic; filtering in the browser would work for a hundred rows and fail for a capture archive. Editing without a revision check would let two open panels overwrite each other while both report success.

## Proposal

The library is one server-side query over asset and dataset summaries, plus one detail surface per selected row. The same query backs the web table, the CLI, and the MCP tools.

### One list

`GET /library/items` returns a page of mixed rows: an asset row for a standalone image and a dataset row for a subframe group. Both carry a stable id, a name, a thumbnail reference, a status, and a revision. A dataset row aggregates its members: member count, cumulative exposure, uniform or mixed calibration status, and issue counts. The row never expands members inline; the detail view does.

Ordering is explicit and stable: name, import time, capture time, or last edit, ascending or descending. Paging supports 10, 20, 50, and all, with a server-calculated total. A page is a snapshot, not a live cursor; the response carries a lightweight change token so the client can refresh without a full reload.

### Columns and filters

Compact columns are name, per-purpose calibration cell, classification, camera, ISO or gain, exposure, and temperature. Detail adds binning, CFA, imaging system, filter, total exposure, storage, availability, status, and notes. The dataset row shows its aggregate exposure and calibration counts instead of per-member values.

Filters run on the server: free-text name search, calibration status, material form, frame purpose, classification, camera, imaging system, filter, ISO or gain mode, binning, and numeric ranges for exposure, total exposure, temperature, ISO, gain, and offset. The filter-options endpoint returns the observed ranges and distinct values for the current library, so a slider never offers a value that no row can match. `unknown` is a filter value, not an empty string.

### Editing

Inline editing covers name, calibration status and evidence, material form, frame purpose, ISO or gain, offset, camera, imaging system, filter, exposure, total exposure, temperature, binning, CFA, status, and notes. A dataset edits only its name, status, and notes; members, order, and calibration bindings live in the dataset detail.

Every edit carries the revision the user saw. A stale revision returns `409 REVISION_CONFLICT` with the current revision; the client reloads that row instead of retrying blindly. A successful manual edit writes `value_sources[field] = manual`, so a later import or equipment change cannot silently replace a user decision. Batch metadata and equipment application is explicit: the caller names the assets and the fields, and the response reports per-item success and conflict.

### Detail and preview

Selecting a row opens a detail panel with metadata, dataset membership, calibration evidence, project references, and file location. A thumbnail opens a display preview; FITS assets expose HDU selection and header cards. The 100-pixel thumbnail is an index image; the display preview is a viewing image; neither is ever a scientific input. The preview can fail without changing the asset's availability.

### Canvas handoff

Dragging an asset or dataset onto the canvas creates a data source for that id. A dataset source expands to its ordered member paths when the graph runs, not at drop time. The drop does not copy the file or create a second registration; it records the id the graph already knows.

### Change detection

Local writes refresh the affected row immediately. External changes are discovered by polling the library change token, not by a websocket or an event bus. The token changes when an asset, dataset, membership, calibration binding, or trash entry changes; a client that sees a new token refetches the current page and the open detail.

## Alternatives considered

**Separate asset and dataset pages.** Rejected: users search one library, not two databases. Separate pages duplicate filters, paging, counts, and calibration aggregation, and they make a mixed result impossible to sort by capture time.

**Filter and sort in the browser.** Rejected: the full library does not fit in memory, and observed filter ranges must come from the same snapshot as the rows. Server-side filtering also keeps the CLI and MCP behavior identical to the web.

**Push changes over a websocket or event bus.** Rejected for the first version: it adds connection lifecycle, reconnect, and multi-client ordering to a single-user local app. A change token poll is enough until a real-time collaboration requirement exists.

**Edit with last-write-wins.** Rejected: two open panels are normal, and silently overwriting a calibration status or exposure is worse than a conflict. The revision check is the same one the dataset and trash mutations use.

**Use the thumbnail as the scientific preview.** Rejected: a 100-pixel JPEG has already lost the data. Scientific reads go through the asset path and the input-mode check, never through the preview cache.

## Acceptance criteria

- The library returns mixed asset and dataset rows in one page with a stable, explicit order and a total count.
- Every filter is applied before paging, and filter options reflect the observed values in the current library.
- A dataset row aggregates member count, cumulative exposure, and uniform-or-mixed calibration status without loading every member.
- A stale inline edit returns `409 REVISION_CONFLICT` and leaves the newer value intact.
- A manual edit records `manual` as the field's value source and is not overwritten by a later equipment refresh.
- A thumbnail or display-preview failure does not change asset availability or block a dataset.
- Dragging a dataset to the canvas records the dataset id and expands members only when the graph runs.
- A change token changes after an asset, dataset, membership, calibration, or trash mutation.

## Risks

- A mixed-row query with calibration aggregation and numeric filters is the most complex read in the library; it needs covering indexes and a query plan test at realistic row counts.
- The change token can be too coarse and refresh a large page for a one-row edit; it should be a cheap version, not a full ETag of the result.
- Inline editing many fields multiplies revision conflicts; the UI must preserve the user's draft while offering a reload.
- The frontend fork is frozen; the table, filter panel, and detail panel must fit its existing extension points rather than editing upstream components.
