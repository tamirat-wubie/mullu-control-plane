"""Purpose: verify deterministic operator-loop configuration loading.
Governance scope: operator-loop tests only.
Dependencies: the local app config module.
Invariants: configuration loads only from passed values and has explicit defaults.
"""

from __future__ import annotations

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
