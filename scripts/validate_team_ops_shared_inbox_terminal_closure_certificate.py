#!/usr/bin/env python3
"""Validate TeamOps shared inbox terminal closure certificates.

Purpose: prove a TeamOps terminal closure certificate is schema-valid, bound
to a ready review packet, redacted, and free of producer-side provider effects.
Governance scope: TeamOps terminal closure, evidence binding, replay binding,
duplicate-action protection, redaction, and no-production-claim checks.
Dependencies: schemas/terminal_closure_certificate.schema.json and
scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet.
Invariants:
  - Certificates must satisfy the canonical terminal closure schema.
  - TeamOps committed closure must bind the ready terminal review packet.
  - Raw content, secret markers, provider effects, and production claims are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_REVIEW_PACKET,
    TERMINAL_CERTIFICATE_SCHEMA_ID,
    WORKFLOW_ID,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_send_execution_receipt import SHA256_HEX_PATTERN  # noqa: E402
from scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_review_packet,
)
from scripts.validate_terminal_closure_certificate import (  # noqa: E402
    DEFAULT_SCHEMA,
    validate_terminal_closure_certificate,
)


DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_certificate_validation.json"
)
CERTIFICATE_ID_PATTERN = re.compile(r"^teamops-shared-inbox-terminal-closure-certificate-[0-9a-f]{16}$")
REVIEW_PACKET_ID_PATTERN = re.compile(r"^teamops-shared-inbox-terminal-closure-review-packet-[0-9a-f]{16}$")
RAW_FIELD_NAMES = {
    "raw_subject",
    "subject",
    "message_body",
    "body",
    "raw_sender",
    "sender_email",
    "recipient_email",
    "raw_recipient",
    "recipient",
    "raw_provider_response",
    "provider_response",
    "provider_message_id",
    "message_id",
    "raw_dispatch_receipt",
    "dispatch_receipt",
    "sent_message",
    "raw_sent_message",
    "provider_payload",
}
FALSE_METADATA_FIELDS = (
    "external_message_sent_by_minting_producer",
    "external_mailbox_write_performed_by_minting_producer",
    "provider_mutation_performed_by_minting_producer",
    "provider_call_performed_by_minting_producer",
    "draft_created_by_minting_producer",
    "raw_message_content_serialized",
    "raw_provider_payload_serialized",
    "production_ready_claimed",
)
TRUE_METADATA_FIELDS = (
    "terminal_proof",
    "team_ops_terminal_closure",
    "approval_chain_reviewed",
    "send_execution_reviewed",
    "sent_message_observation_reviewed",
    "duplicate_absence_reviewed",
    "deterministic_replay_reviewed",
    "duplicate_absence_observed",
    "deterministic_replay_observed",
    "no_secret_values_serialized",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxTerminalClosureCertificateValidation:
    """Validation result for one TeamOps terminal closure certificate."""

    valid: bool
    ready: bool
    certificate_path: str
    schema_path: str
    source_review_packet_path: str
    certificate_id: str
    source_review_packet_id: str
    disposition: str
    evidence_ref_count: int
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_terminal_closure_certificate(
    *,
    certificate_path: Path = DEFAULT_OUTPUT,
    source_review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> TeamOpsSharedInboxTerminalClosureCertificateValidation:
    """Validate one TeamOps terminal closure certificate."""

    errors: list[str] = []
    certificate = _load_json_object(certificate_path, "TeamOps terminal closure certificate", errors)
    generic_validation = validate_terminal_closure_certificate(
        certificate_path=certificate_path,
        schema_path=schema_path,
    )
    errors.extend(generic_validation.errors)
    if certificate:
        _validate_certificate_semantics(certificate, errors)
    review_packet = _load_json_object(source_review_packet_path, "TeamOps terminal closure review packet", errors)
    if certificate and review_packet:
        _validate_review_binding(certificate, review_packet, source_review_packet_path, errors)
    ready = not errors and _certificate_ready(certificate)
    if require_ready and not ready:
        errors.append("TeamOps terminal closure certificate ready must be true")
        ready = False
    metadata = certificate.get("metadata", {}) if isinstance(certificate.get("metadata"), dict) else {}
    evidence_refs = certificate.get("evidence_refs", [])
    return TeamOpsSharedInboxTerminalClosureCertificateValidation(
        valid=not errors,
        ready=ready,
        certificate_path=_path_label(certificate_path),
        schema_path=_path_label(schema_path),
        source_review_packet_path=_path_label(source_review_packet_path),
        certificate_id=str(certificate.get("certificate_id", "")),
        source_review_packet_id=str(metadata.get("source_review_packet_id", "")),
        disposition=str(certificate.get("disposition", "")),
        evidence_ref_count=len(evidence_refs) if isinstance(evidence_refs, list) else 0,
        errors=tuple(errors),
        next_action=_next_action(ready),
    )


def write_team_ops_shared_inbox_terminal_closure_certificate_validation(
    validation: TeamOpsSharedInboxTerminalClosureCertificateValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps terminal closure certificate validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_certificate_semantics(certificate: dict[str, Any], errors: list[str]) -> None:
    _validate_no_secret_markers(certificate, errors)
    _validate_no_raw_field_names(certificate, errors)
    if CERTIFICATE_ID_PATTERN.fullmatch(str(certificate.get("certificate_id", ""))) is None:
        errors.append("certificate_id must match TeamOps terminal closure certificate pattern")
    if certificate.get("command_id") != WORKFLOW_ID:
        errors.append("command_id must bind TeamOps shared inbox workflow")
    if REVIEW_PACKET_ID_PATTERN.fullmatch(str(certificate.get("execution_id", ""))) is None:
        errors.append("execution_id must bind TeamOps terminal closure review packet")
    if certificate.get("disposition") != "committed":
        errors.append("TeamOps terminal closure certificate disposition must be committed")
    if not str(certificate.get("response_closure_ref", "")).startswith("teamops-terminal-closure-review:"):
        errors.append("response_closure_ref must bind TeamOps terminal closure review ref")
    evidence_refs = certificate.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or len(evidence_refs) < 9:
        errors.append("TeamOps terminal closure certificate requires at least nine evidence refs")
    graph_refs = certificate.get("graph_refs", [])
    if not isinstance(graph_refs, list) or f"workflow:{WORKFLOW_ID}" not in graph_refs:
        errors.append("graph_refs must include TeamOps workflow ref")
    metadata = certificate.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
        return
    if metadata.get("source") != "team_ops_shared_inbox_terminal_closure_certificate":
        errors.append("metadata.source must identify TeamOps terminal closure certificate")
    for field_name in TRUE_METADATA_FIELDS:
        if metadata.get(field_name) is not True:
            errors.append(f"metadata.{field_name} must be true")
    for field_name in FALSE_METADATA_FIELDS:
        if metadata.get(field_name) is not False:
            errors.append(f"metadata.{field_name} must be false")
    if metadata.get("terminal_certificate_schema_id") != TERMINAL_CERTIFICATE_SCHEMA_ID:
        errors.append("metadata.terminal_certificate_schema_id must bind terminal closure schema")
    if SHA256_HEX_PATTERN.fullmatch(str(metadata.get("source_review_packet_hash", ""))) is None:
        errors.append("metadata.source_review_packet_hash must be sha256 hex")


def _validate_review_binding(
    certificate: dict[str, Any],
    review_packet: dict[str, Any],
    source_review_packet_path: Path,
    errors: list[str],
) -> None:
    review_validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=source_review_packet_path,
        require_ready=True,
    )
    if not review_validation.valid or not review_validation.ready:
        errors.append("source TeamOps terminal closure review packet must be ready")
    metadata = certificate.get("metadata", {}) if isinstance(certificate.get("metadata"), dict) else {}
    if metadata.get("source_review_packet_id") != review_packet.get("receipt_id"):
        errors.append("metadata.source_review_packet_id must match review packet receipt_id")
    if metadata.get("source_review_packet_ref") != review_packet.get("review_packet_ref"):
        errors.append("metadata.source_review_packet_ref must match review packet ref")
    if metadata.get("source_review_packet_hash") != review_packet.get("review_packet_hash"):
        errors.append("metadata.source_review_packet_hash must match review packet hash")
    if certificate.get("execution_id") != review_packet.get("receipt_id"):
        errors.append("execution_id must match review packet receipt_id")
    if certificate.get("verification_result_id") != review_packet.get("review_packet_ref"):
        errors.append("verification_result_id must match review packet ref")
    expected_reconciliation_id = f"teamops-effect-reconciliation:{str(review_packet.get('review_packet_hash', ''))[:16]}"
    if certificate.get("effect_reconciliation_id") != expected_reconciliation_id:
        errors.append("effect_reconciliation_id must derive from review packet hash")
    if certificate.get("response_closure_ref") != review_packet.get("review_packet_ref"):
        errors.append("response_closure_ref must match review packet ref")
    evidence_refs = certificate.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        errors.append("evidence_refs must be a list")
        return
    required_refs = tuple(str(ref) for ref in review_packet.get("required_terminal_evidence_refs", ()) if isinstance(ref, str))
    missing_refs = tuple(ref for ref in required_refs if ref not in evidence_refs)
    if missing_refs:
        errors.append("evidence_refs must include every required terminal review evidence ref")
    if review_packet.get("review_packet_ref") not in evidence_refs:
        errors.append("evidence_refs must include review packet ref")


def _certificate_ready(certificate: Mapping[str, Any]) -> bool:
    metadata = certificate.get("metadata", {}) if isinstance(certificate.get("metadata"), dict) else {}
    evidence_refs = certificate.get("evidence_refs", [])
    return (
        certificate.get("disposition") == "committed"
        and CERTIFICATE_ID_PATTERN.fullmatch(str(certificate.get("certificate_id", ""))) is not None
        and certificate.get("command_id") == WORKFLOW_ID
        and REVIEW_PACKET_ID_PATTERN.fullmatch(str(certificate.get("execution_id", ""))) is not None
        and str(certificate.get("response_closure_ref", "")).startswith("teamops-terminal-closure-review:")
        and isinstance(evidence_refs, list)
        and len(evidence_refs) >= 9
        and metadata.get("source") == "team_ops_shared_inbox_terminal_closure_certificate"
        and all(metadata.get(field_name) is True for field_name in TRUE_METADATA_FIELDS)
        and all(metadata.get(field_name) is False for field_name in FALSE_METADATA_FIELDS)
        and metadata.get("terminal_certificate_schema_id") == TERMINAL_CERTIFICATE_SCHEMA_ID
        and SHA256_HEX_PATTERN.fullmatch(str(metadata.get("source_review_packet_hash", ""))) is not None
    )


def _validate_no_secret_markers(payload: Mapping[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"certificate must not serialize secret marker: {marker}")


def _validate_no_raw_field_names(payload: Mapping[str, Any], errors: list[str]) -> None:
    for key in _iter_object_keys(payload):
        if key in RAW_FIELD_NAMES:
            errors.append(f"certificate must not serialize raw field: {key}")


def _iter_object_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_iter_object_keys(child))
        return tuple(keys)
    if isinstance(value, list):
        keys = []
        for child in value:
            keys.extend(_iter_object_keys(child))
        return tuple(keys)
    return ()


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
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


def _next_action(ready: bool) -> str:
    if ready:
        return "bind TeamOps terminal closure certificate into signed evidence bundle"
    return "regenerate TeamOps terminal closure certificate from ready review packet"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps terminal closure certificate validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps terminal closure certificate.")
    parser.add_argument("--certificate", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--source-review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure certificate validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=Path(args.certificate),
        source_review_packet_path=Path(args.source_review_packet),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_terminal_closure_certificate_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps terminal closure certificate valid ready={validation.ready}")
    else:
        print(f"TeamOps terminal closure certificate invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
