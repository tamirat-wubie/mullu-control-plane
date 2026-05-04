#!/usr/bin/env python3
"""Validate deployment publication claims against collected witness evidence.

Purpose: keep the public deployment status claim causally tied to the live
deployment witness artifact.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: DEPLOYMENT_STATUS.md and .change_assurance/deployment_witness.json.
Invariants:
  - The repository may stay not-published without a witness artifact.
  - A published deployment claim requires a published witness artifact.
  - Published public endpoints must be HTTPS production URLs.
  - Published witnesses require verified runtime and conformance signatures.
  - Published witnesses require an explicit passing gateway health step.
  - Published witnesses require every collection step to pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_DEPLOYMENT_STATUS_PATH = REPO_ROOT / "DEPLOYMENT_STATUS.md"
DEFAULT_WITNESS_PATH = REPO_ROOT / ".change_assurance" / "deployment_witness.json"
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "deployment_publication_closure_validation.json"
)
DEPLOYMENT_WITNESS_SCHEMA_PATH = REPO_ROOT / "schemas" / "deployment_witness.schema.json"
DEPLOYMENT_STATE_PATTERN = re.compile(
    r"^\*\*Deployment witness state:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)
PUBLIC_HEALTH_PATTERN = re.compile(
    r"^\*\*Public production health endpoint:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)
HEALTH_RESPONSE_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
VALID_DEPLOYMENT_STATES = frozenset({"not-published", "published"})
REQUIRED_PUBLISHED_FIELDS = (
    "witness_id",
    "gateway_url",
    "public_health_endpoint",
    "health_http_status",
    "health_response_digest",
    "deployment_claim",
    "health_status",
    "runtime_witness_status",
    "signature_status",
    "conformance_status",
    "conformance_signature_status",
    "latest_conformance_certificate_id",
    "latest_terminal_certificate_id",
    "latest_command_event_hash",
    "runtime_witness_id",
    "runtime_environment",
    "runtime_signature_key_id",
    "runtime_responsibility_debt_clear",
    "authority_responsibility_debt_clear",
    "authority_pending_approval_chain_count",
    "authority_overdue_approval_chain_count",
    "authority_open_obligation_count",
    "authority_overdue_obligation_count",
    "authority_escalated_obligation_count",
    "authority_unowned_high_risk_capability_count",
    "steps",
)


@dataclass(frozen=True, slots=True)
class DeploymentPublicationClosureValidation:
    """Structured validation report for deployment publication closure."""

    deployment_status_path: str
    witness_path: str
    valid: bool
    errors: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_publication_closure(
    *,
    deployment_status_text: str,
    witness_payload: dict[str, Any] | None,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    """Validate that public deployment status has matching witness evidence."""
    errors: list[str] = []
    deployment_state = _extract_required_field(
        deployment_status_text,
        DEPLOYMENT_STATE_PATTERN,
        "Deployment witness state",
        errors,
    )
    public_health_endpoint = _extract_required_field(
        deployment_status_text,
        PUBLIC_HEALTH_PATTERN,
        "Public production health endpoint",
        errors,
    )
    if deployment_state is None or public_health_endpoint is None:
        return errors
    if deployment_state not in VALID_DEPLOYMENT_STATES:
        errors.append(f"deployment witness state is unsupported: {deployment_state!r}")
        return errors

    if deployment_state == "not-published":
        if public_health_endpoint != "not-declared":
            errors.append(
                "not-published deployment must keep public production health "
                "endpoint not-declared"
            )
        if witness_payload is not None and witness_payload.get("deployment_claim") == "published":
            errors.append(
                f"{witness_path}: published witness conflicts with not-published status"
            )
        return errors

    if public_health_endpoint == "not-declared":
        errors.append("published deployment requires a declared public health endpoint")
    if witness_payload is None:
        errors.append(f"{witness_path}: published deployment requires witness artifact")
        return errors

    errors.extend(_validate_published_witness(witness_payload, witness_path))
    errors.extend(
        _validate_public_health_matches_witness(
            public_health_endpoint=public_health_endpoint,
            witness_payload=witness_payload,
            witness_path=witness_path,
        )
    )
    return errors


def load_witness_payload(witness_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load a witness artifact if present, returning explicit parse errors."""
    if not witness_path.exists():
        return None, []
    try:
        parsed = json.loads(witness_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, [f"{witness_path}: witness JSON parse failed"]
    if not isinstance(parsed, dict):
        return None, [f"{witness_path}: witness JSON root must be an object"]
    return parsed, []


def validate_deployment_publication_closure_report(
    *,
    deployment_status_path: Path = DEFAULT_DEPLOYMENT_STATUS_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> DeploymentPublicationClosureValidation:
    """Build one deterministic deployment publication closure validation report."""
    errors: list[str] = []
    if not deployment_status_path.exists():
        errors.append(f"{deployment_status_path}: deployment status document missing")
        deployment_status_text = ""
    else:
        deployment_status_text = deployment_status_path.read_text(encoding="utf-8")

    witness_payload, witness_errors = load_witness_payload(witness_path)
    errors.extend(witness_errors)
    if deployment_status_text:
        if witness_payload is not None:
            errors.extend(_validate_witness_schema(witness_payload, witness_path))
        errors.extend(
            validate_publication_closure(
                deployment_status_text=deployment_status_text,
                witness_payload=witness_payload,
                witness_path=witness_path,
            )
        )

    return DeploymentPublicationClosureValidation(
        deployment_status_path=_bounded_deployment_status_path(deployment_status_path),
        witness_path=_bounded_witness_path(witness_path),
        valid=not errors,
        errors=tuple(
            _bounded_report_error(
                error,
                deployment_status_path=deployment_status_path,
                witness_path=witness_path,
            )
            for error in errors
        ),
    )


def write_deployment_publication_closure_validation_report(
    validation: DeploymentPublicationClosureValidation,
    output_path: Path,
) -> Path:
    """Write one deployment publication closure validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _bounded_deployment_status_path(deployment_status_path: Path) -> str:
    """Return a public-safe deployment status path label for validation reports."""
    if deployment_status_path == DEFAULT_DEPLOYMENT_STATUS_PATH:
        return "DEPLOYMENT_STATUS.md"
    return "provided_deployment_status"


def _bounded_witness_path(witness_path: Path) -> str:
    """Return a public-safe witness path label for validation reports."""
    if witness_path == DEFAULT_WITNESS_PATH:
        return ".change_assurance/deployment_witness.json"
    return "provided_witness"


def _bounded_report_error(
    error: str,
    *,
    deployment_status_path: Path,
    witness_path: Path,
) -> str:
    """Return a public-safe error for structured validation reports."""
    bounded = (
        error.replace(
            str(deployment_status_path),
            _bounded_deployment_status_path(deployment_status_path),
        )
        .replace(str(witness_path), _bounded_witness_path(witness_path))
    )
    prefix, detail = _split_public_error_prefix(bounded)
    return f"{prefix}{_bounded_report_error_detail(detail)}"


def _split_public_error_prefix(error: str) -> tuple[str, str]:
    for prefix in (
        "DEPLOYMENT_STATUS.md: ",
        "provided_deployment_status: ",
        ".change_assurance/deployment_witness.json: ",
        "provided_witness: ",
    ):
        if error.startswith(prefix):
            return prefix, error.removeprefix(prefix)
    return "", error


def _bounded_report_error_detail(error_detail: str) -> str:
    if error_detail.startswith("schema contract:"):
        return "schema contract validation failed"
    if error_detail.startswith("deployment witness state is unsupported"):
        return "deployment witness state is unsupported"
    if error_detail.startswith("missing published witness fields:"):
        return error_detail
    if error_detail in {
        "deployment status document missing",
        "not-published deployment must keep public production health endpoint not-declared",
        "published witness conflicts with not-published status",
        "published deployment requires a declared public health endpoint",
        "published deployment requires witness artifact",
        "witness JSON parse failed",
        "witness JSON root must be an object",
        "published gateway_url must not be localhost",
        "published gateway_url must use https",
        "health_response_digest must be a sha256 digest",
        "authority responsibility debt must be clear",
        "runtime responsibility debt must be clear",
        "steps must be a non-empty list",
        "published witness requires passing gateway health step",
        "public production health endpoint must use https",
    }:
        return error_detail
    if error_detail.startswith("DEPLOYMENT_STATUS.md missing field:"):
        return error_detail
    if error_detail.startswith("health_http_status "):
        return "health_http_status mismatch"
    if error_detail.startswith("witness step failed:"):
        return "witness step failed"
    if error_detail.startswith("steps[") and error_detail.endswith(" must be an object"):
        return "witness step malformed"
    if error_detail.startswith("witness public health endpoint does not match"):
        return "witness public health endpoint mismatch"
    if error_detail.startswith("public production health endpoint does not match"):
        return "public production health endpoint mismatch"
    if " != " in error_detail:
        field_name = error_detail.split(" ", 1)[0]
        if field_name in REQUIRED_PUBLISHED_FIELDS:
            return f"{field_name} mismatch"
    if error_detail.endswith(" must be non-empty"):
        field_name = error_detail.removesuffix(" must be non-empty")
        if field_name in REQUIRED_PUBLISHED_FIELDS:
            return error_detail
    for field_name in (
        "authority_overdue_approval_chain_count",
        "authority_overdue_obligation_count",
        "authority_escalated_obligation_count",
        "authority_unowned_high_risk_capability_count",
    ):
        if error_detail.startswith(f"{field_name} "):
            return f"{field_name} must be zero"
    return "deployment publication closure validation failed"


def _validate_witness_schema(
    witness_payload: dict[str, Any],
    witness_path: Path,
) -> list[str]:
    schema = _load_schema(DEPLOYMENT_WITNESS_SCHEMA_PATH)
    return [
        f"{witness_path}: schema contract: {error}"
        for error in _validate_schema_instance(schema, witness_payload)
    ]


def _validate_published_witness(
    witness_payload: dict[str, Any],
    witness_path: Path,
) -> list[str]:
    errors: list[str] = []
    missing_fields = tuple(
        field for field in REQUIRED_PUBLISHED_FIELDS if field not in witness_payload
    )
    if missing_fields:
        errors.append(f"{witness_path}: missing published witness fields: {list(missing_fields)}")

    required_values = {
        "deployment_claim": "published",
        "health_status": "healthy",
        "runtime_witness_status": "healthy",
        "signature_status": "verified",
        "conformance_signature_status": "verified",
    }
    for field_name, expected_value in required_values.items():
        observed_value = witness_payload.get(field_name)
        if observed_value != expected_value:
            errors.append(
                f"{witness_path}: {field_name} {observed_value!r} != {expected_value!r}"
            )

    for field_name in (
        "witness_id",
        "gateway_url",
        "public_health_endpoint",
        "latest_conformance_certificate_id",
        "latest_terminal_certificate_id",
        "latest_command_event_hash",
        "runtime_witness_id",
        "runtime_environment",
        "runtime_signature_key_id",
    ):
        if not str(witness_payload.get(field_name, "")).strip():
            errors.append(f"{witness_path}: {field_name} must be non-empty")

    gateway_url = str(witness_payload.get("gateway_url", ""))
    if gateway_url.startswith(("http://localhost", "http://127.0.0.1")):
        errors.append(f"{witness_path}: published gateway_url must not be localhost")
    if gateway_url and not gateway_url.startswith("https://"):
        errors.append(f"{witness_path}: published gateway_url must use https")
    health_http_status = witness_payload.get("health_http_status")
    if health_http_status != 200:
        errors.append(f"{witness_path}: health_http_status {health_http_status!r} != 200")
    health_response_digest = str(witness_payload.get("health_response_digest", ""))
    if HEALTH_RESPONSE_DIGEST_PATTERN.fullmatch(health_response_digest) is None:
        errors.append(f"{witness_path}: health_response_digest must be a sha256 digest")
    if witness_payload.get("authority_responsibility_debt_clear") is not True:
        errors.append(f"{witness_path}: authority responsibility debt must be clear")
    if witness_payload.get("runtime_responsibility_debt_clear") is not True:
        errors.append(f"{witness_path}: runtime responsibility debt must be clear")
    for field_name in (
        "authority_overdue_approval_chain_count",
        "authority_overdue_obligation_count",
        "authority_escalated_obligation_count",
        "authority_unowned_high_risk_capability_count",
    ):
        if witness_payload.get(field_name) != 0:
            errors.append(f"{witness_path}: {field_name} {witness_payload.get(field_name)!r} != 0")

    steps = witness_payload.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append(f"{witness_path}: steps must be a non-empty list")
        return errors
    health_step_passed = False
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"{witness_path}: steps[{index}] must be an object")
            continue
        step_name = str(step.get("name", "")).strip().lower()
        if step_name == "gateway health" and step.get("passed") is True:
            health_step_passed = True
        if step.get("passed") is not True:
            reported_step_name = step.get("name", f"steps[{index}]")
            errors.append(f"{witness_path}: witness step failed: {reported_step_name}")
    if not health_step_passed:
        errors.append(f"{witness_path}: published witness requires passing gateway health step")
    return errors


def _validate_public_health_matches_witness(
    *,
    public_health_endpoint: str,
    witness_payload: dict[str, Any],
    witness_path: Path,
) -> list[str]:
    gateway_url = str(witness_payload.get("gateway_url", "")).rstrip("/")
    if not gateway_url:
        return []
    if not gateway_url.startswith("https://"):
        return []
    witness_health_endpoint = str(witness_payload.get("public_health_endpoint", "")).strip()
    expected_health_endpoint = witness_health_endpoint or f"{gateway_url}/health"
    if witness_health_endpoint and witness_health_endpoint != f"{gateway_url}/health":
        return [
            "witness public health endpoint does not match witness gateway URL: "
            f"{witness_health_endpoint!r} != {gateway_url + '/health'!r} "
            f"from {witness_path}"
        ]
    if not public_health_endpoint.startswith("https://"):
        return ["public production health endpoint must use https"]
    if public_health_endpoint != expected_health_endpoint:
        return [
            "public production health endpoint does not match witness gateway URL: "
            f"{public_health_endpoint!r} != {expected_health_endpoint!r} "
            f"from {witness_path}"
        ]
    return []


def _extract_required_field(
    text: str,
    pattern: re.Pattern[str],
    label: str,
    errors: list[str],
) -> str | None:
    match = pattern.search(text)
    if match is None:
        errors.append(f"DEPLOYMENT_STATUS.md missing field: {label}")
        return None
    return match.group(1).strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for deployment publication closure validation."""
    parser = argparse.ArgumentParser(
        description="Validate deployment publication status against witness evidence.",
    )
    parser.add_argument(
        "--deployment-status",
        default=str(DEFAULT_DEPLOYMENT_STATUS_PATH),
        help="Path to DEPLOYMENT_STATUS.md.",
    )
    parser.add_argument(
        "--witness",
        default=str(DEFAULT_WITNESS_PATH),
        help="Path to collected deployment witness JSON.",
    )
    parser.add_argument(
        "--output",
        default="",
        help=(
            "Optional path for a structured validation report. "
            f"Suggested: {DEFAULT_VALIDATION_OUTPUT}"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment publication closure validation."""
    args = parse_args(argv)
    deployment_status_path = Path(args.deployment_status)
    witness_path = Path(args.witness)
    validation = validate_deployment_publication_closure_report(
        deployment_status_path=deployment_status_path,
        witness_path=witness_path,
    )
    if args.output:
        write_deployment_publication_closure_validation_report(
            validation,
            Path(args.output),
        )

    print("=== Deployment Publication Closure Validation ===")
    print(f"  deployment status: {deployment_status_path}")
    print(f"  witness:           {witness_path}")
    if not validation.valid:
        print(f"\nFAILED - {len(validation.errors)} error(s):")
        for error in validation.errors:
            print(f"  X {error}")
        return 1
    print("\nDEPLOYMENT PUBLICATION CLOSURE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
