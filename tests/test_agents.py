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
import sys
import types
from collections.abc import Callable
from pathlib import Path

import pytest

from maker_checker_agents import agents
from maker_checker_agents.agents import run_checker, run_maker
from maker_checker_agents.config import ModelAssignments, ModelSpec, Provider, load_policy
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


# --- Real dispatch/parse against a stubbed transport (0008 Decision 1, #519) ---
# These exercise the REAL _make_client / _extract_text / _parse_output code without
# the `live` extras or keys — closing the gap where the only test of the real vendor
# path was the CI-skipped live test (the mirror-test battle scar, README §8 / #519).


def _install_fake_vendors(
    monkeypatch: pytest.MonkeyPatch, content: object
) -> None:
    """Stub the lazily-imported vendor + message modules so real `_invoke` runs.

    The fake ChatModel records its construction kwargs and returns a response whose
    `.content` is whatever shape the test wants (str, or Anthropic-style block list).
    """

    class _FakeChat:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def invoke(self, messages: object) -> types.SimpleNamespace:
            return types.SimpleNamespace(content=content)

    for module_name, class_name in (
        ("langchain_anthropic", "ChatAnthropic"),
        ("langchain_google_genai", "ChatGoogleGenerativeAI"),
    ):
        module = types.ModuleType(module_name)
        setattr(module, class_name, _FakeChat)
        monkeypatch.setitem(sys.modules, module_name, module)

    class _Msg:
        def __init__(self, content: object) -> None:
            self.content = content

    messages = types.ModuleType("langchain_core.messages")
    messages.HumanMessage = _Msg  # type: ignore[attr-defined]
    messages.SystemMessage = _Msg  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langchain_core", types.ModuleType("langchain_core"))
    monkeypatch.setitem(sys.modules, "langchain_core.messages", messages)


def test_checker_end_to_end_with_stubbed_anthropic_block_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Checker is Anthropic, which returns content as a *list of blocks* — the
    # real production shape. `_invoke` is NOT patched: real dispatch + flatten + parse.
    payload = [{"type": "text", "text": _ok_payload("limited")}]
    _install_fake_vendors(monkeypatch, payload)
    out = run_checker(CASE, POLICY)
    assert isinstance(out, AgentOutput)
    assert out.risk_tier == "limited"
    assert out.articles_cited == ["Article 6", "Annex III"]


def test_make_client_dispatches_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_vendors(monkeypatch, "")
    client = agents._make_client(ModelSpec(provider="anthropic", model="claude-sonnet-4-6"))
    assert type(client).__name__ == "_FakeChat"
    assert client.kwargs == {"model": "claude-sonnet-4-6", "temperature": 0}


def test_make_client_dispatches_google(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_vendors(monkeypatch, "")
    client = agents._make_client(ModelSpec(provider="google", model="gemini-2.5-pro"))
    assert type(client).__name__ == "_FakeChat"
    assert client.kwargs == {"model": "gemini-2.5-pro", "temperature": 0}


def test_extract_text_passes_through_str() -> None:
    assert agents._extract_text("hello") == "hello"


def test_extract_text_flattens_block_list_and_ignores_non_text() -> None:
    content = ["a", {"type": "text", "text": "b"}, {"type": "image"}, 123, {"text": "c"}]
    assert agents._extract_text(content) == "abc"


def test_extract_text_falls_back_to_str_for_other_shapes() -> None:
    assert agents._extract_text({"foo": "bar"}) == str({"foo": "bar"})


# --- Parse-boundary behaviour the docstrings/0008 claim but did not test --------


def test_json_extracted_from_markdown_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    # The common real LLM shape: prose + a fenced code block. Exercises the regex
    # branch of _extract_json that no bare-json test reaches.
    fenced = f"Here is my classification:\n```json\n{_ok_payload('high')}\n```\n"
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(fenced))
    out = run_maker(CASE, POLICY)
    assert isinstance(out, AgentOutput)
    assert out.risk_tier == "high"


@pytest.mark.parametrize("bad_cited", ['"Article 6"', "{}", "[1, null, true]"])
def test_malformed_articles_cited_degrades_to_empty_not_failure(
    monkeypatch: pytest.MonkeyPatch, bad_cited: str
) -> None:
    # 0008 Decision 2: a malformed citation list degrades to [], it does NOT fail
    # the classification. Citations are illustrative, not load-bearing.
    payload = f'{{"risk_tier": "high", "rationale": "ok", "articles_cited": {bad_cited}}}'
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(payload))
    out = run_maker(CASE, POLICY)
    assert isinstance(out, AgentOutput)
    assert out.articles_cited == []


def test_mixed_articles_cited_keeps_only_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = '{"risk_tier": "high", "rationale": "ok", "articles_cited": [1, "Article 6", null]}'
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(payload))
    out = run_maker(CASE, POLICY)
    assert isinstance(out, AgentOutput)
    assert out.articles_cited == ["Article 6"]


@pytest.mark.parametrize(
    "payload",
    [
        '{"risk_tier": "high", "rationale": ""}',
        '{"risk_tier": "high", "rationale": "   "}',
        '{"risk_tier": "high"}',
        '{"risk_tier": "high", "rationale": 5}',
    ],
)
def test_missing_or_empty_rationale_is_failure(
    monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    # 0008 Decision 3: success requires a rationale. Empty/whitespace/missing/
    # non-string rationale → agent failure (None) → routes to the human.
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(payload))
    assert run_maker(CASE, POLICY) is None


@pytest.mark.parametrize(
    "payload",
    [
        '{"rationale": "ok"}',
        '{"risk_tier": 3, "rationale": "ok"}',
        '{"risk_tier": null, "rationale": "ok"}',
    ],
)
def test_missing_or_nonstring_tier_is_failure(
    monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    monkeypatch.setattr(agents, "_invoke", _stub_invoke(payload))
    assert run_maker(CASE, POLICY) is None


# --- Environment pre-flight (Option E: the adapter owns key requirements) --


def _both(provider: Provider) -> ModelAssignments:
    return ModelAssignments(
        maker=ModelSpec(provider=provider, model="m"),
        checker=ModelSpec(provider=provider, model="c"),
    )


def test_preflight_passes_when_all_required_keys_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    agents.preflight_environment(POLICY.models)  # google + anthropic — no raise


def test_preflight_raises_naming_every_missing_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(agents.AdapterPreflightError) as exc:
        agents.preflight_environment(POLICY.models)
    msg = str(exc.value)
    assert "GOOGLE_API_KEY" in msg and "ANTHROPIC_API_KEY" in msg


def test_preflight_derives_keys_from_config_not_hardcoded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both agents on one vendor must not demand the other vendor's key (config-not-code)."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    agents.preflight_environment(_both("anthropic"))  # no raise: GOOGLE_API_KEY not required


def test_preflight_same_vendor_names_only_that_vendor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(agents.AdapterPreflightError) as exc:
        agents.preflight_environment(_both("anthropic"))
    msg = str(exc.value)
    assert "ANTHROPIC_API_KEY" in msg
    assert "GOOGLE_API_KEY" not in msg


def test_preflight_blocks_on_partial_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """One key present, one missing still blocks — and names only the missing one."""
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(agents.AdapterPreflightError) as exc:
        agents.preflight_environment(POLICY.models)  # google + anthropic
    msg = str(exc.value)
    assert "ANTHROPIC_API_KEY" in msg
    assert "GOOGLE_API_KEY" not in msg  # the present key is not named


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
