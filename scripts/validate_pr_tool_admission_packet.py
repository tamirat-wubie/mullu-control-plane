#!/usr/bin/env python3
"""Validate a projection-only PR tool admission packet.

Purpose: prove PR tool admission is local-only and cannot push, open, merge,
deploy, or call connectors.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: PR tool admission packet schema and semantic validator.
Invariants: external effects remain blocked and packet hash is checked.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_pr_tool_admission_packet import (  # noqa: E402
    DEFAULT_SCHEMA,
    PrToolAdmissionPacketValidation,
    validate_pr_tool_admission_packet as validate_pr_tool_admission_packet_object,
)


DEFAULT_PACKET = REPO_ROOT / "examples" / "pr_tool_admission_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_tool_admission_packet_validation.json"


def validate_pr_tool_admission_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
) -> PrToolAdmissionPacketValidation:
    """Validate a PR tool admission packet file."""

    packet = _load_json_object(packet_path)
    return validate_pr_tool_admission_packet_object(
        packet=packet,
        schema_path=schema_path,
        packet_path=packet_path,
    )


def write_pr_tool_admission_packet_validation(
    validation: PrToolAdmissionPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse PR tool admission packet validation arguments."""

    parser = argparse.ArgumentParser(description="Validate PR tool admission packet.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for PR tool admission packet validation."""

    args = parse_args(argv)
    validation = validate_pr_tool_admission_packet(
        packet_path=Path(args.packet),
        schema_path=Path(args.schema),
    )
    write_pr_tool_admission_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("PR TOOL ADMISSION PACKET VALID")
    else:
        print(f"PR TOOL ADMISSION PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
