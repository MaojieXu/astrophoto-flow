# Bilingual documentation

English | [中文](README.zh.md)

Both people and agents read this repo's documentation, so every document in scope is maintained in English and Simplified Chinese. This page defines the pairing contract, the gate, scope, and exclusions; [translation-rules.md](translation-rules.md) defines how to translate; [terminology.md](terminology.md) is the terminology source of truth. Routine agent work follows the lightweight path in [docs/AGENTS.md](../AGENTS.md); the extended [.agents/skills/astrophotoflow-translate](../../.agents/skills/astrophotoflow-translate/SKILL.md) workflow is available only through explicit user invocation.

## The pairing contract

- **Both languages carry equal authority.** A document may be authored and reviewed in either language first — a Chinese-first Agent Note is as legitimate as an English-first one — and the counterpart is translated from it. Neither file outranks the other; what binds them is that they must say the same thing.
- **A pair is three sibling files.** The English `foo.md`, the Chinese `foo.zh.md`, and a consistency record `foo.i18n.yaml`, all in the same directory. No locale directories, no separate translation repo, no interleaved bilingual files. Pairs merge whole: a change never lands one language without the other two files.
- **The consistency record.** `foo.i18n.yaml` holds one entry per heading section that still contains language-specific content. The key is the section's English heading-slug path (`/` for text before the first heading; a repeated path gets `~2`, `~3`, …), and the entry holds a hash of the English and of the Chinese blocks in that section that differ between the two sides:

  ```yaml
  /foo:
    en: 41d772192075e133
    zh: dda91c6c670cfd9d
  /foo/usage:
    en: 86940bea4a3c7ed6
    zh: de78429597783c7f
  ```

  Section `i` of one side corresponds to section `i` of the other. Each side's hash covers every top-level block of the section except fenced code blocks, the kind of content the gate already requires to be identical on both sides; content that merely happens to be identical is still hashed. A section with no remaining blocks has no entry. Editing a code block on both sides leaves the record unchanged, and edits to different sections change separate record lines, so Git's default text merge, including GitHub's, composes them. A record conflicts only when both branches changed hashed content in the same section; resolve the Markdown and re-record the pair. An out-of-sync pair is updated by patching the counterpart minimally against the edited side's diff, never by re-translating whole files; the gate names each changed section. After bringing the pair back in line, `pnpm verify-translation-pairing --write <pair>` re-records the entries; that YAML diff is the reviewable act of confirming consistency, which is why `--write` requires naming the pairs you confirmed (`--write --all` is the explicit corpus-wide form).

  The Chinese file must retain its English backlink; the English source must retain its Chinese link. Hash keys come from English headings, so renamed Chinese headings never break the record.
- **Language switcher.** The Chinese file always links back immediately after its H1 heading with `[English](foo.md) | 中文`, and the English source reciprocates there with `English | [中文](foo.zh.md)`.
- **Structure mirrors the counterpart.** Heading depths and order, list kinds, ordered-list starts, list item counts, table row and column counts, semantic link targets with exact query/fragment suffixes, and verbatim code blocks match one to one across the pair. When a relative document link targets the active bilingual corpus, the English side uses its `.md` path and the Chinese side uses its `.zh.md` path. A missing counterpart in that corpus is a pair-completeness error rather than a fallback; targets outside the active corpus keep the authored path. See [translation-rules.md](translation-rules.md) for the full preservation rules. The repository's Markdown conventions apply to `.zh.md` files unchanged.

## The gate: verify-translation-pairing

`pnpm verify-translation-pairing` enforces the contract mechanically:

1. Every document in scope has a complete pair.
2. Every pair artifact that exists at all is complete and consistent: all three files present, the record is canonical and its entries equal the entries computed from the current contents (changing language-specific content on either side without re-confirming the pair goes red), the Chinese side and the English source carry their language switchers, every ordinary relative document link uses its source side's target locale, and the structural signatures match in order — heading depths, verbatim code blocks (info string and content), table row and column counts, list kinds, ordered-list starts, item counts, and semantic link targets with exact query/fragment suffixes apart from the switcher.
3. Files listed as `excluded` have no `.zh.md` and no `.i18n.yaml` at all. Frozen Agent Notes under `.agents/notes/archived/` are outside this evolving gate; their dedicated verifier requires and seals the complete existing triplet instead.

`pnpm verify-translation-pairing --list` prints the current pairing state of every document in scope — missing, out-of-sync, or ok. It never fails; `missing` and `out-of-sync` rows identify violations that the normal check rejects.

`pnpm verify-translation-pairing <pair...>` checks just the named pairs — any of a pair's three files (or its bare stem) names it — so an update loop verifies its own pair in seconds instead of re-scanning the corpus. The no-argument corpus-wide form is what a full documentation check runs; a scoped green never substitutes for it.

The practical rule this gate creates: **when a change edits either side of a paired document, the same change updates the counterpart directly in one terminology-guided pass and re-records the pair with `--write <pair>`.** A change that leaves a pair out of sync goes red.

The gate's limit, stated plainly: **a green gate means the pair was confirmed consistent at these exact contents, not that the confirmation was sound.** It checks hashes and Markdown structure; it cannot judge whether the two sides say the same thing, or whether the wording is accurate, well-termed, and natural — that is the reviewer's half of the contract, per [translation-rules.md](translation-rules.md). A re-recorded pair with a sloppy counterpart passes the gate; it must not pass review.

## Scope and exclusions

**Scope**: every `README.md`, every document under `docs/**`, and every active Agent Note under `.agents/notes/**`. Dependency and ignored build-output trees and the frozen `.agents/notes/archived/` tree are discovery exclusions, not evolving translation source.

**Excluded** (never paired, and the gate rejects a `.zh.md` or `.i18n.yaml` for them):

- Root `AGENTS.md`, `docs/AGENTS.md`, and `.agents/notes/**/AGENTS.md` — agent instructions, maintained in English only.
- [terminology.md](terminology.md) — bilingual by construction.
- `.agents/notes/archived/` — frozen historical triplets. [`verify-archived-agent-notes`](../../scripts/verify-archived-agent-notes.ts) validates their completeness and content seals; translation maintenance must never rewrite them.

**Universal requirement**: every current or future document in scope merges as a complete bilingual pair. [`translation-pairing.manifest.json`](../../scripts/translation-pairing.manifest.json) contains only explicit exclusions; there is no per-file rollout list, date cutoff, or README-specific policy class.

## Division of labor

Routine counterparts are updated directly by the working agent in one pass after it loads [terminology.md](terminology.md); it does not invoke a translation skill, run a separate translation-review pass, or delegate to a subagent. The extended [astrophotoflow-translate](../../.agents/skills/astrophotoflow-translate/SKILL.md) skill owns the staged procedure for explicit user invocation. For a first draft of a whole document, [pipeline.md](pipeline.md) describes the scripted route; reading the diff and recording the pair stay manual. The gate checks pair completeness, recorded hashes, switchers, link locale, and its documented structural signature; review still owns translation quality, terminology, and the structural requirements that the signature does not encode.
