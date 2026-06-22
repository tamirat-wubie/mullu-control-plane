#!/usr/bin/env python3
"""Bind the First Usable Demo read model into the Personal Assistant console.

Purpose: compose the existing personal-assistant console read model with the
static first usable demo operator read model without changing live gateway
routes or runtime authority.
Governance scope: read-only console binding, product-compression visibility,
no-effect authority preservation, and customer-readiness claim separation.
Invariants:
  - Binding does not execute skills, connectors, workers, memory writes, gateway
    writes, deployment mutations, provider draft creation, sends, or payments.
  - The original console effect boundary remains false.
  - The first usable demo effect boundary remains false.
  - The combined payload is JSON-ready and secret/private-payload scanned by the
    existing console renderer if rendered by callers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from mcoi_runtime.personal_assistant import build_personal_assistant_console_read_model
from scripts.render_first_usable_demo_operator_page import (
    DEFAULT_READ_MODEL_OUTPUT,
    render_first_usable_demo_operator_page,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "first_usable_demo_console_binding.json"
REQUIRED_FALSE_CONSOLE_EFFECT_FIELDS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "mailbox_read_allowed",
    "mailbox_mutation_allowed",
    "external_send_allowed",
    "calendar_write_allowed",
    "task_write_allowed",
    "memory_write_allowed",
    "nested_mind_live_activation_allowed",
    "deployment_mutation_allowed",
    "public_readiness_claim_allowed",
)
REQUIRED_FALSE_FIRST_DEMO_EFFECT_FIELDS = (
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


def build_first_usable_demo_console_binding(*, generated_at: str) -> dict[str, Any]:
    """Return the composed console + first-demo no-effect read model."""
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("generated_at must be a non-empty string")

    console = build_personal_assistant_console_read_model(generated_at=generated_at)
    first_demo = render_first_usable_demo_operator_page(generated_at=generated_at).read_model
    _assert_false_fields(console.get("effect_boundary", {}), REQUIRED_FALSE_CONSOLE_EFFECT_FIELDS, "console.effect_boundary")
    _assert_false_fields(
        first_demo.get("effect_boundary", {}),
        REQUIRED_FALSE_FIRST_DEMO_EFFECT_FIELDS,
        "first_usable_demo.effect_boundary",
    )
    first_demo_section = {
        "item_count": 1,
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "external_send_allowed": False,
        "customer_readiness_claim_allowed": False,
        "source_packet_id": first_demo.get("source_packet_id", ""),
        "read_model_id": first_demo.get("read_model_id", ""),
    }
    sections = dict(_mapping(console.get("sections")))
    sections["first_usable_demo"] = first_demo_section
    evidence_refs = list(console.get("evidence_refs", [])) if isinstance(console.get("evidence_refs"), list) else []
    for ref in ("examples/first_usable_demo_packet.json", "scripts/render_first_usable_demo_operator_page.py"):
        if ref not in evidence_refs:
            evidence_refs.append(ref)
    binding = {
        **console,
        "sections": sections,
        "first_usable_demo": first_demo,
        "first_usable_demo_binding": {
            "binding_id": "personal_assistant_console_first_usable_demo_binding_v1",
            "binding_state": "static_read_model_bound",
            "source_console_id": console.get("console_id", ""),
            "source_first_demo_read_model_id": first_demo.get("read_model_id", ""),
            "source_packet_id": first_demo.get("source_packet_id", ""),
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
            "next_action": "review_bound_static_demo_before_any_route_or_live_connector_promotion",
        },
        "evidence_refs": evidence_refs,
    }
    _assert_false_fields(
        binding["first_usable_demo_binding"],
        (
            "execution_allowed",
            "live_connector_execution_allowed",
            "external_send_allowed",
            "connector_mutation_allowed",
            "memory_write_allowed",
            "deployment_mutation_allowed",
            "customer_readiness_claim_allowed",
        ),
        "first_usable_demo_binding",
    )
    return binding


def write_first_usable_demo_console_binding(path: Path, *, generated_at: str) -> dict[str, Any]:
    """Write the composed read model and return it."""
    payload = build_first_usable_demo_console_binding(generated_at=generated_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _assert_false_fields(payload: object, fields: tuple[str, ...], label: str) -> None:
    mapping = _mapping(payload)
    missing = [field for field in fields if mapping.get(field) is not False]
    if missing:
        raise ValueError(f"{label} authority fields must be false: {', '.join(missing)}")


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--first-demo-output",
        type=Path,
        default=DEFAULT_READ_MODEL_OUTPUT,
        help="Optional companion path documented for operators; this command writes only the console binding.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = write_first_usable_demo_console_binding(args.output, generated_at=args.generated_at)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
