"""Tests for Agentic Service Harness read-only repository task intake.

Purpose: prove repository task intake remains read-only, identity-bound,
contract-only, redacted, and non-terminal before any execution authority is
admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_read_only_repo_task_intake.
Invariants:
  - Valid foundation examples pass schema and semantic validation.
  - Repository/task identity drift, execution requests, mutation route strings,
    and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_read_only_repo_task_intake import (  # noqa: E402
    DEFAULT_EXAMPLES,
    main,
    validate_agentic_service_harness_read_only_repo_task_intake,
    write_read_only_repo_task_intake_validation,
)


def test_read_only_repo_task_intake_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_read_only_repo_task_intake()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.schema_path == "schemas/agentic_service_harness_read_only_repo_task_intake.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_read_only_repo_task_intake.foundation.json",
    )
    payload = _default_payload()
    assert payload["task_intake"]["allowed_action_classes"] == ["read_only"]
    assert payload["task_intake"]["requested_commands"] == []
    assert payload["preflight_gates"]["execution_authority_granted"] is False


def test_read_only_repo_task_intake_rejects_identity_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["repository_connection_binding"]["repository_connection_id"] = "repo-conn-other"
    payload["task_intake"]["agent_task_id"] = "agent-task-other"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_only_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "repository_connection_id must match" in serialized_errors
    assert "agent_task_id must match" in serialized_errors
    assert validation.example_count == 1


def test_read_only_repo_task_intake_rejects_execution_request(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["task_intake"]["code_execution_requested"] = True
    payload["task_intake"]["requested_commands"] = ["pytest tests/test_example.py"]
    payload["preflight_gates"]["execution_authority_granted"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_only_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "code_execution_requested" in serialized_errors
    assert "requested_commands" in serialized_errors
    assert "execution_authority_granted" in serialized_errors


def test_read_only_repo_task_intake_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/v1/harness/repo-task-intake"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_only_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_read_only_repo_task_intake_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["repository_connection_binding"]["access_token_value"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_read_only_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_read_only_repo_task_intake_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "read-only-repo-task-intake-validation.json"
    validation = validate_agentic_service_harness_read_only_repo_task_intake()

    written = write_read_only_repo_task_intake_validation(validation, output_path)
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
    example_path = tmp_path / "agentic_service_harness_read_only_repo_task_intake.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
