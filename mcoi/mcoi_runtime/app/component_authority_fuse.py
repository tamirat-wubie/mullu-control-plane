"""Build Component Harness authority fuse records.

Purpose: project non-executing authority fuse records for registered
components so no component can upgrade itself.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation component passports.
Invariants:
  - Authority fuses are read-only evidence and never execution authority.
  - Every component self-upgrade path remains blocked.
  - Live action, connector calls, mutation, and terminal closure remain denied.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
FUSE_SET_ID = "component_authority_fuse.foundation.v1"
REQUIRED_FUSE_EVIDENCE = (
    "component_schema_contract",
    "component_validator",
    "component_lifecycle_transition_receipt",
    "component_authority_upgrade_witness",
    "component_proof_matrix_row",
    "component_ci_gate",
    "operator_approval_if_external_effect",
)
AUTHORITY_TRANSITION_LADDER = (
    "read_only",
    "draft_only",
    "live_probe",
    "approval_required",
    "approved_live_action",
)


class ComponentAuthorityFuseError(ValueError):
    """Raised when component authority fuses cannot be projected safely."""


def build_component_authority_fuse(
    *,
    passports_path: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic foundation authority fuse records.

    Input contract: optional path to the component passport artifact.
    Output contract: JSON-serializable authority fuse set.
    Error contract: raises ComponentAuthorityFuseError for missing, malformed,
    incomplete, or authority-unsafe passport state.
    """

    repo_root = _repo_root()
    effective_passports_path = passports_path or repo_root / "examples" / "component_passports.foundation.json"
    passports = _load_json_object(effective_passports_path, "component passports")
    passport_entries = passports.get("passports")
    if not isinstance(passport_entries, list) or not passport_entries:
        raise ComponentAuthorityFuseError("component passports must contain a non-empty passports list")

    fuse_records = [_fuse_record(passport) for passport in passport_entries if isinstance(passport, dict)]
    if len(fuse_records) != len(passport_entries):
        raise ComponentAuthorityFuseError("component passport entries must be objects")

    return {
        "schema_version": SCHEMA_VERSION,
        "fuse_set_id": FUSE_SET_ID,
        "mode": str(passports.get("mode", "foundation")),
        "source_refs": {
            "component_passports": _path_label(effective_passports_path, repo_root),
        },
        "fuse_set_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "terminal_closure_required": True,
        "authority_transition_ladder": list(AUTHORITY_TRANSITION_LADDER),
        "required_fuse_evidence": list(REQUIRED_FUSE_EVIDENCE),
        "summary": {
            "component_count": len(fuse_records),
            "fuse_count": len(fuse_records),
            "blocked_self_upgrade_count": sum(1 for record in fuse_records if not record["self_upgrade_allowed"]),
            "approved_live_action_count": sum(
                1 for record in fuse_records if record["current_authority_level"] == "approved_live_action"
            ),
            "terminal_closure_allowed_count": sum(1 for record in fuse_records if record["terminal_closure_allowed"]),
        },
        "fuses": fuse_records,
        "validators": [
            {
                "validator_id": "component_authority_fuse_validator",
                "command": "python scripts/validate_component_authority_fuse.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "component_authority_fuse_tests",
                "command": "python -m pytest tests/test_validate_component_authority_fuse.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": "Require external authority-upgrade evidence before any component authority transition can advance.",
    }


def _fuse_record(passport: dict[str, Any]) -> dict[str, Any]:
    component_id = _required_text(passport, "component_id", "component passport")
    lifecycle = _required_object(passport, "lifecycle", f"passport {component_id}")
    current_authority_level = _required_text(lifecycle, "authority_level", f"passport {component_id} lifecycle")
    authority = _required_object(passport, "authority", f"passport {component_id}")
    if authority.get("can_claim_terminal_closure") is not False:
        raise ComponentAuthorityFuseError(f"component {component_id} can_claim_terminal_closure must be false")
    if authority.get("can_execute") is not False:
        raise ComponentAuthorityFuseError(f"component {component_id} can_execute must be false")
    missing_evidence = list(REQUIRED_FUSE_EVIDENCE)
    return {
        "fuse_id": f"component_authority_fuse.{component_id}.foundation.v1",
        "component_id": component_id,
        "current_authority_level": current_authority_level,
        "requested_authority_level": _next_authority_level(current_authority_level),
        "fuse_state": "blocked",
        "decision": "blocked",
        "outcome": "GovernanceBlocked",
        "self_upgrade_allowed": False,
        "can_upgrade_authority": False,
        "can_mutate_authority_envelope": False,
        "can_enable_live_action": False,
        "terminal_closure_allowed": False,
        "required_evidence": list(REQUIRED_FUSE_EVIDENCE),
        "missing_evidence": missing_evidence,
        "present_evidence_refs": _string_list(passport.get("evidence_refs")),
        "required_validator_refs": [
            "component_passports_validator",
            "component_authority_fuse_validator",
        ],
        "fuse_is_not_execution_authority": True,
        "fuse_is_not_terminal_closure": True,
    }


def _next_authority_level(current_authority_level: str) -> str:
    if current_authority_level == "read_only_advisory":
        return "draft_only"
    if current_authority_level in ("none", "registry_only", "blocked"):
        return "read_only"
    if current_authority_level not in AUTHORITY_TRANSITION_LADDER:
        return "approval_required"
    index = AUTHORITY_TRANSITION_LADDER.index(current_authority_level)
    if index >= len(AUTHORITY_TRANSITION_LADDER) - 1:
        return "approved_live_action"
    return AUTHORITY_TRANSITION_LADDER[index + 1]


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentAuthorityFuseError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentAuthorityFuseError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ComponentAuthorityFuseError(f"{label} root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _required_object(payload: dict[str, Any], field_name: str, label: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ComponentAuthorityFuseError(f"{label} must carry object field {field_name}")
    return value


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentAuthorityFuseError(f"{label} must carry text field {field_name}")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "examples" / "component_passports.foundation.json").exists():
            return candidate
    raise ComponentAuthorityFuseError("repository root with component passports could not be found")


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
