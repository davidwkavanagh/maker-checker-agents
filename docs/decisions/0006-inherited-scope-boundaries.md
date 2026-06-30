# 0006 — Inherited scope boundaries: what was deliberately not built

**Status:** Accepted

## Context

This engine is a fresh, minimal rebuild of the maker-checker pattern, descended
from a larger regulated-AI system that classifies against the EU AI Act and
produces legally-consequential, signed audit records. That parent system carries
a real penalty exposure, so it grew a full stateful surface: a reviewer dialogue,
persistence, a hosted API, PII controls, observability infrastructure.

This repo is a **single-shot CLI engine that classifies fictional cases offline.**
It protects no legal artifact. Carrying the parent system's surface here would be
ceremony — and would leak company specifics. The discipline was to keep the
*engine and its governance idea* and consciously cut everything that only existed
to carry legal weight.

This record names those cuts, so that a reader who knows the domain can see they
were *decisions*, not gaps. (See [`adr-lineage.md`](adr-lineage.md) for the full
parent-decision-to-repo map.)

## Decision

The following concerns from the parent system are **deliberately out of scope, or
reduced to the minimum a single-shot offline engine needs.** Each is a real thing
the parent built; none belongs in a minimal public engine.

| Dropped or reduced | What the parent system did | Why it's out of scope here |
|---|---|---|
| **Conversational HITL** | A typed, multi-turn reviewer dialogue (challenge / clarify / override). | This engine routes a case *to* a human and stops. There is no dialogue surface to govern. The always-human invariant survives in [0005]. |
| **Bounded review sessions** | Isolated sessions with a status lifecycle, archived per audit rules. | No persistence, no sessions, no status machine — a single classification has nowhere to bleed. |
| **Two UI surfaces** | A submitter co-pilot and a reviewer workflow over one engine. | No UI at all. The CLI is the only surface; the engine is the product. |
| **Reviewer decision model + SoD** | Four reviewer outcomes, segregation-of-duties enforcement, escalation logging. | No accounts, no decision recording. Routing to a human is the boundary; what the human *does* is out of scope. |
| **API / backend layer** | A FastAPI backend (CQRS, audit-PDF generation, status commands). | No service, no endpoints. A CLI replaces the backend; there is no second runtime to bridge. |
| **Persistence** | A database storing full briefs, verdicts, and audit columns. | Fictional cases, run once, printed. Storing them buys nothing and adds a data-residency problem the repo doesn't have. |
| **PII / data-boundary controls** | Tokenisation stripping sensitive data before it crosses a provider boundary. | Fictional cases carry no real PII. The repo keeps a lightweight **sensitivity flag** (it surfaces, it does not tokenise) and the *lesson* — a prompt instruction is not a control — survives in the README and [0005]. |
| **Observability infrastructure** | Hosted tracing with sensitive-field masking. | Offline by default. Standard-library logging is the entire observability story; there is no third-party trace boundary to mask. |
| **Hosted deployment** | A hosted service with an ephemeral filesystem, EU data-residency config. | Runs from a clean clone. The *principle* (fail-fast config, honest degradation) is kept; the infrastructure is not. |
| **MCP tool surface** | A least-privilege set of MCP tools exposed to a frontend. | No frontend to serve and no tools to expose. The restraint principle is moot without a surface. |
| **Real corpus ingestion + grounding** | A pipeline turning regulatory PDFs into a structured vector store (layout parsing → LLM batch extraction → legal-tuned embeddings → ChromaDB), then retrieval-grounding each classification against it with retrieved-source provenance. | **Built and tested in the parent system; not reproduced here** — copying it would expose proprietary code and need a real vector store. The grounding / provenance *design* is recorded in [0007] so the engineering is visible without duplicating it. |

**Two of these are reductions, not clean removals** — the sensitivity flag (in
place of tokenisation) and standard-library logging (in place of hosted tracing) keep
the minimum the engine needs while dropping the surrounding infrastructure. The other
nine are genuine absences (real ingestion among them — its grounding/provenance design
is recorded in [0007], but no retrieval runs here).

## Consequences

- The repo stays small and runnable from a clean clone — the point of a public
  demo. The engine and its governance idea are intact; the legal-weight scaffolding
  is not imported.
- A domain-aware reader can see each cut was considered. Naming them is the same
  signal as [0002] (choosing *not* to use a generative router): judgment about
  what not to build.
- If this engine ever needed to carry real legal weight, this table is the
  build list — each cut is a known, bounded re-addition, not a surprise.

## What this is NOT

This is not a list of things the parent system got wrong, and not a roadmap for
*this* repo. Concerns that *are* coming to this engine (the deterministic verdict and
the evaluation method) are **deferred**, not cut — they're tracked in
[`adr-lineage.md`](adr-lineage.md) and land with their code, not here. Grounding is
*not* among them: it's built in the parent and deliberately not reproduced (see the
ingestion/grounding row above), with its design in [0007].

## Amendment — 2026-06-30 (#3, via [0008])

The "classifies fictional cases **offline**" / "single-shot offline engine"
framing above is superseded by [0008]: the engine makes **live cross-vendor API
calls with the caller's own keys** — there is no offline replay mode (a capture/
replay harness was itself gold-plating, against the KISS discipline this record
defends). Only the run-mode is corrected; the scope cuts in the table stand
unchanged. Note "**Offline by default**" in the *Observability* row still holds —
there it means no hosted trace boundary to mask, not the absence of API calls. See
[0008].

[0002]: 0002-deterministic-config-driven-scope-gate.md
[0005]: 0005-type-enforced-hitl.md
[0007]: 0007-grounding-and-retrieved-source-provenance.md
[0008]: 0008-runnable-agent-layer.md
