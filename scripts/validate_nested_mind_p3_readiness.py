"""Purpose: validate P3 readiness from append-only nested-mind evidence.
Governance scope: gate memory-lattice topology work behind live verified
record_observation evidence.
Dependencies: NestedMindEvidenceStore and runtime-only nested-mind records.
Invariants:
  - P3 is blocked unless accepted submission, verified witness, and verified
    reconciliation are present in one causal chain.
  - This script is read-only and performs no nested-mind network calls.
  - Tokens and raw response bodies are never required or inspected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_PATH = REPO_ROOT / "mcoi"
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.persistence.nested_mind_store import NestedMindEvidenceStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate nested-mind P3 readiness.")
    parser.add_argument("--store", required=True, help="Path to nested-mind evidence JSONL store")
    parser.add_argument("--mind-id", default="", help="Optional mind_id filter")
    args = parser.parse_args(argv)

    result = validate_p3_readiness(Path(args.store), mind_id=args.mind_id or None)
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["status"] == "ready" else 1


def validate_p3_readiness(path: Path, *, mind_id: str | None = None) -> dict[str, Any]:
    store = NestedMindEvidenceStore(path)
    entries = store.list_by_mind_id(mind_id) if mind_id else store.list_all()
    submissions = [
        entry.payload
        for entry in entries
        if entry.record_type == "submission_report" and entry.payload.get("status") == "accepted"
    ]
    witnesses = [
        entry.payload
        for entry in entries
        if entry.record_type == "commit_witness" and entry.payload.get("status") == "verified"
    ]
    reconciliations = [
        entry.payload
        for entry in entries
        if entry.record_type == "reconciliation_report" and entry.payload.get("status") == "verified"
    ]

    blockers: list[str] = []
    if not submissions:
        blockers.append("accepted_submission_missing")
    if not witnesses:
        blockers.append("verified_commit_witness_missing")
    if not reconciliations:
        blockers.append("verified_reconciliation_missing")
    if blockers:
        return _result("blocked", blockers=blockers)

    for submission in submissions:
        witness = _matching_witness(submission, witnesses)
        if witness is None:
            continue
        reconciliation = _matching_reconciliation(submission, witness, reconciliations)
        if reconciliation is None:
            continue
        return _result(
            "ready",
            plan_id=str(submission["plan_id"]),
            mind_id=str(submission["mind_id"]),
            commit_witness_id=str(witness["witness_id"]),
            reconciliation_report_id=str(reconciliation["report_id"]),
        )

    return _result("blocked", blockers=("verified_causal_chain_missing",))


def _matching_witness(
    submission: Mapping[str, Any],
    witnesses: list[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    expected_witness_id = submission.get("commit_witness_id")
    for witness in witnesses:
        if witness.get("witness_id") != expected_witness_id:
            continue
        if witness.get("mind_id") != submission.get("mind_id"):
            continue
        if witness.get("proposal_evidence_id") != submission.get("proposal_evidence_id"):
            continue
        return witness
    return None


def _matching_reconciliation(
    submission: Mapping[str, Any],
    witness: Mapping[str, Any],
    reconciliations: list[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    for reconciliation in reconciliations:
        if reconciliation.get("plan_id") != submission.get("plan_id"):
            continue
        if reconciliation.get("commit_witness_id") != witness.get("witness_id"):
            continue
        if reconciliation.get("mind_id") != submission.get("mind_id"):
            continue
        if reconciliation.get("expected_commit_hash") != witness.get("nested_mind_commit_hash"):
            continue
        if reconciliation.get("expected_history_hash") != witness.get("nested_mind_history_hash"):
            continue
        return reconciliation
    return None


def _result(
    status: str,
    *,
    blockers: tuple[str, ...] | list[str] = (),
    plan_id: str = "",
    mind_id: str = "",
    commit_witness_id: str = "",
    reconciliation_report_id: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "blockers": tuple(blockers),
        "plan_id": plan_id,
        "mind_id": mind_id,
        "commit_witness_id": commit_witness_id,
        "reconciliation_report_id": reconciliation_report_id,
    }


if __name__ == "__main__":
    raise SystemExit(main())
