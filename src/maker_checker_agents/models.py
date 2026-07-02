"""Domain models for the maker-checker pipeline.

The risk-tier vocabulary is deliberately *not* a hardcoded enum: it comes from
the YAML policy layer (see ``config.py``), so a non-technical owner can change
the taxonomy without a code change. Models carry the tier as a validated string
and the pipeline checks it against the loaded policy at runtime.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Verdict(StrEnum):
    """Outcome of the deterministic comparison between the two agents."""

    CONSISTENT = "consistent"
    DIVERGENT = "divergent"
    INCONCLUSIVE = "inconclusive"


class Case(BaseModel):
    """A single classification request — the input to the pipeline."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    system_name: str
    purpose: str = Field(description="What the AI system is for.")
    domain: str = Field(description="Sector / context of deployment.")
    data_subjects: list[str] = Field(default_factory=list)
    data_types: list[str] = Field(default_factory=list)
    description: str = ""


class AgentOutput(BaseModel):
    """An independent classification produced by one agent (Maker or Checker).

    Maker and Checker emit the same shape — independence is about not sharing
    *data*, not about having different schemas.
    """

    model_config = ConfigDict(frozen=True)

    risk_tier: str
    rationale: str
    articles_cited: list[str] = Field(default_factory=list)


class ScopeResult(BaseModel):
    """Outcome of the deterministic scope gate.

    ``proceed`` gates only the *expensive model spend*, never the human.
    ``routed_to_human`` is typed ``Literal[True]``: it is impossible to construct
    a ``ScopeResult`` — in scope or out — that skips the human. This enforces
    routing on every result the gate *builds*; it does not promise the pipeline
    never fails. A run can still fail outright later — both agents down → the
    runner errors rather than routing an empty case ([0010]), never forcing a
    verdict through. ``sensitive`` is set when the case matches the policy's
    sensitivity keywords. ``degraded`` marks a gate that failed open on error.
    """

    model_config = ConfigDict(frozen=True)

    applicable_frameworks: list[str] = Field(default_factory=list)
    proceed: bool
    routed_to_human: Literal[True] = True
    sensitive: bool = False
    degraded: bool = False
    reason: str = ""


class VerdictResult(BaseModel):
    """Deterministic comparison of the two agents plus the routing outcome.

    ``routed_to_human`` is always ``True``: the human carries the decision and is
    never a fallback. Divergence does not gate whether a human is involved — it
    only changes what the human is told.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    verdict: Verdict
    maker: AgentOutput | None
    checker: AgentOutput | None
    degraded: bool = False
    routed_to_human: Literal[True] = True
    notes: str = ""


class PipelineResult(BaseModel):
    """The end-to-end outcome of one run: scope decision + optional verdict.

    ``verdict`` is ``None`` when the scope gate skipped the agent pair (the case was
    out of scope — the expensive spend is skipped, [0010] Decision 4). It is a
    ``VerdictResult`` whenever the pair ran and *at least one* agent classified. If
    both agents fail there is nothing to review, so the runner raises
    ``PipelineError`` instead of returning a result ([0010]). ``routed_to_human`` is
    ``Literal[True]``: every *returned* result reaches a human whether it was
    classified or skipped — enforced by the type, not a comment.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    scope: ScopeResult
    verdict: VerdictResult | None = None
    routed_to_human: Literal[True] = True
