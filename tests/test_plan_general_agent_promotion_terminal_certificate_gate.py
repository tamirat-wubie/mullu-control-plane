"""Tests for general-agent promotion terminal certificate gate planning.

Purpose: prove terminal certificate candidates are admitted only from runnable
or explicitly approved live-evidence queue items.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.plan_general_agent_promotion_terminal_certificate_gate.
Invariants:
  - Environment-blocked items remain blocked even with approval evidence.
  - Approval-bound items require approved refs.
  - Invalid approval receipts fail closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_general_agent_promotion_terminal_certificate_gate import (  # noqa: E402
    main,
    plan_general_agent_promotion_terminal_certificate_gate,
    validate_general_agent_promotion_terminal_certificate_gate,
    write_general_agent_promotion_terminal_certificate_gate,
)


def test_terminal_certificate_gate_admits_only_runnable_and_approved_items(tmp_path: Path) -> None:
    queue_path = _write_queue(tmp_path)
    approval_path = _write_approval_receipt(
        tmp_path,
        approvals={
            "deploy-publish": "approval://deployment/publish",
            "portfolio-review": "approval://portfolio/review",
        },
    )

    gate = plan_general_agent_promotion_terminal_certificate_gate(
        queue_path=queue_path,
        approval_receipt_path=approval_path,
    )
    actions = {action.source_action_id: action for action in gate.actions}

    assert gate.ready_for_terminal_certificate is False
    assert gate.action_count == 6
    assert gate.admitted_action_count == 3
    assert gate.blocked_action_count == 3
    assert gate.approval_bound_admitted_count == 2
    assert gate.source_queue_path == "general_agent_promotion_live_evidence_queue.json"
    assert gate.approval_receipt_path == "general_agent_promotion_terminal_approvals.json"
    assert actions["document-live"].terminal_gate_status == "admitted_runnable"
    assert actions["deploy-publish"].terminal_gate_status == "admitted_approved"
    assert actions["portfolio-review"].terminal_gate_status == "admitted_approved"
    assert actions["voice-live"].terminal_gate_status == "blocked_dependency"
    assert "dependency_action_requires_closure:voice-secret" in actions["voice-live"].blocked_reasons
    assert actions["browser-sandbox"].terminal_gate_status == "blocked_environment"
    assert "execution_environment_unmet:browser_sandbox_runner_linux_only" in actions["browser-sandbox"].blocked_reasons
    assert actions["deploy-blocked"].terminal_gate_status == "blocked_approval_and_environment"
    assert actions["deploy-blocked"].approval_ref_present is False
    assert "explicit_approval_ref_missing" in actions["deploy-blocked"].blocked_reasons
    assert tmp_path.name not in json.dumps(gate.as_dict(), sort_keys=True)
    assert validate_general_agent_promotion_terminal_certificate_gate(gate) == ()


def test_terminal_certificate_gate_blocks_approval_classes_without_receipt(tmp_path: Path) -> None:
    queue_path = _write_queue(tmp_path)
    missing_approval_path = tmp_path / "missing-approvals.json"

    gate = plan_general_agent_promotion_terminal_certificate_gate(
        queue_path=queue_path,
        approval_receipt_path=missing_approval_path,
    )
    actions = {action.source_action_id: action for action in gate.actions}

    assert gate.metadata["approval_receipt_present"] is False
    assert gate.approval_receipt_path == "missing-approvals.json"
    assert gate.admitted_action_count == 1
    assert gate.missing_approval_count == 3
    assert actions["deploy-publish"].terminal_gate_status == "blocked_approval"
    assert "approval_receipt_missing" in actions["deploy-publish"].blocked_reasons
    assert "explicit_approval_ref_missing" in gate.blocked_reasons
    assert validate_general_agent_promotion_terminal_certificate_gate(gate) == ()


def test_terminal_certificate_gate_invalid_approval_receipt_fails_closed(tmp_path: Path) -> None:
    queue_path = _write_queue(tmp_path)
    approval_path = _write_approval_receipt(
        tmp_path,
        approvals={"deploy-publish": "approval://deployment/publish"},
        value_serialized=True,
    )

    gate = plan_general_agent_promotion_terminal_certificate_gate(
        queue_path=queue_path,
        approval_receipt_path=approval_path,
    )
    deploy_action = next(action for action in gate.actions if action.source_action_id == "deploy-publish")

    assert gate.metadata["approval_receipt_present"] is True
    assert gate.metadata["approval_receipt_valid"] is False
    assert deploy_action.terminal_gate_status == "blocked_approval"
    assert deploy_action.approval_ref_present is False
    assert any(reason.startswith("approval_receipt_entry_") for reason in gate.blocked_reasons)
    assert validate_general_agent_promotion_terminal_certificate_gate(gate) == ()


def test_terminal_certificate_gate_writer_and_cli_emit_schema_valid_json(tmp_path: Path, capsys) -> None:
    queue_path = _write_queue(tmp_path)
    approval_path = _write_approval_receipt(
        tmp_path,
        approvals={
            "deploy-publish": "approval://deployment/publish",
            "portfolio-review": "approval://portfolio/review",
        },
    )
    output_path = tmp_path / "general_agent_promotion_terminal_certificate_gate.json"
    gate = plan_general_agent_promotion_terminal_certificate_gate(
        queue_path=queue_path,
        approval_receipt_path=approval_path,
    )

    written = write_general_agent_promotion_terminal_certificate_gate(gate, output_path)
    exit_code = main(
        [
            "--queue",
            str(queue_path),
            "--approval-receipt",
            str(approval_path),
            "--output",
            str(output_path),
            "--json",
            "--strict",
        ]
    )
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(capsys.readouterr().out)

    assert written == output_path
    assert exit_code == 0
    assert file_payload["schema_version"] == 1
    assert "schema_valid" not in file_payload
    assert stdout_payload["schema_valid"] is True
    assert stdout_payload["metadata"]["gate_is_not_execution"] is True
    assert stdout_payload["metadata"]["secret_values_serialized"] is False


def test_terminal_certificate_gate_cli_require_ready_blocks_partial_gate(tmp_path: Path, capsys) -> None:
    queue_path = _write_queue(tmp_path)
    approval_path = _write_approval_receipt(tmp_path, approvals={})

    exit_code = main(
        [
            "--queue",
            str(queue_path),
            "--approval-receipt",
            str(approval_path),
            "--output",
            str(tmp_path / "gate.json"),
            "--json",
            "--strict",
            "--require-ready",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["schema_valid"] is True
    assert payload["ready_for_terminal_certificate"] is False
    assert payload["blocked_action_count"] > 0


def _write_queue(tmp_path: Path) -> Path:
    queue_path = tmp_path / "general_agent_promotion_live_evidence_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "queue_id": "general-agent-promotion-live-evidence-queue-0123456789abcdef",
                "generated_at": "2026-05-01T12:00:00+00:00",
                "source_plan_path": "promotion-plan.json",
                "environment_contract_path": "environment-bindings.json",
                "environment_binding_receipt_path": "environment-receipt.json",
                "ready_to_execute": False,
                "action_count": 6,
                "runnable_action_count": 1,
                "blocked_action_count": 5,
                "approval_required_action_count": 3,
                "missing_binding_count": 1,
                "missing_bindings": ["MULLU_GATEWAY_URL"],
                "blocked_reasons": [
                    "dependency_action_requires_closure:voice-secret",
                    "environment_binding_missing:MULLU_GATEWAY_URL",
                    "execution_environment_unmet:browser_sandbox_runner_linux_only",
                ],
                "actions": [
                    _queue_action("document-live", "runnable_local", False, "adapter"),
                    _queue_action("deploy-publish", "requires_approval", True, "deployment"),
                    _queue_action("portfolio-review", "review_only", True, "portfolio"),
                    _queue_action(
                        "voice-live",
                        "requires_dependency_closure",
                        False,
                        "adapter",
                        blocked_reasons=["dependency_action_requires_closure:voice-secret"],
                        dependent_action_ids=["voice-secret"],
                    ),
                    _queue_action(
                        "browser-sandbox",
                        "requires_execution_environment",
                        False,
                        "adapter",
                        blocked_reasons=["execution_environment_unmet:browser_sandbox_runner_linux_only"],
                    ),
                    _queue_action(
                        "deploy-blocked",
                        "approval_and_environment_blocked",
                        True,
                        "deployment",
                        blocked_reasons=["environment_binding_missing:MULLU_GATEWAY_URL"],
                    ),
                ],
                "metadata": {
                    "queue_is_not_execution": True,
                    "secret_values_serialized": False,
                    "environment_receipt_present": True,
                    "environment_receipt_ready": False,
                    "contract_binding_count": 7,
                    "source_plan_id": "general-agent-promotion-closure-plan-0123456789abcdef",
                    "source_plan_hash": "a" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    return queue_path


def _queue_action(
    source_action_id: str,
    execution_class: str,
    approval_required: bool,
    source_plan_type: str,
    *,
    blocked_reasons: list[str] | None = None,
    dependent_action_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "queue_item_id": f"live-evidence-queue-item-01-{source_action_id}",
        "source_action_id": source_action_id,
        "source_plan_type": source_plan_type,
        "action_type": "live-receipt",
        "blocker": f"{source_action_id}-blocker",
        "execution_class": execution_class,
        "approval_required": approval_required,
        "required_bindings": [],
        "missing_bindings": [],
        "uncontracted_bindings": [],
        "manual_parameters": [],
        "dependent_action_ids": dependent_action_ids or [],
        "blocked_reasons": blocked_reasons or [],
        "command": f"Run {source_action_id}.",
        "evidence_required": [f"evidence:{source_action_id}"],
        "receipt_validator": f"validator:{source_action_id}",
    }


def _write_approval_receipt(
    tmp_path: Path,
    *,
    approvals: dict[str, str],
    value_serialized: bool = False,
) -> Path:
    approval_path = tmp_path / "general_agent_promotion_terminal_approvals.json"
    approval_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "receipt_id": "general-agent-promotion-terminal-approvals-v1",
                "checked_at": "2026-05-01T12:00:00+00:00",
                "secret_serialization": "forbidden",
                "approvals": [
                    {
                        "source_action_id": source_action_id,
                        "approval_ref": approval_ref,
                        "approved": True,
                        "scope": "terminal_certificate_gate",
                        "value_serialized": value_serialized,
                    }
                    for source_action_id, approval_ref in approvals.items()
                ],
                "metadata": {
                    "gate_is_not_execution": True,
                    "secret_values_serialized": False,
                    "approval_values_are_refs": True,
                    "terminal_certificate_gate_schema_id": (
                        "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return approval_path
