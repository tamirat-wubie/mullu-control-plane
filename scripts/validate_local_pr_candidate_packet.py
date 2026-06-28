#!/usr/bin/env python3
"""Validate the local PR candidate packet.

Purpose: prove the local PR candidate packet remains a projection-only artifact
and does not grant PR creation, branch push, merge, deployment, or connector
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local PR candidate packet schema and builder semantics.
Invariants: candidate readiness requires approval and complete receipts while
all external effects remain disabled.
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

from scripts.build_local_pr_candidate_packet import (  # noqa: E402
    DEFAULT_SCHEMA,
    validate_local_pr_candidate_packet as validate_packet_object,
)


DEFAULT_PACKET = REPO_ROOT / "examples" / "local_pr_candidate_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "local_pr_candidate_packet_validation.json"


@dataclass(frozen=True, slots=True)
class LocalPrCandidatePacketFileValidation:
    """Validation report for a local PR candidate packet file."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    candidate_status: str
    candidate_ready: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_local_pr_candidate_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
) -> LocalPrCandidatePacketFileValidation:
    """Validate a local PR candidate packet file."""

    errors: list[str] = []
    packet = _load_json_object(packet_path, errors)
    if packet:
        validation = validate_packet_object(
            packet=packet,
            schema_path=schema_path,
            packet_path=packet_path,
        )
        errors.extend(validation.errors)
    return LocalPrCandidatePacketFileValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        candidate_status=str(packet.get("candidate_status", "")) if isinstance(packet, dict) else "",
        candidate_ready=packet.get("candidate_ready") is True if isinstance(packet, dict) else False,
    )


def write_local_pr_candidate_packet_validation(
    validation: LocalPrCandidatePacketFileValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic validation report."""

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

    parser = argparse.ArgumentParser(description="Validate local PR candidate packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for local PR candidate packet validation."""

    args = parse_args(argv)
    validation = validate_local_pr_candidate_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
    )
    write_local_pr_candidate_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print(f"LOCAL PR CANDIDATE PACKET OK packet={validation.packet_path}")
    else:
        print(f"LOCAL PR CANDIDATE PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
