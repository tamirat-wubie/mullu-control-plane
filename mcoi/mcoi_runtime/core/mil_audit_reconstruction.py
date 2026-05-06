"""Purpose: reconstruct replayable audit chains from admitted MIL terminal memory.
Governance scope: audit-only reconstruction from certified artifacts; no live adapter calls and no effect replay.
Dependencies: trace and replay contracts, WHQR documents, MIL terminal certificate bundles, and learning admission results.
Invariants: reconstruction requires admitted episodic memory and preserves parent-child causality across WHQR, policy, MIL, dispatch, certificate, and learning nodes.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.replay import ReplayEffect, ReplayMode, ReplayRecord
from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.contracts.whqr import WHQRDocument
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory import MemoryTier
from mcoi_runtime.core.mil_learning_admission import MILLearningAdmissionResult
from mcoi_runtime.core.mil_terminal_certificate import MILTerminalCertificateBundle


@dataclass(frozen=True, slots=True)
class MILAuditReconstruction:
    trace_entries: tuple[TraceEntry, ...]
    replay_record: ReplayRecord
    chain_hash: str


def reconstruct_mil_audit(
    bundle: MILTerminalCertificateBundle,
    admission: MILLearningAdmissionResult,
    *,
    whqr_document: WHQRDocument | None = None,
    recorded_at: str,
    state_hash: str = "mil-state",
    registry_hash: str = "mil-registry",
) -> MILAuditReconstruction:
    if admission.decision.status is not LearningAdmissionStatus.ADMIT or admission.memory_entry is None:
        raise RuntimeCoreInvariantError("MIL audit reconstruction requires admitted learning memory")
    if admission.memory_entry.tier is not MemoryTier.EPISODIC:
        raise RuntimeCoreInvariantError("MIL audit reconstruction requires episodic memory")
    if bundle.certificate.certificate_id not in admission.memory_entry.source_ids:
        raise RuntimeCoreInvariantError("MIL audit memory does not anchor terminal certificate")

    entries = _trace_entries(bundle, admission, whqr_document, recorded_at, state_hash, registry_hash)
    chain_hash = stable_identifier(
        "mil-audit-chain",
        {
            "trace_ids": tuple(entry.trace_id for entry in entries),
            "memory_entry_id": admission.memory_entry.entry_id,
        },
    )
    replay = ReplayRecord(
        replay_id=stable_identifier("mil-audit-replay", {"chain_hash": chain_hash}),
        trace_id=entries[-1].trace_id,
        source_hash=chain_hash,
        approved_effects=(
            ReplayEffect(
                bundle.certificate.certificate_id,
                "terminal certificate retained",
                {"memory_entry_id": admission.memory_entry.entry_id},
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at=recorded_at,
        metadata={
            "program_id": bundle.program.program_id,
            "certificate_id": bundle.certificate.certificate_id,
            "admission_id": admission.decision.admission_id,
        },
    )
    return MILAuditReconstruction(entries, replay, chain_hash)


def _trace_entries(
    bundle: MILTerminalCertificateBundle,
    admission: MILLearningAdmissionResult,
    whqr_document: WHQRDocument | None,
    recorded_at: str,
    state_hash: str,
    registry_hash: str,
) -> tuple[TraceEntry, ...]:
    subject = bundle.program.whqr_decision.subject_id
    goal = bundle.program.goal_id
    parent = None
    rows = []
    specs = (
        (
            "whqr_semantic_tree",
            whqr_document.canonical_hash() if whqr_document else bundle.program.whqr_decision.decision_id,
            {"whqr_version": whqr_document.whqr_version if whqr_document else None},
        ),
        (
            "policy_decision",
            bundle.program.whqr_decision.decision_id,
            {"status": bundle.program.whqr_decision.status.value},
        ),
        ("mil_program", bundle.program.program_id, {"instruction_count": len(bundle.program.instructions)}),
        (
            "dispatch_execution",
            bundle.execution_result.execution_id,
            {"execution_status": bundle.execution_result.status.value},
        ),
        (
            "terminal_certificate",
            bundle.certificate.certificate_id,
            {"disposition": bundle.certificate.disposition.value},
        ),
        (
            "learning_admission",
            admission.decision.admission_id,
            {"status": admission.decision.status.value, "memory_entry_id": admission.memory_entry.entry_id},
        ),
    )
    for event_type, anchor, metadata in specs:
        trace_id = stable_identifier(
            "mil-audit-trace",
            {"event_type": event_type, "anchor": anchor, "parent": parent},
        )
        rows.append(
            TraceEntry(
                trace_id,
                parent,
                event_type,
                subject,
                goal,
                state_hash,
                registry_hash,
                recorded_at,
                metadata={"anchor": anchor, **{key: value for key, value in metadata.items() if value is not None}},
            )
        )
        parent = trace_id
    return tuple(rows)
