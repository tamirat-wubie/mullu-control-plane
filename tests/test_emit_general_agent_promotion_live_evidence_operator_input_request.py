"""Tests for general-agent live evidence operator input requests.

Purpose: prove blocked promotion live-evidence queues become public-safe
operator input requests.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.emit_general_agent_promotion_live_evidence_operator_input_request.
Invariants:
  - Missing environment bindings and manual parameters are explicit.
  - Secret values, connector query contents, and raw probe paths are not serialized.
  - Ready queues do not produce blocked operator inputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.emit_general_agent_promotion_live_evidence_operator_input_request import (  # noqa: E402
    emit_general_agent_live_evidence_operator_input_request,
    main,
    write_general_agent_live_evidence_operator_input_request,
)

SCHEMA_PATH = (
    _ROOT / "schemas" / "general_agent_promotion_live_evidence_operator_input_request.schema.json"
)


def test_operator_input_request_reports_missing_bindings_and_parameters(tmp_path: Path) -> None:
    queue_path = _write_blocked_queue(tmp_path)

    request = emit_general_agent_live_evidence_operator_input_request(
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
    )
    required_names = {name for item in request.required_inputs for name in item.required_names}
    input_kinds = {item.input_kind for item in request.required_inputs}
    rendered = json.dumps(request.as_dict(), sort_keys=True)

    assert request.request_id.startswith("general-agent-promotion-live-evidence-operator-input-request-")
    assert request.ready_to_execute is False
    assert request.execution_allowed is False
    assert request.solver_outcome == "AwaitingEvidence"
    assert request.proof_state == "Unknown"
    assert request.no_secret_values_serialized is True
    assert request.external_effect_performed is False
    assert request.production_ready_claimed is False
    assert {"environment_binding", "manual_parameter", "dependency_closure"} <= input_kinds
    assert {
        "OPENAI_API_KEY",
        "EMAIL_CALENDAR_CONNECTOR_TOKEN",
        "email_calendar_connector_id",
        "email_calendar_read_only_query",
    } <= required_names
    assert "secret-value" not in rendered
    assert "from:private@example.com" not in rendered
    assert "C:/private/probe.wav" not in rendered


def test_operator_input_request_cli_writes_report(tmp_path: Path, capsys) -> None:
    queue_path = _write_blocked_queue(tmp_path)
    output_path = tmp_path / "operator_input_request.json"
    request = emit_general_agent_live_evidence_operator_input_request(
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_general_agent_live_evidence_operator_input_request(request, output_path)
    exit_code = main(
        [
            "--queue",
            str(queue_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["execution_allowed"] is False
    assert payload["required_inputs"]
    assert stdout_payload["request_id"] == payload["request_id"]
    assert captured.err == ""


def test_operator_input_request_allows_ready_queue(tmp_path: Path) -> None:
    queue_path = _write_ready_queue(tmp_path)

    request = emit_general_agent_live_evidence_operator_input_request(
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
    )

    assert request.ready_to_execute is True
    assert request.execution_allowed is True
    assert request.solver_outcome == "SolvedVerified"
    assert request.proof_state == "Pass"
    assert request.required_inputs == ()
    assert request.blocked_actions == ()


def _write_blocked_queue(tmp_path: Path) -> Path:
    queue_path = tmp_path / "general_agent_promotion_live_evidence_queue.json"
    queue = _base_queue(
        ready_to_execute=False,
        actions=[
            _queue_action(
                queue_item_id="live-evidence-queue-item-01-voice-openai-voice-dependency-missing-openai-api-key",
                source_action_id="voice-openai-voice-dependency-missing-OPENAI-API-KEY",
                blocker="voice_dependency_missing:OPENAI_API_KEY",
                execution_class="approval_and_environment_blocked",
                approval_required=True,
                required_bindings=["MULLU_AUTHORITY_OPERATOR_SECRET", "OPENAI_API_KEY"],
                missing_bindings=["MULLU_AUTHORITY_OPERATOR_SECRET", "OPENAI_API_KEY"],
                blocked_reasons=[
                    "environment_binding_missing:MULLU_AUTHORITY_OPERATOR_SECRET",
                    "environment_binding_missing:OPENAI_API_KEY",
                ],
            ),
            _queue_action(
                queue_item_id="live-evidence-queue-item-04-communication-email-calendar-worker-email-calendar-live-evidence-missing",
                source_action_id="communication-email-calendar-worker-email-calendar-live-evidence-missing",
                blocker="email_calendar_live_evidence_missing",
                execution_class="requires_dependency_closure",
                approval_required=False,
                required_bindings=["EMAIL_CALENDAR_CONNECTOR_TOKEN"],
                missing_bindings=["EMAIL_CALENDAR_CONNECTOR_TOKEN"],
                manual_parameters=["email_calendar_connector_id", "email_calendar_read_only_query"],
                blocked_reasons=[
                    "environment_binding_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
                    "manual_parameter_required:email_calendar_connector_id",
                    "manual_parameter_required:email_calendar_read_only_query",
                    "dependency_action_requires_closure:communication-email-calendar-worker-email-calendar-dependency-missing-EMAIL-CALENDAR-CONNECTOR-TOKEN",
                ],
            ),
        ],
    )
    queue_path.write_text(json.dumps(queue), encoding="utf-8")
    return queue_path


def _write_ready_queue(tmp_path: Path) -> Path:
    queue_path = tmp_path / "general_agent_promotion_live_evidence_queue.json"
    queue = _base_queue(ready_to_execute=True, actions=[])
    queue_path.write_text(json.dumps(queue), encoding="utf-8")
    return queue_path


def _base_queue(*, ready_to_execute: bool, actions: list[dict[str, object]]) -> dict[str, object]:
    blocked_actions = [
        action
        for action in actions
        if action.get("execution_class") != "runnable_local"
    ]
    missing_bindings = sorted(
        {
            binding
            for action in actions
            for binding in action.get("missing_bindings", [])
            if isinstance(binding, str)
        }
    )
    blocked_reasons = sorted(
        {
            reason
            for action in actions
            for reason in action.get("blocked_reasons", [])
            if isinstance(reason, str)
        }
    )
    return {
        "schema_version": 1,
        "queue_id": "general-agent-promotion-live-evidence-queue-0123456789abcdef",
        "generated_at": "2026-05-01T12:00:00+00:00",
        "source_plan_path": ".change_assurance/general_agent_promotion_closure_plan.json",
        "environment_contract_path": "examples/general_agent_promotion_environment_bindings.json",
        "environment_binding_receipt_path": ".change_assurance/general_agent_promotion_environment_binding_receipt.json",
        "ready_to_execute": ready_to_execute,
        "action_count": len(actions),
        "runnable_action_count": len(actions) - len(blocked_actions),
        "blocked_action_count": len(blocked_actions),
        "approval_required_action_count": sum(
            1 for action in actions if action.get("approval_required") is True
        ),
        "missing_binding_count": len(missing_bindings),
        "missing_bindings": missing_bindings,
        "blocked_reasons": blocked_reasons,
        "actions": actions,
        "metadata": {
            "queue_is_not_execution": True,
            "secret_values_serialized": False,
            "environment_receipt_present": True,
            "environment_receipt_ready": False,
            "contract_binding_count": 9,
            "source_plan_id": "general-agent-promotion-closure-plan-0123456789abcdef",
            "source_plan_hash": "0" * 64,
        },
    }


def _queue_action(
    *,
    queue_item_id: str,
    source_action_id: str,
    blocker: str,
    execution_class: str,
    approval_required: bool,
    required_bindings: list[str],
    missing_bindings: list[str],
    manual_parameters: list[str] | None = None,
    blocked_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "queue_item_id": queue_item_id,
        "source_action_id": source_action_id,
        "source_plan_type": "adapter",
        "action_type": "live-receipt",
        "blocker": blocker,
        "execution_class": execution_class,
        "approval_required": approval_required,
        "required_bindings": required_bindings,
        "missing_bindings": missing_bindings,
        "uncontracted_bindings": [],
        "manual_parameters": manual_parameters or [],
        "dependent_action_ids": [],
        "blocked_reasons": blocked_reasons or [],
        "command": "redacted governed command",
        "evidence_required": ["redacted_evidence_name"],
        "receipt_validator": "redacted.receipt.validator",
    }
