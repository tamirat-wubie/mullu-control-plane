#!/usr/bin/env python3
"""Validate TeamOps shared inbox terminal closure evidence bundles.

Purpose: verify signed TeamOps trust-ledger bundles against the source terminal
closure certificate, schema contract, HMAC signature, and no-effect metadata.
Governance scope: TeamOps trust-ledger bundle verification, source-certificate
binding, evidence-ref proof scheme, redaction, and no-production-claim checks.
Dependencies: scripts.verify_evidence_bundle and
scripts.validate_team_ops_shared_inbox_terminal_closure_certificate.
Invariants:
  - A bundle must pass trust-ledger schema, hash, and signature verification.
  - A bundle must bind the ready TeamOps terminal closure certificate.
  - Provider-observation receipt identity must match the source certificate.
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
    DEFAULT_OUTPUT as DEFAULT_CERTIFICATE,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_REVIEW_PACKET,
    SCHEMA_ID,
    WORKFLOW_ID,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_certificate,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet import (  # noqa: E402
    PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN,
)
from scripts.verify_evidence_bundle import BUNDLE_SCHEMA_PATH, verify_bundle_file  # noqa: E402


DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_evidence_bundle_validation.json"
)
BUNDLE_ID_PATTERN = re.compile(r"^trust-bundle-[0-9a-f]{16}$")
FALSE_METADATA_FIELDS = (
    "external_anchor_requested_by_producer",
    "external_message_sent_by_producer",
    "external_mailbox_write_performed_by_producer",
    "provider_mutation_performed_by_producer",
    "provider_call_performed_by_producer",
    "raw_message_content_serialized",
    "raw_provider_payload_serialized",
    "production_ready_claimed",
)
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
    "provider_payload",
}


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxTerminalClosureEvidenceBundleValidation:
    """Validation result for one TeamOps terminal closure evidence bundle."""

    valid: bool
    ready: bool
    bundle_path: str
    certificate_path: str
    source_review_packet_path: str
    bundle_id: str
    command_id: str
    terminal_certificate_id: str
    provider_observation_receipt_id: str
    provider_observation_receipt_valid: bool
    evidence_ref_count: int
    signature_key_id: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
    *,
    bundle_path: Path = DEFAULT_OUTPUT,
    certificate_path: Path = DEFAULT_CERTIFICATE,
    source_review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    signing_secret: str,
    require_ready: bool = False,
) -> TeamOpsSharedInboxTerminalClosureEvidenceBundleValidation:
    """Validate one signed TeamOps terminal closure evidence bundle."""

    errors: list[str] = []
    bundle = _load_json_object(bundle_path, "TeamOps terminal closure evidence bundle", errors)
    certificate = _load_json_object(certificate_path, "TeamOps terminal closure certificate", errors)
    if signing_secret:
        trust_report = verify_bundle_file(bundle_path=bundle_path, signing_secret=signing_secret, strict=True)
        if trust_report.get("valid") is not True:
            errors.append(f"trust ledger verification failed: {trust_report.get('reason', 'unknown')}")
        errors.extend(str(error) for error in trust_report.get("schema_errors", ()))
    else:
        errors.append("TeamOps terminal closure evidence bundle signing secret is required")
    if bundle:
        _validate_bundle_semantics(bundle, errors)
    if certificate:
        certificate_validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
            certificate_path=certificate_path,
            source_review_packet_path=source_review_packet_path,
            require_ready=True,
        )
        if not certificate_validation.valid or not certificate_validation.ready:
            errors.append("source TeamOps terminal closure certificate must be ready")
    if bundle and certificate:
        _validate_certificate_binding(bundle, certificate, errors)
    ready = not errors and _bundle_ready(bundle)
    if require_ready and not ready:
        errors.append("TeamOps terminal closure evidence bundle ready must be true")
        ready = False
    evidence_refs = bundle.get("evidence_refs", [])
    metadata = bundle.get("metadata", {}) if isinstance(bundle.get("metadata"), dict) else {}
    return TeamOpsSharedInboxTerminalClosureEvidenceBundleValidation(
        valid=not errors,
        ready=ready,
        bundle_path=_path_label(bundle_path),
        certificate_path=_path_label(certificate_path),
        source_review_packet_path=_path_label(source_review_packet_path),
        bundle_id=str(bundle.get("bundle_id", "")),
        command_id=str(bundle.get("command_id", "")),
        terminal_certificate_id=str(bundle.get("terminal_certificate_id", "")),
        provider_observation_receipt_id=str(metadata.get("provider_observation_receipt_id", "")),
        provider_observation_receipt_valid=metadata.get("provider_observation_receipt_valid") is True,
        evidence_ref_count=len(evidence_refs) if isinstance(evidence_refs, list) else 0,
        signature_key_id=str(bundle.get("signature_key_id", "")),
        errors=tuple(dict.fromkeys(errors)),
        next_action=_next_action(ready),
    )


def write_team_ops_shared_inbox_terminal_closure_evidence_bundle_validation(
    validation: TeamOpsSharedInboxTerminalClosureEvidenceBundleValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps evidence bundle validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_bundle_semantics(bundle: dict[str, Any], errors: list[str]) -> None:
    _validate_no_secret_markers(bundle, errors)
    _validate_no_raw_field_names(bundle, errors)
    if BUNDLE_ID_PATTERN.fullmatch(str(bundle.get("bundle_id", ""))) is None:
        errors.append("bundle_id must match trust bundle pattern")
    if bundle.get("command_id") != WORKFLOW_ID:
        errors.append("command_id must bind TeamOps shared inbox workflow")
    if bundle.get("external_anchor_status") != "not_requested":
        errors.append("external_anchor_status must be not_requested")
    if bundle.get("external_anchor_ref") != "":
        errors.append("external_anchor_ref must be empty before external anchoring")
    evidence_refs = bundle.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or len(evidence_refs) < 9:
        errors.append("TeamOps evidence bundle requires at least nine proof refs")
    elif any(not str(ref).startswith("proof://") for ref in evidence_refs):
        errors.append("all evidence refs must use proof:// scheme")
    metadata = bundle.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
        return
    if metadata.get("source") != "team_ops_shared_inbox_terminal_closure_evidence_bundle":
        errors.append("metadata.source must identify TeamOps terminal closure evidence bundle")
    if metadata.get("team_ops_terminal_closure_bundle") is not True:
        errors.append("metadata.team_ops_terminal_closure_bundle must be true")
    if metadata.get("bundle_schema_id") != SCHEMA_ID:
        errors.append("metadata.bundle_schema_id must bind trust-ledger bundle schema")
    if metadata.get("no_secret_values_serialized") is not True:
        errors.append("metadata.no_secret_values_serialized must be true")
    provider_receipt_id = str(metadata.get("provider_observation_receipt_id", ""))
    if PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN.fullmatch(provider_receipt_id) is None:
        errors.append("metadata.provider_observation_receipt_id must bind provider observation receipt")
    if not str(metadata.get("provider_observation_receipt_ref", "")).strip():
        errors.append("metadata.provider_observation_receipt_ref must be non-empty")
    if metadata.get("provider_observation_receipt_valid") is not True:
        errors.append("metadata.provider_observation_receipt_valid must be true")
    for field_name in FALSE_METADATA_FIELDS:
        if metadata.get(field_name) is not False:
            errors.append(f"metadata.{field_name} must be false")


def _validate_certificate_binding(
    bundle: dict[str, Any],
    certificate: dict[str, Any],
    errors: list[str],
) -> None:
    metadata = bundle.get("metadata", {}) if isinstance(bundle.get("metadata"), dict) else {}
    certificate_metadata = certificate.get("metadata", {}) if isinstance(certificate.get("metadata"), dict) else {}
    if bundle.get("terminal_certificate_id") != certificate.get("certificate_id"):
        errors.append("terminal_certificate_id must match source certificate id")
    if bundle.get("hash_chain_root") != metadata.get("source_certificate_hash"):
        errors.append("hash_chain_root must match metadata.source_certificate_hash")
    if metadata.get("source_review_packet_id") != certificate_metadata.get("source_review_packet_id"):
        errors.append("metadata.source_review_packet_id must match certificate metadata")
    if metadata.get("source_review_packet_hash") != certificate_metadata.get("source_review_packet_hash"):
        errors.append("metadata.source_review_packet_hash must match certificate metadata")
    if metadata.get("provider_observation_receipt_ref") != certificate_metadata.get("provider_observation_receipt_ref"):
        errors.append("metadata.provider_observation_receipt_ref must match certificate metadata")
    if metadata.get("provider_observation_receipt_id") != certificate_metadata.get("provider_observation_receipt_id"):
        errors.append("metadata.provider_observation_receipt_id must match certificate metadata")
    if metadata.get("provider_observation_receipt_valid") is not True:
        errors.append("metadata.provider_observation_receipt_valid must be true")
    evidence_refs = bundle.get("evidence_refs", [])
    if isinstance(evidence_refs, list):
        required_refs = (
            f"proof://teamops/command/{WORKFLOW_ID}",
            f"proof://teamops/terminal-certificate/{certificate.get('certificate_id', '')}",
            f"proof://teamops/terminal-review/{certificate_metadata.get('source_review_packet_id', '')}",
            f"proof://teamops/provider-observation/{certificate_metadata.get('provider_observation_receipt_id', '')}",
        )
        for ref in required_refs:
            if ref not in evidence_refs:
                errors.append(f"evidence_refs must include {ref}")


def _bundle_ready(bundle: Mapping[str, Any]) -> bool:
    metadata = bundle.get("metadata", {}) if isinstance(bundle.get("metadata"), dict) else {}
    evidence_refs = bundle.get("evidence_refs", [])
    return (
        BUNDLE_ID_PATTERN.fullmatch(str(bundle.get("bundle_id", ""))) is not None
        and bundle.get("command_id") == WORKFLOW_ID
        and bool(str(bundle.get("terminal_certificate_id", "")).strip())
        and bundle.get("external_anchor_status") == "not_requested"
        and bundle.get("external_anchor_ref") == ""
        and isinstance(evidence_refs, list)
        and len(evidence_refs) >= 9
        and all(str(ref).startswith("proof://") for ref in evidence_refs)
        and metadata.get("source") == "team_ops_shared_inbox_terminal_closure_evidence_bundle"
        and metadata.get("team_ops_terminal_closure_bundle") is True
        and metadata.get("bundle_schema_id") == SCHEMA_ID
        and metadata.get("no_secret_values_serialized") is True
        and (
            PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN.fullmatch(
                str(metadata.get("provider_observation_receipt_id", ""))
            )
            is not None
        )
        and bool(str(metadata.get("provider_observation_receipt_ref", "")).strip())
        and metadata.get("provider_observation_receipt_valid") is True
        and all(metadata.get(field_name) is False for field_name in FALSE_METADATA_FIELDS)
    )


def _validate_no_secret_markers(payload: Mapping[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"bundle must not serialize secret marker: {marker}")


def _validate_no_raw_field_names(payload: Mapping[str, Any], errors: list[str]) -> None:
    for key in _iter_object_keys(payload):
        if key in RAW_FIELD_NAMES:
            errors.append(f"bundle must not serialize raw field: {key}")


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
        return "prepare TeamOps terminal closure evidence bundle for external anchor preflight"
    return "regenerate TeamOps terminal closure evidence bundle from ready certificate"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps evidence bundle validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps terminal closure evidence bundle.")
    parser.add_argument("--bundle", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--certificate", default=str(DEFAULT_CERTIFICATE))
    parser.add_argument("--source-review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--signing-secret", required=True)
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure evidence bundle validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=Path(args.bundle),
        certificate_path=Path(args.certificate),
        source_review_packet_path=Path(args.source_review_packet),
        signing_secret=args.signing_secret,
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps terminal closure evidence bundle valid ready={validation.ready}")
    else:
        print(f"TeamOps terminal closure evidence bundle invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
