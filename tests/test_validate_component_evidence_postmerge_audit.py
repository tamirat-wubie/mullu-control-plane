"""Tests for Component Harness evidence post-merge audit validation.

Purpose: prove post-merge audits remain source-bound, read-only, and
non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_evidence_postmerge_audit and
foundation Component Harness fixtures.
Invariants: audits cannot accept evidence, grant authority, approve promotion,
execute, mutate, or claim terminal closure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.component_evidence_postmerge_audit import (
    ComponentEvidencePostmergeAuditError,
    build_component_evidence_postmerge_audit,
)
from mcoi_runtime.app.component_evidence_request_queue import build_component_evidence_request_queue
from mcoi_runtime.app.component_evidence_submission_intake import build_component_evidence_submission_intake
from scripts.validate_component_evidence_postmerge_audit import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_evidence_postmerge_audit,
    write_component_evidence_postmerge_audit_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_evidence_postmerge_audit.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _findings(payload: dict[str, object]) -> list[dict[str, object]]:
    findings = payload["audit_findings"]
    assert isinstance(findings, list)
    return findings


def test_component_evidence_postmerge_audit_schema_valid_and_write(tmp_path: Path) -> None:
    validation = validate_component_evidence_postmerge_audit()
    output_path = tmp_path / "component-evidence-postmerge-audit-validation.json"

    written_path = write_component_evidence_postmerge_audit_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.request_slot_count == 7
    assert validation.audit_finding_count == 5
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_evidence_postmerge_audit_validation.json"


def test_component_evidence_postmerge_audit_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_evidence_postmerge_audit()

    assert example == projection
    assert example["audit_is_not_evidence_acceptance"] is True
    assert example["evidence_accepted"] is False
    assert example["authority_granted"] is False
    assert example["terminal_closure_allowed"] is False
    assert example["summary"]["postmerge_blocker_count"] == 4


def test_component_evidence_postmerge_audit_rejects_acceptance_and_closure_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["evidence_accepted"] = True
    payload["terminal_closure_allowed"] = True
    payload["summary"]["accepted_evidence_count"] = 1
    finding = _findings(payload)[0]
    finding["proof_state"] = "Unknown"
    finding["required_validator_refs"] = ["component_evidence_request_queue_validator"]

    validation = validate_component_evidence_postmerge_audit(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_accepted must be false" in serialized_errors
    assert "terminal_closure_allowed must be false" in serialized_errors
    assert "summary.accepted_evidence_count must be 0" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "must require component_evidence_submission_intake_validator" in serialized_errors


def test_component_evidence_postmerge_audit_requires_blockers_and_validators(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["postmerge_blockers"] = ["submitted_evidence_not_verified"]
    payload["validators"] = []
    finding = _findings(payload)[0]
    finding["evidence_refs"] = []

    validation = validate_component_evidence_postmerge_audit(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "postmerge_blockers must include evidence_acceptance_not_performed" in serialized_errors
    assert "postmerge_blockers must include terminal_closure_denied" in serialized_errors
    assert "missing validator component_evidence_postmerge_audit_validator" in serialized_errors
    assert "must carry evidence refs" in serialized_errors


def test_component_evidence_postmerge_audit_runtime_rejects_request_id_mismatch() -> None:
    queue = build_component_evidence_request_queue()
    intake = build_component_evidence_submission_intake(evidence_request_queue=queue)
    intake["intake_slots"][0]["request_id"] = "component_evidence_request_queue.mismatched.v1"

    with pytest.raises(ComponentEvidencePostmergeAuditError, match="queue and intake request IDs must match"):
        build_component_evidence_postmerge_audit(
            evidence_request_queue=queue,
            evidence_submission_intake=intake,
        )

    assert len(queue["request_slots"]) == 7
    assert len(intake["intake_slots"]) == 7
    assert queue["terminal_closure_allowed"] is False


def test_component_evidence_postmerge_audit_runtime_rejects_unsafe_sources() -> None:
    queue = build_component_evidence_request_queue()
    intake = build_component_evidence_submission_intake(evidence_request_queue=queue)
    queue["can_execute"] = True

    with pytest.raises(ComponentEvidencePostmergeAuditError, match="queue can_execute must be false"):
        build_component_evidence_postmerge_audit(
            evidence_request_queue=queue,
            evidence_submission_intake=intake,
        )

    queue["can_execute"] = False
    intake["authority_granted"] = True
    with pytest.raises(ComponentEvidencePostmergeAuditError, match="intake authority_granted must be false"):
        build_component_evidence_postmerge_audit(
            evidence_request_queue=queue,
            evidence_submission_intake=intake,
        )

    assert queue["can_execute"] is False
    assert intake["terminal_closure_allowed"] is False
