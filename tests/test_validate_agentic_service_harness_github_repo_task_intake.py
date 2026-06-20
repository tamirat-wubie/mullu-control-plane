"""Tests for the Agentic Service Harness GitHub repo task intake validator.

Purpose: prove the GitHub repo task intake contract remains read-only,
contract-only, redacted, and non-terminal before any execution, repository
write, pull-request creation, receipt append, or mutation route is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_repo_task_intake.
Invariants:
  - Valid default examples pass schema and semantic validation.
  - Adapter execution, branch writes, PR creation, mutation route strings,
    missing denial classes, and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_github_repo_task_intake import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_FORBIDDEN_ACTION_CLASSES,
    main,
    validate_agentic_service_harness_github_repo_task_intake,
    write_github_repo_task_intake_validation,
)


def test_github_repo_task_intake_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_github_repo_task_intake()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_service_ok is True
    assert validation.forbidden_action_class_count == len(EXPECTED_FORBIDDEN_ACTION_CLASSES)
    assert validation.schema_path == "schemas/agentic_service_harness_github_repo_task_intake.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_github_repo_task_intake.foundation.json",
    )
    payload = _default_payload()
    assert payload["task_scope_intake"]["allowed_action_classes"] == ["read_only"]
    assert set(payload["task_scope_intake"]["forbidden_action_classes"]) == (
        EXPECTED_FORBIDDEN_ACTION_CLASSES
    )
    assert payload["intake_decision"]["execution_admitted"] is False
    assert payload["intake_decision"]["terminal_closure_allowed"] is False


def test_github_repo_task_intake_rejects_adapter_execution(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["adapter_executed"] = True
    payload["task_scope_intake"]["executes_adapter"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "adapter_executed" in serialized_errors
    assert "executes_adapter" in serialized_errors
    assert "must be false" in serialized_errors


def test_github_repo_task_intake_rejects_branch_and_pr_effects(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["repository_connection_check"]["creates_branch"] = True
    payload["task_scope_intake"]["opens_pull_request"] = True
    payload["authority_denials"]["branch_write_enabled"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "creates_branch" in serialized_errors
    assert "opens_pull_request" in serialized_errors
    assert "branch_write_enabled" in serialized_errors


def test_github_repo_task_intake_rejects_missing_forbidden_action_class(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["task_scope_intake"]["forbidden_action_classes"] = [
        action
        for action in payload["task_scope_intake"]["forbidden_action_classes"]
        if action != "terminal_closure"
    ]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden_action_classes missing" in serialized_errors
    assert "terminal_closure" in serialized_errors


def test_github_repo_task_intake_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/v1/harness/github/tasks"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_github_repo_task_intake_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["repository_connection_check"]["serialized_token_value"] = (
        "github_pat_forbiddencredential"
    )
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_github_repo_task_intake(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_repo_task_intake_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-repo-task-intake-validation.json"
    validation = validate_agentic_service_harness_github_repo_task_intake()

    written = write_github_repo_task_intake_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["forbidden_action_class_count"] == len(EXPECTED_FORBIDDEN_ACTION_CLASSES)


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_github_repo_task_intake.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
