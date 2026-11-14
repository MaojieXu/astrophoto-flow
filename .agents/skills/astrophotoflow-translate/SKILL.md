---
name: astrophotoflow-translate
description: Manually run the extended AstroPhotoFlow bilingual-document workflow, including whole-document translation, minimal counterpart updates, and scoped pairing verification.
disable-model-invocation: true
user-invocable: true
---

# Translating AstroPhotoFlow docs

## Invocation boundary

Run this extended workflow only when the user explicitly invokes `astrophotoflow-translate` by name. Never select or load it for ordinary documentation work, from another skill, or from an inferred translation need; routine translation follows the one-shot, one-pass rule in [docs/AGENTS.md](../../../docs/AGENTS.md) — load [terminology.md](../../../docs/i18n/terminology.md), update both sides in one pass, re-record.

## What this skill is

**This skill is guidance, not a translation memory.** It is the workflow map for keeping `foo.md ↔ foo.zh.md` pairs consistent and natural in both languages. Both languages carry equal authority — a change is authored in either one, and that side is the source for that update. You are the translator: the rules say what must hold, not how to phrase any particular sentence — phrasing judgment is yours, terminology is not.

## Triage by change type — this decides everything else

- **Update** (pair exists, one side edited): follow [the update path](#the-update-path). Never re-translate a whole document to apply an update — a minimal update preserves the reviewed phrasing of everything that did not change; a re-translation throws that review away.
- **New pair** (no counterpart yet): follow [the whole-document path](#the-whole-document-path-new-pairs).
- **Deleted or renamed doc**: delete or rename the counterpart and the `.i18n.yaml` alongside it — the gate reports an incomplete pair otherwise.

Frozen Agent Notes under `.agents/notes/archived/` are not translation work. Their complete triplets are sealed by the archive verifier; never update, re-record, or repair either side after archival.

## The update path

1. **Read the authored diff**, not the whole document: `git diff <authored side>` since the last re-record gives the units that moved.
2. **Mechanical-only change? Apply it directly.** When every change lies inside code fences that the pair shares byte-identically, splice the edited fences into the counterpart and confirm structure with the scoped check — no hand-editing needed.
3. **Prose change? Edit the smallest unit that covers it.** Preserve the reviewed phrasing of everything the diff does not touch, then verify the changed hunks clause by clause against the source: nothing added, nothing dropped, terminology per the table, code spans verbatim.
4. **Whole-document change?** When both sides changed in ways that no longer align unit by unit, treat it as a new pair and reconcile under [translation-rules.md](../../../docs/i18n/translation-rules.md).
5. **Record and verify, scoped**: `pnpm verify-translation-pairing --write <pair>`, then `pnpm verify-translation-pairing <pair>`. `--write` names exactly the pairs you confirmed — it refuses to run bare, so a bulk re-record is always an explicit `--all`. The corpus-wide check runs in `pnpm check`, not inside each translation task.

## The whole-document path (new pairs)

The orchestrating agent may delegate this pass to a subagent holding the pair paths; the translator reads the sources of truth first, then translates section by section, keeping each section's structure locked to the source as it goes rather than fixing structure at the end.

### The script-driven variant

When the user prefers a machine draft, `pnpm translate <source.md>` assembles this same reviewed prompt, writes the counterpart, and records the run under `.artifacts/translations/`; [pipeline.md](../../../docs/i18n/pipeline.md) lists the commands and the credential variables. Read the result against the source, fix what the model got wrong, then record with `--write`. A machine draft is never the confirmation, however clean the gate looks.

### Sources of truth (read, don't re-summarize)

- **[docs/i18n/README.md](../../../docs/i18n/README.md)** — the pairing contract: the three-file pair (`foo.md`, `foo.zh.md`, `foo.i18n.yaml`), the consistency record's per-section hashes, the language-switcher lines, scope, and exclusions.
- **[docs/i18n/translation-rules.md](../../../docs/i18n/translation-rules.md)** — how to translate: faithfulness, structure preservation, terminology discipline, typography (MUST/SHOULD levels).
- **[docs/i18n/terminology.md](../../../docs/i18n/terminology.md)** — the terminology table, binding in both directions. Load it BEFORE translating, not when a term feels uncertain; the terms you do not notice are the ones that drift.
- **[astrophotoflow-prose-standard](../astrophotoflow-prose-standard/SKILL.md)** — required prose coverage and editorial judgment. Apply it to both sides without adding or dropping source propositions.

### Translate

- **Pass 1 — write, don't transpose.** Read a semantic unit, then restate it as a native technical author in the target language's register. Preserve the required frame without forcing sentence-by-sentence correspondence.
- **Pass 2 — verify against the source, clause by clause.** Fidelity is checked here, not written in: confirm nothing was added or dropped, every term follows the table, and each code span survived verbatim. Fix by rewriting the sentence natively, not by patching words into it.
- **Read the completed counterpart alone.** After the source comparison, read the translated file without the source beside it and rewrite phrasing whose awkwardness only becomes visible in isolation.
- Write only the final text to the file, never drafts or notes.
- Every term in [terminology.md](../../../docs/i18n/terminology.md) renders exactly as specified: for a Chinese target, use the Chinese and first-occurrence columns; an unlisted term needs a citable Chinese OSS/vendor precedent or stays English under 「待定术语」. For an English target, use the English column and an established English technical term; preserve an ambiguous source term with a short gloss and list it as pending. Never invent a rendering inline.
- Code blocks are byte-identical across the pair, comments included. Repository-relative document links keep the same semantic target and exact query/fragment suffix: targets in the active bilingual corpus use `.md` on the English side and `.zh.md` on the Chinese side, a missing in-scope counterpart is an error, targets outside the corpus keep their authored path, and the switcher remains the cross-locale exception.
- The pairing gate checks heading depths, fenced blocks, table row and column counts, list kinds, ordered-list starts, list item counts, link locale, and semantic targets. Manually verify list and table order, noncanonical list numbering, inline code, emphasis, meaning, terminology, and tone.

## Find the work

- `pnpm verify-translation-pairing --list` prints every in-scope document as missing / out-of-sync / ok. Missing and out-of-sync rows are contract violations; the normal check rejects them.
- In a change that edits paired docs, the work list is the diff itself: every changed side of a pair needs its counterpart updated and the pair re-recorded in the same change, and the gate goes red if you forget.

## Finish the pair

1. Switcher: `[English](foo.md) | 中文` immediately after the Chinese file's H1, `English | [中文](foo.zh.md)` after the English file's H1 — add both if this is a new pair.
2. Record consistency: `pnpm verify-translation-pairing --write <pair>` recomputes and records the per-section hashes in `foo.i18n.yaml`. The yaml diff is the reviewable statement "I confirmed these two say the same thing" — only run it after you actually have.
3. No manifest entry is needed for an ordinary document: every in-scope source requires a pair. Change [scripts/translation-pairing.manifest.json](../../../scripts/translation-pairing.manifest.json) only when the owning policy documents a genuine bilingual-by-construction exclusion.
4. Before finishing: the touched pairs are green under the scoped check, and `pnpm check` is green once for the whole change.
5. Keep the change reviewable: state which pairs are new versus minimally updated and list 「待定术语」 prominently.

## How to respond to translation review

Evaluate each comment on its merits. For terminology comments, remember the terminology table is the contract — apply a reviewer's rendering decision to [terminology.md](../../../docs/i18n/terminology.md), not only to one file.
