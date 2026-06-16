#!/usr/bin/env python3
"""Validate the TrustedCaptureEvidencePacket contract.

Purpose: verify that capture evidence remains digest-only, operator-scoped,
and separated from browser, screen, video, audio, sensor, write, connector, and
publication authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, capture
policy decision ledger, evidence classification, browser observation receipt,
UAO, and LifeMeaningJudgment schemas.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example stores no raw surface, media, audio, sensor payload,
    source body, or secret values.
  - Live capture, media recording, camera, microphone, sensor reads, file
    writes, connector calls, external writes, publication, terminal closure,
    and success claims remain denied.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "trusted_capture_evidence_packet.schema.json"
DEFAULT_PACKET_PATH = WORKSPACE_ROOT / "examples" / "trusted_capture_evidence_packet.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:trusted-capture-evidence-packet:1"
EXPECTED_SCHEMA_TITLE = "Trusted Capture Evidence Packet"
EXPECTED_PACKET_VERSION = "trusted_capture_evidence_packet.v1"
REQUIRED_RECEIPT_REFS = {
    "trusted_capture_evidence_packet_schema": "schemas/trusted_capture_evidence_packet.schema.json",
    "capture_policy_decision_ledger_schema": "schemas/capture_policy_decision_ledger.schema.json",
    "evidence_classification_manifest_schema": "schemas/evidence_classification_manifest.schema.json",
    "browser_observation_receipt_schema": "schemas/browser_observation_receipt.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/trusted_capture_evidence_packet.schema.json",
    "examples/trusted_capture_evidence_packet.foundation.json",
    "scripts/validate_trusted_capture_evidence_packet.py",
    "tests/test_validate_trusted_capture_evidence_packet.py",
    "docs/89_trusted_capture_evidence_packet_contract.md",
    "schemas/capture_policy_decision_ledger.schema.json",
    "schemas/evidence_classification_manifest.schema.json",
    "schemas/browser_observation_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "docs/82_cross_repo_opportunity_map.md",
)
DENIED_AUTHORITY_FIELDS = (
    "live_capture_performed",
    "media_recording_performed",
    "screen_recording_performed",
    "microphone_capture_performed",
    "camera_capture_performed",
    "sensor_read_performed",
    "file_write_performed",
    "connector_call_performed",
    "external_write_performed",
    "raw_media_stored",
    "raw_source_body_stored",
    "raw_secret_value_stored",
    "publication_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
RAW_STORAGE_FIELDS = (
    "raw_surface_stored",
    "raw_media_stored",
    "raw_audio_stored",
    "raw_sensor_payload_stored",
    "raw_secret_value_stored",
)
DIGEST_FIELDS = (
    ("capture_scope", "source_surface_hash"),
    ("capture_artifacts", "surface_digest_ref"),
    ("capture_artifacts", "frame_digest_ref"),
    ("capture_artifacts", "media_digest_ref"),
    ("capture_artifacts", "transcript_digest_ref"),
    ("capture_artifacts", "sensor_digest_ref"),
    ("capture_artifacts", "artifact_manifest_ref"),
)


class TrustedCaptureEvidencePacketError(ValueError):
    """Raised when a TrustedCaptureEvidencePacket artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TrustedCaptureEvidencePacketError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "packet_id",
            "packet_version",
            "capture_scope",
            "capture_artifacts",
            "authority_boundary",
            "privacy_guard",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_trusted_capture_evidence_packet_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one trusted capture packet."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("trusted capture evidence packet must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_capture_scope(record.get("capture_scope"), errors)
    _validate_capture_artifacts(record.get("capture_artifacts"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_privacy_guard(record.get("privacy_guard"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_trusted_capture_evidence_packet(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode packet."""

    schema = _load_schema(schema_path)
    packet = load_json_object(packet_path, "TrustedCaptureEvidencePacket")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_trusted_capture_evidence_packet_record(packet, schema))
    return errors


def build_mutated_trusted_capture_evidence_packet(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default packet."""

    packet = load_json_object(DEFAULT_PACKET_PATH, "TrustedCaptureEvidencePacket")
    mutated = deepcopy(packet)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("packet_version") != EXPECTED_PACKET_VERSION:
        errors.append("packet_version must match trusted_capture_evidence_packet.v1")
    for parent_name, field_name in DIGEST_FIELDS:
        parent = record.get(parent_name)
        value = parent.get(field_name) if isinstance(parent, dict) else None
        _validate_digest_ref(f"{parent_name}.{field_name}", value, errors)


def _validate_capture_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("capture_scope must be an object")
        return
    if scope.get("surface_redaction_policy") != "digest_only_no_raw_surface":
        errors.append("capture_scope.surface_redaction_policy must be digest_only_no_raw_surface")
    if scope.get("capture_mode") != "dry_run_operator_supplied_digest":
        errors.append("capture_scope.capture_mode must be dry_run_operator_supplied_digest")
    if scope.get("consent_scope") != "operator_local_explicit":
        errors.append("capture_scope.consent_scope must be operator_local_explicit")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("capture_scope.tenant_scope must be foundation-local-only")
    expected_refs = {
        "capture_policy_ref": REQUIRED_RECEIPT_REFS["capture_policy_decision_ledger_schema"],
        "evidence_classification_ref": REQUIRED_RECEIPT_REFS["evidence_classification_manifest_schema"],
    }
    for field_name, expected_ref in expected_refs.items():
        if scope.get(field_name) != expected_ref:
            errors.append(f"capture_scope.{field_name} must be {expected_ref}")
    for field_name in ("consent_ref", "uao_ref"):
        if not isinstance(scope.get(field_name), str) or scope.get(field_name) == "":
            errors.append(f"capture_scope.{field_name} must be non-empty")


def _validate_capture_artifacts(artifacts: Any, errors: list[str]) -> None:
    if not isinstance(artifacts, dict):
        errors.append("capture_artifacts must be an object")
        return
    if artifacts.get("browser_observation_ref") != REQUIRED_RECEIPT_REFS["browser_observation_receipt_schema"]:
        errors.append(
            "capture_artifacts.browser_observation_ref must be "
            f"{REQUIRED_RECEIPT_REFS['browser_observation_receipt_schema']}"
        )


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in DENIED_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_privacy_guard(guard: Any, errors: list[str]) -> None:
    if not isinstance(guard, dict):
        errors.append("privacy_guard must be an object")
        return
    for field_name in RAW_STORAGE_FIELDS:
        if guard.get(field_name) is not False:
            errors.append(f"privacy_guard.{field_name} must be false")
    if guard.get("private_payload_redacted") is not True:
        errors.append("privacy_guard.private_payload_redacted must be true")
    if guard.get("operator_review_required") is not True:
        errors.append("privacy_guard.operator_review_required must be true")
    if not isinstance(guard.get("retention_policy_ref"), str) or guard.get("retention_policy_ref") == "":
        errors.append("privacy_guard.retention_policy_ref must be non-empty")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    boundary = record.get("authority_boundary")
    guard = record.get("privacy_guard")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(boundary, dict) or not isinstance(guard, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("authority_boundary, privacy_guard, receipt_refs, and contract_summary must be typed")
        return
    if summary.get("digest_only") is not True:
        errors.append("contract_summary.digest_only must be true")
    if summary.get("capture_authority_denied") is not True:
        errors.append("contract_summary.capture_authority_denied must be true")
    expected_counts = {
        "authority_denial_count": len(DENIED_AUTHORITY_FIELDS),
        "privacy_guard_count": len(guard),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _validate_digest_ref(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{label} must be non-empty")
        return
    if not value.startswith("hash://sha256/"):
        errors.append(f"{label} must use hash://sha256/ digest ref")
    if "http://" in value or "https://" in value or "file://" in value:
        errors.append(f"{label} must not store raw capture URL, file path, or body")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate TrustedCaptureEvidencePacket artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate TrustedCaptureEvidencePacket contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_trusted_capture_evidence_packet(args.schema, args.packet)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "trusted_capture_evidence_packet_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "packet_path": workspace_display_path(args.packet),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] trusted_capture_evidence_packet")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
