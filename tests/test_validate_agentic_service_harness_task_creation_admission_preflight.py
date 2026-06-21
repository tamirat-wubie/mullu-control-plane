"""Test task creation admission preflight validation.

Purpose: verify the task creation admission gate stays blocked until authority,
approval, UAO, rollback, and receipt evidence are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_task_creation_admission_preflight.
Invariants: no task creation route, task record write, adapter execution,
receipt append, secret serialization, or terminal closure is admitted.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_agentic_service_harness_task_creation_admission_preflight as validator


def test_task_creation_admission_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_task_creation_admission_preflight()

    assert validation.ok is True
    assert validation.example_count == 1
    assert validation.source_validators_ok is True
    assert validation.errors == ()


def test_task_creation_admission_preflight_rejects_route_and_write_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["scope"]["task_creation_route_admitted"] = True
    payload["admission_decision"]["task_record_write_admitted"] = True
    payload["authority_denials"]["task_creation_route_enabled"] = True
    example_path = _write_payload(tmp_path, payload)

    validation = validator.validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "scope.task_creation_route_admitted must be false" in serialized_errors
    assert "admission_decision.task_record_write_admitted must be false" in serialized_errors
    assert "authority_denials.task_creation_route_enabled must be false" in serialized_errors


def test_task_creation_admission_preflight_rejects_missing_blockers(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["admission_decision"]["blocked_reason_refs"] = [
        "blocked://task-creation-route/not-admitted"
    ]
    example_path = _write_payload(tmp_path, payload)

    validation = validator.validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocked_reason_refs missing" in serialized_errors
    assert "blocked://terminal-closure/not-authorized" in serialized_errors


def test_task_creation_admission_preflight_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["admission_request"]["requested_route_ref"] = "POST /api/v1/harness/tasks"
    example_path = _write_payload(tmp_path, payload)

    validation = validator.validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "requested_route_ref must remain not-admitted" in serialized_errors
    assert "mutation route string" in serialized_errors


def test_task_creation_admission_preflight_rejects_secret_like_surface(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["admission_request"]["api_key"] = "sk-test-not-allowed"
    example_path = _write_payload(tmp_path, payload)

    validation = validator.validate_agentic_service_harness_task_creation_admission_preflight(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_task_creation_admission_preflight_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["example_count"] == 1
    assert payload["source_validators_ok"] is True


def _load_fixture() -> dict[str, object]:
    fixture_path = REPO_ROOT / "examples" / "agentic_service_harness_task_creation_admission_preflight.foundation.json"
    return deepcopy(json.loads(fixture_path.read_text(encoding="utf-8")))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "task_creation_admission_preflight.foundation.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return example_path
