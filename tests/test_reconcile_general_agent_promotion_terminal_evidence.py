"""Tests for terminal evidence reconciliation.

Purpose: prove terminal certificate candidates require live receipt evidence
before minting readiness can be true.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.reconcile_general_agent_promotion_terminal_evidence.
Invariants:
  - Missing evidence blocks terminal certificate minting readiness.
  - Receipt evidence is summarized by path, not by raw values.
  - Reconciliation never executes actions or mints certificates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.reconcile_general_agent_promotion_terminal_evidence as reconciliation_module  # noqa: E402
from scripts.reconcile_general_agent_promotion_terminal_evidence import (  # noqa: E402
    main,
    reconcile_general_agent_promotion_terminal_evidence,
    validate_general_agent_promotion_terminal_evidence_reconciliation,
    write_general_agent_promotion_terminal_evidence_reconciliation,
)


def test_terminal_evidence_reconciliation_accepts_matching_document_receipt(tmp_path: Path) -> None:
    candidate_path = _write_candidates(tmp_path)
    receipt_path = _write_document_receipt(tmp_path, status="passed")

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(receipt_path,),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is True
    assert reconciliation.candidate_count == 1
    assert reconciliation.reconciled_candidate_count == 1
    assert reconciliation.blocked_candidate_count == 0
    assert reconciliation.missing_evidence_count == 0
    assert reconciliation.source_candidate_path == "general_agent_promotion_terminal_certificate_candidates.json"
    assert candidate.reconciliation_status == "reconciled"
    assert set(candidate.evidence_matched) == {"document_live_receipt.json", "production_parser_registry_receipt"}
    assert candidate.missing_evidence == ()
    assert candidate.receipt_refs == ("document_live_receipt.json",)
    assert reconciliation.metadata["reconciliation_is_not_execution"] is True
    assert reconciliation.metadata["terminal_certificates_minted"] is False
    assert tmp_path.name not in json.dumps(reconciliation.as_dict(), sort_keys=True)
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_accepts_capability_improvement_proof_receipt(tmp_path: Path) -> None:
    candidate_path = _write_capability_improvement_candidates(tmp_path)
    receipt_path = _write_capability_improvement_proof_receipt(tmp_path)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(receipt_path,),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is True
    assert reconciliation.candidate_count == 1
    assert reconciliation.reconciled_candidate_count == 1
    assert reconciliation.blocked_candidate_count == 0
    assert reconciliation.missing_evidence_count == 0
    assert candidate.reconciliation_status == "reconciled"
    assert set(candidate.evidence_matched) == {
        "capability_registry:agentic_control.governance_gate.evaluate",
        "change_command_not_certified",
        "terminal_closure_missing",
    }
    assert candidate.missing_evidence == ()
    assert candidate.receipt_refs == ("capability_improvement_proof_receipt.json",)
    assert reconciliation.metadata["secret_values_serialized"] is False
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_accepts_ready_deployment_publication_packet(
    tmp_path: Path,
) -> None:
    candidate_path = _write_deployment_publication_candidates(tmp_path)
    receipt_path = _write_deployment_publication_evidence_packet(tmp_path, ready=True)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(receipt_path,),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is True
    assert reconciliation.reconciled_candidate_count == 1
    assert reconciliation.blocked_candidate_count == 0
    assert reconciliation.missing_evidence_count == 0
    assert set(candidate.evidence_matched) == {
        "upstream_api_production_readiness_report",
        "deployment_upstream_blocker_receipt",
        "deployment_upstream_blocker_validation",
        "upstream_recovery_completion_witness",
        "api_runtime_host_readiness",
        "dns_publication_authority",
    }
    assert candidate.missing_evidence == ()
    assert candidate.receipt_refs == ("deployment_publication_evidence_packet.json",)
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_rejects_blocked_deployment_publication_packet(
    tmp_path: Path,
) -> None:
    candidate_path = _write_deployment_publication_candidates(tmp_path)
    receipt_path = _write_deployment_publication_evidence_packet(tmp_path, ready=False)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(receipt_path,),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is False
    assert reconciliation.reconciled_candidate_count == 0
    assert reconciliation.blocked_candidate_count == 1
    assert reconciliation.missing_evidence_count == 6
    assert candidate.reconciliation_status == "blocked_missing_evidence"
    assert "deployment_upstream_blocker_receipt" in candidate.missing_evidence
    assert "dns_publication_authority" in candidate.missing_evidence
    assert candidate.receipt_refs == ()
    assert "missing_evidence:deployment_upstream_blocker_receipt" in reconciliation.blocked_reasons
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_accepts_individual_dns_publication_receipts(
    tmp_path: Path,
) -> None:
    candidate_path = _write_deployment_dns_candidates(tmp_path)
    target_receipt = _write_gateway_dns_target_binding_receipt(tmp_path, ready=True)
    target_validation = _write_gateway_dns_target_binding_validation(tmp_path, ready=True, valid=True)
    resolution_receipt = _write_gateway_dns_resolution_receipt(tmp_path, resolved=True)
    resolution_validation = _write_gateway_dns_resolution_validation(tmp_path, valid=True)
    preflight_receipt = _write_deployment_witness_preflight(tmp_path, ready=True)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(
            target_receipt,
            target_validation,
            resolution_receipt,
            resolution_validation,
            preflight_receipt,
        ),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is True
    assert reconciliation.reconciled_candidate_count == 1
    assert reconciliation.blocked_candidate_count == 0
    assert reconciliation.missing_evidence_count == 0
    assert set(candidate.evidence_matched) == {
        "gateway_dns_target_binding_receipt",
        "gateway_dns_target_binding_validation",
        "dns_resolution_receipt",
        "dns_resolution_receipt_validation",
        "deployment_witness_preflight",
    }
    assert candidate.missing_evidence == ()
    assert set(candidate.receipt_refs) == {
        "gateway_dns_target_binding_receipt_validation.json",
        "gateway_dns_resolution_receipt_validation.json",
        "deployment_witness_preflight.json",
    }
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_rejects_unready_individual_dns_publication_receipts(
    tmp_path: Path,
) -> None:
    candidate_path = _write_deployment_dns_candidates(tmp_path)
    target_receipt = _write_gateway_dns_target_binding_receipt(tmp_path, ready=False)
    target_validation = _write_gateway_dns_target_binding_validation(tmp_path, ready=False, valid=True)
    resolution_receipt = _write_gateway_dns_resolution_receipt(tmp_path, resolved=False)
    resolution_validation = _write_gateway_dns_resolution_validation(tmp_path, valid=False)
    preflight_receipt = _write_deployment_witness_preflight(tmp_path, ready=False)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(
            target_receipt,
            target_validation,
            resolution_receipt,
            resolution_validation,
            preflight_receipt,
        ),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is False
    assert reconciliation.reconciled_candidate_count == 0
    assert reconciliation.blocked_candidate_count == 1
    assert reconciliation.missing_evidence_count == 5
    assert candidate.receipt_refs == ()
    assert "gateway_dns_target_binding_receipt" in candidate.missing_evidence
    assert "deployment_witness_preflight" in candidate.missing_evidence
    assert "missing_evidence:dns_resolution_receipt_validation" in reconciliation.blocked_reasons
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_rejects_unsafe_capability_proof_receipt(tmp_path: Path) -> None:
    candidate_path = _write_capability_improvement_candidates(tmp_path)
    receipt_path = _write_capability_improvement_proof_receipt(tmp_path, registry_mutated=True)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(receipt_path,),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is False
    assert reconciliation.reconciled_candidate_count == 0
    assert reconciliation.blocked_candidate_count == 1
    assert reconciliation.missing_evidence_count == 3
    assert candidate.reconciliation_status == "blocked_missing_evidence"
    assert "capability_registry:agentic_control.governance_gate.evaluate" in candidate.missing_evidence
    assert "change_command_not_certified" in candidate.missing_evidence
    assert "terminal_closure_missing" in candidate.missing_evidence
    assert candidate.receipt_refs == ()
    assert "missing_evidence:change_command_not_certified" in reconciliation.blocked_reasons
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_default_discovers_capability_proof_receipts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate_path = _write_capability_improvement_candidates(tmp_path)
    assurance_path = tmp_path / ".change_assurance"
    assurance_path.mkdir()
    _write_capability_improvement_proof_receipt(
        assurance_path,
        name="capability_improvement_proof_receipt_agentic_control_governance_gate_evaluate.json",
    )
    monkeypatch.setattr(reconciliation_module, "REPO_ROOT", tmp_path)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(candidate_path=candidate_path)
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is True
    assert reconciliation.reconciled_candidate_count == 1
    assert reconciliation.blocked_candidate_count == 0
    assert candidate.missing_evidence == ()
    assert candidate.receipt_refs == (
        ".change_assurance/capability_improvement_proof_receipt_agentic_control_governance_gate_evaluate.json",
    )
    assert "change_command_not_certified" in candidate.evidence_matched
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_blocks_missing_receipt(tmp_path: Path) -> None:
    candidate_path = _write_candidates(tmp_path)

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(tmp_path / "missing-document-live-receipt.json",),
    )
    candidate = reconciliation.candidates[0]

    assert reconciliation.ready_for_terminal_certificate_minting is False
    assert reconciliation.reconciled_candidate_count == 0
    assert reconciliation.blocked_candidate_count == 1
    assert reconciliation.missing_evidence_count == 2
    assert candidate.reconciliation_status == "blocked_missing_evidence"
    assert "document_live_receipt.json" in candidate.missing_evidence
    assert "production_parser_registry_receipt" in candidate.missing_evidence
    assert "missing_evidence:document_live_receipt.json" in reconciliation.blocked_reasons
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_invalid_candidates_fail_closed(tmp_path: Path) -> None:
    candidate_path = tmp_path / "invalid-candidates.json"
    candidate_path.write_text(json.dumps({"schema_version": 1, "candidates": []}), encoding="utf-8")

    reconciliation = reconcile_general_agent_promotion_terminal_evidence(candidate_path=candidate_path)

    assert reconciliation.ready_for_terminal_certificate_minting is False
    assert reconciliation.source_candidate_set_id == "invalid-terminal-candidate-set"
    assert reconciliation.candidate_count == 1
    assert reconciliation.blocked_candidate_count == 1
    assert reconciliation.candidates[0].reconciliation_status == "blocked_invalid_candidates"
    assert any(reason.startswith("terminal_certificate_candidates_invalid:") for reason in reconciliation.blocked_reasons)
    assert validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation) == ()


def test_terminal_evidence_reconciliation_writer_and_cli_emit_schema_valid_json(tmp_path: Path, capsys) -> None:
    candidate_path = _write_candidates(tmp_path)
    receipt_path = _write_document_receipt(tmp_path, status="passed")
    output_path = tmp_path / "general_agent_promotion_terminal_evidence_reconciliation.json"
    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=candidate_path,
        receipt_paths=(receipt_path,),
    )

    written = write_general_agent_promotion_terminal_evidence_reconciliation(reconciliation, output_path)
    exit_code = main(
        [
            "--candidates",
            str(candidate_path),
            "--receipt",
            str(receipt_path),
            "--output",
            str(output_path),
            "--json",
            "--strict",
            "--require-ready",
        ]
    )
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(capsys.readouterr().out)

    assert written == output_path
    assert exit_code == 0
    assert file_payload["schema_version"] == 1
    assert "schema_valid" not in file_payload
    assert stdout_payload["schema_valid"] is True
    assert stdout_payload["ready_for_terminal_certificate_minting"] is True
    assert stdout_payload["metadata"]["secret_values_serialized"] is False


def _write_candidates(tmp_path: Path) -> Path:
    candidate_path = tmp_path / "general_agent_promotion_terminal_certificate_candidates.json"
    candidate_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_set_id": "general-agent-promotion-terminal-certificate-candidates-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_gate_path": "gate.json",
                "source_gate_id": "general-agent-promotion-terminal-certificate-gate-0123456789abcdef",
                "ready_for_candidate_review": True,
                "ready_for_terminal_certificate_minting": False,
                "gate_action_count": 1,
                "candidate_count": 1,
                "skipped_gate_action_count": 0,
                "blocked_gate_action_count": 0,
                "blocked_reasons": ["terminal_certificate_minting_not_performed"],
                "candidates": [
                    {
                        "candidate_id": "terminal-certificate-candidate-0123456789abcdef",
                        "source_gate_item_id": "terminal-certificate-gate-item-01-document-live",
                        "source_queue_item_id": "live-evidence-queue-item-01-document-live",
                        "source_action_id": "document-live",
                        "source_plan_type": "adapter",
                        "terminal_gate_status": "admitted_runnable",
                        "approval_ref_present": False,
                        "approval_ref": None,
                        "evidence_required": [
                            "document_live_receipt.json",
                            "production_parser_registry_receipt",
                        ],
                        "receipt_validator": "adapter_evidence.document.production_parsers.receipt_check.passed",
                        "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                        "minting_status": "candidate_only",
                        "certificate_minted": False,
                        "execution_performed": False,
                    }
                ],
                "metadata": {
                    "candidate_plan_is_not_execution": True,
                    "terminal_certificates_minted": False,
                    "secret_values_serialized": False,
                    "source_gate_ready": False,
                    "source_gate_hash": "a" * 64,
                    "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                    "terminal_certificate_gate_schema_id": (
                        "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return candidate_path


def _write_capability_improvement_candidates(tmp_path: Path) -> Path:
    candidate_path = tmp_path / "general_agent_promotion_terminal_certificate_candidates.json"
    candidate_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_set_id": "general-agent-promotion-terminal-certificate-candidates-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_gate_path": "gate.json",
                "source_gate_id": "general-agent-promotion-terminal-certificate-gate-0123456789abcdef",
                "ready_for_candidate_review": True,
                "ready_for_terminal_certificate_minting": False,
                "gate_action_count": 1,
                "candidate_count": 1,
                "skipped_gate_action_count": 0,
                "blocked_gate_action_count": 0,
                "blocked_reasons": ["terminal_certificate_minting_not_performed"],
                "candidates": [
                    {
                        "candidate_id": "terminal-certificate-candidate-0123456789abcdef",
                        "source_gate_item_id": "terminal-certificate-gate-item-01-capability-proof",
                        "source_queue_item_id": "live-evidence-queue-item-01-capability-proof",
                        "source_action_id": "capability-improvement-agentic-control-governance-gate-evaluate",
                        "source_plan_type": "portfolio",
                        "terminal_gate_status": "admitted_approved",
                        "approval_ref_present": True,
                        "approval_ref": "approval://terminal-certificate-gate/capability-proof",
                        "evidence_required": [
                            "capability_registry:agentic_control.governance_gate.evaluate",
                            "change_command_not_certified",
                            "terminal_closure_missing",
                        ],
                        "receipt_validator": "capability_improvement_portfolio:test:plan",
                        "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                        "minting_status": "candidate_only",
                        "certificate_minted": False,
                        "execution_performed": False,
                    }
                ],
                "metadata": {
                    "candidate_plan_is_not_execution": True,
                    "terminal_certificates_minted": False,
                    "secret_values_serialized": False,
                    "source_gate_ready": False,
                    "source_gate_hash": "a" * 64,
                    "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                    "terminal_certificate_gate_schema_id": (
                        "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return candidate_path


def _write_deployment_publication_candidates(tmp_path: Path) -> Path:
    candidate_path = tmp_path / "general_agent_promotion_terminal_certificate_candidates.json"
    candidate_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_set_id": "general-agent-promotion-terminal-certificate-candidates-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_gate_path": "gate.json",
                "source_gate_id": "general-agent-promotion-terminal-certificate-gate-0123456789abcdef",
                "ready_for_candidate_review": True,
                "ready_for_terminal_certificate_minting": False,
                "gate_action_count": 1,
                "candidate_count": 1,
                "skipped_gate_action_count": 0,
                "blocked_gate_action_count": 0,
                "blocked_reasons": ["terminal_certificate_minting_not_performed"],
                "candidates": [
                    {
                        "candidate_id": "terminal-certificate-candidate-0123456789abcdef",
                        "source_gate_item_id": "terminal-certificate-gate-item-01-deployment",
                        "source_queue_item_id": "live-evidence-queue-item-01-deployment",
                        "source_action_id": "close-upstream-api-readiness-gate",
                        "source_plan_type": "deployment",
                        "terminal_gate_status": "admitted_approved",
                        "approval_ref_present": True,
                        "approval_ref": "approval://terminal-certificate-gate/deployment",
                        "evidence_required": [
                            "upstream_api_production_readiness_report",
                            "deployment_upstream_blocker_receipt",
                            "deployment_upstream_blocker_validation",
                            "upstream_recovery_completion_witness",
                            "api_runtime_host_readiness",
                            "dns_publication_authority",
                        ],
                        "receipt_validator": "deployment_publication_evidence_packet",
                        "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                        "minting_status": "candidate_only",
                        "certificate_minted": False,
                        "execution_performed": False,
                    }
                ],
                "metadata": {
                    "candidate_plan_is_not_execution": True,
                    "terminal_certificates_minted": False,
                    "secret_values_serialized": False,
                    "source_gate_ready": True,
                    "source_gate_hash": "a" * 64,
                    "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                    "terminal_certificate_gate_schema_id": (
                        "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return candidate_path


def _write_deployment_dns_candidates(tmp_path: Path) -> Path:
    candidate_path = tmp_path / "general_agent_promotion_terminal_certificate_candidates.json"
    candidate_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_set_id": "general-agent-promotion-terminal-certificate-candidates-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_gate_path": "gate.json",
                "source_gate_id": "general-agent-promotion-terminal-certificate-gate-0123456789abcdef",
                "ready_for_candidate_review": True,
                "ready_for_terminal_certificate_minting": False,
                "gate_action_count": 1,
                "candidate_count": 1,
                "skipped_gate_action_count": 0,
                "blocked_gate_action_count": 0,
                "blocked_reasons": ["terminal_certificate_minting_not_performed"],
                "candidates": [
                    {
                        "candidate_id": "terminal-certificate-candidate-0123456789abcdef",
                        "source_gate_item_id": "terminal-certificate-gate-item-01-dns",
                        "source_queue_item_id": "live-evidence-queue-item-01-dns",
                        "source_action_id": "verify-gateway-dns",
                        "source_plan_type": "deployment",
                        "terminal_gate_status": "admitted_approved",
                        "approval_ref_present": True,
                        "approval_ref": "approval://terminal-certificate-gate/dns",
                        "evidence_required": [
                            "gateway_dns_target_binding_receipt",
                            "gateway_dns_target_binding_validation",
                            "dns_resolution_receipt",
                            "dns_resolution_receipt_validation",
                            "deployment_witness_preflight",
                        ],
                        "receipt_validator": "deployment_publication_dns_evidence",
                        "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                        "minting_status": "candidate_only",
                        "certificate_minted": False,
                        "execution_performed": False,
                    }
                ],
                "metadata": {
                    "candidate_plan_is_not_execution": True,
                    "terminal_certificates_minted": False,
                    "secret_values_serialized": False,
                    "source_gate_ready": True,
                    "source_gate_hash": "a" * 64,
                    "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                    "terminal_certificate_gate_schema_id": (
                        "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return candidate_path


def _write_gateway_dns_target_binding_receipt(tmp_path: Path, *, ready: bool) -> Path:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "gateway-dns-target-binding-0123456789abcdef",
                "ready": ready,
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_gateway_dns_target_binding_validation(tmp_path: Path, *, ready: bool, valid: bool) -> Path:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt_validation.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "gateway-dns-target-binding-0123456789abcdef",
                "ready": ready,
                "valid": valid,
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_gateway_dns_resolution_receipt(tmp_path: Path, *, resolved: bool) -> Path:
    receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "gateway-dns-resolution-0123456789abcdef",
                "resolved": resolved,
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_gateway_dns_resolution_validation(tmp_path: Path, *, valid: bool) -> Path:
    receipt_path = tmp_path / "gateway_dns_resolution_receipt_validation.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "gateway-dns-resolution-0123456789abcdef",
                "valid": valid,
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_deployment_witness_preflight(tmp_path: Path, *, ready: bool) -> Path:
    receipt_path = tmp_path / "deployment_witness_preflight.json"
    receipt_path.write_text(
        json.dumps(
            {
                "gateway_url": "https://api.mullusi.com",
                "expected_environment": "pilot",
                "ready": ready,
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_document_receipt(tmp_path: Path, *, status: str) -> Path:
    receipt_path = tmp_path / "document_live_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "document-live-receipt-1",
                "adapter_id": "document.production_parsers",
                "status": status,
                "verification_status": "passed" if status == "passed" else "failed",
                "checked_at": "2026-05-01T12:00:00+00:00",
                "production_parser_ids": [
                    "production-pdf",
                    "production-docx",
                    "production-xlsx",
                    "production-pptx",
                ],
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_deployment_publication_evidence_packet(tmp_path: Path, *, ready: bool) -> Path:
    receipt_path = tmp_path / "deployment_publication_evidence_packet.json"
    receipt_path.write_text(
        json.dumps(
            {
                "packet_id": "deployment-publication-evidence-packet-0123456789abcdef",
                "output_dir": ".change_assurance/deployment_publication_evidence_packet",
                "gateway_host": "api.mullusi.com",
                "gateway_url": "https://api.mullusi.com",
                "expected_environment": "pilot",
                "ready": ready,
                "blockers": [] if ready else ["deployment_upstream_api_gate_not_ready"],
                "artifacts": {
                    "deployment_publication_closure_plan": "deployment_publication_closure_plan.json",
                    "deployment_publication_closure_plan_schema_validation": (
                        "deployment_publication_closure_plan_schema_validation.json"
                    ),
                    "deployment_publication_evidence_packet": "deployment_publication_evidence_packet.json",
                    "deployment_publication_evidence_packet_validation": (
                        "deployment_publication_evidence_packet_validation.json"
                    ),
                    "deployment_upstream_blocker_receipt": "deployment_upstream_blocker_receipt.json",
                    "deployment_upstream_blocker_validation": (
                        "deployment_upstream_blocker_receipt_validation.json"
                    ),
                    "gateway_dns_resolution_receipt": "gateway_dns_resolution_receipt.json",
                    "gateway_dns_resolution_validation": "gateway_dns_resolution_receipt_validation.json",
                    "gateway_dns_target_binding_receipt": "gateway_dns_target_binding_receipt.json",
                    "gateway_dns_target_binding_validation": "gateway_dns_target_binding_receipt_validation.json",
                    "gateway_publication_dispatch_plan": "gateway_publication_dispatch_plan.json",
                    "gateway_publication_readiness": "gateway_publication_readiness.json",
                },
                "validation_status": {
                    "deployment_publication_closure_plan_schema": ready,
                    "deployment_upstream_blocker": ready,
                    "gateway_dns_resolution": ready,
                    "gateway_dns_target_binding": ready,
                },
                "dispatch_command": [
                    "gh",
                    "workflow",
                    "run",
                    "gateway-publication.yml",
                ],
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_capability_improvement_proof_receipt(
    tmp_path: Path,
    *,
    registry_mutated: bool = False,
    name: str = "capability_improvement_proof_receipt.json",
) -> Path:
    receipt_path = tmp_path / name
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "receipt_type": "capability_improvement_proof_receipt",
                "receipt_id": "capability-improvement-proof-receipt-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_portfolio_path": "capability_improvement_portfolio.json",
                "source_portfolio_id": "capability-improvement-portfolio-0123456789abcdef",
                "source_portfolio_hash": "portfolio-hash",
                "capability_id": "agentic_control.governance_gate.evaluate",
                "plan_id": "capability-upgrade-plan-0123456789abcdef",
                "plan_hash": "plan-hash",
                "candidate_id": "capability-upgrade-candidate-0123456789abcdef",
                "status": "passed",
                "verification_status": "passed",
                "evidence_keys": [
                    "capability_registry:agentic_control.governance_gate.evaluate",
                    "change_command_not_certified",
                    "terminal_closure_missing",
                ],
                "stage_proofs": [
                    {
                        "stage": "capability_health",
                        "status": "passed",
                        "evidence_refs": ["capability_registry:agentic_control.governance_gate.evaluate"],
                    },
                    {
                        "stage": "weakness_diagnosis",
                        "status": "passed",
                        "evidence_refs": ["capability_maturity:capability-maturity-0123456789abcdef"],
                    },
                    {
                        "stage": "eval_generation",
                        "status": "passed",
                        "evidence_refs": ["fixtures/agentic_control.governance_gate.evaluate/upgrade/regression.json"],
                    },
                    {
                        "stage": "upgrade_candidate",
                        "status": "passed",
                        "evidence_refs": ["capability-upgrade-candidate-0123456789abcdef"],
                    },
                    {
                        "stage": "sandbox_test",
                        "status": "passed",
                        "evidence_refs": ["sandbox:agentic_control.governance_gate.evaluate:baseline-replay"],
                    },
                    {
                        "stage": "change_command",
                        "status": "passed",
                        "evidence_refs": ["change-command:agentic_control.governance_gate.evaluate:0123456789abcdef"],
                    },
                    {
                        "stage": "change_certificate",
                        "status": "passed",
                        "evidence_refs": ["change-certificate:agentic_control.governance_gate.evaluate:0123456789abcdef"],
                    },
                    {
                        "stage": "canary",
                        "status": "passed",
                        "evidence_refs": ["canary-handoff:agentic_control.governance_gate.evaluate:0123456789abcdef"],
                    },
                    {
                        "stage": "terminal_closure",
                        "status": "passed",
                        "evidence_refs": ["terminal-closure:agentic_control.governance_gate.evaluate:0123456789abcdef"],
                    },
                    {
                        "stage": "learning_admission",
                        "status": "passed",
                        "evidence_refs": ["learning-admission:agentic_control.governance_gate.evaluate:0123456789abcdef"],
                    },
                ],
                "resolved_blockers": [
                    "change_command_not_certified",
                    "terminal_closure_missing",
                ],
                "blockers": [],
                "metadata": {
                    "proof_is_not_execution": True,
                    "capability_activation_performed": False,
                    "registry_mutated": registry_mutated,
                    "terminal_certificates_minted": False,
                    "secret_values_serialized": False,
                    "operator_review_required": True,
                    "source_plan_activation_blocked": True,
                    "portfolio_schema_id": "urn:mullusi:schema:capability-improvement-portfolio:1",
                },
            }
        ),
        encoding="utf-8",
    )
    return receipt_path
