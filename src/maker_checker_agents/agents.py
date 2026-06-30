"""The Maker and Checker agents — cross-vendor, state-isolated (issue #3, 0008).

Two independently-callable units, ``run_maker`` and ``run_checker``. Independence
is enforced by the **function signature**: ``run_checker(case, policy)`` has no
parameter through which the Maker's output could reach it ([0001], [0005]) — the
"no other classification has been shown to you" prompt line is framing, never the
mechanism.

Vendor dispatch reads ``policy.models`` (Google Maker, Anthropic Checker); both go
through LangChain's uniform ``ChatModel`` interface, which is what keeps the
cross-vendor seam a single code path. ``_invoke`` is the only part that needs the
``live`` optional-dependencies and an API key; tests monkeypatch it, so the real
parse/validate/degradation logic below is exercised directly.

Degradation (0008 §3): an API error, a timeout, an unparseable response, **or a
``risk_tier`` outside the loaded taxonomy** is an agent *failure* — the agent
returns ``None`` and the pipeline routes the case to a human regardless
([0003] fail-open, [0005] always-human). A malformed tier never enters the verdict
comparison (#4).

Citations (0008 §2): agents *do* emit ``articles_cited`` from the model's own
knowledge. These are **ungrounded** — the parametric-bleed failure mode [0007]
names — and *not how the production system grounds them*. The README states this
at the point of output; here a malformed citation list degrades to empty rather
than failing the classification.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, assert_never

from .config import ModelSpec, Policy
from .models import AgentOutput, Case

logger = logging.getLogger(__name__)

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def run_maker(case: Case, policy: Policy) -> AgentOutput | None:
    """Classify ``case`` with the Maker model. ``None`` on agent failure (0008 §3)."""
    return _classify(case, policy, policy.models.maker, policy.prompts.maker_system, "maker")


def run_checker(case: Case, policy: Policy) -> AgentOutput | None:
    """Classify ``case`` with the Checker model, independently of the Maker.

    The signature carries only ``case`` and ``policy`` — there is no parameter
    through which the Maker's output could arrive. Independence is structural.
    """
    return _classify(case, policy, policy.models.checker, policy.prompts.checker_system, "checker")


def _classify(
    case: Case, policy: Policy, spec: ModelSpec, system_prompt: str, label: str
) -> AgentOutput | None:
    """Run one agent end to end; any failure degrades to ``None`` (never raises)."""
    try:
        raw = _invoke(spec, system_prompt.strip(), _build_user_message(case, policy))
        output = _parse_output(raw, policy.risk_tier_ids)
        if output is None:
            logger.warning("%s agent: unparseable or out-of-taxonomy output — degraded", label)
        return output
    except Exception as exc:  # API error, timeout, etc. — fail toward the human
        logger.warning("%s agent failed: %s — degraded", label, exc)
        return None


def _build_user_message(case: Case, policy: Policy) -> str:
    """The classification request: the case, the valid tiers, and the output shape."""
    tiers = "\n".join(f"- {t.id}: {t.label} — {t.description}" for t in policy.risk_taxonomy)
    return (
        "Classify the following AI system against the risk taxonomy.\n\n"
        f"System name: {case.system_name}\n"
        f"Purpose: {case.purpose}\n"
        f"Domain: {case.domain}\n"
        f"Data subjects: {', '.join(case.data_subjects) or 'unspecified'}\n"
        f"Data types: {', '.join(case.data_types) or 'unspecified'}\n"
        f"Description: {case.description or 'none'}\n\n"
        f"Valid risk tiers (choose exactly one id):\n{tiers}\n\n"
        "Respond with a single JSON object and nothing else:\n"
        '{"risk_tier": "<one tier id>", "rationale": "<one or two sentences>", '
        '"articles_cited": ["<article reference>", ...]}'
    )


def _parse_output(text: str, valid_tiers: list[str]) -> AgentOutput | None:
    """Validate the model's response at the agent boundary (0008 §3).

    A tier outside ``valid_tiers``, a missing rationale, or unparseable text is a
    failure → ``None``. A malformed ``articles_cited`` degrades to ``[]`` (citations
    are illustrative, not load-bearing — 0008 §2), it does not fail the agent.
    """
    data = _extract_json(text)
    if data is None:
        return None
    tier = data.get("risk_tier")
    rationale = data.get("rationale")
    if not isinstance(tier, str) or tier not in valid_tiers:
        return None
    if not isinstance(rationale, str) or not rationale.strip():
        return None
    raw_cited = data.get("articles_cited", [])
    cited = (
        [c for c in raw_cited if isinstance(c, str)] if isinstance(raw_cited, list) else []
    )
    return AgentOutput(risk_tier=tier, rationale=rationale, articles_cited=cited)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse the first JSON object in ``text``; ``None`` if there isn't one."""
    candidates = [text]
    match = _JSON_OBJECT.search(text)
    if match is not None:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _invoke(spec: ModelSpec, system: str, user: str) -> str:
    """Call the configured vendor and return the raw text response.

    The only part that needs the ``live`` extras and an API key: it constructs the
    client (``_make_client``) and makes the one network call. The vendor-dispatch
    and response-flattening logic live in ``_make_client`` / ``_extract_text``, which
    are pure and unit-tested against a stubbed transport (0008 Decision 1 contract
    test; #519 — at least one test hits the real dispatch/parse artifact).
    """
    client = _make_client(spec)

    from langchain_core.messages import HumanMessage, SystemMessage

    response: Any = client.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return _extract_text(response.content)


def _make_client(spec: ModelSpec) -> Any:
    """Bind a vendor to its LangChain ``ChatModel`` (the cross-vendor seam).

    Exhaustive over ``Provider`` — a new vendor is a mypy error here, never a silent
    default. Lazy imports keep the ``live`` extras out of CI.
    """
    if spec.provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=spec.model, temperature=0)
    if spec.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=spec.model, temperature=0)
    assert_never(spec.provider)


def _extract_text(content: Any) -> str:
    """Flatten a LangChain message ``content`` into plain text.

    Vendors differ in shape: a ``str`` (Google), a list of content blocks
    (Anthropic returns ``[{"type": "text", "text": ...}, ...]``), or otherwise.
    Pure and total, so the real flattening is exercised without the ``live`` extras.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return str(content)
