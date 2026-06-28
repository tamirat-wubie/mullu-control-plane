"""Tests for sandbox-to-PR preparation packet validation.

Purpose: prove the local Developer Workflow v1 PR packet is schema-valid,
operator-safe, and semantically consistent.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_sandbox_to_pr_preparation_packet and the packet
schema/example pair.
Invariants: external effects remain blocked, evidence remains source-bound,
and blockers match the observed preparation state.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_sandbox_to_pr_preparation_packet import (
    DEFAULT_OUTPUT,
    DEFAULT_PACKET,
    validate_sandbox_to_pr_preparation_packet,
    write_sandbox_to_pr_preparation_packet_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    packet_path = tmp_path / "sandbox_to_pr_preparation_packet.json"
    packet_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path


def test_sandbox_to_pr_packet_validates_and_writes_report(tmp_path: Path) -> None:
    validation = validate_sandbox_to_pr_preparation_packet()
    output_path = tmp_path / "sandbox-to-pr-packet-validation.json"

    written_path = write_sandbox_to_pr_preparation_packet_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.packet_status == "awaiting_receipts"
    assert validation.blocker == "sandbox_receipts_incomplete"
    assert validation.evidence_count == 4
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "sandbox_to_pr_preparation_packet_validation.json"
    payload = _default_payload()
    assert [item["evidence_id"] for item in payload["next_evidence"]] == [
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    ]
    assert [item["action"] for item in payload["next_evidence"]] == [
        "attach before state, after state, diff, command, and rollback receipt",
        "attach bounded local test command receipt and observed result",
        "attach reviewed diff hash and reviewer evidence reference",
        "attach final local receipt summary and no-external-effect witness",
    ]
    assert payload["receipt_bundle_ref"]["validator"] == (
        "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py"
    )
    assert payload["receipt_bundle_ref"]["builder"] == (
        "python scripts/build_developer_workflow_sandbox_receipt_bundle.py"
    )


def test_sandbox_to_pr_packet_rejects_external_effect_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["external_effects_allowed"] = True
    payload["execution_boundary"] = "production"

    validation = validate_sandbox_to_pr_preparation_packet(packet_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_effects_allowed must remain false" in serialized_errors
    assert "execution_boundary must be local_lab_only" in serialized_errors


def test_sandbox_to_pr_packet_rejects_evidence_status_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    evidence = payload["required_evidence"]
    assert isinstance(evidence, list)
    evidence[1]["status"] = "complete"  # type: ignore[index]

    validation = validate_sandbox_to_pr_preparation_packet(packet_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "sandbox_receipts evidence status must match receipts.ready" in serialized_errors


def test_sandbox_to_pr_packet_rejects_next_evidence_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    next_evidence = payload["next_evidence"]
    assert isinstance(next_evidence, list)
    next_evidence.reverse()
    next_evidence[0]["status"] = "complete"  # type: ignore[index]
    next_evidence[0]["action"] = "skip the sandbox receipt"  # type: ignore[index]

    validation = validate_sandbox_to_pr_preparation_packet(packet_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "next_evidence must list canonical receipt evidence in order" in serialized_errors
    assert "status must be pending" in serialized_errors
    assert "action must be canonical" in serialized_errors


def test_sandbox_to_pr_packet_rejects_friction_control_evidence_drift(tmp_path: Path) -> None:
    friction_control = json.loads((Path("examples") / "capability_friction_control.foundation.json").read_text(encoding="utf-8"))
    sandbox_to_pr = friction_control["sandbox_to_pr_now"]
    assert isinstance(sandbox_to_pr, dict)
    next_evidence = sandbox_to_pr["next_evidence"]
    assert isinstance(next_evidence, list)
    next_evidence[0]["label"] = "Changed receipt label"  # type: ignore[index]
    next_evidence[1]["action"] = "skip local test evidence"  # type: ignore[index]
    friction_control_path = tmp_path / "capability_friction_control.json"
    friction_control_path.write_text(json.dumps(friction_control, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_sandbox_to_pr_preparation_packet(friction_control_path=friction_control_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "next_evidence drifts from" in serialized_errors


def test_sandbox_to_pr_packet_rejects_blocker_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["blocker"] = "none"

    validation = validate_sandbox_to_pr_preparation_packet(packet_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocker must be 'sandbox_receipts_incomplete'" in serialized_errors
    assert "status and blocker are inconsistent" in serialized_errors


def test_sandbox_to_pr_packet_rejects_unapproved_pr_candidate_ready(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["status"] = "pr_candidate_ready"
    payload["blocker"] = "none"
    pr_candidate = payload["pr_candidate"]
    assert isinstance(pr_candidate, dict)
    pr_candidate["prepared"] = True
    pr_candidate["status"] = "complete"
    evidence = payload["required_evidence"]
    assert isinstance(evidence, list)
    evidence[3]["status"] = "complete"  # type: ignore[index]

    validation = validate_sandbox_to_pr_preparation_packet(packet_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocker must be 'sandbox_receipts_incomplete'" in serialized_errors


def test_sandbox_to_pr_packet_rejects_receipt_bundle_reference_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    receipt_bundle_ref = payload["receipt_bundle_ref"]
    assert isinstance(receipt_bundle_ref, dict)
    receipt_bundle_ref["validator"] = "python scripts/other_validator.py"
    receipt_bundle_ref["builder"] = "python scripts/other_builder.py"

    validation = validate_sandbox_to_pr_preparation_packet(packet_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipt_bundle_ref.validator must point to sandbox receipt bundle validator" in serialized_errors
    assert "receipt_bundle_ref.builder must point to sandbox receipt bundle builder" in serialized_errors


def test_sandbox_to_pr_packet_rejects_receipt_bundle_count_drift(tmp_path: Path) -> None:
    receipt_bundle = json.loads(
        (Path("examples") / "developer_workflow_sandbox_receipt_bundle.foundation.json").read_text(encoding="utf-8")
    )
    receipt_bundle["completed_count"] = 1
    receipt_bundle_path = tmp_path / "developer_workflow_sandbox_receipt_bundle.json"
    receipt_bundle_path.write_text(json.dumps(receipt_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_sandbox_to_pr_preparation_packet(receipt_bundle_path=receipt_bundle_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipts.completed_count drifts from" in serialized_errors


def test_sandbox_to_pr_packet_rejects_receipt_bundle_signature_drift(tmp_path: Path) -> None:
    receipt_bundle = json.loads(
        (Path("examples") / "developer_workflow_sandbox_receipt_bundle.foundation.json").read_text(encoding="utf-8")
    )
    receipts = receipt_bundle["receipts"]
    assert isinstance(receipts, list)
    receipts[0]["label"] = "Changed receipt label"  # type: ignore[index]
    receipt_bundle_path = tmp_path / "developer_workflow_sandbox_receipt_bundle.json"
    receipt_bundle_path.write_text(json.dumps(receipt_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_sandbox_to_pr_preparation_packet(receipt_bundle_path=receipt_bundle_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "next_evidence drifts from" in serialized_errors
