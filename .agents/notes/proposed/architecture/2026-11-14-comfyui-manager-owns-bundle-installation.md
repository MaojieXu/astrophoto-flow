# Agent Note: The ComfyUI manager owns bundle installation

Status: proposed

English | [中文](2026-11-14-comfyui-manager-owns-bundle-installation.zh.md)

## Problem

The old workbench implemented its own bundle installation: it discovered releases, cloned a pinned Git tag, verified the manifest, ran the executable's version check, loaded the adapter, recorded an install receipt, and exposed install, prepare, uninstall, and upgrade through a native confirmation flow. The new project will adapt the official ComfyUI Manager instead. Keeping the old installer would duplicate repository discovery, dependency handling, update policy, confirmation, rollback, and security checks, and would create two incompatible sources of installation state.

The boundary is not obvious: the manager installs files, but the workbench decides which bundle versions a graph may run and which versions are still referenced. Both sides must agree on the installed directory, the validation result, and what happens when a bundle is removed while a graph or call still needs it.

## Proposal

The ComfyUI Manager fork owns installation. The workbench owns validation, registration, and execution.

### Manager responsibilities

The manager fork owns:

- repository and release discovery, including Git and the registry it supports;
- install, update, remove, and dependency installation;
- the user confirmation surface and its warnings;
- download, checkout, rollback, and partial-install cleanup;
- the installed directory and its files.

A bundle is installed as `custom_nodes/<package_id>/` with `bundle.json` at its root. The manager does not rewrite `bundle.json`, rename its fields, or merge it with manager metadata. Manager-specific repository information stays in the manager's own catalog, not in the bundle manifest.

The manager is enabled in the engine launch. Installed bundle directories are data for the workbench's validator; the engine does not import them as ComfyUI node modules. A bundle's `__init__.py` is a no-op marker, not a node registration.

### Workbench responsibilities

The workbench does not implement Git, release discovery, dependency installation, update policy, or install receipts. It does not expose install, update, uninstall, or prepare through HTTP, CLI, or MCP.

The workbench:

- scans `custom_nodes/*/bundle.json` at startup and after a manager operation;
- validates the directory against the bundle contract;
- records each bundle as `ready`, `invalid`, `incomplete`, or `unavailable`, with the failing field and descriptor hash;
- exposes the installed bundle catalog to the canvas and to graph validation;
- pins `package_id`, `bundle_version`, `host_api`, and descriptor hash in graphs and calls;
- refuses to run a graph whose pinned combination is not `ready`.

The workbench may expose a read-only `bundle_status` result and a link to the manager surface. It does not present an install button, a version dropdown, or a "prepare" action of its own.

### Removal and active references

Before removing or updating a bundle, the manager must ask the workbench for references. The workbench returns:

- saved graphs that pin the exact bundle version;
- active software calls using the bundle;
- receipts that have not reached a terminal state;
- any prepared runtime directory the call still needs.

If the workbench is unreachable, the manager refuses a destructive operation rather than guessing. If references exist, the manager shows them and requires an explicit confirmation; it does not delete files under an active call.

Removing a bundle never deletes library assets, datasets, graphs, or receipts. A graph that pinned the removed version becomes unavailable and refuses to run; it does not silently fall back to another version. Reinstalling the same `package_id` and `bundle_version` with the same descriptor hash restores the graph.

### Validation timing

The manager may install or update a directory while the workbench is running. The workbench validates after the manager reports completion, and again before a graph run. A partially written directory is `incomplete` and is not runnable. A bundle that was `ready` and then disappears becomes `unavailable`; an active call keeps its already-resolved paths and is allowed to finish or fail, but no new call starts.

The manager and workbench share one installed directory; neither keeps a second copy of the bundle files. The manager's catalog may remember available versions, but the workbench treats the filesystem and the validated descriptor hash as the facts.

## Alternatives considered

**Keep the old workbench installer and ignore the manager.** Rejected: it duplicates the manager's repository, dependency, update, confirmation, and rollback work, and the user has already chosen to adapt the manager.

**Wrap the manager behind a workbench install API.** Rejected: it creates a second API and a second confirmation surface for the same operation, and the workbench would still need to track manager state. A direct manager surface with a read-only workbench status is simpler.

**Let the manager also validate and register nodes.** Rejected: validation depends on the workbench's node schema, adapter contract, and graph pins. The manager should install files, not decide whether a graph may run.

**Let the workbench keep a release catalog and only use the manager to download.** Rejected: two catalogs drift, and the workbench would still own version selection and update policy. The manager owns the catalog; the workbench reads installed descriptors.

**Remove bundles without asking the workbench.** Rejected: a manager cannot know which graphs or calls still need a version, and deleting an executable under an active call turns a recoverable conflict into a failed run.

**Import installed bundle directories as ordinary ComfyUI custom nodes.** Rejected: the engine runs with custom nodes disabled, and a bundle's `__init__.py` is a manager marker, not a node implementation. Importing it would execute bundle code outside the adapter contract.

## Acceptance criteria

- The manager installs a bundle at `custom_nodes/<package_id>/` with `bundle.json` at the root.
- The workbench exposes no install, update, uninstall, or prepare operation through HTTP, CLI, or MCP.
- The workbench validates installed bundles at startup and after a manager operation, and records `ready`, `invalid`, `incomplete`, or `unavailable`.
- A graph pins `package_id`, `bundle_version`, `host_api`, and descriptor hash; an unavailable version refuses to run.
- Before removing or updating a bundle, the manager obtains the workbench's graph, call, and receipt references; if the workbench is unreachable, the manager refuses.
- Removing a bundle does not delete assets, datasets, graphs, or receipts.
- A partially installed directory is `incomplete` and is not runnable.
- An active call may finish with its resolved paths, but no new call starts after the bundle disappears.

## Risks

- The manager fork's API and directory conventions may change. The workbench must depend on `bundle.json` and the installed path, not on manager internals.
- Two state owners can still disagree about a version. The descriptor hash and the filesystem are the workbench's facts; the manager's catalog is advisory.
- A manager update can replace a bundle while the workbench is validating. The validator must read a stable snapshot and reject a directory that changes mid-read.
- The manager may install a bundle with missing Python dependencies. The workbench can only mark it `invalid` or `incomplete`; it must not run `pip` itself.
- The manager's confirmation may be weaker than the old workbench's install plan. The trust model and the warnings shown by the fork must be stated.
- Users may expect the workbench to repair or roll back a broken bundle. The workbench reports the failure and links to the manager; it does not own repair.
