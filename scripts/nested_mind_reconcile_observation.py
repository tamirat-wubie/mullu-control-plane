"""Purpose: operator CLI for nested-mind read-after-write reconciliation.
Governance scope: read-only verification of a stored commit witness.
Dependencies: nested-mind read connector, observation reconciler, evidence store.
Invariants:
  - Performs no nested-mind writes.
  - Appends only typed reconciliation reports to the evidence store.
  - Requires read-only nested-mind bootstrap gates.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_PATH = REPO_ROOT / "mcoi"
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.adapters import (  # noqa: E402
    NestedMindObservationReconciler,
)
from mcoi_runtime.app.nested_mind_integration import mount_nested_mind_connector_from_env  # noqa: E402
from mcoi_runtime.contracts import (  # noqa: E402
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
)
from mcoi_runtime.contracts._base import require_non_empty_text  # noqa: E402
from mcoi_runtime.persistence import NestedMindEvidenceStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile a nested-mind observation commit witness.")
    parser.add_argument("--store", required=True, help="Append-only nested-mind evidence JSONL store")
    parser.add_argument("--plan-id", required=True, help="Plan id bound to the commit witness")
    parser.add_argument("--witness-id", required=True, help="Stored NestedMindCommitWitness id")
    parser.add_argument("--no-replay", action="store_true", help="Skip replay route; projection and audit still run")
    args = parser.parse_args(argv)

    store_path = Path(_require_cli_text(args.store, "store"))
    plan_id = _require_cli_text(args.plan_id, "plan_id")
    witness_id = _require_cli_text(args.witness_id, "witness_id")

    store = NestedMindEvidenceStore(store_path)
    witness = _load_witness(store, witness_id)
    bootstrap = mount_nested_mind_connector_from_env(runtime_env=os.environ, clock=_utc_now)
    if bootstrap.connector is None:
        raise RuntimeError("nested-mind read connector was not mounted")
    reconciler = NestedMindObservationReconciler(clock=_utc_now, read_connector=bootstrap.connector)
    report = reconciler.reconcile(plan_id=plan_id, witness=witness, replay=not args.no_replay)
    store.record_reconciliation_report(report)
    print(report.to_json())
    return 0 if report.status.value == "verified" else 1


def _load_witness(store: NestedMindEvidenceStore, witness_id: str) -> NestedMindCommitWitness:
    for entry in store.list_all():
        if entry.record_type == "commit_witness" and entry.record_id == witness_id:
            return _witness_from_payload(entry.payload)
    raise RuntimeError("commit witness not found in nested-mind evidence store")


def _require_cli_text(value: str, field_name: str) -> str:
    try:
        return require_non_empty_text(value, field_name)
    except ValueError as exc:
        raise RuntimeError(f"{field_name} is required") from exc


def _witness_from_payload(payload: Mapping[str, Any]) -> NestedMindCommitWitness:
    return NestedMindCommitWitness(
        witness_id=str(payload.get("witness_id", "")),
        proposal_evidence_id=str(payload.get("proposal_evidence_id", "")),
        mind_id=str(payload.get("mind_id", "")),
        mullu_receipt_hash=str(payload.get("mullu_receipt_hash", "")),
        nested_mind_commit_hash=str(payload.get("nested_mind_commit_hash", "")),
        nested_mind_history_hash=str(payload.get("nested_mind_history_hash", "")),
        witnessed_at=str(payload.get("witnessed_at", "")),
        status=NestedMindCommitWitnessStatus(str(payload.get("status", ""))),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {},
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
