# ADR lineage — where this engine's decisions come from

This engine is a fresh, minimal rebuild descended from a larger regulated-AI
system that classifies against the EU AI Act and produces signed audit records.
That parent system recorded its decisions in 21 architecture decision records.

This document maps **every one of those 21 parent decisions** to its status in
this repo, so the inheritance is provable rather than asserted. Each parent
decision is one of:

- **Covered** — the idea lives here, recorded in one of this repo's decision
  records ([0001](0001-cross-vendor-agent-independence.md)–[0008](0008-runnable-agent-layer.md)).
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
| **001** Deterministic over probabilistic | No LLM where code suffices; the verdict is code, not a judge | **Covered** (principle) → [0002]; deterministic *verdict* itself **deferred** → verdict build |
| **002** Conversational HITL | Typed multi-turn reviewer dialogue | **Cut** → [0006] |
| **003** Bounded review sessions | Session isolation + status lifecycle | **Cut** → [0006] |
| **004** Two interface layers | Submitter co-pilot + reviewer UI | **Cut** → [0006] |
| **005** MCP tool surface | Least-privilege tools to a frontend | **Cut** → [0006] |
| **006** LangGraph orchestration | Graph runtime for the pipeline | **Deferred** → pipeline build, as a **departure** (plain-Python orchestration, no framework — KISS) |
| **007** LangSmith observability | Hosted tracing + field masking | **Cut** → [0006] (stdlib logging instead) |
| **008** Supabase brief storage | Persistence + data residency | **Cut** → [0006] |
| **009** Safe Harbour tokenisation | Strip PII before a provider boundary | **Cut** → [0006] (sensitivity *flag* kept; lesson kept) |
| **010** Local → hosted deployment | Railway, ephemeral filesystem | **Cut** → [0006] (runs from clean clone) |
| **011** Tiered decision pipeline | 4 tiers + cross-provider challenge; "what we reject" table | **Covered** → [0001] + [0002] + [0005] |
| **012** Multi-agent + graceful degradation | Failure modes, parallel fan-out, verdict cap | **Covered** — fail-open → [0003]; agent degradation (out-of-taxonomy / unparseable = failure) → [0008]. Parallel fan-out still **deferred** → pipeline build (#5) |
| **013** Tiered eval set | Rubric, gatekeeper tiers, hypothesis | **Deferred** → eval-framework work (designed/NEXT) |
| **014** HITL reviewer decision model | 4 outcomes, segregation of duties, escalation | **Cut** → [0006] (always-human *principle* kept in [0005]) |
| **015** Maker-Checker independence | State isolation, Checker never sees Maker | **Covered** → [0001] |
| **016** Prompt governance + state integrity + injection-resistance | Prompts in governed config; write-once audit field; resistance to prompt injection | **Split** — prompt-governance **Covered** → [0004], integrity **Covered** → frozen Pydantic models; **injection-resistance Cut** → [0006] (scan / escape / flag-to-human built & tested in the parent, not reproduced — only the taxonomy check is kept here) |
| **017** Parametric bleed / grounding | Why ground citations; provenance as proof | **Cut** → [0006] (built & tested in the parent; not reproduced here to protect code); design recorded in [0007] |
| **018** Semantic knowledge layer | Real corpus ingest (ChromaDB, voyage-law-2, batch) + retrieved-source provenance | **Cut** → [0006] (built in the parent; not reproduced here); design recorded in [0007] |
| **019** FastAPI reviewer backend | API surface, CQRS, audit endpoints | **Cut** → [0006] (CLI instead) |
| **020** Multi-framework architecture | `framework_triggers`, Node 1.5 detection, clean-room state, fallback | **Covered** → [0002] (gate) + [0001] (state isolation) + [0003] (fallback); per-framework *classification* **deferred** (designed/NEXT) |
| **021** Rubric scorer governance | Independent third-model scorer, DCP-governed prompt | **Deferred** → eval-framework work (designed/NEXT) |

## Summary

21 distinct parent decisions. Four are **split** — part is settled here while another
part lands elsewhere (deferred to the build that needs it, or cut to the parent) — so
they appear in more than one row below, and the columns deliberately do **not** sum to 21.

| Status | Parent decisions |
|---|---|
| Covered | 011, 015 + split 001, 012, 016, 020 |
| Deferred | 006, 013, 021 + split 001, 012, 020 |
| Cut / reduced | 002, 003, 004, 005, 007, 008, 009, 010, 014, 016, 017, 018, 019 |

The four splits: **001** (deterministic principle covered / the verdict itself
deferred), **012** (fail-open + agent degradation covered / parallel fan-out deferred),
**016** (prompt-governance + integrity covered / injection-resistance cut to the parent),
**020** (detection + state isolation + fallback covered / per-framework classification
deferred). The first, second and fourth are covered/deferred; **016** is the one
covered/cut split.

ADR-017 (grounding) and ADR-018 (knowledge layer) are **not** splits: both are fully
cut from this rebuild — built and tested in the parent, deliberately not reproduced —
with their combined design recorded in [0007].

[0006] records the cut/reduced group — **12 entries**: the ten surface/infra
removals, the grounding/ingestion cluster (ADR-017 + ADR-018 — built in the parent,
not reproduced; design in [0007]), and prompt-injection hardening (ADR-016's
resistance half — built in the parent, not reproduced; named in README §8). Two of the
twelve are reductions rather than clean removals (sensitivity flag, stdlib logging); the
other ten are genuine absences.

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
