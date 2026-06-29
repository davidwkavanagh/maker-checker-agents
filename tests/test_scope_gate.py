"""Tests for the deterministic scope gate — against the real policy.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from maker_checker_agents import scope_gate
from maker_checker_agents.config import load_policy
from maker_checker_agents.models import Case
from maker_checker_agents.scope_gate import run_scope_gate

POLICY = load_policy(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")


def test_in_scope_case_proceeds() -> None:
    case = Case(
        case_id="c1",
        system_name="Loan screener",
        purpose="Automated credit scoring for loan applications",
        domain="finance",
    )
    result = run_scope_gate(case, POLICY)
    assert result.proceed is True
    assert "eu_ai_act" in result.applicable_frameworks


def test_in_scope_by_domain_only() -> None:
    case = Case(case_id="c2", system_name="HR helper", purpose="Assist with paperwork", domain="hr")
    assert run_scope_gate(case, POLICY).proceed is True


def test_out_of_scope_skips_pair_but_never_the_human() -> None:
    case = Case(
        case_id="c3",
        system_name="Recipe suggester",
        purpose="Suggest dinner recipes from pantry items",
        domain="cooking",
    )
    result = run_scope_gate(case, POLICY)
    assert result.proceed is False
    assert result.applicable_frameworks == []
    # The invariant is the typed field, not a phrase in the reason string.
    assert result.routed_to_human is True


def test_partial_phrase_does_not_match() -> None:
    # "recognition" present but "facial"/"emotion" absent -> no trigger phrase complete.
    case = Case(
        case_id="c4",
        system_name="Dictation",
        purpose="speech recognition for note taking",
        domain="consumer",
    )
    assert run_scope_gate(case, POLICY).proceed is False


def test_sensitivity_keyword_flags_case() -> None:
    case = Case(
        case_id="c5",
        system_name="School tool",
        purpose="recruitment screening involving children",
        domain="education",
    )
    result = run_scope_gate(case, POLICY)
    assert result.proceed is True
    assert result.sensitive is True


def test_gate_fails_open_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(scope_gate, "_phrase_present", boom)
    case = Case(case_id="c6", system_name="X", purpose="credit scoring", domain="finance")
    result = run_scope_gate(case, POLICY)
    assert result.proceed is True
    assert result.degraded is True
    assert set(result.applicable_frameworks) == set(POLICY.framework_triggers)
    assert result.routed_to_human is True
