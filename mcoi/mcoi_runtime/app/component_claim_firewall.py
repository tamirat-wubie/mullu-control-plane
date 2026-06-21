"""Build Component Harness claim firewall records.

Purpose: project non-executing claim decisions that keep public and product
claims bounded by component authority evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation component passports and authority fuses.
Invariants:
  - Claim firewall records are read-only evidence and never execution authority.
  - Live, customer-ready, autonomous, compliance, and terminal claims remain
    blocked while authority fuses deny live action.
  - Allowed claims are evidence-bounded and cannot imply terminal closure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
FIREWALL_ID = "component_claim_firewall.foundation.v1"
BLOCKED_CLAIMS = (
    "production ready",
    "customer ready",
    "live Gmail enabled",
    "autonomous execution",
    "compliance certified",
    "enterprise SLA",
    "Nested Mind live",
)
ALLOWED_BOUNDED_CLAIMS = (
    "read-only projection exists",
    "draft-only evidence exists",
    "approval evidence exists",
    "terminal evidence bundle exists",
    "deployment witness published",
)
REQUIRED_VALIDATOR_REFS = (
    "component_passports_validator",
    "component_authority_fuse_validator",
    "component_claim_firewall_validator",
)


class ComponentClaimFirewallError(ValueError):
    """Raised when component claim firewall records cannot be projected safely."""


def build_component_claim_firewall(
    *,
    passports_path: Path | None = None,
    authority_fuse_path: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic foundation claim firewall records.

    Input contract: optional paths to component passport and authority fuse
    artifacts.
    Output contract: JSON-serializable claim firewall set.
    Error contract: raises ComponentClaimFirewallError for missing, malformed,
    incomplete, or authority-unsafe source state.
    """

    repo_root = _repo_root()
    effective_passports_path = passports_path or repo_root / "examples" / "component_passports.foundation.json"
    effective_authority_fuse_path = (
        authority_fuse_path or repo_root / "examples" / "component_authority_fuse.foundation.json"
    )
    passports = _load_json_object(effective_passports_path, "component passports")
    authority_fuse = _load_json_object(effective_authority_fuse_path, "component authority fuse")
    passport_entries = passports.get("passports")
    fuse_entries = authority_fuse.get("fuses")
    if not isinstance(passport_entries, list) or not passport_entries:
        raise ComponentClaimFirewallError("component passports must contain a non-empty passports list")
    if not isinstance(fuse_entries, list) or not fuse_entries:
        raise ComponentClaimFirewallError("component authority fuse must contain a non-empty fuses list")

    passport_by_component = _passport_by_component(passport_entries)
    fuse_by_component = _fuse_by_component(fuse_entries)
    if set(passport_by_component) != set(fuse_by_component):
        missing_fuses = sorted(set(passport_by_component) - set(fuse_by_component))
        extra_fuses = sorted(set(fuse_by_component) - set(passport_by_component))
        raise ComponentClaimFirewallError(
            f"passport/fuse component mismatch missing_fuses={missing_fuses} extra_fuses={extra_fuses}"
        )
    for component_id, fuse in fuse_by_component.items():
        _require_denial_fuse(component_id, fuse)

    blocked_checks = [_blocked_claim_check(claim_text, passport_by_component) for claim_text in BLOCKED_CLAIMS]
    allowed_checks = [
        _allowed_bounded_claim_check(claim_text, passport_by_component)
        for claim_text in ALLOWED_BOUNDED_CLAIMS
    ]
    claim_checks = blocked_checks + allowed_checks

    return {
        "schema_version": SCHEMA_VERSION,
        "firewall_id": FIREWALL_ID,
        "mode": str(passports.get("mode", "foundation")),
        "source_refs": {
            "component_passports": _path_label(effective_passports_path, repo_root),
            "component_authority_fuse": _path_label(effective_authority_fuse_path, repo_root),
        },
        "firewall_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "terminal_closure_required": True,
        "blocked_claims": list(BLOCKED_CLAIMS),
        "allowed_bounded_claims": list(ALLOWED_BOUNDED_CLAIMS),
        "summary": {
            "component_count": len(passport_by_component),
            "claim_check_count": len(claim_checks),
            "blocked_claim_count": len(blocked_checks),
            "allowed_bounded_claim_count": len(allowed_checks),
            "terminal_closure_allowed_count": sum(
                1 for claim_check in claim_checks if claim_check["terminal_closure_allowed"]
            ),
        },
        "claim_checks": claim_checks,
        "validators": [
            {
                "validator_id": "component_claim_firewall_validator",
                "command": "python scripts/validate_component_claim_firewall.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "component_claim_firewall_tests",
                "command": "python -m pytest tests/test_validate_component_claim_firewall.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Use the claim firewall before publishing documentation, demos, or "
            "operator read models that describe component readiness."
        ),
    }


def _blocked_claim_check(
    claim_text: str,
    passport_by_component: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blocking_component_ids = _blocking_components_for_claim(claim_text, passport_by_component)
    evidence_refs = _evidence_refs_for_components(blocking_component_ids, passport_by_component)
    return {
        "claim_id": f"blocked.{_slug(claim_text)}",
        "claim_text": claim_text,
        "claim_class": "blocked_public_readiness",
        "decision": "blocked",
        "outcome": "GovernanceBlocked",
        "required_component_states": [
            "approved_live_action",
            "external_effect_witnessed",
            "terminal_closure_witnessed",
        ],
        "blocking_component_ids": blocking_component_ids,
        "evidence_refs": evidence_refs,
        "required_validator_refs": list(REQUIRED_VALIDATOR_REFS),
        "claim_is_not_execution_authority": True,
        "terminal_closure_allowed": False,
    }


def _allowed_bounded_claim_check(
    claim_text: str,
    passport_by_component: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    component_ids = _components_for_allowed_claim(claim_text, passport_by_component)
    evidence_refs = _evidence_refs_for_components(component_ids, passport_by_component)
    return {
        "claim_id": f"allowed_bounded.{_slug(claim_text)}",
        "claim_text": claim_text,
        "claim_class": "allowed_evidence_bounded",
        "decision": "allowed_bounded",
        "outcome": "SolvedVerified",
        "required_component_states": [
            "registered",
            "validated",
            "non_terminal",
        ],
        "blocking_component_ids": [],
        "evidence_refs": evidence_refs,
        "required_validator_refs": list(REQUIRED_VALIDATOR_REFS),
        "claim_is_not_execution_authority": True,
        "terminal_closure_allowed": False,
    }


def _blocking_components_for_claim(
    claim_text: str,
    passport_by_component: dict[str, dict[str, Any]],
) -> list[str]:
    lower_claim = claim_text.lower()
    if "gmail" in lower_claim:
        return [
            component_id
            for component_id in ("personal_assistant", "gmail_account_binding_gate")
            if component_id in passport_by_component
        ]
    if "nested mind" in lower_claim:
        return [component_id for component_id in ("nested_mind_bridge",) if component_id in passport_by_component]
    return sorted(passport_by_component)


def _components_for_allowed_claim(
    claim_text: str,
    passport_by_component: dict[str, dict[str, Any]],
) -> list[str]:
    lower_claim = claim_text.lower()
    if "draft" in lower_claim or "approval" in lower_claim:
        return [component_id for component_id in ("personal_assistant",) if component_id in passport_by_component]
    if "terminal evidence" in lower_claim:
        return [
            component_id
            for component_id in ("teamops_shared_inbox", "worker_runtime")
            if component_id in passport_by_component
        ]
    if "deployment witness" in lower_claim:
        return [
            component_id
            for component_id in ("governance_core", "agentic_service_harness")
            if component_id in passport_by_component
        ]
    return sorted(passport_by_component)


def _evidence_refs_for_components(
    component_ids: list[str],
    passport_by_component: dict[str, dict[str, Any]],
) -> list[str]:
    evidence_refs: set[str] = set()
    for component_id in component_ids:
        passport = passport_by_component.get(component_id)
        if passport is None:
            continue
        evidence_refs.update(_string_list(passport.get("evidence_refs")))
        proofs = passport.get("proofs")
        if isinstance(proofs, dict):
            evidence_refs.update(_string_list(proofs.get("proof_surface_evidence_refs")))
    return sorted(evidence_refs)


def _passport_by_component(passports: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for passport in passports:
        if not isinstance(passport, dict):
            raise ComponentClaimFirewallError("component passport entries must be objects")
        component_id = _required_text(passport, "component_id", "component passport")
        if component_id in result:
            raise ComponentClaimFirewallError(f"duplicate component passport {component_id}")
        result[component_id] = passport
    return result


def _fuse_by_component(fuses: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for fuse in fuses:
        if not isinstance(fuse, dict):
            raise ComponentClaimFirewallError("component authority fuse entries must be objects")
        component_id = _required_text(fuse, "component_id", "component authority fuse")
        if component_id in result:
            raise ComponentClaimFirewallError(f"duplicate component authority fuse {component_id}")
        result[component_id] = fuse
    return result


def _require_denial_fuse(component_id: str, fuse: dict[str, Any]) -> None:
    for field_name in (
        "self_upgrade_allowed",
        "can_upgrade_authority",
        "can_mutate_authority_envelope",
        "can_enable_live_action",
        "terminal_closure_allowed",
    ):
        if fuse.get(field_name) is not False:
            raise ComponentClaimFirewallError(f"component {component_id} authority fuse {field_name} must be false")
    if fuse.get("decision") != "blocked":
        raise ComponentClaimFirewallError(f"component {component_id} authority fuse decision must be blocked")
    if fuse.get("outcome") != "GovernanceBlocked":
        raise ComponentClaimFirewallError(f"component {component_id} authority fuse outcome must be GovernanceBlocked")


def _slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("-", "_")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentClaimFirewallError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentClaimFirewallError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ComponentClaimFirewallError(f"{label} root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentClaimFirewallError(f"{label} must carry text field {field_name}")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "examples" / "component_authority_fuse.foundation.json").exists():
            return candidate
    raise ComponentClaimFirewallError("repository root with component authority fuse could not be found")


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
