#!/usr/bin/env python3
"""Validate terminal closure certificate artifacts.

Purpose: keep final command disposition proof machine-readable, schema-valid,
and bounded to one terminal closure path.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/terminal_closure_certificate.json,
schemas/terminal_closure_certificate.schema.json.
Invariants:
  - A certificate must validate against the public terminal closure schema.
  - Committed closure must not carry compensation or accepted-risk proof.
  - Non-committed dispositions must carry their required case or recovery proof.
  - Evidence references are reported by count only, not dereferenced.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_CERTIFICATE = REPO_ROOT / "examples" / "terminal_closure_certificate.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "terminal_closure_certificate.schema.json"
VALID_DISPOSITIONS = frozenset({"committed", "compensated", "accepted_risk", "requires_review"})


@dataclass(frozen=True, slots=True)
class TerminalClosureCertificateValidation:
    """Validation result for one terminal closure certificate."""

    valid: bool
    certificate_id: str
    certificate_path: str
    schema_path: str
    disposition: str
    evidence_ref_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_terminal_closure_certificate(
    *,
    certificate_path: Path = DEFAULT_CERTIFICATE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> TerminalClosureCertificateValidation:
    """Validate one terminal closure certificate artifact."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "terminal closure schema", errors)
    certificate = _load_json_object(certificate_path, "terminal closure certificate", errors)
    if not schema or not certificate:
        return _validation_result(certificate_path, schema_path, certificate, errors)

    errors.extend(_validate_schema_instance(schema, certificate))
    _validate_scalar_fields(certificate, errors)
    _validate_disposition_semantics(certificate, errors)
    return _validation_result(certificate_path, schema_path, certificate, errors)


def _validate_scalar_fields(certificate: dict[str, Any], errors: list[str]) -> None:
    disposition = certificate.get("disposition")
    if disposition not in VALID_DISPOSITIONS:
        errors.append(f"disposition must be one of {sorted(VALID_DISPOSITIONS)}")
    evidence_refs = certificate.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("evidence_refs must contain at least one proof reference")


def _validate_disposition_semantics(certificate: dict[str, Any], errors: list[str]) -> None:
    disposition = certificate.get("disposition")
    if disposition == "committed":
        for field_name in ("compensation_outcome_id", "accepted_risk_id"):
            if certificate.get(field_name):
                errors.append(f"committed closure must not include {field_name}")
    if disposition == "compensated" and not certificate.get("compensation_outcome_id"):
        errors.append("compensated closure requires compensation_outcome_id")
    if disposition == "accepted_risk":
        if not certificate.get("accepted_risk_id"):
            errors.append("accepted_risk closure requires accepted_risk_id")
        if not certificate.get("case_id"):
            errors.append("accepted_risk closure requires case_id")
    if disposition == "requires_review" and not certificate.get("case_id"):
        errors.append("requires_review closure requires case_id")


def _validation_result(
    certificate_path: Path,
    schema_path: Path,
    certificate: dict[str, Any],
    errors: list[str],
) -> TerminalClosureCertificateValidation:
    evidence_refs = certificate.get("evidence_refs", ())
    return TerminalClosureCertificateValidation(
        valid=not errors,
        certificate_id=str(certificate.get("certificate_id", "")),
        certificate_path=str(certificate_path),
        schema_path=str(schema_path),
        disposition=str(certificate.get("disposition", "")),
        evidence_ref_count=len(evidence_refs) if isinstance(evidence_refs, list) else 0,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} must be JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse terminal closure certificate validation arguments."""
    parser = argparse.ArgumentParser(description="Validate a terminal closure certificate.")
    parser.add_argument("--certificate", default=str(DEFAULT_CERTIFICATE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for terminal closure certificate validation."""
    args = parse_args(argv)
    result = validate_terminal_closure_certificate(
        certificate_path=Path(args.certificate),
        schema_path=Path(args.schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"terminal closure certificate ok disposition={result.disposition}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
