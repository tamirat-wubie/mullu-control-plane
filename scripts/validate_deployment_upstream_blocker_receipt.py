#!/usr/bin/env python3
"""Validate a deployment upstream blocker receipt.

Purpose: fail closed when upstream API/DNS readiness evidence is malformed or
not ready for deployment witness publication.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: deployment_upstream_blocker_receipt.schema.json.
Invariants:
  - Receipt JSON must match the public upstream blocker contract.
  - Ready receipts require upstream SolvedVerified state and explicit API/DNS allowance.
  - Blocked receipts must preserve blockers and next actions.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_RECEIPT = REPO_ROOT / ".change_assurance" / "deployment_upstream_blocker_receipt.json"
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "deployment_upstream_blocker_receipt_validation.json"
)
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "deployment_upstream_blocker_receipt.schema.json"
RECEIPT_ID_PATTERN = re.compile(r"^deployment-upstream-blocker-[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True)
class DeploymentUpstreamBlockerValidation:
    """Validation result for one deployment upstream blocker receipt."""

    valid: bool
    ready: bool
    receipt_path: str
    schema_path: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation result."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_deployment_upstream_blocker_receipt(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> DeploymentUpstreamBlockerValidation:
    """Validate one deployment upstream blocker receipt."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "deployment upstream blocker receipt schema", errors)
    receipt = _load_json_object(receipt_path, "deployment upstream blocker receipt", errors)
    if schema and receipt:
        errors.extend(_validate_schema_instance(schema, receipt))
        _validate_semantics(receipt, errors)
        if require_ready and receipt.get("ready") is not True:
            errors.append("require ready: not-ready")
    ready = bool(receipt.get("ready") is True) if receipt else False
    next_action = _next_action(receipt) if receipt else "produce deployment upstream blocker receipt"
    return DeploymentUpstreamBlockerValidation(
        valid=not errors,
        ready=ready,
        receipt_path=str(receipt_path),
        schema_path=str(schema_path),
        errors=tuple(errors),
        next_action=next_action,
    )


def write_deployment_upstream_blocker_validation_report(
    validation: DeploymentUpstreamBlockerValidation,
    output_path: Path,
) -> Path:
    """Write one deployment upstream blocker validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(receipt: dict[str, Any], errors: list[str]) -> None:
    receipt_id = str(receipt.get("receipt_id", ""))
    if not RECEIPT_ID_PATTERN.fullmatch(receipt_id):
        errors.append("receipt_id must match deployment-upstream-blocker pattern")
    blockers = receipt.get("blockers", [])
    if receipt.get("ready") is True:
        if receipt.get("upstream_state") != "SolvedVerified":
            errors.append("ready receipt requires upstream_state=SolvedVerified")
        if receipt.get("api_provisioning_allowed") is not True:
            errors.append("ready receipt requires api_provisioning_allowed=true")
        if receipt.get("dns_publication_allowed") is not True:
            errors.append("ready receipt requires dns_publication_allowed=true")
        if blockers:
            errors.append("ready receipt must not carry blockers")
    else:
        if not blockers:
            errors.append("blocked receipt must carry blockers")
        if not receipt.get("next_actions"):
            errors.append("blocked receipt must carry next_actions")
    gateway_url = str(receipt.get("target_gateway_url", ""))
    gateway_host = str(receipt.get("target_gateway_host", ""))
    if gateway_url != f"https://{gateway_host}":
        errors.append("target_gateway_url must match target_gateway_host")


def _next_action(receipt: dict[str, Any]) -> str:
    if receipt.get("ready") is True:
        return "continue with gateway DNS target binding and resolution receipts"
    actions = receipt.get("next_actions", [])
    if isinstance(actions, list) and actions:
        return str(actions[0])
    return "complete upstream API readiness before DNS publication"


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {path}")
        return {}
    try:
        payload = _loads_strict_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment upstream blocker validation arguments."""
    parser = argparse.ArgumentParser(description="Validate a deployment upstream blocker receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment upstream blocker receipt validation."""
    args = parse_args(argv)
    validation = validate_deployment_upstream_blocker_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_deployment_upstream_blocker_validation_report(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("deployment upstream blocker receipt valid")
    else:
        print(f"deployment upstream blocker receipt invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
