#!/usr/bin/env python3
"""Validate TeamOps terminal closure anchor preflight receipts.

Purpose: verify TeamOps anchor preflight receipts remain schema-valid, bound to
the signed terminal closure evidence bundle, and no-effect.
Governance scope: TeamOps anchor preflight validation, trust-ledger artifact
projection, no-secret serialization, and no-production-claim enforcement.
Dependencies: schemas/team_ops_shared_inbox_terminal_closure_anchor_preflight.schema.json
and scripts.validate_team_ops_shared_inbox_terminal_closure_evidence_bundle.
Invariants:
  - Ready receipts must bind a ready TeamOps terminal closure evidence bundle.
  - Ready receipts must preserve provider-observation receipt identity and artifact anchoring.
  - Anchor receipts, remote submits, and ledger appends must remain false.
  - Secret markers and raw provider/message fields are rejected.
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

from gateway.trust_ledger import _artifact_root_hash  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_preflight import (  # noqa: E402
    DEFAULT_OUTPUT,
    REQUIRED_ARTIFACT_TYPES,
    SCHEMA_PATH,
    _artifact_objects,
    _project_anchor_artifacts,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_BUNDLE,
    DEFAULT_REVIEW_PACKET,
    WORKFLOW_ID,
)
from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CERTIFICATE,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_terminal_closure_evidence_bundle import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_evidence_bundle,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet import (  # noqa: E402
    PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN,
)


DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_anchor_preflight_validation.json"
)
FALSE_METADATA_FIELDS = (
    "anchor_receipt_created",
    "anchor_bundle_called",
    "remote_submit_executed",
    "ledger_append_executed",
    "provider_call_performed",
    "external_mailbox_write_performed",
    "external_message_sent",
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
    "provider_payload",
    "provider_response",
    "raw_provider_response",
}


@dataclass(frozen=True, slots=True)
class TeamOpsTerminalClosureAnchorPreflightValidation:
    """Validation result for one TeamOps anchor preflight receipt."""

    valid: bool
    ready: bool
    preflight_path: str
    bundle_path: str
    receipt_id: str
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


def validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
    *,
    preflight_path: Path = DEFAULT_OUTPUT,
    bundle_path: Path = DEFAULT_BUNDLE,
    certificate_path: Path = DEFAULT_CERTIFICATE,
    source_review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    bundle_signing_secret: str,
    require_ready: bool = False,
) -> TeamOpsTerminalClosureAnchorPreflightValidation:
    """Validate one TeamOps terminal closure anchor preflight receipt."""

    errors: list[str] = []
    preflight = _load_json_object(preflight_path, "TeamOps terminal closure anchor preflight", errors)
    bundle = _load_json_object(bundle_path, "TeamOps terminal closure evidence bundle", errors)
    if preflight:
        errors.extend(_validate_schema_instance(_load_schema(SCHEMA_PATH), preflight))
        _validate_preflight_semantics(preflight, errors)
    if bundle_signing_secret:
        bundle_validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
            bundle_path=bundle_path,
            certificate_path=certificate_path,
            source_review_packet_path=source_review_packet_path,
            signing_secret=bundle_signing_secret,
            require_ready=True,
        )
        if not bundle_validation.valid or not bundle_validation.ready:
            errors.append("source TeamOps terminal closure evidence bundle must be ready")
    else:
        errors.append("TeamOps evidence bundle signing secret is required")
    if preflight and bundle:
        _validate_bundle_binding(preflight, bundle, errors)
    ready = not errors and preflight.get("ready") is True
    if require_ready and not ready:
        errors.append("TeamOps terminal closure anchor preflight ready must be true")
        ready = False
    return TeamOpsTerminalClosureAnchorPreflightValidation(
        valid=not errors,
        ready=ready,
        preflight_path=_path_label(preflight_path),
        bundle_path=_path_label(bundle_path),
        receipt_id=str(preflight.get("receipt_id", "")),
        bundle_id=str(preflight.get("bundle_id", "")),
        command_id=str(preflight.get("command_id", "")),
        terminal_certificate_id=str(preflight.get("terminal_certificate_id", "")),
        provider_observation_receipt_id=str(preflight.get("provider_observation_receipt_id", "")),
        provider_observation_receipt_valid=preflight.get("provider_observation_receipt_valid") is True,
        artifact_count=int(preflight.get("artifact_count", 0) or 0),
        artifact_root_hash=str(preflight.get("artifact_root_hash", "")),
        errors=tuple(dict.fromkeys(errors)),
        next_action=_next_action(ready),
    )


def write_team_ops_shared_inbox_terminal_closure_anchor_preflight_validation(
    validation: TeamOpsTerminalClosureAnchorPreflightValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps anchor preflight validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_preflight_semantics(preflight: dict[str, Any], errors: list[str]) -> None:
    _validate_no_secret_markers(preflight, errors)
    _validate_no_raw_field_names(preflight, errors)
    if preflight.get("command_id") != WORKFLOW_ID:
        errors.append("command_id must bind TeamOps shared inbox workflow")
    if preflight.get("planned_external_anchor_status") != "pending":
        errors.append("planned_external_anchor_status must be pending")
    if preflight.get("planned_external_anchor_ref") != "":
        errors.append("planned_external_anchor_ref must be empty before anchor creation")
    if not str(preflight.get("provider_observation_receipt_ref", "")).strip():
        errors.append("provider_observation_receipt_ref must be non-empty")
    if PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN.fullmatch(
        str(preflight.get("provider_observation_receipt_id", ""))
    ) is None:
        errors.append("provider_observation_receipt_id must bind provider observation receipt")
    if preflight.get("provider_observation_receipt_valid") is not True:
        errors.append("provider_observation_receipt_valid must be true")
    required_types = set(preflight.get("required_artifact_types", []))
    if not set(REQUIRED_ARTIFACT_TYPES).issubset(required_types):
        errors.append("required_artifact_types must include trust-ledger anchor requirements")
    artifacts = preflight.get("artifacts", [])
    if not isinstance(artifacts, list) or len(artifacts) < 4:
        errors.append("artifacts must contain projected trust-ledger anchor artifacts")
    else:
        try:
            observed_root = _artifact_root_hash(_artifact_objects(tuple(artifacts)))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"artifact projection invalid: {exc}")
        else:
            if observed_root != preflight.get("artifact_root_hash"):
                errors.append("artifact_root_hash must match projected artifacts")
    metadata = preflight.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
        return
    if metadata.get("source") != "team_ops_shared_inbox_terminal_closure_anchor_preflight":
        errors.append("metadata.source must identify TeamOps anchor preflight")
    if metadata.get("preflight_only") is not True:
        errors.append("metadata.preflight_only must be true")
    if metadata.get("no_secret_values_serialized") is not True:
        errors.append("metadata.no_secret_values_serialized must be true")
    if metadata.get("requires_operator_confirmation_for_anchor") is not True:
        errors.append("metadata.requires_operator_confirmation_for_anchor must be true")
    for field_name in FALSE_METADATA_FIELDS:
        if metadata.get(field_name) is not False:
            errors.append(f"metadata.{field_name} must be false")


def _validate_bundle_binding(
    preflight: dict[str, Any],
    bundle: dict[str, Any],
    errors: list[str],
) -> None:
    for field_name in ("bundle_id", "command_id", "terminal_certificate_id", "bundle_hash"):
        if preflight.get(field_name) != bundle.get(field_name):
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
        if preflight.get(field_name) != metadata.get(field_name):
            errors.append(f"{field_name} must match source TeamOps evidence bundle metadata")
    expected_artifacts = list(_project_anchor_artifacts(bundle))
    if preflight.get("artifacts") != expected_artifacts:
        errors.append("artifacts must match deterministic source-bundle projection")


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
            errors.append(f"anchor preflight must not serialize secret marker: {marker}")


def _validate_no_raw_field_names(payload: Mapping[str, Any], errors: list[str]) -> None:
    for key in _iter_object_keys(payload):
        if key in RAW_FIELD_NAMES:
            errors.append(f"anchor preflight must not serialize raw field: {key}")


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
        return "operator may create a pending trust-ledger anchor receipt in a separate governed step"
    return "repair TeamOps anchor preflight blockers before anchor receipt creation"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps anchor preflight validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps terminal closure anchor preflight.")
    parser.add_argument("--preflight", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--certificate", default=str(DEFAULT_CERTIFICATE))
    parser.add_argument("--source-review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--bundle-signing-secret", required=True)
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps anchor preflight validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        preflight_path=Path(args.preflight),
        bundle_path=Path(args.bundle),
        certificate_path=Path(args.certificate),
        source_review_packet_path=Path(args.source_review_packet),
        bundle_signing_secret=args.bundle_signing_secret,
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_terminal_closure_anchor_preflight_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps terminal closure anchor preflight valid ready={validation.ready}")
    else:
        print(f"TeamOps terminal closure anchor preflight invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
