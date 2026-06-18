"""Validate assistant profile registry parity.

Purpose: prove assistant_profiles YAML files cannot drift from runtime profile
contracts without a deterministic validation failure.
Governance scope: profile authority, capability boundaries, protected denials,
and no-secret profile publication.
Dependencies: scripts.validate_assistant_profile_registry.
Invariants:
  - Registry files match runtime profile policy fields.
  - Protected forbidden capabilities are enforced by runtime profile contracts.
  - Drift and secret-like payloads fail closed.
"""

from __future__ import annotations

import shutil

from scripts.validate_assistant_profile_registry import (
    DEFAULT_PROFILE_DIR,
    PROTECTED_FORBIDDEN_CAPABILITIES,
    parse_bounded_profile_yaml,
    validate_assistant_profile_registry,
)


def _copy_profiles(target_dir) -> None:
    target_dir.mkdir(exist_ok=True)
    for source in DEFAULT_PROFILE_DIR.glob("*.default.yaml"):
        shutil.copyfile(source, target_dir / source.name)


def test_assistant_profile_registry_matches_runtime_profiles() -> None:
    result = validate_assistant_profile_registry()

    assert result.valid is True
    assert result.profile_count == 6
    assert result.runtime_profile_count == 6
    assert "finance_ops.default" in result.profile_ids
    assert "team_ops.default" in result.profile_ids
    assert set(PROTECTED_FORBIDDEN_CAPABILITIES) == set(result.protected_forbidden_capabilities)
    assert result.errors == ()


def test_assistant_profile_registry_detects_allowed_capability_drift(tmp_path) -> None:
    _copy_profiles(tmp_path)
    finance_path = tmp_path / "finance_ops.default.yaml"
    finance_text = finance_path.read_text(encoding="utf-8")
    finance_path.write_text(finance_text.replace("  - payment.execute.with_approval\n", ""), encoding="utf-8")

    result = validate_assistant_profile_registry(profile_dir=tmp_path)

    assert result.valid is False
    assert result.profile_count == 6
    assert any("finance_ops.default: allowed_capabilities drift" in error for error in result.errors)
    assert all("payment.execute.with_approval" not in error or "drift" in error for error in result.errors)


def test_assistant_profile_registry_detects_identity_and_skill_drift(tmp_path) -> None:
    _copy_profiles(tmp_path)
    team_path = tmp_path / "team_ops.default.yaml"
    team_text = team_path.read_text(encoding="utf-8")
    team_path.write_text(
        team_text.replace("kind: team_ops\n", "kind: founder\n").replace(
            "  - skill.team_ops.owner_assignment\n", ""
        ),
        encoding="utf-8",
    )

    result = validate_assistant_profile_registry(profile_dir=tmp_path)

    assert result.valid is False
    assert result.profile_count == 6
    assert any("team_ops.default: kind drift" in error for error in result.errors)
    assert any("team_ops.default: skill_ids drift" in error for error in result.errors)
    assert not any("allowed_capabilities drift" in error for error in result.errors)


def test_assistant_profile_registry_rejects_cross_kind_skill_namespace(tmp_path) -> None:
    _copy_profiles(tmp_path)
    team_path = tmp_path / "team_ops.default.yaml"
    team_text = team_path.read_text(encoding="utf-8")
    team_path.write_text(
        team_text.replace("  - skill.team_ops.owner_assignment\n", "  - skill.finance_ops.invoice_intake\n"),
        encoding="utf-8",
    )

    result = validate_assistant_profile_registry(profile_dir=tmp_path)

    assert result.valid is False
    assert result.profile_count == 6
    assert any("team_ops.default.yaml: skill_ids outside kind namespace" in error for error in result.errors)
    assert any("team_ops.default: skill_ids drift" in error for error in result.errors)
    assert not any("kind drift" in error for error in result.errors)


def test_assistant_profile_registry_detects_forbidden_floor_drift(tmp_path) -> None:
    _copy_profiles(tmp_path)
    team_path = tmp_path / "team_ops.default.yaml"
    team_text = team_path.read_text(encoding="utf-8")
    team_path.write_text(team_text.replace("  - policy.modify\n", ""), encoding="utf-8")

    result = validate_assistant_profile_registry(profile_dir=tmp_path)

    assert result.valid is False
    assert result.profile_count == 6
    assert any("team_ops.default: forbidden_capabilities drift after protected floor" in error for error in result.errors)
    assert "policy.modify" in result.protected_forbidden_capabilities


def test_assistant_profile_registry_rejects_secret_like_payload(tmp_path) -> None:
    _copy_profiles(tmp_path)
    personal_path = tmp_path / "personal.default.yaml"
    personal_path.write_text(
        personal_path.read_text(encoding="utf-8") + "\nsecret_marker: sk_live_forbiddenprofilevalue\n",
        encoding="utf-8",
    )

    result = validate_assistant_profile_registry(profile_dir=tmp_path)

    assert result.valid is False
    assert result.profile_count == 6
    assert any("unknown profile fields ['secret_marker']" in error for error in result.errors)
    assert any("secret-like value must not be serialized" in error for error in result.errors)


def test_bounded_profile_yaml_parser_rejects_unsupported_indentation() -> None:
    try:
        parse_bounded_profile_yaml("assistant_id: personal.default\n    nested: denied\n")
    except ValueError as exc:
        message = str(exc)
    else:  # pragma: no cover - unsupported YAML must fail closed.
        raise AssertionError("unsupported indentation was accepted")

    assert "unsupported indentation" in message
    assert "line 2" in message
    assert "nested" not in parse_bounded_profile_yaml("assistant_id: personal.default\n")
