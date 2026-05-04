#!/usr/bin/env python3
"""Workspace groups authority directory adapter.

Purpose: transform a bounded workspace users/groups export plus explicit
authority mapping rules into the normalized authority directory source consumed
by scripts/sync_authority_directory.py.
Governance scope: source evidence, group ownership mappings, approval-policy
mappings, escalation-policy mappings, and rejected records.
Dependencies: standard-library JSON, hashing, argparse, pathlib.
Invariants:
  - Workspace users and groups are imported only as identity and membership evidence.
  - Authority ownership and policy records require explicit mapping rules.
  - Missing user emails or group emails are rejected instead of fabricated.
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


def convert_workspace_groups_authority_directory(
    *,
    tenant_id: str,
    workspace_export_path: Path,
    mapping_path: Path,
    source_ref: str = "",
) -> dict[str, Any]:
    """Convert one workspace groups export and explicit mapping file into normalized authority JSON."""
    tenant = tenant_id.strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    workspace_payload = _load_source_mapping(workspace_export_path, label="workspace_export")
    mapping = _load_source_mapping(mapping_path, label="authority_mapping")
    workspace_hash = _source_file_hash(workspace_export_path)
    mapping_hash = _source_file_hash(mapping_path)
    domain = str(workspace_payload.get("domain", "workspace")).strip() or "workspace"
    source = source_ref.strip() or f"workspace://{domain}/groups/export"
    source_hash = f"sha256:{_source_stable_hash({'workspace_hash': workspace_hash, 'mapping_hash': mapping_hash})}"

    users = _workspace_users(workspace_payload.get("users", ()))
    groups = _workspace_groups(workspace_payload.get("groups", ()))
    users_by_email = {str(user["email"]): user for user in users}
    groups_by_email = {str(group["email"]): group for group in groups}
    rejected: list[dict[str, str]] = []

    role_assignments = tuple(_normalize_role_assignments(
        mapping.get("role_assignments", ()),
        groups_by_email,
        group_fields=("group_email", "group"),
        group_identity_field="email",
        rejected=rejected,
    ))
    ownership_bindings = tuple(_normalize_ownership_bindings(
        mapping.get("ownership_bindings", ()),
        groups_by_email,
        users_by_email,
        rejected=rejected,
    ))
    approval_policies = tuple(_normalize_approval_policies(mapping.get("approval_policies", ()), rejected=rejected))
    escalation_policies = tuple(_normalize_escalation_policies(
        mapping.get("escalation_policies", ()),
        groups_by_email,
        users_by_email,
        rejected=rejected,
    ))

    return {
        "tenant_id": tenant,
        "source_system": "workspace_groups_export",
        "source_ref": source,
        "source_hash": source_hash,
        "people": tuple({
            "identity_id": str(user["email"]),
            "display_name": str(user.get("name", user["email"])),
            "user_name": str(user["email"]),
            "active": bool(user.get("active", True)),
        } for user in users),
        "teams": tuple({
            "team_id": str(group["email"]),
            "display_name": str(group.get("name", group["email"])),
            "member_ids": tuple(
                str(email)
                for email in group.get("members", ())
                if str(email).strip()
            ),
        } for group in groups),
        "role_assignments": role_assignments,
        "ownership_bindings": ownership_bindings,
        "approval_policies": approval_policies,
        "escalation_policies": escalation_policies,
        "rejected_records": tuple(rejected),
    }


def write_workspace_groups_authority_directory(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one normalized authority directory JSON payload."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _workspace_users(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("workspace users must be a list")
    users: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"workspace user at index {index} must be mapping")
        if not str(record.get("email", "")).strip():
            raise ValueError(f"workspace user at index {index} requires email")
        users.append(dict(record))
    return tuple(users)


def _workspace_groups(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("workspace groups must be a list")
    groups: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"workspace group at index {index} must be mapping")
        if not str(record.get("email", "")).strip():
            raise ValueError(f"workspace group at index {index} requires email")
        if not isinstance(record.get("members", ()), list):
            raise ValueError(f"workspace group at index {index} members must be list")
        groups.append(dict(record))
    return tuple(groups)



def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the workspace groups authority directory adapter CLI contract."""
    parser = argparse.ArgumentParser(description="Convert workspace group evidence into normalized authority directory JSON.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--workspace-export", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--output", type=Path, default=Path(".change_assurance/authority_directory_from_workspace_groups.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for workspace groups authority directory normalization."""
    args = parse_args(argv)
    try:
        payload = convert_workspace_groups_authority_directory(
            tenant_id=args.tenant_id,
            workspace_export_path=args.workspace_export,
            mapping_path=args.mapping,
            source_ref=args.source_ref,
        )
        written = write_workspace_groups_authority_directory(payload, args.output)
        print(f"Workspace groups authority directory written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Workspace groups authority directory failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "source_unavailable"
    message = str(exc)
    if message in {
        "workspace_groups_export must be JSON",
        "workspace_groups_mapping must be JSON",
        "workspace_groups_export root must be mapping",
        "workspace_groups_mapping root must be mapping",
        "workspace groups must be a list",
        "workspace users must be a list",
    }:
        return message
    return "invalid_workspace_groups_authority_directory"


if __name__ == "__main__":
    raise SystemExit(main())
