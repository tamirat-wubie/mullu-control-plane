"""Purpose: verify deterministic operator-loop configuration loading.
Governance scope: operator-loop tests only.
Dependencies: the local app config module.
Invariants: configuration loads only from passed values and has explicit defaults.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app.config import AppConfig


def test_app_config_uses_explicit_defaults() -> None:
    config = AppConfig()

    assert config.allowed_planning_classes == ("constraint",)
    assert config.enabled_executor_routes == ("shell_command",)
    assert config.enabled_observer_routes == ("filesystem", "process")
    assert config.policy_pack_id is None
    assert config.policy_pack_version is None
    assert config.effect_assurance_required is False


def test_app_config_loads_deterministically_from_mapping() -> None:
    config = AppConfig.from_mapping(
        {
            "allowed_planning_classes": ("constraint", "reference"),
            "enabled_executor_routes": ("shell_command",),
            "enabled_observer_routes": ("filesystem",),
            "policy_pack_id": "strict-approval",
            "policy_pack_version": "v0.1",
            "effect_assurance_required": True,
        }
    )

    assert config.allowed_planning_classes == ("constraint", "reference")
    assert config.enabled_executor_routes == ("shell_command",)
    assert config.enabled_observer_routes == ("filesystem",)
    assert config.policy_pack_id == "strict-approval"
    assert config.policy_pack_version == "v0.1"
    assert config.effect_assurance_required is True


def test_app_config_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="^unknown config keys$") as exc_info:
        AppConfig.from_mapping({"unknown_key": "value"})
    message = str(exc_info.value)
    assert message == "unknown config keys"
    assert "unknown_key" not in message
    assert "config keys" in message


def test_app_config_rejects_non_text_autonomy_mode() -> None:
    with pytest.raises(ValueError, match="^config values must be non-empty strings$") as exc_info:
        AppConfig.from_mapping({"autonomy_mode": 7})
    message = str(exc_info.value)
    assert message == "config values must be non-empty strings"
    assert "autonomy_mode" not in message
    assert "non-empty strings" in message


def test_app_config_rejects_empty_policy_pack_id() -> None:
    with pytest.raises(ValueError, match="^config values must be non-empty strings$") as exc_info:
        AppConfig.from_mapping({"policy_pack_id": ""})
    message = str(exc_info.value)
    assert message == "config values must be non-empty strings"
    assert "policy_pack_id" not in message
    assert "non-empty strings" in message


def test_app_config_rejects_non_boolean_effect_assurance_flag() -> None:
    with pytest.raises(ValueError, match="^effect_assurance_required must be a boolean$"):
        AppConfig.from_mapping({"effect_assurance_required": "yes"})
