#!/usr/bin/env python3
"""Collect one Developer Workflow v1 sandbox receipt evidence record.

Purpose: hash explicit local artifacts into the evidence format consumed by
the Developer Workflow v1 sandbox receipt bundle builder.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local artifact files and the sandbox receipt bundle contract.
Invariants:
  - The collector does not run commands, write code, call connectors, or prepare PRs.
  - Only operator-supplied local artifact paths are read.
  - Evidence output records hashes and references, not raw artifact contents.
  - Unknown receipt ids and missing artifact files fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_developer_workflow_sandbox_receipt_bundle import EXPECTED_RECEIPTS  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_evidence.partial.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_evidence.collected.json"
DEFAULT_WORKFLOW_RUN_ID = "developer_workflow_v1_foundation_run"
CANONICAL_RECEIPT_IDS = frozenset(receipt_id for receipt_id, _, _ in EXPECTED_RECEIPTS)


def collect_developer_workflow_sandbox_receipt_evidence(
    *,
    existing_evidence: Mapping[str, Any] | None,
    workflow_run_id: str,
    receipt_id: str,
    before_file: Path,
    after_file: Path,
    diff_file: Path,
    command: str,
    rollback_command: str,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    """Return evidence JSON with one canonical receipt evidence record merged."""

    _require_receipt_id(receipt_id)
    normalized_refs = _normalize_refs(evidence_refs)
    evidence: dict[str, Any] = {
        "workflow_run_id": workflow_run_id.strip() or DEFAULT_WORKFLOW_RUN_ID,
        "receipts": {},
    }
    if existing_evidence:
        existing_workflow_run_id = str(existing_evidence.get("workflow_run_id") or "").strip()
        if existing_workflow_run_id:
            evidence["workflow_run_id"] = existing_workflow_run_id
        raw_receipts = existing_evidence.get("receipts", {})
        if not isinstance(raw_receipts, Mapping):
            raise ValueError("existing_receipts_must_be_object")
        evidence["receipts"] = {str(key): value for key, value in raw_receipts.items()}
    evidence["workflow_run_id"] = workflow_run_id.strip() or str(evidence["workflow_run_id"])
    evidence["receipts"][receipt_id] = {
        "before_state_hash": _hash_file(before_file),
        "after_state_hash": _hash_file(after_file),
        "diff_hash": _hash_file(diff_file),
        "rollback_command": _required_text(rollback_command, "rollback_command"),
        "command": _required_text(command, "command"),
        "evidence_refs": normalized_refs,
    }
    return evidence


def write_developer_workflow_sandbox_receipt_evidence(evidence: Mapping[str, Any], output_path: Path) -> Path:
    """Write collected evidence as deterministic JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _hash_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise ValueError(f"artifact_file_missing:{path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _normalize_refs(values: Sequence[str]) -> list[str]:
    refs = [str(value).strip() for value in values if str(value).strip()]
    if not refs:
        raise ValueError("evidence_refs_required")
    return list(dict.fromkeys(refs))


def _required_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_receipt_id(receipt_id: str) -> None:
    if receipt_id not in CANONICAL_RECEIPT_IDS:
        raise ValueError(f"unknown_receipt_id:{receipt_id}")


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"evidence_json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("evidence_json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse collector arguments."""

    parser = argparse.ArgumentParser(description="Collect one Developer Workflow sandbox receipt evidence record.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--workflow-run-id", default=DEFAULT_WORKFLOW_RUN_ID)
    parser.add_argument("--receipt-id", required=True, choices=tuple(sorted(CANONICAL_RECEIPT_IDS)))
    parser.add_argument("--before-file", required=True)
    parser.add_argument("--after-file", required=True)
    parser.add_argument("--diff-file", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--rollback-command", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the evidence collector."""

    args = parse_args(argv)
    try:
        existing_evidence = _load_json_object(Path(args.input) if args.input else None)
        evidence = collect_developer_workflow_sandbox_receipt_evidence(
            existing_evidence=existing_evidence,
            workflow_run_id=str(args.workflow_run_id),
            receipt_id=str(args.receipt_id),
            before_file=Path(args.before_file),
            after_file=Path(args.after_file),
            diff_file=Path(args.diff_file),
            command=str(args.command),
            rollback_command=str(args.rollback_command),
            evidence_refs=tuple(str(value) for value in args.evidence_ref),
        )
        output_path = write_developer_workflow_sandbox_receipt_evidence(evidence, Path(args.output))
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT EVIDENCE INVALID error={exc}")
        return 2
    if args.json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    else:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT EVIDENCE COLLECTED path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
