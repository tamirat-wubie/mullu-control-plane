#!/usr/bin/env python3
"""Emit missing operator inputs for general-agent live evidence.

Purpose: translate the general-agent promotion live evidence queue into a
public-safe operator input request without executing queued actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/general_agent_promotion_live_evidence_operator_input_request.schema.json
and .change_assurance/general_agent_promotion_live_evidence_queue.json.
Invariants:
  - The request contains input names, blocker names, and queue refs only.
  - Secret values, raw probe audio paths, connector query contents, and DNS
    target values are never serialized.
  - The request never authorizes execution; the queue remains the source of
    execution readiness.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_QUEUE = REPO_ROOT / ".change_assurance" / "general_agent_promotion_live_evidence_queue.json"
DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "general_agent_promotion_live_evidence_operator_input_request.schema.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "general_agent_promotion_live_evidence_operator_input_request.json"
)


@dataclass(frozen=True, slots=True)
class GeneralAgentLiveEvidenceOperatorInput:
    """One missing input derived from a live evidence queue item."""

    input_id: str
    blocker: str
    input_kind: str
    required_names: tuple[str, ...]
    current_state: str
    source_queue_item_ids: tuple[str, ...]
    evidence_source: str
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready input payload."""
        payload = asdict(self)
        payload["required_names"] = list(self.required_names)
        payload["source_queue_item_ids"] = list(self.source_queue_item_ids)
        return payload


@dataclass(frozen=True, slots=True)
class GeneralAgentLiveEvidenceOperatorInputRequest:
    """Public-safe operator input request for live evidence closure."""

    request_id: str
    queue_id: str
    ready_to_execute: bool
    execution_allowed: bool
    solver_outcome: str
    proof_state: str
    required_inputs: tuple[GeneralAgentLiveEvidenceOperatorInput, ...]
    blocked_actions: tuple[str, ...]
    source_artifacts: dict[str, str]
    no_secret_values_serialized: bool
    queue_is_not_execution: bool
    external_effect_performed: bool
    production_ready_claimed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready request payload."""
        return {
            "request_id": self.request_id,
            "queue_id": self.queue_id,
            "ready_to_execute": self.ready_to_execute,
            "execution_allowed": self.execution_allowed,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "required_inputs": [item.as_dict() for item in self.required_inputs],
            "blocked_actions": list(self.blocked_actions),
            "source_artifacts": dict(self.source_artifacts),
            "no_secret_values_serialized": self.no_secret_values_serialized,
            "queue_is_not_execution": self.queue_is_not_execution,
            "external_effect_performed": self.external_effect_performed,
            "production_ready_claimed": self.production_ready_claimed,
            "next_action": self.next_action,
        }


def emit_general_agent_live_evidence_operator_input_request(
    *,
    queue_path: Path = DEFAULT_QUEUE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> GeneralAgentLiveEvidenceOperatorInputRequest:
    """Build one public-safe operator input request from a live evidence queue."""
    queue = _load_json_object(queue_path, "general-agent live evidence queue")
    required_inputs = _derive_required_inputs(queue)
    ready_to_execute = queue.get("ready_to_execute") is True
    execution_allowed = ready_to_execute and not required_inputs
    request = GeneralAgentLiveEvidenceOperatorInputRequest(
        request_id=_request_id(queue, required_inputs, execution_allowed),
        queue_id=str(queue.get("queue_id", "")),
        ready_to_execute=ready_to_execute,
        execution_allowed=execution_allowed,
        solver_outcome="SolvedVerified" if execution_allowed else "AwaitingEvidence",
        proof_state="Pass" if execution_allowed else "Unknown",
        required_inputs=required_inputs,
        blocked_actions=_blocked_actions(queue),
        source_artifacts={
            "general_agent_promotion_live_evidence_queue": _path_label(queue_path)
        },
        no_secret_values_serialized=True,
        queue_is_not_execution=True,
        external_effect_performed=False,
        production_ready_claimed=False,
        next_action=_next_action(required_inputs, execution_allowed),
    )
    _validate_request_against_schema(request, schema_path)
    return request


def write_general_agent_live_evidence_operator_input_request(
    request: GeneralAgentLiveEvidenceOperatorInputRequest,
    output_path: Path,
) -> Path:
    """Write one operator input request JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(request.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _derive_required_inputs(
    queue: dict[str, Any],
) -> tuple[GeneralAgentLiveEvidenceOperatorInput, ...]:
    inputs: dict[tuple[str, str, str], GeneralAgentLiveEvidenceOperatorInput] = {}
    actions = queue.get("actions", [])
    if not isinstance(actions, list):
        return ()
    for action in actions:
        if not isinstance(action, dict):
            continue
        queue_item_id = str(action.get("queue_item_id", "")).strip()
        blocker = str(action.get("blocker", "")).strip() or "unknown_blocker"
        for binding_name in _string_items(action.get("missing_bindings", [])):
            _merge_input(
                inputs,
                blocker=blocker,
                input_kind="environment_binding",
                required_name=binding_name,
                current_state="missing",
                queue_item_id=queue_item_id,
                next_action=(
                    "bind this environment input outside the request without printing "
                    "or serializing its value, then rerun the environment binding receipt"
                ),
            )
        for parameter_name in _string_items(action.get("manual_parameters", [])):
            _merge_input(
                inputs,
                blocker=blocker,
                input_kind="manual_parameter",
                required_name=parameter_name,
                current_state="missing",
                queue_item_id=queue_item_id,
                next_action=(
                    "provide this bounded operator parameter outside the request, "
                    "then rerun the live evidence queue planner"
                ),
            )
        for reason in _string_items(action.get("blocked_reasons", [])):
            prefix = "dependency_action_requires_closure:"
            if not reason.startswith(prefix):
                continue
            _merge_input(
                inputs,
                blocker=blocker,
                input_kind="dependency_closure",
                required_name=reason.removeprefix(prefix),
                current_state="requires_dependency_closure",
                queue_item_id=queue_item_id,
                next_action="close the dependency action before rerunning this queue item",
            )
    return tuple(sorted(inputs.values(), key=lambda item: item.input_id))


def _merge_input(
    inputs: dict[tuple[str, str, str], GeneralAgentLiveEvidenceOperatorInput],
    *,
    blocker: str,
    input_kind: str,
    required_name: str,
    current_state: str,
    queue_item_id: str,
    next_action: str,
) -> None:
    key = (blocker, input_kind, required_name)
    existing = inputs.get(key)
    if existing is None:
        inputs[key] = GeneralAgentLiveEvidenceOperatorInput(
            input_id=_input_id(blocker, input_kind, required_name),
            blocker=blocker,
            input_kind=input_kind,
            required_names=(required_name,),
            current_state=current_state,
            source_queue_item_ids=(queue_item_id,),
            evidence_source="general_agent_promotion_live_evidence_queue",
            next_action=next_action,
        )
        return
    queue_item_ids = tuple(
        sorted({*existing.source_queue_item_ids, queue_item_id})
    )
    inputs[key] = GeneralAgentLiveEvidenceOperatorInput(
        input_id=existing.input_id,
        blocker=existing.blocker,
        input_kind=existing.input_kind,
        required_names=existing.required_names,
        current_state=existing.current_state,
        source_queue_item_ids=queue_item_ids,
        evidence_source=existing.evidence_source,
        next_action=existing.next_action,
    )


def _blocked_actions(queue: dict[str, Any]) -> tuple[str, ...]:
    actions = queue.get("actions", [])
    if not isinstance(actions, list):
        return ()
    blocked = {
        str(action.get("source_action_id", "")).strip()
        for action in actions
        if isinstance(action, dict)
        and str(action.get("execution_class", "")).strip() != "runnable_local"
        and str(action.get("source_action_id", "")).strip()
    }
    return tuple(sorted(blocked))


def _request_id(
    queue: dict[str, Any],
    required_inputs: tuple[GeneralAgentLiveEvidenceOperatorInput, ...],
    execution_allowed: bool,
) -> str:
    material = {
        "execution_allowed": execution_allowed,
        "inputs": [item.as_dict() for item in required_inputs],
        "queue_id": queue.get("queue_id", ""),
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"general-agent-promotion-live-evidence-operator-input-request-{digest[:16]}"


def _input_id(blocker: str, input_kind: str, required_name: str) -> str:
    material = f"{blocker}:{input_kind}:{required_name}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"general-agent-live-evidence-input-{digest[:12]}"


def _next_action(
    required_inputs: tuple[GeneralAgentLiveEvidenceOperatorInput, ...],
    execution_allowed: bool,
) -> str:
    if execution_allowed:
        return "rerun the general-agent promotion live evidence queue with execution authority"
    if any(item.input_kind == "environment_binding" for item in required_inputs):
        return "bind missing environment inputs, emit the redacted binding receipt, then rerun the live evidence queue"
    if any(item.input_kind == "manual_parameter" for item in required_inputs):
        return "provide missing manual parameters, then rerun the live evidence queue"
    if any(item.input_kind == "dependency_closure" for item in required_inputs):
        return "close dependency actions, then rerun the live evidence queue"
    return "inspect the live evidence queue blockers"


def _validate_request_against_schema(
    request: GeneralAgentLiveEvidenceOperatorInputRequest,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, request.as_dict())
    if errors:
        raise ValueError("general-agent live evidence operator input request schema errors: " + "; ".join(errors))


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _string_items(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse operator input request emission arguments."""
    parser = argparse.ArgumentParser(
        description="Emit general-agent live evidence operator input request."
    )
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator input request emission."""
    args = parse_args(argv)
    request = emit_general_agent_live_evidence_operator_input_request(
        queue_path=Path(args.queue),
        schema_path=Path(args.schema),
    )
    write_general_agent_live_evidence_operator_input_request(request, Path(args.output))
    if args.json:
        print(json.dumps(request.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
