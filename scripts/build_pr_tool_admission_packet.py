#!/usr/bin/env python3
"""Build a projection-only PR tool admission packet.

Purpose: decide whether a local PR candidate may enter local PR-tool
preparation without pushing a branch or opening an external pull request.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local PR candidate packet and local schema validation.
Invariants:
  - Local tool admission requires a ready local PR candidate.
  - External effects, PR creation, and branch push remain false.
  - External PR execution still requires a separate approval witness.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_CANDIDATE_PACKET = REPO_ROOT / "examples" / "local_pr_candidate_packet.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "pr_tool_admission_packet.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_tool_admission_packet.generated.json"
LOCAL_ACTIONS = ("render_pr_body", "assemble_pr_metadata", "prepare_pr_command_preview")
FORBIDDEN_EFFECTS = (
    "open_external_pr",
    "push_branch",
    "merge",
    "deploy",
    "call_connector",
)


@dataclass(frozen=True, slots=True)
class PrToolAdmissionPacketValidation:
    """Validation report for a PR tool admission packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_path: str
    admission_status: str
    local_pr_tool_admitted: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_pr_tool_admission_packet(
    *,
    candidate_packet: Mapping[str, Any],
    candidate_packet_path: Path,
) -> dict[str, Any]:
    """Return a local PR-tool admission packet without external authority."""

    candidate_ready = candidate_packet.get("candidate_ready") is True
    admission_status = "local_tool_admitted" if candidate_ready else "blocked_candidate_incomplete"
    rollback = candidate_packet.get("rollback", {})
    if not isinstance(rollback, Mapping):
        rollback = {}
    packet = {
        "packet_id": "pr_tool_admission_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _text_or_default(
            candidate_packet.get("workflow_run_id"),
            "developer_workflow_v1_foundation_run",
        ),
        "admission_status": admission_status,
        "local_pr_tool_admitted": candidate_ready,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "candidate": {
            "candidate_status": str(candidate_packet.get("candidate_status") or "blocked"),
            "candidate_ready": candidate_ready,
            "candidate_packet_hash": str(candidate_packet.get("packet_hash") or ""),
            "title": str(candidate_packet.get("title") or ""),
            "branch_name": str(candidate_packet.get("branch_name") or ""),
            "diff_refs": [str(item) for item in candidate_packet.get("diff_refs", ())],
            "test_refs": [str(item) for item in candidate_packet.get("test_refs", ())],
            "rollback_evidence_refs": [str(item) for item in rollback.get("evidence_refs", ())],
        },
        "local_tool_actions_allowed": list(LOCAL_ACTIONS) if candidate_ready else [],
        "external_approval_required_before_execution": True,
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
        "source_refs": {
            "candidate_packet_path": _path_label(candidate_packet_path),
            "candidate_packet_schema": "schemas/local_pr_candidate_packet.schema.json",
            "admission_builder": "python scripts/build_pr_tool_admission_packet.py",
        },
        "packet_hash": "",
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def validate_pr_tool_admission_packet(
    *,
    packet: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = Path("<generated>"),
) -> PrToolAdmissionPacketValidation:
    """Validate schema and local-only PR tool admission semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(packet)))
    _validate_packet_semantics(packet, errors)
    return PrToolAdmissionPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_path=_path_label(packet_path),
        admission_status=str(packet.get("admission_status") or ""),
        local_pr_tool_admitted=packet.get("local_pr_tool_admitted") is True,
    )


def write_pr_tool_admission_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic local PR-tool admission packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str]) -> None:
    if packet.get("external_effects_allowed") is not False:
        errors.append("external_effects_allowed_must_be_false")
    if packet.get("pr_creation_allowed") is not False:
        errors.append("pr_creation_allowed_must_be_false")
    if packet.get("branch_push_allowed") is not False:
        errors.append("branch_push_allowed_must_be_false")
    if packet.get("external_approval_required_before_execution") is not True:
        errors.append("external_approval_required_before_execution_must_be_true")
    effects = tuple(str(effect) for effect in packet.get("forbidden_effects", ()) if str(effect).strip())
    for expected_effect in FORBIDDEN_EFFECTS:
        if expected_effect not in effects:
            errors.append(f"missing_forbidden_effect:{expected_effect}")
    candidate = packet.get("candidate", {})
    if not isinstance(candidate, Mapping):
        errors.append("candidate_must_be_object")
        return
    candidate_ready = candidate.get("candidate_ready") is True
    should_admit = candidate_ready and candidate.get("candidate_status") == "ready_for_pr_tool"
    if packet.get("local_pr_tool_admitted") is not should_admit:
        errors.append("local_pr_tool_admitted_mismatch")
    expected_status = "local_tool_admitted" if should_admit else "blocked_candidate_incomplete"
    if packet.get("admission_status") != expected_status:
        errors.append(f"admission_status_must_be:{expected_status}")
    expected_actions = tuple(LOCAL_ACTIONS) if should_admit else ()
    if tuple(packet.get("local_tool_actions_allowed", ())) != expected_actions:
        errors.append("local_tool_actions_allowed_mismatch")
    if packet.get("packet_hash") != canonical_hash({**dict(packet), "packet_hash": ""}):
        errors.append("packet_hash_mismatch")


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _text_or_default(value: object, default: str) -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse PR tool admission packet builder arguments."""

    parser = argparse.ArgumentParser(description="Build local PR tool admission packet.")
    parser.add_argument("--candidate-packet", default=str(DEFAULT_CANDIDATE_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for PR tool admission packet building."""

    args = parse_args(argv)
    try:
        candidate_packet_path = Path(args.candidate_packet)
        candidate_packet = _load_json_object(candidate_packet_path)
        packet = build_pr_tool_admission_packet(
            candidate_packet=candidate_packet,
            candidate_packet_path=candidate_packet_path,
        )
        output_path = write_pr_tool_admission_packet(packet, Path(args.output))
        validation = validate_pr_tool_admission_packet(
            packet=packet,
            schema_path=Path(args.schema),
            packet_path=output_path,
        )
    except ValueError as exc:
        print(f"PR TOOL ADMISSION PACKET INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"PR TOOL ADMISSION PACKET INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"PR TOOL ADMISSION PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
