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
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


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
    saml_payload = _load_json_mapping(saml_export_path, label="saml_export")
    mapping = _load_json_mapping(mapping_path, label="authority_mapping")
    saml_hash = _file_hash(saml_export_path)
    mapping_hash = _file_hash(mapping_path)
    issuer = str(saml_payload.get("issuer", "saml-idp")).strip() or "saml-idp"
    source = source_ref.strip() or f"saml://{issuer}/groups/export"
    source_hash = f"sha256:{_stable_hash({'saml_hash': saml_hash, 'mapping_hash': mapping_hash})}"

    subjects = _saml_subjects(saml_payload.get("subjects", ()))
    groups = _saml_groups(saml_payload.get("groups", ()))
    subjects_by_id = {str(subject["subject_id"]): subject for subject in subjects}
    groups_by_name = {str(group["group"]): group for group in groups}
    rejected: list[dict[str, str]] = []

    role_assignments = tuple(_role_assignments(mapping.get("role_assignments", ()), groups_by_name, rejected))
    ownership_bindings = tuple(_ownership_bindings(mapping.get("ownership_bindings", ()), groups_by_name, subjects_by_id, rejected))
    approval_policies = tuple(_approval_policies(mapping.get("approval_policies", ()), rejected))
    escalation_policies = tuple(_escalation_policies(mapping.get("escalation_policies", ()), groups_by_name, subjects_by_id, rejected))

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
        accepted.append({"group": group_name, "group_id": str(group["group"]), "role": role})
    return accepted


def _ownership_bindings(
    raw_records: Any,
    groups_by_name: dict[str, dict[str, Any]],
    subjects_by_id: dict[str, dict[str, Any]],
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
        if primary_owner_id not in subjects_by_id or fallback_owner_id not in subjects_by_id:
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
    subjects_by_id: dict[str, dict[str, Any]],
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
        if str(record["fallback_owner_id"]) not in subjects_by_id:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "fallback_owner_not_found"})
            continue
        if str(record["escalation_team"]) not in groups_by_name:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "escalation_team_not_found"})
            continue
        accepted.append(dict(record))
    return accepted


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


def _list_or_reject(raw_records: Any, record_type: str, rejected: list[dict[str, str]]) -> tuple[Any, ...]:
    if raw_records in (None, ""):
        return ()
    if not isinstance(raw_records, (list, tuple)):
        rejected.append({"record_type": record_type, "reason": "records_must_be_list"})
        return ()
    return tuple(raw_records)


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
    return str(exc) or "invalid_saml_groups_authority_directory"


if __name__ == "__main__":
    raise SystemExit(main())
