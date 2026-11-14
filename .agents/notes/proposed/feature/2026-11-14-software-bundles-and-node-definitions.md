# Agent Note: A software bundle is a pinned manifest, adapter, and node set

Status: proposed

English | [中文](2026-11-14-software-bundles-and-node-definitions.zh.md)

## Problem

The old workbench registered astronomy software as bundles: a package declared its executable, adapter, operations, node definitions, and localizations, and the canvas could place those nodes without embedding the software in the workbench. The new repository could hardcode a handful of Siril nodes, but then every new tool would require a code change, a graph would not record which software version produced a result, and an unregistered executable would become an invisible dependency.

A bundle also has to be installable by the ComfyUI Manager fork rather than by a second installer. That makes the package layout part of the contract: the manager installs a directory, and the workbench reads a manifest from it. An abstract "bundle" with no fixed file layout cannot be validated, pinned, or installed by either side.

## Proposal

One bundle is one installable directory. The ComfyUI Manager fork owns installation and removal; the workbench owns validation, registration, and execution. The directory layout is fixed:

```text
bundle.json
__init__.py
requirements.txt          # optional
adapter/main.py
operations/*.json
nodes/*.json
locales/en.json
locales/zh.json
app/...                   # optional executable payload
```

`__init__.py` is a no-op custom-node marker so the manager can treat the directory as a normal custom-node package. It exports `NODE_CLASS_MAPPINGS = {}` and `WEB_DIRECTORY = None`. The workbench never imports it as a ComfyUI node module; it reads `bundle.json` and the files it references.

### The bundle manifest

`bundle.json` is data, not executable code. It uses Bundle SDK v2 field names so an existing bundle can migrate without a second vocabulary:

```json
{
  "schema_version": 1,
  "package_id": "siril",
  "name": "Siril",
  "description": "Siril operations exposed as workbench nodes.",
  "bundle_version": "0.2.0",
  "release_channel": "stable",
  "software_version": "1.4.4",
  "platform": "windows-x86_64",
  "host_api": 2,
  "executable": "app/bin/siril.exe",
  "version_args": ["--version"],
  "version_output": "siril 1.4.4",
  "adapter": "adapter/main.py",
  "operations": ["operations/autostretch.json"],
  "nodes": ["nodes/autostretch.json"],
  "output_nodes": ["0e2f0e3a-6d4d-4f6e-9a4e-0f3a1b2c3d4e"],
  "commands": "commands.txt",
  "assessments": "assessments.md",
  "locales": { "en": "locales/en.json", "zh": "locales/zh.json" }
}
```

- `package_id` is stable and matches `^[a-z][a-z0-9-]*$`.
- `bundle_version` is a semantic version; a development build may use `X.Y.Z-dev.N`.
- `software_version` is the version of the external program, not the bundle.
- `platform` names the executable platform; the first supported value is `windows-x86_64`.
- `host_api` is the adapter API version. Version `2` is the adapter contract below.
- Paths are relative to the bundle root. Absolute paths, `..`, and paths that escape the root are invalid.
- `output_nodes` lists the node definition ids whose outputs may be registered as scientific results. Every id must appear in `nodes`.
- `commands` and `assessments` are optional documentation files; they never grant execution permission.

### Operation descriptors

Each `operations/*.json` file describes one software operation. An operation is the unit the adapter executes and the node binds to:

```json
{
  "operation": {
    "package_id": "siril",
    "version": "1.4.4",
    "operation_id": "autostretch",
    "name": "Auto stretch",
    "description": "Apply Siril's automatic histogram stretch.",
    "syntax": "autostretch",
    "scriptable": true,
    "cancel_supported": true,
    "calibration_effect": "none",
    "inputs": [
      {
        "name": "image",
        "type": "APF_SCIENCE",
        "formats": ["fits"],
        "cardinality": "one",
        "required": true,
        "supports_hdu": true,
        "supports_slice": false,
        "multiple_connections": false,
        "data_kind": "image",
        "colour_layout": "planar"
      }
    ],
    "outputs": [
      {
        "name": "result",
        "type": "APF_SCIENCE",
        "formats": ["fits"],
        "cardinality": "one",
        "required": true,
        "role": "image",
        "data_kind": "image",
        "colour_layout": "planar"
      }
    ],
    "parameters": [
      {
        "name": "linked",
        "kind": "boolean",
        "default": true,
        "advanced": false
      }
    ],
    "parameter_widgets": {}
  },
  "preview": {
    "kind": "science-image",
    "input": "image",
    "output": "result",
    "max_edge": 1024
  },
  "automatic_result_preview": true
}
```

`operation_id` is unique inside the bundle. Input and output names are unique and disjoint. `preview.input` must name a declared image input; `preview.output` must name a declared `APF_SCIENCE` output. `parameter_widgets` may add editor hints but cannot change a parameter's type or bounds.

### Node definitions

Each `nodes/*.json` file describes one canvas node. The node definition is the contract between the canvas, the service, and the adapter:

```json
{
  "definition_id": "0e2f0e3a-6d4d-4f6e-9a4e-0f3a1b2c3d4e",
  "source": "package",
  "name": "Auto stretch",
  "description": "Apply Siril's automatic histogram stretch.",
  "category": ["Siril", "Image"],
  "inputs": [{ "name": "image", "type": "APF_SCIENCE" }],
  "outputs": [{ "name": "result", "type": "APF_SCIENCE" }],
  "parameters": [
    {
      "name": "linked",
      "kind": "boolean",
      "default": true,
      "advanced": false
    }
  ],
  "execution": {
    "package_id": "siril",
    "operation_id": "autostretch",
    "inputs": { "image": "image" },
    "parameters": {
      "linked": { "kind": "parameter", "name": "linked" }
    },
    "outputs": { "result": "result" }
  },
  "localizations": {
    "zh": {
      "name": "自动拉伸",
      "description": "应用 Siril 的自动直方图拉伸。",
      "parameter_names": { "linked": "联动通道" }
    }
  }
}
```

- `definition_id` is a stable UUID. Renaming a node does not change it.
- Every input, output, and parameter name is unique; the three sets do not overlap.
- `execution.inputs` maps every node input to an operation input; `execution.outputs` maps every node output to an operation output.
- `execution.parameters` maps a node parameter either to an operation parameter (`kind: "parameter"`) or to a fixed value (`kind: "fixed"`). A fixed value is validated against the operation parameter schema.
- `localizations` covers every locale declared by the bundle. Missing names fall back to the bundle's default name, but a declared localization file must not contain an empty value.
- A parameter may be marked `advanced`, but it remains part of the same schema and the same saved graph.

### The adapter

`adapter/main.py` exports four callables:

```python
def build_plan(operation_id, sources, parameters, directory, **options):
    """Return a NamedProcessPlan for one invocation."""

def parse_result(operation_id, directory, plan, log_path):
    """Inspect the invocation directory and report produced outputs."""

def parse_progress(text):
    """Return a BundleProgress for one log line or chunk."""

def parse_failure(log_path):
    """Return a user-readable failure reason."""
```

`build_plan` returns a `NamedProcessPlan` with:

- `schema_version`: `2`;
- `arguments`: an argument list, never a shell string;
- `outputs`: a map from declared output name to `ProcessOutput`;
- `temporary_directory`: a directory inside the invocation directory;
- `thread_limit` and `environment`: optional process controls;
- `linear_sample`: optional declaration for linear input handling.

`ProcessOutput` names concrete `files` and glob `patterns`, each with a format, an optional minimum count, an optional `allow_empty`, and an optional frame count. `supporting_patterns` declares non-scientific files such as logs or reports. Every path is relative to the invocation directory or the bundle root; the adapter cannot write outside them.

The adapter receives resolved file paths and a temporary output directory. It never receives a database handle, a bearer token, or a shell. The workbench validates the plan before starting the process.

### Validation and registration

On startup and after every manager operation, the workbench scans installed bundle directories and validates:

1. `bundle.json` parses, uses a supported `schema_version`, and has a unique `package_id`.
2. Every referenced operation, node, adapter, locale, and documentation file exists inside the bundle root.
3. The executable exists, runs with `version_args`, and prints exactly `version_output` after whitespace normalization.
4. The adapter imports in an isolated namespace and exposes the four callables.
5. Every operation and node has a unique id; every node binding resolves to a declared operation, input, output, and parameter.
6. Every localization covers the declared operations and node names; unknown keys are rejected.
7. Every path in an operation, node, plan, or output pattern stays inside its allowed root.

A bundle that fails validation is listed as `invalid` with the failing field and is not placeable or runnable. A valid bundle is listed as `ready`; the workbench records `package_id`, `bundle_version`, `software_version`, `host_api`, and a hash of `bundle.json` plus every referenced descriptor. The manager may reinstall or update the directory; the workbench revalidates before the next graph run.

### Pinning and results

A graph node stores `package_id`, `bundle_version`, `host_api`, `definition_id`, and the descriptor hash. Opening a graph whose exact combination is unavailable shows the node as unavailable and refuses to run it; it never substitutes the latest version.

A call freezes the operation id, input assets or datasets, parameter values, software version, bundle version, adapter hash, and prompt id. The adapter writes only into the invocation directory. A successful output is registered through normal intake: it receives a new asset id, a hash, and provenance links to the call, inputs, bundle version, and parameter snapshot. An output that is only downloaded is an export, not an asset.

## Alternatives considered

**Hardcode the Siril nodes in the workbench.** Rejected: every new tool would require a code change, the software version would be hidden in the binary, and a result could not name the adapter that produced it.

**Keep the old abstract manifest with a free-form file list.** Rejected: it cannot be validated or installed by the manager, and two bundles could describe the same operation with incompatible field names. The fixed layout and Bundle SDK v2 fields make the contract checkable.

**Let each bundle define its own installation format.** Rejected: the manager would need a plugin per bundle, and the workbench could not tell an installed bundle from a random directory. One layout is enough for the first version.

**Let the workbench install and update bundles.** Rejected: it duplicates the ComfyUI Manager fork, creates a second source of installation state, and forces the workbench to implement Git, dependency, and rollback behavior. Installation belongs to the manager.

**Accept arbitrary node types from the engine.** Rejected: a graph could execute an unregistered command or import path. Only a validated bundle manifest or the engine's built-in catalog may contribute executable node types.

**Run every adapter in a container.** Rejected for the first version: it adds a runtime dependency and a filesystem-mapping problem while the real software is already a native process. Isolation can be added behind the adapter later.

## Acceptance criteria

- A bundle directory has `bundle.json`, an adapter, operation descriptors, node descriptors, and locale files in the fixed layout.
- `bundle.json` validates against Bundle SDK v2 and resolves every referenced file inside the bundle root.
- Every node binding resolves to a declared operation, input, output, and parameter; every output node is declared in `output_nodes`.
- The executable's `version_args` output matches `version_output`; a mismatch marks the bundle invalid.
- The adapter exposes `build_plan`, `parse_result`, `parse_progress`, and `parse_failure`.
- A graph records `package_id`, `bundle_version`, `host_api`, `definition_id`, and the descriptor hash.
- An unavailable version is shown as unavailable and refuses to run; it is never silently replaced.
- A result is registered through normal intake with provenance to the call, inputs, bundle version, and parameters.

## Risks

- A bundle adapter executes third-party software. Validation and the manager's confirmation reduce the risk but do not sandbox it; the trust model must be stated.
- The fixed layout may not fit software that needs multiple executables or a non-Python adapter. The first version accepts one executable and one Python adapter; a later version can add an adapter kind without changing the node schema.
- Bundle SDK v2 field names carry old assumptions. Reusing them reduces migration work but may preserve a field that no longer has a meaning; each field must be either implemented or rejected.
- The manager may install a directory while a graph is running. The workbench pins versions and revalidates before the next run; it must not swap a module under an active call.
- Localization coverage can lag new operations. Missing keys must fail validation rather than silently showing English in a Chinese UI.
- The descriptor hash covers files, not the executable's behavior. A replaced executable with the same version string is still trusted until the manager or user revalidates it.
