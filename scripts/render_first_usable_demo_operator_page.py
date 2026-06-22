#!/usr/bin/env python3
"""Render a read-only operator page for the First Usable Demo Packet.

Purpose: turn the machine-readable first usable demo packet into an operator-facing
read model and static HTML page without creating any live assistant authority.
Governance scope: product compression, read-only operator visibility, no-effect
claims, promotion gate clarity, and customer-readiness separation.
Invariants:
  - Rendering never calls connectors, sends messages, moves money, writes memory,
    mutates deployments, creates drafts in providers, or opens runtime authority.
  - All effect-bearing authority fields remain false.
  - The output is deterministic when generated_at is supplied.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from html import escape
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.validate_first_usable_demo_packet import (
    DEFAULT_PACKET,
    validate_first_usable_demo_packet,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_READ_MODEL_OUTPUT = REPO_ROOT / ".change_assurance" / "first_usable_demo_operator_read_model.json"
DEFAULT_HTML_OUTPUT = REPO_ROOT / ".change_assurance" / "first_usable_demo_operator_page.html"
REQUIRED_FALSE_AUTHORITY_FIELDS = (
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
REQUIRED_FALSE_CLAIM_FIELDS = (
    "deployment_health_evidence_is_customer_readiness",
    "public_health_endpoint_is_live_assistant_authority",
    "foundation_demo_is_paid_use_ready",
    "readiness_packet_is_legal_or_business_clearance",
)


@dataclass(frozen=True, slots=True)
class FirstUsableDemoOperatorRender:
    """Rendered operator read-model and HTML page."""

    read_model: dict[str, Any]
    html: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_first_usable_demo_packet(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    """Load the first usable demo packet as a JSON object."""
    payload = json.loads(packet_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("first usable demo packet must be a JSON object")
    return payload


def build_first_usable_demo_operator_read_model(
    packet: Mapping[str, Any],
    *,
    packet_path: Path = DEFAULT_PACKET,
    generated_at: str = "",
) -> dict[str, Any]:
    """Build a no-effect operator-facing read model from the packet."""
    validation = validate_first_usable_demo_packet(packet_path=packet_path)
    if not validation.valid:
        raise ValueError("first usable demo packet failed validation: " + "; ".join(validation.errors))

    current_authority = _mapping(packet.get("current_authority"))
    claim_boundary = _mapping(packet.get("claim_boundary"))
    effect_boundary_errors = _false_field_errors(current_authority, REQUIRED_FALSE_AUTHORITY_FIELDS, "current_authority")
    effect_boundary_errors.extend(_false_field_errors(claim_boundary, REQUIRED_FALSE_CLAIM_FIELDS, "claim_boundary"))
    if effect_boundary_errors:
        raise ValueError("first usable demo packet authority drift: " + "; ".join(effect_boundary_errors))

    user_story = _mapping(packet.get("canonical_user_story"))
    first_demo_lane = _list_of_mappings(packet.get("first_demo_lane"))
    promotion_gates = _list_of_mappings(packet.get("promotion_gates"))
    readiness_index = _mapping(packet.get("readiness_index"))
    actions_not_taken = [str(item) for item in user_story.get("explicit_non_goals", [])]
    next_safe_actions = [str(item) for item in packet.get("next_safe_actions", [])]
    evidence_refs = tuple(
        dict.fromkeys(
            str(step.get("evidence_ref", ""))
            for step in first_demo_lane
            if str(step.get("evidence_ref", "")).strip()
        )
    )
    operator_questions = _operator_questions(packet, actions_not_taken, next_safe_actions)
    return {
        "read_model_id": "first_usable_demo_operator_read_model_v1",
        "source_packet_ref": _path_label(packet_path),
        "source_packet_id": str(packet.get("packet_id", "")),
        "product_name": str(packet.get("product_name", "")),
        "control_surface": str(packet.get("control_surface", "")),
        "demo_name": str(packet.get("demo_name", "")),
        "generated_at": generated_at,
        "governed": True,
        "read_only": True,
        "fixture_backed": True,
        "foundation_only": True,
        "solver_outcome": str(packet.get("solver_outcome", "AwaitingEvidence")),
        "operator_visible_status": "reviewable_no_effect_demo_packet",
        "demo_goal": str(packet.get("demo_goal", "")),
        "canonical_user_story": dict(user_story),
        "operator_questions": operator_questions,
        "first_demo_lane": [dict(step) for step in first_demo_lane],
        "promotion_gates": [dict(gate) for gate in promotion_gates],
        "readiness_index": dict(readiness_index),
        "claim_boundary": dict(claim_boundary),
        "effect_boundary": dict(current_authority),
        "actions_not_taken": actions_not_taken,
        "evidence_refs": list(evidence_refs),
        "constructive_deltas": [str(item) for item in packet.get("constructive_deltas", [])],
        "fracture_deltas": [str(item) for item in packet.get("fracture_deltas", [])],
        "next_safe_actions": next_safe_actions,
        "assurance": {
            "assurance_id": "first_usable_demo_operator_page_no_effect_assurance",
            "validation_outcome": validation.solver_outcome,
            "packet_valid": validation.valid,
            "authority_drift_detected": False,
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "live_connector_execution_allowed": False,
            "customer_readiness_claim_allowed": False,
            "next_action": next_safe_actions[0] if next_safe_actions else "review_demo_packet",
        },
    }


def render_first_usable_demo_operator_html(read_model: Mapping[str, Any]) -> str:
    """Render a static operator page from a first usable demo read model."""
    title = str(read_model.get("demo_name", "First Usable Demo"))
    status = str(read_model.get("operator_visible_status", "reviewable_no_effect_demo_packet"))
    questions = _html_list(
        f"{item.get('question', '')}: {item.get('answer', '')}"
        for item in _list_of_mappings(read_model.get("operator_questions"))
    )
    lane_rows = "".join(
        "<tr>"
        f"<td>{escape(str(step.get('step_id', '')))}</td>"
        f"<td>{escape(str(step.get('surface', '')))}</td>"
        f"<td>{escape(str(step.get('expected_output', '')))}</td>"
        f"<td>{escape(str(step.get('authority', '')))}</td>"
        "</tr>"
        for step in _list_of_mappings(read_model.get("first_demo_lane"))
    )
    effect_boundary = _mapping(read_model.get("effect_boundary"))
    false_authority = all(effect_boundary.get(field) is False for field in REQUIRED_FALSE_AUTHORITY_FIELDS)
    return "".join(
        (
            "<!doctype html>\n<html lang=\"en\">\n<head>\n",
            "<meta charset=\"utf-8\">\n",
            "<title>",
            escape(title),
            "</title>\n",
            "</head>\n<body>\n",
            "<main data-governed=\"true\" data-read-only=\"true\">\n",
            "<h1>",
            escape(title),
            "</h1>\n",
            "<p><strong>Status:</strong> ",
            escape(status),
            "</p>\n",
            "<p><strong>No-effect authority preserved:</strong> ",
            "true" if false_authority else "false",
            "</p>\n",
            "<h2>Operator questions</h2>\n",
            questions,
            "<h2>Demo lane</h2>\n",
            "<table><thead><tr><th>Step</th><th>Surface</th><th>Output</th><th>Authority</th></tr></thead><tbody>",
            lane_rows,
            "</tbody></table>\n",
            "<h2>Actions explicitly not taken</h2>\n",
            _html_list(str(item) for item in read_model.get("actions_not_taken", [])),
            "<h2>Next safe actions</h2>\n",
            _html_list(str(item) for item in read_model.get("next_safe_actions", [])),
            "</main>\n</body>\n</html>\n",
        )
    )


def render_first_usable_demo_operator_page(
    *,
    packet_path: Path = DEFAULT_PACKET,
    generated_at: str = "",
) -> FirstUsableDemoOperatorRender:
    """Return the read model and static HTML page for the demo packet."""
    packet = load_first_usable_demo_packet(packet_path)
    read_model = build_first_usable_demo_operator_read_model(packet, packet_path=packet_path, generated_at=generated_at)
    html = render_first_usable_demo_operator_html(read_model)
    return FirstUsableDemoOperatorRender(read_model=read_model, html=html)


def write_operator_outputs(
    render: FirstUsableDemoOperatorRender,
    *,
    read_model_output: Path = DEFAULT_READ_MODEL_OUTPUT,
    html_output: Path = DEFAULT_HTML_OUTPUT,
) -> None:
    """Write the read model JSON and static HTML operator page."""
    read_model_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    read_model_output.write_text(
        json.dumps(render.read_model, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    html_output.write_text(render.html, encoding="utf-8")


def _operator_questions(
    packet: Mapping[str, Any],
    actions_not_taken: list[str],
    next_safe_actions: list[str],
) -> list[dict[str, str]]:
    user_story = _mapping(packet.get("canonical_user_story"))
    readiness = _mapping(packet.get("readiness_index"))
    return [
        {
            "question": "What did the assistant understand the user wanted?",
            "answer": str(user_story.get("request", "")),
        },
        {
            "question": "Which exact action is proposed?",
            "answer": "prepare a governed no-effect operator review of an invoice/email draft request",
        },
        {
            "question": "What is blocked by policy or missing evidence?",
            "answer": ", ".join(
                field for field, value in readiness.items() if str(value).startswith(("blocked", "awaiting"))
            ),
        },
        {
            "question": "What approval is required before external effect?",
            "answer": "explicit operator approval plus connector authority proof, effect receipt, rollback evidence, and terminal closure",
        },
        {
            "question": "What draft or preview was produced?",
            "answer": "static read-only operator packet and demo lane preview",
        },
        {
            "question": "What actions were explicitly not taken?",
            "answer": ", ".join(actions_not_taken),
        },
        {
            "question": "What receipt and proof references were generated?",
            "answer": ", ".join(str(step.get("evidence_ref", "")) for step in _list_of_mappings(packet.get("first_demo_lane"))),
        },
        {
            "question": "What is the next safe action?",
            "answer": next_safe_actions[0] if next_safe_actions else "review_demo_packet",
        },
    ]


def _false_field_errors(mapping: Mapping[str, Any], field_names: tuple[str, ...], label: str) -> list[str]:
    return [f"{label}.{field_name} must be false" for field_name in field_names if mapping.get(field_name) is not False]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _html_list(items: Any) -> str:
    rendered = "".join(f"<li>{escape(str(item))}</li>" for item in items)
    return f"<ul>{rendered}</ul>\n"


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--read-model-output", type=Path, default=DEFAULT_READ_MODEL_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--json", action="store_true", help="Emit rendered read model as JSON")
    args = parser.parse_args(argv)
    render = render_first_usable_demo_operator_page(packet_path=args.packet, generated_at=args.generated_at)
    write_operator_outputs(render, read_model_output=args.read_model_output, html_output=args.html_output)
    if args.json:
        print(json.dumps(render.read_model, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.read_model_output}")
        print(f"wrote {args.html_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
