#!/usr/bin/env python3
"""Validate a Local Developer Workflow v1 closure packet.

Purpose: fail closed if a closure packet overclaims execution authority or
drifts from its source preview artifacts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.local_developer_workflow_v1.closure_packet.
Invariants: validation rejects live execution, source mutation, branch push,
PR creation, merge, deployment, connector calls, and external writes.
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

from software_dev.local_developer_workflow_v1.closure_packet import (  # noqa: E402
    CLOSURE_PACKET_FILENAME,
    validate_local_developer_workflow_closure_packet,
)
from software_dev.local_developer_workflow_v1.runner import ARTIFACT_FILENAMES  # noqa: E402


DEFAULT_ARTIFACT_DIR = REPO_ROOT / ".change_assurance"
DEFAULT_PACKET = DEFAULT_ARTIFACT_DIR / CLOSURE_PACKET_FILENAME
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_DIR / "local_developer_workflow_v1_closure_packet_validation.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse closure packet validator arguments."""

    parser = argparse.ArgumentParser(description="Validate Local Developer Workflow v1 closure packet.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for closure packet validation."""

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
    validation = validate_local_developer_workflow_closure_packet(
        packet=packet,
        artifacts=artifacts,
        artifact_paths=artifact_paths,
        packet_path=packet_path,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("LOCAL DEVELOPER WORKFLOW CLOSURE PACKET VALID")
    else:
        print(f"LOCAL DEVELOPER WORKFLOW CLOSURE PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"json_root_must_be_object:{path}")
    return dict(payload)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


if __name__ == "__main__":
    raise SystemExit(main())
