#!/usr/bin/env python3
"""Preflight physical capability promotion readiness.

Purpose: verify a candidate physical capability pack before any fixture-only
capability can be represented as a production claim.
Governance scope: physical-action boundary, capability maturity, production
evidence projection, and explicit blocker reporting.
Dependencies: checked-in physical capsule/capability fixtures, capability
maturity assessor, and deployment collector physical evidence policy.
Invariants:
  - Preflight never sends hardware commands or performs live effects.
  - Sandbox-only physical capabilities never become production claims.
  - Live physical candidates require complete live safety evidence.
  - Production readiness must be derived from capability maturity evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from gateway.capability_maturity import CapabilityRegistryMaturityProjector  # noqa: E402
from mcoi_runtime.contracts.governed_capability_fabric import (  # noqa: E402
    CapabilityRegistryEntry,
    DomainCapsule,
    GovernedCapabilityRecord,
)
from scripts.collect_deployment_witness import (  # noqa: E402
    PHYSICAL_ACTION_RECEIPT_SCHEMA_REF,
    REQUIRED_PHYSICAL_LIVE_EVIDENCE_FIELDS,
    _evaluate_physical_capability_policy,
)

DEFAULT_CAPSULE = REPO_ROOT / "capsules" / "physical.json"
DEFAULT_CAPABILITY_PACK = REPO_ROOT / "capabilities" / "physical" / "capability_pack.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "physical_capability_promotion_preflight.json"
PHYSICAL_CAPABILITY_PREFIXES = ("physical.", "iot.", "robotics.")


@dataclass(frozen=True, slots=True)
class PhysicalPromotionPreflightStep:
    """One physical promotion preflight step."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready step payload."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PhysicalPromotionPreflightReport:
    """Full physical capability promotion preflight report."""

    ready: bool
    checked_at: str
    readiness_level: str
    step_count: int
    physical_capability_count: int
    sandbox_only_capabilities: tuple[str, ...]
    live_physical_candidates: tuple[str, ...]
    production_claim_capabilities: tuple[str, ...]
    steps: tuple[PhysicalPromotionPreflightStep, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready preflight report."""
        return {
            "ready": self.ready,
            "checked_at": self.checked_at,
            "readiness_level": self.readiness_level,
            "step_count": self.step_count,
            "physical_capability_count": self.physical_capability_count,
            "sandbox_only_capabilities": list(self.sandbox_only_capabilities),
            "live_physical_candidates": list(self.live_physical_candidates),
            "production_claim_capabilities": list(self.production_claim_capabilities),
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class _PhysicalCapabilityProjection:
    capability_id: str
    maturity_level: str
    production_ready: bool
    world_mutating: bool
    safety_evidence: Mapping[str, Any]
    live_safety_evidence_complete: bool
    safety_blockers: tuple[str, ...]


def preflight_physical_capability_promotion(
    *,
    capsule_path: Path = DEFAULT_CAPSULE,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
) -> PhysicalPromotionPreflightReport:
    """Return physical capability promotion readiness without executing effects."""
    capsule, entries, load_errors = _load_inputs(capsule_path, capability_pack_path)
    if load_errors:
        steps = (
            PhysicalPromotionPreflightStep(
                name="physical capsule and pack load",
                passed=False,
                detail=f"errors={list(load_errors)}",
            ),
        )
        return _report_from_steps(
            steps=steps,
            physical_capability_count=0,
            sandbox_only_capabilities=(),
            live_physical_candidates=(),
            production_claim_capabilities=(),
        )
    return preflight_physical_capability_records(capsule=capsule, registry_entries=entries)


def preflight_physical_capability_records(
    *,
    capsule: DomainCapsule,
    registry_entries: Iterable[CapabilityRegistryEntry],
) -> PhysicalPromotionPreflightReport:
    """Return physical promotion readiness for already parsed capability records."""
    if not isinstance(capsule, DomainCapsule):
        raise ValueError("physical_preflight_capsule_type_invalid")
    entries = tuple(registry_entries)
    for index, entry in enumerate(entries):
        if not isinstance(entry, CapabilityRegistryEntry):
            raise ValueError(f"physical_preflight_registry_entry_type_invalid:{index}")
    return _preflight_loaded_physical_capabilities(capsule, entries)


def _preflight_loaded_physical_capabilities(
    capsule: DomainCapsule,
    entries: tuple[CapabilityRegistryEntry, ...],
) -> PhysicalPromotionPreflightReport:
    by_id = {entry.capability_id: entry for entry in entries}
    missing_refs = tuple(capability_id for capability_id in capsule.capability_refs if capability_id not in by_id)
    referenced_entries = tuple(by_id[capability_id] for capability_id in capsule.capability_refs if capability_id in by_id)
    physical_entries = tuple(entry for entry in referenced_entries if _is_physical_capability(entry.capability_id))
    projections = tuple(_project_physical_capability(entry) for entry in physical_entries)
    live_candidates = tuple(projection.capability_id for projection in projections if projection.world_mutating)
    sandbox_only = tuple(projection.capability_id for projection in projections if not projection.world_mutating)
    production_claims = tuple(
        projection.capability_id
        for projection in projections
        if projection.production_ready
    )
    safety_blockers = tuple(
        blocker
        for projection in projections
        if projection.world_mutating
        for blocker in projection.safety_blockers
    )
    readiness_blockers = tuple(
        f"{projection.capability_id}:production_ready_required"
        for projection in projections
        if projection.world_mutating and not projection.production_ready
    )
    evidence_payload = _capability_evidence_payload(projections)
    physical_policy = _evaluate_physical_capability_policy(evidence_payload)
    projection_policy_passed = physical_policy.passed and not physical_policy.blockers
    steps = (
        PhysicalPromotionPreflightStep(
            name="physical capsule and pack load",
            passed=not missing_refs,
            detail=(
                f"capsule_id={capsule.capsule_id} capability_count={len(entries)} "
                f"missing_refs={list(missing_refs)}"
            ),
        ),
        PhysicalPromotionPreflightStep(
            name="physical capability classification",
            passed=bool(physical_entries) and all(entry.domain == "physical" for entry in physical_entries),
            detail=(
                f"physical_capability_count={len(physical_entries)} "
                f"sandbox_only={list(sandbox_only)} live_candidates={list(live_candidates)}"
            ),
        ),
        PhysicalPromotionPreflightStep(
            name="live physical safety evidence complete",
            passed=not safety_blockers,
            detail="complete=true" if not safety_blockers else f"blockers={list(safety_blockers)}",
        ),
        PhysicalPromotionPreflightStep(
            name="physical production readiness gate",
            passed=not readiness_blockers,
            detail="production_ready=true" if not readiness_blockers else f"blockers={list(readiness_blockers)}",
        ),
        PhysicalPromotionPreflightStep(
            name="physical production evidence projection",
            passed=projection_policy_passed,
            detail=physical_policy.detail(),
        ),
    )
    return _report_from_steps(
        steps=steps,
        physical_capability_count=len(physical_entries),
        sandbox_only_capabilities=sandbox_only,
        live_physical_candidates=live_candidates,
        production_claim_capabilities=production_claims,
    )


def write_physical_promotion_preflight_report(
    report: PhysicalPromotionPreflightReport,
    output_path: Path,
) -> Path:
    """Write one physical promotion preflight report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _load_inputs(
    capsule_path: Path,
    capability_pack_path: Path,
) -> tuple[DomainCapsule, tuple[CapabilityRegistryEntry, ...], tuple[str, ...]]:
    errors: list[str] = []
    capsule_payload = _load_json_object(capsule_path, errors, "physical capsule")
    pack_payload = _load_json_object(capability_pack_path, errors, "physical capability pack")
    if errors:
        return _empty_capsule(), (), tuple(errors)
    try:
        capsule = DomainCapsule.from_mapping(capsule_payload)
    except (KeyError, TypeError, ValueError):
        errors.append("physical capsule contract invalid")
        capsule = _empty_capsule()
    raw_capabilities = pack_payload.get("capabilities", ())
    if not isinstance(raw_capabilities, list):
        errors.append("physical capability pack must contain capabilities array")
        raw_capabilities = []
    entries: list[CapabilityRegistryEntry] = []
    for index, raw_entry in enumerate(raw_capabilities):
        try:
            entries.append(CapabilityRegistryEntry.from_mapping(raw_entry))
        except (KeyError, TypeError, ValueError):
            errors.append(f"physical capability entry invalid at index {index}")
    return capsule, tuple(entries), tuple(errors)


def _load_json_object(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"{label} could not be read")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _project_physical_capability(entry: CapabilityRegistryEntry) -> _PhysicalCapabilityProjection:
    governed_record = GovernedCapabilityRecord.from_registry_entry(entry)
    assessment = CapabilityRegistryMaturityProjector().assess_entry(entry)
    safety_evidence = _physical_live_safety_evidence(entry)
    safety_blockers = (
        ()
        if not governed_record.world_mutating
        else _physical_safety_blockers(entry.capability_id, safety_evidence)
    )
    return _PhysicalCapabilityProjection(
        capability_id=entry.capability_id,
        maturity_level=assessment.maturity_level,
        production_ready=assessment.production_ready,
        world_mutating=governed_record.world_mutating,
        safety_evidence=safety_evidence,
        live_safety_evidence_complete=not safety_blockers,
        safety_blockers=safety_blockers,
    )


def _physical_safety_blockers(capability_id: str, evidence: Mapping[str, Any]) -> tuple[str, ...]:
    if not evidence:
        return (f"{capability_id}:physical_live_safety_evidence_required",)
    blockers: list[str] = []
    for field_name in REQUIRED_PHYSICAL_LIVE_EVIDENCE_FIELDS:
        if not str(evidence.get(field_name, "")).strip():
            blockers.append(f"{capability_id}:{field_name}_required")
    return tuple(blockers)


def _capability_evidence_payload(
    projections: tuple[_PhysicalCapabilityProjection, ...],
) -> dict[str, Any]:
    capability_evidence: dict[str, Any] = {}
    live_capabilities: list[str] = []
    sandbox_only_capabilities: list[str] = []
    for projection in projections:
        if projection.production_ready:
            capability_evidence[projection.capability_id] = _production_evidence_value(projection)
            live_capabilities.append(projection.capability_id)
        elif projection.maturity_level in {"C4", "C5"}:
            capability_evidence[projection.capability_id] = "pilot"
        elif projection.maturity_level == "C3":
            capability_evidence[projection.capability_id] = "sandbox"
            sandbox_only_capabilities.append(projection.capability_id)
        elif projection.maturity_level in {"C1", "C2"}:
            capability_evidence[projection.capability_id] = "tested"
        else:
            capability_evidence[projection.capability_id] = "described_only"
    return {
        "enabled": True,
        "capability_count": len(capability_evidence),
        "capability_evidence": capability_evidence,
        "live_capabilities": live_capabilities,
        "sandbox_only_capabilities": sandbox_only_capabilities,
    }


def _production_evidence_value(projection: _PhysicalCapabilityProjection) -> str | dict[str, Any]:
    if not projection.live_safety_evidence_complete:
        return "production"
    return {
        "maturity": "production",
        "effect_mode": "live",
        "production_admissible": True,
        "physical_action_receipt_schema_ref": PHYSICAL_ACTION_RECEIPT_SCHEMA_REF,
        **dict(projection.safety_evidence),
    }


def _physical_live_safety_evidence(entry: CapabilityRegistryEntry) -> Mapping[str, Any]:
    extensions = entry.extensions
    evidence = extensions.get("physical_live_safety_evidence", {})
    evidence = evidence if isinstance(evidence, Mapping) else {}
    return evidence


def _report_from_steps(
    *,
    steps: tuple[PhysicalPromotionPreflightStep, ...],
    physical_capability_count: int,
    sandbox_only_capabilities: tuple[str, ...],
    live_physical_candidates: tuple[str, ...],
    production_claim_capabilities: tuple[str, ...],
) -> PhysicalPromotionPreflightReport:
    blockers = tuple(step.name for step in steps if not step.passed)
    ready = not blockers
    if ready and production_claim_capabilities:
        readiness_level = "physical-production-ready"
    elif ready:
        readiness_level = "physical-sandbox-only"
    else:
        readiness_level = "blocked"
    return PhysicalPromotionPreflightReport(
        ready=ready,
        checked_at=_validation_clock(),
        readiness_level=readiness_level,
        step_count=len(steps),
        physical_capability_count=physical_capability_count,
        sandbox_only_capabilities=sandbox_only_capabilities,
        live_physical_candidates=live_physical_candidates,
        production_claim_capabilities=production_claim_capabilities,
        steps=steps,
        blockers=blockers,
    )


def _is_physical_capability(capability_id: str) -> bool:
    normalized = capability_id.strip().lower()
    return any(normalized.startswith(prefix) for prefix in PHYSICAL_CAPABILITY_PREFIXES)


def _empty_capsule() -> DomainCapsule:
    return DomainCapsule.from_mapping({
        "capsule_id": "physical.empty",
        "domain": "physical",
        "version": "0.0.0",
        "ontology_refs": ["none"],
        "capability_refs": ["none"],
        "policy_refs": ["none"],
        "evidence_rules": ["none"],
        "approval_rules": ["none"],
        "recovery_rules": ["none"],
        "test_fixture_refs": ["none"],
        "read_model_refs": ["none"],
        "operator_view_refs": ["none"],
        "owner_team": "physical-safety",
        "certification_status": "draft",
        "metadata": {},
        "extensions": {},
    })


def _validation_clock() -> str:
    return "2026-05-06T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse physical promotion preflight arguments."""
    parser = argparse.ArgumentParser(description="Preflight physical capability promotion readiness.")
    parser.add_argument("--capsule", default=str(DEFAULT_CAPSULE))
    parser.add_argument("--capability-pack", default=str(DEFAULT_CAPABILITY_PACK))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for physical promotion preflight."""
    args = parse_args(argv)
    report = preflight_physical_capability_promotion(
        capsule_path=Path(args.capsule),
        capability_pack_path=Path(args.capability_pack),
    )
    write_physical_promotion_preflight_report(report, Path(args.output))
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    elif report.ready:
        print(f"PHYSICAL CAPABILITY PROMOTION PREFLIGHT READY readiness_level={report.readiness_level}")
    else:
        print(f"PHYSICAL CAPABILITY PROMOTION PREFLIGHT BLOCKED blockers={list(report.blockers)}")
    return 0 if report.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
