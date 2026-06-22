#!/usr/bin/env python3
"""Validate pull-request hygiene before merge.

Purpose: catch accidental placeholder/temp files, oversized accidental diffs,
and create/delete churn before a branch is considered merge-ready.
Governance scope: source-control hygiene only; this script does not call live
connectors, mutate GitHub state, write product runtime state, or claim release
readiness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

_DEFAULT_MAX_CHANGED_FILES = 200
_FORBIDDEN_EXACT_NAMES = {
    ".tmp",
    ".temp",
    ".scratch",
    ".tmp-should-not-exist",
    "tmp",
    "temp",
    "scratch",
    "placeholder",
    "untitled",
    "deleteme",
    "delete_me",
    "delete-me",
}
_FORBIDDEN_SUFFIXES = (
    "~",
    ".bak",
    ".orig",
    ".rej",
    ".swp",
    ".tmp",
    ".temp",
    ".placeholder",
)
_FORBIDDEN_PREFIXES = (
    "tmp_",
    "temp_",
    "scratch_",
    "placeholder_",
    "delete_me",
    "deleteme",
)
_FORBIDDEN_TOP_LEVEL_DIRS = {"tmp", "temp", "scratch", ".tmp", ".temp", ".scratch"}
_SAFE_STATUS_PREFIXES = ("A", "M", "D", "R", "C", "T")


class PrHygieneError(ValueError):
    """Raised when the changed-file manifest is malformed."""


def validate_changed_files(
    lines: Sequence[str],
    *,
    max_changed_files: int = _DEFAULT_MAX_CHANGED_FILES,
) -> dict[str, Any]:
    """Return a PR hygiene receipt for a git name-status manifest."""

    entries = _parse_name_status_lines(lines)
    changed_paths = [entry["path"] for entry in entries]
    violations: list[dict[str, str]] = []

    if len(changed_paths) > max_changed_files:
        violations.append(
            {
                "violation_id": "changed_file_count_exceeds_limit",
                "path": "*",
                "detail": f"{len(changed_paths)} changed files exceeds limit {max_changed_files}",
            }
        )

    for entry in entries:
        path = entry["path"]
        status = entry["status"]
        if not status.startswith(_SAFE_STATUS_PREFIXES):
            violations.append(
                {
                    "violation_id": "unsupported_change_status",
                    "path": path,
                    "detail": f"unsupported status {status}",
                }
            )
        placeholder_reason = _placeholder_reason(path)
        if placeholder_reason:
            violations.append(
                {
                    "violation_id": "placeholder_or_temporary_file_path",
                    "path": path,
                    "detail": placeholder_reason,
                }
            )

    path_statuses: dict[str, set[str]] = {}
    for entry in entries:
        path_statuses.setdefault(entry["path"], set()).add(entry["status"][0])
        old_path = entry.get("old_path")
        if isinstance(old_path, str) and old_path:
            path_statuses.setdefault(old_path, set()).add("D")
    for path, statuses in sorted(path_statuses.items()):
        if "A" in statuses and "D" in statuses:
            violations.append(
                {
                    "violation_id": "create_delete_churn_detected",
                    "path": path,
                    "detail": "same path appears as both added and deleted in the change manifest",
                }
            )

    status = "passed" if not violations else "failed"
    return {
        "receipt_id": "pr_hygiene_guard_receipt_v1",
        "status": status,
        "changed_file_count": len(changed_paths),
        "max_changed_files": max_changed_files,
        "violations": violations,
        "changed_files": changed_paths,
        "governance_boundary": {
            "source_control_hygiene_only": True,
            "repository_write_allowed": False,
            "github_mutation_allowed": False,
            "runtime_effect_allowed": False,
            "customer_readiness_claim_allowed": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changed-files",
        type=Path,
        required=True,
        help="Path to a git diff --name-status style changed-file manifest.",
    )
    parser.add_argument("--max-files", type=int, default=_DEFAULT_MAX_CHANGED_FILES)
    parser.add_argument("--json", action="store_true", help="Print the hygiene receipt as JSON.")
    args = parser.parse_args(argv)

    lines = args.changed_files.read_text(encoding="utf-8").splitlines()
    receipt = validate_changed_files(lines, max_changed_files=args.max_files)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"PR hygiene: {receipt['status']} ({receipt['changed_file_count']} files)")
        for violation in receipt["violations"]:
            print(f"- {violation['violation_id']}: {violation['path']} — {violation['detail']}")
    return 0 if receipt["status"] == "passed" else 1


def _parse_name_status_lines(lines: Iterable[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        parts = re.split(r"\s+", line, maxsplit=2)
        if len(parts) < 2:
            raise PrHygieneError(f"malformed changed-file line: {raw_line!r}")
        status = parts[0]
        if status.startswith(("R", "C")):
            if len(parts) != 3:
                raise PrHygieneError(f"rename/copy line must include old and new path: {raw_line!r}")
            entries.append({"status": status, "old_path": _normalize_path(parts[1]), "path": _normalize_path(parts[2])})
            continue
        entries.append({"status": status, "path": _normalize_path(parts[1])})
    return entries


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or ".." in normalized.split("/"):
        raise PrHygieneError(f"unsafe changed-file path: {path!r}")
    return normalized


def _placeholder_reason(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "empty path"
    if parts[0].lower() in _FORBIDDEN_TOP_LEVEL_DIRS:
        return "top-level temporary/scratch directory is not allowed"
    name = parts[-1].lower()
    if name in _FORBIDDEN_EXACT_NAMES:
        return "placeholder or temporary file name is not allowed"
    if name.startswith(_FORBIDDEN_PREFIXES):
        return "placeholder or temporary file prefix is not allowed"
    if name.endswith(_FORBIDDEN_SUFFIXES):
        return "temporary editor/backup suffix is not allowed"
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
