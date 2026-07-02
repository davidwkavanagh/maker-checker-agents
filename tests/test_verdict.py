"""Tests for the deterministic verdict layer (issue #4, decision record 0009).

The verdict is a *pure* comparison of the two agents' classifications — no LLM,
no I/O. It is the hero the README calls a "deterministic verdict, not an LLM
judge": the thing that decides agreement must not be allowed to hallucinate, so
it is plain code with binding tests.

Two properties matter beyond the happy path and get their own tests:

* **The safety cap.** A degraded run (the scope gate failed open) must never be
  reported as CONSISTENT or DIVERGENT — those read as "the two agents were
  compared cleanly", which is false. It is capped to INCONCLUSIVE. This mirrors
  Sandra's verdict cap (ADR-012), adapted to this repo's scope: Sandra caps on
  Node 1.5 status; there is no Node 1.5 here (deliberately cut), so the cap
  triggers on the scope gate's ``degraded`` fail-open flag instead.
* **HITL is unconditional.** ``routed_to_human`` is ``True`` on every path —
  agreement, divergence, or failure. Divergence does not gate whether a human is
  involved; it only changes what the human is told.

The threshold-dispatch test binds the config-consumption claim: the verdict
reads ``agreement.threshold`` from policy and dispatches on it, rather than
hardcoding exact-match. Only ``exact`` is supported today; an unknown strategy
raises rather than silently falling through.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maker_checker_agents.config import load_policy
from maker_checker_agents.models import AgentOutput, Verdict, VerdictResult
from maker_checker_agents.verdict import _agree, run_verdict

POLICY = load_policy(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")


def _out(tier: str) -> AgentOutput:
    """A well-formed agent classification at a given tier."""
    return AgentOutput(
        risk_tier=tier,
        rationale=f"classified as {tier}",
        articles_cited=["Article 6"],
    )


# --- Comparison: consistent / divergent -----------------------------------


def test_matching_tiers_are_consistent() -> None:
    result = run_verdict(
        case_id="c1", maker=_out("high"), checker=_out("high"),
        degraded=False, policy=POLICY,
    )
    assert result.verdict is Verdict.CONSISTENT
    assert result.notes == ""


def test_differing_tiers_are_divergent() -> None:
    result = run_verdict(
        case_id="c1", maker=_out("high"), checker=_out("limited"),
        degraded=False, policy=POLICY,
    )
    assert result.verdict is Verdict.DIVERGENT
    assert "different risk tiers" in result.notes


# --- Single / double agent failure → INCONCLUSIVE --------------------------


def test_maker_failure_is_inconclusive() -> None:
    result = run_verdict(
        case_id="c1", maker=None, checker=_out("high"),
        degraded=False, policy=POLICY,
    )
    assert result.verdict is Verdict.INCONCLUSIVE


def test_checker_failure_is_inconclusive() -> None:
    result = run_verdict(
        case_id="c1", maker=_out("high"), checker=None,
        degraded=False, policy=POLICY,
    )
    assert result.verdict is Verdict.INCONCLUSIVE


def test_both_agents_failing_is_inconclusive() -> None:
    # Both-fail is a verdict of INCONCLUSIVE, NOT a fourth "FAILED" value.
    # A run that failed entirely is the runner's concern (#5), not the verdict's.
    result = run_verdict(
        case_id="c1", maker=None, checker=None,
        degraded=False, policy=POLICY,
    )
    assert result.verdict is Verdict.INCONCLUSIVE
    assert "no classification" in result.notes


def test_degraded_and_missing_agent_reports_the_failure_note() -> None:
    # Branch ordering: the None-check precedes the degraded-check, so a run that is
    # BOTH degraded and missing an agent reports the "no classification" note, not
    # the degraded one. INCONCLUSIVE either way — this locks the note wording.
    result = run_verdict(
        case_id="c1", maker=None, checker=_out("high"),
        degraded=True, policy=POLICY,
    )
    assert result.verdict is Verdict.INCONCLUSIVE
    assert "no classification" in result.notes


# --- The safety cap: a degraded run can never read CONSISTENT --------------


def test_degraded_run_is_capped_even_when_tiers_match() -> None:
    # THE cap test. Two valid, identical classifications — but the scope gate
    # failed open, so the run is degraded. It must NOT be reported CONSISTENT.
    result = run_verdict(
        case_id="c1", maker=_out("high"), checker=_out("high"),
        degraded=True, policy=POLICY,
    )
    assert result.verdict is Verdict.INCONCLUSIVE
    assert "degraded" in result.notes


def test_degraded_run_is_capped_when_tiers_differ() -> None:
    result = run_verdict(
        case_id="c1", maker=_out("high"), checker=_out("limited"),
        degraded=True, policy=POLICY,
    )
    assert result.verdict is Verdict.INCONCLUSIVE


# --- HITL is unconditional -------------------------------------------------


@pytest.mark.parametrize(
    ("maker", "checker", "degraded"),
    [
        (_out("high"), _out("high"), False),       # consistent
        (_out("high"), _out("limited"), False),    # divergent
        (None, _out("high"), False),               # single failure
        (None, None, False),                       # double failure
        (_out("high"), _out("high"), True),        # degraded / capped
    ],
)
def test_routed_to_human_is_always_true(
    maker: AgentOutput | None, checker: AgentOutput | None, degraded: bool
) -> None:
    result = run_verdict(
        case_id="c1", maker=maker, checker=checker,
        degraded=degraded, policy=POLICY,
    )
    assert result.routed_to_human is True


# --- The output carries both classifications (the legible side-by-side) ----


def test_result_carries_both_classifications_and_degraded_flag() -> None:
    maker, checker = _out("high"), _out("limited")
    result = run_verdict(
        case_id="case-42", maker=maker, checker=checker,
        degraded=True, policy=POLICY,
    )
    assert isinstance(result, VerdictResult)
    assert result.case_id == "case-42"
    assert result.maker is maker
    assert result.checker is checker
    assert result.degraded is True


# --- Threshold dispatch: config is consumed, not hardcoded -----------------


def test_agree_exact_requires_identical_tiers() -> None:
    assert _agree("high", "high", "exact") is True
    assert _agree("high", "limited", "exact") is False


def test_agree_rejects_unknown_strategy() -> None:
    # The seam is real: an unrecognised strategy raises rather than silently
    # falling through to exact-match. 'exact' is the only supported value today.
    with pytest.raises(ValueError, match="threshold"):
        _agree("high", "high", "adjacent-tier-ok")


def test_run_verdict_routes_threshold_through_agree() -> None:
    # Binds the config-consumption claim at the boundary that matters. Agreement.
    # threshold is Literal["exact"], so no *validated* policy can carry another
    # value; model_copy bypasses validation to inject a bogus strategy and drive it
    # THROUGH run_verdict. This proves run_verdict routes agreement through _agree
    # on the configured value — if the comparison were inlined, this would not raise.
    bad_agreement = POLICY.agreement.model_copy(update={"threshold": "adjacent-tier-ok"})
    bad_policy = POLICY.model_copy(update={"agreement": bad_agreement})
    with pytest.raises(ValueError, match="threshold"):
        run_verdict(
            case_id="c1", maker=_out("high"), checker=_out("high"),
            degraded=False, policy=bad_policy,
        )
