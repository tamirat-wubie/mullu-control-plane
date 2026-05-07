#!/usr/bin/env python3
"""SAML groups authority directory adapter.

Purpose: transform a bounded SAML subjects/groups export plus explicit
authority mapping rules into the normalized authority directory source consumed
by scripts/sync_authority_directory.py.
Governance scope: source evidence, group ownership mappings, approval-policy
mappings, escalation-policy mappings, and rejected records.
Dependencies: standard-library JSON, hashing, argparse, pathlib.
Invariants:
  - SAML subjects and groups are imported only as identity and membership evidence.
  - Authority ownership and policy records require explicit mapping rules.
  - Missing SAML subjects or groups are rejected instead of fabricated.
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


def convert_saml_groups_authority_directory(
    *,
    tenant_id: str,
    saml_export_path: Path,
    mapping_path: Path,
    source_ref: str = "",
) -> dict[str, Any]:
    """Convert one SAML groups export and explicit mapping file into normalized authority JSON."""
    tenant = tenant_id.strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    saml_payload = _load_source_mapping(saml_export_path, label="saml_export")
    mapping = _load_source_mapping(mapping_path, label="authority_mapping")
    saml_hash = _source_file_hash(saml_export_path)
    mapping_hash = _source_file_hash(mapping_path)
    issuer = str(saml_payload.get("issuer", "saml-idp")).strip() or "saml-idp"
    source = source_ref.strip() or f"saml://{issuer}/groups/export"
    source_hash = f"sha256:{_source_stable_hash({'saml_hash': saml_hash, 'mapping_hash': mapping_hash})}"

    subjects = _saml_subjects(saml_payload.get("subjects", ()))
    groups = _saml_groups(saml_payload.get("groups", ()))
    subjects_by_id = {str(subject["subject_id"]): subject for subject in subjects}
    groups_by_name = {str(group["group"]): group for group in groups}
    rejected: list[dict[str, str]] = []

    role_assignments = tuple(_normalize_role_assignments(
        mapping.get("role_assignments", ()),
        groups_by_name,
        group_fields=("group",),
        group_identity_field="group",
        rejected=rejected,
    ))
    ownership_bindings = tuple(_normalize_ownership_bindings(
        mapping.get("ownership_bindings", ()),
        groups_by_name,
        subjects_by_id,
        rejected=rejected,
    ))
    approval_policies = tuple(_normalize_approval_policies(mapping.get("approval_policies", ()), rejected=rejected))
    escalation_policies = tuple(_normalize_escalation_policies(
        mapping.get("escalation_policies", ()),
        groups_by_name,
        subjects_by_id,
        rejected=rejected,
    ))

    return {
        "tenant_id": tenant,
        "source_system": "saml_groups_export",
        "source_ref": source,
        "source_hash": source_hash,
        "people": tuple({
            "identity_id": str(subject["subject_id"]),
            "display_name": str(subject.get("display_name", subject["subject_id"])),
            "user_name": str(subject.get("name_id", subject["subject_id"])),
            "active": bool(subject.get("active", True)),
        } for subject in subjects),
        "teams": tuple({
            "team_id": str(group["group"]),
            "display_name": str(group.get("display_name", group["group"])),
            "member_ids": tuple(
                str(subject_id)
                for subject_id in group.get("members", ())
                if str(subject_id).strip()
            ),
        } for group in groups),
        "role_assignments": role_assignments,
        "ownership_bindings": ownership_bindings,
        "approval_policies": approval_policies,
        "escalation_policies": escalation_policies,
        "rejected_records": tuple(rejected),
    }


def write_saml_groups_authority_directory(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one normalized authority directory JSON payload."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _saml_subjects(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("SAML subjects must be a list")
    subjects: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"SAML subject at index {index} must be mapping")
        if not str(record.get("subject_id", "")).strip():
            raise ValueError(f"SAML subject at index {index} requires subject_id")
        subjects.append(dict(record))
    return tuple(subjects)


def _saml_groups(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("SAML groups must be a list")
    groups: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"SAML group at index {index} must be mapping")
        if not str(record.get("group", "")).strip():
            raise ValueError(f"SAML group at index {index} requires group")
        if not isinstance(record.get("members", ()), list):
            raise ValueError(f"SAML group at index {index} members must be list")
        groups.append(dict(record))
    return tuple(groups)



def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the SAML groups authority directory adapter CLI contract."""
    parser = argparse.ArgumentParser(description="Convert SAML group evidence into normalized authority directory JSON.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--saml-export", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--output", type=Path, default=Path(".change_assurance/authority_directory_from_saml_groups.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for SAML groups authority directory normalization."""
    args = parse_args(argv)
    try:
        payload = convert_saml_groups_authority_directory(
            tenant_id=args.tenant_id,
            saml_export_path=args.saml_export,
            mapping_path=args.mapping,
            source_ref=args.source_ref,
        )
        written = write_saml_groups_authority_directory(payload, args.output)
        print(f"SAML groups authority directory written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"SAML groups authority directory failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "source_unavailable"
    message = str(exc)
    if message in {
        "saml_groups_export must be JSON",
        "saml_groups_mapping must be JSON",
        "saml_groups_export root must be mapping",
        "saml_groups_mapping root must be mapping",
        "SAML groups must be a list",
        "SAML users must be a list",
    }:
        return message
    return "invalid_saml_groups_authority_directory"


if __name__ == "__main__":
    raise SystemExit(main())
