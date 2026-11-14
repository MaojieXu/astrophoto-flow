# Workbench

The workbench serves one workspace at a time. Images stay where they were
imported, a dataset keeps its current member order, and an original file is
never rewritten.

## Services

The web page and the engine run as two long-lived services. The API service
owns the typed tools; the engine owns the queue, history, progress, and
cancellation entry.

- A registered software call appears as a canvas node.
- A preview is a view, not scientific input.
- A result is saved only on an explicit request.
