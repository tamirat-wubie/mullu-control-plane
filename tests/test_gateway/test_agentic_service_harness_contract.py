"""Tests for the Agentic Service Harness planning contract validator.

Purpose: prove the first harness contract remains schema-bound, approval-gated,
and free of UI, mutation endpoint, external adapter, secret, or high-risk
authority overclaims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_contract and
schemas/agentic_service_harness.schema.json.
Invariants:
  - Valid default examples pass as a complete scenario set.
  - Denial flags cannot be raised.
  - Branch-write and open-PR examples remain pending approval.
  - Blocked high-risk actions remain complete and blocked.
  - Secret-like payloads and non-finite JSON constants fail closed.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_contract import (  # noqa: E402
    BLOCKED_HIGH_RISK_ACTIONS,
    DEFAULT_EXAMPLES,
    EXPECTED_NON_GOALS,
    EXPECTED_SCENARIOS,
    main,
    validate_agentic_service_harness_contract,
    write_agentic_service_harness_contract_validation,
)


def test_agentic_service_harness_contract_accepts_default_examples() -> None:
    validation = validate_agentic_service_harness_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.scenario_count == len(EXPECTED_SCENARIOS)
    assert validation.blocked_high_risk_action_count == len(BLOCKED_HIGH_RISK_ACTIONS)
    assert validation.non_goal_count == len(EXPECTED_NON_GOALS)
    assert validation.schema_path == "schemas/agentic_service_harness.schema.json"
    assert all(path.startswith("examples/") for path in validation.example_paths)


def test_agentic_service_harness_contract_rejects_mutation_denial_flag(
    tmp_path: Path,
) -> None:
    payload = _default_payload("agentic_service_harness.read_only.json")
    payload["mutation_endpoints_admitted"] = True
    example_paths = _replace_default_example(
        tmp_path,
        "agentic_service_harness.read_only.json",
        payload,
    )

    validation = validate_agentic_service_harness_contract(example_paths=example_paths)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert validation.scenario_count == len(EXPECTED_SCENARIOS)
    assert "mutation_endpoints_admitted" in serialized_errors


def test_agentic_service_harness_contract_rejects_branch_write_without_pending_gate(
    tmp_path: Path,
) -> None:
    payload = _default_payload("agentic_service_harness.branch_write_awaiting_approval.json")
    payload["approval_gates"][0]["status"] = "approved"
    payload["approval_gates"][0]["approval_required"] = False
    example_paths = _replace_default_example(
        tmp_path,
        "agentic_service_harness.branch_write_awaiting_approval.json",
        payload,
    )

    validation = validate_agentic_service_harness_contract(example_paths=example_paths)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "write_to_branch gate 0 must stay pending" in serialized_errors
    assert "write_to_branch gate 0 must require approval" in serialized_errors


def test_agentic_service_harness_contract_rejects_open_pr_external_effect_gate(
    tmp_path: Path,
) -> None:
    payload = _default_payload("agentic_service_harness.open_pr_awaiting_approval.json")
    payload["approval_gates"][0]["permits_external_effect"] = True
    example_paths = _replace_default_example(
        tmp_path,
        "agentic_service_harness.open_pr_awaiting_approval.json",
        payload,
    )

    validation = validate_agentic_service_harness_contract(example_paths=example_paths)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "open_pr gate 0 must not permit external effect" in serialized_errors
    assert validation.scenario_count == len(EXPECTED_SCENARIOS)


def test_agentic_service_harness_contract_rejects_approval_request_binding_gap(
    tmp_path: Path,
) -> None:
    payload = _default_payload("agentic_service_harness.open_pr_awaiting_approval.json")
    gate = payload["approval_gates"][0]
    gate["approval_request_ref"] = ""
    gate["requested_evidence_ref"] = "approval://missing"
    gate["response_record_collected"] = True
    gate["authority_granted"] = True
    example_paths = _replace_default_example(
        tmp_path,
        "agentic_service_harness.open_pr_awaiting_approval.json",
        payload,
    )

    validation = validate_agentic_service_harness_contract(example_paths=example_paths)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_request_ref must be a non-empty ref" in serialized_errors
    assert "requested_evidence_ref must appear in evidence_refs" in serialized_errors
    assert "response_record_collected must remain false" in serialized_errors
    assert "authority_granted must remain false" in serialized_errors


def test_agentic_service_harness_contract_rejects_repository_authority_gap(
    tmp_path: Path,
) -> None:
    payload = _default_payload("agentic_service_harness.read_only.json")
    repository = payload["repository_connections"][0]
    repository["write_authority_enabled"] = True
    repository["permission_scopes"].append("contents_write")
    repository["revocation_evidence_ref"] = ""
    example_paths = _replace_default_example(
        tmp_path,
        "agentic_service_harness.read_only.json",
        payload,
    )

    validation = validate_agentic_service_harness_contract(example_paths=example_paths)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "write_authority_enabled must remain false" in serialized_errors
    assert "permission_scopes must not include write scopes" in serialized_errors
    assert "revocation_evidence_ref must be a non-empty ref" in serialized_errors


def test_agentic_service_harness_contract_rejects_incomplete_blocked_actions(
    tmp_path: Path,
) -> None:
    payload = _default_payload("agentic_service_harness.blocked_high_risk.json")
    payload["agent_runs"][0]["blocked_actions"].remove("deploy")
    example_paths = _replace_default_example(
        tmp_path,
        "agentic_service_harness.blocked_high_risk.json",
        payload,
    )

    validation = validate_agentic_service_harness_contract(example_paths=example_paths)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocked_high_risk agent_run.blocked_actions missing" in serialized_errors
    assert "deploy" in serialized_errors


def test_agentic_service_harness_contract_rejects_secret_like_payload(
    tmp_path: Path,
) -> None:
    payload = _default_payload("agentic_service_harness.read_only.json")
    payload["users"][0]["metadata"]["serialized_secret_value"] = "ghp_examplecredential"
    payload["users"][0]["metadata"]["contains_secret_values"] = True
    example_paths = _replace_default_example(
        tmp_path,
        "agentic_service_harness.read_only.json",
        payload,
    )

    validation = validate_agentic_service_harness_contract(example_paths=example_paths)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "contains_secret_values" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_agentic_service_harness_contract_bounds_nonfinite_json_detail(
    tmp_path: Path,
) -> None:
    malformed_path = tmp_path / "agentic_service_harness.nonfinite.json"
    malformed_path.write_text(
        '{"contract_id": "agentic-service-harness-test", "score": Infinity}',
        encoding="utf-8",
    )

    validation = validate_agentic_service_harness_contract(example_paths=(malformed_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "JSON parse failed" in serialized_errors
    assert "Infinity" not in serialized_errors


def test_agentic_service_harness_contract_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "agentic_service_harness_validation.json"
    validation = validate_agentic_service_harness_contract()

    written = write_agentic_service_harness_contract_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["scenario_count"] == len(EXPECTED_SCENARIOS)


def _default_payload(filename: str) -> dict[str, object]:
    path = next(path for path in DEFAULT_EXAMPLES if path.name == filename)
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))


def _replace_default_example(
    tmp_path: Path,
    filename: str,
    payload: dict[str, object],
) -> tuple[Path, ...]:
    replacement_path = tmp_path / filename
    replacement_path.write_text(json.dumps(payload), encoding="utf-8")
    return tuple(
        replacement_path if path.name == filename else path
        for path in DEFAULT_EXAMPLES
    )
