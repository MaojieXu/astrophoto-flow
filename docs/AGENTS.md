# AGENTS.md — The documentation standard

This file defines document structure, Markdown tiers, writing rules, and budget ceilings. Use [astrophotoflow-doc-writing](../.agents/skills/astrophotoflow-doc-writing/SKILL.md) for placement and validation, and [astrophotoflow-prose-standard](../.agents/skills/astrophotoflow-prose-standard/SKILL.md) for required coverage and editorial judgment.

## Document structure

These rules apply to human-facing documentation; [Agent Notes](../.agents/notes/README.md) remain outside their scope. A document's subject and tree position fix its scope: describe its own subject at appropriate detail and direct children only by purpose, responsibility, and high-level behavior; link to the owning descendant for lower-level detail. Document type does not widen that scope. A reference may be exhaustive only about its own subject. Testing mechanisms, fixtures, and harnesses belong at the lowest owning level; higher documents link there.

Classify every in-scope document as a tutorial or reference. Tutorials follow an ordered path to an outcome and introduce only what each step needs. References define a lookup scope and current behavior without a teaching sequence. Separate substantial tutorial and reference content; label a section when either part is small.

Before writing a tutorial, privately classify the reader's starting knowledge and each concept as beginner, intermediate, or advanced. Establish prerequisites before dependent concepts, increase difficulty gradually, and move unnecessary advanced material to a later tutorial or reference.

Author in this order: locate the document in the tree; set its permitted detail; choose tutorial or reference; for a tutorial, order concepts by prerequisite and difficulty; relocate descendant-owned detail; replace lower-level explanations with links to their owners.

## The tier taxonomy: one home per fact

Each fact has one home: the tier whose job it is; elsewhere, link there.

| Tier | Job | Does NOT belong there |
|---|---|---|
| Root [`AGENTS.md`](../AGENTS.md) | Standing orders: rules an agent needs in context in every session, one to three lines each, linking its home | Stories, worked examples, situational procedures, anything restated from a linked home |
| Subtree `AGENTS.md` (`docs/`, `.agents/notes/`) | Orders specific to that subtree | Repo-wide rules the root file already carries |
| Reference pages under `docs/` | One subject per page at reference depth: setup, workflow, and subsystem behavior an agent or maintainer looks up | Decision rationale (→ Agent Notes), standing orders (→ root `AGENTS.md`), status annotations |
| [Agent Notes](../.agents/notes/README.md) | Active decision records: the why, what-was-given-up, and required verification; `implemented/` notes describe shipped reality in present tense | Migration plans, acceptance-task checklists, fixture walkthroughs, and spec-speak (“should…”) once the decision has shipped; archived notes are frozen history, never current authority |
| [Bilingual contract](i18n/README.md) | The pairing rules, translation rules, and the [terminology table](i18n/terminology.md) | Per-document translation state, project decisions, editorial judgment (→ prose standard skill) |
| Skills (`.agents/skills/`) | Reusable workflows and specialized decision standards | Product and runtime contracts (→ docs or source) |

Placement: decisions → Agent Notes; procedures → skills; standing orders → root `AGENTS.md` with a rationale link; domain vocabulary → `docs/i18n/terminology.md`; setup and day-to-day commands → a reference page under `docs/`.

## Writing rules

- **Document current state.** Keep history in commits, PRs, Agent Notes, and archived notes. Other prose names live mechanisms, not changes or stack positions.
- **Apply the Agent Note creation criteria.** Mechanical/local edits are exempt; keep existing owning notes accurate ([scope](../.agents/notes/README.md)).
- **One physical line per paragraph.** Use editor soft-wrap; review rejects hard-wrapped paragraphs. Code blocks, tables, and list structure keep their formatting.
- **Pairs update together**: [terminology-guided](i18n/terminology.md), single-pass active-agent work repositions first-use annotations, preserves untouched prose, and re-records; the [contract](i18n/README.md) owns the mechanics.
- **Comments and JSDoc state complete contracts, not reasoning transcripts.** Preserve behavior, failure, timing, ownership, modality, exceptions, consequences, and non-obvious orientation; delete narration, test walkthroughs, review analysis, and code restatement. Keep the local contract and link its rationale. Use [astrophotoflow-prose-standard](../.agents/skills/astrophotoflow-prose-standard/SKILL.md) for details.
- Write directly: name actors and facts. Name the exact check, type, API, operation, or behavior instead of metaphorical “gate”, “vocabulary”, or “surface”.

## Wordcount budgets

[scripts/doc-budgets.manifest.json](../scripts/doc-budgets.manifest.json) sets standing-doc ceilings; `pnpm verify-doc-budgets` rejects excess or missing files. The manifest is the only list of ceilings — this page does not restate the numbers.

When the gate goes red:

1. **Relocate** content that belongs in another tier; leave a one-line link if needed.
2. **Condense** content that belongs here but can be shorter.
3. **Raise** the ceiling only when the words need the space; justify the manifest diff. A too-low ceiling is a budget bug.

Ceilings are guardrails, not reduction targets. At or below target, retain at least 5% headroom; above target, freeze the ceiling until relocation or condensation brings the document under target. Lower a ceiling only when the document still has room.

## The slop checklist

Hunt these in any doc; [astrophotoflow-doc-writing](../.agents/skills/astrophotoflow-doc-writing/SKILL.md) runs this list as an audit:

- Duplicated rules: search a distinctive phrase; keep one home and link the rest.
- History outside its permitted tier: state current facts and link the historical owner.
- Implementation-status annotations in prose or diagrams (“implemented!”, “future: …”). Status rots; the repository layout carries it.
- Hand-restated catalogs or inventories of tests, files, and status when source or a generator is authoritative.
- Reasoning transcripts: step-by-step implementation narration, proof of obvious branches, test walkthroughs, or rejected local alternatives. Keep the resulting contract or durable rationale; delete the path used to derive it.
- Rationale repeated beside sibling methods instead of once at the owning capability or helper.
- Paragraph walls: one paragraph carrying several rules and parenthetical asides. Split it or demote the detail to its home.
- Emphasis inflation: bold, CAPS, or “critically” everywhere means nothing stands out. Reserve emphasis for the clause that changes behavior.
- Spec-speak in `implemented/` Agent Notes: “should”, migration plans, acceptance checklists. An implemented Agent Note describes what is, per the [implemented-note instructions](../.agents/notes/implemented/AGENTS.md).

## Repository references

Use relative Markdown links for current files and tags or PR numbers for historical references; review rejects a bare commit identifier in maintained files.
