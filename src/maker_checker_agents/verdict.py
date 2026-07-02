"""The deterministic verdict — a pure comparison of the two agents.

This is the hero the README calls a *"deterministic verdict, not an LLM judge"*.
The thing that decides whether the two independent classifications agree must not
be allowed to hallucinate, so it is plain code: no model call, no I/O. The
verdict, plus both classifications shown side by side, is the legible output a
human acts on — and a human always acts on it (``routed_to_human`` is ``True`` on
every path; divergence changes what the reviewer is told, not whether one is
involved).

Two safety properties:

* **The cap.** A degraded run — the scope gate failed open on an error — must
  never be reported CONSISTENT or DIVERGENT, because those read as "the pair was
  compared cleanly". It is capped to INCONCLUSIVE. This mirrors Sandra's verdict
  cap (ADR-012); Sandra caps on Node 1.5 status, which does not exist here
  (deliberately cut), so the trigger is the scope gate's ``degraded`` flag.
* **Failure is INCONCLUSIVE, not a fourth value.** If either agent produced no
  classification, there is nothing to compare → INCONCLUSIVE. A run that failed
  outright (no verdict at all) is the runner's concern (#5), not the verdict's.

The comparison trusts the agent layer: a non-``None`` ``AgentOutput`` is guaranteed
to carry an in-taxonomy ``risk_tier`` — ``agents.py`` validates the tier against
``policy.risk_tier_ids`` at the agent boundary and returns ``None`` otherwise
([0008] Decision 3). So the verdict compares tiers directly and does not re-check
membership; its correctness rests on that upstream guarantee.

Agreement strictness is read from ``policy.agreement.threshold`` — config, not
code (decision 0004). ``exact`` is the only supported strategy today; the seam is
live and validated, not a tuning knob (see 0009).
"""

from __future__ import annotations

from .config import Policy
from .models import AgentOutput, Verdict, VerdictResult


def _agree(maker_tier: str, checker_tier: str, threshold: str) -> bool:
    """Decide whether two tiers count as agreement under the configured strategy.

    ``run_verdict`` routes agreement through this helper on the configured
    ``threshold`` rather than a hardcoded comparison (a test binds that routing).
    Only ``exact`` is supported today; if a non-``exact`` value ever reaches here it
    raises rather than silently weakening agreement. (A policy typo is already caught
    upstream at load — ``config.py``'s ``Literal["exact"]`` rejects it with a
    ``ConfigError`` — so this raise is defense-in-depth.) The branch is a documented
    forward seam, not a live tuning knob (see 0009 Decision 4).
    """
    if threshold == "exact":
        return maker_tier == checker_tier
    raise ValueError(f"unsupported agreement threshold: {threshold!r}")


def run_verdict(
    *,
    case_id: str,
    maker: AgentOutput | None,
    checker: AgentOutput | None,
    degraded: bool,
    policy: Policy,
) -> VerdictResult:
    """Compare the two agents and route the case to a human.

    Pure and deterministic. ``degraded`` is the scope gate's fail-open flag; the
    runner (#5) supplies it. ``routed_to_human`` is always ``True``.
    """
    if maker is None or checker is None:
        verdict = Verdict.INCONCLUSIVE
        notes = "one or both agents produced no classification"
    elif degraded:
        # Safety cap: a degraded run cannot be reported as a clean comparison.
        verdict = Verdict.INCONCLUSIVE
        notes = "scope gate degraded (failed open) — capped to inconclusive"
    elif _agree(maker.risk_tier, checker.risk_tier, policy.agreement.threshold):
        verdict = Verdict.CONSISTENT
        notes = ""
    else:
        verdict = Verdict.DIVERGENT
        notes = "agents assigned different risk tiers"

    return VerdictResult(
        case_id=case_id,
        verdict=verdict,
        maker=maker,
        checker=checker,
        degraded=degraded,
        notes=notes,
    )
