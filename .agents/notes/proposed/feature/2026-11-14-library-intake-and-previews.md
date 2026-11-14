# Agent Note: Import fixes identity before it copies

Status: proposed

English | [中文](2026-11-14-library-intake-and-previews.zh.md)

## Problem

An import is the only moment when a file's identity, metadata, and library location are decided. The old repository split that moment into enumeration, registration, content copy, metadata parsing, and preview generation, but its task record, preflight token, and resume rules were spread across several modules. The new repository has no import pipeline yet, and a naive implementation would either copy first and assign an id later, or wait for every preview before showing anything. Both make partial failure expensive: a copied file with no id cannot be retried safely, and a batch that hides successful assets because one preview failed looks like data loss.

## Proposal

Import is an asynchronous task over an immutable source list. The task enumerates, registers identity, copies and verifies content, parses metadata, and generates previews as separate stages. A failure in a later stage never erases an earlier success.

### Entry points

The library accepts files and one folder level. A selected folder contributes its immediate files; it does not recurse, and it does not require a pre-authorized root. The local backend can read a native path, and the browser can upload file bytes to a staging area; both produce the same task and the same asset record. A browser upload is not a second library: staged bytes are copied into the managed library and the staging copy is deleted after publication.

### Preflight

Before a task starts, the service enumerates the selection, checks extensions and readable headers, sums byte sizes, groups files by classification, and returns a review payload with a short-lived `review_token`. The token binds the exact source list, classification, dataset intent, and import defaults the user confirmed. Submitting with a different list or a changed source requires a new preflight. The CLI may skip the interactive confirmation, but it still receives the same review payload and token.

### Task stages

A task moves through `queued`, `running`, `cancelling`, `completed`, `completed_with_errors`, `failed`, `cancelled`, and `interrupted`. Each item moves through four stages:

- **enumerate**: resolve the source, record size and modification time, reject unsupported formats;
- **register**: assign `asset_id`, read header metadata, and publish a pending asset with `availability = missing`;
- **content**: stream the source into a staging file, compute BLAKE3, recheck size and modification time, and atomically publish the library copy;
- **metadata and preview**: parse FITS/XISF headers and generate the 100-pixel thumbnail.

Registration before content is deliberate: a failed copy leaves a known asset id that can be retried, not an orphan file. The asset becomes `available` only after the content stage commits. Content and preview failures are reported separately; a preview failure does not block the asset.

### Source freeze and duplicates

The accepted size and `mtime_ns` are the source contract. The content stage rechecks both before and after the copy; any change aborts that item with `SOURCE_CHANGED` and leaves no partial library file. Duplicate detection is limited to the current task: the same source path twice is skipped as `DUPLICATE_SOURCE`. There is no global hash dedupe, because two imports can carry different classification or dataset intent.

### Formats and metadata

The importer recognizes FITS (including fpack), XISF, NumPy arrays, common raster images, camera RAW, and video/SER containers. The exact extension list lives in one module and is exposed by the preflight. FITS and XISF headers are parsed with a versioned parser; an unreadable header marks `metadata_status = failed` but does not unpublish the asset. Classification is never guessed from the filename: the precedence is manual value, then file observation, then frozen import preset, then `unknown`.

### Previews

Every asset gets a 100-pixel longest-edge JPEG thumbnail. Dataset rows reuse the first member's recipe as a group thumbnail. Display previews and FITS HDU views are generated on demand, never used as scientific input. A preview failure is recorded and retryable; it does not change the asset's availability or block a dataset.

### Cancellation, resume, and retry

Cancel stops the current item and lets completed items stand. Resume continues the same task from the first incomplete item. Retry creates a new task with `retry_of_task_id` and reuses the existing asset id when the original was registered but never published. A caller-supplied `request_id` makes retries idempotent: the same request returns the same task instead of starting a second copy.

### Report

The task report separates `registration`, `content`, and `preview`. Each item reports its stage, status, bytes copied, hash result, and error code. A batch is complete only when every item has a terminal stage result; "registration finished" is not "import finished".

## Alternatives considered

**Import synchronously in the request.** Rejected: a large capture takes minutes, the browser times out, and a dropped connection leaves the caller unable to learn whether the copy happened. The task record is the only safe way to reconcile.

**Copy first and assign the id after success.** Rejected: a failed copy leaves an untracked file, and a retry cannot tell whether the bytes on disk belong to the same import. The early id is what makes retry and trash safe.

**Wait for previews before publishing the asset.** Rejected: previews are derived data. A corrupt thumbnail should not hide a valid original or block a dataset that only needs the file.

**Deduplicate globally by content hash.** Rejected: identical bytes can be imported twice with different classification, equipment snapshots, or dataset destinations. Global dedupe would silently merge those intents and make deletion ambiguous.

**Watch a folder instead of importing.** Rejected: a watcher cannot distinguish a finished copy from a file still being written, cannot ask for classification, and creates assets without a user decision. Folder watching can be added later as a producer of import tasks, not as a second ledger.

**Use reference imports for large files.** Rejected by the managed-copy decision: the library must own its bytes. A reference import would reintroduce missing drives and external edits.

## Acceptance criteria

- A batch of files and one folder level produces one task and one asset per accepted file; no subdirectory is traversed implicitly.
- Every item reports registration, content, and preview outcomes separately, including bytes copied and error codes.
- A source changed between preflight and copy fails with `SOURCE_CHANGED` and leaves no published asset or partial library file.
- A preview failure leaves the asset available and the dataset importable.
- Cancelling a task keeps completed assets; resuming continues from the first incomplete item; retrying does not create a second asset id for the same item.
- The same `request_id` returns the same task, and the same source path twice in one task is skipped as `DUPLICATE_SOURCE`.
- The browser upload path and the native path produce identical asset records.
- No import stage writes outside the staging area and the managed library.

## Risks

- A format matrix that includes RAW, video, and fpack makes header parsing and thumbnail generation uneven; the preflight must report "accepted but preview unsupported" rather than failing the asset.
- Hashing while copying is CPU- and I/O-heavy on large batches; concurrency defaults must stay conservative and be configurable per workspace.
- Antivirus scanners and network shares can hold a staging file open after the copy; atomic publication needs retries and a clear `COPY_FAILED` state.
- Browser uploads duplicate bytes temporarily; a crashed upload must be cleaned by the staging sweeper, not left as a hidden second library.
