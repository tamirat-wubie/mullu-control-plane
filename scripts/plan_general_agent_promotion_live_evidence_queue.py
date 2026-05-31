#!/usr/bin/env python3
"""Plan the general-agent promotion live-evidence execution queue.

Purpose: classify aggregate promotion closure actions into runnable, approval,
environment-bound, execution-environment-bound, and review-only queue items
without executing live effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: aggregate promotion closure plan, environment binding contract,
redacted environment binding receipt, and live evidence queue schema.
Invariants:
  - The queue is a proof artifact, not an execution grant.
  - Secret values are never read, printed, or serialized.
  - Missing bindings, uncontracted bindings, manual parameters, and execution
    environment blockers are explicit.
  - Approval-required source actions remain approval-required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_general_agent_promotion_environment_bindings import (  # noqa: E402
    DEFAULT_CONTRACT as DEFAULT_ENVIRONMENT_BINDINGS,
)
from scripts.validate_general_agent_promotion_environment_binding_receipt import (  # noqa: E402
    validate_general_agent_promotion_environment_binding_receipt,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_PROMOTION_PLAN = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan.json"
DEFAULT_ENVIRONMENT_BINDING_RECEIPT = (
    REPO_ROOT / ".change_assurance" / "general_agent_promotion_environment_binding_receipt.json"
)
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_live_evidence_queue.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_live_evidence_queue.json"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"

PLACEHOLDER_PATTERN = re.compile(r"<([^<>]+)>")
PLACEHOLDER_BINDINGS: dict[str, str] = {
    "approved_audio_sample": "MULLU_VOICE_PROBE_AUDIO",
    "gateway_url": "MULLU_GATEWAY_URL",
}
PLACEHOLDER_MANUAL_PARAMETERS: dict[str, str] = {
    "connector_id": "email_calendar_connector_id",
    "read_only_query": "email_calendar_read_only_query",
}


@dataclass(frozen=True, slots=True)
class EnvironmentReceiptState:
    """Presence projection from the redacted environment binding receipt."""

    present: bool
    ready: bool
    present_bindings: frozenset[str]
    receipt_errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LiveEvidenceQueueAction:
    """One classified live-evidence queue item."""

    queue_item_id: str
    source_action_id: str
    source_plan_type: str
    action_type: str
    blocker: str
    execution_class: str
    approval_required: bool
    required_bindings: tuple[str, ...]
    missing_bindings: tuple[str, ...]
    uncontracted_bindings: tuple[str, ...]
    manual_parameters: tuple[str, ...]
    execution_environment: dict[str, Any] | None
    blocked_reasons: tuple[str, ...]
    command: str
    evidence_required: tuple[str, ...]
    receipt_validator: str

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-ready queue action data."""
        payload = {
            "queue_item_id": self.queue_item_id,
            "source_action_id": self.source_action_id,
            "source_plan_type": self.source_plan_type,
            "action_type": self.action_type,
            "blocker": self.blocker,
            "execution_class": self.execution_class,
            "approval_required": self.approval_required,
            "required_bindings": list(self.required_bindings),
            "missing_bindings": list(self.missing_bindings),
            "uncontracted_bindings": list(self.uncontracted_bindings),
            "manual_parameters": list(self.manual_parameters),
            "blocked_reasons": list(self.blocked_reasons),
            "command": self.command,
            "evidence_required": list(self.evidence_required),
            "receipt_validator": self.receipt_validator,
        }
        if self.execution_environment is not None:
            payload["execution_environment"] = dict(self.execution_environment)
        return payload


@dataclass(frozen=True, slots=True)
class LiveEvidenceQueuePlan:
    """Classified queue for promotion live-evidence work."""

    schema_version: int
    queue_id: str
    generated_at: str
    source_plan_path: str
    environment_contract_path: str
    environment_binding_receipt_path: str
    ready_to_execute: bool
    action_count: int
    runnable_action_count: int
    blocked_action_count: int
    approval_required_action_count: int
    missing_binding_count: int
    missing_bindings: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    actions: tuple[LiveEvidenceQueueAction, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready queue output."""
        return {
            "schema_version": self.schema_version,
            "queue_id": self.queue_id,
            "generated_at": self.generated_at,
            "source_plan_path": self.source_plan_path,
            "environment_contract_path": self.environment_contract_path,
            "environment_binding_receipt_path": self.environment_binding_receipt_path,
            "ready_to_execute": self.ready_to_execute,
            "action_count": self.action_count,
            "runnable_action_count": self.runnable_action_count,
            "blocked_action_count": self.blocked_action_count,
            "approval_required_action_count": self.approval_required_action_count,
            "missing_binding_count": self.missing_binding_count,
            "missing_bindings": list(self.missing_bindings),
            "blocked_reasons": list(self.blocked_reasons),
            "actions": [action.as_dict() for action in self.actions],
            "metadata": dict(self.metadata),
        }


def plan_general_agent_promotion_live_evidence_queue(
    *,
    promotion_plan_path: Path = DEFAULT_PROMOTION_PLAN,
    environment_bindings_path: Path = DEFAULT_ENVIRONMENT_BINDINGS,
    environment_binding_receipt_path: Path = DEFAULT_ENVIRONMENT_BINDING_RECEIPT,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> LiveEvidenceQueuePlan:
    """Classify promotion closure actions into a live-evidence queue."""
    promotion_plan = _load_json_object(promotion_plan_path, "promotion closure plan")
    environment_contract = _load_json_object(environment_bindings_path, "environment binding contract")
    source_plan_hash = _stable_hash(promotion_plan)
    contract_bindings = _contract_binding_names(environment_contract)
    receipt_state = _environment_receipt_state(
        receipt_path=environment_binding_receipt_path,
        contract_path=environment_bindings_path,
    )
    actions = tuple(
        _queue_action(
            index=index,
            action=action,
            contract_bindings=contract_bindings,
            receipt_state=receipt_state,
        )
        for index, action in enumerate(_source_actions(promotion_plan), start=1)
    )
    missing_bindings = tuple(
        sorted(
            {
                binding
                for action in actions
                for binding in action.missing_bindings
            }
        )
    )
    blocked_reasons = tuple(
        sorted(
            {
                reason
                for action in actions
                for reason in action.blocked_reasons
            }
        )
    )
    runnable_count = sum(1 for action in actions if action.execution_class == "runnable_local")
    blocked_count = len(actions) - runnable_count
    queue_material = {
        "generated_at": generated_at,
        "source_plan_hash": source_plan_hash,
        "receipt_path": str(environment_binding_receipt_path),
        "actions": [action.as_dict() for action in actions],
    }
    queue_digest = _stable_hash(queue_material)
    return LiveEvidenceQueuePlan(
        schema_version=1,
        queue_id=f"general-agent-promotion-live-evidence-queue-{queue_digest[:16]}",
        generated_at=generated_at,
        source_plan_path=str(promotion_plan_path),
        environment_contract_path=str(environment_bindings_path),
        environment_binding_receipt_path=str(environment_binding_receipt_path),
        ready_to_execute=blocked_count == 0,
        action_count=len(actions),
        runnable_action_count=runnable_count,
        blocked_action_count=blocked_count,
        approval_required_action_count=sum(1 for action in actions if action.approval_required),
        missing_binding_count=len(missing_bindings),
        missing_bindings=missing_bindings,
        blocked_reasons=blocked_reasons,
        actions=actions,
        metadata={
            "queue_is_not_execution": True,
            "secret_values_serialized": False,
            "environment_receipt_present": receipt_state.present,
            "environment_receipt_ready": receipt_state.ready,
            "contract_binding_count": len(contract_bindings),
            "source_plan_id": str(promotion_plan.get("plan_id", "")),
            "source_plan_hash": source_plan_hash,
        },
    )


def write_general_agent_promotion_live_evidence_queue(
    queue: LiveEvidenceQueuePlan,
    output_path: Path,
) -> Path:
    """Write one deterministic live-evidence queue artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(queue.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_general_agent_promotion_live_evidence_queue(
    queue: LiveEvidenceQueuePlan | dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[str, ...]:
    """Validate one live-evidence queue artifact against its public schema."""
    schema = _load_schema(schema_path)
    payload = queue.as_dict() if isinstance(queue, LiveEvidenceQueuePlan) else queue
    return tuple(_validate_schema_instance(schema, payload))


def _queue_action(
    *,
    index: int,
    action: dict[str, Any],
    contract_bindings: frozenset[str],
    receipt_state: EnvironmentReceiptState,
) -> LiveEvidenceQueueAction:
    source_action_id = _field_text(action, "action_id", f"source-action-{index:02d}")
    source_plan_type = _source_plan_type(action)
    action_type = _field_text(action, "action_type", "manual-review")
    blocker = _field_text(action, "blocker", "unknown_blocker")
    command = _field_text(action, "command", "No command declared by source action.")
    required_bindings, manual_parameters = _required_bindings(action, source_plan_type, action_type, blocker, command)
    uncontracted_bindings = tuple(binding for binding in required_bindings if binding not in contract_bindings)
    missing_bindings = _missing_bindings(
        required_bindings=required_bindings,
        contract_bindings=contract_bindings,
        receipt_state=receipt_state,
    )
    execution_environment = _execution_environment(action)
    execution_environment_reasons = _execution_environment_blocked_reasons(execution_environment)
    blocked_reasons = _blocked_reasons(
        missing_bindings=missing_bindings,
        uncontracted_bindings=uncontracted_bindings,
        manual_parameters=manual_parameters,
        execution_environment_reasons=execution_environment_reasons,
        receipt_state=receipt_state,
    )
    approval_required = action.get("approval_required") is True
    execution_class = _execution_class(
        source_plan_type=source_plan_type,
        approval_required=approval_required,
        missing_bindings=missing_bindings,
        manual_parameters=manual_parameters,
        execution_environment_blocked=bool(execution_environment_reasons),
    )
    return LiveEvidenceQueueAction(
        queue_item_id=f"live-evidence-queue-item-{index:02d}-{_safe_id(source_action_id)}",
        source_action_id=source_action_id,
        source_plan_type=source_plan_type,
        action_type=action_type,
        blocker=blocker,
        execution_class=execution_class,
        approval_required=approval_required,
        required_bindings=required_bindings,
        missing_bindings=missing_bindings,
        uncontracted_bindings=uncontracted_bindings,
        manual_parameters=manual_parameters,
        execution_environment=execution_environment,
        blocked_reasons=blocked_reasons,
        command=command,
        evidence_required=_string_tuple(action.get("evidence_required", ())),
        receipt_validator=_field_text(action, "receipt_validator", "not_declared"),
    )


def _required_bindings(
    action: dict[str, Any],
    source_plan_type: str,
    action_type: str,
    blocker: str,
    command: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    required: list[str] = []
    manual: list[str] = []
    if action.get("approval_required") is True:
        required.append("MULLU_AUTHORITY_OPERATOR_SECRET")
    if blocker == "browser_live_evidence_missing" or "browser_live_receipt" in command:
        required.append("MULLU_BROWSER_SANDBOX_EVIDENCE")
    if blocker == "voice_live_evidence_missing" or "--target voice" in command:
        required.append("MULLU_VOICE_PROBE_AUDIO")
    if blocker.startswith("voice_dependency_missing:OPENAI_API_KEY"):
        required.append("OPENAI_API_KEY")
    if blocker.startswith("email_calendar_dependency_missing:"):
        required.append("EMAIL_CALENDAR_CONNECTOR_TOKEN")
    if blocker == "email_calendar_live_evidence_missing" or "--target email-calendar" in command:
        required.append("EMAIL_CALENDAR_CONNECTOR_TOKEN")
    if source_plan_type == "deployment":
        required.extend(_deployment_bindings(action_type, blocker))
    for placeholder in PLACEHOLDER_PATTERN.findall(command):
        placeholder_key = placeholder.strip()
        if placeholder_key in PLACEHOLDER_BINDINGS:
            required.append(PLACEHOLDER_BINDINGS[placeholder_key])
        elif placeholder_key in PLACEHOLDER_MANUAL_PARAMETERS:
            manual.append(PLACEHOLDER_MANUAL_PARAMETERS[placeholder_key])
        else:
            manual.append(placeholder_key)
    return tuple(dict.fromkeys(required)), tuple(dict.fromkeys(manual))


def _deployment_bindings(action_type: str, blocker: str) -> tuple[str, ...]:
    if action_type == "publish-witness" or blocker == "deployment_witness_not_published":
        return (
            "MULLU_GATEWAY_URL",
            "MULLU_RUNTIME_WITNESS_SECRET",
            "MULLU_RUNTIME_CONFORMANCE_SECRET",
            "MULLU_DEPLOYMENT_WITNESS_SECRET",
        )
    if action_type == "status-update" or blocker == "production_health_not_declared":
        return ("MULLU_GATEWAY_URL",)
    if action_type == "responsibility-debt-closure" or blocker.endswith("_responsibility_debt_present"):
        return ("MULLU_GATEWAY_URL",)
    return ()


def _missing_bindings(
    *,
    required_bindings: tuple[str, ...],
    contract_bindings: frozenset[str],
    receipt_state: EnvironmentReceiptState,
) -> tuple[str, ...]:
    missing: list[str] = []
    for binding in required_bindings:
        if binding not in contract_bindings:
            missing.append(binding)
            continue
        if not receipt_state.present or binding not in receipt_state.present_bindings:
            missing.append(binding)
    return tuple(dict.fromkeys(missing))


def _blocked_reasons(
    *,
    missing_bindings: tuple[str, ...],
    uncontracted_bindings: tuple[str, ...],
    manual_parameters: tuple[str, ...],
    execution_environment_reasons: tuple[str, ...],
    receipt_state: EnvironmentReceiptState,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if missing_bindings and not receipt_state.present:
        reasons.append("environment_binding_receipt_missing")
    reasons.extend(receipt_state.receipt_errors)
    reasons.extend(f"binding_not_in_environment_contract:{binding}" for binding in uncontracted_bindings)
    reasons.extend(f"environment_binding_missing:{binding}" for binding in missing_bindings)
    reasons.extend(f"manual_parameter_required:{parameter}" for parameter in manual_parameters)
    reasons.extend(execution_environment_reasons)
    return tuple(dict.fromkeys(reasons))


def _execution_class(
    *,
    source_plan_type: str,
    approval_required: bool,
    missing_bindings: tuple[str, ...],
    manual_parameters: tuple[str, ...],
    execution_environment_blocked: bool,
) -> str:
    environment_blocked = bool(missing_bindings or manual_parameters)
    if source_plan_type == "portfolio":
        return "approval_and_environment_blocked" if environment_blocked else "review_only"
    if approval_required and (environment_blocked or execution_environment_blocked):
        return "approval_and_environment_blocked"
    if approval_required:
        return "requires_approval"
    if execution_environment_blocked:
        return "requires_execution_environment"
    if environment_blocked:
        return "requires_environment_binding"
    return "runnable_local"


def _execution_environment(action: dict[str, Any]) -> dict[str, Any] | None:
    environment = action.get("execution_environment")
    if not isinstance(environment, dict):
        return None
    normalized: dict[str, Any] = {}
    for key in (
        "required_host_os",
        "current_host_os",
        "current_environment_ready",
        "blocker_if_unmet",
        "requirements",
    ):
        if key in environment:
            normalized[key] = environment[key]
    requirements = normalized.get("requirements")
    if isinstance(requirements, list):
        normalized["requirements"] = [str(requirement) for requirement in requirements if str(requirement).strip()]
    return normalized


def _execution_environment_blocked_reasons(
    execution_environment: dict[str, Any] | None,
) -> tuple[str, ...]:
    if execution_environment is None or execution_environment.get("current_environment_ready") is True:
        return ()
    blocker = str(execution_environment.get("blocker_if_unmet", "")).strip() or "execution_environment_not_ready"
    required_host = str(execution_environment.get("required_host_os", "")).strip()
    current_host = str(execution_environment.get("current_host_os", "")).strip()
    reasons = [f"execution_environment_unmet:{blocker}"]
    if required_host:
        reasons.append(f"execution_environment_required_host_os:{required_host}")
    if current_host:
        reasons.append(f"execution_environment_current_host_os:{current_host}")
    return tuple(dict.fromkeys(reasons))


def _environment_receipt_state(*, receipt_path: Path, contract_path: Path) -> EnvironmentReceiptState:
    if not receipt_path.exists():
        return EnvironmentReceiptState(
            present=False,
            ready=False,
            present_bindings=frozenset(),
            receipt_errors=(),
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return EnvironmentReceiptState(
            present=False,
            ready=False,
            present_bindings=frozenset(),
            receipt_errors=("environment_binding_receipt_invalid",),
        )
    if not isinstance(receipt, dict):
        return EnvironmentReceiptState(
            present=False,
            ready=False,
            present_bindings=frozenset(),
            receipt_errors=("environment_binding_receipt_invalid",),
        )
    receipt_validation = validate_general_agent_promotion_environment_binding_receipt(
        receipt_path=receipt_path,
        contract_path=contract_path,
        require_ready=False,
    )
    if not receipt_validation.valid:
        return EnvironmentReceiptState(
            present=True,
            ready=False,
            present_bindings=frozenset(),
            receipt_errors=tuple(
                f"environment_binding_receipt_invalid:{error}"
                for error in receipt_validation.errors
            ),
        )
    present_bindings = frozenset(
        str(binding.get("name", ""))
        for binding in receipt.get("bindings", ())
        if isinstance(binding, dict) and binding.get("present") is True
    )
    return EnvironmentReceiptState(
        present=True,
        ready=receipt.get("ready") is True,
        present_bindings=present_bindings,
        receipt_errors=(),
    )


def _source_actions(plan: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    actions = plan.get("actions", ())
    if not isinstance(actions, list):
        raise ValueError("promotion closure plan actions must be a list")
    return tuple(action for action in actions if isinstance(action, dict))


def _contract_binding_names(contract: dict[str, Any]) -> frozenset[str]:
    bindings = contract.get("bindings", ())
    if not isinstance(bindings, list):
        raise ValueError("environment binding contract bindings must be a list")
    return frozenset(str(binding.get("name", "")) for binding in bindings if isinstance(binding, dict))


def _source_plan_type(action: dict[str, Any]) -> str:
    observed = _field_text(action, "source_plan_type", "adapter")
    if observed in {"adapter", "deployment", "portfolio"}:
        return observed
    return "adapter"


def _field_text(action: dict[str, Any], field_name: str, fallback: str) -> str:
    value = str(action.get(field_name, "")).strip()
    return value or fallback


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _safe_id(value: str) -> str:
    normalized = "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")
    compact = "-".join(part for part in normalized.split("-") if part)
    return (compact or "unknown")[:72]


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse live-evidence queue planner arguments."""
    parser = argparse.ArgumentParser(description="Plan promotion live-evidence queue without executing effects.")
    parser.add_argument("--plan", default=str(DEFAULT_PROMOTION_PLAN))
    parser.add_argument("--environment-bindings", default=str(DEFAULT_ENVIRONMENT_BINDINGS))
    parser.add_argument("--environment-binding-receipt", default=str(DEFAULT_ENVIRONMENT_BINDING_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for live-evidence queue planning."""
    args = parse_args(argv)
    queue = plan_general_agent_promotion_live_evidence_queue(
        promotion_plan_path=Path(args.plan),
        environment_bindings_path=Path(args.environment_bindings),
        environment_binding_receipt_path=Path(args.environment_binding_receipt),
        generated_at=args.generated_at,
    )
    schema_errors = validate_general_agent_promotion_live_evidence_queue(queue, Path(args.schema))
    write_general_agent_promotion_live_evidence_queue(queue, Path(args.output))
    payload = queue.as_dict() | {"schema_valid": not schema_errors, "schema_errors": list(schema_errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif schema_errors:
        for error in schema_errors:
            print(f"error: {error}")
    else:
        print(
            "GENERAL AGENT PROMOTION LIVE EVIDENCE QUEUE WRITTEN "
            f"ready={queue.ready_to_execute} runnable={queue.runnable_action_count} blocked={queue.blocked_action_count}"
        )
    if schema_errors and args.strict:
        return 2
    if args.require_ready and not queue.ready_to_execute:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
