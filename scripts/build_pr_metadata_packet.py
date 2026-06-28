#!/usr/bin/env python3
"""Build a projection-only PR metadata packet.

Purpose: render governed PR title, body sections, labels, and branch metadata
from a local PR candidate without opening an external pull request.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local PR candidate packet, optional PR command preview packet,
and local schema validation.
Invariants:
  - Metadata generation is preview-only and non-executing.
  - Candidate readiness controls metadata readiness.
  - External effects, PR creation, and branch push remain false.
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
DEFAULT_COMMAND_PREVIEW_PACKET = REPO_ROOT / "examples" / "pr_command_preview_packet.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "pr_metadata_packet.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_metadata_packet.generated.json"
GOVERNANCE_SCOPE = ("OCE", "RAG", "CDCV", "CQTE", "UWMA", "SRCA", "PRS")
DEFAULT_LABELS = ("governance", "developer-workflow", "local-lab")


@dataclass(frozen=True, slots=True)
class PrMetadataPacketValidation:
    """Validation report for a PR metadata packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_path: str
    metadata_status: str
    title: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_pr_metadata_packet(
    *,
    candidate_packet: Mapping[str, Any],
    candidate_packet_path: Path,
    command_preview_packet: Mapping[str, Any] | None = None,
    command_preview_packet_path: Path | None = None,
    target_branch: str = "main",
) -> dict[str, Any]:
    """Return a projection-only PR metadata packet."""

    candidate_ready = candidate_packet.get("candidate_ready") is True
    metadata_status = "ready_for_preview" if candidate_ready else "blocked_candidate_incomplete"
    rollback = candidate_packet.get("rollback", {})
    if not isinstance(rollback, Mapping):
        rollback = {}
    command_preview = _command_preview_summary(command_preview_packet)
    source_refs = {
        "candidate_packet_path": _path_label(candidate_packet_path),
        "candidate_packet_schema": "schemas/local_pr_candidate_packet.schema.json",
        "metadata_builder": "python scripts/build_pr_metadata_packet.py",
    }
    if command_preview_packet_path is not None:
        source_refs["command_preview_packet_path"] = _path_label(command_preview_packet_path)
        source_refs["command_preview_packet_schema"] = "schemas/pr_command_preview_packet.schema.json"
    packet = {
        "packet_id": "pr_metadata_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _text_or_default(
            candidate_packet.get("workflow_run_id"),
            "developer_workflow_v1_foundation_run",
        ),
        "metadata_status": metadata_status,
        "preview_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "title": _required_text(candidate_packet.get("title"), "title"),
        "body": {
            "summary": _required_text(candidate_packet.get("summary"), "summary"),
            "governance_scope": list(GOVERNANCE_SCOPE),
            "testing": _testing_entries(candidate_packet, command_preview_packet),
            "rollback": _rollback_entries(rollback),
        },
        "labels": list(DEFAULT_LABELS),
        "source_branch": _required_text(candidate_packet.get("branch_name"), "branch_name"),
        "target_branch": target_branch,
        "command_preview": command_preview,
        "rollback": {
            "required": True,
            "evidence_refs": [str(item) for item in rollback.get("evidence_refs", ())],
            "notes": str(rollback.get("command") or "Use governed rollback evidence before discarding metadata."),
        },
        "source_refs": source_refs,
        "packet_hash": "",
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def validate_pr_metadata_packet(
    *,
    packet: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = Path("<generated>"),
) -> PrMetadataPacketValidation:
    """Validate schema and preview-only PR metadata semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(packet)))
    _validate_packet_semantics(packet, errors)
    return PrMetadataPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_path=_path_label(packet_path),
        metadata_status=str(packet.get("metadata_status") or ""),
        title=str(packet.get("title") or ""),
    )


def write_pr_metadata_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic PR metadata packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str]) -> None:
    if packet.get("preview_only") is not True:
        errors.append("preview_only_must_be_true")
    if packet.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    for field_name in ("external_effects_allowed", "pr_creation_allowed", "branch_push_allowed"):
        if packet.get(field_name) is not False:
            errors.append(f"{field_name}_must_be_false")
    body = packet.get("body", {})
    if not isinstance(body, Mapping):
        errors.append("body_must_be_object")
        return
    if tuple(body.get("governance_scope", ())) != GOVERNANCE_SCOPE:
        errors.append("governance_scope_must_match_canonical_order")
    command_preview = packet.get("command_preview", {})
    if not isinstance(command_preview, Mapping):
        errors.append("command_preview_must_be_object")
        return
    if command_preview.get("preview_status") == "commands_rendered" and command_preview.get("commands_rendered") is not True:
        errors.append("command_preview_rendered_mismatch")
    if packet.get("packet_hash") != canonical_hash({**dict(packet), "packet_hash": ""}):
        errors.append("packet_hash_mismatch")


def _command_preview_summary(command_preview_packet: Mapping[str, Any] | None) -> dict[str, Any]:
    if not command_preview_packet:
        return {"preview_status": "absent", "commands_rendered": False, "packet_hash": ""}
    return {
        "preview_status": str(command_preview_packet.get("preview_status") or "blocked"),
        "commands_rendered": command_preview_packet.get("commands_rendered") is True,
        "packet_hash": str(command_preview_packet.get("packet_hash") or ""),
    }


def _testing_entries(
    candidate_packet: Mapping[str, Any],
    command_preview_packet: Mapping[str, Any] | None,
) -> list[str]:
    entries = [
        "Validate local PR candidate packet before metadata use.",
        "Validate PR metadata packet before command preview or external PR action.",
    ]
    if candidate_packet.get("test_refs"):
        entries.append("Candidate test refs: " + ", ".join(str(item) for item in candidate_packet.get("test_refs", ())))
    if command_preview_packet:
        entries.append("Command preview status: " + str(command_preview_packet.get("preview_status") or "absent"))
    return entries


def _rollback_entries(rollback: Mapping[str, Any]) -> list[str]:
    evidence_refs = [str(item) for item in rollback.get("evidence_refs", ())]
    if evidence_refs:
        return ["Rollback evidence refs: " + ", ".join(evidence_refs)]
    return ["Rollback evidence remains pending until local sandbox receipts complete."]


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


def _required_text(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name}_required")
    return normalized


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
    """Parse PR metadata packet builder arguments."""

    parser = argparse.ArgumentParser(description="Build projection-only PR metadata packet.")
    parser.add_argument("--candidate-packet", default=str(DEFAULT_CANDIDATE_PACKET))
    parser.add_argument("--command-preview-packet", default=str(DEFAULT_COMMAND_PREVIEW_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--target-branch", default="main")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for PR metadata packet building."""

    args = parse_args(argv)
    try:
        candidate_path = Path(args.candidate_packet)
        preview_path = Path(args.command_preview_packet)
        candidate_packet = _load_json_object(candidate_path)
        preview_packet = _load_json_object(preview_path) if str(args.command_preview_packet).strip() else None
        packet = build_pr_metadata_packet(
            candidate_packet=candidate_packet,
            candidate_packet_path=candidate_path,
            command_preview_packet=preview_packet,
            command_preview_packet_path=preview_path if preview_packet else None,
            target_branch=str(args.target_branch),
        )
        output_path = write_pr_metadata_packet(packet, Path(args.output))
        validation = validate_pr_metadata_packet(
            packet=packet,
            schema_path=Path(args.schema),
            packet_path=output_path,
        )
    except ValueError as exc:
        print(f"PR METADATA PACKET INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"PR METADATA PACKET INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"PR METADATA PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
