#!/usr/bin/env python3
"""Produce a bounded finance approval operator summary.

Purpose: collapse the handoff packet and aggregate chain into one redacted
operator status artifact.
Governance scope: finance promotion boundary, ok/ready separation, readiness
blocker preservation, and must-not-claim visibility.
Dependencies: finance approval handoff packet, finance live handoff chain
validation, and schemas/finance_approval_operator_summary.schema.json.
Invariants:
  - Summary production is read-only and never executes live adapter actions.
  - Packet ok and ready are preserved as separate fields.
  - Chain ok and ready are preserved as separate fields.
  - Secret values are not read or serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_finance_approval_handoff_packet import DEFAULT_OUTPUT as DEFAULT_PACKET  # noqa: E402
from scripts.validate_finance_approval_live_handoff_chain import DEFAULT_OUTPUT as DEFAULT_CHAIN  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_operator_summary.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_operator_summary.json"


def produce_finance_approval_operator_summary(
    *,
    packet_path: Path = DEFAULT_PACKET,
    chain_path: Path = DEFAULT_CHAIN,
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Return a redacted finance operator summary and validation errors."""
    errors: list[str] = []
    packet = _load_json_object(packet_path, "finance handoff packet", errors)
    chain = _load_json_object(chain_path, "finance live handoff chain validation", errors)
    schema = _load_json_object(schema_path, "finance operator summary schema", errors)
    promotion_boundary = packet.get("promotion_boundary", {}) if isinstance(packet.get("promotion_boundary"), dict) else {}
    claim_boundary = packet.get("claim_boundary", {}) if isinstance(packet.get("claim_boundary"), dict) else {}
    artifact_statuses = {
        str(artifact.get("name", "")): str(artifact.get("status", ""))
        for artifact in packet.get("artifacts", [])
        if isinstance(artifact, dict) and artifact.get("name")
    }
    readiness_blockers = _dedupe(
        [
            *[str(blocker) for blocker in promotion_boundary.get("readiness_blockers", []) if isinstance(blocker, str)],
            *[str(blocker) for blocker in chain.get("readiness_blockers", []) if isinstance(blocker, str)],
        ]
    )
    summary_material = {
        "packet_id": packet.get("packet_id", ""),
        "packet_ready": packet.get("ready") is True,
        "chain_ready": chain.get("ready") is True,
        "readiness_blockers": readiness_blockers,
    }
    summary = {
        "summary_id": _stable_id("finance-operator-summary", summary_material),
        "checked_at": _validation_clock(),
        "packet_id": str(packet.get("packet_id", "")),
        "packet_ok": promotion_boundary.get("ok") is True,
        "packet_ready": packet.get("ready") is True,
        "packet_status": str(packet.get("status", "")),
        "chain_ok": chain.get("ok") is True,
        "chain_ready": chain.get("ready") is True,
        "promotion_mode": str(promotion_boundary.get("mode", "")),
        "strict_promotion_command": str(promotion_boundary.get("strict_promotion_command", "")),
        "readiness_blockers": readiness_blockers,
        "next_actions": [str(action) for action in packet.get("next_actions", []) if isinstance(action, str)],
        "artifact_statuses": artifact_statuses,
        "must_not_claim": [str(claim) for claim in claim_boundary.get("must_not_claim", []) if isinstance(claim, str)],
    }
    _validate_summary_semantics(summary, errors)
    if schema:
        errors.extend(_validate_schema_instance(schema, summary))
    return summary, tuple(errors)


def write_finance_approval_operator_summary(summary: dict[str, Any], output_path: Path) -> Path:
    """Write one finance operator summary."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_summary_semantics(summary: dict[str, Any], errors: list[str]) -> None:
    if summary["packet_ready"] != summary["chain_ready"]:
        errors.append("packet_ready and chain_ready must match")
    if summary["packet_ready"] and summary["readiness_blockers"]:
        errors.append("ready operator summary must not contain readiness_blockers")
    if not summary["packet_ready"] and not summary["readiness_blockers"]:
        errors.append("blocked operator summary must contain readiness_blockers")
    for token in ("validate_finance_approval_live_handoff_chain.py", "--strict", "--require-ready", "--json"):
        if token not in str(summary["strict_promotion_command"]):
            errors.append(f"strict_promotion_command missing token {token}")
    for forbidden_claim in (
        "autonomous payment execution",
        "bank settlement",
        "ERP reconciliation",
        "live email delivery",
        "production finance automation",
    ):
        if forbidden_claim not in summary["must_not_claim"]:
            errors.append(f"must_not_claim missing {forbidden_claim}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return payload


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _stable_id(prefix: str, material: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance operator summary arguments."""
    parser = argparse.ArgumentParser(description="Produce finance approval operator summary.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--chain", default=str(DEFAULT_CHAIN))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance operator summary production."""
    args = parse_args(argv)
    summary, errors = produce_finance_approval_operator_summary(
        packet_path=Path(args.packet),
        chain_path=Path(args.chain),
        schema_path=Path(args.schema),
    )
    write_finance_approval_operator_summary(summary, Path(args.output))
    payload = summary | {"errors": list(errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not errors:
        print(f"finance approval operator summary ready={summary['packet_ready']}")
    else:
        print(f"finance approval operator summary invalid errors={list(errors)}")
    return 0 if not errors or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
