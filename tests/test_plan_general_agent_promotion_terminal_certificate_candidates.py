"""Tests for terminal certificate candidate planning.

Purpose: prove terminal certificate candidates are derived only from admitted
gate items without executing actions or minting certificates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.plan_general_agent_promotion_terminal_certificate_candidates.
Invariants:
  - Blocked gate items are never promoted to candidates.
  - Candidate planning remains non-executing.
  - Terminal closure certificates are not minted by this planner.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_general_agent_promotion_terminal_certificate_candidates import (  # noqa: E402
    main,
    plan_general_agent_promotion_terminal_certificate_candidates,
    validate_general_agent_promotion_terminal_certificate_candidates,
    write_general_agent_promotion_terminal_certificate_candidates,
)


def test_terminal_certificate_candidates_include_only_admitted_gate_items(tmp_path: Path) -> None:
    gate_path = _write_gate(tmp_path)

    plan = plan_general_agent_promotion_terminal_certificate_candidates(gate_path=gate_path)
    candidates = {candidate.source_action_id: candidate for candidate in plan.candidates}

    assert plan.ready_for_candidate_review is True
    assert plan.ready_for_terminal_certificate_minting is False
    assert plan.gate_action_count == 3
    assert plan.candidate_count == 2
    assert plan.skipped_gate_action_count == 1
    assert plan.blocked_gate_action_count == 1
    assert plan.source_gate_path == "general_agent_promotion_terminal_certificate_gate.json"
    assert set(candidates) == {"document-live", "deploy-publish"}
    assert "voice-live" not in candidates
    assert candidates["document-live"].approval_ref is None
    assert candidates["deploy-publish"].approval_ref == "approval://deployment/publish"
    assert "terminal_certificate_minting_not_performed" in plan.blocked_reasons
    assert plan.metadata["candidate_plan_is_not_execution"] is True
    assert plan.metadata["terminal_certificates_minted"] is False
    assert tmp_path.name not in json.dumps(plan.as_dict(), sort_keys=True)
    assert validate_general_agent_promotion_terminal_certificate_candidates(plan) == ()


def test_terminal_certificate_candidates_invalid_gate_fails_closed(tmp_path: Path) -> None:
    gate_path = tmp_path / "invalid-gate.json"
    gate_path.write_text(json.dumps({"schema_version": 1, "actions": []}), encoding="utf-8")

    plan = plan_general_agent_promotion_terminal_certificate_candidates(gate_path=gate_path)

    assert plan.ready_for_candidate_review is False
    assert plan.ready_for_terminal_certificate_minting is False
    assert plan.candidate_count == 0
    assert plan.skipped_gate_action_count == 0
    assert plan.source_gate_id == "invalid-terminal-certificate-gate"
    assert any(reason.startswith("terminal_certificate_gate_invalid:") for reason in plan.blocked_reasons)
    assert validate_general_agent_promotion_terminal_certificate_candidates(plan) == ()


def test_terminal_certificate_candidates_writer_and_cli_emit_schema_valid_json(
    tmp_path: Path,
    capsys,
) -> None:
    gate_path = _write_gate(tmp_path)
    output_path = tmp_path / "general_agent_promotion_terminal_certificate_candidates.json"
    plan = plan_general_agent_promotion_terminal_certificate_candidates(gate_path=gate_path)

    written = write_general_agent_promotion_terminal_certificate_candidates(plan, output_path)
    exit_code = main(
        [
            "--gate",
            str(gate_path),
            "--output",
            str(output_path),
            "--json",
            "--strict",
            "--require-candidates",
        ]
    )
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(capsys.readouterr().out)

    assert written == output_path
    assert exit_code == 0
    assert file_payload["schema_version"] == 1
    assert "schema_valid" not in file_payload
    assert stdout_payload["schema_valid"] is True
    assert stdout_payload["candidate_count"] == 2
    assert stdout_payload["ready_for_terminal_certificate_minting"] is False
    assert stdout_payload["metadata"]["secret_values_serialized"] is False


def _write_gate(tmp_path: Path) -> Path:
    gate_path = tmp_path / "general_agent_promotion_terminal_certificate_gate.json"
    gate_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "gate_id": "general-agent-promotion-terminal-certificate-gate-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_queue_path": "queue.json",
                "approval_receipt_path": "approvals.json",
                "ready_for_terminal_certificate": False,
                "action_count": 3,
                "admitted_action_count": 2,
                "blocked_action_count": 1,
                "approval_bound_admitted_count": 1,
                "missing_approval_count": 0,
                "blocked_reasons": ["environment_binding_missing:MULLU_VOICE_PROBE_AUDIO"],
                "actions": [
                    _gate_action("document-live", "admitted_runnable", "adapter", None),
                    _gate_action(
                        "deploy-publish",
                        "admitted_approved",
                        "deployment",
                        "approval://deployment/publish",
                    ),
                    _gate_action(
                        "voice-live",
                        "blocked_environment",
                        "adapter",
                        None,
                        blocked_reasons=["environment_binding_missing:MULLU_VOICE_PROBE_AUDIO"],
                    ),
                ],
                "metadata": {
                    "gate_is_not_execution": True,
                    "secret_values_serialized": False,
                    "approval_receipt_present": True,
                    "approval_receipt_valid": True,
                    "queue_id": "general-agent-promotion-live-evidence-queue-0123456789abcdef",
                    "queue_hash": "a" * 64,
                    "queue_ready_to_execute": False,
                    "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
                },
            }
        ),
        encoding="utf-8",
    )
    return gate_path


def _gate_action(
    source_action_id: str,
    terminal_gate_status: str,
    source_plan_type: str,
    approval_ref: str | None,
    *,
    blocked_reasons: list[str] | None = None,
) -> dict[str, object]:
    admitted = terminal_gate_status in {"admitted_runnable", "admitted_approved"}
    candidate_id = "terminal-certificate-candidate-0123456789abcdef" if admitted else None
    if source_action_id == "deploy-publish":
        candidate_id = "terminal-certificate-candidate-fedcba9876543210"
    return {
        "gate_item_id": f"terminal-certificate-gate-item-01-{source_action_id}",
        "source_queue_item_id": f"live-evidence-queue-item-01-{source_action_id}",
        "source_action_id": source_action_id,
        "source_plan_type": source_plan_type,
        "execution_class": "requires_approval" if approval_ref else "runnable_local",
        "terminal_gate_status": terminal_gate_status,
        "approval_required": approval_ref is not None,
        "approval_ref_present": approval_ref is not None,
        "approval_ref": approval_ref,
        "certificate_candidate_id": candidate_id,
        "blocked_reasons": blocked_reasons or [],
        "evidence_required": [f"evidence:{source_action_id}"],
        "receipt_validator": f"validator:{source_action_id}",
    }
