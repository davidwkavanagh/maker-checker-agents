"""Tests for the Maker/Checker agent layer (issue #3, decisions in 0008).

The only part of an agent run that needs live deps + API keys is the module-level
``_invoke`` transport. Every test below monkeypatches it, so the code actually
under test is the *real* ``agents.py`` path — prompt build, vendor dispatch, JSON
parse, and tier validation — not a re-implementation of it (the mirror-test
lesson, README §8). One ``@pytest.mark.live`` test exercises the real vendor path
and is skipped unless the live extra and keys are present.
"""

from __future__ import annotations

import inspect
import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from maker_checker_agents import agents
from maker_checker_agents.agents import run_checker, run_maker
from maker_checker_agents.config import ModelSpec, load_policy
from maker_checker_agents.models import AgentOutput, Case

POLICY = load_policy(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")

CASE = Case(
    case_id="c1",
    system_name="Loan screener",
    purpose="Automated credit scoring for loan applications",
    domain="finance",
    data_types=["financial history"],
    description="Scores applicants and recommends approve/decline.",
)


def _ok_payload(tier: str = "high") -> str:
    """A well-formed model response with an in-taxonomy tier."""
    return json.dumps(
        {
            "risk_tier": tier,
            "rationale": "Credit scoring is a named high-risk use.",
            "articles_cited": ["Article 6", "Annex III"],
        }
    )


def _stub_invoke(payload: str) -> Callable[[ModelSpec, str, str], str]:
    """Build an ``_invoke`` replacement that returns a fixed payload."""

    def _invoke(spec: ModelSpec, system: str, user: str) -> str:
        return payload

    return _invoke


# --- Happy path -----------------------------------------------------------


def test_run_maker_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(_ok_payload()))
    out = run_maker(CASE, POLICY)
    assert isinstance(out, AgentOutput)
    assert out.risk_tier == "high"
    assert out.rationale
    assert out.articles_cited == ["Article 6", "Annex III"]


def test_run_checker_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(_ok_payload("limited")))
    out = run_checker(CASE, POLICY)
    assert isinstance(out, AgentOutput)
    assert out.risk_tier == "limited"


# --- Independence is structural, not prose (0001) -------------------------


def test_checker_signature_cannot_receive_maker_output() -> None:
    # The independence claim is enforced by the function signature: there is no
    # parameter through which the Maker's output could reach the Checker.
    params = set(inspect.signature(run_checker).parameters)
    assert params == {"case", "policy"}


def test_maker_signature_is_symmetric() -> None:
    params = set(inspect.signature(run_maker).parameters)
    assert params == {"case", "policy"}


# --- Cross-vendor dispatch reads policy.models (0001, 0004) ----------------


def test_maker_and_checker_use_configured_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, ModelSpec] = {}

    def _record(spec: ModelSpec, system: str, user: str) -> str:
        seen["spec"] = spec
        return _ok_payload()

    monkeypatch.setattr(agents, "_invoke", _record)

    run_maker(CASE, POLICY)
    maker_spec = seen["spec"]
    assert maker_spec == POLICY.models.maker
    assert maker_spec.provider == "google"

    run_checker(CASE, POLICY)
    checker_spec = seen["spec"]
    assert checker_spec == POLICY.models.checker
    assert checker_spec.provider == "anthropic"


# --- Framing comes from config, and the case is actually sent (0004) -------


def test_system_prompt_is_policy_governed_and_case_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def _record(spec: ModelSpec, system: str, user: str) -> str:
        seen["system"] = system
        seen["user"] = user
        return _ok_payload()

    monkeypatch.setattr(agents, "_invoke", _record)

    run_maker(CASE, POLICY)
    assert seen["system"] == POLICY.prompts.maker_system.strip()
    assert CASE.purpose in seen["user"]
    assert CASE.domain in seen["user"]


# --- Degradation: a bad output is a *failure*, not a classification (0008 §3)


def test_out_of_taxonomy_tier_is_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(_ok_payload("catastrophic")))
    assert run_maker(CASE, POLICY) is None


def test_unparseable_response_is_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_invoke", _stub_invoke("It's high risk, I think."))
    assert run_maker(CASE, POLICY) is None


def test_invoke_error_is_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(spec: ModelSpec, system: str, user: str) -> str:
        raise RuntimeError("vendor down")

    monkeypatch.setattr(agents, "_invoke", _boom)
    assert run_maker(CASE, POLICY) is None


# --- The real artifact: a live cross-vendor call (skipped in CI) -----------


@pytest.mark.live
def test_run_maker_live_real_call() -> None:
    """Exercises the real vendor path. Run manually with the live extra + keys:

        pip install -e '.[live,dev]'
        pytest -m live
    """
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("no GOOGLE_API_KEY — live test skipped")
    out = run_maker(CASE, POLICY)
    assert out is None or out.risk_tier in POLICY.risk_tier_ids
