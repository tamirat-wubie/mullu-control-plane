#!/usr/bin/env python3
"""Validate Component Harness claim firewall records.

Purpose: prove public and product claims cannot outrun component authority,
proof, and fuse evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_claim_firewall.schema.json,
examples/component_claim_firewall.foundation.json, component passports, and
component authority fuses.
Invariants:
  - Blocked readiness/live claims remain blocked.
  - Evidence-bounded claims remain non-terminal and non-executing.
  - The checked example matches the deterministic runtime projection.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.component_claim_firewall import (  # noqa: E402
    ALLOWED_BOUNDED_CLAIMS,
    BLOCKED_CLAIMS,
    REQUIRED_VALIDATOR_REFS,
    build_component_claim_firewall,
)
from scripts.validate_component_authority_fuse import validate_component_authority_fuse  # noqa: E402
from scripts.validate_component_passports import validate_component_passports  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_claim_firewall.schema.json"
DEFAULT_FIREWALL = REPO_ROOT / "examples" / "component_claim_firewall.foundation.json"
DEFAULT_PASSPORTS = REPO_ROOT / "examples" / "component_passports.foundation.json"
DEFAULT_AUTHORITY_FUSE = REPO_ROOT / "examples" / "component_authority_fuse.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_claim_firewall_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_claim_firewall_validator": "python scripts/validate_component_claim_firewall.py",
    "component_claim_firewall_tests": "python -m pytest tests/test_validate_component_claim_firewall.py -q",
}


@dataclass(frozen=True, slots=True)
class ComponentClaimFirewallValidation:
    """Validation report for component claim firewall records."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    firewall_path: str
    passports_path: str
    authority_fuse_path: str
    claim_check_count: int
    blocked_claim_count: int
    allowed_bounded_claim_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_claim_firewall(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    firewall_path: Path = DEFAULT_FIREWALL,
    passports_path: Path = DEFAULT_PASSPORTS,
    authority_fuse_path: Path = DEFAULT_AUTHORITY_FUSE,
) -> ComponentClaimFirewallValidation:
    """Validate claim firewall records against passports and authority fuses."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component claim firewall schema", errors)
    firewall = _load_json_object(firewall_path, "component claim firewall example", errors)
    passports = _load_json_object(passports_path, "component passports example", errors)
    authority_fuse = _load_json_object(authority_fuse_path, "component authority fuse example", errors)

    passport_validation = validate_component_passports(passport_path=passports_path)
    if not passport_validation.ok:
        errors.extend(f"component passport validation failed: {error}" for error in passport_validation.errors)
    fuse_validation = validate_component_authority_fuse(fuse_path=authority_fuse_path, passports_path=passports_path)
    if not fuse_validation.ok:
        errors.extend(f"component authority fuse validation failed: {error}" for error in fuse_validation.errors)

    runtime_firewall = (
        build_component_claim_firewall(
            passports_path=passports_path,
            authority_fuse_path=authority_fuse_path,
        )
        if passports and authority_fuse
        else {}
    )
    if schema and firewall:
        errors.extend(f"{_path_label(firewall_path)}: {error}" for error in _validate_schema_instance(schema, firewall))
        if firewall != runtime_firewall:
            errors.append(f"{_path_label(firewall_path)}: example does not match runtime projection")
    if firewall and passports and authority_fuse:
        _validate_firewall(firewall, passports, authority_fuse, errors, _path_label(firewall_path))

    claim_checks = firewall.get("claim_checks", ()) if isinstance(firewall, dict) else ()
    blocked_count = sum(
        1 for claim_check in claim_checks if isinstance(claim_check, dict) and claim_check.get("decision") == "blocked"
    )
    allowed_count = sum(
        1
        for claim_check in claim_checks
        if isinstance(claim_check, dict) and claim_check.get("decision") == "allowed_bounded"
    )
    return ComponentClaimFirewallValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        firewall_path=_path_label(firewall_path),
        passports_path=_path_label(passports_path),
        authority_fuse_path=_path_label(authority_fuse_path),
        claim_check_count=len(claim_checks) if isinstance(claim_checks, list) else 0,
        blocked_claim_count=blocked_count,
        allowed_bounded_claim_count=allowed_count,
    )


def write_component_claim_firewall_validation(
    validation: ComponentClaimFirewallValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic component claim firewall validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_firewall(
    firewall: dict[str, Any],
    passports: dict[str, Any],
    authority_fuse: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if firewall.get("firewall_is_not_execution_authority") is not True:
        errors.append(f"{label}: firewall_is_not_execution_authority must be true")
    for flag_name in ("live_execution_enabled", "live_connector_send_enabled"):
        if firewall.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    if firewall.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    if tuple(_string_list(firewall.get("blocked_claims"))) != BLOCKED_CLAIMS:
        errors.append(f"{label}: blocked_claims must match canonical blocked claim list")
    if tuple(_string_list(firewall.get("allowed_bounded_claims"))) != ALLOWED_BOUNDED_CLAIMS:
        errors.append(f"{label}: allowed_bounded_claims must match canonical allowed bounded claim list")
    _validate_validators(firewall, errors, label)
    _validate_authority_fuses(authority_fuse, errors, label)

    passport_by_component = _passport_by_component(passports, errors, label)
    claim_checks = firewall.get("claim_checks")
    if not isinstance(claim_checks, list):
        errors.append(f"{label}: claim_checks must be a list")
        return
    seen_claim_texts: set[str] = set()
    for claim_check in claim_checks:
        if not isinstance(claim_check, dict):
            errors.append(f"{label}: claim check entries must be objects")
            continue
        claim_text = str(claim_check.get("claim_text", ""))
        if claim_text in seen_claim_texts:
            errors.append(f"{label}: duplicate claim check {claim_text}")
        seen_claim_texts.add(claim_text)
        _validate_claim_check(claim_check, passport_by_component, errors, label)

    missing_blocked = sorted(set(BLOCKED_CLAIMS) - seen_claim_texts)
    missing_allowed = sorted(set(ALLOWED_BOUNDED_CLAIMS) - seen_claim_texts)
    extra_claims = sorted(seen_claim_texts - set(BLOCKED_CLAIMS) - set(ALLOWED_BOUNDED_CLAIMS))
    if missing_blocked:
        errors.append(f"{label}: missing blocked claims {missing_blocked}")
    if missing_allowed:
        errors.append(f"{label}: missing allowed bounded claims {missing_allowed}")
    if extra_claims:
        errors.append(f"{label}: unknown claim checks {extra_claims}")


def _validate_claim_check(
    claim_check: dict[str, Any],
    passport_by_component: dict[str, dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    claim_text = str(claim_check.get("claim_text", ""))
    if claim_check.get("claim_is_not_execution_authority") is not True:
        errors.append(f"{label}: claim {claim_text} claim_is_not_execution_authority must be true")
    if claim_check.get("terminal_closure_allowed") is not False:
        errors.append(f"{label}: claim {claim_text} terminal_closure_allowed must be false")
    validator_refs = set(_string_list(claim_check.get("required_validator_refs")))
    for validator_ref in REQUIRED_VALIDATOR_REFS:
        if validator_ref not in validator_refs:
            errors.append(f"{label}: claim {claim_text} must require {validator_ref}")
    for component_id in _string_list(claim_check.get("blocking_component_ids")):
        if component_id not in passport_by_component:
            errors.append(f"{label}: claim {claim_text} blocks unknown component {component_id}")
    if claim_text in BLOCKED_CLAIMS:
        if claim_check.get("decision") != "blocked":
            errors.append(f"{label}: claim {claim_text} decision must be blocked")
        if claim_check.get("outcome") != "GovernanceBlocked":
            errors.append(f"{label}: claim {claim_text} outcome must be GovernanceBlocked")
        if not _string_list(claim_check.get("blocking_component_ids")):
            errors.append(f"{label}: blocked claim {claim_text} must name blocking components")
    elif claim_text in ALLOWED_BOUNDED_CLAIMS:
        if claim_check.get("decision") != "allowed_bounded":
            errors.append(f"{label}: claim {claim_text} decision must be allowed_bounded")
        if claim_check.get("outcome") != "SolvedVerified":
            errors.append(f"{label}: claim {claim_text} outcome must be SolvedVerified")
        if _string_list(claim_check.get("blocking_component_ids")):
            errors.append(f"{label}: allowed bounded claim {claim_text} must not name blocking components")
        if not _string_list(claim_check.get("evidence_refs")):
            errors.append(f"{label}: allowed bounded claim {claim_text} must carry evidence_refs")


def _validate_validators(firewall: dict[str, Any], errors: list[str], label: str) -> None:
    validators = firewall.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id: dict[str, dict[str, Any]] = {}
    for validator in validators:
        if not isinstance(validator, dict):
            errors.append(f"{label}: validator entries must be objects")
            continue
        validator_by_id[str(validator.get("validator_id", ""))] = validator
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _validate_authority_fuses(authority_fuse: dict[str, Any], errors: list[str], label: str) -> None:
    fuses = authority_fuse.get("fuses")
    if not isinstance(fuses, list):
        errors.append(f"{label}: authority fuse source must carry fuses list")
        return
    for fuse in fuses:
        if not isinstance(fuse, dict):
            errors.append(f"{label}: authority fuse entries must be objects")
            continue
        component_id = str(fuse.get("component_id", ""))
        for field_name in (
            "self_upgrade_allowed",
            "can_upgrade_authority",
            "can_mutate_authority_envelope",
            "can_enable_live_action",
            "terminal_closure_allowed",
        ):
            if fuse.get(field_name) is not False:
                errors.append(f"{label}: component {component_id} source fuse {field_name} must be false")
        if fuse.get("decision") != "blocked":
            errors.append(f"{label}: component {component_id} source fuse decision must be blocked")


def _passport_by_component(
    passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    entries = passports.get("passports")
    if not isinstance(entries, list):
        errors.append(f"{label}: passports must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for passport in entries:
        if not isinstance(passport, dict):
            errors.append(f"{label}: passport entries must be objects")
            continue
        component_id = passport.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            errors.append(f"{label}: passport entries must carry component_id")
            continue
        result[component_id] = passport
    return result


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse component claim firewall validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness claim firewall records.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--firewall", default=str(DEFAULT_FIREWALL))
    parser.add_argument("--passports", default=str(DEFAULT_PASSPORTS))
    parser.add_argument("--authority-fuse", default=str(DEFAULT_AUTHORITY_FUSE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component claim firewall validation."""

    args = parse_args(argv)
    validation = validate_component_claim_firewall(
        schema_path=Path(args.schema),
        firewall_path=Path(args.firewall),
        passports_path=Path(args.passports),
        authority_fuse_path=Path(args.authority_fuse),
    )
    write_component_claim_firewall_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT CLAIM FIREWALL VALID")
    else:
        print(f"COMPONENT CLAIM FIREWALL INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
