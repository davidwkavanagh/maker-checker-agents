"""Tests for the domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from maker_checker_agents.models import AgentOutput, Case, Verdict, VerdictResult


def test_case_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        Case(case_id="c1")  # type: ignore[call-arg]


def test_case_is_immutable() -> None:
    case = Case(case_id="c1", system_name="Loan AI", purpose="screen", domain="finance")
    with pytest.raises(ValidationError):
        case.purpose = "changed"  # type: ignore[misc]


def test_verdict_values() -> None:
    assert {v.value for v in Verdict} == {"consistent", "divergent", "inconclusive"}


def test_human_is_always_in_the_loop_by_default() -> None:
    result = VerdictResult(
        case_id="c1",
        verdict=Verdict.CONSISTENT,
        maker=AgentOutput(risk_tier="high", rationale="r"),
        checker=AgentOutput(risk_tier="high", rationale="r"),
    )
    assert result.routed_to_human is True
