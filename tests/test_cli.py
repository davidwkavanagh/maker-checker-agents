"""Tests for the CLI — the demo surface (issue #6).

The CLI is the repo's only surface ([0006]). It is *two verbs* that mirror the
honesty spine:

* ``list`` — the map: prints the fictional cases and their *illustrative* expected
  tier. Free, deterministic, and runnable **with no API keys** — a first-contact
  cloner's first command succeeds and teaches the scope before the key wall.
* ``run <case-id>`` — the proof: sends one case through ``run_pipeline`` (live
  Maker ‖ Checker) and prints the **reviewer's-eye view** — the *full* decision of
  both agents (tier, rationale, cited articles) plus the verdict and the
  routed-to-human line. This engine hands the whole picture to a human and stops;
  it does not build the review pipeline itself ([0006]).

These tests pin behaviour, not copy. The agents make real paid calls, so
``run_pipeline`` is monkeypatched on the CLI's own namespace (where the CLI looks
it up); the fictional-case *content* is reviewed separately and asserted here only
for structure.

Locked constraints these tests guard:

* **Live calls, own keys, no mock** ([0008] D1). A pre-flight key check (a config
  guard, *not* a replay harness) must fire before any spend.
* **Citation honesty** ([0008] D2). Where citations render, a factual note must say
  they are illustrative/ungrounded — not how production grounds them ([0007]).
* **Unconditional HITL** ([0005]). Every *returned* result routes to a human. The
  one non-routed path is both-agents-fail, which ``run_pipeline`` raises as
  ``PipelineError`` — the CLI must render that as a designed message, never a
  traceback, and never fabricate a verdict.
* **No secret leaks.** No API-key value may ever reach stdout/stderr.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from maker_checker_agents import cli
from maker_checker_agents.cases import DEMO_CASES, DemoCase, get_demo_case
from maker_checker_agents.config import load_policy
from maker_checker_agents.models import (
    AgentOutput,
    Case,
    PipelineResult,
    ScopeResult,
    Verdict,
    VerdictResult,
)
from maker_checker_agents.pipeline import PipelineError
from maker_checker_agents.scope_gate import run_scope_gate
from maker_checker_agents.verdict import run_verdict

POLICY = load_policy(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")

_GOOGLE = "GOOGLE_API_KEY"
_ANTHROPIC = "ANTHROPIC_API_KEY"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _agent(tier: str, cited: list[str] | None = None) -> AgentOutput:
    return AgentOutput(
        risk_tier=tier,
        rationale=f"The system is {tier} because of its stated purpose.",
        articles_cited=cited if cited is not None else ["Article 6", "Annex III"],
    )


def _in_scope_case() -> Case:
    """A case the *real* scope gate matches (``recruitment`` keyword, ``hr`` domain)."""
    return Case(
        case_id="c-in",
        system_name="Applicant ranker",
        purpose="Automated recruitment CV screening",
        domain="hr",
    )


def _result(
    *,
    verdict: Verdict = Verdict.DIVERGENT,
    maker: AgentOutput | None,
    checker: AgentOutput | None,
    proceed: bool = True,
    degraded: bool = False,
    verdict_present: bool = True,
) -> PipelineResult:
    scope = ScopeResult(
        applicable_frameworks=["eu_ai_act"] if proceed else [],
        proceed=proceed,
        degraded=degraded,
    )
    vr = (
        VerdictResult(
            case_id="c-in",
            verdict=verdict,
            maker=maker,
            checker=checker,
            degraded=degraded,
        )
        if verdict_present
        else None
    )
    return PipelineResult(case_id="c-in", scope=scope, verdict=vr)


def _set_keys(
    monkeypatch: pytest.MonkeyPatch, google: str = "g-key", anthropic: str = "a-key"
) -> None:
    monkeypatch.setenv(_GOOGLE, google)
    monkeypatch.setenv(_ANTHROPIC, anthropic)


def _clear_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_GOOGLE, raising=False)
    monkeypatch.delenv(_ANTHROPIC, raising=False)


class _Recorder:
    """A ``run_pipeline`` stand-in that records whether it was called."""

    def __init__(self, result: PipelineResult | None = None, raises: Exception | None = None):
        self.called = False
        self.called_with_case: str | None = None
        self._result = result
        self._raises = raises

    def __call__(self, case: Case, policy: object) -> PipelineResult:
        self.called = True
        self.called_with_case = case.case_id
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


# --------------------------------------------------------------------------- #
# The fictional case set (structure only — content is reviewed separately)
# --------------------------------------------------------------------------- #
def test_demo_cases_are_valid_and_ids_unique() -> None:
    assert len(DEMO_CASES) >= 4
    for demo in DEMO_CASES:
        assert isinstance(demo, DemoCase)
        assert isinstance(demo.case, Case)
    ids = [demo.case.case_id for demo in DEMO_CASES]
    assert len(set(ids)) == len(ids), "case ids must be unique"


def test_expected_tiers_are_in_taxonomy() -> None:
    for demo in DEMO_CASES:
        if demo.expected_tier is not None:
            assert demo.expected_tier in POLICY.risk_tier_ids


def test_case_set_spans_tiers() -> None:
    tiers = {demo.expected_tier for demo in DEMO_CASES if demo.expected_tier is not None}
    assert {"high", "unacceptable"} <= tiers
    assert len(tiers) >= 3, "the set should span at least three tiers"


def test_case_set_includes_a_real_out_of_scope_case() -> None:
    """At least one case the *real* gate skips — bound to the gate, not a label."""
    skipped = [d for d in DEMO_CASES if not run_scope_gate(d.case, POLICY).proceed]
    assert skipped, "need at least one genuinely out-of-scope case"
    assert all(d.expected_tier is None for d in skipped), "out-of-scope cases carry no tier"


def test_case_set_includes_a_divergence_designed_case() -> None:
    assert any(demo.designed_to_diverge for demo in DEMO_CASES)


def test_get_demo_case_lookup() -> None:
    first = DEMO_CASES[0]
    assert get_demo_case(first.case.case_id) is first
    assert get_demo_case("no-such-case") is None


# --------------------------------------------------------------------------- #
# Rendering — pure, no live calls
# --------------------------------------------------------------------------- #
def test_render_result_shows_both_agents_full_decision() -> None:
    maker = _agent("high", cited=["Article 6"])
    checker = _agent("limited", cited=["Article 52"])
    out = cli.render_result(
        _result(verdict=Verdict.DIVERGENT, maker=maker, checker=checker), POLICY
    )
    # both tiers, both rationales, both citation sets — the reviewer sees everything
    assert "high" in out and "limited" in out
    assert maker.rationale in out and checker.rationale in out
    assert "Article 6" in out and "Article 52" in out
    assert "divergent" in out.lower()


def test_render_result_always_shows_routed_to_human() -> None:
    out = cli.render_result(
        _result(verdict=Verdict.CONSISTENT, maker=_agent("high"), checker=_agent("high")),
        POLICY,
    )
    assert "human" in out.lower()


def test_render_result_includes_citation_honesty_note() -> None:
    out = cli.render_result(
        _result(
            verdict=Verdict.CONSISTENT,
            maker=_agent("high", cited=["Article 6"]),
            checker=_agent("high", cited=["Article 6"]),
        ),
        POLICY,
    )
    low = out.lower()
    assert "illustrative" in low or "ungrounded" in low
    assert "0007" in out or "production" in low  # points to the grounded production fix


def test_render_result_out_of_scope_has_no_verdict_but_routes() -> None:
    out = cli.render_result(
        _result(
            verdict=Verdict.CONSISTENT,
            maker=None,
            checker=None,
            proceed=False,
            verdict_present=False,
        ),
        POLICY,
    )
    low = out.lower()
    assert "out of scope" in low or "not classified" in low or "skipped" in low
    assert "human" in low
    # no fabricated verdict word for a skipped case
    assert "consistent" not in low and "divergent" not in low


def test_render_result_surfaces_a_degraded_capped_run() -> None:
    """A degraded (fail-open) run must be visibly flagged as capped.

    Built via the *real* ``run_verdict`` producer, not a hand-set ``degraded`` flag —
    ``render_result`` never reads that flag; degradation reaches output only through
    the authoritative ``notes`` the verdict layer writes on the capped path.
    """
    scope = ScopeResult(applicable_frameworks=["eu_ai_act"], proceed=True, degraded=True)
    vr = run_verdict(
        case_id="c-in",
        maker=_agent("high"),
        checker=_agent("high"),
        degraded=True,
        policy=POLICY,
    )
    out = cli.render_result(PipelineResult(case_id="c-in", scope=scope, verdict=vr), POLICY).lower()
    assert "degraded" in out  # surfaced via the authoritative note
    assert "inconclusive" in out  # the safety cap


def test_render_pipeline_error_is_a_designed_message_not_a_traceback() -> None:
    out = cli.render_pipeline_error()
    low = out.lower()
    assert "cannot proceed" in low or "both" in low
    assert "traceback" not in low


# --------------------------------------------------------------------------- #
# CLI dispatch
# --------------------------------------------------------------------------- #
def test_list_runs_without_keys_and_makes_no_calls(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_keys(monkeypatch)
    recorder = _Recorder()
    monkeypatch.setattr(cli, "run_pipeline", recorder)

    rc = cli.main(["list"])

    assert rc == 0
    assert recorder.called is False, "list must never call the pipeline"
    out = capsys.readouterr().out
    for demo in DEMO_CASES:
        assert demo.case.case_id in out


def test_list_labels_expected_tier_as_illustrative(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["list"])
    out = capsys.readouterr().out.lower()
    assert "illustrative" in out or "expected" in out


def test_run_missing_keys_preflights_and_does_not_spend(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_keys(monkeypatch)
    recorder = _Recorder(result=_result(maker=_agent("high"), checker=_agent("high")))
    monkeypatch.setattr(cli, "run_pipeline", recorder)

    rc = cli.main(["run", DEMO_CASES[0].case.case_id])

    assert rc != 0
    assert recorder.called is False, "must not call the pipeline without keys"
    err = capsys.readouterr().err
    assert _GOOGLE in err and _ANTHROPIC in err


def test_run_unknown_case_id_errors_without_spend(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_keys(monkeypatch)
    recorder = _Recorder(result=_result(maker=_agent("high"), checker=_agent("high")))
    monkeypatch.setattr(cli, "run_pipeline", recorder)

    rc = cli.main(["run", "does-not-exist"])

    assert rc != 0
    assert recorder.called is False
    err = capsys.readouterr().err.lower()
    assert "does-not-exist" in err or "unknown" in err or "not found" in err


def test_run_renders_full_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_keys(monkeypatch)
    result = _result(
        verdict=Verdict.DIVERGENT,
        maker=_agent("high", cited=["Article 6"]),
        checker=_agent("limited", cited=["Article 52"]),
    )
    recorder = _Recorder(result=result)
    monkeypatch.setattr(cli, "run_pipeline", recorder)

    rc = cli.main(["run", DEMO_CASES[0].case.case_id])

    assert rc == 0
    assert recorder.called_with_case == DEMO_CASES[0].case.case_id
    out = capsys.readouterr().out
    assert "high" in out and "limited" in out
    assert "human" in out.lower()
    assert "illustrative" in out.lower() or "ungrounded" in out.lower()


def test_run_both_fail_shows_designed_message_no_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_keys(monkeypatch)
    monkeypatch.setattr(
        cli, "run_pipeline", _Recorder(raises=PipelineError("both agents failed"))
    )

    rc = cli.main(["run", DEMO_CASES[0].case.case_id])

    assert rc != 0
    captured = capsys.readouterr()
    combined = (captured.out + captured.err).lower()
    assert "cannot proceed" in combined or "both" in combined
    assert "traceback" not in combined
    # never fabricate a verdict on failure
    assert "consistent" not in combined and "divergent" not in combined


def test_no_api_key_value_is_ever_printed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret_g = "SECRET-GOOGLE-abc123"
    secret_a = "SECRET-ANTHROPIC-xyz789"
    _set_keys(monkeypatch, google=secret_g, anthropic=secret_a)
    result = _result(maker=_agent("high"), checker=_agent("high"))
    monkeypatch.setattr(cli, "run_pipeline", _Recorder(result=result))

    cli.main(["list"])
    cli.main(["run", DEMO_CASES[0].case.case_id])

    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert secret_g not in blob and secret_a not in blob


def test_no_args_shows_usage_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main([])
    assert rc != 0


def test_render_result_renders_verdict_notes() -> None:
    """F2: render surfaces the verdict layer's authoritative note, not a hand-rolled banner."""
    scope = ScopeResult(applicable_frameworks=["eu_ai_act"], proceed=True)
    vr = VerdictResult(
        case_id="c-in",
        verdict=Verdict.INCONCLUSIVE,
        maker=_agent("high"),
        checker=None,
        notes="one or both agents produced no classification",
    )
    out = cli.render_result(PipelineResult(case_id="c-in", scope=scope, verdict=vr), POLICY)
    assert "one or both agents produced no classification" in out


def test_run_malformed_policy_shows_designed_message_not_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """F1: a missing/malformed policy renders a clean message, never a raw traceback."""
    _set_keys(monkeypatch)
    monkeypatch.setattr(cli, "_POLICY_PATH", tmp_path / "does-not-exist.yaml")
    monkeypatch.setattr(
        cli, "run_pipeline", _Recorder(result=_result(maker=_agent("high"), checker=_agent("high")))
    )

    rc = cli.main(["run", DEMO_CASES[0].case.case_id])

    assert rc != 0
    err = capsys.readouterr().err.lower()
    assert "cannot run" in err
    assert "traceback" not in err


def test_render_result_surfaces_the_sensitivity_flag() -> None:
    """0006: the sensitivity flag is a retained reduction that MUST surface on the CLI."""
    scope = ScopeResult(applicable_frameworks=["eu_ai_act"], proceed=True, sensitive=True)
    vr = VerdictResult(
        case_id="c-in", verdict=Verdict.CONSISTENT, maker=_agent("high"), checker=_agent("high")
    )
    out = cli.render_result(PipelineResult(case_id="c-in", scope=scope, verdict=vr), POLICY).lower()
    assert "sensitive" in out  # the retained-reduction flag surfaces
    assert "eu_ai_act" in out  # matched framework surfaced too (scope context)


def test_render_result_out_of_scope_surfaces_sensitivity() -> None:
    """The sensitivity flag surfaces on the out-of-scope path too (audit-added code)."""
    scope = ScopeResult(applicable_frameworks=[], proceed=False, sensitive=True)
    out = cli.render_result(
        PipelineResult(case_id="c-oos", scope=scope, verdict=None), POLICY
    ).lower()
    assert "out of scope" in out or "skipped" in out
    assert "sensitive" in out


def test_render_result_consistent_shows_agreed_tier_and_verdict_word() -> None:
    """Agreement is the rubber-stamp case — the render MUST show the verdict and the agreed tier."""
    out = cli.render_result(
        _result(verdict=Verdict.CONSISTENT, maker=_agent("high"), checker=_agent("high")),
        POLICY,
    )
    assert "consistent" in out.lower()
    assert "high" in out


def test_list_shows_each_case_expected_tier_and_out_of_scope_label(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bind the map to per-row tier values and the out-of-scope label.

    A mislabeled risk tier on the first compliance-facing artifact is legally
    consequential; asserting only case_ids (as the other list tests do) misses it.
    """
    cli.main(["list"])
    lines = capsys.readouterr().out.splitlines()
    for demo in DEMO_CASES:
        row = next(line for line in lines if demo.case.case_id in line)
        expected = demo.expected_tier if demo.expected_tier is not None else "out of scope"
        assert expected in row, f"{demo.case.case_id} row is missing {expected!r}"


def test_python_m_invocation_runs_list() -> None:
    """The `python -m maker_checker_agents` fallback the ACs imply — exercised end to end."""
    result = subprocess.run(
        [sys.executable, "-m", "maker_checker_agents", "list"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert DEMO_CASES[0].case.case_id in result.stdout
