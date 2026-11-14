# Agent Note: Agents retrieve processing guidance from a local knowledge base

Status: proposed

English | [中文](2026-11-14-agent-knowledge-base-rag.zh.md)

## Problem

An agent helping with astrophotography processing answers from model memory. The correct procedure depends on the software release, the sensor and filter, and the workflow the practitioner actually follows; official documentation and experienced practitioners' write-ups carry that knowledge, but it is scattered across manuals, PDFs, and forum posts and changes between releases. Without retrieval, the agent produces plausible but outdated or misquoted steps, cannot point to a source, and repeats the same uncertainty in every session. The MCP surface exposes the workbench but no way to consult a curated reference corpus.

## Proposal

Add a local knowledge base of official and expert astrophotography processing documentation, exposed by the MCP server as a `knowledge` module. The agent reads a short usage guide, searches the corpus, and receives article and passage information it can cite. The module answers "what does the documented workflow say", not "run this graph"; it never touches assets, datasets, calibration bindings, or the canvas.

### Corpus

The corpus covers data-processing workflow documentation: calibration, stacking, stretching, color, noise reduction, mosaics, and the software-specific steps around them. Each source is recorded in a manifest with its title, author or publisher, URL or local path, license and local-storage permission, document version or retrieval date, and content hash. A source whose license does not permit a local copy is represented by metadata and a link and is excluded from offline retrieval; it is not copied silently.

Ingestion is an offline, reproducible build: validate the manifest, extract text, split it into section-aware passages, compute embeddings, build the BM25 and vector indexes, and write an immutable corpus version. A query result carries that version and the document date. Rebuilding unchanged input yields the same corpus version and passage ids; a changed document produces a new version.

### Retrieval

A query returns ranked passages. Candidate generation runs BM25 and embedding retrieval independently: BM25 preserves exact identifiers and rare terms such as `FITS`, `CFA`, and `drizzle`, while the embedding side covers paraphrase and synonyms. The two ranked lists are fused, then a reranker scores query-passage pairs and produces the final top-k.

Each result carries the passage text, article title, section path, source, document version or date, score, stable passage id, and corpus version. An optional filter narrows by source, product, or topic. If no passage clears a relevance floor, the module returns `INSUFFICIENT_EVIDENCE` with the query and corpus version instead of the closest unrelated text.

The module returns evidence, not generated prose. The agent composes the answer and cites passage ids, so a reader can check the source and the retrieval layer cannot invent a step the corpus does not contain.

### MCP surface

The module adds two task tools to the existing [MCP surface](../architecture/2026-11-14-node-mcp-for-the-tool-surface.md): `knowledge_search` for a query with optional filters and `knowledge_get` for a passage or article id. A short usage guide is attached to the tool descriptions and exposed as a `knowledge://guide` resource: when to call (before answering a processing-how-to question), how to cite, and that retrieved text is evidence rather than instructions.

The MCP process keeps its existing constraints: no SQLite handle, no Python import, and no child process. Because the selected LangFlow/LangGraph stack is Python and the MCP process is Node, the retrieval engine runs as a local sidecar reached over loopback HTTP; the MCP process remains a thin client. The local controller starts and stops the sidecar with the workbench, so the MCP process still spawns nothing. The sidecar owns only its corpus and index directory, reads no workspace configuration, and holds no service token.

### Locality and ownership

The knowledge base runs entirely on the local machine. Query-time execution makes no request outside the machine; embedding and reranker models are local, and a first-run model download is an explicit, documented step. The sidecar binds loopback only.

The knowledge base is reference material, not [managed assets](../architecture/2026-11-14-managed-asset-ledger.md). Its documents are not imported into the asset library, not fingerprinted as originals, not dataset members, and not shown in the library. It has no write path to the workspace database, the asset library, or the graph.

### Authoring and operation

LangGraph defines the retrieval graph in code; LangFlow may sketch or inspect the same graph, but the checked-in graph is the source of truth. The retrieval graph, prompt templates, model identifiers, and relevance floor are configuration with defaults, not values hidden in the index.

A checked-in evaluation set of real processing questions and expected articles or passages accompanies the corpus. A retrieval change runs against that set, so "the results look relevant" is not the acceptance signal.

## Alternatives considered

**Rely on model memory or a long system prompt.** Rejected: the knowledge is versioned and larger than a prompt, the agent cannot cite it, and a stale step is indistinguishable from a current one.

**Search the web at query time.** Rejected: the requirement is local operation, and a curated corpus is the point. Live search adds network variance, untrusted sources, and no stable corpus version to cite.

**Use BM25 alone or embeddings alone.** Rejected: BM25 misses paraphrase and embeddings miss exact identifiers or rare terms. The two candidate lists plus a reranker are complementary, and each stage is testable on its own.

**Generate answers inside the module.** Rejected: it hides the evidence behind prose and adds a second place where steps can be invented. The module returns passages; the agent writes the answer and cites them.

**Import the documents as assets.** Rejected: the asset ledger tracks capture originals, datasets, and calibration. Reference documents have different provenance and no scientific-input role, and mixing them would pollute library queries and ownership rules.

**Use a hosted vector database or hosted embeddings.** Rejected: it breaks local operation and sends the corpus and queries off the machine. A local index is sufficient for a single-user corpus.

**Serve the LangFlow runtime directly.** Rejected for the first version: LangFlow is an authoring and inspection surface, and shipping its runtime adds a second application to operate. The retrieval graph is small enough to keep as reviewed code.

## Acceptance criteria

- An agent can call the MCP knowledge module and receive top-k passages with article title, section, source, corpus version, and stable passage id.
- Each query produces both BM25 and embedding candidates; a fixture test shows that each list contributes and that the reranker can change the final order.
- Repeating a query against an unchanged corpus version returns the same ranked passage ids.
- A query with no passage above the relevance floor returns `INSUFFICIENT_EVIDENCE`, not unrelated text.
- Query-time execution makes no request outside the machine, and the sidecar listens on loopback only.
- The knowledge base cannot write to the workspace database, the asset library, or the graph.
- The MCP process still opens no SQLite database, imports no Python, and spawns no child process.
- The manifest records title, source, license and local-storage permission, document version or date, and hash for every indexed document; a rebuild from the same manifest yields the same corpus version and passage ids.
- The usage guide is visible to the agent and states when to call the module, the citation format, and the insufficient-evidence behavior.
- A stopped sidecar or a missing index returns a readable error naming the next step, not a stack trace.

## Risks

- Licensing is the first blocker. Official manuals and expert posts may not permit local copies or redistribution; the manifest must record permission, and a link-only source cannot support offline retrieval. The corpus scope has to state that trade-off rather than assume it away.
- Documents drift with software releases. A cited passage can be correct for the indexed version and wrong for the installed one, so results must show the document date and corpus version, and the rebuild cadence must be explicit.
- Retrieval quality on domain language is unproven. Mixed Chinese and English sources, product-specific vocabulary, and BM25 tokenization all affect recall; the evaluation set is the only defense against tuning by impression.
- Chunking can split a procedure or a parameter table into useless fragments. Passages need section-aware boundaries, neighboring context, and citations that point to the section rather than a bare fragment.
- Local embedding and reranker models cost disk, memory, and CPU time. The first query after a cold start can be slow, and a CPU-only machine must remain usable.
- Retrieved text is untrusted input. A document can contain instructions aimed at the agent; passages must be delimited as data, never followed as instructions, and never allowed to trigger tools.
- The sidecar adds a process to start, health-check, and stop. An agent call before the index is ready must fail clearly instead of returning an empty list that looks like a real answer.
- The feature can drift into a chat product or a second workbench database. The first version stays retrieval-only and read-only, with no answer generation and no library writes.
- Agents may over-trust a retrieved passage. The usage guide must require a citation and a statement when the corpus does not answer, so a confident answer never hides a missing source.
