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


def _write_capability_improvement_proof_receipt(
    tmp_path: Path,
    *,
    registry_mutated: bool = False,
) -> Path:
    receipt_path = tmp_path / "capability_improvement_proof_receipt.json"
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
