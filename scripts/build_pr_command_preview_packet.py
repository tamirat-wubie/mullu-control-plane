#!/usr/bin/env python3
"""Build a non-executing PR command preview packet.

Purpose: render external PR command text only when an approval witness grants
branch push and PR creation authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: external PR execution approval witness and local schema validation.
Invariants:
  - This packet never executes commands.
  - Command text is rendered only when witness authority is complete.
  - Blocked previews contain no push or PR creation command text.
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


DEFAULT_WITNESS = REPO_ROOT / "examples" / "external_pr_execution_approval_witness.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "pr_command_preview_packet.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_command_preview_packet.generated.json"
COMMAND_EFFECTS = ("push_branch", "open_external_pr")


@dataclass(frozen=True, slots=True)
class PrCommandPreviewPacketValidation:
    """Validation report for a PR command preview packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_path: str
    preview_status: str
    commands_rendered: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_pr_command_preview_packet(
    *,
    approval_witness: Mapping[str, Any],
    approval_witness_path: Path,
    pr_body_path: str = ".change_assurance/pr_body.md",
) -> dict[str, Any]:
    """Return a non-executing PR command preview packet."""

    admission = approval_witness.get("admission", {})
    if not isinstance(admission, Mapping):
        admission = {}
    branch_name = _required_text(admission.get("branch_name"), "branch_name")
    candidate_title = _required_text(admission.get("candidate_title"), "candidate_title")
    authority_ready = _witness_grants_external_pr_authority(approval_witness)
    packet = {
        "packet_id": "pr_command_preview_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _text_or_default(
            approval_witness.get("workflow_run_id"),
            "developer_workflow_v1_foundation_run",
        ),
        "preview_status": "commands_rendered" if authority_ready else "blocked",
        "preview_only": True,
        "execution_performed": False,
        "execution_boundary": "external_repository_pr",
        "external_effects_allowed_by_witness": authority_ready,
        "commands_rendered": authority_ready,
        "blocked_reason": "" if authority_ready else _blocked_reason(approval_witness),
        "witness": {
            "approval_status": str(approval_witness.get("approval_status") or "pending"),
            "execution_status": str(approval_witness.get("execution_status") or "awaiting_local_pr_tool_admission"),
            "witness_hash": str(approval_witness.get("witness_hash") or ""),
            "branch_name": branch_name,
            "candidate_title": candidate_title,
        },
        "command_preview": _command_preview(branch_name, candidate_title, pr_body_path) if authority_ready else [],
        "rollback_preview": _rollback_preview(branch_name),
        "source_refs": {
            "approval_witness_path": _path_label(approval_witness_path),
            "approval_witness_schema": "schemas/external_pr_execution_approval_witness.schema.json",
            "preview_builder": "python scripts/build_pr_command_preview_packet.py",
        },
        "packet_hash": "",
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def validate_pr_command_preview_packet(
    *,
    packet: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = Path("<generated>"),
) -> PrCommandPreviewPacketValidation:
    """Validate schema and non-executing PR preview semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(packet)))
    _validate_packet_semantics(packet, errors)
    return PrCommandPreviewPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_path=_path_label(packet_path),
        preview_status=str(packet.get("preview_status") or ""),
        commands_rendered=packet.get("commands_rendered") is True,
    )


def write_pr_command_preview_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic PR command preview packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str]) -> None:
    if packet.get("preview_only") is not True:
        errors.append("preview_only_must_be_true")
    if packet.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    witness = packet.get("witness", {})
    if not isinstance(witness, Mapping):
        errors.append("witness_must_be_object")
        return
    authority_ready = (
        packet.get("external_effects_allowed_by_witness") is True
        and witness.get("approval_status") == "approved"
        and witness.get("execution_status") == "approved_for_external_pr_execution"
    )
    expected_status = "commands_rendered" if authority_ready else "blocked"
    if packet.get("preview_status") != expected_status:
        errors.append(f"preview_status_must_be:{expected_status}")
    if packet.get("commands_rendered") is not authority_ready:
        errors.append("commands_rendered_mismatch")
    commands = tuple(packet.get("command_preview", ()))
    if authority_ready:
        if len(commands) != 2:
            errors.append("approved_preview_must_render_two_commands")
        observed_effects = tuple(str(item.get("effect", "")) for item in commands if isinstance(item, Mapping))
        if observed_effects != COMMAND_EFFECTS:
            errors.append("command_effects_must_match_canonical_order")
    elif commands:
        errors.append("blocked_preview_must_not_render_commands")
    if tuple(item.get("rollback_id", "") for item in packet.get("rollback_preview", ()) if isinstance(item, Mapping)) != (
        "delete_remote_branch",
        "close_external_pr",
    ):
        errors.append("rollback_preview_must_match_canonical_order")
    if packet.get("packet_hash") != canonical_hash({**dict(packet), "packet_hash": ""}):
        errors.append("packet_hash_mismatch")


def _witness_grants_external_pr_authority(witness: Mapping[str, Any]) -> bool:
    return (
        witness.get("approval_status") == "approved"
        and witness.get("execution_status") == "approved_for_external_pr_execution"
        and witness.get("external_effects_allowed") is True
        and witness.get("pr_creation_allowed") is True
        and witness.get("branch_push_allowed") is True
        and tuple(witness.get("approved_external_effects", ())) == COMMAND_EFFECTS
    )


def _command_preview(branch_name: str, title: str, pr_body_path: str) -> list[dict[str, str]]:
    quoted_title = _powershell_single_quote(title)
    quoted_body_path = _powershell_single_quote(pr_body_path)
    return [
        {
            "command_id": "push_branch",
            "effect": "push_branch",
            "command": f"git push -u origin {branch_name}",
        },
        {
            "command_id": "open_external_pr",
            "effect": "open_external_pr",
            "command": f"gh pr create --title {quoted_title} --body-file {quoted_body_path} --head {branch_name}",
        },
    ]


def _rollback_preview(branch_name: str) -> list[dict[str, str]]:
    return [
        {
            "rollback_id": "delete_remote_branch",
            "command": f"git push origin --delete {branch_name}",
        },
        {
            "rollback_id": "close_external_pr",
            "command": "gh pr close <pr-number> --comment 'Closing by governed rollback witness'",
        },
    ]


def _blocked_reason(witness: Mapping[str, Any]) -> str:
    if witness.get("execution_status") == "awaiting_operator_approval":
        return "operator_external_pr_approval_missing"
    if witness.get("execution_status") == "approved_for_external_pr_execution":
        return "approved_effect_flags_incomplete"
    return "local_pr_tool_admission_missing"


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


def _powershell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse PR command preview packet builder arguments."""

    parser = argparse.ArgumentParser(description="Build non-executing PR command preview packet.")
    parser.add_argument("--approval-witness", default=str(DEFAULT_WITNESS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pr-body-path", default=".change_assurance/pr_body.md")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for PR command preview packet building."""

    args = parse_args(argv)
    try:
        witness_path = Path(args.approval_witness)
        approval_witness = _load_json_object(witness_path)
        packet = build_pr_command_preview_packet(
            approval_witness=approval_witness,
            approval_witness_path=witness_path,
            pr_body_path=str(args.pr_body_path),
        )
        output_path = write_pr_command_preview_packet(packet, Path(args.output))
        validation = validate_pr_command_preview_packet(
            packet=packet,
            schema_path=Path(args.schema),
            packet_path=output_path,
        )
    except ValueError as exc:
        print(f"PR COMMAND PREVIEW PACKET INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"PR COMMAND PREVIEW PACKET INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"PR COMMAND PREVIEW PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
