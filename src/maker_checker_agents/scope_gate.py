"""The scope gate — deterministic, config-driven triage.

Detection over a *known* regulatory taxonomy is a classification problem with a
definable boundary, not a generation problem. So the gate is plain code driven
by ``policy.framework_triggers`` — zero cost, zero latency, and it cannot
hallucinate. (A semantic / vector router is the production upgrade; see README.)

The asymmetric-risk rule: the gate may skip the *expensive model spend* on a
case it is confident is out of scope, but it never short-circuits the *human*.
Out-of-scope cases are still routed to a reviewer, and any gate error fails open
(every framework treated as applicable, marked degraded) — never a silent drop.
"""

from __future__ import annotations

import logging

from .config import Policy
from .models import Case, ScopeResult

logger = logging.getLogger(__name__)


def _matches(case: Case, keywords: list[str], domains: list[str]) -> bool:
    haystack = " ".join([case.purpose, case.description, *case.data_types]).lower()
    if any(keyword.lower() in haystack for keyword in keywords):
        return True
    return case.domain.lower() in {domain.lower() for domain in domains}


def run_scope_gate(case: Case, policy: Policy) -> ScopeResult:
    """Decide whether a case is in scope for the expensive maker-checker pair."""
    try:
        applicable = [
            name
            for name, trigger in policy.framework_triggers.items()
            if _matches(case, trigger.keywords, trigger.domains)
        ]
        if applicable:
            return ScopeResult(
                applicable_frameworks=applicable,
                proceed=True,
                reason=f"matched: {', '.join(applicable)}",
            )
        return ScopeResult(
            applicable_frameworks=[],
            proceed=False,
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
