"""Tests for terminal minting gate.

Purpose: prove terminal certificate minting readiness requires both reconciled
evidence and explicit authority while preserving the non-execution boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.gate_general_agent_promotion_terminal_minting.
Invariants:
  - Missing authority blocks minting readiness.
  - Blocked reconciliation blocks minting readiness.
  - The gate never mints terminal certificates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.gate_general_agent_promotion_terminal_minting import (  # noqa: E402
    gate_general_agent_promotion_terminal_minting,
    main,
    validate_general_agent_promotion_terminal_minting_gate,
    write_general_agent_promotion_terminal_minting_gate,
)


def test_terminal_minting_gate_admits_ready_reconciliation_with_authority(tmp_path: Path) -> None:
    reconciliation_path = _write_reconciliation(tmp_path, ready=True)

    gate = gate_general_agent_promotion_terminal_minting(
        reconciliation_path=reconciliation_path,
        authority_ref="operator-approval:terminal-minting-1",
    )
    candidate = gate.candidates[0]

    assert gate.ready_for_terminal_certificate_minting is True
    assert gate.authority_ref_present is True
    assert gate.admitted_candidate_count == 1
    assert gate.blocked_candidate_count == 0
    assert gate.source_reconciliation_path == "general_agent_promotion_terminal_evidence_reconciliation.json"
    assert candidate.minting_gate_status == "admitted_for_terminal_certificate_minting"
    assert candidate.ready_for_terminal_certificate_minting is True
    assert candidate.blocked_reasons == ()
    assert candidate.prospective_certificate_id.startswith("terminal-closure-certificate-")
    assert gate.metadata["minting_gate_is_not_execution"] is True
    assert gate.metadata["terminal_certificates_minted"] is False
    assert tmp_path.name not in json.dumps(gate.as_dict(), sort_keys=True)
    assert validate_general_agent_promotion_terminal_minting_gate(gate) == ()


def test_terminal_minting_gate_blocks_ready_reconciliation_without_authority(tmp_path: Path) -> None:
    reconciliation_path = _write_reconciliation(tmp_path, ready=True)

    gate = gate_general_agent_promotion_terminal_minting(reconciliation_path=reconciliation_path)
    candidate = gate.candidates[0]

    assert gate.ready_for_terminal_certificate_minting is False
    assert gate.authority_ref_present is False
    assert gate.admitted_candidate_count == 0
    assert gate.blocked_candidate_count == 1
    assert candidate.minting_gate_status == "blocked_missing_authority"
    assert "missing_terminal_minting_authority_ref" in candidate.blocked_reasons
    assert "missing_terminal_minting_authority_ref" in gate.blocked_reasons
    assert validate_general_agent_promotion_terminal_minting_gate(gate) == ()


def test_terminal_minting_gate_blocks_unready_reconciliation_even_with_authority(tmp_path: Path) -> None:
    reconciliation_path = _write_reconciliation(tmp_path, ready=False)

    gate = gate_general_agent_promotion_terminal_minting(
        reconciliation_path=reconciliation_path,
        authority_ref="operator-approval:terminal-minting-1",
    )
    candidate = gate.candidates[0]

    assert gate.ready_for_terminal_certificate_minting is False
    assert gate.admitted_candidate_count == 0
    assert gate.blocked_candidate_count == 1
    assert candidate.minting_gate_status == "blocked_reconciliation_not_ready"
    assert "terminal_evidence_reconciliation_not_ready" in candidate.blocked_reasons
    assert "missing_evidence:document_live_receipt.json" in candidate.blocked_reasons
    assert validate_general_agent_promotion_terminal_minting_gate(gate) == ()


def test_terminal_minting_gate_invalid_reconciliation_fails_closed(tmp_path: Path) -> None:
    reconciliation_path = tmp_path / "invalid-reconciliation.json"
    reconciliation_path.write_text(json.dumps({"schema_version": 1, "candidates": []}), encoding="utf-8")

    gate = gate_general_agent_promotion_terminal_minting(
        reconciliation_path=reconciliation_path,
        authority_ref="operator-approval:terminal-minting-1",
    )

    assert gate.ready_for_terminal_certificate_minting is False
    assert gate.candidate_count == 1
    assert gate.blocked_candidate_count == 1
    assert gate.candidates[0].minting_gate_status == "blocked_invalid_reconciliation"
    assert any(reason.startswith("terminal_evidence_reconciliation_invalid:") for reason in gate.blocked_reasons)
    assert validate_general_agent_promotion_terminal_minting_gate(gate) == ()


def test_terminal_minting_gate_writer_and_cli_emit_schema_valid_json(tmp_path: Path, capsys) -> None:
    reconciliation_path = _write_reconciliation(tmp_path, ready=True)
    output_path = tmp_path / "general_agent_promotion_terminal_minting_gate.json"
    gate = gate_general_agent_promotion_terminal_minting(
        reconciliation_path=reconciliation_path,
        authority_ref="operator-approval:terminal-minting-1",
    )

    written = write_general_agent_promotion_terminal_minting_gate(gate, output_path)
    exit_code = main(
        [
            "--reconciliation",
            str(reconciliation_path),
            "--authority-ref",
            "operator-approval:terminal-minting-1",
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
    assert stdout_payload["metadata"]["terminal_certificates_minted"] is False


def _write_reconciliation(tmp_path: Path, *, ready: bool) -> Path:
    reconciliation_path = tmp_path / "general_agent_promotion_terminal_evidence_reconciliation.json"
    candidate_status = "reconciled" if ready else "blocked_missing_evidence"
    missing_evidence = [] if ready else ["document_live_receipt.json"]
    blocked_reasons = [] if ready else ["missing_evidence:document_live_receipt.json"]
    reconciliation_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reconciliation_id": "general-agent-promotion-terminal-evidence-reconciliation-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_candidate_path": "candidates.json",
                "source_candidate_set_id": "general-agent-promotion-terminal-certificate-candidates-0123456789abcdef",
                "ready_for_terminal_certificate_minting": ready,
                "candidate_count": 1,
                "reconciled_candidate_count": 1 if ready else 0,
                "blocked_candidate_count": 0 if ready else 1,
                "missing_evidence_count": 0 if ready else 1,
                "blocked_reasons": blocked_reasons,
                "candidates": [
                    {
                        "candidate_id": "terminal-certificate-candidate-0123456789abcdef",
                        "source_action_id": "document-live",
                        "reconciliation_status": candidate_status,
                        "ready_for_terminal_certificate_minting": ready,
                        "certificate_minted": False,
                        "execution_performed": False,
                        "evidence_required": ["document_live_receipt.json"],
                        "evidence_matched": ["document_live_receipt.json"] if ready else [],
                        "missing_evidence": missing_evidence,
                        "receipt_refs": ["document_live_receipt.json"] if ready else [],
                        "blocked_reasons": blocked_reasons,
                    }
                ],
                "metadata": {
                    "reconciliation_is_not_execution": True,
                    "terminal_certificates_minted": False,
                    "secret_values_serialized": False,
                    "source_candidate_hash": "a" * 64,
                    "candidate_schema_id": (
                        "urn:mullusi:schema:general-agent-promotion-terminal-certificate-candidates:1"
                    ),
                    "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                },
            }
        ),
        encoding="utf-8",
    )
    return reconciliation_path
