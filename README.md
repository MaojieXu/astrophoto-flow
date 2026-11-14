# AstroPhotoFlow

English | [中文](README.zh.md)

AstroPhotoFlow is a local astronomy imaging workbench driven from the browser: it keeps image assets and datasets, registers real astronomy software as canvas nodes, and lets you assemble, run, inspect, and save results on a native canvas. People work in the web app, scripts drive the CLI, and external agents use the platform MCP server, which orchestrates and queries but never executes a graph.

This repository holds the layer those rules live in. The product source tree is not in place yet: the rewrite starts from the process the code has to satisfy.

## What is here

- `AGENTS.md` — standing orders for agents working in this repository.
- `.agents/notes/` — the decision corpus, its lifecycle rules, and the frozen archive.
- `.agents/skills/` — the procedures that keep notes, documentation, and translations consistent.
- `docs/AGENTS.md` — the documentation standard; `docs/i18n/` — the bilingual pairing contract.
- `scripts/` — the gates that check all of the above.

## Checks

Install dependencies once, then run the gates:

```sh
pnpm install
pnpm check
pnpm check:full
```

`pnpm check` runs the documentation, notes, and pairing gates; `pnpm check:full` adds typechecking and unit tests. Each failure names the rule it enforces.
