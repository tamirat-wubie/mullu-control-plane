#!/usr/bin/env python3
"""Report repository-local workspace governance artifact integrity.

Purpose: provide a read-only integrity report for artifacts declared by the
repository governance witness.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: Python standard library and docs/workspace-governance-witness.json.
Invariants:
  - Integrity reporting is read-only and deterministic.
  - Artifact paths are repository-relative and cannot escape the checkout.
  - Existing artifacts always receive SHA-256 digest evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "docs" / "workspace-governance-witness.json"


@dataclass(frozen=True, slots=True)
class IntegrityArtifact:
    """One governance artifact integrity record."""

    name: str
    path: str
    purpose: str
    exists: bool
    size_bytes: int | None
    sha256: str | None
    issue: str | None


def load_witness(witness_path: Path) -> dict[str, Any]:
    """Load a governance witness JSON object."""

    if not witness_path.exists():
        raise FileNotFoundError(f"missing governance witness: {witness_path}")
    if not witness_path.is_file():
        raise IsADirectoryError(f"governance witness path is not a file: {witness_path}")
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    if not isinstance(witness, dict):
        raise ValueError("governance witness must be a JSON object")
    return witness


def build_integrity(witness: dict[str, Any], workspace_root: Path = WORKSPACE_ROOT) -> tuple[IntegrityArtifact, ...]:
    """Build a read-only integrity report from witness artifacts."""

    artifacts = witness.get("artifacts")
    if not isinstance(artifacts, list):
        return (
            IntegrityArtifact(
                name="<witness>",
                path="<artifacts>",
                purpose="witness artifacts collection",
                exists=False,
                size_bytes=None,
                sha256=None,
                issue="artifacts must be a list",
            ),
        )

    integrity = tuple(_integrity_artifact(artifact, workspace_root) for artifact in artifacts)
    artifact_count = witness.get("artifact_count")
    if isinstance(artifact_count, bool) or artifact_count != len(artifacts):
        return integrity + (
            IntegrityArtifact(
                name="<witness>",
                path="<artifact_count>",
                purpose="witness artifact count declaration",
                exists=False,
                size_bytes=None,
                sha256=None,
                issue="artifact_count must match artifacts length",
            ),
        )
    return integrity


def build_integrity_report(integrity_records: tuple[IntegrityArtifact, ...]) -> dict[str, object]:
    """Build a machine-readable integrity report."""

    missing_count = sum(1 for artifact in integrity_records if not artifact.exists)
    issue_count = sum(1 for artifact in integrity_records if artifact.issue is not None)
    hashed_count = sum(1 for artifact in integrity_records if artifact.sha256 is not None)
    return {
        "report_id": "workspace_governance_integrity",
        "status": "passed" if missing_count == 0 and issue_count == 0 else "failed",
        "artifact_count": len(integrity_records),
        "hashed_count": hashed_count,
        "missing_count": missing_count,
        "issue_count": issue_count,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "artifacts": [asdict(artifact) for artifact in integrity_records],
    }


def render_integrity(report: dict[str, object], output_stream: TextIO) -> None:
    """Render a human-readable integrity report."""

    output_stream.write(
        "STATUS: {0}; artifacts={1}; hashed={2}; missing={3}; issues={4}\n".format(
            report["status"],
            report["artifact_count"],
            report["hashed_count"],
            report["missing_count"],
            report["issue_count"],
        )
    )
    for artifact in report["artifacts"]:
        if not isinstance(artifact, dict):
            continue
        status = "hashed" if artifact["sha256"] is not None else "missing"
        digest = "" if artifact["sha256"] is None else f"; sha256={artifact['sha256']}"
        issue = "" if artifact["issue"] is None else f"; issue={artifact['issue']}"
        output_stream.write(f"[{status}] {artifact['name']}: {artifact['path']}{digest}{issue}\n")


def _integrity_artifact(artifact: Any, workspace_root: Path) -> IntegrityArtifact:
    if not isinstance(artifact, dict):
        return IntegrityArtifact(
            name="<invalid>",
            path="<invalid>",
            purpose="invalid artifact entry",
            exists=False,
            size_bytes=None,
            sha256=None,
            issue="artifact entry must be an object",
        )
    name = artifact.get("name")
    relative_path = artifact.get("path")
    purpose = artifact.get("purpose")
    if not isinstance(name, str) or not name:
        name = "<missing-name>"
    if not isinstance(purpose, str) or not purpose:
        purpose = "<missing-purpose>"
    if not isinstance(relative_path, str) or not relative_path:
        return IntegrityArtifact(
            name=name,
            path="<missing-path>",
            purpose=purpose,
            exists=False,
            size_bytes=None,
            sha256=None,
            issue="artifact path must be a non-empty string",
        )
    path_issue = _validate_relative_path(relative_path)
    if path_issue is not None:
        return IntegrityArtifact(
            name=name,
            path=relative_path,
            purpose=purpose,
            exists=False,
            size_bytes=None,
            sha256=None,
            issue=path_issue,
        )
    artifact_path = workspace_root / relative_path
    if not artifact_path.is_file():
        return IntegrityArtifact(
            name=name,
            path=relative_path,
            purpose=purpose,
            exists=False,
            size_bytes=None,
            sha256=None,
            issue="referenced file does not exist",
        )
    payload = artifact_path.read_bytes()
    return IntegrityArtifact(
        name=name,
        path=relative_path,
        purpose=purpose,
        exists=True,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        issue=None,
    )


def _validate_relative_path(relative_path: str) -> str | None:
    path = Path(relative_path)
    if path.is_absolute():
        return "absolute path is not allowed"
    if "\\" in relative_path:
        return "backslash path is not allowed"
    if any(path_part == ".." for path_part in path.parts):
        return "parent traversal is not allowed"
    return None


def main(argv: list[str] | None = None) -> int:
    """Report repository-local workspace governance artifact integrity."""

    parser = argparse.ArgumentParser(description="Report workspace governance artifact integrity.")
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH, help="governance witness JSON path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable integrity JSON")
    args = parser.parse_args(argv)

    try:
        witness = load_witness(args.witness)
        integrity_records = build_integrity(witness)
        report = build_integrity_report(integrity_records)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-integrity: {exc}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        render_integrity(report, sys.stdout)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
