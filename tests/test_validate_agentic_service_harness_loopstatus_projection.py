"""Tests for Agentic Service Harness LoopStatus projection.

Purpose: prove LoopStatus projection remains read-only, blocked, non-terminal,
and tied to the holistic loop read model before task creation admission.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_loopstatus_projection.
Invariants:
  - Valid foundation examples pass schema and semantic validation.
  - Reference drift, transition authority, missing blockers, mutation routes,
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

from scripts.validate_agentic_service_harness_loopstatus_projection import (  # noqa: E402
    DEFAULT_EXAMPLES,
    main,
    validate_agentic_service_harness_loopstatus_projection,
    write_loopstatus_projection_validation,
)


def test_loopstatus_projection_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_loopstatus_projection()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.schema_path == "schemas/agentic_service_harness_loopstatus_projection.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_loopstatus_projection.foundation.json",
    )
    payload = _default_payload()
    assert payload["loop_status_projection"]["projected_outcome"] == "AwaitingEvidence"
    assert payload["loop_status_projection"]["status_transition"] is False
    assert payload["readiness_gates"]["task_creation_route_admitted"] is False


def test_loopstatus_projection_rejects_reference_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["loop_status_projection"]["project_id"] = "project-drift"
    payload["loop_status_projection"]["loop_status_ref"] = "loopstatus://drift"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_loopstatus_projection(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "scope.project_id must match" in serialized_errors
    assert "scope.loop_status_ref must match" in serialized_errors
    assert validation.example_count == 1


def test_loopstatus_projection_rejects_transition_authority(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["status_transition_admitted"] = True
    payload["loop_status_projection"]["status_transition"] = True
    payload["authority_denials"]["status_transition"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_loopstatus_projection(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "scope.status_transition_admitted" in serialized_errors
    assert "loop_status_projection.status_transition" in serialized_errors
    assert "authority_denials.status_transition" in serialized_errors


def test_loopstatus_projection_rejects_missing_blockers(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["loop_status_projection"]["blocker_refs"] = []
    payload["readiness_gates"]["blocked_reason_refs"] = []
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_loopstatus_projection(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing loop blocker refs" in serialized_errors
    assert "missing readiness blocked_reason_refs" in serialized_errors
    assert "blocked://task-creation-route/not-admitted" in serialized_errors


def test_loopstatus_projection_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/v1/harness/tasks"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_loopstatus_projection(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_loopstatus_projection_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["access_token_value"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_loopstatus_projection(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_loopstatus_projection_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "loopstatus-projection-validation.json"
    validation = validate_agentic_service_harness_loopstatus_projection()

    written = write_loopstatus_projection_validation(validation, output_path)
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
    example_path = tmp_path / "agentic_service_harness_loopstatus_projection.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
