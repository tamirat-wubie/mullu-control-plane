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
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.deployment_profiles import get_profile as get_deployment_profile
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
    assert "process" in result.config.enabled_observer_routes


def test_load_pilot_prod_profile() -> None:
    result = load_profile(ProfileName.PILOT_PROD)
    assert result.profile_name == "pilot-prod"
    assert result.config.autonomy_mode == "approval_required"
    assert "process" in result.config.enabled_observer_routes
    assert result.config.policy_pack_id == "default-safe"
    assert result.config.policy_pack_version == "v0.1"


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
    assert "pilot-prod" in profiles


def test_config_profiles_match_deployment_profile_inventory() -> None:
    for profile_name in list_profiles():
        deployment_profile = get_deployment_profile(profile_name)
        assert deployment_profile is not None
        loaded = load_profile(profile_name)
        assert loaded.config == AppConfig.from_mapping(deployment_profile.to_config_dict())


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
    with pytest.raises(ValueError, match="^policy pack unavailable$") as exc_info:
        registry.load_packs(("nonexistent",))
    assert "nonexistent" not in str(exc_info.value)


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
    with pytest.raises(ValueError, match="^policy pack already registered$") as exc_info:
        registry.register(PolicyPack(
            pack_id="default-safe",
            name="dup",
            description="dup",
            rules=(PolicyRule(rule_id="r", description="d", condition="c", action="allow"),),
        ))
    assert "default-safe" not in str(exc_info.value)


def test_policy_rule_validates() -> None:
    with pytest.raises(ValueError, match="action"):
        PolicyRule(rule_id="r", description="d", condition="c", action="invalid")


# --- CLI with profiles ---


def test_cli_profiles_command() -> None:
    exit_code = main(["profiles"])
    assert exit_code == 0


def test_cli_profile_help_lists_all_profiles() -> None:
    parser = build_parser()
    profile_action = next(action for action in parser._actions if action.dest == "profile")
    help_text = profile_action.help or ""

    for profile_name in list_profiles():
        assert str(profile_name) in help_text


def test_cli_packs_command() -> None:
    exit_code = main(["packs"])
    assert exit_code == 0


def test_cli_status_with_profile() -> None:
    exit_code = main(["--profile", "local-dev", "status"])
    assert exit_code == 0


def test_cli_status_with_pilot_prod_profile() -> None:
    exit_code = main(["--profile", "pilot-prod", "status"])
    assert exit_code == 0


def test_cli_status_with_shipped_config_examples(capsys: pytest.CaptureFixture[str]) -> None:
    examples_root = Path(__file__).resolve().parent.parent / "examples"
    config_examples = sorted(examples_root.glob("config-*.json"))

    assert config_examples

    for config_path in config_examples:
        exit_code = main(["--config", str(config_path), "status"])
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
    assert "malformed JSON (JSONDecodeError)" in captured.err
    assert str(config_file) not in captured.err
    assert "Expecting" not in captured.err


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
    assert str(config_file) not in captured.err


def test_cli_bounds_unexpected_config_validation_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcoi_runtime.app import cli as cli_module

    config_file = tmp_path / "bad-config-value.json"
    config_file.write_text('{"enabled_executor_routes": ["shell_command"]}', encoding="utf-8")

    def _raise_unexpected(_data: object) -> AppConfig:
        raise ValueError("secret backend invariant detail")

    monkeypatch.setattr(cli_module.AppConfig, "from_mapping", _raise_unexpected)

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(config_file), "status"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "invalid config file (ValueError)" in captured.err
    assert "secret backend invariant detail" not in captured.err
    assert str(config_file) not in captured.err


def test_cli_rejects_config_with_unknown_keys(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_file = tmp_path / "unknown-config.json"
    config_file.write_text(
        json.dumps(
            {
                "enabled_executor_routes": ["shell_command"],
                "enabled_observer_routes": ["filesystem"],
                "allowed_planning_classes": ["constraint"],
                "unexpected_key": "drift",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(config_file), "status"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "unknown config keys" in captured.err
    assert str(config_file) not in captured.err


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


def test_cli_rejects_request_with_unknown_top_level_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = json.dumps(
        {
            "request_id": "req-unknown-1",
            "subject_id": "operator-1",
            "goal_id": "goal-1",
            "template": {
                "template_id": "tpl-1",
                "action_type": "shell_command",
                "command_argv": [sys.executable, "-c", "print('x')"],
            },
            "bindings": {},
            "unexpected_field": True,
        }
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["run", request])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "unsupported request fields" in captured.err
    assert "unexpected_field" not in captured.err


def test_cli_rejects_request_missing_identity_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = json.dumps(
        {
            "subject_id": "operator-1",
            "goal_id": "goal-1",
            "template": {
                "template_id": "tpl-1",
                "action_type": "shell_command",
                "command_argv": [sys.executable, "-c", "print('x')"],
            },
            "bindings": {},
        }
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["run", request])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "request identity fields must be non-empty strings" in captured.err
    assert "request_id" not in captured.err
    assert "inline input" not in captured.err


def test_cli_redacts_config_file_access_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_file = tmp_path / "config-protected.json"
    config_file.write_text("{}", encoding="utf-8")
    original_read_text = Path.read_text

    def _denied(self: Path, *args, **kwargs):
        if self == config_file:
            raise PermissionError("secret filesystem detail")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _denied)

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(config_file), "status"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "cannot read config file" in captured.err
    assert "file access denied (PermissionError)" in captured.err
    assert "secret filesystem detail" not in captured.err
    assert str(config_file) not in captured.err


def test_cli_redacts_request_file_access_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_file = tmp_path / "request-protected.json"
    request_file.write_text("{}", encoding="utf-8")
    original_read_text = Path.read_text

    def _denied(self: Path, *args, **kwargs):
        if self == request_file:
            raise PermissionError("secret request detail")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _denied)

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(request_file)])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "cannot read request file" in captured.err
    assert "file access denied (PermissionError)" in captured.err
    assert "secret request detail" not in captured.err
    assert str(request_file) not in captured.err


class _FakeHTTPResponse:
    def __init__(self, *, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_cli_demo_redacts_unreachable_server_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.error
    import urllib.request

    def _urlopen(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError("secret socket detail"))

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)

    exit_code = main(["demo"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Server not reachable at http://localhost:8000" in captured.out
    assert "http transport failed (ConnectionRefusedError)" in captured.out
    assert "secret socket detail" not in captured.out


def test_cli_demo_bounds_invalid_register_response(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.request

    def _urlopen(request, timeout=0):
        url = request.full_url if hasattr(request, "full_url") else request
        if url == "http://localhost:8000/health":
            return _FakeHTTPResponse(status=200, body=b"{}")
        if url == "http://localhost:8000/api/v1/agent/register":
            return _FakeHTTPResponse(status=200, body=b"not-json")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)

    exit_code = main(["demo"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "[1] Register agent: failed (invalid JSON response (JSONDecodeError))" in captured.out
    assert "not-json" not in captured.out


def test_cli_demo_bounds_audit_check_and_completes(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json as _json
    import urllib.request

    def _urlopen(request, timeout=0):
        url = request.full_url if hasattr(request, "full_url") else request
        if url == "http://localhost:8000/health":
            return _FakeHTTPResponse(status=200, body=b"{}")
        if url == "http://localhost:8000/api/v1/agent/register":
            return _FakeHTTPResponse(status=200, body=_json.dumps({"agent_id": "demo-agent"}).encode("utf-8"))
        if url == "http://localhost:8000/api/v1/agent/action-request":
            return _FakeHTTPResponse(
                status=200,
                body=_json.dumps({"decision": "allow", "action_id": "action-1"}).encode("utf-8"),
            )
        if url == "http://localhost:8000/api/v1/agent/action-result":
            return _FakeHTTPResponse(status=200, body=b"{}")
        if url == "http://localhost:8000/api/v1/audit?action=agent.adapter.action_request&limit=5":
            return _FakeHTTPResponse(status=200, body=b"not-json")
        if url == "http://localhost:8000/api/v1/agent/heartbeat":
            return _FakeHTTPResponse(status=200, body=b"{}")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)

    exit_code = main(["demo"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[4] Audit trail: check failed (invalid JSON response (JSONDecodeError))" in captured.out
    assert "[5] Heartbeat sent: healthy" in captured.out
    assert "not-json" not in captured.out
