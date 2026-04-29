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
    scim_payload = _load_source_mapping(scim_export_path, label="scim_export")
    mapping = _load_source_mapping(mapping_path, label="authority_mapping")
    scim_hash = _source_file_hash(scim_export_path)
    mapping_hash = _source_file_hash(mapping_path)
    source = source_ref.strip() or scim_export_path.resolve().as_uri()
    source_hash = f"sha256:{_source_stable_hash({'scim_hash': scim_hash, 'mapping_hash': mapping_hash})}"

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
    role_assignments = tuple(_normalize_role_assignments(
        mapping.get("role_assignments", ()),
        groups_by_name,
        group_fields=("group",),
        group_identity_field="id",
        rejected=rejected,
    ))
    ownership_bindings = tuple(_normalize_ownership_bindings(
        mapping.get("ownership_bindings", ()),
        groups_by_name,
        users_by_id,
        rejected=rejected,
    ))
    approval_policies = tuple(_normalize_approval_policies(mapping.get("approval_policies", ()), rejected=rejected))
    escalation_policies = tuple(_normalize_escalation_policies(
        mapping.get("escalation_policies", ()),
        groups_by_name,
        users_by_id,
        rejected=rejected,
    ))

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
