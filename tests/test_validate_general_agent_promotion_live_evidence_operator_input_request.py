"""Tests for general-agent live evidence operator input request validation.

Purpose: prove operator input request validation catches schema, readiness, and
queue-alignment drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_general_agent_promotion_live_evidence_operator_input_request.
Invariants:
  - Blocked requests remain non-executing.
  - Execution allowance mirrors the source queue.
  - Blocked action projections cannot drift silently.
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
    write_general_agent_live_evidence_operator_input_request,
)
from scripts.validate_general_agent_promotion_live_evidence_operator_input_request import (  # noqa: E402
    main,
    validate_general_agent_live_evidence_operator_input_request,
    write_general_agent_live_evidence_operator_input_request_validation,
)
SCHEMA_PATH = (
    _ROOT / "schemas" / "general_agent_promotion_live_evidence_operator_input_request.schema.json"
)


def test_validate_operator_input_request_accepts_blocked_request(tmp_path: Path) -> None:
    queue_path = _write_blocked_queue(tmp_path)
    request_path = _write_request(tmp_path, queue_path)

    validation = validate_general_agent_live_evidence_operator_input_request(
        request_path=request_path,
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.valid is True
    assert validation.ready_to_execute is False
    assert validation.execution_allowed is False
    assert validation.errors == ()
    assert "bind missing environment inputs" in validation.next_action


def test_validate_operator_input_request_accepts_ready_request(tmp_path: Path) -> None:
    queue_path = _write_ready_queue(tmp_path)
    request_path = _write_request(tmp_path, queue_path)

    validation = validate_general_agent_live_evidence_operator_input_request(
        request_path=request_path,
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready_to_execute is True
    assert validation.execution_allowed is True
    assert validation.errors == ()
    assert "execution authority" in validation.next_action


def test_validate_operator_input_request_rejects_execution_drift(tmp_path: Path) -> None:
    queue_path = _write_blocked_queue(tmp_path)
    request_path = _write_request(tmp_path, queue_path)
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    payload["execution_allowed"] = True
    payload["solver_outcome"] = "SolvedVerified"
    payload["proof_state"] = "Pass"
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_live_evidence_operator_input_request(
        request_path=request_path,
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.valid is False
    assert validation.execution_allowed is True
    assert any("require blocked" in error for error in validation.errors)
    assert any("execution_allowed must equal source readiness" in error for error in validation.errors)


def test_validate_operator_input_request_cli_writes_validation(tmp_path: Path, capsys) -> None:
    queue_path = _write_blocked_queue(tmp_path)
    request_path = _write_request(tmp_path, queue_path)
    output_path = tmp_path / "validation.json"
    validation = validate_general_agent_live_evidence_operator_input_request(
        request_path=request_path,
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_general_agent_live_evidence_operator_input_request_validation(
        validation,
        output_path,
    )
    exit_code = main(
        [
            "--request",
            str(request_path),
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
    assert payload["valid"] is True
    assert stdout_payload["valid"] is True
    assert captured.err == ""


def _write_request(tmp_path: Path, queue_path: Path) -> Path:
    request_path = tmp_path / "general_agent_promotion_live_evidence_operator_input_request.json"
    request = emit_general_agent_live_evidence_operator_input_request(
        queue_path=queue_path,
        schema_path=SCHEMA_PATH,
    )
    write_general_agent_live_evidence_operator_input_request(request, request_path)
    return request_path


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
            )
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
        "manual_parameters": [],
        "dependent_action_ids": [],
        "blocked_reasons": blocked_reasons or [],
        "command": "redacted governed command",
        "evidence_required": ["redacted_evidence_name"],
        "receipt_validator": "redacted.receipt.validator",
    }
