"""Shared authority directory mapping normalization helpers.

Purpose: provide deterministic mapping validation for authority directory
adapters that convert external directory exports into normalized governance
records.
Governance scope: role assignments, ownership bindings, approval policies,
escalation policies, JSON source loading, and source evidence hashes.
Dependencies: standard-library JSON, hashing, pathlib.
Invariants:
  - Mapping records must be explicit mappings or rejected with causal context.
  - Referenced groups and owners must exist in the source export.
  - Source hashes are deterministic and derived from bounded input files.
  - Helpers normalize records only; they never persist authority state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_json_mapping(path: Path, *, label: str) -> dict[str, Any]:
    """Load a JSON mapping root from disk or raise a bounded validation error."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be mapping")
    return payload


def file_hash(path: Path) -> str:
    """Return the SHA-256 hash for one bounded source file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible mapping."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def role_assignments(
    raw_records: Any,
    groups_by_key: dict[str, dict[str, Any]],
    *,
    group_fields: tuple[str, ...],
    group_identity_field: str,
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Normalize role mappings whose group references must exist in source evidence."""
    accepted: list[dict[str, Any]] = []
    for index, record in enumerate(_list_or_reject(raw_records, "role_assignment", rejected)):
        if not isinstance(record, dict):
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "record_must_be_mapping"})
            continue
        group_ref = _first_present(record, group_fields)
        role = str(record.get("role", "")).strip()
        group = groups_by_key.get(group_ref)
        if not group_ref or not role:
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "missing_group_or_role"})
            continue
        if group is None:
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "group_not_found"})
            continue
        accepted.append({"group": group_ref, "group_id": str(group[group_identity_field]), "role": role})
    return accepted


def ownership_bindings(
    raw_records: Any,
    groups_by_key: dict[str, dict[str, Any]],
    users_by_key: dict[str, dict[str, Any]],
    *,
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Normalize ownership mappings whose teams and owners must exist."""
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
        if owner_team not in groups_by_key or escalation_team not in groups_by_key:
            rejected.append({"record_type": "ownership_binding", "index": str(index), "reason": "team_not_found"})
            continue
        if primary_owner_id not in users_by_key or fallback_owner_id not in users_by_key:
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


def approval_policies(raw_records: Any, *, rejected: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Normalize approval policy records after required-field validation."""
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


def escalation_policies(
    raw_records: Any,
    groups_by_key: dict[str, dict[str, Any]],
    users_by_key: dict[str, dict[str, Any]],
    *,
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Normalize escalation policies whose fallback owner and team must exist."""
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
        if str(record["fallback_owner_id"]) not in users_by_key:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "fallback_owner_not_found"})
            continue
        if str(record["escalation_team"]) not in groups_by_key:
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


def _first_present(record: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = str(record.get(field, "")).strip()
        if value:
            return value
    return ""
