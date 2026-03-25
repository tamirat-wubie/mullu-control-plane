"""Purpose: verify shipped example artifacts remain governed and executable in shape.
Governance scope: product-facing JSON artifact validation only.
Dependencies: artifact validation script and local example inventory.
Invariants: shipped config and request artifacts fail closed on drift and remain deterministic to discover.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_artifacts


def test_example_inventory_covers_shipped_and_pilot_artifacts() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    config_names = {path.name for path in inventory.config_paths}
    request_names = {path.name for path in inventory.request_paths}
    auxiliary_names = {path.name for path in inventory.auxiliary_paths}
    pilot_names = {path.name for path in inventory.pilot_directories}

    assert "config-local-dev.json" in config_names
    assert "request-echo.json" in request_names
    assert "input_document.json" in auxiliary_names
    assert "approval_gated_command" in pilot_names


def test_validate_example_artifacts_strictly() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    errors = validate_artifacts.validate_example_artifacts(strict=True)

    assert errors == []
    assert len(inventory.config_paths) >= 5
    assert len(inventory.request_paths) >= 3
    assert len(inventory.auxiliary_paths) >= 1


def test_validate_config_artifact_rejects_unknown_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "config-invalid.json"
    config_path.write_text(
        json.dumps(
            {
                "allowed_planning_classes": ["constraint"],
                "enabled_executor_routes": ["shell_command"],
                "enabled_observer_routes": ["filesystem"],
                "unexpected_key": "drift",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_config_artifact(config_path)

    assert len(errors) == 1
    assert "unknown config keys" in errors[0]
    assert config_path.name in errors[0]


def test_validate_request_artifact_rejects_unknown_fields(tmp_path: Path) -> None:
    request_path = tmp_path / "request-invalid.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "req-1",
                "subject_id": "operator-1",
                "goal_id": "goal-1",
                "template": {
                    "template_id": "tpl-1",
                    "action_type": "shell_command",
                    "command_argv": [sys.executable, "-c", "print('ok')"],
                },
                "bindings": {},
                "unexpected_field": True,
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_request_artifact(request_path)

    assert len(errors) == 1
    assert "unsupported request fields" in errors[0]
    assert "unexpected_field" in errors[0]


def test_validate_request_artifact_accepts_runtime_binding_template(tmp_path: Path) -> None:
    request_path = tmp_path / "request-runtime-binding.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "req-bind-1",
                "subject_id": "operator-1",
                "goal_id": "goal-bind-1",
                "template": {
                    "template_id": "tpl-bind-1",
                    "action_type": "shell_command",
                    "command_argv": ["{python_executable}", "-c", "print('bound')"],
                },
                "bindings": {},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_request_artifact(request_path)
    payload = json.loads(request_path.read_text(encoding="utf-8"))

    assert errors == []
    assert payload["template"]["command_argv"][0] == "{python_executable}"
    assert request_path.name.endswith(".json")


def test_validate_auxiliary_pilot_artifact_accepts_shipped_document_input() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    auxiliary_path = next(
        path for path in inventory.auxiliary_paths if path.name == "input_document.json"
    )

    errors = validate_artifacts.validate_example_artifacts(strict=True)

    assert errors == []
    assert auxiliary_path.exists()
    assert auxiliary_path.parent.name == "document_to_action"


def test_validate_auxiliary_pilot_document_rejects_missing_required_fields(tmp_path: Path) -> None:
    auxiliary_path = tmp_path / "input_document.json"
    auxiliary_path.write_text(
        json.dumps(
            {
                "task": "backup_database",
                "target": "production_db",
                "notify_email": "ops@example.com",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_auxiliary_artifact(
        auxiliary_path,
        artifact_key="examples/pilots/document_to_action/input_document.json",
    )

    assert len(errors) == 1
    assert "missing auxiliary fields" in errors[0]
    assert "retention_days" in errors[0]


def test_validate_auxiliary_pilot_document_rejects_non_positive_retention_days(tmp_path: Path) -> None:
    auxiliary_path = tmp_path / "input_document.json"
    auxiliary_path.write_text(
        json.dumps(
            {
                "task": "backup_database",
                "target": "production_db",
                "retention_days": 0,
                "notify_email": "ops@example.com",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_auxiliary_artifact(
        auxiliary_path,
        artifact_key="examples/pilots/document_to_action/input_document.json",
    )

    assert len(errors) == 1
    assert "retention_days" in errors[0]
    assert "positive integer" in errors[0]
