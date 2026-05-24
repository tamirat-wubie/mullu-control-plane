"""Tests for general-agent promotion live-evidence queue planning.

Purpose: prove aggregate promotion actions are classified into runnable,
approval-bound, environment-bound, and review-only queue items.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.plan_general_agent_promotion_live_evidence_queue.
Invariants:
  - Queue planning never serializes secret values.
  - Missing bindings, uncontracted bindings, and manual parameters are explicit.
  - Schema validation covers the emitted queue artifact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_general_agent_promotion_live_evidence_queue import (  # noqa: E402
    main,
    plan_general_agent_promotion_live_evidence_queue,
    validate_general_agent_promotion_live_evidence_queue,
    write_general_agent_promotion_live_evidence_queue,
)


def test_live_evidence_queue_classifies_bindings_and_approvals(tmp_path: Path) -> None:
    plan_path = _write_promotion_plan(tmp_path)
    contract_path = _write_environment_contract(tmp_path)
    receipt_path = _write_environment_receipt(
        tmp_path,
        present_names=("MULLU_BROWSER_SANDBOX_EVIDENCE",),
    )

    queue = plan_general_agent_promotion_live_evidence_queue(
        promotion_plan_path=plan_path,
        environment_bindings_path=contract_path,
        environment_binding_receipt_path=receipt_path,
    )
    actions = {action.source_action_id: action for action in queue.actions}

    assert queue.ready_to_execute is False
    assert queue.action_count == 4
    assert queue.runnable_action_count == 1
    assert queue.blocked_action_count == 3
    assert queue.metadata["secret_values_serialized"] is False
    assert actions["browser-live"].execution_class == "runnable_local"
    assert actions["voice-live"].execution_class == "requires_environment_binding"
    assert "MULLU_VOICE_PROBE_AUDIO" in actions["voice-live"].missing_bindings
    assert actions["deployment-publish"].execution_class == "approval_and_environment_blocked"
    assert "MULLU_RUNTIME_WITNESS_SECRET" in actions["deployment-publish"].missing_bindings
    assert actions["portfolio-review"].execution_class == "approval_and_environment_blocked"
    assert "MULLU_AUTHORITY_OPERATOR_SECRET" in actions["portfolio-review"].missing_bindings
    assert "environment_binding_missing:MULLU_AUTHORITY_OPERATOR_SECRET" in queue.blocked_reasons
    assert validate_general_agent_promotion_live_evidence_queue(queue) == ()


def test_live_evidence_queue_exposes_missing_receipt_and_uncontracted_bindings(tmp_path: Path) -> None:
    plan_path = _write_promotion_plan(tmp_path, include_voice_dependency=True)
    contract_path = _write_environment_contract(tmp_path)
    missing_receipt_path = tmp_path / "missing-receipt.json"

    queue = plan_general_agent_promotion_live_evidence_queue(
        promotion_plan_path=plan_path,
        environment_bindings_path=contract_path,
        environment_binding_receipt_path=missing_receipt_path,
    )
    actions = {action.source_action_id: action for action in queue.actions}

    assert queue.metadata["environment_receipt_present"] is False
    assert queue.ready_to_execute is False
    assert "environment_binding_receipt_missing" in queue.blocked_reasons
    assert "OPENAI_API_KEY" in actions["voice-secret"].uncontracted_bindings
    assert "OPENAI_API_KEY" in actions["voice-secret"].missing_bindings
    assert "binding_not_in_environment_contract:OPENAI_API_KEY" in actions["voice-secret"].blocked_reasons
    assert queue.missing_binding_count >= 1
    assert validate_general_agent_promotion_live_evidence_queue(queue) == ()


def test_live_evidence_queue_rejects_invalid_receipt_presence(tmp_path: Path) -> None:
    plan_path = _write_promotion_plan(tmp_path)
    contract_path = _write_environment_contract(tmp_path)
    receipt_path = _write_environment_receipt(tmp_path, present_names=_CONTRACT_NAMES)
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_payload["bindings"][0]["value_serialized"] = True
    receipt_path.write_text(json.dumps(receipt_payload), encoding="utf-8")

    queue = plan_general_agent_promotion_live_evidence_queue(
        promotion_plan_path=plan_path,
        environment_bindings_path=contract_path,
        environment_binding_receipt_path=receipt_path,
    )
    browser_action = next(action for action in queue.actions if action.source_action_id == "browser-live")

    assert queue.metadata["environment_receipt_present"] is True
    assert queue.metadata["environment_receipt_ready"] is False
    assert browser_action.execution_class == "requires_environment_binding"
    assert "MULLU_BROWSER_SANDBOX_EVIDENCE" in browser_action.missing_bindings
    assert any(reason.startswith("environment_binding_receipt_invalid:") for reason in queue.blocked_reasons)
    assert validate_general_agent_promotion_live_evidence_queue(queue) == ()


def test_live_evidence_queue_writer_and_cli_emit_schema_valid_json(tmp_path: Path, capsys) -> None:
    plan_path = _write_promotion_plan(tmp_path)
    contract_path = _write_environment_contract(tmp_path)
    receipt_path = _write_environment_receipt(tmp_path, present_names=_CONTRACT_NAMES)
    output_path = tmp_path / "general_agent_promotion_live_evidence_queue.json"
    queue = plan_general_agent_promotion_live_evidence_queue(
        promotion_plan_path=plan_path,
        environment_bindings_path=contract_path,
        environment_binding_receipt_path=receipt_path,
    )

    written = write_general_agent_promotion_live_evidence_queue(queue, output_path)
    exit_code = main(
        [
            "--plan",
            str(plan_path),
            "--environment-bindings",
            str(contract_path),
            "--environment-binding-receipt",
            str(receipt_path),
            "--output",
            str(output_path),
            "--json",
            "--strict",
        ]
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(capsys.readouterr().out)

    assert written == output_path
    assert exit_code == 0
    assert payload["schema_version"] == 1
    assert "schema_valid" not in payload
    assert stdout_payload["schema_valid"] is True
    assert stdout_payload["metadata"]["secret_values_serialized"] is False


def test_live_evidence_queue_cli_require_ready_blocks_non_runnable_queue(tmp_path: Path, capsys) -> None:
    plan_path = _write_promotion_plan(tmp_path)
    contract_path = _write_environment_contract(tmp_path)
    receipt_path = _write_environment_receipt(tmp_path, present_names=("MULLU_BROWSER_SANDBOX_EVIDENCE",))

    exit_code = main(
        [
            "--plan",
            str(plan_path),
            "--environment-bindings",
            str(contract_path),
            "--environment-binding-receipt",
            str(receipt_path),
            "--output",
            str(tmp_path / "queue.json"),
            "--json",
            "--strict",
            "--require-ready",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["schema_valid"] is True
    assert payload["ready_to_execute"] is False
    assert payload["blocked_action_count"] > 0


_CONTRACT_NAMES = (
    "MULLU_BROWSER_SANDBOX_EVIDENCE",
    "MULLU_VOICE_PROBE_AUDIO",
    "MULLU_GATEWAY_URL",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_DEPLOYMENT_WITNESS_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
)


def _write_promotion_plan(tmp_path: Path, *, include_voice_dependency: bool = False) -> Path:
    actions = [
        {
            "action_id": "browser-live",
            "source_plan_type": "adapter",
            "action_type": "receipt",
            "blocker": "browser_live_evidence_missing",
            "command": "python scripts/produce_capability_adapter_live_receipts.py --target browser --strict",
            "receipt_validator": "browser_live_receipt.json",
            "evidence_required": ["browser_live_receipt.json"],
            "approval_required": False,
        },
        {
            "action_id": "voice-live",
            "source_plan_type": "adapter",
            "action_type": "receipt",
            "blocker": "voice_live_evidence_missing",
            "command": (
                "python scripts/produce_capability_adapter_live_receipts.py "
                "--target voice --voice-audio-path <approved_audio_sample> --strict"
            ),
            "receipt_validator": "voice_live_receipt.json",
            "evidence_required": ["voice_live_receipt.json"],
            "approval_required": False,
        },
        {
            "action_id": "deployment-publish",
            "source_plan_type": "deployment",
            "action_type": "publish-witness",
            "blocker": "deployment_witness_not_published",
            "command": "python scripts/publish_gateway_publication.py --gateway-url \"$MULLU_GATEWAY_URL\"",
            "receipt_validator": "gateway_publication_receipt.json",
            "evidence_required": ["gateway_publication_receipt.json"],
            "approval_required": True,
        },
        {
            "action_id": "portfolio-review",
            "source_plan_type": "portfolio",
            "action_type": "capability-improvement",
            "blocker": "capability_improvement_required:browser.open",
            "command": "Review activation-blocked improvement plan capability-upgrade-plan-browser-open.",
            "receipt_validator": "capability_improvement_portfolio:hash:plan",
            "evidence_required": ["capability_health:browser.open"],
            "approval_required": True,
        },
    ]
    if include_voice_dependency:
        actions.append(
            {
                "action_id": "voice-secret",
                "source_plan_type": "adapter",
                "action_type": "credential",
                "blocker": "voice_dependency_missing:OPENAI_API_KEY",
                "command": "Set OPENAI_API_KEY only in the governed voice-worker secret store.",
                "receipt_validator": "adapter_evidence.voice.openai.dependency.OPENAI_API_KEY",
                "evidence_required": ["secret_presence_attestation"],
                "approval_required": True,
            }
        )
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "plan_id": "general-agent-promotion-closure-plan-0123456789abcdef",
                "readiness_level": "pilot-governed-core",
                "source_ready": False,
                "total_action_count": len(actions),
                "approval_required_action_count": sum(1 for action in actions if action["approval_required"]),
                "source_plans": ["adapter.json", "deployment.json", "portfolio.json"],
                "blockers": [action["blocker"] for action in actions],
                "actions": actions,
            }
        ),
        encoding="utf-8",
    )
    return plan_path


def _write_environment_contract(tmp_path: Path) -> Path:
    contract_path = tmp_path / "general_agent_promotion_environment_bindings.json"
    contract_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contract_id": "general-agent-promotion-environment-bindings-v1",
                "status": "blocked_until_operator_binding",
                "secret_serialization": "forbidden",
                "bindings": [
                    {
                        "name": name,
                        "purpose": f"{name} presence proof.",
                        "binding_kind": _binding_kind(name),
                        "risk": _binding_risk(name),
                        "approval_required": name in {
                            "MULLU_VOICE_PROBE_AUDIO",
                            "MULLU_RUNTIME_WITNESS_SECRET",
                            "MULLU_RUNTIME_CONFORMANCE_SECRET",
                            "MULLU_DEPLOYMENT_WITNESS_SECRET",
                            "MULLU_AUTHORITY_OPERATOR_SECRET",
                        },
                        "may_serialize_value": False,
                        "required_for": ["handoff_preflight"],
                        "receipt_projection": "name_and_presence_only",
                    }
                    for name in _CONTRACT_NAMES
                ],
            }
        ),
        encoding="utf-8",
    )
    return contract_path


def _write_environment_receipt(tmp_path: Path, *, present_names: tuple[str, ...]) -> Path:
    receipt_path = tmp_path / "general_agent_promotion_environment_binding_receipt.json"
    missing = tuple(name for name in _CONTRACT_NAMES if name not in present_names)
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "receipt_id": "general-agent-promotion-environment-binding-receipt-v1",
                "checked_at": "2026-05-01T12:00:00+00:00",
                "contract_id": "general-agent-promotion-environment-bindings-v1",
                "secret_serialization": "forbidden",
                "ready": not missing,
                "binding_count": len(_CONTRACT_NAMES),
                "missing_bindings": list(missing),
                "bindings": [
                    {
                        "name": name,
                        "present": name in present_names,
                        "binding_kind": _binding_kind(name),
                        "risk": _binding_risk(name),
                        "approval_required": name in {
                            "MULLU_VOICE_PROBE_AUDIO",
                            "MULLU_RUNTIME_WITNESS_SECRET",
                            "MULLU_RUNTIME_CONFORMANCE_SECRET",
                            "MULLU_DEPLOYMENT_WITNESS_SECRET",
                            "MULLU_AUTHORITY_OPERATOR_SECRET",
                        },
                        "receipt_projection": "name_and_presence_only",
                        "value_serialized": False,
                    }
                    for name in _CONTRACT_NAMES
                ],
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _binding_kind(name: str) -> str:
    if name.endswith("_EVIDENCE"):
        return "artifact_path"
    if name.endswith("_AUDIO"):
        return "audio_path"
    if name.endswith("_URL"):
        return "url"
    return "secret"


def _binding_risk(name: str) -> str:
    if name == "MULLU_BROWSER_SANDBOX_EVIDENCE":
        return "medium"
    if name in {"MULLU_VOICE_PROBE_AUDIO", "MULLU_GATEWAY_URL"}:
        return "high"
    return "critical"
