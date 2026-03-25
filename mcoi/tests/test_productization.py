"""Purpose: verify productization — profiles, policy packs, CLI commands.
Governance scope: productization tests only.
Dependencies: profiles, policy packs, CLI.
Invariants: profiles are deterministic; packs load explicitly; CLI is reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from mcoi_runtime.app.cli import build_parser, main
from mcoi_runtime.app.policy_packs import PolicyPack, PolicyPackRegistry, PolicyRule
from mcoi_runtime.app.profiles import (
    ProfileLoadError,
    ProfileName,
    list_profiles,
    load_profile,
)


# --- Profiles ---


def test_load_local_dev_profile() -> None:
    result = load_profile(ProfileName.LOCAL_DEV)
    assert result.profile_name == "local-dev"
    assert "shell_command" in result.config.enabled_executor_routes
    assert "filesystem" in result.config.enabled_observer_routes
    assert result.overrides_applied == 0


def test_load_safe_readonly_profile() -> None:
    result = load_profile(ProfileName.SAFE_READONLY)
    assert "process" not in result.config.enabled_observer_routes


def test_load_profile_with_overrides() -> None:
    result = load_profile(
        ProfileName.LOCAL_DEV,
        overrides={"enabled_observer_routes": ("filesystem",)},
    )
    assert result.overrides_applied == 1
    assert result.config.enabled_observer_routes == ("filesystem",)


def test_unknown_profile_fails() -> None:
    with pytest.raises(ProfileLoadError, match="unknown profile"):
        load_profile("nonexistent-profile")


def test_unknown_override_key_fails() -> None:
    with pytest.raises(ProfileLoadError, match="unknown config key"):
        load_profile(ProfileName.LOCAL_DEV, overrides={"bad_key": "value"})


def test_list_profiles_returns_all() -> None:
    profiles = list_profiles()
    assert "local-dev" in profiles
    assert "safe-readonly" in profiles
    assert "operator-approved" in profiles
    assert "sandboxed" in profiles


# --- Policy Packs ---


def test_builtin_packs_exist() -> None:
    registry = PolicyPackRegistry()
    packs = registry.list_packs()
    pack_ids = tuple(p.pack_id for p in packs)
    assert "default-safe" in pack_ids
    assert "strict-approval" in pack_ids
    assert "readonly-only" in pack_ids


def test_load_packs() -> None:
    registry = PolicyPackRegistry()
    result = registry.load_packs(("default-safe", "strict-approval"))
    assert result.packs_loaded == ("default-safe", "strict-approval")
    assert result.total_rules > 0


def test_load_unknown_pack_fails() -> None:
    registry = PolicyPackRegistry()
    with pytest.raises(ValueError, match="unknown policy pack"):
        registry.load_packs(("nonexistent",))


def test_register_custom_pack() -> None:
    registry = PolicyPackRegistry()
    custom = PolicyPack(
        pack_id="custom-1",
        name="Custom",
        description="test",
        rules=(PolicyRule(
            rule_id="r-1", description="d", condition="c", action="deny",
        ),),
    )
    registry.register(custom)
    assert registry.get("custom-1") is not None


def test_duplicate_pack_fails() -> None:
    registry = PolicyPackRegistry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register(PolicyPack(
            pack_id="default-safe",
            name="dup",
            description="dup",
            rules=(PolicyRule(rule_id="r", description="d", condition="c", action="allow"),),
        ))


def test_policy_rule_validates() -> None:
    with pytest.raises(ValueError, match="action"):
        PolicyRule(rule_id="r", description="d", condition="c", action="invalid")


# --- CLI with profiles ---


def test_cli_profiles_command() -> None:
    exit_code = main(["profiles"])
    assert exit_code == 0


def test_cli_packs_command() -> None:
    exit_code = main(["packs"])
    assert exit_code == 0


def test_cli_status_with_profile() -> None:
    exit_code = main(["--profile", "local-dev", "status"])
    assert exit_code == 0


def test_cli_status_with_shipped_config_examples(capsys: pytest.CaptureFixture[str]) -> None:
    examples_root = Path(__file__).resolve().parent.parent / "examples"

    for config_name in ("config-local-dev.json", "config-safe-readonly.json"):
        exit_code = main(["--config", str(examples_root / config_name), "status"])
        output = capsys.readouterr().out

        assert exit_code == 0
        assert "=== MCOI Runtime Status ===" in output


def test_cli_rejects_malformed_config_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_file = tmp_path / "bad-config.json"
    config_file.write_text('{"enabled_executor_routes": ["shell_command"]', encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(config_file), "status"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "invalid config JSON" in captured.err
    assert str(config_file) in captured.err


def test_cli_rejects_non_object_config_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_file = tmp_path / "bad-config-root.json"
    config_file.write_text('["not", "an", "object"]', encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(config_file), "status"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "config JSON root must be an object" in captured.err


def test_cli_run_with_profile() -> None:
    request = json.dumps({
        "request_id": "prof-1",
        "subject_id": "op",
        "goal_id": "g-1",
        "template": {
            "template_id": "tpl-1",
            "action_type": "shell_command",
            "command_argv": [sys.executable, "-c", "print('profile-test')"],
        },
        "bindings": {},
    })
    exit_code = main(["--profile", "local-dev", "run", request])
    assert exit_code == 1  # verification open = not complete


def test_cli_run_with_example_file(tmp_path: Path) -> None:
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps({
        "request_id": "file-1",
        "subject_id": "op",
        "goal_id": "g-1",
        "template": {
            "template_id": "tpl-1",
            "action_type": "shell_command",
            "command_argv": [sys.executable, "-c", "print('from-file')"],
        },
        "bindings": {},
    }), encoding="utf-8")
    exit_code = main(["run", str(request_file)])
    assert exit_code == 1
