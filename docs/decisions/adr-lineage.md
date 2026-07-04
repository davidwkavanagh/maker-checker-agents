# ADR lineage — where this engine's decisions come from

This engine is a fresh, minimal rebuild descended from a larger regulated-AI
system that classifies against the EU AI Act and produces signed audit records.
That parent system recorded its decisions in 21 architecture decision records.

This document maps **every one of those 21 parent decisions** to its status in
this repo, so the inheritance is provable rather than asserted. Each parent
decision is one of:

- **Covered** — the idea lives here, recorded in one of this repo's decision
  records ([0001](0001-cross-vendor-agent-independence.md)–[0011](0011-cli-and-demo-cases.md)).
- **Deferred** — the idea is coming to this engine, but its decision record is
  written *with* the code that implements it (writing it now would be fiction).
  Tracked against a backlog item.
- **Cut** — deliberately not reproduced in this public rebuild — either out of scope
  for a single-shot CLI engine, or built and tested in the parent system and
  not copied here (to keep the demo small and avoid exposing proprietary code).
  Recorded as a group in [0006](0006-inherited-scope-boundaries.md). A cut may still
  carry a design record showing the parent-system engineering (e.g. grounding → [0007]).

The point of keeping this map: a reader who knows the domain can confirm nothing
was missed by accident. Cuts and deferrals are decisions, not gaps.

## The map

| Parent decision | Concern | Status in this repo |
|---|---|---|
| **001** Deterministic over probabilistic | No LLM where code suffices; the verdict is code, not a judge | **Covered** → [0002] (principle) + [0009] (the deterministic verdict itself) |
| **002** Conversational HITL | Typed multi-turn reviewer dialogue | **Cut** → [0006] |
| **003** Bounded review sessions | Session isolation + status lifecycle | **Cut** → [0006] |
| **004** Two interface layers | Submitter co-pilot + reviewer UI | **Cut** → [0006] |
| **005** MCP tool surface | Least-privilege tools to a frontend | **Cut** → [0006] |
| **006** LangGraph orchestration | Graph runtime for the pipeline | **Departure** → [0010] (plain-Python stdlib orchestration, no framework; the stages are discrete node-functions so it is an on-ramp to LangGraph — Sandra takes the framework for durable interrupt/resume + multi-framework routing, both cut here) |
| **007** LangSmith observability | Hosted tracing + field masking | **Cut** → [0006] (stdlib logging instead) |
| **008** Supabase brief storage | Persistence + data residency | **Cut** → [0006] |
| **009** Safe Harbour tokenisation | Strip PII before a provider boundary | **Cut** → [0006] (sensitivity *flag* kept; lesson kept) |
| **010** Local → hosted deployment | Railway, ephemeral filesystem | **Cut** → [0006] (runs from clean clone) |
| **011** Tiered decision pipeline | 4 tiers incl. Node-1 confidence scoring + quality-halt; cross-provider challenge; "what we reject" table | **Split** — tier pipeline + cross-provider challenge **Covered** → [0001] + [0002] + [0005], flow assembled in [0010]; **Node-1 confidence scoring / quality-halt Cut** → [0006] (built &amp; tested in the parent, not reproduced) |
| **012** Multi-agent + graceful degradation | Failure modes, parallel fan-out, verdict cap | **Covered** — fail-open → [0003]; agent degradation (out-of-taxonomy / unparseable = failure) → [0008]; verdict cap (degraded run → INCONCLUSIVE, trigger adapted from Node 1.5 to the scope gate) → [0009]; parallel fan-out (concurrent Maker ‖ Checker, threads) + both-agents-fail → run failure (`PipelineError`, cannot proceed; Sandra's `FAILED` status at this repo's no-persistence scope) → [0010] |
| **013** Tiered eval set | Rubric, gatekeeper tiers, hypothesis | **Deferred** → eval-framework work (designed/NEXT) |
| **014** HITL reviewer decision model | 4 outcomes, segregation of duties, escalation | **Cut** → [0006] (always-human *principle* kept in [0005]) |
| **015** Maker-Checker independence | State isolation, Checker never sees Maker | **Covered** → [0001] |
| **016** Prompt governance + state integrity + injection-resistance | Prompts in governed config; write-once audit field; resistance to prompt injection | **Split** — prompt-governance **Covered** → [0004], integrity **Covered** → frozen Pydantic models; **injection-resistance Cut** → [0006] (scan / escape / flag-to-human built & tested in the parent, not reproduced — only the taxonomy check is kept here) |
| **017** Parametric bleed / grounding | Why ground citations; provenance as proof | **Cut** → [0006] (built & tested in the parent; not reproduced here to protect code); design recorded in [0007] |
| **018** Semantic knowledge layer | Real corpus ingest (ChromaDB, voyage-law-2, batch) + retrieved-source provenance | **Cut** → [0006] (built in the parent; not reproduced here); design recorded in [0007] |
| **019** FastAPI reviewer backend | API surface, CQRS, audit endpoints | **Cut** → [0006] (CLI instead — the single surface, built in [0011]) |
| **020** Multi-framework architecture | `framework_triggers`, Node 1.5 detection, clean-room state, fallback | **Covered** → [0002] (gate) + [0001] (state isolation) + [0003] (fallback); per-framework *classification* **deferred** (designed/NEXT) |
| **021** Rubric scorer governance | Independent third-model scorer, DCP-governed prompt | **Deferred** → eval-framework work (designed/NEXT) |

## Summary

21 distinct parent decisions. Three are **split** — part is settled here while another
part lands elsewhere (deferred to the build that needs it, or cut to the parent) — so
they appear in more than one row below, and the columns deliberately do **not** sum to 21.
One (**006**) is a **departure**: settled here, but *differently* from the parent.

| Status | Parent decisions |
|---|---|
| Covered | 001, 012, 015 + split 011, 016, 020 |
| Departure | 006 → [0010] (framework replaced by stdlib, on-ramp preserved) |
| Deferred | 013, 021 + split 020 |
| Cut / reduced | 002, 003, 004, 005, 007, 008, 009, 010, 014, 016, 017, 018, 019 + split 011 |

The three splits: **011** (tier pipeline + cross-provider challenge covered / Node-1
confidence scoring + quality-halt cut to the parent), **016** (prompt-governance +
integrity covered / injection-resistance cut to the parent), **020** (detection +
state isolation + fallback covered / per-framework classification deferred). **011**
and **016** are covered/cut splits; **020** is covered/deferred. (**001** was a
covered/deferred split until #4 — the deterministic verdict landed in [0009]; **012**
was covered/deferred until #5 — parallel fan-out landed in [0010] — so both are now
fully covered.)

ADR-017 (grounding) and ADR-018 (knowledge layer) are **not** splits: both are fully
cut from this rebuild — built and tested in the parent, deliberately not reproduced —
with their combined design recorded in [0007].

[0006] records the cut/reduced group — **13 entries**: the ten surface/infra
removals, the grounding/ingestion cluster (ADR-017 + ADR-018 — built in the parent,
not reproduced; design in [0007]), prompt-injection hardening (ADR-016's resistance
half — built in the parent, not reproduced; named in README §8), and Node-1 confidence
scoring / quality-halt (ADR-011's scoring half — built in the parent, not reproduced).
Two of the thirteen are reductions rather than clean removals (sensitivity flag, stdlib
logging); the remaining eleven entries are genuine absences.

Deferred decisions are recorded against their backlog item so the decision record
gets written when the code does — see the build backlog. This document is updated
as deferred items land.

[0001]: 0001-cross-vendor-agent-independence.md
[0002]: 0002-deterministic-config-driven-scope-gate.md
[0003]: 0003-fail-open-on-gate-error.md
[0004]: 0004-config-as-governance.md
[0005]: 0005-type-enforced-hitl.md
[0006]: 0006-inherited-scope-boundaries.md
[0007]: 0007-grounding-and-retrieved-source-provenance.md
[0008]: 0008-runnable-agent-layer.md
[0009]: 0009-deterministic-verdict-and-cap.md
[0010]: 0010-pipeline-orchestration.md
[0011]: 0011-cli-and-demo-cases.md
