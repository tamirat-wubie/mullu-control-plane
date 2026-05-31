"""Purpose: read-after-write reconciliation for nested-mind observations.
Governance scope: read-only projection/audit/replay verification after submit.
Dependencies: read-only nested-mind connector JSON methods and witness contracts.
Invariants:
  - Reconciliation performs no writes and admits no memory.
  - Projection must expose expected commit and history hashes.
  - Audit must confirm expected history hash before VERIFIED status is emitted.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from mcoi_runtime.contracts.integration import ConnectorStatus
from mcoi_runtime.contracts.nested_mind_observation_reconciliation import (
    NestedMindObservationReconciliationReport,
    NestedMindObservationReconciliationStatus,
)
from mcoi_runtime.contracts.nested_mind_receipts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
)
from mcoi_runtime.core.invariants import stable_identifier


class NestedMindObservationReconciler:
    """Read-only verifier for visibility of a nested-mind observation commit."""

    def __init__(self, *, clock: Callable[[], str], read_connector: object) -> None:
        self._clock = clock
        self._read_connector = read_connector

    def reconcile(
        self,
        *,
        plan_id: str,
        witness: NestedMindCommitWitness,
        replay: bool = True,
    ) -> NestedMindObservationReconciliationReport:
        checked_at = self._clock()
        if witness.status is not NestedMindCommitWitnessStatus.VERIFIED:
            projection = self._read_connector.read_projection_json(witness.mind_id)
            audit = self._read_connector.verify_history_json(witness.mind_id)
            return self._report(
                plan_id=plan_id,
                witness=witness,
                projection_result_id=projection.connector_result.result_id,
                audit_result_id=audit.connector_result.result_id,
                replay_result_id=None,
                status=NestedMindObservationReconciliationStatus.FAILED,
                checked_at=checked_at,
                blockers=("commit_witness_not_verified",),
            )

        projection = self._read_connector.read_projection_json(witness.mind_id)
        audit = self._read_connector.verify_history_json(witness.mind_id)
        replay_outcome = self._read_connector.replay_history_json(witness.mind_id) if replay else None

        if (
            projection.connector_result.status is not ConnectorStatus.SUCCEEDED
            or audit.connector_result.status is not ConnectorStatus.SUCCEEDED
            or (replay_outcome is not None and replay_outcome.connector_result.status is not ConnectorStatus.SUCCEEDED)
        ):
            return self._report(
                plan_id=plan_id,
                witness=witness,
                projection_result_id=projection.connector_result.result_id,
                audit_result_id=audit.connector_result.result_id,
                replay_result_id=(
                    replay_outcome.connector_result.result_id if replay_outcome is not None else None
                ),
                status=NestedMindObservationReconciliationStatus.FAILED,
                checked_at=checked_at,
                blockers=("connector_read_failed",),
            )

        projection_payload = projection.json_payload
        audit_payload = audit.json_payload
        projection_commit = _first_text(projection_payload, "commit_hash", "latest_commit_hash")
        projection_history = _first_text(projection_payload, "history_hash", "latest_history_hash")
        audit_history = _first_text(audit_payload, "history_hash", "verified_history_hash")

        if not projection_commit:
            return self._report(
                plan_id=plan_id,
                witness=witness,
                projection_result_id=projection.connector_result.result_id,
                audit_result_id=audit.connector_result.result_id,
                replay_result_id=(
                    replay_outcome.connector_result.result_id if replay_outcome is not None else None
                ),
                status=NestedMindObservationReconciliationStatus.NOT_VISIBLE,
                checked_at=checked_at,
                blockers=("projection_missing_commit_hash",),
            )
        if projection_commit != witness.nested_mind_commit_hash or projection_history != witness.nested_mind_history_hash:
            return self._report(
                plan_id=plan_id,
                witness=witness,
                projection_result_id=projection.connector_result.result_id,
                audit_result_id=audit.connector_result.result_id,
                replay_result_id=(
                    replay_outcome.connector_result.result_id if replay_outcome is not None else None
                ),
                status=NestedMindObservationReconciliationStatus.PROJECTION_MISMATCH,
                checked_at=checked_at,
                blockers=("projection_hash_mismatch",),
            )
        if audit_history != witness.nested_mind_history_hash:
            return self._report(
                plan_id=plan_id,
                witness=witness,
                projection_result_id=projection.connector_result.result_id,
                audit_result_id=audit.connector_result.result_id,
                replay_result_id=(
                    replay_outcome.connector_result.result_id if replay_outcome is not None else None
                ),
                status=NestedMindObservationReconciliationStatus.HISTORY_MISMATCH,
                checked_at=checked_at,
                blockers=("audit_history_hash_mismatch",),
            )
        return self._report(
            plan_id=plan_id,
            witness=witness,
            projection_result_id=projection.connector_result.result_id,
            audit_result_id=audit.connector_result.result_id,
            replay_result_id=(
                replay_outcome.connector_result.result_id if replay_outcome is not None else None
            ),
            status=NestedMindObservationReconciliationStatus.VERIFIED,
            checked_at=checked_at,
            blockers=(),
            metadata={"memory_admission": False},
        )

    def _report(
        self,
        *,
        plan_id: str,
        witness: NestedMindCommitWitness,
        projection_result_id: str,
        audit_result_id: str,
        replay_result_id: str | None,
        status: NestedMindObservationReconciliationStatus,
        checked_at: str,
        blockers: tuple[str, ...],
        metadata: Mapping[str, Any] | None = None,
    ) -> NestedMindObservationReconciliationReport:
        return NestedMindObservationReconciliationReport(
            report_id=stable_identifier(
                "nested-mind-observation-reconciliation",
                {
                    "plan_id": plan_id,
                    "commit_witness_id": witness.witness_id,
                    "status": status.value,
                    "checked_at": checked_at,
                },
            ),
            plan_id=plan_id,
            commit_witness_id=witness.witness_id,
            mind_id=witness.mind_id,
            mullu_receipt_hash=witness.mullu_receipt_hash,
            expected_commit_hash=witness.nested_mind_commit_hash,
            expected_history_hash=witness.nested_mind_history_hash,
            projection_connector_result_id=projection_result_id,
            audit_connector_result_id=audit_result_id,
            replay_connector_result_id=replay_result_id,
            status=status,
            checked_at=checked_at,
            blockers=blockers,
            metadata=metadata or {},
        )


def _first_text(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None
