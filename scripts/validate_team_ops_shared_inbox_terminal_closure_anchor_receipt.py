#!/usr/bin/env python3
"""Validate TeamOps terminal closure anchor receipt wrappers.

Purpose: verify TeamOps anchor receipt wrappers remain schema-valid, bound to a
ready preflight and signed trust-ledger anchor receipt, and free of remote effects.
Governance scope: TeamOps anchor receipt validation, source-preflight binding,
trust-ledger anchor verification, no-secret serialization, and no-production claims.
Dependencies: schemas/team_ops_shared_inbox_terminal_closure_anchor_receipt.schema.json,
schemas/trust_ledger_anchor_receipt.schema.json, and gateway.trust_ledger.
Invariants:
  - Ready wrappers must bind a ready TeamOps anchor preflight and source bundle.
  - Ready wrappers must preserve provider-observation receipt identity and required artifact anchoring.
  - The embedded trust-ledger anchor receipt must verify with anchor secret.
  - Remote submits, provider calls, ledger appends, and production claims are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.trust_ledger import ExternalProofAnchorReceipt, TrustLedger, TrustLedgerEvidenceArtifact  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_receipt import (  # noqa: E402
    DEFAULT_OUTPUT,
    SCHEMA_PATH,
    TRUST_LEDGER_ANCHOR_RECEIPT_SCHEMA_PATH,
    _bundle_from_payload,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_preflight import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PREFLIGHT,
    REQUIRED_ARTIFACT_TYPES,
    _artifact_objects,
    _project_anchor_artifacts,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_BUNDLE,
    DEFAULT_REVIEW_PACKET,
)
from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CERTIFICATE,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_terminal_closure_anchor_preflight import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_anchor_preflight,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet import (  # noqa: E402
    PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN,
)


DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_anchor_receipt_validation.json"
)
FALSE_METADATA_FIELDS = (
    "remote_submit_executed",
    "ledger_append_executed",
    "provider_call_performed",
    "external_mailbox_write_performed",
    "external_message_sent",
    "raw_message_content_serialized",
    "raw_provider_payload_serialized",
    "production_ready_claimed",
)
TRUE_METADATA_FIELDS = (
    "preflight_ready_required",
    "anchor_receipt_created",
    "anchor_bundle_called",
    "no_secret_values_serialized",
    "requires_separate_remote_submission_preflight",
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
    "provider_payload",
    "provider_response",
    "raw_provider_response",
}


@dataclass(frozen=True, slots=True)
class TeamOpsTerminalClosureAnchorReceiptValidation:
    """Validation result for one TeamOps anchor receipt wrapper."""

    valid: bool
    ready: bool
    receipt_path: str
    preflight_path: str
    bundle_path: str
    receipt_id: str
    source_preflight_receipt_id: str
    anchor_receipt_id: str
    bundle_id: str
    command_id: str
    terminal_certificate_id: str
    provider_observation_receipt_id: str
    provider_observation_receipt_valid: bool
    artifact_count: int
    artifact_root_hash: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready validation receipt."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_terminal_closure_anchor_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    bundle_path: Path = DEFAULT_BUNDLE,
    certificate_path: Path = DEFAULT_CERTIFICATE,
    source_review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    bundle_signing_secret: str,
    anchor_signing_secret: str,
    require_ready: bool = False,
) -> TeamOpsTerminalClosureAnchorReceiptValidation:
    """Validate one TeamOps terminal closure anchor receipt wrapper."""

    errors: list[str] = []
    receipt = _load_json_object(receipt_path, "TeamOps terminal closure anchor receipt", errors)
    preflight = _load_json_object(preflight_path, "TeamOps terminal closure anchor preflight", errors)
    bundle = _load_json_object(bundle_path, "TeamOps terminal closure evidence bundle", errors)
    if receipt:
        errors.extend(_validate_schema_instance(_load_schema(SCHEMA_PATH), receipt))
        anchor_receipt_payload = receipt.get("anchor_receipt", {})
        if isinstance(anchor_receipt_payload, dict):
            errors.extend(_validate_schema_instance(_load_schema(TRUST_LEDGER_ANCHOR_RECEIPT_SCHEMA_PATH), anchor_receipt_payload))
        else:
            errors.append("anchor_receipt must be an object")
        _validate_receipt_semantics(receipt, errors)
    if bundle_signing_secret:
        preflight_validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
            preflight_path=preflight_path,
            bundle_path=bundle_path,
            certificate_path=certificate_path,
            source_review_packet_path=source_review_packet_path,
            bundle_signing_secret=bundle_signing_secret,
            require_ready=True,
        )
        if not preflight_validation.valid or not preflight_validation.ready:
            errors.append("source TeamOps terminal closure anchor preflight must be ready")
    else:
        errors.append("TeamOps evidence bundle signing secret is required")
    if receipt and preflight and bundle:
        _validate_source_binding(receipt, preflight, bundle, errors)
        _validate_anchor_signature(receipt, bundle, anchor_signing_secret, errors)
    ready = not errors and receipt.get("ready") is True
    if require_ready and not ready:
        errors.append("TeamOps terminal closure anchor receipt ready must be true")
        ready = False
    return TeamOpsTerminalClosureAnchorReceiptValidation(
        valid=not errors,
        ready=ready,
        receipt_path=_path_label(receipt_path),
        preflight_path=_path_label(preflight_path),
        bundle_path=_path_label(bundle_path),
        receipt_id=str(receipt.get("receipt_id", "")),
        source_preflight_receipt_id=str(receipt.get("source_preflight_receipt_id", "")),
        anchor_receipt_id=str(receipt.get("anchor_receipt_id", "")),
        bundle_id=str(receipt.get("bundle_id", "")),
        command_id=str(receipt.get("command_id", "")),
        terminal_certificate_id=str(receipt.get("terminal_certificate_id", "")),
        provider_observation_receipt_id=str(receipt.get("provider_observation_receipt_id", "")),
        provider_observation_receipt_valid=receipt.get("provider_observation_receipt_valid") is True,
        artifact_count=int(receipt.get("artifact_count", 0) or 0),
        artifact_root_hash=str(receipt.get("artifact_root_hash", "")),
        errors=tuple(dict.fromkeys(errors)),
        next_action=_next_action(ready),
    )


def write_team_ops_shared_inbox_terminal_closure_anchor_receipt_validation(
    validation: TeamOpsTerminalClosureAnchorReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps anchor receipt validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_receipt_semantics(receipt: dict[str, Any], errors: list[str]) -> None:
    _validate_no_secret_markers(receipt, errors)
    _validate_no_raw_field_names(receipt, errors)
    if receipt.get("external_anchor_status") != "pending":
        errors.append("external_anchor_status must remain pending")
    if receipt.get("external_anchor_ref") != "":
        errors.append("external_anchor_ref must remain empty before remote submission")
    if not str(receipt.get("provider_observation_receipt_ref", "")).strip():
        errors.append("provider_observation_receipt_ref must be non-empty")
    if PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN.fullmatch(
        str(receipt.get("provider_observation_receipt_id", ""))
    ) is None:
        errors.append("provider_observation_receipt_id must bind provider observation receipt")
    if receipt.get("provider_observation_receipt_valid") is not True:
        errors.append("provider_observation_receipt_valid must be true")
    required_types = set(receipt.get("required_artifact_types", []))
    if not set(REQUIRED_ARTIFACT_TYPES).issubset(required_types):
        errors.append("required_artifact_types must include trust-ledger anchor requirements")
    metadata = receipt.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
        return
    if metadata.get("source") != "team_ops_shared_inbox_terminal_closure_anchor_receipt":
        errors.append("metadata.source must identify TeamOps anchor receipt")
    for field_name in TRUE_METADATA_FIELDS:
        if metadata.get(field_name) is not True:
            errors.append(f"metadata.{field_name} must be true")
    for field_name in FALSE_METADATA_FIELDS:
        if metadata.get(field_name) is not False:
            errors.append(f"metadata.{field_name} must be false")


def _validate_source_binding(
    receipt: dict[str, Any],
    preflight: dict[str, Any],
    bundle: dict[str, Any],
    errors: list[str],
) -> None:
    if receipt.get("source_preflight_receipt_id") != preflight.get("receipt_id"):
        errors.append("source_preflight_receipt_id must match TeamOps anchor preflight")
    for field_name in ("bundle_id", "command_id", "terminal_certificate_id", "bundle_hash", "anchor_target"):
        if receipt.get(field_name) != preflight.get(field_name):
            errors.append(f"{field_name} must match TeamOps anchor preflight")
    for field_name in (
        "provider_observation_receipt_ref",
        "provider_observation_receipt_id",
        "provider_observation_receipt_valid",
    ):
        if receipt.get(field_name) != preflight.get(field_name):
            errors.append(f"{field_name} must match TeamOps anchor preflight")
    for field_name in ("bundle_id", "command_id", "terminal_certificate_id", "bundle_hash"):
        if receipt.get(field_name) != bundle.get(field_name):
            errors.append(f"{field_name} must match source TeamOps evidence bundle")
    metadata = bundle.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("source TeamOps evidence bundle metadata must be an object")
        return
    for field_name in (
        "provider_observation_receipt_ref",
        "provider_observation_receipt_id",
        "provider_observation_receipt_valid",
    ):
        if receipt.get(field_name) != metadata.get(field_name):
            errors.append(f"{field_name} must match source TeamOps evidence bundle metadata")
    expected_artifacts = list(_project_anchor_artifacts(bundle))
    if receipt.get("artifacts") != expected_artifacts:
        errors.append("artifacts must match deterministic source-bundle projection")
    if receipt.get("artifacts") != preflight.get("artifacts"):
        errors.append("artifacts must match TeamOps anchor preflight")
    anchor_receipt = receipt.get("anchor_receipt", {})
    if isinstance(anchor_receipt, dict):
        for field_name in ("anchor_receipt_id", "anchor_receipt_hash", "artifact_root_hash", "artifact_count"):
            if receipt.get(field_name) != anchor_receipt.get(field_name):
                errors.append(f"{field_name} must match embedded trust-ledger anchor receipt")


def _validate_anchor_signature(
    receipt: dict[str, Any],
    bundle: dict[str, Any],
    anchor_signing_secret: str,
    errors: list[str],
) -> None:
    if not anchor_signing_secret:
        errors.append("anchor signing secret is required")
        return
    try:
        bundle_object = _bundle_from_payload(bundle)
        anchor_receipt = _anchor_receipt_from_payload(receipt.get("anchor_receipt", {}))
        artifacts = _artifact_objects(tuple(receipt.get("artifacts", ())))
        verification = TrustLedger().verify_anchor_receipt(
            anchor_receipt,
            bundle=bundle_object,
            artifacts=artifacts,
            signing_secret=anchor_signing_secret,
        )
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"trust-ledger anchor receipt verification failed: {exc}")
        return
    if not verification.verified:
        errors.append(f"trust-ledger anchor receipt must verify: {verification.reason}")


def _anchor_receipt_from_payload(payload: Mapping[str, Any]) -> ExternalProofAnchorReceipt:
    return ExternalProofAnchorReceipt(
        anchor_receipt_id=str(payload["anchor_receipt_id"]),
        bundle_id=str(payload["bundle_id"]),
        tenant_id=str(payload["tenant_id"]),
        command_id=str(payload["command_id"]),
        terminal_certificate_id=str(payload["terminal_certificate_id"]),
        anchor_target=str(payload["anchor_target"]),
        external_anchor_ref=str(payload["external_anchor_ref"]),
        external_anchor_status=str(payload["external_anchor_status"]),
        bundle_hash=str(payload["bundle_hash"]),
        artifact_root_hash=str(payload["artifact_root_hash"]),
        hash_chain_root=str(payload["hash_chain_root"]),
        artifact_count=int(payload["artifact_count"]),
        required_artifact_types=[str(item) for item in payload["required_artifact_types"]],
        anchored_at=str(payload["anchored_at"]),
        signature_key_id=str(payload["signature_key_id"]),
        signature=str(payload["signature"]),
        anchor_receipt_hash=str(payload["anchor_receipt_hash"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _validate_no_secret_markers(payload: Mapping[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"anchor receipt must not serialize secret marker: {marker}")


def _validate_no_raw_field_names(payload: Mapping[str, Any], errors: list[str]) -> None:
    for key in _iter_object_keys(payload):
        if key in RAW_FIELD_NAMES:
            errors.append(f"anchor receipt must not serialize raw field: {key}")


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


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _next_action(ready: bool) -> str:
    if ready:
        return "operator may run a separate remote submission preflight before any external anchor submit"
    return "repair TeamOps anchor receipt blockers before remote submission preflight"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps anchor receipt validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps terminal closure anchor receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--certificate", default=str(DEFAULT_CERTIFICATE))
    parser.add_argument("--source-review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--bundle-signing-secret", required=True)
    parser.add_argument("--anchor-signing-secret", required=True)
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps anchor receipt validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        receipt_path=Path(args.receipt),
        preflight_path=Path(args.preflight),
        bundle_path=Path(args.bundle),
        certificate_path=Path(args.certificate),
        source_review_packet_path=Path(args.source_review_packet),
        bundle_signing_secret=args.bundle_signing_secret,
        anchor_signing_secret=args.anchor_signing_secret,
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_terminal_closure_anchor_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps terminal closure anchor receipt valid ready={validation.ready}")
    else:
        print(f"TeamOps terminal closure anchor receipt invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
