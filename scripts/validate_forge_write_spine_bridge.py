#!/usr/bin/env python3
"""Validate the Forge write-spine bridge contract.

Purpose: prove the Forge dev3 write-spine is applied here as a reference-only
contract with explicit state-write gates and no production authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: bridge schema, bridge fixture, and shared schema validator.
Invariants:
  - The bridge never registers a runtime adapter or external effects.
  - Production state-changing remains blocked.
  - Commit is impossible before Phi_gov certificate and H_lineage attestation.
  - Certificate and service-boundary constraints stay explicit.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_write_spine_bridge.schema.json"
DEFAULT_BRIDGE = REPO_ROOT / "examples" / "forge_write_spine_bridge.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_write_spine_bridge_validation.json"
EXPECTED_STAGE_IDS = (
    "conditional_decision",
    "fenced_snapshot",
    "phigov_certificate",
    "prepared_transition",
    "lineage_authorization_attestation",
    "fenced_commit",
    "lineage_completion_attestation",
)
EXPECTED_CERTIFICATE_FIELDS = (
    "certificate_id",
    "issuer",
    "request_id",
    "decision_receipt_hash",
    "mesh_id",
    "snapshot_id",
    "before_state_hash",
    "after_state_hash",
    "delta_hash",
    "policy_hash",
    "evaluation_context_hash",
    "execution_scope_hash",
    "issued_at",
    "expires_at",
    "key_id",
    "trust_epoch",
    "nonce",
    "signature",
)
REQUIRED_INVARIANTS = (
    "conditional_decision_required",
    "fencing_token_required",
    "immutable_snapshot_required",
    "signed_phigov_certificate_required",
    "prepared_transition_before_live_mutation",
    "lineage_authorization_attestation_required",
    "commit_after_attestation_only",
    "lineage_completion_attestation_required",
    "production_state_changing_blocked",
    "development_reference_not_runtime_authority",
)
REQUIRED_MAPPING_SURFACES = (
    "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
    "gateway/distributed_lease_boundary.py",
    "schemas/forge_write_spine_bridge.schema.json",
    "mcoi/mcoi_runtime/contracts/receipt_signing.py",
    "gateway/command_spine.py",
    "docs/FOUNDATION_MODE.md",
)


@dataclass(frozen=True, slots=True)
class ForgeWriteSpineBridgeValidation:
    """Validation report for the Forge write-spine bridge."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    bridge_path: str
    stage_count: int
    invariant_count: int
    production_state_changing: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_write_spine_bridge(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    bridge_path: Path = DEFAULT_BRIDGE,
) -> ForgeWriteSpineBridgeValidation:
    """Validate bridge schema shape and state-write semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge write-spine bridge schema", errors)
    bridge = _load_json_object(bridge_path, "Forge write-spine bridge", errors)
    if schema and bridge:
        errors.extend(f"{_path_label(bridge_path)}: {error}" for error in _validate_schema_instance(schema, bridge))
        _validate_reference_boundary(bridge, errors, _path_label(bridge_path))
        _validate_stage_order(bridge, errors, _path_label(bridge_path))
        _validate_certificate_contract(bridge, errors, _path_label(bridge_path))
        _validate_service_boundary(bridge, errors, _path_label(bridge_path))
        _validate_workspace_mapping(bridge, errors, _path_label(bridge_path))
        _validate_required_invariants(bridge, errors, _path_label(bridge_path))
    deployment_boundary = bridge.get("deployment_boundary", {}) if isinstance(bridge, Mapping) else {}
    write_spine = bridge.get("write_spine", ()) if isinstance(bridge, Mapping) else ()
    invariants = bridge.get("required_invariants", ()) if isinstance(bridge, Mapping) else ()
    return ForgeWriteSpineBridgeValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        bridge_path=_path_label(bridge_path),
        stage_count=len(write_spine) if isinstance(write_spine, list) else 0,
        invariant_count=len(invariants) if isinstance(invariants, list) else 0,
        production_state_changing=str(deployment_boundary.get("production_state_changing", ""))
        if isinstance(deployment_boundary, Mapping)
        else "",
    )


def write_forge_write_spine_bridge_validation(
    validation: ForgeWriteSpineBridgeValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic bridge validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_reference_boundary(bridge: Mapping[str, Any], errors: list[str], label: str) -> None:
    source = bridge.get("source_repository", {})
    deployment = bridge.get("deployment_boundary", {})
    if bridge.get("application_mode") != "reference_contract_only":
        errors.append(f"{label}: application_mode must remain reference_contract_only")
    if bridge.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must remain false")
    if bridge.get("state_write_runtime_registered") is not False:
        errors.append(f"{label}: state_write_runtime_registered must remain false")
    if isinstance(source, Mapping) and source.get("production_state_changing") != "NO_GO":
        errors.append(f"{label}: source_repository.production_state_changing must remain NO_GO")
    if isinstance(deployment, Mapping) and deployment.get("production_state_changing") != "NO_GO":
        errors.append(f"{label}: deployment_boundary.production_state_changing must remain NO_GO")


def _validate_stage_order(bridge: Mapping[str, Any], errors: list[str], label: str) -> None:
    stages = bridge.get("write_spine")
    if not isinstance(stages, list):
        errors.append(f"{label}: write_spine must be a list")
        return
    stage_ids = tuple(str(stage.get("stage_id", "")) for stage in stages if isinstance(stage, Mapping))
    orders = tuple(int(stage.get("order", 0) or 0) for stage in stages if isinstance(stage, Mapping))
    if stage_ids != EXPECTED_STAGE_IDS:
        errors.append(f"{label}: write_spine stage order must match the canonical Forge bridge")
    if orders != tuple(range(1, len(EXPECTED_STAGE_IDS) + 1)):
        errors.append(f"{label}: write_spine order fields must be contiguous from 1 to 7")
    by_id = {str(stage.get("stage_id", "")): stage for stage in stages if isinstance(stage, Mapping)}
    if by_id.get("phigov_certificate", {}).get("commit_gate") != "before_prepare":
        errors.append(f"{label}: Phi_gov certificate must gate before prepare")
    if by_id.get("lineage_authorization_attestation", {}).get("commit_gate") != "before_commit":
        errors.append(f"{label}: lineage authorization attestation must gate before commit")
    if by_id.get("fenced_commit", {}).get("order", 0) <= by_id.get("lineage_authorization_attestation", {}).get("order", 99):
        errors.append(f"{label}: fenced commit must occur after lineage authorization attestation")
    stage_positions = {stage_id: index + 1 for index, stage_id in enumerate(stage_ids)}
    if stage_positions.get("fenced_commit", 0) <= stage_positions.get("lineage_authorization_attestation", 99):
        errors.append(f"{label}: fenced commit must occur after lineage authorization attestation")
    if by_id.get("lineage_completion_attestation", {}).get("commit_gate") != "after_commit":
        errors.append(f"{label}: lineage completion attestation must gate after commit")


def _validate_certificate_contract(bridge: Mapping[str, Any], errors: list[str], label: str) -> None:
    certificate = bridge.get("certificate_contract")
    if not isinstance(certificate, Mapping):
        errors.append(f"{label}: certificate_contract must be an object")
        return
    fields = certificate.get("required_fields")
    if not isinstance(fields, list):
        errors.append(f"{label}: certificate_contract.required_fields must be a list")
        return
    observed = tuple(str(field) for field in fields)
    if observed != EXPECTED_CERTIFICATE_FIELDS:
        errors.append(f"{label}: certificate_contract.required_fields must preserve canonical field order")
    if certificate.get("development_only") is not True:
        errors.append(f"{label}: certificate_contract.development_only must remain true")
    if "decision_receipt_hash" not in observed or "delta_hash" not in observed:
        errors.append(f"{label}: certificate_contract must bind decision receipt and delta hash")
    if "nonce" not in observed or "signature" not in observed:
        errors.append(f"{label}: certificate_contract must bind nonce and signature")


def _validate_service_boundary(bridge: Mapping[str, Any], errors: list[str], label: str) -> None:
    service = bridge.get("service_boundary")
    if not isinstance(service, Mapping):
        errors.append(f"{label}: service_boundary must be an object")
        return
    required_true = (
        "signed_rpc",
        "caller_audience_binding",
        "request_expiry",
        "persistent_nonce_replay_guard",
        "pinned_phigov_trust_root",
        "pinned_lineage_identity",
        "local_development_keys",
    )
    for key in required_true:
        if service.get(key) is not True:
            errors.append(f"{label}: service_boundary.{key} must remain true")
    if service.get("transport_confidentiality") is not False:
        errors.append(f"{label}: transport_confidentiality must remain false until production transport exists")
    if service.get("production_authorized") is not False:
        errors.append(f"{label}: production_authorized must remain false")


def _validate_workspace_mapping(bridge: Mapping[str, Any], errors: list[str], label: str) -> None:
    mappings = bridge.get("workspace_mapping")
    if not isinstance(mappings, list):
        errors.append(f"{label}: workspace_mapping must be a list")
        return
    surfaces = tuple(
        str(mapping.get("workspace_surface", ""))
        for mapping in mappings
        if isinstance(mapping, Mapping)
    )
    for required_surface in REQUIRED_MAPPING_SURFACES:
        if required_surface not in surfaces:
            errors.append(f"{label}: workspace_mapping missing {required_surface}")
    mapping_by_surface = {
        str(mapping.get("workspace_surface", "")): mapping
        for mapping in mappings
        if isinstance(mapping, Mapping)
    }
    if mapping_by_surface.get("schemas/forge_write_spine_bridge.schema.json", {}).get("status") != "reference_only":
        errors.append(f"{label}: bridge schema mapping must remain reference_only")


def _validate_required_invariants(bridge: Mapping[str, Any], errors: list[str], label: str) -> None:
    invariants = bridge.get("required_invariants")
    if not isinstance(invariants, list):
        errors.append(f"{label}: required_invariants must be a list")
        return
    observed = tuple(str(invariant) for invariant in invariants)
    if observed != REQUIRED_INVARIANTS:
        errors.append(f"{label}: required_invariants must preserve canonical order")
    if len(set(observed)) != len(observed):
        errors.append(f"{label}: required_invariants must be unique")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse Forge write-spine bridge validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge write-spine bridge.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--bridge", default=str(DEFAULT_BRIDGE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge write-spine bridge validation."""

    args = parse_args(argv)
    validation = validate_forge_write_spine_bridge(
        schema_path=Path(args.schema),
        bridge_path=Path(args.bridge),
    )
    write_forge_write_spine_bridge_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE WRITE-SPINE BRIDGE VALID")
    else:
        print(f"FORGE WRITE-SPINE BRIDGE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
