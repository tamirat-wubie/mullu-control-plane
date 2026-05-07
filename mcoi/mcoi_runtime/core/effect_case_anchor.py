"""Purpose: create durable case anchors for unresolved Effect Assurance results.
Governance scope: effect mismatch investigation anchoring only.
Dependencies: case runtime contracts and runtime invariant helpers.
Invariants:
  - Missing case runtime leaves behavior unchanged.
  - Duplicate anchors are idempotent for retry-safe reconciliation.
  - Outward-facing case strings are stable and non-reflective.
"""

from __future__ import annotations

from mcoi_runtime.contracts.case_runtime import CaseKind, CaseSeverity, FindingSeverity
from mcoi_runtime.contracts.effect_assurance import ReconciliationStatus
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


def open_effect_reconciliation_case(
    case_runtime: CaseRuntimeEngine | None,
    *,
    command_id: str,
    tenant_id: str,
    source_type: str,
    source_id: str,
    effect_plan_id: str,
    verification_result_id: str,
    reconciliation_status: ReconciliationStatus,
) -> str | None:
    """Open a case, evidence item, and finding for an unresolved effect result."""
    if case_runtime is None:
        return None

    case_id = f"case-{command_id}"
    try:
        case_runtime.open_case(
            case_id,
            tenant_id,
            "Effect reconciliation mismatch",
            kind=CaseKind.INCIDENT,
            severity=CaseSeverity.HIGH,
            description="Governed effect reconciliation requires investigation.",
            opened_by="effect_assurance",
        )
    except RuntimeCoreInvariantError as exc:
        if "Duplicate case_id" not in str(exc):
            raise

    evidence_id = stable_identifier(
        "effect-case-evidence",
        {
            "case_id": case_id,
            "effect_plan_id": effect_plan_id,
            "verification_result_id": verification_result_id,
            "source_id": source_id,
        },
    )
    try:
        case_runtime.add_evidence(
            evidence_id,
            case_id,
            source_type,
            source_id,
            title="Effect reconciliation record",
            description="Effect reconciliation evidence requires review.",
            submitted_by="effect_assurance",
        )
    except RuntimeCoreInvariantError as exc:
        if "Duplicate evidence_id" not in str(exc):
            raise

    finding_id = stable_identifier(
        "effect-case-finding",
        {
            "case_id": case_id,
            "effect_plan_id": effect_plan_id,
            "status": reconciliation_status.value,
        },
    )
    try:
        case_runtime.record_finding(
            finding_id,
            case_id,
            "Effect mismatch detected",
            severity=FindingSeverity.HIGH,
            description="Observed effects did not satisfy the effect plan.",
            evidence_ids=(evidence_id,),
            remediation="Review the effect plan, observed receipts, and compensation path.",
        )
    except RuntimeCoreInvariantError as exc:
        if "Duplicate finding_id" not in str(exc):
            raise
    return case_id
