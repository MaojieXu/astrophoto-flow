# Agent Note: Keep the frontend fork verbatim and freeze it

Status: proposed

English | [中文](2026-11-14-freeze-the-frontend-fork.zh.md)

## Problem

The frontend is a full copy of ComfyUI_frontend 1.57.1: 4507 files identical to upstream, 104 changed, 69 added. Those 173 files carry about 30 imports that will not survive an upgrade, because upstream moved shared components into `@comfyorg/design-system` and the API client into `@comfyorg/api-client`. Following upstream therefore costs a re-port per release, and nothing in the repository records what the changes were for.

## Proposal

Keep the fork as a verbatim copy at a pinned commit and do not track upstream. Shrink the diff from the inside instead: wherever an extension point covers a change, move that change into `src/platform/astrophotoflow/` and leave the upstream file alone. The four extension points to verify on 1.57.1 are graph read and write, sidebar tabs, node definition refresh, and execution status. If all four work, the diff keeps shrinking; if the graph or the sidebar turns out to be unreachable, the fork stays frozen as it is and we stop pretending it can shrink.

Pure business UI belongs in `packages/astrophotoflow-ui/`; host integration belongs in `src/platform/astrophotoflow/`. Pinia keeps native and local UI state, Vue Query keeps business-service data and cache, and the generated OpenAPI client uses Zod validation. Tailwind CSS and the existing PrimeVue/design-system components supply the controls. The [native-canvas proposal](../architecture/2026-11-14-native-canvas-and-service-receipts.md) keeps saving, drafts and undo in ComfyUI instead of introducing another editor or graph store.

## Alternatives considered

**Track upstream and re-port each release.** Rejected: 30 broken imports per upgrade for no user-visible gain; our changes are integration, not editor features, and upstream has no reason to carry them.

**Replace the fork with a thin extension over an upstream build.** This is the right end state, and it is rejected only as a first move: the four extension points are unverified, and an extension that cannot reach the graph or the sidebar is not a product.

**A submodule with local patches.** Rejected: patches over 173 files rot as upstream moves, and a full copy plus a recorded modification list reconstructs the tree without introducing a second mechanism for the same job.

## Acceptance criteria

- All four extension points work on 1.57.1 without editing an upstream file.
- Our code sits under `frontend/src/platform/astrophotoflow/`; the remaining changed-plus-added file count is below today's 173 and falls with each change we migrate.
- `frontend/` has no build step of ours; the build is upstream's plus our directory.

## Risks

- Security and browser-compatibility fixes never arrive, and a Chromium change can break the editor with no upstream to merge.
- An upstream bug we hit has to be fixed in the fork and remembered, which is what the modification list is for.
- The cost of migrating to a thin extension in three years is unknown and larger than today's, since the diff will have grown.
