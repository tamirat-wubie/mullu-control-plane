#!/usr/bin/env python3
"""Validate finance approval handoff packet schema conformance.

Purpose: reject malformed or claim-unsafe finance handoff packets before
operator handoff.
Governance scope: packet schema validation, artifact completeness, nested
artifact validation, proof summary consistency, status derivation, and
must-not-claim protections.
Dependencies: schemas/finance_approval_handoff_packet.schema.json and
.change_assurance/finance_approval_handoff_packet.json.
Invariants:
  - Packet shape matches the public protocol schema.
  - Ready/status/blockers are mutually consistent.
  - All five source artifact references are represented exactly once.
  - Referenced plan, binding receipt, closure run, and preflight artifacts validate when present.
  - Proof pilot states and must-not-claim boundaries are preserved.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_finance_approval_live_handoff_closure_run_schema import (  # noqa: E402
    validate_finance_approval_live_handoff_closure_run_schema,
)
from scripts.validate_finance_approval_email_calendar_binding_receipt import (  # noqa: E402
    validate_finance_approval_email_calendar_binding_receipt,
)
from scripts.validate_finance_approval_live_handoff_plan_schema import (  # noqa: E402
    validate_finance_approval_live_handoff_plan_schema,
)
from scripts.validate_finance_approval_live_handoff_preflight_schema import (  # noqa: E402
    validate_finance_approval_live_handoff_preflight_schema,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_handoff_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / ".change_assurance" / "finance_approval_handoff_packet.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_handoff_packet_schema_validation.json"
EXPECTED_ARTIFACTS = (
    "pilot_witness",
    "live_handoff_plan",
    "email_calendar_binding_receipt",
    "live_handoff_closure_run",
    "live_handoff_preflight",
)
REQUIRED_MUST_NOT_CLAIM = (
    "autonomous payment execution",
    "bank settlement",
    "ERP reconciliation",
    "live email delivery",
    "production finance automation",
)


@dataclass(frozen=True, slots=True)
class FinanceHandoffPacketSchemaValidation:
    """Schema and semantic validation for one finance handoff packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_path: str
    schema_path: str
    artifact_count: int
    blocker_count: int
    readiness_level: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_handoff_packet_schema(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
) -> FinanceHandoffPacketSchemaValidation:
    """Validate finance handoff packet schema and semantic consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance handoff packet schema", errors)
    packet = _load_json_object(packet_path, "finance handoff packet", errors)
    if not schema or not packet:
        return _validation_result(packet_path=packet_path, schema_path=schema_path, packet=packet, errors=errors)

    errors.extend(_validate_schema_instance(schema, packet))
    _validate_status_consistency(packet, errors)
    _validate_artifacts(packet, errors)
    _validate_handoff_plan_artifact(packet, packet_path, errors)
    _validate_binding_receipt_artifact(packet, packet_path, errors)
    _validate_closure_run_artifact(packet, packet_path, errors)
    _validate_preflight_artifact(packet, packet_path, errors)
    _validate_proof_summary(packet, errors)
    _validate_claim_boundary(packet, errors)
    return _validation_result(packet_path=packet_path, schema_path=schema_path, packet=packet, errors=errors)


def write_finance_handoff_packet_schema_validation(
    validation: FinanceHandoffPacketSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic finance handoff packet schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_status_consistency(packet: dict[str, Any], errors: list[str]) -> None:
    ready = packet.get("ready") is True
    blockers = packet.get("blockers", [])
    if packet.get("status") == "ready" and not ready:
        errors.append("status=ready requires ready=true")
    if packet.get("status") == "blocked" and ready:
        errors.append("status=blocked requires ready=false")
    if ready and blockers:
        errors.append("ready packet must not contain blockers")
    if not ready and not blockers:
        errors.append("blocked packet must contain blockers")


def _validate_artifacts(packet: dict[str, Any], errors: list[str]) -> None:
    artifacts = packet.get("artifacts", [])
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
        return
    artifact_names = [str(artifact.get("name", "")) for artifact in artifacts if isinstance(artifact, dict)]
    if tuple(sorted(artifact_names)) != tuple(sorted(EXPECTED_ARTIFACTS)):
        errors.append(
            "artifact names must match expected finance handoff artifacts: "
            f"observed={sorted(artifact_names)} expected={sorted(EXPECTED_ARTIFACTS)}"
        )
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append("artifact entries must be objects")
            continue
        if artifact.get("present") is not True and artifact.get("status") != "missing":
            errors.append(f"{artifact.get('name', '')} missing artifact must use status=missing")


def _validate_handoff_plan_artifact(packet: dict[str, Any], packet_path: Path, errors: list[str]) -> None:
    plan_artifact = _artifact_by_name(packet, "live_handoff_plan")
    if not plan_artifact or plan_artifact.get("present") is not True:
        return
    plan_path = _resolve_artifact_path(str(plan_artifact.get("path", "")), packet_path)
    validation = validate_finance_approval_live_handoff_plan_schema(plan_path=plan_path)
    if not validation.ok:
        errors.append(f"live_handoff_plan schema invalid: {list(validation.errors)}")


def _validate_binding_receipt_artifact(packet: dict[str, Any], packet_path: Path, errors: list[str]) -> None:
    binding_artifact = _artifact_by_name(packet, "email_calendar_binding_receipt")
    if not binding_artifact or binding_artifact.get("present") is not True:
        return
    receipt_path = _resolve_artifact_path(str(binding_artifact.get("path", "")), packet_path)
    validation = validate_finance_approval_email_calendar_binding_receipt(receipt_path=receipt_path)
    if not validation.valid:
        errors.append(f"email_calendar_binding_receipt schema invalid: {list(validation.errors)}")
    expected_status = "ready" if validation.ready else "blocked"
    if binding_artifact.get("status") != expected_status:
        errors.append(
            "email_calendar_binding_receipt artifact status must match binding receipt readiness: "
            f"artifact={binding_artifact.get('status', '')} receipt={expected_status}"
        )


def _validate_closure_run_artifact(packet: dict[str, Any], packet_path: Path, errors: list[str]) -> None:
    closure_artifact = _artifact_by_name(packet, "live_handoff_closure_run")
    if not closure_artifact or closure_artifact.get("present") is not True:
        return
    closure_path = _resolve_artifact_path(str(closure_artifact.get("path", "")), packet_path)
    validation = validate_finance_approval_live_handoff_closure_run_schema(closure_run_path=closure_path)
    if not validation.ok:
        errors.append(f"live_handoff_closure_run schema invalid: {list(validation.errors)}")
    if closure_artifact.get("status") != validation.status:
        errors.append(
            "live_handoff_closure_run artifact status must match closure run status: "
            f"artifact={closure_artifact.get('status', '')} closure_run={validation.status}"
        )


def _validate_preflight_artifact(packet: dict[str, Any], packet_path: Path, errors: list[str]) -> None:
    preflight_artifact = _artifact_by_name(packet, "live_handoff_preflight")
    if not preflight_artifact or preflight_artifact.get("present") is not True:
        return
    preflight_path = _resolve_artifact_path(str(preflight_artifact.get("path", "")), packet_path)
    validation = validate_finance_approval_live_handoff_preflight_schema(preflight_path=preflight_path)
    if not validation.ok:
        errors.append(f"live_handoff_preflight schema invalid: {list(validation.errors)}")
    expected_status = "ready" if validation.blocker_count == 0 else "blocked"
    if preflight_artifact.get("status") != expected_status:
        errors.append(
            "live_handoff_preflight artifact status must match preflight blocker state: "
            f"artifact={preflight_artifact.get('status', '')} preflight={expected_status}"
        )


def _validate_proof_summary(packet: dict[str, Any], errors: list[str]) -> None:
    proof_summary = packet.get("proof_summary", {})
    if not isinstance(proof_summary, dict):
        errors.append("proof_summary must be an object")
        return
    if proof_summary.get("witness_status") != "passed":
        errors.append("proof_summary.witness_status must be passed")
    if proof_summary.get("blocked_case_state") != "requires_review":
        errors.append("proof_summary.blocked_case_state must be requires_review")
    if proof_summary.get("successful_case_state") != "closed_sent":
        errors.append("proof_summary.successful_case_state must be closed_sent")
    effect_refs = proof_summary.get("successful_effect_refs", [])
    if not isinstance(effect_refs, list) or not effect_refs:
        errors.append("proof_summary.successful_effect_refs must be non-empty")


def _validate_claim_boundary(packet: dict[str, Any], errors: list[str]) -> None:
    claim_boundary = packet.get("claim_boundary", {})
    if not isinstance(claim_boundary, dict):
        errors.append("claim_boundary must be an object")
        return
    must_not_claim = set(str(item) for item in claim_boundary.get("must_not_claim", []) if isinstance(item, str))
    missing = sorted(set(REQUIRED_MUST_NOT_CLAIM) - must_not_claim)
    if missing:
        errors.append(f"claim_boundary.must_not_claim missing {missing}")


def _artifact_by_name(packet: dict[str, Any], name: str) -> dict[str, Any]:
    artifacts = packet.get("artifacts", [])
    if not isinstance(artifacts, list):
        return {}
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("name") == name:
            return artifact
    return {}


def _resolve_artifact_path(path_text: str, packet_path: Path) -> Path:
    artifact_path = Path(path_text)
    if artifact_path.is_absolute():
        return artifact_path
    return packet_path.parent / artifact_path


def _validation_result(
    *,
    packet_path: Path,
    schema_path: Path,
    packet: dict[str, Any],
    errors: list[str],
) -> FinanceHandoffPacketSchemaValidation:
    artifacts = packet.get("artifacts", ())
    blockers = packet.get("blockers", ())
    return FinanceHandoffPacketSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_path=str(packet_path),
        schema_path=str(schema_path),
        artifact_count=len(artifacts) if isinstance(artifacts, list) else 0,
        blocker_count=len(blockers) if isinstance(blockers, list) else 0,
        readiness_level=str(packet.get("readiness_level", "")),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance handoff packet schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance approval handoff packet schema.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance handoff packet schema validation."""
    args = parse_args(argv)
    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=Path(args.packet),
        schema_path=Path(args.schema),
    )
    write_finance_handoff_packet_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FINANCE HANDOFF PACKET SCHEMA VALID")
    else:
        print(f"FINANCE HANDOFF PACKET SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
