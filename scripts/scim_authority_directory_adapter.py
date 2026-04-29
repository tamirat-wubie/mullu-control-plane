#!/usr/bin/env python3
"""SCIM authority directory adapter.

Purpose: transform a bounded SCIM export plus explicit authority mapping rules
into the normalized authority directory source consumed by
scripts/sync_authority_directory.py.
Governance scope: source evidence, explicit team ownership mappings,
approval-policy mappings, escalation-policy mappings, and rejected records.
Dependencies: standard-library JSON, hashing, argparse, pathlib.
Invariants:
  - SCIM users and groups are imported only as identity and membership evidence.
  - Authority ownership and policy records require explicit mapping rules.
  - Missing SCIM references are rejected instead of fabricated.
  - The adapter emits normalized JSON but never persists authority state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def convert_scim_authority_directory(
    *,
    tenant_id: str,
    scim_export_path: Path,
    mapping_path: Path,
    source_ref: str = "",
) -> dict[str, Any]:
    """Convert one SCIM export and explicit mapping file into normalized authority JSON."""
    tenant = tenant_id.strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    scim_payload = _load_json_mapping(scim_export_path, label="scim_export")
    mapping = _load_json_mapping(mapping_path, label="authority_mapping")
    scim_hash = _file_hash(scim_export_path)
    mapping_hash = _file_hash(mapping_path)
    source = source_ref.strip() or scim_export_path.resolve().as_uri()
    source_hash = f"sha256:{_stable_hash({'scim_hash': scim_hash, 'mapping_hash': mapping_hash})}"

    users = _scim_resources(scim_payload.get("Users", scim_payload.get("users", ())), "user")
    groups = _scim_resources(scim_payload.get("Groups", scim_payload.get("groups", ())), "group")
    users_by_id = {str(user["id"]): user for user in users}
    groups_by_name = {
        str(group.get("displayName", group["id"])): group
        for group in groups
    }
    rejected: list[dict[str, str]] = []

    teams = tuple(
        {
            "team_id": str(group["id"]),
            "display_name": str(group.get("displayName", group["id"])),
            "member_ids": tuple(
                str(member.get("value", ""))
                for member in group.get("members", ())
                if isinstance(member, dict) and str(member.get("value", "")).strip()
            ),
        }
        for group in groups
    )
    role_assignments = tuple(_role_assignments(mapping.get("role_assignments", ()), groups_by_name, rejected))
    ownership_bindings = tuple(_ownership_bindings(mapping.get("ownership_bindings", ()), groups_by_name, users_by_id, rejected))
    approval_policies = tuple(_approval_policies(mapping.get("approval_policies", ()), rejected))
    escalation_policies = tuple(_escalation_policies(mapping.get("escalation_policies", ()), groups_by_name, users_by_id, rejected))

    return {
        "tenant_id": tenant,
        "source_system": "scim_export",
        "source_ref": source,
        "source_hash": source_hash,
        "people": tuple({
            "identity_id": str(user["id"]),
            "display_name": str(user.get("displayName", user["id"])),
            "user_name": str(user.get("userName", "")),
            "active": bool(user.get("active", True)),
        } for user in users),
        "teams": teams,
        "role_assignments": role_assignments,
        "ownership_bindings": ownership_bindings,
        "approval_policies": approval_policies,
        "escalation_policies": escalation_policies,
        "rejected_records": tuple(rejected),
    }


def write_scim_authority_directory(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one normalized authority directory JSON payload."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _role_assignments(
    raw_records: Any,
    groups_by_name: dict[str, dict[str, Any]],
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for index, record in enumerate(_list_or_reject(raw_records, "role_assignment", rejected)):
        if not isinstance(record, dict):
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "record_must_be_mapping"})
            continue
        group_name = str(record.get("group", "")).strip()
        role = str(record.get("role", "")).strip()
        group = groups_by_name.get(group_name)
        if not group_name or not role:
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "missing_group_or_role"})
            continue
        if group is None:
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "group_not_found"})
            continue
        accepted.append({"group": group_name, "group_id": str(group["id"]), "role": role})
    return accepted


def _ownership_bindings(
    raw_records: Any,
    groups_by_name: dict[str, dict[str, Any]],
    users_by_id: dict[str, dict[str, Any]],
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for index, record in enumerate(_list_or_reject(raw_records, "ownership_binding", rejected)):
        if not isinstance(record, dict):
            rejected.append({"record_type": "ownership_binding", "index": str(index), "reason": "record_must_be_mapping"})
            continue
        owner_team = str(record.get("owner_team", "")).strip()
        escalation_team = str(record.get("escalation_team", "")).strip()
        primary_owner_id = str(record.get("primary_owner_id", "")).strip()
        fallback_owner_id = str(record.get("fallback_owner_id", "")).strip()
        missing = tuple(
            field
            for field, value in (
                ("resource_ref", record.get("resource_ref", "")),
                ("owner_team", owner_team),
                ("primary_owner_id", primary_owner_id),
                ("fallback_owner_id", fallback_owner_id),
                ("escalation_team", escalation_team),
            )
            if not str(value).strip()
        )
        if missing:
            rejected.append({"record_type": "ownership_binding", "index": str(index), "reason": f"missing_fields:{','.join(missing)}"})
            continue
        if owner_team not in groups_by_name or escalation_team not in groups_by_name:
            rejected.append({"record_type": "ownership_binding", "index": str(index), "reason": "team_not_found"})
            continue
        if primary_owner_id not in users_by_id or fallback_owner_id not in users_by_id:
            rejected.append({"record_type": "ownership_binding", "index": str(index), "reason": "owner_not_found"})
            continue
        accepted.append({
            "resource_ref": str(record["resource_ref"]),
            "owner_team": owner_team,
            "primary_owner_id": primary_owner_id,
            "fallback_owner_id": fallback_owner_id,
            "escalation_team": escalation_team,
        })
    return accepted


def _approval_policies(raw_records: Any, rejected: list[dict[str, str]]) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    required = (
        "policy_id",
        "capability",
        "risk_tier",
        "required_roles",
        "required_approver_count",
        "separation_of_duty",
        "timeout_seconds",
        "escalation_policy_id",
    )
    for index, record in enumerate(_list_or_reject(raw_records, "approval_policy", rejected)):
        if not isinstance(record, dict):
            rejected.append({"record_type": "approval_policy", "index": str(index), "reason": "record_must_be_mapping"})
            continue
        missing = tuple(field for field in required if field not in record or record[field] in ("", ()))
        if missing:
            rejected.append({"record_type": "approval_policy", "index": str(index), "reason": f"missing_fields:{','.join(missing)}"})
            continue
        accepted.append(dict(record))
    return accepted


def _escalation_policies(
    raw_records: Any,
    groups_by_name: dict[str, dict[str, Any]],
    users_by_id: dict[str, dict[str, Any]],
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    required = (
        "policy_id",
        "notify_after_seconds",
        "escalate_after_seconds",
        "incident_after_seconds",
        "fallback_owner_id",
        "escalation_team",
    )
    for index, record in enumerate(_list_or_reject(raw_records, "escalation_policy", rejected)):
        if not isinstance(record, dict):
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "record_must_be_mapping"})
            continue
        missing = tuple(field for field in required if field not in record or record[field] in ("", ()))
        if missing:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": f"missing_fields:{','.join(missing)}"})
            continue
        if str(record["fallback_owner_id"]) not in users_by_id:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "fallback_owner_not_found"})
            continue
        if str(record["escalation_team"]) not in groups_by_name:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "escalation_team_not_found"})
            continue
        accepted.append(dict(record))
    return accepted


def _list_or_reject(raw_records: Any, record_type: str, rejected: list[dict[str, str]]) -> tuple[Any, ...]:
    if raw_records in (None, ""):
        return ()
    if not isinstance(raw_records, (list, tuple)):
        rejected.append({"record_type": record_type, "reason": "records_must_be_list"})
        return ()
    return tuple(raw_records)


def _scim_resources(raw_records: Any, resource_type: str) -> tuple[dict[str, Any], ...]:
    resources = raw_records
    if isinstance(raw_records, dict) and isinstance(raw_records.get("Resources"), list):
        resources = raw_records["Resources"]
    if not isinstance(resources, list):
        raise ValueError(f"SCIM {resource_type} resources must be a list")
    accepted: list[dict[str, Any]] = []
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise ValueError(f"SCIM {resource_type} resource at index {index} must be mapping")
        if not str(resource.get("id", "")).strip():
            raise ValueError(f"SCIM {resource_type} resource at index {index} requires id")
        accepted.append(dict(resource))
    return tuple(accepted)


def _load_json_mapping(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be mapping")
    return payload


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the SCIM authority directory adapter CLI contract."""
    parser = argparse.ArgumentParser(description="Convert SCIM export evidence into normalized authority directory JSON.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--scim-export", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--output", type=Path, default=Path(".change_assurance/authority_directory_from_scim.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for SCIM authority directory normalization."""
    args = parse_args(argv)
    try:
        payload = convert_scim_authority_directory(
            tenant_id=args.tenant_id,
            scim_export_path=args.scim_export,
            mapping_path=args.mapping,
            source_ref=args.source_ref,
        )
        written = write_scim_authority_directory(payload, args.output)
        print(f"SCIM authority directory written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"SCIM authority directory failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "source_unavailable"
    return str(exc) or "invalid_scim_authority_directory"


if __name__ == "__main__":
    raise SystemExit(main())
