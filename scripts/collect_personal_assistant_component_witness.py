#!/usr/bin/env python3
"""Collect a personal-assistant component witness receipt.

Purpose: project local component graph, bundle compilation, and lifecycle
transition evidence into one no-effect personal-assistant witness receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: checked-in component graph, bundle compilation, lifecycle receipt
examples, and JSON output.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The receipt is not execution authority and is not terminal closure.
  - Secret values and raw private connector payloads are never serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH = REPO_ROOT / "examples" / "component_graph.foundation.json"
DEFAULT_BUNDLE = REPO_ROOT / "examples" / "component_bundle_compilation.personal_assistant_v0.json"
DEFAULT_LIFECYCLE = REPO_ROOT / "examples" / "component_lifecycle_transition_receipts.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_component_witness_receipt.json"

COMPONENT_ID = "personal_assistant"
BUNDLE_ID = "personal_assistant_v0"
GMAIL_GATE_COMPONENT_ID = "gmail_account_binding_gate"
NO_EFFECT_FLAGS = (
    "live_execution_enabled",
    "live_connector_send_enabled",
    "can_execute",
    "can_mutate",
    "can_call_connector",
    "can_claim_terminal_closure",
)
PRIVATE_ACTIONS = (
    "connector_call",
    "external_send",
    "mailbox_mutation",
    "send_email",
    "provider_write",
    "account_binding_claim",
)
FORBIDDEN_CLAIMS = (
    "production_ready",
    "customer_ready",
    "live_gmail_enabled",
    "autonomous_execution",
    "compliance_certified",
    "enterprise_sla",
    "nested_mind_live",
)


def collect_personal_assistant_component_witness(
    *,
    graph_path: Path = DEFAULT_GRAPH,
    bundle_path: Path = DEFAULT_BUNDLE,
    lifecycle_path: Path = DEFAULT_LIFECYCLE,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one local no-effect personal-assistant component witness."""
    graph = _read_json_object(graph_path, "component graph")
    bundle = _read_json_object(bundle_path, "component bundle compilation")
    lifecycle = _read_json_object(lifecycle_path, "component lifecycle transition receipts")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    node = _find_by_key(_list_of_objects(graph.get("nodes")), "component_id", COMPONENT_ID)
    membership = _find_bundle_membership(graph, component_id=COMPONENT_ID, bundle_id=BUNDLE_ID)
    inbox_simulation = _find_simulation(bundle, "inbox_readiness_probe")
    send_email_simulation = _find_simulation(bundle, "send_email_request")
    lifecycle_receipt = _find_lifecycle_receipt(lifecycle, COMPONENT_ID)

    component_witness = {
        "component_present": bool(node),
        "mode": _bounded_text(node.get("mode"), fallback="missing"),
        "state": _bounded_text(node.get("state"), fallback="missing"),
        "authority_level": _bounded_text(node.get("authority_level"), fallback="missing"),
        "proof_binding_state": _bounded_text(node.get("proof_binding_state"), fallback="missing"),
        "route_binding_state": _bounded_text(node.get("route_binding_state"), fallback="missing"),
        "bundle_membership_is_not_execution_authority": membership.get(
            "membership_is_not_execution_authority"
        )
        is True,
    }
    request_path_witness = {
        "inbox_probe_path_bound": _request_path_exists(
            graph,
            from_component_id="governance_core",
            to_component_id=COMPONENT_ID,
            scenario_ref="inbox_readiness_probe",
        )
        and _request_path_exists(
            graph,
            from_component_id=COMPONENT_ID,
            to_component_id=GMAIL_GATE_COMPONENT_ID,
            scenario_ref="inbox_readiness_probe",
        ),
        "send_email_path_blocked": send_email_simulation.get("outcome") == "GovernanceBlocked",
        "gmail_gate_required": GMAIL_GATE_COMPONENT_ID
        in _string_list(inbox_simulation.get("selected_component_ids")),
        "approval_required": inbox_simulation.get("approval_required") is True,
        "inbox_probe_outcome": _bounded_text(inbox_simulation.get("outcome"), fallback="missing"),
        "send_email_outcome": _bounded_text(send_email_simulation.get("outcome"), fallback="missing"),
        "blocked_actions": sorted(
            set(_string_list(inbox_simulation.get("blocked_actions")))
            | set(_string_list(send_email_simulation.get("blocked_actions")))
        ),
    }
    lifecycle_witness = {
        "receipt_id": _bounded_text(lifecycle_receipt.get("receipt_id"), fallback="missing"),
        "from_state": _bounded_text(lifecycle_receipt.get("from_state"), fallback="missing"),
        "to_state": _bounded_text(lifecycle_receipt.get("to_state"), fallback="missing"),
        "authority_level": _bounded_text(lifecycle_receipt.get("authority_level"), fallback="missing"),
        "external_effect": lifecycle_receipt.get("external_effect") is True,
        "operator_approval_required": lifecycle_receipt.get("operator_approval_required") is True,
        "receipt_is_not_execution_authority": lifecycle_receipt.get("receipt_is_not_execution_authority")
        is True,
        "receipt_is_not_terminal_closure": lifecycle_receipt.get("receipt_is_not_terminal_closure")
        is True,
    }
    effect_boundary = {
        "live_execution_enabled": bundle.get("live_execution_enabled") is True,
        "live_connector_send_enabled": bundle.get("live_connector_send_enabled") is True,
        "can_execute": bundle.get("can_execute") is True,
        "can_mutate": bundle.get("can_mutate") is True,
        "can_call_connector": bundle.get("can_call_connector") is True,
        "can_claim_terminal_closure": bundle.get("can_claim_terminal_closure") is True,
        "can_send_external_message": False,
        "can_write_files": False,
        "secret_values_serialized": False,
        "raw_private_connector_payloads_serialized": False,
    }

    component_verified = _component_verified(component_witness)
    request_path_verified = _request_path_verified(request_path_witness)
    lifecycle_verified = _lifecycle_verified(lifecycle_witness)
    no_effect_boundary_verified = not any(effect_boundary[flag] for flag in effect_boundary)
    witness_closed = (
        component_verified
        and request_path_verified
        and lifecycle_verified
        and no_effect_boundary_verified
        and all(claim in _string_list(bundle.get("forbidden_claims")) for claim in FORBIDDEN_CLAIMS)
    )
    proof_state = "Pass" if witness_closed else "Fail"
    solver_outcome = "SolvedVerified" if witness_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.component_witness_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "component_id": COMPONENT_ID,
        "bundle_id": BUNDLE_ID,
        "evidence_refs": {
            "component_graph": _path_label(graph_path),
            "component_bundle_compilation": _path_label(bundle_path),
            "component_lifecycle_transition_receipts": _path_label(lifecycle_path),
        },
        "component_witness": component_witness,
        "request_path_witness": request_path_witness,
        "lifecycle_witness": lifecycle_witness,
        "effect_boundary": effect_boundary,
        "summary": {
            "component_witness_verified": component_verified,
            "request_path_witness_verified": request_path_verified,
            "lifecycle_witness_verified": lifecycle_verified,
            "no_effect_boundary_verified": no_effect_boundary_verified,
            "witness_closed": witness_closed,
        },
        "forbidden_claims_preserved": list(FORBIDDEN_CLAIMS),
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-component-witness-{generated_at[:10]}",
                    "reason": _lineage_reason(witness_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {
        "receipt_id": _receipt_id(receipt_without_id),
        **receipt_without_id,
    }


def write_personal_assistant_component_witness_receipt(
    receipt: Mapping[str, object],
    output_path: Path,
) -> Path:
    """Write one personal-assistant component witness receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _component_verified(component_witness: Mapping[str, object]) -> bool:
    return (
        component_witness.get("component_present") is True
        and component_witness.get("mode") == "draft_only"
        and component_witness.get("state") == "draft_only"
        and component_witness.get("authority_level") == "draft_only"
        and component_witness.get("proof_binding_state") == "proof_bound"
        and component_witness.get("route_binding_state") == "bound"
        and component_witness.get("bundle_membership_is_not_execution_authority") is True
    )


def _request_path_verified(request_path_witness: Mapping[str, object]) -> bool:
    blocked_actions = set(_string_list(request_path_witness.get("blocked_actions")))
    return (
        request_path_witness.get("inbox_probe_path_bound") is True
        and request_path_witness.get("send_email_path_blocked") is True
        and request_path_witness.get("gmail_gate_required") is True
        and request_path_witness.get("approval_required") is True
        and request_path_witness.get("inbox_probe_outcome") == "AwaitingEvidence"
        and request_path_witness.get("send_email_outcome") == "GovernanceBlocked"
        and all(action in blocked_actions for action in PRIVATE_ACTIONS)
    )


def _lifecycle_verified(lifecycle_witness: Mapping[str, object]) -> bool:
    return (
        lifecycle_witness.get("from_state") == "mounted"
        and lifecycle_witness.get("to_state") == "draft_only"
        and lifecycle_witness.get("authority_level") == "draft_only"
        and lifecycle_witness.get("external_effect") is False
        and lifecycle_witness.get("operator_approval_required") is False
        and lifecycle_witness.get("receipt_is_not_execution_authority") is True
        and lifecycle_witness.get("receipt_is_not_terminal_closure") is True
    )


def _find_bundle_membership(
    graph: Mapping[str, Any],
    *,
    component_id: str,
    bundle_id: str,
) -> Mapping[str, Any]:
    for membership in _list_of_objects(graph.get("bundle_memberships")):
        if membership.get("component_id") == component_id and membership.get("bundle_id") == bundle_id:
            return membership
    return {}


def _find_simulation(bundle: Mapping[str, Any], intent: str) -> Mapping[str, Any]:
    for simulation in _list_of_objects(bundle.get("matching_simulations")):
        if simulation.get("intent") == intent:
            return simulation
    return {}


def _find_lifecycle_receipt(lifecycle: Mapping[str, Any], component_id: str) -> Mapping[str, Any]:
    for receipt in _list_of_objects(lifecycle.get("transition_receipts")):
        if receipt.get("component_id") == component_id:
            return receipt
    return {}


def _request_path_exists(
    graph: Mapping[str, Any],
    *,
    from_component_id: str,
    to_component_id: str,
    scenario_ref: str,
) -> bool:
    for edge in _list_of_objects(graph.get("edges")):
        if (
            edge.get("from_component_id") == from_component_id
            and edge.get("to_component_id") == to_component_id
            and edge.get("relation") == "request_path_next"
            and edge.get("edge_is_not_execution_authority") is True
            and scenario_ref in _string_list(edge.get("scenario_refs"))
        ):
            return True
    return False


def _find_by_key(items: tuple[Mapping[str, Any], ...], key: str, value: str) -> Mapping[str, Any]:
    for item in items:
        if item.get(key) == value:
            return item
    return {}


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to read {label}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return parsed


def _list_of_objects(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _bounded_text(value: object, *, fallback: str) -> str:
    return value[:180] if isinstance(value, str) and value else fallback


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _receipt_id(receipt_without_id: Mapping[str, object]) -> str:
    material = json.dumps(
        receipt_without_id,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"personal-assistant-component-witness-{hashlib.sha256(material).hexdigest()[:16]}"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _lineage_reason(witness_closed: bool) -> str:
    if witness_closed:
        return "Recorded local component evidence that Personal Assistant remains draft-only and no-effect."
    return "Recorded local component evidence and preserved AwaitingEvidence because the witness did not close."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse personal-assistant component witness collection arguments."""
    parser = argparse.ArgumentParser(description="Collect personal-assistant component witness evidence.")
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--lifecycle", default=str(DEFAULT_LIFECYCLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """CLI entry point for personal-assistant component witness collection."""
    args = parse_args(argv)
    receipt = collect_personal_assistant_component_witness(
        graph_path=Path(args.graph),
        bundle_path=Path(args.bundle),
        lifecycle_path=Path(args.lifecycle),
        now_utc=now_utc,
    )
    write_personal_assistant_component_witness_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"personal-assistant component witness outcome: {receipt['solver_outcome']}")
    return 0 if receipt["solver_outcome"] == "SolvedVerified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
