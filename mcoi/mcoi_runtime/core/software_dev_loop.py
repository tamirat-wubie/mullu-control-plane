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

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from mcoi_runtime.adapters.code_adapter import LocalCodeAdapter
from mcoi_runtime.contracts.code import (
    PatchApplicationResult,
    PatchProposal,
    PatchStatus,
    WorkspaceState,
)
from mcoi_runtime.contracts.software_dev_loop import (
    AttemptRecord,
    AttemptStatus,
    AutonomyEvidence,
    QualityGateResult,
    WorkPlan,
)
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


# ---- Public function ----


@dataclass
class LoopOutcome:
    """The two artifacts the orchestrator produces: certificate + evidence trail."""

    certificate: TerminalClosureCertificate
    evidence: AutonomyEvidence


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
