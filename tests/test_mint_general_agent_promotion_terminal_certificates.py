"""Tests for terminal certificate minting executor.

Purpose: prove terminal closure certificates are minted only from a ready
promotion minting gate and remain schema-valid.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.mint_general_agent_promotion_terminal_certificates.
Invariants:
  - A blocked gate mints no terminal certificate.
  - A ready gate mints schema-valid terminal closure certificates.
  - The minting run records blocked reasons without serializing secrets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.mint_general_agent_promotion_terminal_certificates import (  # noqa: E402
    main,
    mint_general_agent_promotion_terminal_certificates,
    validate_general_agent_promotion_terminal_certificate_minting_run,
    write_general_agent_promotion_terminal_certificate_minting_run,
)
from scripts.validate_terminal_closure_certificate import validate_terminal_closure_certificate  # noqa: E402


def test_terminal_certificate_minting_executor_mints_ready_gate(tmp_path: Path) -> None:
    gate_path = _write_gate(tmp_path, ready=True)
    certificate_dir = tmp_path / "certificates"

    run = mint_general_agent_promotion_terminal_certificates(
        minting_gate_path=gate_path,
        certificate_output_dir=certificate_dir,
    )
    certificate_ref = run.certificates[0]
    certificate_payload = json.loads(Path(certificate_ref.certificate_path).read_text(encoding="utf-8"))
    certificate_validation = validate_terminal_closure_certificate(
        certificate_path=Path(certificate_ref.certificate_path)
    )

    assert run.terminal_certificates_minted is True
    assert run.certificate_count == 1
    assert run.blocked_candidate_count == 0
    assert run.blocked_reasons == ()
    assert run.metadata["minting_executor_performed"] is True
    assert run.metadata["secret_values_serialized"] is False
    assert certificate_ref.schema_valid is True
    assert certificate_ref.validation_errors == ()
    assert certificate_validation.valid is True
    assert certificate_payload["certificate_id"] == "terminal-closure-certificate-0123456789abcdef"
    assert certificate_payload["command_id"] == "document-live"
    assert certificate_payload["execution_id"] == "terminal-certificate-candidate-0123456789abcdef"
    assert certificate_payload["disposition"] == "committed"
    assert "document_live_receipt.json" in certificate_payload["evidence_refs"]
    assert validate_general_agent_promotion_terminal_certificate_minting_run(run) == ()


def test_terminal_certificate_minting_executor_blocks_unready_gate(tmp_path: Path) -> None:
    gate_path = _write_gate(tmp_path, ready=False)
    certificate_dir = tmp_path / "certificates"

    run = mint_general_agent_promotion_terminal_certificates(
        minting_gate_path=gate_path,
        certificate_output_dir=certificate_dir,
    )

    assert run.terminal_certificates_minted is False
    assert run.certificate_count == 0
    assert run.blocked_candidate_count == 1
    assert "missing_terminal_minting_authority_ref" in run.blocked_reasons
    assert run.metadata["minting_executor_performed"] is False
    assert not certificate_dir.exists()
    assert validate_general_agent_promotion_terminal_certificate_minting_run(run) == ()


def test_terminal_certificate_minting_executor_invalid_gate_fails_closed(tmp_path: Path) -> None:
    gate_path = tmp_path / "invalid-minting-gate.json"
    gate_path.write_text(json.dumps({"schema_version": 1, "candidates": []}), encoding="utf-8")

    run = mint_general_agent_promotion_terminal_certificates(minting_gate_path=gate_path)

    assert run.terminal_certificates_minted is False
    assert run.certificate_count == 0
    assert run.blocked_candidate_count == 1
    assert any(reason.startswith("terminal_minting_gate_invalid:") for reason in run.blocked_reasons)
    assert validate_general_agent_promotion_terminal_certificate_minting_run(run) == ()


def test_terminal_certificate_minting_executor_writer_and_cli_emit_schema_valid_json(
    tmp_path: Path,
    capsys,
) -> None:
    gate_path = _write_gate(tmp_path, ready=True)
    certificate_dir = tmp_path / "certificates"
    output_path = tmp_path / "general_agent_promotion_terminal_certificate_minting_run.json"
    run = mint_general_agent_promotion_terminal_certificates(
        minting_gate_path=gate_path,
        certificate_output_dir=certificate_dir,
    )

    written = write_general_agent_promotion_terminal_certificate_minting_run(run, output_path)
    exit_code = main(
        [
            "--gate",
            str(gate_path),
            "--certificate-dir",
            str(certificate_dir),
            "--output",
            str(output_path),
            "--json",
            "--strict",
            "--require-minted",
        ]
    )
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(capsys.readouterr().out)

    assert written == output_path
    assert exit_code == 0
    assert file_payload["schema_version"] == 1
    assert "schema_valid" not in file_payload
    assert stdout_payload["schema_valid"] is True
    assert stdout_payload["terminal_certificates_minted"] is True
    assert stdout_payload["certificate_count"] == 1


def _write_gate(tmp_path: Path, *, ready: bool) -> Path:
    gate_path = tmp_path / "general_agent_promotion_terminal_minting_gate.json"
    status = "admitted_for_terminal_certificate_minting" if ready else "blocked_missing_authority"
    blocked_reasons = [] if ready else ["missing_terminal_minting_authority_ref"]
    gate_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "minting_gate_id": "general-agent-promotion-terminal-minting-gate-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_reconciliation_path": "reconciliation.json",
                "source_reconciliation_id": (
                    "general-agent-promotion-terminal-evidence-reconciliation-0123456789abcdef"
                ),
                "authority_ref_present": ready,
                "authority_ref": "operator-approval:terminal-minting-1" if ready else None,
                "ready_for_terminal_certificate_minting": ready,
                "candidate_count": 1,
                "admitted_candidate_count": 1 if ready else 0,
                "blocked_candidate_count": 0 if ready else 1,
                "blocked_reasons": blocked_reasons,
                "candidates": [
                    {
                        "candidate_id": "terminal-certificate-candidate-0123456789abcdef",
                        "source_action_id": "document-live",
                        "minting_gate_status": status,
                        "ready_for_terminal_certificate_minting": ready,
                        "certificate_minted": False,
                        "execution_performed": False,
                        "authority_ref_present": ready,
                        "receipt_refs": ["document_live_receipt.json"] if ready else [],
                        "blocked_reasons": blocked_reasons,
                        "prospective_certificate_id": "terminal-closure-certificate-0123456789abcdef",
                    }
                ],
                "metadata": {
                    "minting_gate_is_not_execution": True,
                    "terminal_certificates_minted": False,
                    "secret_values_serialized": False,
                    "source_reconciliation_hash": "a" * 64,
                    "reconciliation_schema_id": (
                        "urn:mullusi:schema:general-agent-promotion-terminal-evidence-reconciliation:1"
                    ),
                    "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                    "authority_model": "explicit_operator_authority_required",
                },
            }
        ),
        encoding="utf-8",
    )
    return gate_path
