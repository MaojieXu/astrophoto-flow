# Licensing

English | [中文](licensing.zh.md)

This repository is released under **GPL-3.0-only**. Every component carries that license, including the MCP server, which could be licensed differently because it runs as a separate process and contains no engine code. One license across the repository removes per-directory arbitration.

| Component | SPDX | Why |
|---|---|---|
| Workbench service | `GPL-3.0-only` | our code, distributed together with a derived engine |
| MCP server | `GPL-3.0-only` | independent process; same license for simplicity |
| Engine fork | `GPL-3.0-only` | derived from ComfyUI |
| UI fork | `GPL-3.0-only` | derived from ComfyUI_frontend |
| Engine shell | `GPL-3.0-only` | runs inside the engine process |

## Upstream works

Both upstreams are forked: their sources live in this repository and this project carries modifications on top of the pins below. The pins name the release each fork was last merged against.

| Upstream | Version | Commit | License |
|---|---|---|---|
| ComfyUI | 0.42.0 | `1a82e6d01f395b43275c77acd289af1eb7090bb9` | `GPL-3.0-only` |
| ComfyUI_frontend | 1.57.1 | `c875ee420aa027a359b2953361eb3b356b7bef00` | `GPL-3.0-only` |

ComfyUI-Manager and comfy-cli were evaluated and are not redistributed.

## Recording modifications

GPL-3.0 section 5(a) requires a changed file to state that it changed and when. A modified upstream file carries a `Modified: <date> — <what changed>` line in its header; where the format makes a header impossible, the change is recorded below. New files added next to upstream code need no such notice, because they are not modifications of an existing file.

| Date | Fork | Change |
|---|---|---|
| 2026-11-14 | Engine + UI | Reduced the engine to an image core and removed the model runtime, routes and dependencies; removed the model-library, assets and global-blueprint UI. Full entries: `src/workbench/upstream.lock.json`. |
| 2026-11-14 | Both | Updated tests and the boundary gate. |

## What a release must carry

A release tag names one commit. Its tree must contain the exact sources the published artifacts were built from — the engine fork, the UI fork, and the workbench — because recipients may request the source of the version they received. Third-party dependencies keep their own licenses; `LICENSE` does not replace them.
