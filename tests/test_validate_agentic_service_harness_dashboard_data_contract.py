"""Tests for the Agentic Service Harness dashboard data contract validator.

Purpose: prove the dashboard data contract remains read-only, contract-only,
redacted, and non-terminal before dashboard UI creation, routes, mutation
controls, adapter execution, receipt append, or terminal closure are admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_dashboard_data_contract.
Invariants:
  - Valid default examples pass schema and semantic validation.
  - UI creation, route registration, mutation route strings, missing widgets,
    missing source collections, and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_dashboard_data_contract import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_SOURCE_COLLECTIONS,
    EXPECTED_WIDGET_IDS,
    main,
    validate_agentic_service_harness_dashboard_data_contract,
    write_dashboard_data_contract_validation,
)


def test_dashboard_data_contract_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_dashboard_data_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.read_model_source_ok is True
    assert validation.task_intake_source_ok is True
    assert validation.widget_count == len(EXPECTED_WIDGET_IDS)
    assert validation.source_collection_count == len(EXPECTED_SOURCE_COLLECTIONS)
    assert validation.schema_path == "schemas/agentic_service_harness_dashboard_data_contract.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    )
    payload = _default_payload()
    assert set(payload["data_contract"]["source_collections"]) == EXPECTED_SOURCE_COLLECTIONS
    assert {widget["widget_id"] for widget in payload["widgets"]} == EXPECTED_WIDGET_IDS
    assert payload["scope"]["ui_created"] is False
    assert payload["authority_denials"]["terminal_closure"] is False


def test_dashboard_data_contract_rejects_ui_creation(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["dashboard_implemented"] = True
    payload["scope"]["ui_created"] = True
    payload["widgets"][0]["ui_component_created"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "dashboard_implemented" in serialized_errors
    assert "ui_created" in serialized_errors
    assert "ui_component_created" in serialized_errors


def test_dashboard_data_contract_rejects_route_and_mutation_controls(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["data_contract"]["route_registered"] = True
    payload["data_contract"]["mutation_controls_allowed"] = True
    payload["screen_states"][0]["display_rule"] = "Forbidden route: POST /api/v1/harness/dashboard"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "route_registered" in serialized_errors
    assert "mutation_controls_allowed" in serialized_errors
    assert "mutation route string" in serialized_errors


def test_dashboard_data_contract_rejects_missing_widget(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["widgets"] = [
        widget for widget in payload["widgets"] if widget["widget_id"] != "approval_gate"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "widgets missing" in serialized_errors
    assert "approval_gate" in serialized_errors


def test_dashboard_data_contract_rejects_missing_source_collection(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["data_contract"]["source_collections"] = [
        collection
        for collection in payload["data_contract"]["source_collections"]
        if collection != "github_repo_task_intake"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_collections missing" in serialized_errors
    assert "github_repo_task_intake" in serialized_errors


def test_dashboard_data_contract_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["data_bindings"][0]["serialized_token_value"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_dashboard_data_contract_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "dashboard-data-contract-validation.json"
    validation = validate_agentic_service_harness_dashboard_data_contract()

    written = write_dashboard_data_contract_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["widget_count"] == len(EXPECTED_WIDGET_IDS)


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_dashboard_data_contract.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
