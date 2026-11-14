---
name: astrophotoflow-doc-writing
description: Create, restructure, review, or audit AstroPhotoFlow Markdown documentation using audience-first hierarchy, one owner per fact, progressive user-to-developer detail, executed-operation fact-checking, bilingual pairing, and the repository's gates. Use for new or revised docs, docs-tree organization, documentation-quality audits, and wordcount budgets.
---

# AstroPhotoFlow documentation

## What this skill adds

The [documentation standard](../../../docs/AGENTS.md) owns the hierarchy, the writing rules, the budgets, and the slop checklist. This skill owns the procedure: how to establish what a page may say, where it belongs, and how it gets checked. Read both before writing; never restate a rule that has an owner.

## Workflow

Follow this sequence for each requested scope. Keep the common reader path brief, but do not delete failures, ownership, limitations, or other required contracts merely to reduce words.

1. Read the applicable `AGENTS.md` files, [the documentation standard](../../../docs/AGENTS.md), the target page, its source, and its bilingual record. For a decision page, read [the Agent Note rules](../../notes/README.md) instead: notes keep their own lifecycle.
2. Classify the page by one primary job and reader: product quick start, user task guide, contributor tutorial, architecture overview, subsystem reference, generated reference, agent instruction, or decision record.
3. Place the page at its nearest owner. Code-adjacent contracts stay beside the code that enforces them; cross-cutting learning belongs in `docs/`. A fact that already has an owner gets a link, not a copy.
4. Define the reader's starting state, observable outcome, likely failure, recovery path, and next useful depth before writing details.
5. Write the sections in reader order: orientation, then user-facing detail, then developer detail, with deeper material one link away.
6. Update the bilingual counterpart in the same pass. Keep headings, lists, tables, code, links, and physical line count aligned, then re-record the pair with `--write`.
7. Verify every claim against code, tests, generators, or a current decision owner — and run the operations the page instructs, per the fact-check procedure below. Update the owner before any derivative artifact.
8. Run `pnpm check`, then re-read the complete diff for correctness and, separately, for brevity and repository fit.

## Fact-check procedure: test, do not assume

Documentation states how the product behaves today, and the only admissible evidence for an operation claim is having run it. This procedure is mandatory for every new document and every new paragraph that claims an operation, command, default, error, or platform difference.

1. **Run every claimed operation against the current checkout.** Execute each CLI command and configuration snippet exactly as the document will show it; write down only what you observed, including the exact output, warnings, and failure modes. If a claim depends on a key or a network you do not have, say so and name the verification owner instead of asserting the behavior.
2. **Delete what you could not reproduce.** Never carry a command, field, default value, or behavior from memory, analogy, or a neighboring page. When a claim fails to reproduce, fix the claim — not the test.
3. **Read the code that enforces the rule.** A generated catalog or a schema is derivative: cite its source of truth, and never hand-edit it.
4. **Check the pre-edit state.** Before revising an existing page, read its current text and the change that made it stale; correcting prose against older prose is how a wrong fact survives.
5. **Re-record the pair after every edit.** Each paired edit re-runs `pnpm verify-translation-pairing --write <pair>` so the sidecar tracks the confirmed pair.

## Voice rules

- **Say what the subject does.** Describe outcomes, benefits, when to choose it, and the main cost — not its role, type, or internal identity. Omit source identifiers unless the reader uses them in configuration, a command, or a public API.
- **Explain, never enumerate.** Developer material covers the design concept, architecture, and dataflow well enough to understand how the subject works; link the code for exact detail instead of restating it.
- **Current state only.** Ordinary documentation describes the current repository. Decision records keep their own historical scope and say so.
- **Use controlled technical English.** One term per concept, explicit actor, one main action per sentence, modality and exceptions preserved. Do not force a shorter sentence when precision would fall.

## Quality criteria

- **Brief:** the common path contains only facts needed for its outcome; exhaustive truth stays one direct link away.
- **Intuitive:** prerequisites precede dependent concepts, one next action is obvious, and headings use terms readers search for.
- **Friendly:** readers can recognize success, understand risk before acting, recover from likely failure, and choose whether to continue deeper.
- **Accurate:** each durable claim has one owner and a verification path proportionate to its risk.
- **Agent-readable:** stable headings, terminology, ownership, and status support targeted retrieval without loading the corpus.
- **Newcomer-complete:** a professional engineer with no repository context can reconstruct the relevant architecture or feature through three to five linked pages.

Do not apply a universal word limit to exhaustive references. Measure entry-path length, unrelated material scanned for one lookup, largest section, and page size; split by an existing domain owner when retrieval cost is high.

## Audit the corpus

Read, do not re-summarize, the owning contracts: [docs/AGENTS.md](../../../docs/AGENTS.md), [the Agent Note rules](../../notes/README.md), [the bilingual pairing contract](../../../docs/i18n/README.md), and [root AGENTS.md](../../../AGENTS.md). Exclude `.agents/notes/archived/` from audits and edits — archived notes are frozen history.

Apply the standard's authoring order to every human-facing document in scope (not to Agent Notes): locate the document and state its own subject; set the permitted detail level and move deeper explanations to owning descendants with links; classify tutorial or reference from intended use, not path; split substantial mixed forms. Then check placement constraints: paired docs cost a counterpart update and a `--write` re-record on every edit; generated catalogs are never hand-edited; a move is atomic with every inbound link repaired in the same change.

After the structural pass, hunt the slop checklist with the cheapest probes first: grep distinctive phrases to find duplicated rules, replace hand-written inventories with their authoritative owners, and remove migration plans and future-tense spec language from implemented records. Measure outliers with `pnpm verify-doc-budgets --list`; if removing prose changes a promised behavior rather than its explanation, propose the behavior change first. Keep every load-bearing rule, preferably as one to three lines plus a link to its rationale.

## Wordcount budgets

`pnpm verify-doc-budgets` compares standing documents against ceilings in [scripts/doc-budgets.manifest.json](../../../scripts/doc-budgets.manifest.json); a red gate follows the ordered relocate-condense-raise policy in [docs/AGENTS.md](../../../docs/AGENTS.md#wordcount-budgets). Ceilings are guardrails, not reduction targets: at or below target, retain at least 5% headroom; raise a ceiling only when the words need the space, and justify the manifest diff.

## Validation

Validate the affected format, not merely Markdown syntax.

- Paired pages: `pnpm verify-translation-pairing --list`, then the scoped check; confirm structure, terminology, and link parity.
- Agent Notes: the note gates run inside `pnpm check`.
- Skills: frontmatter `name` matches the directory, and the description states when to use the skill.
- Every command a page instructs: re-run it before claiming it works.

Run `pnpm check` for the documentation gates and `pnpm check:full` to add typechecking and unit tests.

## Dev Note

None.
