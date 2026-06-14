"""Tests for Agentic Service Harness live task/run producer evidence validation.

Purpose: prove the live producer evidence contract stays planning-only,
evidence-bound, and free of UI, mutation, external adapter, branch, pull
request, deployment, DNS, secret, or destructive authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_task_run_producer_evidence.
Invariants:
  - The default evidence document validates.
  - Missing evidence surfaces fail closed.
  - Mutation route strings and implementation claims fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_live_task_run_producer_evidence import (  # noqa: E402
    DEFAULT_EVIDENCE_DOC,
    DEFAULT_FIXTURE,
    REQUIRED_EVIDENCE_SURFACES,
    REQUIRED_FALSE_FLAGS,
    REQUIRED_SECTIONS,
    main,
    validate_live_task_run_producer_evidence,
)


def test_live_task_run_producer_evidence_accepts_default_artifact() -> None:
    validation = validate_live_task_run_producer_evidence()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.evidence_doc_path == "MULLUSI_AGENTIC_SERVICE_HARNESS_LIVE_TASK_RUN_PRODUCER_EVIDENCE.md"
    assert validation.fixture_path == "examples/agentic_service_harness_live_task_run_producer_evidence.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_task_run_producer_evidence.schema.json"
    assert validation.required_section_count == len(REQUIRED_SECTIONS)
    assert validation.required_evidence_surface_count == len(REQUIRED_EVIDENCE_SURFACES)
    assert validation.required_false_flag_count == len(REQUIRED_FALSE_FLAGS)
    assert validation.required_validator_count >= 5


def test_live_task_run_producer_evidence_rejects_missing_surface(tmp_path: Path) -> None:
    evidence_text = DEFAULT_EVIDENCE_DOC.read_text(encoding="utf-8")
    evidence_path = tmp_path / "producer-evidence.md"
    evidence_path.write_text(
        evidence_text.replace("RollbackEvidence", "RecoveryEvidence"),
        encoding="utf-8",
    )

    validation = validate_live_task_run_producer_evidence(evidence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing evidence_surface: RollbackEvidence" in serialized_errors
    assert validation.evidence_doc_path == "producer-evidence.md"


def test_live_task_run_producer_evidence_rejects_mutation_route(tmp_path: Path) -> None:
    evidence_path = tmp_path / "producer-evidence.md"
    evidence_path.write_text(
        DEFAULT_EVIDENCE_DOC.read_text(encoding="utf-8")
        + "\nForbidden route: POST /api/v1/harness/tasks\n",
        encoding="utf-8",
    )

    validation = validate_live_task_run_producer_evidence(evidence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden mutation_route" in serialized_errors
    assert "missing section" not in serialized_errors


def test_live_task_run_producer_evidence_rejects_implementation_claim(tmp_path: Path) -> None:
    evidence_path = tmp_path / "producer-evidence.md"
    evidence_path.write_text(
        DEFAULT_EVIDENCE_DOC.read_text(encoding="utf-8")
        + "\nlive_producer_implemented=true\n",
        encoding="utf-8",
    )

    validation = validate_live_task_run_producer_evidence(evidence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden live_producer_implementation_claim" in serialized_errors
    assert validation.required_false_flag_count == len(REQUIRED_FALSE_FLAGS)


def test_live_task_run_producer_evidence_rejects_fixture_authority_enablement(tmp_path: Path) -> None:
    fixture = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    fixture["authority_denials"]["branch_write_enabled"] = True
    fixture_path = tmp_path / "producer-evidence.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    validation = validate_live_task_run_producer_evidence(fixture_path=fixture_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "branch_write_enabled" in serialized_errors
    assert validation.fixture_path == "producer-evidence.json"


def test_live_task_run_producer_evidence_rejects_fixture_scope_mismatch(tmp_path: Path) -> None:
    fixture = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    fixture["task_intake_evidence"]["tenant_id"] = "tenant-other"
    fixture_path = tmp_path / "producer-evidence.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    validation = validate_live_task_run_producer_evidence(fixture_path=fixture_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "task tenant_id must match scope" in serialized_errors
    assert validation.required_evidence_surface_count == len(REQUIRED_EVIDENCE_SURFACES)


def test_live_task_run_producer_evidence_rejects_fixture_secret_value(tmp_path: Path) -> None:
    fixture = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    fixture["receipt_evidence"]["command_refs"].append("command://ghp_forbiddencredential")
    fixture_path = tmp_path / "producer-evidence.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    validation = validate_live_task_run_producer_evidence(fixture_path=fixture_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors


def test_live_task_run_producer_evidence_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["required_evidence_surface_count"] == len(REQUIRED_EVIDENCE_SURFACES)
