#!/usr/bin/env python3
"""Produce a finance approval pilot handoff packet.

Purpose: aggregate the finance proof witness, live handoff plan, connector
binding receipt, closure run, preflight report, and readiness report into one bounded
operator handoff artifact.
Governance scope: finance approval packet proof-pilot handoff, live blocker
visibility, claim boundary preservation, and artifact reference integrity.
Dependencies: finance approval pilot witness, live handoff plan, email/calendar
binding receipt, live handoff closure run, live handoff preflight, and readiness
validation.
Invariants:
  - Packet production does not execute live adapter receipts.
  - Packet status is derived from source artifacts.
  - Must-not-claim boundaries from the witness are preserved.
  - Missing artifacts remain blockers instead of being inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_finance_approval_pilot import DEFAULT_ADAPTER_EVIDENCE, validate_finance_approval_pilot  # noqa: E402

DEFAULT_WITNESS = REPO_ROOT / ".change_assurance" / "finance_approval_pilot_witness.json"
DEFAULT_HANDOFF_PLAN = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_plan.json"
DEFAULT_BINDING_RECEIPT = REPO_ROOT / ".change_assurance" / "finance_approval_email_calendar_binding_receipt.json"
DEFAULT_CLOSURE_RUN = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_closure_run.json"
DEFAULT_PREFLIGHT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_preflight.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_handoff_packet.json"


@dataclass(frozen=True, slots=True)
class HandoffArtifact:
    """One handoff artifact reference."""

    name: str
    path: str
    present: bool
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "present": self.present,
            "status": self.status,
        }


def produce_finance_approval_handoff_packet(
    *,
    witness_path: Path = DEFAULT_WITNESS,
    handoff_plan_path: Path = DEFAULT_HANDOFF_PLAN,
    binding_receipt_path: Path = DEFAULT_BINDING_RECEIPT,
    closure_run_path: Path = DEFAULT_CLOSURE_RUN,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    adapter_evidence_path: Path = DEFAULT_ADAPTER_EVIDENCE,
) -> dict[str, Any]:
    """Return a bounded finance approval handoff packet."""
    witness = _load_json(witness_path)
    handoff_plan = _load_json(handoff_plan_path)
    binding_receipt = _load_json(binding_receipt_path)
    closure_run = _load_json(closure_run_path)
    preflight = _load_json(preflight_path)
    readiness = validate_finance_approval_pilot(adapter_evidence_path=adapter_evidence_path)
    artifacts = (
        _artifact("pilot_witness", witness_path, witness, "status"),
        _artifact("live_handoff_plan", handoff_plan_path, handoff_plan, "readiness_level"),
        _artifact("email_calendar_binding_receipt", binding_receipt_path, binding_receipt, "ready"),
        _artifact("live_handoff_closure_run", closure_run_path, closure_run, "status"),
        _artifact("live_handoff_preflight", preflight_path, preflight, "ready"),
    )
    artifact_blockers = tuple(f"{artifact.name}_missing" for artifact in artifacts if not artifact.present)
    blocker_values = tuple(
        dict.fromkeys(
            [
                *artifact_blockers,
                *[str(blocker) for blocker in preflight.get("blockers", ())],
                *[str(blocker) for blocker in readiness.blockers],
            ]
        )
    )
    claim_boundary = witness.get("claim_boundary", {}) if isinstance(witness.get("claim_boundary", {}), dict) else {}
    packet_material = {
        "witness_id": witness.get("witness_id", ""),
        "closure_run_id": closure_run.get("run_id", ""),
        "preflight_ready": preflight.get("ready") is True,
        "readiness_level": readiness.readiness_level,
        "blockers": blocker_values,
    }
    packet_id = _stable_id("finance-handoff-packet", packet_material)
    return {
        "packet_id": packet_id,
        "checked_at": _validation_clock(),
        "status": "ready" if preflight.get("ready") is True and readiness.ready and not artifact_blockers else "blocked",
        "readiness_level": readiness.readiness_level,
        "ready": preflight.get("ready") is True and readiness.ready and not artifact_blockers,
        "blockers": list(blocker_values),
        "artifacts": [artifact.as_dict() for artifact in artifacts],
        "proof_summary": {
            "witness_id": witness.get("witness_id", ""),
            "witness_status": witness.get("status", "missing"),
            "blocked_case_state": witness.get("blocked_path", {}).get("case", {}).get("state", ""),
            "successful_case_state": witness.get("successful_path", {}).get("case", {}).get("state", ""),
            "successful_effect_refs": witness.get("successful_path", {}).get("case", {}).get("effect_refs", []),
        },
        "claim_boundary": {
            "can_claim": list(claim_boundary.get("can_claim", [])),
            "must_not_claim": list(claim_boundary.get("must_not_claim", [])),
        },
        "next_actions": _next_actions(
            binding_receipt=binding_receipt,
            closure_run=closure_run,
            preflight=preflight,
            readiness_ready=readiness.ready,
        ),
    }


def write_finance_approval_handoff_packet(packet: dict[str, Any], output_path: Path) -> Path:
    """Write one finance handoff packet."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _artifact(name: str, path: Path, payload: dict[str, Any], status_field: str) -> HandoffArtifact:
    if not payload:
        return HandoffArtifact(name=name, path=str(path), present=False, status="missing")
    status_value = payload.get(status_field)
    if isinstance(status_value, bool):
        status = "ready" if status_value else "blocked"
    else:
        status = str(status_value or "present")
    return HandoffArtifact(name=name, path=str(path), present=True, status=status)


def _next_actions(
    *,
    binding_receipt: dict[str, Any],
    closure_run: dict[str, Any],
    preflight: dict[str, Any],
    readiness_ready: bool,
) -> list[str]:
    actions: list[str] = []
    if binding_receipt.get("ready") is not True:
        actions.append("bind one scoped email/calendar connector token")
        actions.append("emit and validate finance email/calendar binding receipt with --require-ready")
    if closure_run.get("status") != "ready":
        actions.append("generate and validate finance live handoff closure run")
    if preflight.get("ready") is not True:
        actions.append("rerun finance live handoff preflight with --strict")
    if not readiness_ready:
        actions.append("produce read-only email/calendar live receipt and collect adapter evidence")
    return actions


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _stable_id(prefix: str, material: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance handoff packet arguments."""
    parser = argparse.ArgumentParser(description="Produce finance approval handoff packet.")
    parser.add_argument("--witness", default=str(DEFAULT_WITNESS))
    parser.add_argument("--handoff-plan", default=str(DEFAULT_HANDOFF_PLAN))
    parser.add_argument("--binding-receipt", default=str(DEFAULT_BINDING_RECEIPT))
    parser.add_argument("--closure-run", default=str(DEFAULT_CLOSURE_RUN))
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    parser.add_argument("--adapter-evidence", default=str(DEFAULT_ADAPTER_EVIDENCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance handoff packet production."""
    args = parse_args(argv)
    packet = produce_finance_approval_handoff_packet(
        witness_path=Path(args.witness),
        handoff_plan_path=Path(args.handoff_plan),
        binding_receipt_path=Path(args.binding_receipt),
        closure_run_path=Path(args.closure_run),
        preflight_path=Path(args.preflight),
        adapter_evidence_path=Path(args.adapter_evidence),
    )
    write_finance_approval_handoff_packet(packet, Path(args.output))
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"finance approval handoff packet: {packet['status']}")
    return 0 if packet["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
