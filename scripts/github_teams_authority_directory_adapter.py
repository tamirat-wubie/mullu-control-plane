#!/usr/bin/env python3
"""GitHub teams authority directory adapter.

Purpose: transform a bounded GitHub organization teams export plus explicit
authority mapping rules into the normalized authority directory source consumed
by scripts/sync_authority_directory.py.
Governance scope: source evidence, team ownership mappings, approval-policy
mappings, escalation-policy mappings, and rejected records.
Dependencies: standard-library JSON, hashing, argparse, pathlib.
Invariants:
  - GitHub members and teams are imported only as identity and membership evidence.
  - Authority ownership and policy records require explicit mapping rules.
  - Missing GitHub logins or team slugs are rejected instead of fabricated.
  - The adapter emits normalized JSON but never persists authority state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def convert_github_teams_authority_directory(
    *,
    tenant_id: str,
    github_export_path: Path,
    mapping_path: Path,
    source_ref: str = "",
) -> dict[str, Any]:
    """Convert one GitHub teams export and explicit mapping file into normalized authority JSON."""
    tenant = tenant_id.strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    github_payload = _load_json_mapping(github_export_path, label="github_export")
    mapping = _load_json_mapping(mapping_path, label="authority_mapping")
    github_hash = _file_hash(github_export_path)
    mapping_hash = _file_hash(mapping_path)
    organization = str(github_payload.get("organization", "github-org")).strip() or "github-org"
    source = source_ref.strip() or f"github://{organization}/teams/export"
    source_hash = f"sha256:{_stable_hash({'github_hash': github_hash, 'mapping_hash': mapping_hash})}"

    members = _github_members(github_payload.get("members", ()))
    teams = _github_teams(github_payload.get("teams", ()))
    members_by_login = {str(member["login"]): member for member in members}
    teams_by_slug = {str(team["slug"]): team for team in teams}
    rejected: list[dict[str, str]] = []

    role_assignments = tuple(_role_assignments(mapping.get("role_assignments", ()), teams_by_slug, rejected))
    ownership_bindings = tuple(_ownership_bindings(mapping.get("ownership_bindings", ()), teams_by_slug, members_by_login, rejected))
    approval_policies = tuple(_approval_policies(mapping.get("approval_policies", ()), rejected))
    escalation_policies = tuple(_escalation_policies(mapping.get("escalation_policies", ()), teams_by_slug, members_by_login, rejected))

    return {
        "tenant_id": tenant,
        "source_system": "github_teams_export",
        "source_ref": source,
        "source_hash": source_hash,
        "people": tuple({
            "identity_id": str(member["login"]),
            "display_name": str(member.get("name", member["login"])),
            "user_name": str(member["login"]),
            "active": True,
        } for member in members),
        "teams": tuple({
            "team_id": str(team["slug"]),
            "display_name": str(team.get("name", team["slug"])),
            "member_ids": tuple(
                str(login)
                for login in team.get("members", ())
                if str(login).strip()
            ),
        } for team in teams),
        "role_assignments": role_assignments,
        "ownership_bindings": ownership_bindings,
        "approval_policies": approval_policies,
        "escalation_policies": escalation_policies,
        "rejected_records": tuple(rejected),
    }


def write_github_teams_authority_directory(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one normalized authority directory JSON payload."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _role_assignments(
    raw_records: Any,
    teams_by_slug: dict[str, dict[str, Any]],
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for index, record in enumerate(_list_or_reject(raw_records, "role_assignment", rejected)):
        if not isinstance(record, dict):
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "record_must_be_mapping"})
            continue
        team_slug = str(record.get("team_slug", record.get("team", ""))).strip()
        role = str(record.get("role", "")).strip()
        team = teams_by_slug.get(team_slug)
        if not team_slug or not role:
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "missing_team_or_role"})
            continue
        if team is None:
            rejected.append({"record_type": "role_assignment", "index": str(index), "reason": "team_not_found"})
            continue
        accepted.append({"group": team_slug, "group_id": str(team["slug"]), "role": role})
    return accepted


def _ownership_bindings(
    raw_records: Any,
    teams_by_slug: dict[str, dict[str, Any]],
    members_by_login: dict[str, dict[str, Any]],
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
        if owner_team not in teams_by_slug or escalation_team not in teams_by_slug:
            rejected.append({"record_type": "ownership_binding", "index": str(index), "reason": "team_not_found"})
            continue
        if primary_owner_id not in members_by_login or fallback_owner_id not in members_by_login:
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
    teams_by_slug: dict[str, dict[str, Any]],
    members_by_login: dict[str, dict[str, Any]],
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
        if str(record["fallback_owner_id"]) not in members_by_login:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "fallback_owner_not_found"})
            continue
        if str(record["escalation_team"]) not in teams_by_slug:
            rejected.append({"record_type": "escalation_policy", "index": str(index), "reason": "escalation_team_not_found"})
            continue
        accepted.append(dict(record))
    return accepted


def _github_members(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("GitHub members must be a list")
    members: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"GitHub member at index {index} must be mapping")
        if not str(record.get("login", "")).strip():
            raise ValueError(f"GitHub member at index {index} requires login")
        members.append(dict(record))
    return tuple(members)


def _github_teams(raw_records: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_records, list):
        raise ValueError("GitHub teams must be a list")
    teams: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise ValueError(f"GitHub team at index {index} must be mapping")
        if not str(record.get("slug", "")).strip():
            raise ValueError(f"GitHub team at index {index} requires slug")
        if not isinstance(record.get("members", ()), list):
            raise ValueError(f"GitHub team at index {index} members must be list")
        teams.append(dict(record))
    return tuple(teams)


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
    """Parse the GitHub teams authority directory adapter CLI contract."""
    parser = argparse.ArgumentParser(description="Convert GitHub teams evidence into normalized authority directory JSON.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--github-export", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--output", type=Path, default=Path(".change_assurance/authority_directory_from_github_teams.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for GitHub teams authority directory normalization."""
    args = parse_args(argv)
    try:
        payload = convert_github_teams_authority_directory(
            tenant_id=args.tenant_id,
            github_export_path=args.github_export,
            mapping_path=args.mapping,
            source_ref=args.source_ref,
        )
        written = write_github_teams_authority_directory(payload, args.output)
        print(f"GitHub teams authority directory written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GitHub teams authority directory failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "source_unavailable"
    return str(exc) or "invalid_github_teams_authority_directory"


if __name__ == "__main__":
    raise SystemExit(main())
