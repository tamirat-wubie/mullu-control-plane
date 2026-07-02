#!/usr/bin/env python3
"""Validate a Local Developer Workflow v1 PR command preview packet.

Purpose: fail closed when command preview packets drift from review-only,
no-execution semantics.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local_developer_workflow_v1 artifacts and command preview packet
validator.
Invariants: validation rejects execution authority, branch pushes, PR creation,
external effects, and hash drift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from software_dev.local_developer_workflow_v1.command_preview_packet import (  # noqa: E402
    COMMAND_PREVIEW_PACKET_FILENAME,
    validate_local_developer_workflow_pr_command_preview_packet,
)
from software_dev.local_developer_workflow_v1.closure_packet import CLOSURE_PACKET_FILENAME  # noqa: E402
from software_dev.local_developer_workflow_v1.runner import ARTIFACT_FILENAMES  # noqa: E402


DEFAULT_ARTIFACT_DIR = REPO_ROOT / ".change_assurance"
DEFAULT_PACKET = DEFAULT_ARTIFACT_DIR / COMMAND_PREVIEW_PACKET_FILENAME
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_DIR / "local_developer_workflow_v1_pr_command_preview_packet_validation.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command preview packet validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Local Developer Workflow v1 PR command preview packet.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--closure-packet", default="")
    parser.add_argument("--require-closure-packet", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for command preview packet validation."""

    args = parse_args(argv)
    artifact_dir = Path(args.artifact_dir)
    artifact_paths = {
        key: artifact_dir / filename
        for key, filename in ARTIFACT_FILENAMES.items()
    }
    artifacts = {
        key: _load_json_object(path)
        for key, path in artifact_paths.items()
    }
    packet_path = Path(args.packet)
    packet = _load_json_object(packet_path)
    closure_packet_path = Path(args.closure_packet) if args.closure_packet else artifact_dir / CLOSURE_PACKET_FILENAME
    closure_packet = None
    errors: list[str] = []
    if closure_packet_path.exists():
        closure_packet = _load_json_object(closure_packet_path)
    elif args.require_closure_packet:
        errors.append(f"closure_packet_missing:{closure_packet_path}")
    validation = validate_local_developer_workflow_pr_command_preview_packet(
        packet=packet,
        artifacts=artifacts,
        closure_packet=closure_packet,
        artifact_paths=artifact_paths,
        packet_path=packet_path,
        closure_packet_path=closure_packet_path,
    )
    errors.extend(validation.errors)
    output_payload = validation.as_dict()
    output_payload["ok"] = not errors
    output_payload["errors"] = errors
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(output_payload, indent=2, sort_keys=True))
    elif not errors:
        print("LOCAL WORKFLOW PR COMMAND PREVIEW PACKET VALID")
    else:
        print(f"LOCAL WORKFLOW PR COMMAND PREVIEW PACKET INVALID errors={errors}")
    return 0 if not errors or not args.strict else 2


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"json_root_must_be_object:{path}")
    return dict(payload)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


if __name__ == "__main__":
    raise SystemExit(main())
