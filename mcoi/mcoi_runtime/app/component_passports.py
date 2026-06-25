"""Build Component Harness passports.

Purpose: project one operator-facing passport per registered component.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation component registry and authority envelope witnesses.
Invariants:
  - Component passports are read-only evidence and never execution authority.
  - Passport identity, lifecycle, authority, proofs, health, dependencies, and
    blocked actions are derived from governed source artifacts.
  - A passport cannot upgrade authority or claim terminal closure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
PASSPORT_SET_ID = "component_passports.foundation.v1"
LIVE_AUTHORITY_FLAGS = (
    "can_execute",
    "can_mutate",
    "can_call_connector",
    "can_write_files",
    "can_send_external_message",
    "can_claim_terminal_closure",
)


class ComponentPassportError(ValueError):
    """Raised when component passports cannot be projected safely."""


def build_component_passports(
    *,
    registry_path: Path | None = None,
    authority_witnesses_path: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic foundation component passports.

    Input contract: optional paths to the component registry and authority
    envelope witness artifacts.
    Output contract: JSON-serializable passport set.
    Error contract: raises ComponentPassportError when a required artifact is
    missing, malformed, incomplete, or authority-unsafe.
    """

    repo_root = _repo_root()
    effective_registry_path = registry_path or repo_root / "examples" / "component_registry.foundation.json"
    effective_authority_witnesses_path = (
        authority_witnesses_path
        or repo_root / "examples" / "component_authority_envelope_witnesses.foundation.json"
    )
    registry = _load_json_object(effective_registry_path, "component registry")
    authority_witnesses = _load_json_object(effective_authority_witnesses_path, "authority envelope witnesses")
    components = registry.get("components")
    if not isinstance(components, list) or not components:
        raise ComponentPassportError("component registry components must be a non-empty list")

    witness_by_component = _authority_witness_by_component(authority_witnesses)
    passports = [
        _component_passport(component, witness_by_component, repo_root)
        for component in components
        if isinstance(component, dict)
    ]
    if len(passports) != len(components):
        raise ComponentPassportError("component registry entries must be objects")

    missing_witnesses = sorted(
        _required_text(component, "id", "component registry entry")
        for component in components
        if isinstance(component, dict)
        and _required_text(component, "id", "component registry entry") not in witness_by_component
    )
    if missing_witnesses:
        raise ComponentPassportError(f"registered components missing passport authority witnesses {missing_witnesses}")

    return {
        "schema_version": SCHEMA_VERSION,
        "passport_set_id": PASSPORT_SET_ID,
        "mode": str(registry.get("mode", "foundation")),
        "source_refs": {
            "registry": _path_label(effective_registry_path, repo_root),
            "authority_envelope_witnesses": _path_label(effective_authority_witnesses_path, repo_root),
        },
        "passport_set_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "terminal_closure_required": True,
        "summary": {
            "component_count": len(passports),
            "passport_count": len(passports),
            "authority_witness_count": len(witness_by_component),
            "proof_bound_count": sum(
                1 for passport in passports if passport["proofs"]["proof_surface_status"] == "proof_bound"
            ),
            "awaiting_binding_count": sum(
                1 for passport in passports if passport["proofs"]["proof_surface_status"] == "awaiting_binding"
            ),
            "blocked_component_count": sum(
                1 for passport in passports if passport["lifecycle"]["mode"] == "blocked"
            ),
        },
        "passports": passports,
        "validators": [
            {
                "validator_id": "component_passports_validator",
                "command": "python scripts/validate_component_passports.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "component_passports_tests",
                "command": "python -m pytest tests/test_validate_component_passports.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Use component passports as the dashboard-ready trust envelope before "
            "any route-family promotion can claim product ownership or live action."
        ),
    }


def _component_passport(
    component: dict[str, Any],
    witness_by_component: dict[str, dict[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    component_id = _required_text(component, "id", "component registry entry")
    witness = witness_by_component.get(component_id)
    if witness is None:
        raise ComponentPassportError(f"component {component_id} is missing authority envelope witness")
    _require_witness_matches_component(component, witness)
    authority = component.get("authority")
    if not isinstance(authority, dict):
        raise ComponentPassportError(f"component {component_id} authority must be an object")
    normalized_authority = _normalized_authority(component_id, authority)
    for flag_name in LIVE_AUTHORITY_FLAGS:
        if normalized_authority.get(flag_name) is not False:
            raise ComponentPassportError(f"component {component_id} live authority flag {flag_name} must be false")
    blocked_actions = _string_list(component.get("blocked_actions"))
    if "terminal_closure" not in blocked_actions:
        raise ComponentPassportError(f"component {component_id} blocked_actions must include terminal_closure")

    proof_surface = _required_object(component, "proof_surface", f"component {component_id}")
    health_source = _required_object(component, "health_source", f"component {component_id}")
    evidence_refs = _string_list(component.get("evidence_refs"))
    for evidence_ref in evidence_refs:
        evidence_path = evidence_ref.split("#", 1)[0]
        if not (repo_root / evidence_path).exists():
            raise ComponentPassportError(f"component {component_id} evidence_ref missing on disk: {evidence_ref}")

    return {
        "passport_id": f"component_passport.{component_id}.foundation.v1",
        "component_id": component_id,
        "identity": {
            "name": _required_text(component, "name", f"component {component_id}"),
            "type": _required_text(component, "type", f"component {component_id}"),
            "aliases": _string_list(component.get("aliases")),
            "owner_surface": _required_text(component, "owner_surface", f"component {component_id}"),
        },
        "purpose": str(component.get("purpose", "")),
        "lifecycle": {
            "mode": _required_text(component, "mode", f"component {component_id}"),
            "lifecycle_state": _required_text(component, "lifecycle_state", f"component {component_id}"),
            "wiring_state": _required_text(component, "wiring_state", f"component {component_id}"),
            "authority_level": _required_text(component, "authority_level", f"component {component_id}"),
        },
        "authority": normalized_authority,
        "proofs": {
            "proof_surface_status": str(proof_surface.get("status", "")),
            "proof_surface_id": proof_surface.get("surface_id"),
            "proof_surface_evidence_refs": _string_list(proof_surface.get("evidence_refs")),
            "authority_witness_id": _required_text(witness, "witness_id", f"component {component_id} witness"),
            "authority_witness_proof_state": _required_text(
                witness,
                "proof_state",
                f"component {component_id} witness",
            ),
        },
        "receipts": {
            "receipt_required": bool(component.get("receipt_required")),
            "can_emit_receipt": bool(normalized_authority.get("can_emit_receipt")),
            "terminal_closure_required": True,
            "can_claim_terminal_closure": False,
        },
        "health": {
            "source": dict(health_source),
            "status": "known" if health_source.get("type") != "none" else "unknown",
        },
        "dependencies": _string_list(component.get("dependencies")),
        "blocked_actions": blocked_actions,
        "evidence_refs": evidence_refs,
        "last_validation": {
            "state": "validated",
            "validator_refs": [
                "component_registry_validator",
                "component_authority_envelope_witnesses_validator",
                "component_passports_validator",
            ],
        },
        "passport_is_not_execution_authority": True,
        "passport_is_not_terminal_closure": True,
    }


def _authority_witness_by_component(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = payload.get("authority_witnesses")
    if not isinstance(entries, list):
        raise ComponentPassportError("authority envelope witnesses must contain authority_witnesses list")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ComponentPassportError("authority witness entries must be objects")
        component_id = _required_text(entry, "component_id", "authority witness")
        if component_id in result:
            raise ComponentPassportError(f"duplicate authority witness for component {component_id}")
        result[component_id] = entry
    return result


def _require_witness_matches_component(component: dict[str, Any], witness: dict[str, Any]) -> None:
    component_id = _required_text(component, "id", "component registry entry")
    for field_name in ("lifecycle_state", "wiring_state", "authority_level"):
        if witness.get(field_name) != component.get(field_name):
            raise ComponentPassportError(f"component {component_id} witness {field_name} must match registry")
    if witness.get("authority") != component.get("authority"):
        raise ComponentPassportError(f"component {component_id} witness authority must match registry")
    if witness.get("witness_is_not_execution_authority") is not True:
        raise ComponentPassportError(f"component {component_id} witness_is_not_execution_authority must be true")
    if witness.get("witness_is_not_terminal_closure") is not True:
        raise ComponentPassportError(f"component {component_id} witness_is_not_terminal_closure must be true")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentPassportError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentPassportError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ComponentPassportError(f"{label} root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _required_object(payload: dict[str, Any], field_name: str, label: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ComponentPassportError(f"{label} must carry object field {field_name}")
    return value


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentPassportError(f"{label} must carry text field {field_name}")
    return value


def _normalized_authority(component_id: str, authority: dict[str, Any]) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    for field_name in sorted(authority):
        field_value = authority[field_name]
        if not isinstance(field_name, str) or not field_name:
            raise ComponentPassportError(f"component {component_id} authority field names must be non-empty strings")
        if not isinstance(field_value, bool):
            raise ComponentPassportError(f"component {component_id} authority.{field_name} must be boolean")
        normalized[field_name] = field_value
    return normalized


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    if not all(isinstance(item, str) for item in value):
        raise ComponentPassportError("string list fields must only contain strings")
    return value


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "examples" / "component_registry.foundation.json").exists():
            return candidate
    raise ComponentPassportError("repository root with component registry could not be found")


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
