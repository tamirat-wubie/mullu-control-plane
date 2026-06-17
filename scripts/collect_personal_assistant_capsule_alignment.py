#!/usr/bin/env python3
"""Collect a Personal Assistant capsule alignment receipt.

Purpose: project checked-in Personal Assistant capsule, capability pack,
schema manifest, and authority coverage evidence into a replayable no-effect
capsule alignment receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: personal-assistant capsule, capability pack, protocol manifest,
authority coverage receipt, and referenced schema files.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The receipt is not execution authority and is not terminal closure.
  - Foundation Mode keeps production, customer, and live Nested Mind claims blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CAPSULE = REPO_ROOT / "capsules" / "personal_assistant.json"
DEFAULT_CAPABILITY_PACK = REPO_ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
DEFAULT_PROTOCOL_MANIFEST = REPO_ROOT / "schemas" / "mullu_governance_protocol.manifest.json"
DEFAULT_AUTHORITY_COVERAGE = REPO_ROOT / "examples" / "personal_assistant_authority_coverage_receipt.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_capsule_alignment_receipt.json"

NO_EFFECT_FLAGS = (
    "execution_authority_granted",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "system_of_record_write_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "money_legal_public_allowed",
    "production_ready_claim_allowed",
    "customer_ready_claim_allowed",
    "live_nested_mind_activation_allowed",
)


def collect_personal_assistant_capsule_alignment(
    *,
    capsule_path: Path = DEFAULT_CAPSULE,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
    protocol_manifest_path: Path = DEFAULT_PROTOCOL_MANIFEST,
    authority_coverage_path: Path = DEFAULT_AUTHORITY_COVERAGE,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect Personal Assistant capsule alignment receipt."""
    capsule = _read_json_object(capsule_path, "capsule")
    capability_pack = _read_json_object(capability_pack_path, "capability pack")
    protocol_manifest = _read_json_object(protocol_manifest_path, "protocol manifest")
    authority_coverage = _read_json_object(authority_coverage_path, "authority coverage receipt")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    capability_refs = set(_string_list(capsule.get("capability_refs")))
    capabilities = _list_of_objects(capability_pack.get("capabilities"))
    pack_capability_ids = {_bounded_identifier(capability.get("capability_id")) for capability in capabilities}
    manifest_paths = _manifest_paths(protocol_manifest)
    authority_summary = _object(authority_coverage.get("authority_summary"))
    capability_records = _capability_binding_records(capabilities, capability_refs)
    schema_records = _schema_binding_records(capabilities, manifest_paths)
    capsule_boundary = _capsule_boundary(capsule)
    effect_boundary = {flag: False for flag in NO_EFFECT_FLAGS}

    capsule_refs_match_pack = capability_refs == pack_capability_ids
    all_capability_refs_bound = all(record["in_capsule"] and record["in_capability_pack"] for record in capability_records)
    all_schema_refs_bound = all(record["manifest_bound"] and record["file_bound"] for record in schema_records)
    all_policy_refs_bound = all((_repo_path(ref)).exists() for ref in _string_list(capsule.get("policy_refs")))
    all_test_fixture_refs_bound = all((_repo_path(ref)).exists() for ref in _string_list(capsule.get("test_fixture_refs")))
    all_capabilities_candidate_only = all(record["certification_status"] == "candidate" for record in capability_records)
    all_capabilities_fixture_only = all(record["fixture_only"] is True for record in capability_records)
    all_capabilities_secretless = all(record["secret_scope"] == "none" for record in capability_records)
    all_capabilities_networkless = all(record["network_allowlist_empty"] is True for record in capability_records)
    all_capabilities_non_world_mutating = all(record["world_mutating"] is False for record in capability_records)
    all_capabilities_receipted = all(record["receipt_required"] is True for record in capability_records)
    no_effect_boundary_verified = not any(effect_boundary.values())
    authority_coverage_closed = authority_summary.get("authority_coverage_closed") is True

    capsule_alignment_closed = (
        authority_coverage_closed
        and capsule_refs_match_pack
        and all_capability_refs_bound
        and all_schema_refs_bound
        and all_policy_refs_bound
        and all_test_fixture_refs_bound
        and all_capabilities_candidate_only
        and all_capabilities_fixture_only
        and all_capabilities_secretless
        and all_capabilities_networkless
        and all_capabilities_non_world_mutating
        and all_capabilities_receipted
        and capsule_boundary["foundation_mode_required"] is True
        and capsule_boundary["production_ready"] is False
        and capsule_boundary["live_connector_execution_allowed"] is False
        and capsule_boundary["live_nested_mind_activation_allowed"] is False
        and all(record["alignment_covered"] is True for record in capability_records)
        and no_effect_boundary_verified
    )
    proof_state = "Pass" if capsule_alignment_closed else "Fail"
    solver_outcome = "SolvedVerified" if capsule_alignment_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.capsule_alignment_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "source_refs": _source_refs(capsule_path, capability_pack_path, protocol_manifest_path, authority_coverage_path),
        "alignment_summary": {
            "capsule_alignment_closed": capsule_alignment_closed,
            "authority_coverage_closed": authority_coverage_closed,
            "capsule_capability_count": len(capability_refs),
            "pack_capability_count": len(pack_capability_ids),
            "schema_ref_count": len(schema_records),
            "capsule_refs_match_pack": capsule_refs_match_pack,
            "all_capability_refs_bound": all_capability_refs_bound,
            "all_schema_refs_bound": all_schema_refs_bound,
            "all_policy_refs_bound": all_policy_refs_bound,
            "all_test_fixture_refs_bound": all_test_fixture_refs_bound,
            "all_capabilities_candidate_only": all_capabilities_candidate_only,
            "all_capabilities_fixture_only": all_capabilities_fixture_only,
            "all_capabilities_secretless": all_capabilities_secretless,
            "all_capabilities_networkless": all_capabilities_networkless,
            "all_capabilities_non_world_mutating": all_capabilities_non_world_mutating,
            "all_capabilities_receipted": all_capabilities_receipted,
            "capsule_foundation_mode_required": capsule_boundary["foundation_mode_required"],
            "capsule_live_connector_execution_blocked": capsule_boundary["live_connector_execution_allowed"] is False,
            "capsule_live_nested_mind_activation_blocked": capsule_boundary["live_nested_mind_activation_allowed"] is False,
            "no_effect_boundary_verified": no_effect_boundary_verified,
            "production_ready": False,
            "customer_ready": False,
            "next_allowed_action": "continue_foundation_hardening_only",
        },
        "capability_binding_records": capability_records,
        "schema_binding_records": schema_records,
        "capsule_boundary": capsule_boundary,
        "effect_boundary": effect_boundary,
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-capsule-alignment-{generated_at[:10]}",
                    "reason": _lineage_reason(capsule_alignment_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {"receipt_id": _receipt_id(receipt_without_id), **receipt_without_id}


def write_personal_assistant_capsule_alignment(receipt: Mapping[str, object], output_path: Path) -> Path:
    """Write one local Personal Assistant capsule alignment receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _source_refs(*paths: Path) -> list[dict[str, object]]:
    kinds = ("capsule", "capability_pack", "protocol_manifest", "authority_coverage_receipt")
    return [
        {
            "source_id": f"personal_assistant_{kind}",
            "source_ref": _path_label(path),
            "source_kind": kind,
            "bound": path.exists(),
        }
        for kind, path in zip(kinds, paths, strict=True)
    ]


def _capability_binding_records(
    capabilities: list[Mapping[str, Any]],
    capsule_refs: set[str],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for capability in capabilities:
        capability_id = _bounded_identifier(capability.get("capability_id"))
        metadata = _object(capability.get("metadata"))
        isolation_profile = _object(capability.get("isolation_profile"))
        governed_record = _object(_object(capability.get("extensions")).get("governed_record"))
        input_schema_ref = _bounded_identifier(capability.get("input_schema_ref"))
        output_schema_ref = _bounded_identifier(capability.get("output_schema_ref"))
        network_allowlist = _string_list(isolation_profile.get("network_allowlist"))
        certification_status = _bounded_identifier(capability.get("certification_status"))
        fixture_only = metadata.get("fixture_only") is True
        production_ready = metadata.get("production_ready") is True
        secret_scope = _bounded_identifier(isolation_profile.get("secret_scope"))
        world_mutating = governed_record.get("world_mutating") is True
        receipt_required = governed_record.get("receipt_required") is True
        input_schema_bound = _repo_path(input_schema_ref).exists()
        output_schema_bound = _repo_path(output_schema_ref).exists()
        alignment_covered = (
            capability_id in capsule_refs
            and certification_status == "candidate"
            and fixture_only
            and not production_ready
            and secret_scope == "none"
            and not network_allowlist
            and not world_mutating
            and receipt_required
            and input_schema_bound
            and output_schema_bound
        )
        records.append(
            {
                "capability_id": capability_id,
                "in_capsule": capability_id in capsule_refs,
                "in_capability_pack": bool(capability_id),
                "input_schema_ref": input_schema_ref,
                "input_schema_bound": input_schema_bound,
                "output_schema_ref": output_schema_ref,
                "output_schema_bound": output_schema_bound,
                "certification_status": certification_status,
                "fixture_only": fixture_only,
                "production_ready": production_ready,
                "secret_scope": secret_scope,
                "network_allowlist_empty": not network_allowlist,
                "world_mutating": world_mutating,
                "receipt_required": receipt_required,
                "alignment_covered": alignment_covered,
            }
        )
    return records


def _schema_binding_records(
    capabilities: list[Mapping[str, Any]],
    manifest_paths: set[str],
) -> list[dict[str, object]]:
    schema_refs = sorted(
        {
            ref
            for capability in capabilities
            for ref in (
                _bounded_identifier(capability.get("input_schema_ref")),
                _bounded_identifier(capability.get("output_schema_ref")),
            )
            if ref
        }
    )
    return [
        {
            "schema_ref": schema_ref,
            "schema_id": Path(schema_ref).name.removesuffix(".schema.json").replace("_", "-"),
            "manifest_bound": schema_ref in manifest_paths,
            "file_bound": _repo_path(schema_ref).exists(),
        }
        for schema_ref in schema_refs
    ]


def _capsule_boundary(capsule: Mapping[str, Any]) -> dict[str, bool]:
    extensions = _object(capsule.get("extensions"))
    return {
        "foundation_mode_required": extensions.get("foundation_mode_required") is True,
        "production_ready": extensions.get("production_ready") is True,
        "live_connector_execution_allowed": extensions.get("live_connector_execution_allowed") is True,
        "live_nested_mind_activation_allowed": extensions.get("live_nested_mind_activation_allowed") is True,
    }


def _manifest_paths(protocol_manifest: Mapping[str, Any]) -> set[str]:
    schemas = _list_of_objects(protocol_manifest.get("schemas"))
    return {_bounded_identifier(record.get("path")) for record in schemas}


def _lineage_reason(alignment_closed: bool) -> str:
    if alignment_closed:
        return "Capsule alignment closed for no-effect Foundation Mode hardening without granting execution authority."
    return "Capsule alignment remains AwaitingEvidence because at least one capsule, capability, or schema binding is open."


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"failed to read Personal Assistant {label}") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Personal Assistant {label} was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Personal Assistant {label} must be a JSON object")
    return parsed


def _receipt_id(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"personal-assistant-capsule-alignment-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_path(ref: str) -> Path:
    return REPO_ROOT / ref


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _object(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _bounded_identifier(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """Run the Personal Assistant capsule alignment collector."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsule", type=Path, default=DEFAULT_CAPSULE)
    parser.add_argument("--capability-pack", type=Path, default=DEFAULT_CAPABILITY_PACK)
    parser.add_argument("--protocol-manifest", type=Path, default=DEFAULT_PROTOCOL_MANIFEST)
    parser.add_argument("--authority-coverage", type=Path, default=DEFAULT_AUTHORITY_COVERAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print the generated receipt as JSON.")
    args = parser.parse_args(argv)

    receipt = collect_personal_assistant_capsule_alignment(
        capsule_path=args.capsule,
        capability_pack_path=args.capability_pack,
        protocol_manifest_path=args.protocol_manifest,
        authority_coverage_path=args.authority_coverage,
        now_utc=now_utc,
    )
    write_personal_assistant_capsule_alignment(receipt, args.output)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"capsule_alignment_receipt: {_path_label(args.output)}")
        print(f"receipt_id: {receipt['receipt_id']}")
        print(f"solver_outcome: {receipt['solver_outcome']}")
        print(f"capsule_alignment_closed: {receipt['alignment_summary']['capsule_alignment_closed']}")  # type: ignore[index]
    return 0 if receipt["proof_state"] == "Pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
