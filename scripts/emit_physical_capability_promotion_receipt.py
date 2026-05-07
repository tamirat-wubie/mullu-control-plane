#!/usr/bin/env python3
"""Emit a physical capability promotion receipt.

Purpose: produce an operator-facing receipt that binds Forge requirements,
certification handoff refs, registry physical safety evidence, and physical
promotion preflight readiness into one schema-backed evidence bundle.
Governance scope: physical capability promotion evidence, non-mutating
operator receipts, and explicit live safety proof refs.
Dependencies: physical capability fixtures, capability forge, physical
promotion preflight, and physical capability promotion receipt schema.
Invariants:
  - The emitter performs no physical effect and no registry mutation.
  - Live safety refs are explicit; fixture refs are opt-in for tests and demos.
  - The emitted receipt is not admission authority.
  - The emitted receipt is not terminal command closure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from gateway.capability_forge import (  # noqa: E402
    CapabilityForge,
    CapabilityForgeInput,
    install_certification_handoff_evidence,
)
from gateway.physical_capability_promotion_receipt import (  # noqa: E402
    PhysicalCapabilityPromotionReceipt,
    build_physical_capability_promotion_receipt,
)
from mcoi_runtime.contracts.governed_capability_fabric import (  # noqa: E402
    CapabilityRegistryEntry,
    DomainCapsule,
    GovernedCapabilityRecord,
)
from scripts.preflight_physical_capability_promotion import (  # noqa: E402
    DEFAULT_CAPABILITY_PACK,
    DEFAULT_CAPSULE,
    preflight_physical_capability_records,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_CAPABILITY_ID = "physical.unlock_door"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "physical_capability_promotion_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "physical_capability_promotion_receipt.json"
PHYSICAL_SAFETY_REF_FIELDS = (
    "physical_action_receipt_ref",
    "simulation_ref",
    "operator_approval_ref",
    "manual_override_ref",
    "emergency_stop_ref",
    "sensor_confirmation_ref",
    "deployment_witness_ref",
)


def emit_physical_capability_promotion_receipt(
    *,
    capsule_path: Path = DEFAULT_CAPSULE,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    capability_id: str = DEFAULT_CAPABILITY_ID,
    live_read_receipt_ref: str = "",
    live_write_receipt_ref: str = "",
    worker_deployment_ref: str = "",
    recovery_evidence_ref: str = "",
    physical_live_safety_evidence_refs: Mapping[str, str] | None = None,
    use_fixture_refs: bool = False,
    recorded_at: str = "2026-05-06T12:00:00+00:00",
) -> tuple[PhysicalCapabilityPromotionReceipt | None, tuple[str, ...]]:
    """Build and validate one physical capability promotion receipt."""
    errors: list[str] = []
    capsule = _load_capsule(capsule_path, errors)
    entry = _load_capability_entry(capability_pack_path, capability_id, errors)
    schema = _load_receipt_schema(receipt_schema_path, errors)
    if capsule is None or entry is None or not schema:
        return None, tuple(errors)

    refs = _physical_safety_refs(
        capability_id=capability_id,
        entry=entry,
        explicit_refs=physical_live_safety_evidence_refs or {},
        use_fixture_refs=use_fixture_refs,
    )
    live_refs = _live_refs(
        capability_id=capability_id,
        live_read_receipt_ref=live_read_receipt_ref,
        live_write_receipt_ref=live_write_receipt_ref,
        worker_deployment_ref=worker_deployment_ref,
        recovery_evidence_ref=recovery_evidence_ref,
        use_fixture_refs=use_fixture_refs,
    )
    try:
        candidate = CapabilityForge().create_candidate(_forge_input_from_entry(entry))
        handoff = CapabilityForge().build_certification_handoff(
            candidate,
            live_read_receipt_ref=live_refs["live_read_receipt_ref"],
            live_write_receipt_ref=live_refs["live_write_receipt_ref"],
            worker_deployment_ref=live_refs["worker_deployment_ref"],
            recovery_evidence_ref=live_refs["recovery_evidence_ref"],
            physical_live_safety_evidence_refs=refs,
        )
        installed_entry = install_certification_handoff_evidence(
            _entry_without_maturity_override(entry),
            handoff,
            require_production_ready=True,
        )
        preflight_report = preflight_physical_capability_records(
            capsule=_capsule_for_capability(capsule, capability_id),
            registry_entries=(installed_entry,),
        )
        receipt = build_physical_capability_promotion_receipt(
            candidate=candidate,
            handoff=handoff,
            installed_entry=installed_entry,
            preflight_report=preflight_report,
            recorded_at=recorded_at,
        )
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
        return None, tuple(errors)

    errors.extend(_validate_schema_instance(schema, receipt.to_json_dict()))
    return receipt, tuple(errors)


def write_physical_capability_promotion_receipt(
    receipt: PhysicalCapabilityPromotionReceipt,
    output_path: Path,
) -> Path:
    """Write one physical capability promotion receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _load_capsule(path: Path, errors: list[str]) -> DomainCapsule | None:
    payload = _load_json_object(path, "physical capsule", errors)
    if not payload:
        return None
    try:
        return DomainCapsule.from_mapping(payload)
    except (KeyError, TypeError, ValueError):
        errors.append("physical capsule contract invalid")
        return None


def _load_capability_entry(path: Path, capability_id: str, errors: list[str]) -> CapabilityRegistryEntry | None:
    payload = _load_json_object(path, "physical capability pack", errors)
    capabilities = payload.get("capabilities", ()) if payload else ()
    if not isinstance(capabilities, list):
        errors.append("physical capability pack must contain capabilities array")
        return None
    for index, raw_entry in enumerate(capabilities):
        if not isinstance(raw_entry, dict):
            errors.append(f"physical capability entry invalid at index {index}")
            continue
        if raw_entry.get("capability_id") != capability_id:
            continue
        try:
            return CapabilityRegistryEntry.from_mapping(raw_entry)
        except (KeyError, TypeError, ValueError):
            errors.append(f"physical capability entry invalid: {capability_id}")
            return None
    errors.append(f"physical capability not found: {capability_id}")
    return None


def _load_receipt_schema(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return _load_schema(path)
    except (OSError, json.JSONDecodeError):
        errors.append("physical capability promotion receipt schema could not be read")
        return {}


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


def _forge_input_from_entry(entry: CapabilityRegistryEntry) -> CapabilityForgeInput:
    governed_record = GovernedCapabilityRecord.from_registry_entry(entry)
    return CapabilityForgeInput(
        capability_id=entry.capability_id,
        version=entry.version,
        domain=entry.domain,
        risk=_forge_risk(entry),
        side_effects=("physical_actuator_command",) if governed_record.world_mutating else ("physical_sandbox_replay",),
        api_docs_ref=str(entry.metadata.get("api_docs_ref") or f"docs/providers/{entry.domain}.md"),
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        owner_team=entry.obligation_model.owner_team,
        network_allowlist=tuple(entry.isolation_profile.network_allowlist),
        secret_scope=entry.isolation_profile.secret_scope,
        requires_approval=bool(entry.authority_policy.approval_chain),
    )


def _forge_risk(entry: CapabilityRegistryEntry) -> str:
    risk = str(entry.metadata.get("risk_tier") or "high").strip().lower()
    if risk in {"low", "medium", "high"}:
        return risk
    return "high"


def _entry_without_maturity_override(entry: CapabilityRegistryEntry) -> CapabilityRegistryEntry:
    from dataclasses import replace

    extensions = dict(entry.extensions)
    extensions.pop("capability_maturity_evidence", None)
    return replace(entry, extensions=extensions)


def _capsule_for_capability(capsule: DomainCapsule, capability_id: str) -> DomainCapsule:
    from dataclasses import replace

    return replace(capsule, capability_refs=(capability_id,))


def _physical_safety_refs(
    *,
    capability_id: str,
    entry: CapabilityRegistryEntry,
    explicit_refs: Mapping[str, str],
    use_fixture_refs: bool,
) -> dict[str, str]:
    existing = entry.extensions.get("physical_live_safety_evidence", {})
    existing = existing if isinstance(existing, Mapping) else {}
    refs = {
        field_name: str(explicit_refs.get(field_name) or existing.get(field_name) or "").strip()
        for field_name in PHYSICAL_SAFETY_REF_FIELDS
    }
    if use_fixture_refs:
        refs = {
            field_name: refs[field_name] or f"proof://{capability_id}/{field_name.removesuffix('_ref').replace('_', '-')}"
            for field_name in PHYSICAL_SAFETY_REF_FIELDS
        }
    return refs


def _live_refs(
    *,
    capability_id: str,
    live_read_receipt_ref: str,
    live_write_receipt_ref: str,
    worker_deployment_ref: str,
    recovery_evidence_ref: str,
    use_fixture_refs: bool,
) -> dict[str, str]:
    refs = {
        "live_read_receipt_ref": live_read_receipt_ref.strip(),
        "live_write_receipt_ref": live_write_receipt_ref.strip(),
        "worker_deployment_ref": worker_deployment_ref.strip(),
        "recovery_evidence_ref": recovery_evidence_ref.strip(),
    }
    if use_fixture_refs:
        refs = {
            "live_read_receipt_ref": refs["live_read_receipt_ref"] or f"proof://{capability_id}/live-read",
            "live_write_receipt_ref": refs["live_write_receipt_ref"] or f"proof://{capability_id}/live-write",
            "worker_deployment_ref": refs["worker_deployment_ref"] or f"proof://{capability_id}/worker",
            "recovery_evidence_ref": refs["recovery_evidence_ref"] or f"proof://{capability_id}/recovery",
        }
    return refs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse physical capability promotion receipt arguments."""
    parser = argparse.ArgumentParser(description="Emit physical capability promotion receipt.")
    parser.add_argument("--capsule", default=str(DEFAULT_CAPSULE))
    parser.add_argument("--capability-pack", default=str(DEFAULT_CAPABILITY_PACK))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--capability-id", default=DEFAULT_CAPABILITY_ID)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--live-read-receipt-ref", default="")
    parser.add_argument("--live-write-receipt-ref", default="")
    parser.add_argument("--worker-deployment-ref", default="")
    parser.add_argument("--recovery-evidence-ref", default="")
    parser.add_argument("--physical-action-receipt-ref", default="")
    parser.add_argument("--simulation-ref", default="")
    parser.add_argument("--operator-approval-ref", default="")
    parser.add_argument("--manual-override-ref", default="")
    parser.add_argument("--emergency-stop-ref", default="")
    parser.add_argument("--sensor-confirmation-ref", default="")
    parser.add_argument("--deployment-witness-ref", default="")
    parser.add_argument("--use-fixture-refs", action="store_true")
    parser.add_argument("--recorded-at", default="2026-05-06T12:00:00+00:00")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for physical capability promotion receipt emission."""
    args = parse_args(argv)
    receipt, errors = emit_physical_capability_promotion_receipt(
        capsule_path=Path(args.capsule),
        capability_pack_path=Path(args.capability_pack),
        receipt_schema_path=Path(args.receipt_schema),
        capability_id=args.capability_id,
        live_read_receipt_ref=args.live_read_receipt_ref,
        live_write_receipt_ref=args.live_write_receipt_ref,
        worker_deployment_ref=args.worker_deployment_ref,
        recovery_evidence_ref=args.recovery_evidence_ref,
        physical_live_safety_evidence_refs={
            "physical_action_receipt_ref": args.physical_action_receipt_ref,
            "simulation_ref": args.simulation_ref,
            "operator_approval_ref": args.operator_approval_ref,
            "manual_override_ref": args.manual_override_ref,
            "emergency_stop_ref": args.emergency_stop_ref,
            "sensor_confirmation_ref": args.sensor_confirmation_ref,
            "deployment_witness_ref": args.deployment_witness_ref,
        },
        use_fixture_refs=args.use_fixture_refs,
        recorded_at=args.recorded_at,
    )
    payload: dict[str, Any] = {"ready": False, "errors": list(errors)}
    if receipt is not None:
        write_physical_capability_promotion_receipt(receipt, Path(args.output))
        payload = receipt.to_json_dict() | {"ready": not errors, "errors": list(errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif receipt is not None and not errors:
        print(f"physical capability promotion receipt ready receipt_id={receipt.receipt_id}")
    else:
        print(f"physical capability promotion receipt blocked errors={list(errors)}")
    return 0 if receipt is not None and not errors else (2 if args.strict else 0)


if __name__ == "__main__":
    raise SystemExit(main())
