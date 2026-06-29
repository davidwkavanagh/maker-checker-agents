"""The governance layer — typed, fail-fast loading of ``policy.yaml``.

The policy file is the product's most owner-facing asset: a non-technical owner
changes the risk taxonomy, model assignments, agreement strictness, scope rules,
and agent framing here — config, not code. Loading validates eagerly and fails
fast with a clear message, so a malformed policy is caught at startup rather than
mid-classification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(Exception):
    """Raised when the policy file is missing, unreadable, or fails validation."""


class ModelSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model: str


class Models(BaseModel):
    model_config = ConfigDict(frozen=True)

    maker: ModelSpec
    checker: ModelSpec


class RiskTier(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    description: str = ""


class Agreement(BaseModel):
    model_config = ConfigDict(frozen=True)

    threshold: str = "exact"


class FrameworkTrigger(BaseModel):
    model_config = ConfigDict(frozen=True)

    keywords: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class Prompts(BaseModel):
    model_config = ConfigDict(frozen=True)

    maker_system: str
    checker_system: str


class Policy(BaseModel):
    """The validated, in-memory representation of ``policy.yaml``."""

    model_config = ConfigDict(frozen=True)

    risk_taxonomy: list[RiskTier] = Field(min_length=1)
    models: Models
    agreement: Agreement = Field(default_factory=Agreement)
    framework_triggers: dict[str, FrameworkTrigger] = Field(min_length=1)
    sensitivity_keywords: list[str] = Field(default_factory=list)
    prompts: Prompts

    @property
    def risk_tier_ids(self) -> list[str]:
        return [tier.id for tier in self.risk_taxonomy]


def load_policy(path: str | Path) -> Policy:
    """Load and validate the policy file. Fails fast with a clear message."""
    file = Path(path)
    if not file.exists():
        raise ConfigError(f"policy file not found: {file}")
    try:
        raw: Any = yaml.safe_load(file.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"policy file is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("policy file must be a YAML mapping at the top level")
    try:
        return Policy.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"policy file failed validation:\n{exc}") from exc
