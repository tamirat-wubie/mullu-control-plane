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


def test_app_config_loads_deterministically_from_mapping() -> None:
    config = AppConfig.from_mapping(
        {
            "allowed_planning_classes": ("constraint", "reference"),
            "enabled_executor_routes": ("shell_command",),
            "enabled_observer_routes": ("filesystem",),
        }
    )

    assert config.allowed_planning_classes == ("constraint", "reference")
    assert config.enabled_executor_routes == ("shell_command",)
    assert config.enabled_observer_routes == ("filesystem",)


def test_app_config_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="unknown config keys"):
        AppConfig.from_mapping({"unknown_key": "value"})


def test_app_config_rejects_non_text_autonomy_mode() -> None:
    with pytest.raises(ValueError, match="autonomy_mode"):
        AppConfig.from_mapping({"autonomy_mode": 7})
