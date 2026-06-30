#!/usr/bin/env python3
"""Validate browser.submit approval rehearsal packets.

Purpose: reject malformed, raw-browser-data-bearing, effect-bearing, or
unready browser.submit approval rehearsal packets before live submit authority.
Governance scope: approval carry-forward, digest-only browser target evidence,
and external-effect denial.
Dependencies: browser_submit_approval_rehearsal_packet schema and
BrowserObservationReceipt schema.
Invariants:
  - The rehearsal packet never performs a form submit.
  - Raw URLs, selectors, form field names, form field values, session data, and
    secret values are not serialized.
  - A separate live submit execution receipt remains required.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "browser_submit_approval_rehearsal_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "browser_submit_approval_rehearsal_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "browser_submit_approval_rehearsal_packet_validation.json"
RECEIPT_ID_PATTERN = re.compile(r"^browser_submit_rehearsal_[0-9a-f]{16}$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(password|secret|token|api[_-]?key)\\s*[:=]\\s*['\\\"][^'\\\"]{6,}"),
)
RAW_FIELD_NAMES = {
    "raw_url",
    "url",
    "selector",
    "raw_selector",
    "form_payload",
    "raw_form_payload",
    "field_name",
    "raw_field_name",
    "field_value",
    "raw_field_value",
    "cookie",
    "session",
    "dom",
    "screenshot",
}
FALSE_EFFECT_FIELDS = (
    "form_submit_performed",
    "navigation_performed",
    "click_performed",
    "keystroke_injection_performed",
    "external_write_performed",
    "connector_mutation_performed",
    "system_of_record_write_performed",
    "raw_url_serialized",
    "raw_selector_serialized",
    "raw_form_payload_serialized",
    "raw_field_name_serialized",
    "raw_field_value_serialized",
    "cookie_or_session_read",
    "secret_value_serialized",
)
REQUIRED_EVIDENCE_REFS = (
    "schemas/browser_observation_receipt.schema.json",
    "examples/browser_observation_receipt.foundation.json",
)


@dataclass(frozen=True, slots=True)
class BrowserSubmitApprovalRehearsalValidation:
    """Validation result for one browser.submit approval rehearsal packet."""

    valid: bool
    ready: bool
    packet_path: str
    schema_path: str
    receipt_id: str
    status: str
    solver_outcome: str
    proof_state: str
    approval_decision_ready: bool
    decision: str
    browser_submit_ready: bool
    blocked_until: tuple[str, ...]
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""
        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["errors"] = list(self.errors)
        return payload


def validate_browser_submit_approval_rehearsal_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> BrowserSubmitApprovalRehearsalValidation:
    """Validate one browser.submit approval rehearsal packet."""
    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("browser submit approval rehearsal packet schema file missing")
    packet = _load_json_object(packet_path, "browser submit approval rehearsal packet", errors)
    if schema and packet:
        errors.extend(_validate_schema_instance(schema, packet))
        _validate_semantics(packet, errors)
        if require_ready and not _packet_ready(packet):
            errors.append("browser submit approval rehearsal packet ready must be true")
    ready = not errors and _packet_ready(packet)
    return BrowserSubmitApprovalRehearsalValidation(
        valid=not errors,
        ready=ready,
        packet_path=_path_label(packet_path),
        schema_path=_path_label(schema_path),
        receipt_id=str(packet.get("receipt_id", "")),
        status=str(packet.get("status", "")),
        solver_outcome=str(packet.get("solver_outcome", "")),
        proof_state=str(packet.get("proof_state", "")),
        approval_decision_ready=packet.get("approval_decision_ready") is True,
        decision=str(packet.get("decision", "")),
        browser_submit_ready=packet.get("browser_submit_ready") is True,
        blocked_until=tuple(str(item) for item in packet.get("blocked_until", ()))
        if isinstance(packet.get("blocked_until", ()), list)
        else (),
        errors=tuple(errors),
        next_action=_next_action(packet),
    )


def write_browser_submit_approval_rehearsal_validation(
    validation: BrowserSubmitApprovalRehearsalValidation,
    output_path: Path,
) -> Path:
    """Write one browser.submit approval rehearsal validation receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(packet: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(packet, sort_keys=True)
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(serialized):
            errors.append("packet must not serialize secret-like value")
            break
    for field_name in RAW_FIELD_NAMES:
        if field_name in packet:
            errors.append(f"packet must not serialize raw field: {field_name}")
    if not RECEIPT_ID_PATTERN.fullmatch(str(packet.get("receipt_id", ""))):
        errors.append("receipt_id must match browser submit rehearsal pattern")
    for field_name in FALSE_EFFECT_FIELDS:
        if packet.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    for field_name in ("source_url_hash", "target_selector_hash", "form_payload_hash"):
        if SHA256_HEX_PATTERN.fullmatch(str(packet.get(field_name, ""))) is None:
            errors.append(f"{field_name} must be sha256 hex")
    if packet.get("requires_separate_submit_execution_receipt") is not True:
        errors.append("requires_separate_submit_execution_receipt must be true")
    if packet.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")
    evidence_refs = packet.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("evidence_refs must be non-empty")
    else:
        for required_ref in REQUIRED_EVIDENCE_REFS:
            if required_ref not in evidence_refs:
                errors.append(f"evidence_refs missing required ref: {required_ref}")
    if packet.get("source_browser_observation_ref") != "examples/browser_observation_receipt.foundation.json":
        errors.append("source_browser_observation_ref must bind the Foundation browser observation receipt")
    if packet.get("status") == "passed":
        _validate_ready_packet(packet, errors)
    elif packet.get("status") == "blocked":
        _validate_blocked_packet(packet, errors)
    elif packet.get("status") == "failed":
        _validate_failed_packet(packet, errors)
    else:
        errors.append("status must be blocked, failed, or passed")


def _validate_ready_packet(packet: dict[str, Any], errors: list[str]) -> None:
    if packet.get("solver_outcome") != "SolvedVerified":
        errors.append("passed packet requires solver_outcome=SolvedVerified")
    if packet.get("proof_state") != "Pass":
        errors.append("passed packet requires proof_state=Pass")
    if packet.get("approval_decision_valid") is not True:
        errors.append("passed packet requires valid approval decision evidence")
    if packet.get("approval_decision_ready") is not True:
        errors.append("passed packet requires ready approval decision evidence")
    if packet.get("decision") != "approved":
        errors.append("passed packet requires approved decision")
    if packet.get("browser_submit_ready") is not True:
        errors.append("passed packet requires browser_submit_ready=true")
    if packet.get("browser_submit_authorized_by_decision") is not True:
        errors.append("passed packet requires browser_submit_authorized_by_decision=true")
    if packet.get("blocked_until") != []:
        errors.append("passed packet must not carry blockers")


def _validate_blocked_packet(packet: dict[str, Any], errors: list[str]) -> None:
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append("blocked packet requires solver_outcome=AwaitingEvidence")
    if packet.get("proof_state") != "Unknown":
        errors.append("blocked packet requires proof_state=Unknown")
    if packet.get("browser_submit_ready") is not False:
        errors.append("blocked packet must not be browser-submit ready")
    if not isinstance(packet.get("blocked_until"), list) or not packet.get("blocked_until"):
        errors.append("blocked packet must list blockers")


def _validate_failed_packet(packet: dict[str, Any], errors: list[str]) -> None:
    if packet.get("solver_outcome") != "GovernanceBlocked":
        errors.append("failed packet requires solver_outcome=GovernanceBlocked")
    if packet.get("proof_state") != "Fail":
        errors.append("failed packet requires proof_state=Fail")
    if packet.get("browser_submit_ready") is not False:
        errors.append("failed packet must not be browser-submit ready")
    if not isinstance(packet.get("blocked_until"), list) or not packet.get("blocked_until"):
        errors.append("failed packet must list blockers")


def _packet_ready(packet: dict[str, Any]) -> bool:
    return (
        packet.get("status") == "passed"
        and packet.get("solver_outcome") == "SolvedVerified"
        and packet.get("proof_state") == "Pass"
        and packet.get("approval_decision_valid") is True
        and packet.get("approval_decision_ready") is True
        and packet.get("decision") == "approved"
        and packet.get("browser_submit_ready") is True
        and packet.get("browser_submit_authorized_by_decision") is True
        and packet.get("requires_separate_submit_execution_receipt") is True
        and packet.get("no_secret_values_serialized") is True
        and packet.get("source_browser_observation_ref") == "examples/browser_observation_receipt.foundation.json"
        and all(packet.get(field_name) is False for field_name in FALSE_EFFECT_FIELDS)
        and all(SHA256_HEX_PATTERN.fullmatch(str(packet.get(field_name, ""))) is not None for field_name in (
            "source_url_hash",
            "target_selector_hash",
            "form_payload_hash",
        ))
        and isinstance(packet.get("evidence_refs"), list)
        and all(required_ref in packet.get("evidence_refs", []) for required_ref in REQUIRED_EVIDENCE_REFS)
        and packet.get("blocked_until") == []
    )


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


def _next_action(packet: dict[str, Any]) -> str:
    if _packet_ready(packet):
        return "execute separate browser-submit execution receipt only after final effect preflight"
    recovery_actions = packet.get("recovery_actions", [])
    if isinstance(recovery_actions, list) and recovery_actions:
        return str(recovery_actions[0])
    return "regenerate browser submit approval rehearsal packet"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse browser.submit approval rehearsal validation arguments."""
    parser = argparse.ArgumentParser(description="Validate browser.submit approval rehearsal packet.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for browser.submit approval rehearsal validation."""
    args = parse_args(argv)
    validation = validate_browser_submit_approval_rehearsal_packet(
        packet_path=Path(args.packet),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_browser_submit_approval_rehearsal_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"browser submit approval rehearsal packet valid ready={validation.ready}")
    else:
        print(f"browser submit approval rehearsal packet invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
