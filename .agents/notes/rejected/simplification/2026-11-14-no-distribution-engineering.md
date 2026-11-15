# Agent Note: Stop before the distribution layer

Status: rejected — Superseded by [Windows agent delivery](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.md).

English | [中文](2026-11-14-no-distribution-engineering.zh.md)

## Problem

The previous design carried a distribution layer: a wheel with a 13 MB engine archive inside, a console script, an npm launcher, a `bootstrap` tool that owned a runtime fingerprint, `doctor` and `upgrade` tools beside it, and CI to prove the wheel installed. None of it had a reader. One person runs this product on one machine, from a checkout, and pays for the layer on every dependency change: a rebuild, a version bumped in two manifests, a fingerprint that fails because a wheel moved.

## Proposal

Installation uses a clone and the locked dependency commands in the [development reference](../../../../docs/development.md): one backend uv environment, the frontend pnpm workspace, and the root pnpm workspace containing MCP. The workbench controller owns process startup; `python main.py` alone starts the engine, not the business API or retrieval process. The repository needs no wheel configuration for our package, installer launcher, runtime fingerprint, bootstrap tool or CI workflow. A Windows startup guide must be verified against the integrated controller before it claims a complete first call.

The gates stay: they are the part of the old machinery that pays for itself, and they run locally in seconds. The distribution layer is not the gates; it is the packaging of them for other people.

If a release is ever needed, the cheapest honest shape is a release archive plus a documented sha256, not a package ecosystem.

## Alternatives considered

**PyPI wheel plus `uv tool install`.** This was the previous design. Rejected: a 22 MB wheel carrying a 13 MB archive, a runtime prepare step, and a console script, all to remove a clone.

**An npm launcher that downloads the engine and boots everything.** Rejected: it installs a Python toolchain from Node, doubles the ecosystems to keep in step, and fails in the worst way — the launcher succeeds, the runtime does not.

**An `install.ps1` one-shot script.** Rejected as a second code path that restates the README; scripts rot faster than prose and cannot be read by the person deciding whether to trust the install.

**A container image.** Rejected: it does not remove the engine's own install, GPU passthrough on Windows is the hard part, and the product already assumes a local machine.

**CI on every push.** Deferred rather than rejected: gates run locally and one person is the only committer. A workflow earns its place when a second contributor appears or a branch must not merge unverified.

## Acceptance criteria

- On a machine with only git, uv, and pnpm, the README steps produce a running workbench and one real call.
- The repository contains no packaging configuration for our package, no launcher, and no CI workflow.
- After an install, `git status` shows only ignored artifacts.

## Risks

- Nobody else can try the product without a toolchain; the README path is the whole onboarding.
- A future release means doing the packaging work from zero, including the parts that were already solved once.
- Windows without uv leaves a manual step the README does not yet cover.
