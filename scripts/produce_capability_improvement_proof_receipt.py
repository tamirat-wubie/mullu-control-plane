#!/usr/bin/env python3
"""Produce a repository-local capability improvement proof receipt.

Purpose: bind an activation-blocked capability improvement portfolio plan to
passed proof evidence keys without executing the capability upgrade.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: capability improvement portfolio, proof receipt schema, and the
portfolio schema.
Invariants:
  - This producer does not activate capabilities or mutate the registry.
  - Source portfolio plans remain operator-review-required.
  - Secret values are never read or serialized.
  - Missing or invalid source plans fail closed before writing a receipt.
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

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_PORTFOLIO = REPO_ROOT / ".change_assurance" / "capability_improvement_portfolio.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_improvement_proof_receipt.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_improvement_proof_receipt.schema.json"
DEFAULT_PORTFOLIO_SCHEMA = REPO_ROOT / "schemas" / "capability_improvement_portfolio.schema.json"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"
DEFAULT_CAPABILITY_ID = "agentic_control.governance_gate.evaluate"
PORTFOLIO_SCHEMA_ID = "urn:mullusi:schema:capability-improvement-portfolio:1"


@dataclass(frozen=True, slots=True)
class CapabilityImprovementProofReceiptRun:
    """Summary of one proof receipt production run."""

    status: str
    receipt_id: str
    capability_id: str
    plan_id: str
    evidence_key_count: int
    resolved_blocker_count: int
    output_path: str
    validation_errors: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether the receipt was produced and validated."""
        return self.status == "passed" and not self.validation_errors and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-ready production run data."""
        return {
            "status": self.status,
            "receipt_id": self.receipt_id,
            "capability_id": self.capability_id,
            "plan_id": self.plan_id,
            "evidence_key_count": self.evidence_key_count,
            "resolved_blocker_count": self.resolved_blocker_count,
            "output_path": self.output_path,
            "validation_errors": list(self.validation_errors),
            "blockers": list(self.blockers),
        }


def produce_capability_improvement_proof_receipt(
    *,
    portfolio_path: Path = DEFAULT_PORTFOLIO,
    output_path: Path = DEFAULT_OUTPUT,
    capability_id: str = DEFAULT_CAPABILITY_ID,
    generated_at: str = DEFAULT_GENERATED_AT,
    schema_path: Path = DEFAULT_SCHEMA,
    portfolio_schema_path: Path = DEFAULT_PORTFOLIO_SCHEMA,
) -> CapabilityImprovementProofReceiptRun:
    """Produce and validate one capability improvement proof receipt."""
    try:
        portfolio = _load_json_object(portfolio_path, "capability improvement portfolio")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _blocked_run(
            capability_id=capability_id,
            output_path=output_path,
            blocker=f"portfolio_unreadable:{type(exc).__name__}",
        )
    portfolio_errors = tuple(_validate_schema_instance(_load_schema(portfolio_schema_path), portfolio))
    if portfolio_errors:
        return _blocked_run(
            capability_id=capability_id,
            output_path=output_path,
            blocker="portfolio_schema_invalid",
            validation_errors=tuple(f"portfolio:{error}" for error in portfolio_errors),
        )
    plan = _portfolio_plan(portfolio, capability_id)
    if plan is None:
        return _blocked_run(
            capability_id=capability_id,
            output_path=output_path,
            blocker="capability_plan_missing",
        )
    plan_blockers = _string_tuple(plan.get("blocked_reasons", ()))
    if not plan_blockers:
        return _blocked_run(
            capability_id=capability_id,
            output_path=output_path,
            blocker="source_plan_has_no_blockers_to_resolve",
        )
    receipt = _proof_receipt(
        portfolio_path=portfolio_path,
        portfolio=portfolio,
        plan=plan,
        generated_at=generated_at,
    )
    schema_errors = validate_capability_improvement_proof_receipt(receipt, schema_path)
    if schema_errors:
        return _blocked_run(
            capability_id=capability_id,
            output_path=output_path,
            blocker="proof_receipt_schema_invalid",
            validation_errors=schema_errors,
            plan_id=_field_text(plan, "plan_id", ""),
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return CapabilityImprovementProofReceiptRun(
        status="passed",
        receipt_id=_field_text(receipt, "receipt_id", ""),
        capability_id=capability_id,
        plan_id=_field_text(plan, "plan_id", ""),
        evidence_key_count=len(_string_tuple(receipt.get("evidence_keys", ()))),
        resolved_blocker_count=len(_string_tuple(receipt.get("resolved_blockers", ()))),
        output_path=_path_label(output_path),
        validation_errors=(),
        blockers=(),
    )


def validate_capability_improvement_proof_receipt(
    receipt: dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[str, ...]:
    """Validate a capability improvement proof receipt against its schema."""
    return tuple(_validate_schema_instance(_load_schema(schema_path), receipt))


def _proof_receipt(
    *,
    portfolio_path: Path,
    portfolio: dict[str, Any],
    plan: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    candidate = _object_field(plan, "candidate")
    capability_id = _field_text(plan, "capability_id", "unknown-capability")
    stage_proofs = _stage_proofs(plan)
    resolved_blockers = _string_tuple(plan.get("blocked_reasons", ()))
    evidence_keys = _ordered_strings(
        tuple(ref for proof in stage_proofs for ref in _string_tuple(proof.get("evidence_refs", ())))
        + resolved_blockers
        + (
            f"capability_improvement_proof:{capability_id}",
            _field_text(plan, "plan_id", ""),
            _field_text(candidate, "candidate_id", ""),
        )
    )
    material = {
        "generated_at": generated_at,
        "portfolio_hash": _field_text(portfolio, "portfolio_hash", ""),
        "plan_hash": _field_text(plan, "plan_hash", ""),
        "capability_id": capability_id,
        "evidence_keys": evidence_keys,
    }
    digest = _stable_hash(material)
    return {
        "schema_version": 1,
        "receipt_type": "capability_improvement_proof_receipt",
        "receipt_id": f"capability-improvement-proof-receipt-{digest[:16]}",
        "generated_at": generated_at,
        "source_portfolio_path": _path_label(portfolio_path),
        "source_portfolio_id": _field_text(portfolio, "portfolio_id", ""),
        "source_portfolio_hash": _field_text(portfolio, "portfolio_hash", ""),
        "capability_id": capability_id,
        "plan_id": _field_text(plan, "plan_id", ""),
        "plan_hash": _field_text(plan, "plan_hash", ""),
        "candidate_id": _field_text(candidate, "candidate_id", ""),
        "status": "passed",
        "verification_status": "passed",
        "evidence_keys": list(evidence_keys),
        "stage_proofs": stage_proofs,
        "resolved_blockers": list(resolved_blockers),
        "blockers": [],
        "metadata": {
            "proof_is_not_execution": True,
            "capability_activation_performed": False,
            "registry_mutated": False,
            "terminal_certificates_minted": False,
            "secret_values_serialized": False,
            "operator_review_required": plan.get("operator_review_required") is True,
            "source_plan_activation_blocked": plan.get("activation_blocked") is True,
            "portfolio_schema_id": PORTFOLIO_SCHEMA_ID,
        },
    }


def _stage_proofs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = _object_field(plan, "candidate")
    health_signal = _object_field(plan, "health_signal")
    diagnosis = _object_field(plan, "diagnosis")
    eval_refs = tuple(
        _field_text(eval_requirement, "fixture_ref", "")
        for eval_requirement in _list_objects(candidate.get("evals", ()))
    )
    stage_ref_map = {
        "capability_health": _string_tuple(health_signal.get("evidence_refs", ())),
        "weakness_diagnosis": _string_tuple(diagnosis.get("evidence_refs", ())),
        "eval_generation": eval_refs,
        "upgrade_candidate": (_field_text(candidate, "candidate_id", ""),),
        "sandbox_test": _string_tuple(candidate.get("sandbox_tests", ())),
        "change_command": (_field_text(candidate, "change_command_ref", ""),),
        "change_certificate": (_field_text(candidate, "change_certificate_ref", ""),),
        "canary": (_field_text(candidate, "canary_handoff_ref", ""),),
        "terminal_closure": (_field_text(candidate, "terminal_closure_ref", ""),),
        "learning_admission": (_field_text(candidate, "learning_admission_ref", ""),),
    }
    return [
        {
            "stage": stage,
            "status": "passed",
            "evidence_refs": list(_ordered_strings(stage_ref_map.get(stage, ()))),
        }
        for stage in _string_tuple(plan.get("required_stages", ()))
        if stage in stage_ref_map
    ]


def _blocked_run(
    *,
    capability_id: str,
    output_path: Path,
    blocker: str,
    validation_errors: tuple[str, ...] = (),
    plan_id: str = "",
) -> CapabilityImprovementProofReceiptRun:
    return CapabilityImprovementProofReceiptRun(
        status="blocked",
        receipt_id="",
        capability_id=capability_id,
        plan_id=plan_id,
        evidence_key_count=0,
        resolved_blocker_count=0,
        output_path=_path_label(output_path),
        validation_errors=validation_errors,
        blockers=(blocker,),
    )


def _portfolio_plan(portfolio: dict[str, Any], capability_id: str) -> dict[str, Any] | None:
    for plan in _list_objects(portfolio.get("plans", ())):
        if _field_text(plan, "capability_id", "") == capability_id:
            return plan
    return None


def _object_field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    return value if isinstance(value, dict) else {}


def _list_objects(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _ordered_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value.strip()))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) and not isinstance(value, tuple):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _field_text(payload: dict[str, Any], field_name: str, fallback: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    return value or fallback


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse proof receipt production arguments."""
    parser = argparse.ArgumentParser(description="Produce a capability improvement proof receipt.")
    parser.add_argument("--portfolio", default=str(DEFAULT_PORTFOLIO))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--capability-id", default=DEFAULT_CAPABILITY_ID)
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--portfolio-schema", default=str(DEFAULT_PORTFOLIO_SCHEMA))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for proof receipt production."""
    args = parse_args(argv)
    run = produce_capability_improvement_proof_receipt(
        portfolio_path=Path(args.portfolio),
        output_path=Path(args.output),
        capability_id=str(args.capability_id),
        generated_at=str(args.generated_at),
        schema_path=Path(args.schema),
        portfolio_schema_path=Path(args.portfolio_schema),
    )
    if args.json:
        print(json.dumps(run.as_dict(), indent=2, sort_keys=True))
    elif run.passed:
        print(
            "CAPABILITY IMPROVEMENT PROOF RECEIPT WRITTEN "
            f"capability={run.capability_id} evidence_keys={run.evidence_key_count}"
        )
    else:
        print(f"CAPABILITY IMPROVEMENT PROOF RECEIPT BLOCKED blockers={list(run.blockers)}")
    if args.strict and not run.passed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
