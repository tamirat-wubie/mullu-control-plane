#!/usr/bin/env python3
"""Validate Reflex deployment witnesses.

Purpose: replay signed Reflex deployment witness evidence offline for operator
    shells, CI jobs, and governed promotion review.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: mcoi_runtime.core.reflex shared witness verifier.
Invariants:
  - Missing, unreadable, or malformed witness files fail closed.
  - Replay uses the same canonical seed and HMAC verifier as the gateway.
  - Production mutation claims are rejected by the shared verifier.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcoi_runtime.core.reflex import verify_reflex_deployment_witness  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

REFLEX_DEPLOYMENT_WITNESS_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "reflex_deployment_witness_envelope.schema.json"
)

REQUIRED_FIELDS = (
    "witness_id",
    "candidate_id",
    "certificate_id",
    "promotion_decision_id",
    "target_environment",
    "canary_status",
    "health_refs",
    "rollback_plan_ref",
    "signed_at",
    "signature_key_id",
    "signature",
    "production_mutation_applied",
)


@dataclass(frozen=True, slots=True)
class ReflexDeploymentWitnessValidation:
    """Validation result for one Reflex deployment witness."""

    valid: bool
    witness_path: str
    status: str
    witness_id: str
    candidate_id: str
    certificate_id: str
    target_environment: str
    detail: str
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def validate_reflex_deployment_witness(
    witness_path: Path,
    *,
    signing_secret: str,
    expected_environment: str = "",
    expected_candidate_id: str = "",
) -> ReflexDeploymentWitnessValidation:
    """Validate one signed Reflex deployment witness."""
    payload, load_error = _load_payload(witness_path)
    if load_error:
        return _invalid(witness_path, load_error, ("reflex_witness_unreadable",))

    witness = payload.get("witness") if isinstance(payload.get("witness"), dict) else payload
    if not isinstance(witness, dict):
        return _invalid(witness_path, "reflex witness root must be an object", ("reflex_witness_unreadable",))

    errors = list(_schema_errors(payload))
    errors.extend(_witness_shape_errors(
        witness,
        expected_environment=expected_environment,
        expected_candidate_id=expected_candidate_id,
    ))
    replay_passed = verify_reflex_deployment_witness(witness, signing_secret=signing_secret)
    if not replay_passed:
        errors.append("replay_signature_mismatch")

    witness_id = str(witness.get("witness_id", "")).strip()
    candidate_id = str(witness.get("candidate_id", "")).strip()
    certificate_id = str(witness.get("certificate_id", "")).strip()
    target_environment = str(witness.get("target_environment", "")).strip()
    if errors:
        return ReflexDeploymentWitnessValidation(
            valid=False,
            witness_path="<provided>",
            status="failed",
            witness_id=witness_id,
            candidate_id=candidate_id,
            certificate_id=certificate_id,
            target_environment=target_environment,
            detail=",".join(errors),
            blockers=("reflex_witness_invalid",),
        )
    return ReflexDeploymentWitnessValidation(
        valid=True,
        witness_path="<provided>",
        status="passed",
        witness_id=witness_id,
        candidate_id=candidate_id,
        certificate_id=certificate_id,
        target_environment=target_environment,
        detail="reflex deployment witness verified",
        blockers=(),
    )


def _load_payload(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "reflex deployment witness file not found"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "reflex deployment witness unreadable"
    if not isinstance(payload, dict):
        return {}, "reflex deployment witness root must be an object"
    return payload, ""


def _schema_errors(payload: dict[str, Any]) -> tuple[str, ...]:
    try:
        schema = _load_schema(REFLEX_DEPLOYMENT_WITNESS_SCHEMA_PATH)
    except OSError:
        return ("schema_unreadable",)
    errors = _validate_schema_instance(schema, payload)
    return tuple(f"schema:{error}" for error in errors)


def _witness_shape_errors(
    witness: dict[str, Any],
    *,
    expected_environment: str,
    expected_candidate_id: str,
) -> list[str]:
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in witness:
            errors.append(f"{field_name}_missing")
    for field_name in (
        "witness_id",
        "candidate_id",
        "certificate_id",
        "promotion_decision_id",
        "target_environment",
        "canary_status",
        "rollback_plan_ref",
        "signed_at",
        "signature_key_id",
        "signature",
    ):
        if not str(witness.get(field_name, "")).strip():
            errors.append(f"{field_name}_empty")
    if not str(witness.get("witness_id", "")).startswith("reflex-deployment-witness-"):
        errors.append("witness_id_not_reflex_deployment_witness")
    if not str(witness.get("signature", "")).startswith("hmac-sha256:"):
        errors.append("signature_not_hmac_sha256")
    if not isinstance(witness.get("health_refs"), list) or not witness.get("health_refs"):
        errors.append("health_refs_not_non_empty_list")
    if witness.get("production_mutation_applied") is not False:
        errors.append("production_mutation_applied_not_false")
    if expected_environment and witness.get("target_environment") != expected_environment:
        errors.append("target_environment_mismatch")
    if expected_candidate_id and witness.get("candidate_id") != expected_candidate_id:
        errors.append("candidate_id_mismatch")
    return errors


def _invalid(
    witness_path: Path,
    detail: str,
    blockers: tuple[str, ...],
) -> ReflexDeploymentWitnessValidation:
    return ReflexDeploymentWitnessValidation(
        valid=False,
        witness_path="<provided>",
        status="failed",
        witness_id="",
        candidate_id="",
        certificate_id="",
        target_environment="",
        detail=detail,
        blockers=blockers,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--witness", required=True, type=Path, help="Path to Reflex deployment witness JSON")
    parser.add_argument(
        "--signing-secret",
        default=os.environ.get("MULLU_REFLEX_DEPLOYMENT_WITNESS_SECRET", ""),
        help="HMAC signing secret; defaults to MULLU_REFLEX_DEPLOYMENT_WITNESS_SECRET",
    )
    parser.add_argument("--expected-environment", default="", help="Optional expected target environment")
    parser.add_argument("--expected-candidate-id", default="", help="Optional expected Reflex candidate id")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Reflex deployment witness validator."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.signing_secret:
        validation = _invalid(
            args.witness,
            "signing secret required",
            ("reflex_witness_signing_secret_missing",),
        )
    else:
        validation = validate_reflex_deployment_witness(
            args.witness,
            signing_secret=args.signing_secret,
            expected_environment=args.expected_environment,
            expected_candidate_id=args.expected_candidate_id,
        )
    payload = validation.as_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload['status']}: {payload['detail']}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
