#!/usr/bin/env python3
"""Report repository-local workspace governance artifact inventory.

Purpose: provide a read-only inventory of artifacts declared by the repository
governance witness.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: Python standard library and docs/workspace-governance-witness.json.
Invariants:
  - Inventory is read-only and deterministic.
  - Artifact paths are repository-relative and cannot escape the checkout.
  - Missing or malformed artifact records produce explicit issues.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "docs" / "workspace-governance-witness.json"


@dataclass(frozen=True, slots=True)
class InventoryArtifact:
    """One governance artifact inventory record."""

    name: str
    path: str
    purpose: str
    exists: bool
    size_bytes: int | None
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


def build_inventory(witness: dict[str, Any], workspace_root: Path = WORKSPACE_ROOT) -> tuple[InventoryArtifact, ...]:
    """Build a read-only inventory from witness artifacts."""

    artifacts = witness.get("artifacts")
    if not isinstance(artifacts, list):
        return (
            InventoryArtifact(
                name="<witness>",
                path="<artifacts>",
                purpose="witness artifacts collection",
                exists=False,
                size_bytes=None,
                issue="artifacts must be a list",
            ),
        )

    inventory = tuple(_inventory_artifact(artifact, workspace_root) for artifact in artifacts)
    artifact_count = witness.get("artifact_count")
    if isinstance(artifact_count, bool) or artifact_count != len(artifacts):
        return inventory + (
            InventoryArtifact(
                name="<witness>",
                path="<artifact_count>",
                purpose="witness artifact count declaration",
                exists=False,
                size_bytes=None,
                issue="artifact_count must match artifacts length",
            ),
        )
    return inventory


def build_inventory_report(inventory: tuple[InventoryArtifact, ...]) -> dict[str, object]:
    """Build a machine-readable inventory report."""

    missing_count = sum(1 for artifact in inventory if not artifact.exists)
    issue_count = sum(1 for artifact in inventory if artifact.issue is not None)
    return {
        "report_id": "workspace_governance_inventory",
        "status": "passed" if missing_count == 0 and issue_count == 0 else "failed",
        "artifact_count": len(inventory),
        "missing_count": missing_count,
        "issue_count": issue_count,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "artifacts": [asdict(artifact) for artifact in inventory],
    }


def render_inventory(report: dict[str, object], output_stream: TextIO) -> None:
    """Render a human-readable inventory report."""

    output_stream.write(
        "STATUS: {0}; artifacts={1}; missing={2}; issues={3}\n".format(
            report["status"],
            report["artifact_count"],
            report["missing_count"],
            report["issue_count"],
        )
    )
    for artifact in report["artifacts"]:
        if not isinstance(artifact, dict):
            continue
        status = "present" if artifact["exists"] else "missing"
        issue = "" if artifact["issue"] is None else f"; issue={artifact['issue']}"
        output_stream.write(f"[{status}] {artifact['name']}: {artifact['path']}{issue}\n")


def _inventory_artifact(artifact: Any, workspace_root: Path) -> InventoryArtifact:
    if not isinstance(artifact, dict):
        return InventoryArtifact(
            name="<invalid>",
            path="<invalid>",
            purpose="invalid artifact entry",
            exists=False,
            size_bytes=None,
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
        return InventoryArtifact(
            name=name,
            path="<missing-path>",
            purpose=purpose,
            exists=False,
            size_bytes=None,
            issue="artifact path must be a non-empty string",
        )
    path_issue = _validate_relative_path(relative_path)
    if path_issue is not None:
        return InventoryArtifact(
            name=name,
            path=relative_path,
            purpose=purpose,
            exists=False,
            size_bytes=None,
            issue=path_issue,
        )
    artifact_path = workspace_root / relative_path
    if not artifact_path.is_file():
        return InventoryArtifact(
            name=name,
            path=relative_path,
            purpose=purpose,
            exists=False,
            size_bytes=None,
            issue="referenced file does not exist",
        )
    return InventoryArtifact(
        name=name,
        path=relative_path,
        purpose=purpose,
        exists=True,
        size_bytes=artifact_path.stat().st_size,
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
    """Report repository-local workspace governance inventory."""

    parser = argparse.ArgumentParser(description="Report workspace governance artifact inventory.")
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH, help="governance witness JSON path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable inventory JSON")
    args = parser.parse_args(argv)

    try:
        witness = load_witness(args.witness)
        inventory = build_inventory(witness)
        report = build_inventory_report(inventory)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-inventory: {exc}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        render_inventory(report, sys.stdout)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
