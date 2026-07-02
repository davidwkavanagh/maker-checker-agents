# 0009 — The deterministic verdict: comparison, safety cap, and consumed threshold

**Status:** Accepted

## Context

Issue #4 builds the **decision layer** — the step that takes the two independent
classifications ([0008]) and produces a verdict. This is the hero the README
names *"a deterministic verdict, not an LLM judge"*, and the S157 parity audit
found it was the one part of that hero not actually built: the `Verdict` type and
`VerdictResult` existed but nothing produced them. This record makes the decisions
that standing up `verdict.py` forced. They share one spine: **the thing that
decides agreement must not be allowed to hallucinate, and must not overstate its
own certainty.**

## Decision 1 — Deterministic, three-valued, no LLM

The verdict is a pure function: `CONSISTENT` when the two tiers agree, `DIVERGENT`
when they differ, `INCONCLUSIVE` when there is nothing clean to compare. No model
call, no I/O. The verdict plus both classifications shown side by side is the
legible output a human acts on.

*Why:* the whole value of a maker-checker process is that a *machine-checkable*
fact — do two independent judgements match — is decided by code that cannot drift
or hallucinate. An LLM adjudicator would reintroduce exactly the failure mode the
architecture exists to remove. Descends from parent **ADR-001** (deterministic
over probabilistic).

*Alternative:* an LLM that reads both outputs and "judges" agreement — rejected:
non-deterministic, unauditable, and self-defeating.

## Decision 2 — The safety cap: a degraded run is never reported as a clean comparison

If the run is **degraded** — the scope gate failed open on an error ([0003]) — the
verdict is capped to `INCONCLUSIVE` even when the two tiers match. `CONSISTENT` and
`DIVERGENT` both assert "the pair was compared under known-good conditions"; a
degraded run cannot make that claim.

*Why:* this is a *safety* property, not quality plumbing — the happy path looks
finished without it, which is exactly how it gets skipped. It has its own binding
test (degraded + identical tiers → `INCONCLUSIVE`). Descends from parent
**ADR-012 / ADR-020** (the verdict cap).

*Fidelity note (recorded honestly):* Sandra caps on `node_15_status` — its Node 1.5
framework-scoping stage. This repo **deliberately has no Node 1.5** ([0006] scope
boundaries; the semantic router is production-NEXT). So the cap trigger is adapted:
here it fires on the scope gate's `degraded` fail-open flag. **Same invariant, a
different trigger** — the public repo mirrors the property at its own scope, it does
not reproduce Node 1.5.

## Decision 3 — Failure is `INCONCLUSIVE`, not a fourth verdict value

If either agent produced no classification (`None` — an agent failure, [0008]
Decision 3), there is nothing to compare and the verdict is `INCONCLUSIVE`. This
includes the both-failed case. There is **no `FAILED` verdict.**

*Why:* a run that failed outright — no verdict exists at all — is a property of the
**runner** (#5) and, in production, the persistence layer, not of the comparison.
In Sandra, `FAILED` is a pipeline *status* the orchestrator writes; the verdict
comparison itself is strictly three-valued. Keeping `Verdict` three-valued here
mirrors that seam and keeps the comparison a pure function of its two inputs.

*Alternative:* add `FAILED` to the `Verdict` enum and return it on both-`None` —
rejected: conflates "the run failed" (runner concern) with "the two judgements
could not be reconciled" (verdict concern), and diverges from Sandra's own layering.

## Decision 4 — Agreement strictness is read from config, and it is `exact` (B3)

The verdict **reads** `agreement.threshold` from policy and dispatches on it, via a
`_agree(maker_tier, checker_tier, threshold)` helper. `exact` — identical tier
required — is the **only supported strategy**; an unrecognised value raises rather
than silently falling through. This closes the dead-config gap the audit flagged
(the value was declared in policy but read by nothing).

*Why not make it genuinely tunable* (e.g. add `adjacent-tier-ok`, so `high` vs
`limited` counts as agreement)? Two reasons, both decisive:

1. **It is a governance anti-feature.** The risk taxonomy is ordinal. Treating
   adjacent tiers as agreement would *hide a material disagreement* — high-risk
   (heavy obligations) vs limited-risk (transparency only) — from the human. In a
   maker-checker system a tier split is precisely the signal the reviewer must see.
   A knob a compliance owner should never turn is not a feature.
2. **It would invert the honesty spine.** The production system (Sandra) is
   exact-only. Building a tunable threshold *publicly* would make the portfolio repo
   claim a capability production does not have — the wrong direction for a repo whose
   pitch is "mirrors a live system, honestly."

So the seam is **live and validated, one supported value** — not a tuning knob.

*Consequence — doc debt (see below):* the README currently overclaims that an owner
can change *how strict* agreement is; that must be corrected, because under this
decision there is one strategy to select, not a dial to turn.

## Decision 5 — No LLM explanation of the verdict (cut, recorded)

Sandra's Node 4 makes a scoped LLM call to phrase the verdict in plain language.
This repo **does not.** The deterministic result plus the two classifications side
by side is the legible output; rendering it for a human is the CLI's job (#6), in
plain code.

*Why:* the plan (§5) names the hero as a *deterministic non-LLM verdict*. Keeping
the whole verdict path model-free is fidelity to that, not a gap — and it avoids
adding an LLM call whose only job is to restate a comparison the code already made.

## HITL is unconditional (reaffirmed)

`routed_to_human` is `True` on every path — agreement, divergence, or failure —
type-enforced via `Literal[True]` ([0005]). Divergence changes *what the reviewer
is told*, never *whether* one is involved. A parametrized test asserts it across
every outcome.

## Consequences

- The repo's decision layer genuinely runs; the S157 hero is no longer hollow.
- `agreement.threshold` is consumed, so the config-as-governance claim ([0004]) is
  now true for strictness — with the honest bound that `exact` is the only strategy.
- The verdict layer trusts [0008]'s guarantee: any non-`None` `AgentOutput` carries
  an in-taxonomy tier, so the comparison never launders garbage into a divergence.
- **README §3 overclaim neutralised here (#4):** `README.md:44/46` no longer implies
  agreement strictness is a tunable dial — it now reads "config-declared and validated
  too (`exact` today — the seam is live, not yet a tuning dial)." The richer §3 rewrite
  (auditor-tax line, business-consequence rows) remains tracked on #7.
- **Doc debt still tracked to #7's authoring pass** (not silently):
  - [0004] gets a dated amendment (below): strictness is now config-*consumed*.
  - [`adr-lineage.md`](adr-lineage.md): ADR-001 and the verdict/cap half of
    ADR-012 / ADR-020 move from *deferred* to *covered* here; end-to-end runtime and
    parallelism stay deferred to #5.

## Evidence

- `src/maker_checker_agents/verdict.py` — `run_verdict`, `_agree` dispatch.
- `tests/test_verdict.py` — comparison, single/double failure, the safety-cap
  binding test, unconditional-HITL parametrization, threshold-dispatch test.
- `config/policy.yaml` — `agreement.threshold`; `src/.../config.py` — `Agreement`.
- README §2 (runnable hero), §3 (config as governance).

## Lineage

Determinism descends from parent **ADR-001**; the cap from **ADR-012 / ADR-020**
(trigger adapted from Node 1.5 to the scope gate — Decision 2); the always-human
floor from **ADR-003 / ADR-014** via [0005]; config-driven strictness from
**ADR-011 / ADR-016** via [0004]. See [`adr-lineage.md`](adr-lineage.md).

[0003]: 0003-fail-open-on-gate-error.md
[0004]: 0004-config-as-governance.md
[0005]: 0005-type-enforced-hitl.md
[0006]: 0006-inherited-scope-boundaries.md
[0008]: 0008-runnable-agent-layer.md
