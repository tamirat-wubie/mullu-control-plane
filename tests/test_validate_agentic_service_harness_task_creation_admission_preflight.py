"""Tests for Agentic Service Harness task creation admission preflight.

Purpose: prove task creation admission stays read-only, blocked, non-terminal,
and evidence-bound before any user-facing task route exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies:
scripts.validate_agentic_service_harness_task_creation_admission_preflight.
Invariants:
  - Valid foundation examples pass schema and semantic validation.
  - Reference drift, route authority, missing evidence, mutation routes, and
    secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_task_creation_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES,
    main,
    validate_agentic_service_harness_task_creation_admission_preflight,
    write_task_creation_admission_preflight_validation,
)


def test_task_creation_admission_preflight_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_task_creation_admission_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.schema_path == "schemas/agentic_service_harness_task_creation_admission_preflight.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_task_creation_admission_preflight.foundation.json",
    )
    payload = _default_payload()
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["admission_decision"]["proof_state"] == "Unknown"
    assert payload["admission_decision"]["task_creation_route_admitted"] is False


def test_task_creation_admission_preflight_rejects_reference_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["admission_request"]["project_id"] = "project-drift"
    payload["admission_request"]["repository_connection_id"] = "repo-drift"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "scope.project_id must match" in serialized_errors
    assert "scope.repository_connection_id must match" in serialized_errors
    assert validation.example_count == 1


def test_task_creation_admission_preflight_rejects_route_enablement(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["task_creation_route_admitted"] = True
    payload["admission_decision"]["task_creation_route_admitted"] = True
    payload["authority_denials"]["task_creation_route_enabled"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "scope.task_creation_route_admitted" in serialized_errors
    assert "admission_decision.task_creation_route_admitted" in serialized_errors
    assert "authority_denials.task_creation_route_enabled" in serialized_errors


def test_task_creation_admission_preflight_rejects_missing_evidence_and_blockers(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["prerequisite_evidence"]["required_evidence_refs"] = []
    payload["prerequisite_evidence"]["missing_evidence_refs"] = []
    payload["admission_decision"]["blocked_reason_refs"] = []
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing required_evidence_refs" in serialized_errors
    assert "missing missing_evidence_refs" in serialized_errors
    assert "missing blocked_reason_refs" in serialized_errors


def test_task_creation_admission_preflight_rejects_mutation_route_string(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/v1/harness/tasks"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_task_creation_admission_preflight_rejects_secret_like_payload(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["scope"]["access_token_value"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_task_creation_admission_preflight_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "task-creation-admission-preflight-validation.json"
    validation = validate_agentic_service_harness_task_creation_admission_preflight()

    written = write_task_creation_admission_preflight_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["example_count"] == 1


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_task_creation_admission_preflight.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
