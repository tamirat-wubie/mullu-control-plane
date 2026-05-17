#!/usr/bin/env python3
"""Apply public deployment status only after verified witness evidence.

Purpose: convert a published deployment witness into the matching
DEPLOYMENT_STATUS.md public health declaration.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: DEPLOYMENT_STATUS.md, deployment_witness.json, and the deployment
publication closure validator.
Invariants:
  - Status mutation requires a non-empty operator approval reference.
  - Status mutation requires a schema-valid published deployment witness.
  - Public health declaration must match the witness public health endpoint.
  - Dry-run mode validates the full candidate without writing files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_deployment_publication_closure import (  # noqa: E402
    DEFAULT_DEPLOYMENT_STATUS_PATH,
    DEFAULT_WITNESS_PATH,
    DEPLOYMENT_STATE_PATTERN,
    PUBLIC_HEALTH_PATTERN,
    _validate_witness_schema,
    load_witness_payload,
    validate_publication_closure,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_DECLARATION_RECEIPT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "public_production_health_declaration.json"
)
PUBLIC_PRODUCTION_HEALTH_DECLARATION_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "public_production_health_declaration.schema.json"
)
LAST_AUDITED_PATTERN = re.compile(
    r"^\*\*Last audited:\*\*\s+[0-9]{4}-[0-9]{2}-[0-9]{2}$",
    re.MULTILINE,
)
AUDITED_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


@dataclass(frozen=True, slots=True)
class DeploymentPublicationStatusApplication:
    """Result of one evidence-gated public deployment status application."""

    deployment_status_path: str
    witness_path: str
    dry_run: bool
    updated: bool
    deployment_witness_state: str
    public_health_endpoint: str
    operator_approval_ref: str
    errors: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable application receipt."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def apply_deployment_publication_status(
    *,
    deployment_status_path: Path = DEFAULT_DEPLOYMENT_STATUS_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
    operator_approval_ref: str,
    audited_at: str = "",
    dry_run: bool = False,
) -> DeploymentPublicationStatusApplication:
    """Apply a published deployment witness to DEPLOYMENT_STATUS.md."""
    errors: list[str] = []
    approval_ref = operator_approval_ref.strip()
    if not approval_ref:
        errors.append("operator approval reference required")

    try:
        status_text = deployment_status_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        status_text = ""
        errors.append(f"{deployment_status_path}: deployment status document missing")

    witness_payload, witness_errors = load_witness_payload(witness_path)
    errors.extend(witness_errors)
    if witness_payload is None:
        errors.append(f"{witness_path}: deployment witness artifact required")

    publication_endpoint = ""
    candidate_text = status_text
    if witness_payload is not None:
        errors.extend(_validate_witness_schema(witness_payload, witness_path))
        publication_endpoint = str(witness_payload.get("public_health_endpoint", "")).strip()
        if not publication_endpoint:
            errors.append(f"{witness_path}: public_health_endpoint must be non-empty")
        candidate_text, candidate_errors = _published_status_candidate(
            status_text=status_text,
            witness_payload=witness_payload,
            audited_at=_resolved_audited_date(audited_at),
        )
        errors.extend(candidate_errors)
        if not candidate_errors:
            errors.extend(
                validate_publication_closure(
                    deployment_status_text=candidate_text,
                    witness_payload=witness_payload,
                    witness_path=witness_path,
                )
            )

    bounded_errors = tuple(
        _bounded_error(
            error,
            deployment_status_path=deployment_status_path,
            witness_path=witness_path,
        )
        for error in errors
    )
    updated = False
    if not bounded_errors and not dry_run:
        deployment_status_path.write_text(candidate_text, encoding="utf-8")
        updated = True

    return DeploymentPublicationStatusApplication(
        deployment_status_path=_bounded_path(
            deployment_status_path,
            default_path=DEFAULT_DEPLOYMENT_STATUS_PATH,
            default_label="DEPLOYMENT_STATUS.md",
            provided_label="provided_deployment_status",
        ),
        witness_path=_bounded_path(
            witness_path,
            default_path=DEFAULT_WITNESS_PATH,
            default_label=".change_assurance/deployment_witness.json",
            provided_label="provided_witness",
        ),
        dry_run=dry_run,
        updated=updated,
        deployment_witness_state="published" if not bounded_errors else "",
        public_health_endpoint=publication_endpoint if not bounded_errors else "",
        operator_approval_ref=approval_ref if not bounded_errors else "",
        errors=bounded_errors,
    )


def write_deployment_publication_status_application(
    application: DeploymentPublicationStatusApplication,
    output_path: Path,
) -> Path:
    """Write one public-health declaration application receipt."""
    schema_errors = _validate_application_schema(application)
    if schema_errors:
        raise RuntimeError(
            "public production health declaration schema failed: "
            f"{len(schema_errors)} schema error(s)"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(application.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_application_schema(
    application: DeploymentPublicationStatusApplication,
) -> list[str]:
    """Validate the declaration receipt against its public schema."""
    schema = _load_schema(PUBLIC_PRODUCTION_HEALTH_DECLARATION_SCHEMA_PATH)
    return _validate_schema_instance(schema, application.to_json_dict())


def _published_status_candidate(
    *,
    status_text: str,
    witness_payload: dict[str, Any],
    audited_at: str,
) -> tuple[str, list[str]]:
    errors: list[str] = []
    public_health_endpoint = str(witness_payload.get("public_health_endpoint", "")).strip()
    candidate = _replace_required_line(
        text=status_text,
        pattern=DEPLOYMENT_STATE_PATTERN,
        replacement="**Deployment witness state:** `published`",
        label="Deployment witness state",
        errors=errors,
    )
    candidate = _replace_required_line(
        text=candidate,
        pattern=PUBLIC_HEALTH_PATTERN,
        replacement=f"**Public production health endpoint:** `{public_health_endpoint}`",
        label="Public production health endpoint",
        errors=errors,
    )
    if LAST_AUDITED_PATTERN.search(candidate):
        candidate = LAST_AUDITED_PATTERN.sub(f"**Last audited:** {audited_at}", candidate)
    return candidate, errors


def _replace_required_line(
    *,
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    label: str,
    errors: list[str],
) -> str:
    if pattern.search(text) is None:
        errors.append(f"DEPLOYMENT_STATUS.md missing field: {label}")
        return text
    return pattern.sub(replacement, text, count=1)


def _resolved_audited_date(audited_at: str) -> str:
    candidate = audited_at.strip() or datetime.now(timezone.utc).date().isoformat()
    if AUDITED_DATE_PATTERN.fullmatch(candidate) is None:
        raise ValueError("audited_at must use YYYY-MM-DD")
    return candidate


def _bounded_path(
    path: Path,
    *,
    default_path: Path,
    default_label: str,
    provided_label: str,
) -> str:
    return default_label if path == default_path else provided_label


def _bounded_error(
    error: str,
    *,
    deployment_status_path: Path,
    witness_path: Path,
) -> str:
    deployment_status_label = _bounded_path(
        deployment_status_path,
        default_path=DEFAULT_DEPLOYMENT_STATUS_PATH,
        default_label="DEPLOYMENT_STATUS.md",
        provided_label="provided_deployment_status",
    )
    witness_label = _bounded_path(
        witness_path,
        default_path=DEFAULT_WITNESS_PATH,
        default_label=".change_assurance/deployment_witness.json",
        provided_label="provided_witness",
    )
    return error.replace(str(deployment_status_path), deployment_status_label).replace(
        str(witness_path),
        witness_label,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment publication status application arguments."""
    parser = argparse.ArgumentParser(
        description="Apply public deployment status after verified witness evidence.",
    )
    parser.add_argument("--deployment-status", default=str(DEFAULT_DEPLOYMENT_STATUS_PATH))
    parser.add_argument("--witness", default=str(DEFAULT_WITNESS_PATH))
    parser.add_argument(
        "--operator-approval-ref",
        default=os.environ.get("MULLU_DEPLOYMENT_PUBLICATION_APPROVAL_REF", ""),
    )
    parser.add_argument("--audited-at", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--receipt-output", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for evidence-gated deployment status application."""
    args = parse_args(argv)
    try:
        application = apply_deployment_publication_status(
            deployment_status_path=Path(args.deployment_status),
            witness_path=Path(args.witness),
            operator_approval_ref=args.operator_approval_ref,
            audited_at=args.audited_at,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    if args.receipt_output:
        write_deployment_publication_status_application(
            application,
            Path(args.receipt_output),
        )
    if args.json:
        print(json.dumps(application.to_json_dict(), indent=2, sort_keys=True))
    else:
        _print_application(application)
    return 0 if not application.errors else 1


def _print_application(application: DeploymentPublicationStatusApplication) -> None:
    print("=== Deployment Publication Status Application ===")
    print(f"  deployment status: {application.deployment_status_path}")
    print(f"  witness:           {application.witness_path}")
    print(f"  dry_run:           {str(application.dry_run).lower()}")
    print(f"  updated:           {str(application.updated).lower()}")
    if application.errors:
        print(f"\nFAILED - {len(application.errors)} error(s):")
        for error in application.errors:
            print(f"  X {error}")
        return
    print("\nDEPLOYMENT PUBLICATION STATUS APPLICATION OK")


if __name__ == "__main__":
    raise SystemExit(main())
