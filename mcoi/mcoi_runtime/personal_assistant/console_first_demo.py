"""Purpose: bind the first usable demo packet into the console read model.

Governance scope: read-only console composition, no-effect authority preservation,
and customer-readiness claim separation.
Dependencies: personal_assistant.console, examples/first_usable_demo_packet.json,
and examples/personal_assistant_invoice_email_walkthrough.json.
Invariants: this module reads local fixtures only; it does not execute skills,
call connectors, dispatch workers, write memory, mutate deployments, send email,
create provider drafts, move money, or claim customer readiness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .approval import PersonalAssistantApprovalQueue
from .console import build_personal_assistant_console_read_model as _build_base_console_read_model
from .contracts import PersonalAssistantInvariantError
from .memory import PersonalAssistantMemoryObservationLedger
from .skill_registry import PersonalAssistantSkillRegistry

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIRST_USABLE_DEMO_PACKET = _REPO_ROOT / "examples" / "first_usable_demo_packet.json"
_INVOICE_EMAIL_WALKTHROUGH = _REPO_ROOT / "examples" / "personal_assistant_invoice_email_walkthrough.json"
_REQUIRED_FALSE_AUTHORITY_FIELDS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_send_allowed",
    "money_movement_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "customer_readiness_claim_allowed",
    "public_launch_claim_allowed",
    "approval_is_execution",
)
_REQUIRED_FALSE_WALKTHROUGH_EFFECT_FIELDS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "mailbox_read_allowed",
    "mailbox_mutation_allowed",
    "external_send_allowed",
    "provider_draft_creation_allowed",
    "invoice_payment_allowed",
    "money_movement_allowed",
    "connector_mutation_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "customer_readiness_claim_allowed",
    "public_launch_claim_allowed",
)
_REQUIRED_FALSE_WALKTHROUGH_CLAIM_FIELDS = (
    "draft_preview_is_send_authority",
    "approval_review_is_execution",
    "invoice_context_is_payment_authority",
    "console_visibility_is_customer_readiness",
)
_REQUIRED_ACTIONS_NOT_TAKEN = (
    "email_not_sent",
    "provider_draft_not_created",
    "connector_state_not_mutated",
    "invoice_not_paid",
    "memory_not_written",
    "deployment_not_mutated",
    "customer_readiness_not_claimed",
)


def build_personal_assistant_console_read_model(
    *,
    generated_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
    approval_queue: PersonalAssistantApprovalQueue | None = None,
    memory_ledger: PersonalAssistantMemoryObservationLedger | None = None,
    recent_requests: Sequence[Mapping[str, Any]] = (),
    task_items: Sequence[Mapping[str, Any]] = (),
    receipts: Sequence[Mapping[str, Any]] = (),
    teamops_plans: Sequence[Mapping[str, Any]] = (),
    approval_proposals: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build the console read model with the first usable demo section bound."""
    payload = _build_base_console_read_model(
        generated_at=generated_at,
        registry=registry,
        approval_queue=approval_queue,
        memory_ledger=memory_ledger,
        recent_requests=recent_requests,
        task_items=task_items,
        receipts=receipts,
        teamops_plans=teamops_plans,
        approval_proposals=approval_proposals,
    )
    first_demo = _build_first_usable_demo_read_model(generated_at=generated_at)
    sections = dict(_mapping(payload.get("sections")))
    sections["first_usable_demo"] = {
        "item_count": 1,
        "walkthrough_count": first_demo["walkthroughs"]["item_count"],
        "draft_only_walkthrough_bound": first_demo["walkthroughs"]["draft_only_walkthrough_bound"],
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "external_send_allowed": False,
        "customer_readiness_claim_allowed": False,
        "source_packet_id": first_demo["source_packet_id"],
        "read_model_id": first_demo["read_model_id"],
    }
    evidence_refs = list(payload.get("evidence_refs", ())) if isinstance(payload.get("evidence_refs"), list) else []
    for evidence_ref in (
        "examples/first_usable_demo_packet.json",
        "examples/personal_assistant_invoice_email_walkthrough.json",
        "mcoi/mcoi_runtime/personal_assistant/console_first_demo.py",
    ):
        if evidence_ref not in evidence_refs:
            evidence_refs.append(evidence_ref)
    return {
        **payload,
        "sections": sections,
        "first_usable_demo": first_demo,
        "first_usable_demo_binding": {
            "binding_id": "personal_assistant_console_first_usable_demo_binding_v1",
            "binding_state": "bound_to_existing_console_route",
            "source_console_id": str(payload.get("console_id", "")),
            "source_first_demo_read_model_id": first_demo["read_model_id"],
            "source_packet_id": first_demo["source_packet_id"],
            "read_only": True,
            "fixture_backed": True,
            "governed": True,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "external_send_allowed": False,
            "connector_mutation_allowed": False,
            "memory_write_allowed": False,
            "deployment_mutation_allowed": False,
            "customer_readiness_claim_allowed": False,
            "next_action": "review_bound_route_read_model_before_any_live_connector_promotion",
        },
        "evidence_refs": evidence_refs,
    }


def _build_first_usable_demo_read_model(*, generated_at: str) -> dict[str, Any]:
    packet = _load_json(_FIRST_USABLE_DEMO_PACKET, label="first usable demo packet")
    authority = _mapping(packet.get("current_authority"))
    missing_false = [field for field in _REQUIRED_FALSE_AUTHORITY_FIELDS if authority.get(field) is not False]
    if missing_false:
        raise PersonalAssistantInvariantError(
            "first usable demo authority fields must remain false: " + ", ".join(missing_false)
        )
    claim_boundary = _mapping(packet.get("claim_boundary"))
    for field in (
        "deployment_health_evidence_is_customer_readiness",
        "public_health_endpoint_is_live_assistant_authority",
        "foundation_demo_is_paid_use_ready",
        "readiness_packet_is_legal_or_business_clearance",
    ):
        if claim_boundary.get(field) is not False:
            raise PersonalAssistantInvariantError(f"first usable demo claim boundary drift: {field}")
    lane = _sequence_of_mappings(packet.get("first_demo_lane"))
    user_story = _mapping(packet.get("canonical_user_story"))
    invoice_walkthrough = _build_invoice_email_walkthrough_read_model(generated_at=generated_at)
    evidence_refs = list(
        dict.fromkeys(
            (
                *(str(step.get("evidence_ref", "")) for step in lane if str(step.get("evidence_ref", ""))),
                "examples/personal_assistant_invoice_email_walkthrough.json",
                *invoice_walkthrough["evidence_refs"],
            )
        )
    )
    return {
        "read_model_id": "first_usable_demo_operator_read_model_v1",
        "source_packet_ref": "examples/first_usable_demo_packet.json",
        "source_packet_id": str(packet.get("packet_id", "")),
        "product_name": str(packet.get("product_name", "")),
        "control_surface": str(packet.get("control_surface", "")),
        "demo_name": str(packet.get("demo_name", "")),
        "generated_at": generated_at,
        "governed": True,
        "read_only": True,
        "fixture_backed": True,
        "foundation_only": True,
        "solver_outcome": "SolvedVerified",
        "operator_visible_status": "reviewable_no_effect_demo_packet",
        "demo_goal": str(packet.get("demo_goal", "")),
        "canonical_user_story": dict(user_story),
        "first_demo_lane": lane,
        "walkthroughs": {
            "item_count": 1,
            "draft_only_walkthrough_bound": True,
            "invoice_email_walkthrough_id": invoice_walkthrough["walkthrough_id"],
            "external_send_allowed": False,
            "provider_draft_creation_allowed": False,
            "invoice_payment_allowed": False,
            "customer_readiness_claim_allowed": False,
        },
        "invoice_email_walkthrough": invoice_walkthrough,
        "promotion_gates": _sequence_of_mappings(packet.get("promotion_gates")),
        "readiness_index": _mapping(packet.get("readiness_index")),
        "claim_boundary": dict(claim_boundary),
        "effect_boundary": dict(authority),
        "actions_not_taken": [str(item) for item in user_story.get("explicit_non_goals", ())],
        "evidence_refs": evidence_refs,
        "next_safe_actions": [str(item) for item in packet.get("next_safe_actions", ())],
        "assurance": {
            "assurance_id": "first_usable_demo_console_route_no_effect_assurance",
            "packet_valid": True,
            "invoice_email_walkthrough_valid": True,
            "authority_drift_detected": False,
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "live_connector_execution_allowed": False,
            "customer_readiness_claim_allowed": False,
            "next_action": "review_bound_route_read_model_before_any_live_connector_promotion",
        },
    }


def _build_invoice_email_walkthrough_read_model(*, generated_at: str) -> dict[str, Any]:
    payload = _load_json(_INVOICE_EMAIL_WALKTHROUGH, label="invoice email walkthrough")
    effect_boundary = _mapping(payload.get("effect_boundary"))
    claim_boundary = _mapping(payload.get("claim_boundary"))
    for field in _REQUIRED_FALSE_WALKTHROUGH_EFFECT_FIELDS:
        if effect_boundary.get(field) is not False:
            raise PersonalAssistantInvariantError(f"invoice email walkthrough effect drift: {field}")
    for field in _REQUIRED_FALSE_WALKTHROUGH_CLAIM_FIELDS:
        if claim_boundary.get(field) is not False:
            raise PersonalAssistantInvariantError(f"invoice email walkthrough claim drift: {field}")
    draft_projection = _mapping(payload.get("draft_projection"))
    for field in (
        "execution_allowed",
        "external_send_allowed",
        "mailbox_mutation_allowed",
        "connector_mutation_allowed",
        "provider_draft_creation_allowed",
    ):
        if draft_projection.get(field) is not False:
            raise PersonalAssistantInvariantError(f"invoice email draft projection drift: {field}")
    if draft_projection.get("approval_required_before_send") is not True:
        raise PersonalAssistantInvariantError("invoice email draft projection must require approval before send")
    approval_review = _mapping(payload.get("approval_review"))
    if approval_review.get("approval_required") is not True:
        raise PersonalAssistantInvariantError("invoice email walkthrough approval must be required")
    if approval_review.get("approval_is_execution") is not False:
        raise PersonalAssistantInvariantError("invoice email walkthrough approval must not execute")
    receipt_projection = _mapping(payload.get("receipt_projection"))
    actions_not_taken = set(_sequence_of_text(receipt_projection.get("actions_not_taken")))
    missing_actions_not_taken = sorted(set(_REQUIRED_ACTIONS_NOT_TAKEN) - actions_not_taken)
    if missing_actions_not_taken:
        raise PersonalAssistantInvariantError(
            "invoice email walkthrough missing actions_not_taken: " + ", ".join(missing_actions_not_taken)
        )
    input_projection = _mapping(payload.get("input_projection"))
    return {
        "read_model_id": "invoice_email_draft_walkthrough_read_model_v1",
        "source_walkthrough_ref": "examples/personal_assistant_invoice_email_walkthrough.json",
        "walkthrough_id": str(payload.get("walkthrough_id", "")),
        "source_demo_packet_id": str(payload.get("source_demo_packet_id", "")),
        "generated_at": generated_at,
        "governed": True,
        "read_only": True,
        "fixture_backed": True,
        "foundation_only": True,
        "operator_request": str(payload.get("operator_request", "")),
        "input_projection": dict(input_projection),
        "draft_projection": dict(draft_projection),
        "approval_review": dict(approval_review),
        "receipt_projection": dict(receipt_projection),
        "effect_boundary": dict(effect_boundary),
        "claim_boundary": dict(claim_boundary),
        "evidence_refs": _sequence_of_text(payload.get("evidence_refs")),
        "next_safe_actions": _sequence_of_text(payload.get("next_safe_actions")),
        "assurance": {
            "assurance_id": "invoice_email_draft_walkthrough_console_panel_assurance",
            "walkthrough_valid": True,
            "draft_preview_only": True,
            "approval_required_before_send": True,
            "raw_private_payload_serialized": False,
            "provider_draft_creation_allowed": False,
            "external_send_allowed": False,
            "invoice_payment_allowed": False,
            "customer_readiness_claim_allowed": False,
        },
    }


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PersonalAssistantInvariantError(f"{label} is missing") from exc
    except json.JSONDecodeError as exc:
        raise PersonalAssistantInvariantError(f"{label} is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise PersonalAssistantInvariantError(f"{label} must be a mapping")
    return payload


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _sequence_of_text(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
