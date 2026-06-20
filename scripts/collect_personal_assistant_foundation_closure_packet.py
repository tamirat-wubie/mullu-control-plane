#!/usr/bin/env python3
"""Collect a Personal Assistant foundation closure packet.

Purpose: bind the existing Personal Assistant Foundation Mode receipt chain
into one replayable no-effect closure packet.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: checked-in Personal Assistant evidence receipts.
Invariants:
  - Collection reads local JSON evidence only.
  - The packet grants no execution, connector, memory, deployment, or customer authority.
  - The packet is not live activation, product readiness, or terminal closure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_foundation_closure_packet.json"

SOURCE_RECEIPTS: tuple[tuple[str, Path, str], ...] = (
    (
        "foundation_evidence",
        REPO_ROOT / "examples" / "personal_assistant_foundation_evidence_receipt.json",
        "foundation_evidence_closed",
    ),
    (
        "readiness_index",
        REPO_ROOT / "examples" / "personal_assistant_readiness_index_receipt.json",
        "readiness_index_closed",
    ),
    (
        "coherence_ledger",
        REPO_ROOT / "examples" / "personal_assistant_coherence_ledger_receipt.json",
        "coherence_ledger_closed",
    ),
    (
        "authority_coverage",
        REPO_ROOT / "examples" / "personal_assistant_authority_coverage_receipt.json",
        "authority_coverage_closed",
    ),
    (
        "capsule_alignment",
        REPO_ROOT / "examples" / "personal_assistant_capsule_alignment_receipt.json",
        "capsule_alignment_closed",
    ),
    (
        "policy_matrix",
        REPO_ROOT / "examples" / "personal_assistant_policy_matrix_receipt.json",
        "policy_matrix_closed",
    ),
    (
        "runtime_boundary",
        REPO_ROOT / "examples" / "personal_assistant_runtime_boundary_receipt.json",
        "runtime_boundary_closed",
    ),
    (
        "skill_readiness_catalog",
        REPO_ROOT / "examples" / "personal_assistant_skill_readiness_catalog.json",
        "catalog_closed",
    ),
    (
        "dry_run_packet",
        REPO_ROOT / "examples" / "personal_assistant_dry_run_packet.json",
        "dry_run_packet_closed",
    ),
)

NO_EFFECT_FLAGS = (
    "execution_allowed",
    "runtime_execution_authority_granted",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "external_write_allowed",
    "system_of_record_write_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "money_legal_public_allowed",
    "production_ready_claim_allowed",
    "customer_readiness_claim_allowed",
    "customer_ready_claim_allowed",
    "public_readiness_claim_allowed",
    "live_nested_mind_activation_allowed",
    "nested_mind_live_activation_allowed",
    "secret_values_serialized",
    "raw_private_payloads_serialized",
    "raw_private_payload_serialized",
    "raw_connector_payload_serialized",
)

AUTHORITY_DENIALS = (
    "live_connector_execution",
    "connector_mutation",
    "external_write",
    "system_of_record_write",
    "memory_write",
    "deployment_mutation",
    "money_legal_public_action",
    "customer_readiness_claim",
    "production_readiness_claim",
    "live_nested_mind_activation",
    "terminal_closure",
)

BLOCKED_SECRET_VALUE_MARKERS = (
    "access_token=",
    "api_key=",
    "authorization: bearer",
    "bearer ",
    "client_secret=",
    "password=",
    "private_key=",
    "-----begin private key-----",
)

TEXT_SOURCE_SUFFIXES = frozenset({".json", ".md", ".py", ".yaml", ".yml"})


def collect_personal_assistant_foundation_closure_packet(
    *,
    receipt_sources: tuple[tuple[str, Path, str], ...] = SOURCE_RECEIPTS,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect Personal Assistant foundation closure packet."""
    generated_at = _format_utc(now_utc or datetime.now(UTC))
    source_records = [
        _source_receipt_record(source_kind, source_path, closure_field)
        for source_kind, source_path, closure_field in receipt_sources
    ]
    secret_value_markers = sorted(_secret_markers_for_records(source_records))
    all_sources_bound = all(record["bound"] is True for record in source_records)
    all_sources_schema_versioned = all(record["schema_versioned"] is True for record in source_records)
    all_sources_solved_verified = all(record["solver_outcome"] == "SolvedVerified" for record in source_records)
    all_source_closure_flags_pass = all(record["closed"] is True for record in source_records)
    all_no_effect_boundaries_clear = all(record["effect_violation_count"] == 0 for record in source_records)
    all_source_receipts_non_authoritative = all(record["receipt_non_authoritative"] is True for record in source_records)
    no_secret_values_serialized = not secret_value_markers
    authority_denial_records = [
        {
            "authority": authority,
            "denied": True,
            "denial_reason": "Foundation Mode closure packet grants no live or effect-bearing authority.",
        }
        for authority in AUTHORITY_DENIALS
    ]
    no_effect_boundary = {
        "execution_authority_granted": False,
        "live_connector_execution_allowed": False,
        "connector_mutation_allowed": False,
        "external_effect_allowed": False,
        "system_of_record_write_allowed": False,
        "memory_write_allowed": False,
        "deployment_mutation_allowed": False,
        "money_legal_public_allowed": False,
        "production_ready_claim_allowed": False,
        "customer_ready_claim_allowed": False,
        "live_nested_mind_activation_allowed": False,
        "terminal_closure_claim_allowed": False,
    }
    packet_closed = (
        all_sources_bound
        and all_sources_schema_versioned
        and all_sources_solved_verified
        and all_source_closure_flags_pass
        and all_no_effect_boundaries_clear
        and all_source_receipts_non_authoritative
        and no_secret_values_serialized
        and not any(no_effect_boundary.values())
    )
    proof_state = "Pass" if packet_closed else "Fail"
    solver_outcome = "SolvedVerified" if packet_closed else "AwaitingEvidence"

    packet_without_id = {
        "schema_version": "personal_assistant.foundation_closure_packet.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "packet_is_not_execution_authority": True,
        "packet_is_not_terminal_closure": True,
        "packet_is_not_customer_readiness": True,
        "source_receipts": source_records,
        "authority_denials": authority_denial_records,
        "no_effect_boundary": no_effect_boundary,
        "closure_summary": {
            "foundation_closure_packet_closed": packet_closed,
            "source_receipt_count": len(source_records),
            "bound_source_receipt_count": sum(1 for record in source_records if record["bound"] is True),
            "solved_verified_source_receipt_count": sum(
                1 for record in source_records if record["solver_outcome"] == "SolvedVerified"
            ),
            "closed_source_receipt_count": sum(1 for record in source_records if record["closed"] is True),
            "effect_violation_count": sum(_int(record["effect_violation_count"]) for record in source_records),
            "secret_value_marker_count": len(secret_value_markers),
            "all_sources_bound": all_sources_bound,
            "all_sources_schema_versioned": all_sources_schema_versioned,
            "all_sources_solved_verified": all_sources_solved_verified,
            "all_source_closure_flags_pass": all_source_closure_flags_pass,
            "all_no_effect_boundaries_clear": all_no_effect_boundaries_clear,
            "all_source_receipts_non_authoritative": all_source_receipts_non_authoritative,
            "no_secret_values_serialized": no_secret_values_serialized,
            "live_connector_execution_ready": False,
            "memory_write_ready": False,
            "deployment_mutation_ready": False,
            "customer_ready": False,
            "live_nested_mind_ready": False,
            "next_allowed_action": "continue_foundation_hardening_only",
        },
        "secret_value_markers": secret_value_markers,
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-foundation-closure-packet-{generated_at[:10]}",
                    "reason": _lineage_reason(packet_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {
        "packet_id": _packet_id(packet_without_id),
        **packet_without_id,
    }


def write_personal_assistant_foundation_closure_packet(
    packet: Mapping[str, object],
    output_path: Path,
) -> Path:
    """Write one local Personal Assistant foundation closure packet."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _source_receipt_record(source_kind: str, source_path: Path, closure_field: str) -> dict[str, object]:
    bound = source_path.exists()
    payload = _read_json_object(source_path, source_kind) if bound else {}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    summary = _summary_object(payload)
    effect_violations = _effect_violations(payload)
    return {
        "source_kind": source_kind,
        "source_ref": _path_label(source_path),
        "source_sha256": _file_sha256(source_path) if bound else "",
        "receipt_id": _bounded_identifier(payload.get("receipt_id") or payload.get("packet_id") or payload.get("catalog_id")),
        "schema_version": _bounded_identifier(payload.get("schema_version")),
        "schema_versioned": isinstance(payload.get("schema_version"), str) and bool(payload.get("schema_version")),
        "proof_state": _bounded_outcome(payload.get("proof_state"), allowed={"Pass", "Fail"}),
        "solver_outcome": _bounded_outcome(
            payload.get("solver_outcome"),
            allowed={"SolvedVerified", "AwaitingEvidence"},
        ),
        "closure_field": closure_field,
        "closed": summary.get(closure_field) is True,
        "no_effect_boundary_verified": _no_effect_verified(payload, summary),
        "receipt_non_authoritative": _receipt_non_authoritative(payload),
        "effect_violation_count": len(effect_violations),
        "effect_violations": effect_violations,
        "bound": bound,
        "payload_digest_only": True,
        "serialized_length": len(serialized),
    }


def _summary_object(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in (
        "summary",
        "coherence_summary",
        "authority_summary",
        "alignment_summary",
        "policy_matrix_summary",
        "runtime_boundary_summary",
        "catalog_summary",
        "closure_summary",
    ):
        if isinstance(payload.get(key), dict):
            return payload[key]  # type: ignore[return-value]
    return {}


def _no_effect_verified(payload: Mapping[str, Any], summary: Mapping[str, Any]) -> bool:
    if summary.get("no_effect_boundary_verified") is True:
        return True
    if summary.get("runtime_boundary_closed") is True and summary.get("no_effect_boundary_verified") is True:
        return True
    if summary.get("all_skills_non_executable") is True and summary.get("all_skills_foundation_only") is True:
        return True
    if summary.get("no_effect_boundaries_clear") is True:
        return True
    boundary = payload.get("effect_boundary") or payload.get("no_effect_boundary")
    return isinstance(boundary, dict) and not any(value is True for value in boundary.values())


def _receipt_non_authoritative(payload: Mapping[str, Any]) -> bool:
    authority_flags = (
        payload.get("receipt_is_not_execution_authority"),
        payload.get("receipt_is_not_terminal_closure"),
        payload.get("packet_is_not_execution_authority"),
        payload.get("packet_is_not_terminal_closure"),
        payload.get("catalog_is_not_execution_authority"),
    )
    return any(flag is True for flag in authority_flags) and payload.get("solver_outcome") in {
        "SolvedVerified",
        "AwaitingEvidence",
    }


def _effect_violations(payload: Mapping[str, Any]) -> list[str]:
    violations: set[str] = set()
    for boundary_key in ("effect_boundary", "no_effect_boundary"):
        boundary = payload.get(boundary_key)
        if isinstance(boundary, dict):
            _collect_effect_violations(boundary, violations)
    return sorted(violations)


def _collect_effect_violations(value: object, violations: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in NO_EFFECT_FLAGS and child is True:
                violations.add(key)
            elif isinstance(child, (dict, list)):
                _collect_effect_violations(child, violations)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                _collect_effect_violations(item, violations)


def _secret_markers_for_records(records: list[Mapping[str, object]]) -> set[str]:
    markers: set[str] = set()
    for record in records:
        serialized = json.dumps(record, sort_keys=True).casefold()
        markers.update(marker for marker in BLOCKED_SECRET_VALUE_MARKERS if marker in serialized)
    return markers


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to read Personal Assistant {label} receipt") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Personal Assistant {label} receipt must be a JSON object")
    return parsed


def _file_sha256(path: Path) -> str:
    return canonical_source_sha256(path)


def canonical_source_sha256(path: Path) -> str:
    """Return a newline-stable SHA-256 digest for checked-in text sources."""
    raw_bytes = path.read_bytes()
    if path.suffix.casefold() not in TEXT_SOURCE_SUFFIXES:
        return hashlib.sha256(raw_bytes).hexdigest()
    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"failed to decode Personal Assistant text source: {_path_label(path)}") from exc
    normalized_newlines = source_text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized_newlines.encode("utf-8")).hexdigest()


def _packet_id(packet_without_id: Mapping[str, object]) -> str:
    material = json.dumps(packet_without_id, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"personal-assistant-foundation-closure-{hashlib.sha256(material).hexdigest()[:16]}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _path_label(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _bounded_identifier(value: object) -> str:
    return value if isinstance(value, str) and value else "missing"


def _bounded_outcome(value: object, *, allowed: set[str]) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    if "Fail" in allowed:
        return "Fail"
    return "AwaitingEvidence"


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _lineage_reason(packet_closed: bool) -> str:
    if packet_closed:
        return "Bound Personal Assistant Foundation Mode receipt chain without granting live authority."
    return "Bound Personal Assistant Foundation Mode receipt chain and preserved AwaitingEvidence."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse Personal Assistant foundation closure packet arguments."""
    parser = argparse.ArgumentParser(description="Collect a Personal Assistant foundation closure packet.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """Run the Personal Assistant foundation closure packet collector."""
    args = parse_args(argv)
    packet = collect_personal_assistant_foundation_closure_packet(now_utc=now_utc)
    write_personal_assistant_foundation_closure_packet(packet, args.output)
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=False))
    else:
        print(f"foundation_closure_packet: {_path_label(args.output)}")
        print(f"packet_id: {packet['packet_id']}")
        print(f"solver_outcome: {packet['solver_outcome']}")
        print(f"foundation_closure_packet_closed: {packet['closure_summary']['foundation_closure_packet_closed']}")  # type: ignore[index]
    return 0 if packet["proof_state"] == "Pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
