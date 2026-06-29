"""Tests for the policy config layer — exercised against the real policy.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from maker_checker_agents.config import ConfigError, load_policy

POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.yaml"


def test_real_policy_loads_and_validates() -> None:
    policy = load_policy(POLICY_PATH)
    assert "unacceptable" in policy.risk_tier_ids
    assert "eu_ai_act" in policy.framework_triggers
    assert policy.models.maker.provider == "google"
    assert policy.models.checker.provider == "anthropic"


def test_missing_file_fails_fast() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_policy("does/not/exist.yaml")


def test_invalid_policy_fails_validation(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text("risk_taxonomy: []\n")  # empty taxonomy + missing required blocks
    with pytest.raises(ConfigError, match="validation"):
        load_policy(bad)


def test_non_mapping_yaml_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text("- just\n- a\n- list\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_policy(bad)
