#!/usr/bin/env python3
"""Validate the PR-preparation approval packet.

Purpose: prove the Developer Workflow v1 PR-preparation approval packet is a
projection-only local approval request, not authority to open an external PR.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: PR-preparation approval packet schema, example packet, and
builder semantics.
Invariants:
  - External effects and PR creation stay disabled.
  - Complete sandbox receipts can request approval only for local PR candidate
    packet preparation.
  - Packet hash must match canonical packet content.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_pr_preparation_approval_packet import (  # noqa: E402
    DEFAULT_SCHEMA,
    validate_pr_preparation_approval_packet as validate_packet_object,
)


DEFAULT_PACKET = REPO_ROOT / "examples" / "pr_preparation_approval_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_preparation_approval_packet_validation.json"


@dataclass(frozen=True, slots=True)
class PrPreparationApprovalPacketFileValidation:
    """Validation report for the PR-preparation approval packet fixture."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_status: str
    bundle_ready: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_pr_preparation_approval_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
) -> PrPreparationApprovalPacketFileValidation:
    """Validate a PR-preparation approval packet file."""

    errors: list[str] = []
    packet = _load_json_object(packet_path, errors)
    if packet:
        validation = validate_packet_object(
            packet=packet,
            schema_path=schema_path,
            packet_path=packet_path,
        )
        errors.extend(validation.errors)
    bundle = packet.get("bundle", {}) if isinstance(packet, dict) else {}
    return PrPreparationApprovalPacketFileValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_status=str(packet.get("packet_status", "")) if isinstance(packet, dict) else "",
        bundle_ready=bundle.get("ready") is True if isinstance(bundle, dict) else False,
    )


def write_pr_preparation_approval_packet_validation(
    validation: PrPreparationApprovalPacketFileValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic packet validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"packet_file_missing:{_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"packet_json_parse_failed:{_path_label(path)}")
        return {}
    if not isinstance(payload, dict):
        errors.append("packet_json_root_must_be_object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse validator arguments."""

    parser = argparse.ArgumentParser(description="Validate PR-preparation approval packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for PR-preparation approval packet validation."""

    args = parse_args(argv)
    validation = validate_pr_preparation_approval_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
    )
    write_pr_preparation_approval_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print(f"PR PREPARATION APPROVAL PACKET OK packet={validation.packet_path}")
    else:
        print(f"PR PREPARATION APPROVAL PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
