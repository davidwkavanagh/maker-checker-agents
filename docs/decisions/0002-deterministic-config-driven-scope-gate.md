# 0002 — Deterministic, config-driven scope gate — not a generative router

**Status:** Accepted

## Context

Running two frontier models on every case is expensive. A triage gate up front
can skip the expensive pair for cases that obviously don't apply. The question
was *what kind* of gate: a cheap generative model (e.g. a small fast LLM) deciding
scope, or deterministic code.

## Decision

The scope gate is **plain, deterministic code driven by config**
(`policy.framework_triggers`). Detection over a *known* regulatory vocabulary is
a classification problem with a definable boundary — not a generation problem.
Matching is word/token level (a phrase matches when all its words are present),
which avoids naive-substring false positives. Zero cost, zero latency, and it
cannot hallucinate.

This choice was contested mid-build (I flip-flopped toward a generative gate) and
settled by a **cross-model adversarial review (Gemini Pro)**, which argued — and I
agreed — to kill the generative gate. The stronger product story is *knowing when
not to use GenAI*.

## Alternatives considered

- **Generative LLM router (small/fast model).** Rejected — cost and latency on
  every case, and a hallucination risk on a decision that should be predictable.
  Triage should be cheap and deterministic.
- **Semantic / vector router.** Deferred to *production NEXT* (labelled in the
  README). It is the honest upgrade path because the deterministic gate's recall
  is bounded by its literal vocabulary — paraphrases it has never seen are missed.

## Consequences

- The gate is keyless and runs offline — reinforces the config-as-governance hero.
- Recall is bounded by the configured keywords/domains; this limit is stated
  openly, and the semantic router is the named next step rather than implied.
- Matching is order-free token-set membership — a multi-word trigger fires when all
  its words appear anywhere in the case, not as an adjacent phrase. This dodges the
  naive-substring trap (`scoreboard` ≠ `score`) but accepts a bag-of-words over-match
  (`credit` and `scoring` in unrelated sentences match `credit scoring`). Accepted
  deliberately: over-inclusion only wastes model spend, it never skips the human
  (the asymmetric-risk rule), and the semantic router is the precision upgrade.

## Evidence

- `src/maker_checker_agents/scope_gate.py` — token matching over `framework_triggers`.
- `config/policy.yaml` — `framework_triggers`, `sensitivity_keywords`.
- README §7 (route-before-you-spend, *designed not shipped*), §9 (tradeoffs table).

## Lineage

Descends from the parent system's ADR-020 (`framework_triggers` detection) and
ADR-001 (deterministic over probabilistic) — but **departs** from ADR-020's
choice of a generative model (Gemini Flash) for the gate. See
[`adr-lineage.md`](adr-lineage.md).
