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


def test_undecodable_file_is_config_error(tmp_path: Path) -> None:
    """A non-UTF-8 (UTF-16/BOM) policy fails with a clear message, not a raw UnicodeDecodeError."""
    bad = tmp_path / "policy.yaml"
    bad.write_bytes(b"\xff\xfe\x00 not utf-8")
    with pytest.raises(ConfigError, match="could not be read"):
        load_policy(bad)


def test_unreadable_path_is_config_error(tmp_path: Path) -> None:
    """A path that exists but cannot be read (a directory) is a ConfigError, not a raw OSError."""
    with pytest.raises(ConfigError, match="could not be read"):
        load_policy(tmp_path)  # a directory: exists() is True, read_text raises IsADirectoryError


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


def _minimal_policy(**overrides: str) -> str:
    blocks = {
        "taxonomy": "risk_taxonomy:\n  - {id: high, label: High}\n",
        "models": (
            "models:\n  maker: {provider: google, model: g}\n"
            "  checker: {provider: anthropic, model: c}\n"
        ),
        "triggers": "framework_triggers:\n  eu_ai_act:\n    keywords: [biometric]\n",
        "prompts": "prompts:\n  maker_system: m\n  checker_system: c\n",
    }
    blocks.update(overrides)
    return "".join(blocks.values())


def test_duplicate_risk_tier_ids_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    dupes = "risk_taxonomy:\n  - {id: high, label: A}\n  - {id: high, label: B}\n"
    bad.write_text(_minimal_policy(taxonomy=dupes))
    with pytest.raises(ConfigError, match="unique"):
        load_policy(bad)


def test_unsupported_provider_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    typo = (
        "models:\n  maker: {provider: googel, model: g}\n"
        "  checker: {provider: anthropic, model: c}\n"
    )
    bad.write_text(_minimal_policy(models=typo))
    with pytest.raises(ConfigError, match="validation"):
        load_policy(bad)


def test_unknown_agreement_threshold_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text(_minimal_policy() + "agreement:\n  threshold: loose\n")
    with pytest.raises(ConfigError, match="validation"):
        load_policy(bad)
