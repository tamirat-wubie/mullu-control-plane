"""Purpose: sequential autonomy loop for software_dev domain.
Governance scope: orchestration of UCJA gate, workspace snapshot, plan
generation, patch generation, patch application, quality gate execution,
self-debug retry, rollback, and terminal certificate emission.

Sequential, not multi-agent. The loop accepts injected callables for
plan generation, patch generation, and per-gate execution, so the
runtime is deterministic and testable without an LLM. Production wires
these callables to model invocations.

Invariants:
  - Every accepted request produces exactly one TerminalClosureCertificate.
  - UCJA rejection and plan-out-of-blast-radius both yield REQUIRES_REVIEW.
  - All-gates-pass yields COMMITTED.
  - Self-debug exhaustion with successful rollback yields COMPENSATED.
  - Self-debug exhaustion with rollback failure yields REQUIRES_REVIEW.
  - PLAN_ONLY mode terminates after plan validation; DRY_RUN after the
    first patch generates without applying.
  - Per-attempt snapshot of every plan target file is captured before
    apply, so a failing attempt can be undone independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from mcoi_runtime.adapters.code_adapter import LocalCodeAdapter
from mcoi_runtime.contracts.code import (
    PatchProposal,
    PatchStatus,
    WorkspaceState,
)
from mcoi_runtime.contracts.software_dev_loop import (
    AttemptRecord,
    AttemptStatus,
    AutonomyEvidence,
    QualityGateResult,
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
    WorkPlan,
)
from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.contracts.terminal_closure import (
    TerminalClosureCertificate,
    TerminalClosureDisposition,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkMode,
    _request_to_ucja_payload,
)


# ---- Injection protocols ----


class PlanGenerator(Protocol):
    def __call__(
        self, request: SoftwareRequest, snapshot: WorkspaceState,
    ) -> WorkPlan: ...


class PatchGenerator(Protocol):
    def __call__(
        self,
        request: SoftwareRequest,
        snapshot: WorkspaceState,
        plan: WorkPlan,
        attempt: int,
        prior_failures: tuple[QualityGateResult, ...],
    ) -> PatchProposal: ...


class GateRunner(Protocol):
    def __call__(
        self,
        adapter: LocalCodeAdapter,
        request: SoftwareRequest,
        attempt: int,
    ) -> QualityGateResult: ...


# ---- Errors that the loop converts to certificates ----


class _LoopAbort(Exception):
    """Internal: raised by helpers to short-circuit the loop with a typed reason."""

    def __init__(self, reason: str, *, layer: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.layer = layer


# ---- Solver outcome ----


class SolverOutcome(StrEnum):
    """Loop-level typed disposition.

    Mirrors TerminalClosureDisposition but with verbs that read as a
    solver answer (did the work get done?). Always derivable from the
    certificate; surfaced separately so callers don't have to parse the
    certificate to decide whether to retry, escalate, or move on.
    """

    SOLVED = "solved"
    SOLVED_WITH_COMPENSATION = "solved_with_compensation"
    REQUIRES_REVIEW = "requires_review"


def _outcome_from_disposition(
    disposition: TerminalClosureDisposition,
) -> SolverOutcome:
    if disposition is TerminalClosureDisposition.COMMITTED:
        return SolverOutcome.SOLVED
    if disposition is TerminalClosureDisposition.COMPENSATED:
        return SolverOutcome.SOLVED_WITH_COMPENSATION
    return SolverOutcome.REQUIRES_REVIEW


# ---- Public function ----


@dataclass
class LoopOutcome:
    """The artifacts the orchestrator produces.

    `outcome` is the typed solver answer; `certificate` is the typed
    governance record (TerminalClosureCertificate); `evidence` is the
    full structured trail of every step.
    """

    certificate: TerminalClosureCertificate
    evidence: AutonomyEvidence

    @property
    def outcome(self) -> SolverOutcome:
        return _outcome_from_disposition(self.certificate.disposition)

    @property
    def solved(self) -> bool:
        return self.outcome in (
            SolverOutcome.SOLVED,
            SolverOutcome.SOLVED_WITH_COMPENSATION,
        )

    @property
    def receipts(self) -> tuple[SoftwareChangeReceipt, ...]:
        """Return ordered lifecycle receipts derived from evidence.

        Receipts are computed from the immutable certificate/evidence pair,
        so older callers keep the same LoopOutcome contract while newer
        callers can inspect a typed causal chain for every transition.
        """
        return _receipts_from_outcome(self.certificate, self.evidence)


def governed_software_change(
    request: SoftwareRequest,
    *,
    adapter: LocalCodeAdapter,
    plan_generator: PlanGenerator,
    patch_generator: PatchGenerator,
    gate_runners: Mapping[SoftwareQualityGate, GateRunner],
    clock: Callable[[], str],
    ucja_runner: Callable[[dict[str, Any]], "UCJAOutcomeShape"] | None = None,
) -> LoopOutcome:
    """Run the bounded sequential autonomy loop.

    Steps:
      1. UCJA gate (rejected → REQUIRES_REVIEW).
      2. Workspace snapshot (captures content of every file in the request's
         affected_files set, even if missing — recorded as None).
      3. Plan generation + plan blast-radius validation.
      4. For each attempt up to req.max_self_debug_iterations:
           a. Per-attempt snapshot of files the plan targets.
           b. Patch generation. Validate target_file ∈ plan.target_files.
           c. apply_patch. If non-APPLIED → roll back this attempt → next.
           d. Run each requested quality gate via the supplied runner.
              All passed → COMMITTED. Any failed → roll back → next.
      5. Exhausted: roll back to the initial snapshot (every affected file
         restored to original content; created files removed). COMPENSATED
         if rollback succeeds, REQUIRES_REVIEW otherwise.

    Mode short-circuits:
      - PLAN_ONLY: exits after step 3 with COMMITTED if plan is valid.
      - DRY_RUN:    exits after one patch generation + diff parse with
                    COMMITTED. No apply, no gates, no rollback.
      - PATCH_ONLY: applies one patch and returns COMMITTED if it applies,
                    skipping gates entirely.
      - PATCH_AND_TEST / PATCH_TEST_REVIEW / COMMIT_CANDIDATE: full loop.

    Returns LoopOutcome carrying both the typed certificate and the full
    AutonomyEvidence trail (every attempt, gate result, and rollback).
    """
    started_at = clock()
    request_id = f"req-{uuid4().hex[:12]}"
    attempts: list[AttemptRecord] = []
    rollback_succeeded: bool | None = None
    rollback_evidence_id: str | None = None
    review_record_id: str | None = None
    plan_id_for_evidence: str | None = None

    # ---- 1. UCJA gate ----
    ucja_outcome = _run_ucja(request, ucja_runner)
    if not ucja_outcome.accepted:
        completed_at = clock()
        evidence = AutonomyEvidence(
            request_id=request_id,
            ucja_job_id=ucja_outcome.job_id,
            ucja_accepted=False,
            ucja_halted_at_layer=ucja_outcome.halted_at_layer,
            ucja_reason=ucja_outcome.reason,
            initial_snapshot_id="snap-skipped-no-ucja",
            plan_id=None,
            attempts=tuple(),
            review_record_id=None,
            rollback_succeeded=None,
            rollback_evidence_id=None,
            started_at=started_at,
            completed_at=completed_at,
        )
        return LoopOutcome(
            certificate=_certificate_requires_review(
                request_id=request_id,
                completed_at=completed_at,
                case_id=f"ucja-reject-{ucja_outcome.job_id}",
                evidence_refs=(
                    f"ucja:{ucja_outcome.job_id}",
                    f"ucja-reason:{ucja_outcome.reason or 'no-reason'}",
                ),
            ),
            evidence=evidence,
        )

    # ---- 2. Initial workspace snapshot ----
    initial_snapshot_id = f"snap-init-{uuid4().hex[:12]}"
    initial_state = _capture_files(adapter, request.affected_files)

    # ---- 3. Plan generation + blast-radius validation ----
    plan_id_for_evidence = None
    try:
        snapshot_state = adapter.list_files(request.repository or request_id)
        plan = plan_generator(request, snapshot_state)
        plan_id_for_evidence = plan.plan_id
        _validate_plan_within_blast_radius(plan, request)
    except _LoopAbort as abort:
        return _abort_with_review(
            request_id=request_id,
            ucja_outcome=ucja_outcome,
            initial_snapshot_id=initial_snapshot_id,
            plan_id=plan_id_for_evidence,
            attempts=attempts,
            reason=abort.reason,
            layer=abort.layer,
            started_at=started_at,
            completed_at=clock(),
            case_id=f"plan-invalid-{request_id}",
        )
    except (ValueError, TypeError):
        # Bounded reason — exception type stays out of the audit-grade
        # contract field. v4.43.0 (audit governance contract guard).
        return _abort_with_review(
            request_id=request_id,
            ucja_outcome=ucja_outcome,
            initial_snapshot_id=initial_snapshot_id,
            plan_id=plan_id_for_evidence,
            attempts=attempts,
            reason="plan generation error",
            layer="plan",
            started_at=started_at,
            completed_at=clock(),
            case_id=f"plan-error-{request_id}",
        )

    # PLAN_ONLY short-circuit ----
    if request.mode is SoftwareWorkMode.PLAN_ONLY:
        completed_at = clock()
        return LoopOutcome(
            certificate=_certificate_committed(
                request_id=request_id,
                completed_at=completed_at,
                evidence_refs=(f"plan:{plan.plan_id}", f"snapshot:{initial_snapshot_id}"),
            ),
            evidence=AutonomyEvidence(
                request_id=request_id,
                ucja_job_id=ucja_outcome.job_id,
                ucja_accepted=True,
                ucja_halted_at_layer=None,
                ucja_reason="",
                initial_snapshot_id=initial_snapshot_id,
                plan_id=plan.plan_id,
                attempts=tuple(),
                review_record_id=None,
                rollback_succeeded=None,
                rollback_evidence_id=None,
                started_at=started_at,
                completed_at=completed_at,
            ),
        )

    # ---- 4. Self-debug attempt loop ----
    prior_failures: tuple[QualityGateResult, ...] = ()
    max_attempts = request.max_self_debug_iterations + 1

    for attempt_index in range(max_attempts):
        attempt_snapshot_id = f"snap-att-{attempt_index}-{uuid4().hex[:8]}"
        attempt_pre_state = _capture_files(adapter, plan.target_files)

        # 4b. Patch generation
        try:
            patch = patch_generator(request, snapshot_state, plan, attempt_index, prior_failures)
        except (ValueError, TypeError) as exc:
            attempts.append(_failed_attempt(
                attempt_index, attempt_snapshot_id, "patch-gen-error",
                AttemptStatus.PATCH_REJECTED,
                notes=f"patch generator raised {type(exc).__name__}",
            ))
            continue

        if not isinstance(patch, PatchProposal):
            attempts.append(_failed_attempt(
                attempt_index, attempt_snapshot_id, "patch-bad-type",
                AttemptStatus.PATCH_REJECTED,
                notes="patch generator did not return a PatchProposal",
            ))
            continue

        if patch.target_file not in plan.target_files:
            attempts.append(_failed_attempt(
                attempt_index, attempt_snapshot_id, patch.patch_id,
                AttemptStatus.PATCH_REJECTED,
                notes=f"patch target {patch.target_file!r} not in plan.target_files",
            ))
            continue

        # DRY_RUN short-circuit: parse the diff via apply_patch on a
        # disposable copy? Simpler: don't apply. We trust the parser to
        # reject malformed diffs at the next step; for DRY_RUN we just
        # surface the proposed patch and exit.
        if request.mode is SoftwareWorkMode.DRY_RUN:
            attempts.append(AttemptRecord(
                attempt_index=attempt_index,
                snapshot_id=attempt_snapshot_id,
                patch_id=patch.patch_id,
                status=AttemptStatus.GATES_PASSED,  # treat dry-run as success-shape
                patch_result=None,
                gate_results=tuple(),
                rolled_back=False,
                notes="dry_run: patch proposed, not applied",
            ))
            completed_at = clock()
            return LoopOutcome(
                certificate=_certificate_committed(
                    request_id=request_id,
                    completed_at=completed_at,
                    evidence_refs=(
                        f"plan:{plan.plan_id}",
                        f"patch:{patch.patch_id}",
                        f"snapshot:{initial_snapshot_id}",
                        "dry_run:true",
                    ),
                ),
                evidence=_evidence(
                    request_id, ucja_outcome, initial_snapshot_id,
                    plan.plan_id, attempts, None, None, None,
                    started_at, completed_at,
                ),
            )

        # 4c. Apply patch
        patch_result = adapter.apply_patch(patch.patch_id, patch.target_file, patch.unified_diff)
        if patch_result.status is not PatchStatus.APPLIED:
            attempts.append(AttemptRecord(
                attempt_index=attempt_index,
                snapshot_id=attempt_snapshot_id,
                patch_id=patch.patch_id,
                status=AttemptStatus.APPLY_FAILED,
                patch_result=patch_result,
                gate_results=tuple(),
                rolled_back=False,
                notes=patch_result.error_message or "apply failed",
            ))
            continue

        # PATCH_ONLY short-circuit: applied, no gates
        if request.mode is SoftwareWorkMode.PATCH_ONLY:
            attempts.append(AttemptRecord(
                attempt_index=attempt_index,
                snapshot_id=attempt_snapshot_id,
                patch_id=patch.patch_id,
                status=AttemptStatus.GATES_PASSED,
                patch_result=patch_result,
                gate_results=tuple(),
                rolled_back=False,
                notes="patch_only: applied without running gates",
            ))
            completed_at = clock()
            return LoopOutcome(
                certificate=_certificate_committed(
                    request_id=request_id,
                    completed_at=completed_at,
                    evidence_refs=(
                        f"plan:{plan.plan_id}",
                        f"patch:{patch.patch_id}",
                        f"patch-status:{patch_result.status.value}",
                    ),
                ),
                evidence=_evidence(
                    request_id, ucja_outcome, initial_snapshot_id,
                    plan.plan_id, attempts, None, None, None,
                    started_at, completed_at,
                ),
            )

        # 4d. Run each requested quality gate
        gate_results = _run_quality_gates(
            adapter, request, attempt_index, gate_runners,
        )

        if all(g.passed for g in gate_results):
            attempts.append(AttemptRecord(
                attempt_index=attempt_index,
                snapshot_id=attempt_snapshot_id,
                patch_id=patch.patch_id,
                status=AttemptStatus.GATES_PASSED,
                patch_result=patch_result,
                gate_results=gate_results,
                rolled_back=False,
            ))
            review_record_id = (
                f"review-{request_id}" if request.reviewer_required else None
            )
            completed_at = clock()
            evidence_refs = (
                f"plan:{plan.plan_id}",
                f"patch:{patch.patch_id}",
                f"patch-status:{patch_result.status.value}",
            ) + tuple(f"gate:{g.gate}:{g.evidence_id}" for g in gate_results)
            if review_record_id:
                evidence_refs = evidence_refs + (f"review:{review_record_id}",)
            return LoopOutcome(
                certificate=_certificate_committed(
                    request_id=request_id,
                    completed_at=completed_at,
                    evidence_refs=evidence_refs,
                ),
                evidence=_evidence(
                    request_id, ucja_outcome, initial_snapshot_id,
                    plan.plan_id, attempts, review_record_id, None, None,
                    started_at, completed_at,
                ),
            )

        # Gate failed — roll back this attempt before the next
        rollback_ok = _restore_files(adapter, attempt_pre_state)
        attempts.append(AttemptRecord(
            attempt_index=attempt_index,
            snapshot_id=attempt_snapshot_id,
            patch_id=patch.patch_id,
            status=AttemptStatus.GATES_FAILED,
            patch_result=patch_result,
            gate_results=gate_results,
            rolled_back=rollback_ok,
            notes="; ".join(g.summary for g in gate_results if not g.passed) or "gates failed",
        ))
        prior_failures = gate_results

    # ---- 5. Exhausted ----
    completed_at = clock()
    rollback_succeeded = _restore_files(adapter, initial_state)
    rollback_evidence_id = f"rollback-{initial_snapshot_id}"

    if rollback_succeeded:
        return LoopOutcome(
            certificate=_certificate_compensated(
                request_id=request_id,
                completed_at=completed_at,
                evidence_refs=(
                    f"plan:{plan.plan_id}",
                    f"snapshot:{initial_snapshot_id}",
                    rollback_evidence_id,
                    f"attempts:{len(attempts)}",
                ),
                compensation_outcome_id=rollback_evidence_id,
            ),
            evidence=_evidence(
                request_id, ucja_outcome, initial_snapshot_id,
                plan.plan_id, attempts, None,
                rollback_succeeded, rollback_evidence_id,
                started_at, completed_at,
            ),
        )

    return LoopOutcome(
        certificate=_certificate_requires_review(
            request_id=request_id,
            completed_at=completed_at,
            case_id=f"rollback-failed-{initial_snapshot_id}",
            evidence_refs=(
                f"plan:{plan.plan_id}",
                f"snapshot:{initial_snapshot_id}",
                rollback_evidence_id,
                f"attempts:{len(attempts)}",
            ),
        ),
        evidence=_evidence(
            request_id, ucja_outcome, initial_snapshot_id,
            plan.plan_id, attempts, None,
            False, rollback_evidence_id,
            started_at, completed_at,
        ),
    )


# ---- UCJA wrapper ----


@dataclass(frozen=True, slots=True)
class UCJAOutcomeShape:
    """Compatibility shape for UCJA outcomes — what the loop actually needs."""

    accepted: bool
    rejected: bool
    job_id: str
    halted_at_layer: str | None
    reason: str


def _run_ucja(
    request: SoftwareRequest,
    ucja_runner: Callable[[dict[str, Any]], UCJAOutcomeShape] | None,
) -> UCJAOutcomeShape:
    """Run UCJA via the injected runner, or fall back to the live pipeline."""
    payload = _request_to_ucja_payload(request)
    if ucja_runner is not None:
        return ucja_runner(payload)
    # Live UCJA path
    from mcoi_runtime.ucja import UCJAPipeline
    outcome = UCJAPipeline().run(payload)
    return UCJAOutcomeShape(
        accepted=outcome.accepted,
        rejected=outcome.rejected,
        job_id=str(outcome.draft.job_id),
        halted_at_layer=outcome.halted_at_layer,
        reason=outcome.reason,
    )


# ---- Plan validation ----


def _validate_plan_within_blast_radius(plan: WorkPlan, request: SoftwareRequest) -> None:
    """Raise _LoopAbort if plan.target_files escape request.affected_files.

    blast_radius is currently advisory; the enforced bound is the explicit
    affected_files list. Plans that touch files outside that list must
    re-route through a wider request.
    """
    if not request.affected_files:
        # Empty affected_files = no enforced bound at this layer (UCJA already
        # accepted the request). Allow.
        return
    declared = set(request.affected_files)
    actual = set(plan.target_files)
    extra = actual - declared
    if extra:
        # Bounded reason — file names stay out of the audit-grade
        # contract field. The full set is recoverable from the plan
        # record in the audit trail. v4.43.0 (audit governance
        # contract guard).
        raise _LoopAbort(
            reason="plan targets files outside affected_files",
            layer="plan",
        )


# ---- Workspace state capture & restore ----


def _capture_files(adapter: LocalCodeAdapter, paths: tuple[str, ...]) -> dict[str, str | None]:
    """Read each path's current content; record None if absent."""
    state: dict[str, str | None] = {}
    for relative_path in paths:
        state[relative_path] = adapter.read_file(relative_path)
    return state


def _restore_files(adapter: LocalCodeAdapter, state: dict[str, str | None]) -> bool:
    """Restore each path to its captured content; return False on any failure.

    For files captured as None (absent at snapshot time), delete the path
    if it currently exists.
    """
    all_ok = True
    for relative_path, original in state.items():
        if original is None:
            target = adapter.root / relative_path
            try:
                if target.is_file():
                    target.unlink()
            except OSError:
                all_ok = False
            continue
        if not adapter.write_file(relative_path, original):
            all_ok = False
    return all_ok


# ---- Quality gate execution ----


def _run_quality_gates(
    adapter: LocalCodeAdapter,
    request: SoftwareRequest,
    attempt: int,
    runners: Mapping[SoftwareQualityGate, GateRunner],
) -> tuple[QualityGateResult, ...]:
    results: list[QualityGateResult] = []
    for gate in request.quality_gates:
        runner = runners.get(gate)
        if runner is None:
            results.append(QualityGateResult(
                gate=gate.value,
                passed=False,
                evidence_id=f"missing-runner-{gate.value}",
                summary=f"no runner registered for gate {gate.value}",
                exit_code=-1,
            ))
            continue
        try:
            result = runner(adapter, request, attempt)
        except (ValueError, TypeError, OSError) as exc:
            results.append(QualityGateResult(
                gate=gate.value,
                passed=False,
                evidence_id=f"runner-error-{gate.value}",
                summary=f"runner raised {type(exc).__name__}: {exc}",
                exit_code=-1,
            ))
            continue
        if not isinstance(result, QualityGateResult):
            results.append(QualityGateResult(
                gate=gate.value,
                passed=False,
                evidence_id=f"runner-bad-return-{gate.value}",
                summary="runner did not return a QualityGateResult",
                exit_code=-1,
            ))
            continue
        results.append(result)
    return tuple(results)


# ---- Failed-attempt helper ----


def _failed_attempt(
    index: int, snapshot_id: str, patch_id: str,
    status: AttemptStatus, *, notes: str,
) -> AttemptRecord:
    return AttemptRecord(
        attempt_index=index,
        snapshot_id=snapshot_id,
        patch_id=patch_id,
        status=status,
        patch_result=None,
        gate_results=tuple(),
        rolled_back=False,
        notes=notes,
    )


def _abort_with_review(
    *,
    request_id: str,
    ucja_outcome: UCJAOutcomeShape,
    initial_snapshot_id: str,
    plan_id: str | None,
    attempts: list[AttemptRecord],
    reason: str,
    layer: str | None,
    started_at: str,
    completed_at: str,
    case_id: str,
) -> LoopOutcome:
    return LoopOutcome(
        certificate=_certificate_requires_review(
            request_id=request_id,
            completed_at=completed_at,
            case_id=case_id,
            evidence_refs=(
                f"reason:{reason}",
                f"layer:{layer or 'unspecified'}",
                f"snapshot:{initial_snapshot_id}",
            ),
        ),
        evidence=_evidence(
            request_id, ucja_outcome, initial_snapshot_id,
            plan_id, attempts, None, None, None,
            started_at, completed_at,
        ),
    )


def _evidence(
    request_id: str,
    ucja_outcome: UCJAOutcomeShape,
    initial_snapshot_id: str,
    plan_id: str | None,
    attempts: list[AttemptRecord],
    review_record_id: str | None,
    rollback_succeeded: bool | None,
    rollback_evidence_id: str | None,
    started_at: str,
    completed_at: str,
) -> AutonomyEvidence:
    return AutonomyEvidence(
        request_id=request_id,
        ucja_job_id=ucja_outcome.job_id,
        ucja_accepted=ucja_outcome.accepted,
        ucja_halted_at_layer=ucja_outcome.halted_at_layer,
        ucja_reason=ucja_outcome.reason,
        initial_snapshot_id=initial_snapshot_id,
        plan_id=plan_id,
        attempts=tuple(attempts),
        review_record_id=review_record_id,
        rollback_succeeded=rollback_succeeded,
        rollback_evidence_id=rollback_evidence_id,
        started_at=started_at,
        completed_at=completed_at,
    )


# ---- Software-change receipts ----


def _receipt_id(
    *,
    request_id: str,
    stage: SoftwareChangeReceiptStage,
    target_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    outcome: str,
) -> str:
    return stable_identifier(
        "software-receipt",
        {
            "request_id": request_id,
            "stage": stage.value,
            "target_refs": target_refs,
            "evidence_refs": evidence_refs,
            "outcome": outcome,
        },
    )


def _software_receipt(
    *,
    request_id: str,
    stage: SoftwareChangeReceiptStage,
    cause: str,
    outcome: str,
    target_refs: tuple[str, ...],
    constraint_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    created_at: str,
    metadata: Mapping[str, Any] | None = None,
) -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id=_receipt_id(
            request_id=request_id,
            stage=stage,
            target_refs=target_refs,
            evidence_refs=evidence_refs,
            outcome=outcome,
        ),
        request_id=request_id,
        stage=stage,
        cause=cause,
        outcome=outcome,
        target_refs=target_refs,
        constraint_refs=constraint_refs,
        evidence_refs=evidence_refs,
        created_at=created_at,
        metadata=metadata or {},
    )


def _receipts_from_outcome(
    certificate: TerminalClosureCertificate,
    evidence: AutonomyEvidence,
) -> tuple[SoftwareChangeReceipt, ...]:
    receipts: list[SoftwareChangeReceipt] = []
    request_ref = f"request:{evidence.request_id}"
    certificate_ref = f"certificate:{certificate.certificate_id}"
    lifecycle_constraint = "constraint:software_change_lifecycle_v1"

    receipts.append(_software_receipt(
        request_id=evidence.request_id,
        stage=SoftwareChangeReceiptStage.REQUEST_ADMITTED,
        cause="software change request entered governed loop",
        outcome="accepted_for_governance",
        target_refs=(request_ref,),
        constraint_refs=(lifecycle_constraint,),
        evidence_refs=(f"request:{evidence.request_id}",),
        created_at=evidence.started_at,
        metadata={"ucja_job_id": evidence.ucja_job_id},
    ))
    receipts.append(_software_receipt(
        request_id=evidence.request_id,
        stage=SoftwareChangeReceiptStage.UCJA_EVALUATED,
        cause="UCJA gate evaluated request ontology and constraints",
        outcome="accepted" if evidence.ucja_accepted else "rejected",
        target_refs=(request_ref,),
        constraint_refs=(lifecycle_constraint, "constraint:ucja_admission"),
        evidence_refs=(f"ucja:{evidence.ucja_job_id}",),
        created_at=evidence.started_at,
        metadata={
            "halted_at_layer": evidence.ucja_halted_at_layer,
            "reason": evidence.ucja_reason,
        },
    ))

    if evidence.ucja_accepted:
        receipts.append(_software_receipt(
            request_id=evidence.request_id,
            stage=SoftwareChangeReceiptStage.SNAPSHOT_CAPTURED,
            cause="workspace state captured before mutation",
            outcome="captured",
            target_refs=(f"snapshot:{evidence.initial_snapshot_id}",),
            constraint_refs=(lifecycle_constraint, "constraint:rollback_preimage"),
            evidence_refs=(f"snapshot:{evidence.initial_snapshot_id}",),
            created_at=evidence.started_at,
        ))

    if evidence.plan_id:
        receipts.append(_software_receipt(
            request_id=evidence.request_id,
            stage=SoftwareChangeReceiptStage.PLAN_VALIDATED,
            cause="plan generated before patch execution",
            outcome="validated",
            target_refs=(f"plan:{evidence.plan_id}",),
            constraint_refs=(lifecycle_constraint, "constraint:plan_before_patch"),
            evidence_refs=(f"plan:{evidence.plan_id}",),
            created_at=evidence.started_at,
        ))
    else:
        receipts.append(_software_receipt(
            request_id=evidence.request_id,
            stage=SoftwareChangeReceiptStage.PLAN_UNAVAILABLE,
            cause="loop terminated before a valid plan was available",
            outcome=certificate.disposition.value,
            target_refs=(request_ref,),
            constraint_refs=(lifecycle_constraint, "constraint:plan_before_patch"),
            evidence_refs=(certificate_ref,),
            created_at=evidence.completed_at,
        ))

    for attempt in evidence.attempts:
        patch_ref = f"patch:{attempt.patch_id}"
        snapshot_ref = f"snapshot:{attempt.snapshot_id}"
        if attempt.status is AttemptStatus.PATCH_REJECTED:
            receipts.append(_software_receipt(
                request_id=evidence.request_id,
                stage=SoftwareChangeReceiptStage.PATCH_REJECTED,
                cause="patch failed pre-apply validation",
                outcome=attempt.status.value,
                target_refs=(patch_ref,),
                constraint_refs=(lifecycle_constraint, "constraint:patch_within_plan"),
                evidence_refs=(snapshot_ref, patch_ref),
                created_at=evidence.completed_at,
                metadata={"attempt_index": attempt.attempt_index, "notes": attempt.notes},
            ))
            continue
        if attempt.status is AttemptStatus.APPLY_FAILED:
            receipts.append(_software_receipt(
                request_id=evidence.request_id,
                stage=SoftwareChangeReceiptStage.PATCH_APPLY_FAILED,
                cause="patch adapter rejected or failed unified diff application",
                outcome=attempt.status.value,
                target_refs=(patch_ref,),
                constraint_refs=(lifecycle_constraint, "constraint:bounded_patch_apply"),
                evidence_refs=(snapshot_ref, patch_ref),
                created_at=evidence.completed_at,
                metadata={"attempt_index": attempt.attempt_index, "notes": attempt.notes},
            ))
            continue

        receipts.append(_software_receipt(
            request_id=evidence.request_id,
            stage=SoftwareChangeReceiptStage.PATCH_APPLIED,
            cause="patch applied inside declared plan boundary",
            outcome=attempt.status.value,
            target_refs=(patch_ref,),
            constraint_refs=(lifecycle_constraint, "constraint:bounded_patch_apply"),
            evidence_refs=(snapshot_ref, patch_ref),
            created_at=evidence.completed_at,
            metadata={
                "attempt_index": attempt.attempt_index,
                "rolled_back": attempt.rolled_back,
            },
        ))
        for gate_result in attempt.gate_results:
            receipts.append(_software_receipt(
                request_id=evidence.request_id,
                stage=SoftwareChangeReceiptStage.GATE_EVALUATED,
                cause="quality gate evaluated applied patch",
                outcome="passed" if gate_result.passed else "failed",
                target_refs=(f"gate:{gate_result.gate}",),
                constraint_refs=(lifecycle_constraint, "constraint:verification_gate"),
                evidence_refs=(f"gate:{gate_result.gate}:{gate_result.evidence_id}",),
                created_at=evidence.completed_at,
                metadata={
                    "attempt_index": attempt.attempt_index,
                    "exit_code": gate_result.exit_code,
                    "summary": gate_result.summary,
                },
            ))

    if evidence.rollback_evidence_id is not None:
        receipts.append(_software_receipt(
            request_id=evidence.request_id,
            stage=SoftwareChangeReceiptStage.ROLLBACK_COMPLETED,
            cause="rollback restored captured workspace preimage",
            outcome="succeeded" if evidence.rollback_succeeded else "failed",
            target_refs=(f"rollback:{evidence.rollback_evidence_id}",),
            constraint_refs=(lifecycle_constraint, "constraint:rollback_preimage"),
            evidence_refs=(evidence.rollback_evidence_id,),
            created_at=evidence.completed_at,
        ))

    if (
        evidence.review_record_id is not None
        or certificate.disposition is TerminalClosureDisposition.REQUIRES_REVIEW
    ):
        review_ref = (
            f"review:{evidence.review_record_id}"
            if evidence.review_record_id
            else f"case:{certificate.case_id or certificate.certificate_id}"
        )
        receipts.append(_software_receipt(
            request_id=evidence.request_id,
            stage=SoftwareChangeReceiptStage.REVIEW_REQUIRED,
            cause="human or operator review is required by governance outcome",
            outcome=certificate.disposition.value,
            target_refs=(review_ref,),
            constraint_refs=(lifecycle_constraint, "constraint:review_escalation"),
            evidence_refs=(certificate_ref,),
            created_at=evidence.completed_at,
        ))

    receipts.append(_software_receipt(
        request_id=evidence.request_id,
        stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
        cause="terminal closure certificate issued",
        outcome=certificate.disposition.value,
        target_refs=(certificate_ref,),
        constraint_refs=(lifecycle_constraint, "constraint:terminal_closure"),
        evidence_refs=tuple(certificate.evidence_refs) or (certificate_ref,),
        created_at=evidence.completed_at,
        metadata={
            "certificate_id": certificate.certificate_id,
            "case_id": certificate.case_id,
            "compensation_outcome_id": certificate.compensation_outcome_id,
        },
    ))
    return tuple(receipts)


# ---- Certificate factories ----


def _certificate_committed(
    *, request_id: str, completed_at: str, evidence_refs: tuple[str, ...],
) -> TerminalClosureCertificate:
    cert_id = f"cert-{uuid4().hex[:12]}"
    return TerminalClosureCertificate(
        certificate_id=cert_id,
        command_id=request_id,
        execution_id=f"exec-{request_id}",
        disposition=TerminalClosureDisposition.COMMITTED,
        verification_result_id=f"verify-{request_id}",
        effect_reconciliation_id=f"reconcile-{request_id}",
        evidence_refs=evidence_refs,
        closed_at=completed_at,
    )


def _certificate_compensated(
    *, request_id: str, completed_at: str,
    evidence_refs: tuple[str, ...], compensation_outcome_id: str,
) -> TerminalClosureCertificate:
    cert_id = f"cert-{uuid4().hex[:12]}"
    return TerminalClosureCertificate(
        certificate_id=cert_id,
        command_id=request_id,
        execution_id=f"exec-{request_id}",
        disposition=TerminalClosureDisposition.COMPENSATED,
        verification_result_id=f"verify-{request_id}",
        effect_reconciliation_id=f"reconcile-{request_id}",
        evidence_refs=evidence_refs,
        closed_at=completed_at,
        compensation_outcome_id=compensation_outcome_id,
    )


def _certificate_requires_review(
    *, request_id: str, completed_at: str, case_id: str,
    evidence_refs: tuple[str, ...],
) -> TerminalClosureCertificate:
    cert_id = f"cert-{uuid4().hex[:12]}"
    return TerminalClosureCertificate(
        certificate_id=cert_id,
        command_id=request_id,
        execution_id=f"exec-{request_id}",
        disposition=TerminalClosureDisposition.REQUIRES_REVIEW,
        verification_result_id=f"verify-{request_id}",
        effect_reconciliation_id=f"reconcile-{request_id}",
        evidence_refs=evidence_refs,
        closed_at=completed_at,
        case_id=case_id,
    )
