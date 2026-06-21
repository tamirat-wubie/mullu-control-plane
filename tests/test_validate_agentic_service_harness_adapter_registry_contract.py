"""Tests for the Agentic Service Harness adapter registry contract validator.

Purpose: prove the adapter registry contract remains read-only, contract-only,
redacted, and non-terminal before subprocess execution, connector calls,
external model execution, adapter execution, branch writes, PR creation,
receipt append, mutation routes, or terminal closure are admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_adapter_registry_contract.
Invariants:
  - Valid default examples pass schema and semantic validation.
  - Execution authority, connector calls, missing adapters, missing modes,
    mutation route strings, and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_adapter_registry_contract import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_ADAPTER_IDS,
    EXPECTED_FORBIDDEN_ACTION_CLASSES,
    EXPECTED_GATE_REFS,
    EXPECTED_MODE_IDS,
    main,
    validate_agentic_service_harness_adapter_registry_contract,
    write_adapter_registry_contract_validation,
)


def test_adapter_registry_contract_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_adapter_registry_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.dashboard_source_ok is True
    assert validation.task_intake_source_ok is True
    assert validation.adapter_count == len(EXPECTED_ADAPTER_IDS)
    assert validation.mode_count == len(EXPECTED_MODE_IDS)
    assert validation.schema_path == "schemas/agentic_service_harness_adapter_registry_contract.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_adapter_registry_contract.foundation.json",
    )
    payload = _default_payload()
    assert {adapter["adapter_id"] for adapter in payload["adapters"]} == EXPECTED_ADAPTER_IDS
    assert {mode["mode_id"] for mode in payload["mode_bindings"]} == EXPECTED_MODE_IDS
    assert set(payload["registry"]["forbidden_action_classes"]) == EXPECTED_FORBIDDEN_ACTION_CLASSES
    assert set(payload["registry"]["required_gate_refs"]) == EXPECTED_GATE_REFS
    assert payload["authority_denials"]["terminal_closure"] is False


def test_adapter_registry_contract_rejects_execution_enablement(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["subprocess_execution_enabled"] = True
    payload["scope"]["external_model_execution_enabled"] = True
    payload["adapters"][0]["live_integration_enabled"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_adapter_registry_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "subprocess_execution_enabled" in serialized_errors
    assert "external_model_execution_enabled" in serialized_errors
    assert "live_integration_enabled" in serialized_errors


def test_adapter_registry_contract_rejects_repository_effects(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["adapters"][1]["branch_write_enabled"] = True
    payload["adapters"][1]["pull_request_creation_enabled"] = True
    payload["authority_denials"]["receipt_store_append_enabled"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_adapter_registry_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "branch_write_enabled" in serialized_errors
    assert "pull_request_creation_enabled" in serialized_errors
    assert "receipt_store_append_enabled" in serialized_errors


def test_adapter_registry_contract_rejects_missing_adapter(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["adapters"] = [
        adapter
        for adapter in payload["adapters"]
        if adapter["adapter_id"] != "codex_style_planning_adapter"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_adapter_registry_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "adapters missing" in serialized_errors
    assert "codex_style_planning_adapter" in serialized_errors


def test_adapter_registry_contract_rejects_missing_mode_binding(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["mode_bindings"] = [
        mode
        for mode in payload["mode_bindings"]
        if mode["mode_id"] != "open_pr_awaiting_approval"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_adapter_registry_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mode_bindings missing" in serialized_errors
    assert "open_pr_awaiting_approval" in serialized_errors


def test_adapter_registry_contract_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["registry"]["blocked_reason_refs"] = [
        *payload["registry"]["blocked_reason_refs"],
        "Forbidden route: POST /api/v1/harness/adapters",
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_adapter_registry_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "blocked_reason_refs" in serialized_errors


def test_adapter_registry_contract_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["adapters"][0]["serialized_access_token"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_adapter_registry_contract(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_adapter_registry_contract_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "adapter-registry-contract-validation.json"
    validation = validate_agentic_service_harness_adapter_registry_contract()

    written = write_adapter_registry_contract_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["adapter_count"] == len(EXPECTED_ADAPTER_IDS)
    assert stdout_payload["mode_count"] == len(EXPECTED_MODE_IDS)


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_adapter_registry_contract.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
