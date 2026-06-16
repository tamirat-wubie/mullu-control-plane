"""Build Component Harness authority envelope witnesses.

Purpose: project one current authority envelope witness per registered
component without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation component registry JSON artifact.
Invariants:
  - Authority witnesses mirror registry authority exactly.
  - Live execution, mutation, connector calls, external sends, file writes, and
    terminal closure remain false.
  - The witness set is read-only and cannot promote a component.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
WITNESS_SET_ID = "component_authority_envelope_witnesses.foundation.v1"
LIVE_AUTHORITY_FLAGS = (
    "can_execute",
    "can_mutate",
    "can_call_connector",
    "can_write_files",
    "can_send_external_message",
    "can_claim_terminal_closure",
)
PREVIEW_AUTHORITY_FLAGS = (
    "can_read",
    "can_preview",
    "can_draft",
    "can_emit_receipt",
)


class ComponentAuthorityEnvelopeWitnessError(ValueError):
    """Raised when authority envelope witnesses cannot be projected."""


def build_component_authority_envelope_witnesses(
    *,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic foundation authority envelope witnesses.

    Input contract: optional path to the foundation component registry.
    Output contract: JSON-serializable authority witness set.
    Error contract: raises ComponentAuthorityEnvelopeWitnessError for missing,
    malformed, or unsafe registry authority posture.
    """

    repo_root = _repo_root()
    effective_registry_path = registry_path or repo_root / "examples" / "component_registry.foundation.json"
    registry = _load_json_object(effective_registry_path, "component registry")
    components = registry.get("components")
    if not isinstance(components, list) or not components:
        raise ComponentAuthorityEnvelopeWitnessError("component registry components must be a non-empty list")

    witnesses = [_authority_witness(component) for component in components]
    return {
        "schema_version": SCHEMA_VERSION,
        "witness_set_id": WITNESS_SET_ID,
        "mode": str(registry.get("mode", "foundation")),
        "source_registry": _path_label(effective_registry_path, repo_root),
        "witness_set_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "terminal_closure_required": True,
        "authority_policy": {
            "default_all_live_effect_flags_false": True,
            "live_effect_flags": list(LIVE_AUTHORITY_FLAGS),
            "preview_only_flags": list(PREVIEW_AUTHORITY_FLAGS),
            "authority_upgrade_requires_separate_witness": True,
        },
        "authority_witnesses": witnesses,
        "validators": [
            {
                "validator_id": "component_authority_envelope_witnesses_validator",
                "command": "python scripts/validate_component_authority_envelope_witnesses.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "component_authority_envelope_witnesses_tests",
                "command": "python -m pytest tests/test_validate_component_authority_envelope_witnesses.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": "Require a separate authority upgrade witness before any route-family promotion can claim live effects.",
    }


def _authority_witness(component: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(component, dict):
        raise ComponentAuthorityEnvelopeWitnessError("component registry entries must be objects")
    component_id = _required_text(component, "id", "component registry entry")
    authority = component.get("authority")
    if not isinstance(authority, dict):
        raise ComponentAuthorityEnvelopeWitnessError(f"component {component_id} authority must be an object")
    normalized_authority = {key: bool(authority.get(key, False)) for key in sorted(authority)}
    for flag_name in LIVE_AUTHORITY_FLAGS:
        if normalized_authority.get(flag_name) is not False:
            raise ComponentAuthorityEnvelopeWitnessError(
                f"component {component_id} live authority flag {flag_name} must remain false"
            )
    blocked_actions = _string_list(component.get("blocked_actions"))
    if "terminal_closure" not in blocked_actions:
        raise ComponentAuthorityEnvelopeWitnessError(
            f"component {component_id} blocked_actions must include terminal_closure"
        )
    return {
        "witness_id": f"component_authority_envelope.{component_id}.foundation.v1",
        "component_id": component_id,
        "lifecycle_state": _required_text(component, "lifecycle_state", f"component {component_id}"),
        "wiring_state": _required_text(component, "wiring_state", f"component {component_id}"),
        "authority_level": _required_text(component, "authority_level", f"component {component_id}"),
        "proof_state": "Pass",
        "authority": normalized_authority,
        "authority_matches_registry": True,
        "blocked_actions": blocked_actions,
        "evidence_refs": _string_list(component.get("evidence_refs")),
        "required_validator_refs": [
            "component_registry_validator",
            "component_authority_envelope_witnesses_validator",
        ],
        "witness_is_not_execution_authority": True,
        "witness_is_not_terminal_closure": True,
        "authority_upgrade_requires_separate_witness": True,
        "external_effect": False,
    }


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentAuthorityEnvelopeWitnessError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentAuthorityEnvelopeWitnessError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ComponentAuthorityEnvelopeWitnessError(f"{label} root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentAuthorityEnvelopeWitnessError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
