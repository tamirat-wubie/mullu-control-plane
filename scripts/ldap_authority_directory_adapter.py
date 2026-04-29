#!/usr/bin/env python3
"""LDAP authority directory adapter.

Purpose: transform a bounded LDAP users/groups export plus explicit authority
mapping rules into the normalized authority directory source consumed by
scripts/sync_authority_directory.py.
Governance scope: source evidence, group ownership mappings, approval-policy
mappings, escalation-policy mappings, and rejected records.
Dependencies: standard-library JSON, hashing, argparse, pathlib.
Invariants:
  - LDAP users and groups are imported only as identity and membership evidence.
  - Authority ownership and policy records require explicit mapping rules.
  - Missing LDAP DNs are rejected instead of fabricated.
  - The adapter emits normalized JSON but never persists authority state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.authority_directory_mapping import approval_policies as _normalize_approval_policies
from scripts.authority_directory_mapping import escalation_policies as _normalize_escalation_policies
from scripts.authority_directory_mapping import file_hash as _source_file_hash
from scripts.authority_directory_mapping import load_json_mapping as _load_source_mapping
from scripts.authority_directory_mapping import ownership_bindings as _normalize_ownership_bindings
from scripts.authority_directory_mapping import role_assignments as _normalize_role_assignments
from scripts.authority_directory_mapping import stable_hash as _source_stable_hash


def convert_ldap_authority_directory(
    *,
    tenant_id: str,
    ldap_export_path: Path,
    mapping_path: Path,
    source_ref: str = "",
) -> dict[str, Any]:
    """Convert one LDAP export and explicit mapping file into normalized authority JSON."""
    tenant = tenant_id.strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    ldap_payload = _load_source_mapping(ldap_export_path, label="ldap_export")
    mapping = _load_source_mapping(mapping_path, label="authority_mapping")
    ldap_hash = _source_file_hash(ldap_export_path)
    mapping_hash = _source_file_hash(mapping_path)
    directory_ref = str(ldap_payload.get("directory_ref", "ldap-directory")).strip() or "ldap-directory"
    source = source_ref.strip() or f"ldap://{directory_ref}/groups/export"
    source_hash = f"sha256:{_source_stable_hash({'ldap_hash': ldap_hash, 'mapping_hash': mapping_hash})}"

    users = _ldap_users(ldap_payload.get("users", ()))
    groups = _ldap_groups(ldap_payload.get("groups", ()))
    users_by_dn = {str(user["dn"]): user for user in users}
    groups_by_dn = {str(group["dn"]): group for group in groups}
    rejected: list[dict[str, str]] = []

    role_assignments = tuple(_normalize_role_assignments(
        mapping.get("role_assignments", ()),
        groups_by_dn,
        group_fields=("group_dn", "group"),
        group_identity_field="dn",
        rejected=rejected,
    ))
    ownership_bindings = tuple(_normalize_ownership_bindings(
        mapping.get("ownership_bindings", ()),
        groups_by_dn,
        users_by_dn,
        rejected=rejected,
    ))
    approval_policies = tuple(_normalize_approval_policies(mapping.get("approval_policies", ()), rejected=rejected))
    escalation_policies = tuple(_normalize_escalation_policies(
        mapping.get("escalation_policies", ()),
        groups_by_dn,
        users_by_dn,
        rejected=rejected,
    ))

    return {
        "tenant_id": tenant,
        "source_system": "ldap_export",
        "source_ref": source,
        "source_hash": source_hash,
        "people": tuple({
            "identity_id": str(user["dn"]),
            "display_name": str(user.get("display_name", user.get("cn", user["dn"]))),
            "user_name": str(user.get("uid", user.get("mail", user["dn"]))),
            "active": bool(user.get("active", True)),
        } for user in users),
        "teams": tuple({
            "team_id": str(group["dn"]),
            "display_name": str(group.get("display_name", group.get("cn", group["dn"]))),
            "member_ids": tuple(
                str(dn)
                for dn in group.get("members", ())
                if str(dn).strip()
            ),
        } for group in groups),
        "role_assignments": role_assignments,
        "ownership_bindings": ownership_bindings,
        "approval_policies": approval_policies,
        "escalation_policies": escalation_policies,
        "rejected_records": tuple(rejected),
    }


def write_ldap_authority_directory(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one normalized authority directory JSON payload."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _ldap_users(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("LDAP users must be a list")
    users: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"LDAP user at index {index} must be mapping")
        if not str(record.get("dn", "")).strip():
            raise ValueError(f"LDAP user at index {index} requires dn")
        users.append(dict(record))
    return tuple(users)


def _ldap_groups(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("LDAP groups must be a list")
    groups: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"LDAP group at index {index} must be mapping")
        if not str(record.get("dn", "")).strip():
            raise ValueError(f"LDAP group at index {index} requires dn")
        if not isinstance(record.get("members", ()), list):
            raise ValueError(f"LDAP group at index {index} members must be list")
        groups.append(dict(record))
    return tuple(groups)



def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the LDAP authority directory adapter CLI contract."""
    parser = argparse.ArgumentParser(description="Convert LDAP evidence into normalized authority directory JSON.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--ldap-export", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--output", type=Path, default=Path(".change_assurance/authority_directory_from_ldap.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for LDAP authority directory normalization."""
    args = parse_args(argv)
    try:
        payload = convert_ldap_authority_directory(
            tenant_id=args.tenant_id,
            ldap_export_path=args.ldap_export,
            mapping_path=args.mapping,
            source_ref=args.source_ref,
        )
        written = write_ldap_authority_directory(payload, args.output)
        print(f"LDAP authority directory written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"LDAP authority directory failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "source_unavailable"
    return str(exc) or "invalid_ldap_authority_directory"


if __name__ == "__main__":
    raise SystemExit(main())
