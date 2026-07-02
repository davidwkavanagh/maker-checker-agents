"""Tests for the end-to-end runner (issue #5, decision record 0010).

The runner composes four already-tested stages — scope gate, the two agents, the
deterministic verdict — into one run:

    scope gate → (maker ‖ checker, concurrent) → verdict → human

These tests pin the composition, not the stages (those have their own suites).
Five behaviours matter beyond "it wires up":

* **Out of scope skips the spend, never the human.** ``proceed=False`` → the agent
  pair is *not called* and ``verdict`` is ``None``; the case still routes to a human.
* **One agent fails, the run continues; both fail, it cannot proceed.** A single
  ``None`` → INCONCLUSIVE routed for review; both ``None`` → ``PipelineError`` (a run
  failure — the human who started the run gets an error and retries).
* **A degraded (fail-open) gate still runs the pair, and the verdict caps.** The
  ``degraded`` flag is forwarded to the verdict, which caps to INCONCLUSIVE (0009).
* **Parallel, not sequential.** Maker and Checker run at the same time — pinned by a
  ``threading.Barrier`` that only releases if both are in flight at once, so the test
  cannot pass on a sequential implementation (it would deadlock to a timeout).
* **HITL is unconditional** on every returned result, in scope or out.

The agents make real API calls, so they are monkeypatched here — on the *runner's*
namespace, which is where ``run_pipeline`` looks them up.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from maker_checker_agents import pipeline
from maker_checker_agents.config import load_policy
from maker_checker_agents.models import (
    AgentOutput,
    Case,
    PipelineResult,
    ScopeResult,
    Verdict,
)
from maker_checker_agents.pipeline import PipelineError, run_pipeline

POLICY = load_policy(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")


def _out(tier: str) -> AgentOutput:
    """A well-formed agent classification at a given tier."""
    return AgentOutput(risk_tier=tier, rationale=f"classified as {tier}", articles_cited=[])


def _in_scope_case() -> Case:
    """A case the real scope gate matches (``recruitment`` keyword, ``hr`` domain)."""
    return Case(
        case_id="c-in",
        system_name="Applicant ranker",
        purpose="Automated recruitment CV screening",
        domain="hr",
        data_subjects=["job applicants"],
        data_types=["employment history"],
    )


def _out_of_scope_case() -> Case:
    """A case that matches no framework trigger — out of scope."""
    return Case(
        case_id="c-out",
        system_name="NPC pathfinding",
        purpose="Non-player character movement in a video game",
        domain="entertainment",
        data_subjects=[],
        data_types=[],
    )


def _patch_agents(monkeypatch: pytest.MonkeyPatch, maker: object, checker: object) -> None:
    """Replace the agent calls the runner looks up (``pipeline.run_maker`` etc.)."""
    monkeypatch.setattr(pipeline, "run_maker", lambda case, policy: maker)
    monkeypatch.setattr(pipeline, "run_checker", lambda case, policy: checker)


# --- In-scope: the pair runs, the verdict is produced ----------------------


def test_in_scope_agreeing_agents_is_consistent(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_agents(monkeypatch, _out("high"), _out("high"))
    result = run_pipeline(_in_scope_case(), POLICY)
    assert isinstance(result, PipelineResult)
    assert result.scope.proceed is True
    assert result.verdict is not None
    assert result.verdict.verdict is Verdict.CONSISTENT


def test_in_scope_disagreeing_agents_is_divergent(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_agents(monkeypatch, _out("high"), _out("limited"))
    result = run_pipeline(_in_scope_case(), POLICY)
    assert result.verdict is not None
    assert result.verdict.verdict is Verdict.DIVERGENT


def test_in_scope_single_agent_failure_is_inconclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    # The pair ran but ONE agent returned None — the other still classified, so the
    # run continues: INCONCLUSIVE, routed to the human with the one result. Distinct
    # from the out-of-scope skip (verdict None) and from both-fail (raises) below.
    _patch_agents(monkeypatch, None, _out("high"))
    result = run_pipeline(_in_scope_case(), POLICY)
    assert result.verdict is not None
    assert result.verdict.verdict is Verdict.INCONCLUSIVE


def test_hung_agent_times_out_and_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    # A vendor call that never returns must not stall the pipeline: past the timeout
    # the agent is treated as a failure (None). Here the Maker hangs and the Checker
    # succeeds → single-agent-failure path → INCONCLUSIVE, still routed to a human.
    # Deterministic: an Event that is never set (until cleanup) blocks the Maker well
    # past the shrunk 0.3s pipeline timeout — no wall-clock sleep race.
    monkeypatch.setattr(pipeline, "_AGENT_TIMEOUT_SECONDS", 0.3)
    release = threading.Event()

    def _hung_maker(case: Case, policy: object) -> AgentOutput:
        release.wait(timeout=5)  # blocks past the pipeline timeout, then returns cleanly
        return _out("high")

    monkeypatch.setattr(pipeline, "run_maker", _hung_maker)
    monkeypatch.setattr(pipeline, "run_checker", lambda case, policy: _out("high"))
    try:
        result = run_pipeline(_in_scope_case(), POLICY)
        assert result.verdict is not None
        assert result.verdict.maker is None  # the hung Maker degraded to a failure
        assert result.verdict.checker is not None
        assert result.verdict.verdict is Verdict.INCONCLUSIVE
    finally:
        release.set()  # let the abandoned worker finish instead of lingering


def test_both_agents_failing_raises_cannot_proceed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both models down → no classification exists to review → the run cannot proceed.
    # It RAISES rather than returning an INCONCLUSIVE "review" (that is single-agent
    # failure's behaviour, above). A human initiates every run, so the error surfaces
    # to them. This is the FAILED state 0009 deferred to the runner.
    _patch_agents(monkeypatch, None, None)
    with pytest.raises(PipelineError, match="cannot proceed"):
        run_pipeline(_in_scope_case(), POLICY)


# --- Out of scope: skip the spend, never the human -------------------------


def test_out_of_scope_skips_the_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"maker": False, "checker": False}

    def _maker(case: Case, policy: object) -> AgentOutput:
        called["maker"] = True
        return _out("high")

    def _checker(case: Case, policy: object) -> AgentOutput:
        called["checker"] = True
        return _out("high")

    monkeypatch.setattr(pipeline, "run_maker", _maker)
    monkeypatch.setattr(pipeline, "run_checker", _checker)

    result = run_pipeline(_out_of_scope_case(), POLICY)

    assert result.scope.proceed is False
    assert result.verdict is None  # no comparison — the pair never ran
    assert called == {"maker": False, "checker": False}
    assert result.routed_to_human is True


def test_out_of_scope_still_routes_to_human(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_agents(monkeypatch, _out("high"), _out("high"))
    result = run_pipeline(_out_of_scope_case(), POLICY)
    assert result.routed_to_human is True
    assert "human" in result.scope.reason.lower()


# --- Degraded gate: run the pair anyway, cap the verdict -------------------


def test_degraded_gate_runs_agents_and_caps_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force a fail-open scope result: proceed=True, degraded=True. The runner must
    # still run the pair and forward degraded → the verdict caps to INCONCLUSIVE
    # even though the two tiers agree (0009 Decision 2).
    degraded_scope = ScopeResult(
        applicable_frameworks=["eu_ai_act"],
        proceed=True,
        degraded=True,
        reason="gate error, failed open",
    )
    monkeypatch.setattr(pipeline, "run_scope_gate", lambda case, policy: degraded_scope)
    _patch_agents(monkeypatch, _out("high"), _out("high"))

    result = run_pipeline(_in_scope_case(), POLICY)

    assert result.verdict is not None
    # Prove the cap fired on a REAL pair (both agents ran), not via the None-path: with
    # both agents returning "high", a non-forwarded `degraded` would give CONSISTENT.
    assert result.verdict.maker is not None and result.verdict.checker is not None
    assert result.verdict.verdict is Verdict.INCONCLUSIVE
    assert result.verdict.degraded is True


# --- Parallelism: Maker and Checker run concurrently -----------------------


def test_maker_and_checker_run_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    # THE parallelism test — and it is not a mock that would pass sequentially.
    # Both agents wait on a 2-party barrier: it only releases when BOTH have
    # arrived, which can only happen if they are in flight at the same time. A
    # sequential runner would block the first agent forever → BrokenBarrierError
    # at the timeout → test fails. Concurrent → both arrive → both return.
    # Generous timeout: the failure mode we care about (a sequential runner blocking
    # the first agent forever) trips this deterministically; the wide margin only
    # guards against a slow/saturated CI runner producing a spurious BrokenBarrierError.
    barrier = threading.Barrier(2, timeout=30)

    def _agent(case: Case, policy: object) -> AgentOutput:
        barrier.wait()
        return _out("high")

    monkeypatch.setattr(pipeline, "run_maker", _agent)
    monkeypatch.setattr(pipeline, "run_checker", _agent)

    result = run_pipeline(_in_scope_case(), POLICY)

    assert result.verdict is not None
    assert result.verdict.verdict is Verdict.CONSISTENT


# --- HITL is unconditional across every path -------------------------------


@pytest.mark.parametrize(
    ("case_factory", "maker", "checker"),
    [
        (_in_scope_case, _out("high"), _out("high")),      # consistent
        (_in_scope_case, _out("high"), _out("limited")),   # divergent
        (_in_scope_case, None, _out("high")),              # single-agent failure
        (_out_of_scope_case, _out("high"), _out("high")),  # skipped (out of scope)
    ],
)
def test_routed_to_human_is_always_true(
    monkeypatch: pytest.MonkeyPatch,
    case_factory: Callable[[], Case],
    maker: AgentOutput | None,
    checker: AgentOutput | None,
) -> None:
    # `routed_to_human` is `Literal[True]` — it cannot be constructed False, so this
    # assert can't fail on a built result. The behavioural content the parametrize
    # actually pins is that each of these paths RETURNS a routed result rather than
    # raising — the counterpoint to both-fail, which raises (test above).
    _patch_agents(monkeypatch, maker, checker)
    result = run_pipeline(case_factory(), POLICY)
    assert result.routed_to_human is True


# --- The result carries the whole run (what the CLI renders) ---------------


def test_result_carries_scope_verdict_and_correct_attribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Distinct tiers (high vs limited) so a Maker/Checker slot-swap in the fan-out is
    # detectable: the record must attribute "high" to the Maker and "limited" to the
    # Checker, not the reverse. Also pins verdict.case_id and the human-facing note —
    # both land on the audit record, both silently wrong if mis-wired.
    _patch_agents(monkeypatch, _out("high"), _out("limited"))
    result = run_pipeline(_in_scope_case(), POLICY)
    assert result.case_id == "c-in"
    assert result.scope.applicable_frameworks == ["eu_ai_act"]
    assert result.verdict is not None
    assert result.verdict.maker is not None and result.verdict.maker.risk_tier == "high"
    assert result.verdict.checker is not None and result.verdict.checker.risk_tier == "limited"
    assert result.verdict.case_id == "c-in"
    assert result.verdict.notes == "agents assigned different risk tiers"


def test_sensitive_flag_propagates_to_result(monkeypatch: pytest.MonkeyPatch) -> None:
    # A compliance-facing field: the scope gate sets sensitive=True on a sensitivity
    # keyword (here "minors", in the purpose — the gate scans purpose/description/
    # domain/data_types, NOT data_subjects) and the runner must carry it out on the
    # result. No other test exercises sensitive=True, so a dropped flag would ship silently.
    case = Case(
        case_id="c-sens",
        system_name="Applicant ranker",
        purpose="Automated recruitment CV screening of minors",
        domain="hr",
    )
    _patch_agents(monkeypatch, _out("high"), _out("high"))
    result = run_pipeline(case, POLICY)
    assert result.scope.proceed is True
    assert result.scope.sensitive is True
