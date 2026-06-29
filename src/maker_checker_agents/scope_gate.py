"""The scope gate — deterministic, config-driven triage.

Detection over a *known* regulatory taxonomy is a classification problem with a
definable boundary, not a generation problem. So the gate is plain code driven
by ``policy.framework_triggers`` — zero cost, zero latency, and it cannot
hallucinate. Matching is word/token level (a phrase matches when all of its
words are present), which avoids naive-substring traps. Recall is still bounded
by the literal vocabulary — paraphrases it has never seen will be missed; that
is exactly why a semantic / vector router is the production upgrade (see README).

The asymmetric-risk rule: the gate may skip the *expensive model spend* on a
case it is confident is out of scope, but it never skips the *human* —
``ScopeResult.routed_to_human`` is ``Literal[True]`` by type. Any gate error
fails open (every framework treated as applicable, marked degraded) — never a
silent drop.
"""

from __future__ import annotations

import logging
import re

from .config import Policy
from .models import Case, ScopeResult

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(case: Case) -> set[str]:
    blob = " ".join([case.purpose, case.description, case.domain, *case.data_types]).lower()
    return set(_WORD.findall(blob))


def _phrase_present(phrase: str, tokens: set[str]) -> bool:
    """True when every word of ``phrase`` appears in ``tokens`` (order-free)."""
    words = _WORD.findall(phrase.lower())
    return bool(words) and all(word in tokens for word in words)


def run_scope_gate(case: Case, policy: Policy) -> ScopeResult:
    """Decide whether a case is in scope for the expensive maker-checker pair."""
    try:
        tokens = _tokens(case)
        applicable = [
            name
            for name, trigger in policy.framework_triggers.items()
            if any(_phrase_present(kw, tokens) for kw in trigger.keywords)
            or any(_phrase_present(dom, tokens) for dom in trigger.domains)
        ]
        sensitive = any(_phrase_present(kw, tokens) for kw in policy.sensitivity_keywords)
        if applicable:
            return ScopeResult(
                applicable_frameworks=applicable,
                proceed=True,
                sensitive=sensitive,
                reason=f"matched: {', '.join(applicable)}",
            )
        return ScopeResult(
            applicable_frameworks=[],
            proceed=False,
            sensitive=sensitive,
            reason="no governed framework matched — out of scope; human confirmation required",
        )
    except Exception as exc:  # fail open — never drop a case on a gate error
        logger.error("scope gate failed open: %s", exc)
        return ScopeResult(
            applicable_frameworks=list(policy.framework_triggers.keys()),
            proceed=True,
            degraded=True,
            reason=f"gate error, failed open: {exc}",
        )
