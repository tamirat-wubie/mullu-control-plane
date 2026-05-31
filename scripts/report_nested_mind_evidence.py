"""Purpose: summarize nested-mind observation evidence without mutation.
Governance scope: operator visibility for the P3 readiness gate only.
Dependencies: NestedMindEvidenceStore and validate_nested_mind_p3_readiness.
Invariants:
  - Performs no nested-mind network calls and writes no evidence.
  - Reports only typed record identifiers, counts, statuses, and blockers.
  - P3 remains blocked unless the readiness validator returns ready.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_PATH = REPO_ROOT / "mcoi"
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.persistence import NestedMindEvidenceStore  # noqa: E402
from validate_nested_mind_p3_readiness import validate_p3_readiness  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report nested-mind observation evidence status.")
    parser.add_argument("--store", required=True, help="Path to nested-mind evidence JSONL store")
    parser.add_argument("--mind-id", default="", help="Optional mind_id filter")
    args = parser.parse_args(argv)

    report = build_nested_mind_evidence_report(
        Path(args.store),
        mind_id=args.mind_id or None,
    )
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
    return 0 if report["readiness"]["status"] == "ready" else 1


def build_nested_mind_evidence_report(path: Path, *, mind_id: str | None = None) -> dict[str, Any]:
    store = NestedMindEvidenceStore(path)
    entries = store.list_by_mind_id(mind_id) if mind_id else store.list_all()
    readiness = validate_p3_readiness(path, mind_id=mind_id)
    counts = _record_counts(entries)
    return {
        "status": "ready" if readiness["status"] == "ready" else "blocked",
        "mind_id": mind_id or "",
        "total_records": len(entries),
        "record_counts": counts,
        "accepted_submission_ids": _ids_by_status(entries, "submission_report", "accepted"),
        "verified_commit_witness_ids": _ids_by_status(entries, "commit_witness", "verified"),
        "verified_reconciliation_report_ids": _ids_by_status(
            entries,
            "reconciliation_report",
            "verified",
        ),
        "readiness": readiness,
        "next_action": _next_action(readiness),
    }


def _record_counts(entries: tuple[object, ...]) -> dict[str, int]:
    counts: dict[str, int] = {
        "plan": 0,
        "submission_report": 0,
        "commit_witness": 0,
        "bridge_report": 0,
        "reconciliation_report": 0,
    }
    for entry in entries:
        record_type = str(getattr(entry, "record_type"))
        counts[record_type] = counts.get(record_type, 0) + 1
    return counts


def _ids_by_status(entries: tuple[object, ...], record_type: str, status: str) -> tuple[str, ...]:
    ids: list[str] = []
    for entry in entries:
        if getattr(entry, "record_type") != record_type:
            continue
        payload = getattr(entry, "payload")
        if payload.get("status") == status:
            ids.append(str(getattr(entry, "record_id")))
    return tuple(ids)


def _next_action(readiness: dict[str, Any]) -> str:
    if readiness["status"] == "ready":
        return "p3_gate_ready_for_operator_review"
    blockers = tuple(str(blocker) for blocker in readiness.get("blockers", ()))
    if blockers == ("verified_causal_chain_missing",):
        return "reconcile_verified_submission_witness_chain"
    return "collect_live_record_observation_submission_witness_and_reconciliation"


if __name__ == "__main__":
    raise SystemExit(main())
