"""Tests for the sequential software-dev autonomy loop.

Uses deterministic fakes for plan generation, patch generation, and gate
execution so the loop's state machine is the only thing under test. UCJA
is also injected so the gate can be controlled per-test.

Coverage:
  - Happy path: plan + patch + gates all pass → COMMITTED, evidence
    references plan/patch/gate IDs.
  - Self-debug: gate fails attempt 0, generator produces a different
    patch on attempt 1, gates pass → COMMITTED, file holds attempt-1
    content (rollback restored attempt-0 changes).
  - Exhaust + rollback: every attempt fails → COMPENSATED, file restored
    to original content.
  - Rollback failure → REQUIRES_REVIEW.
  - UCJA reject → REQUIRES_REVIEW with case_id pointing at job_id.
  - Plan target outside affected_files → REQUIRES_REVIEW.
  - Patch target outside plan.target_files → attempt rejected.
  - Patch fails to apply (malformed diff) → attempt apply_failed.
  - Mode short-circuits: PLAN_ONLY, DRY_RUN, PATCH_ONLY.
  - Missing gate runner → gate fails closed (no crash).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mcoi_runtime.adapters.code_adapter import (
    CommandPolicy,
    LocalCodeAdapter,
)
from mcoi_runtime.contracts.code import (
    PatchApplicationResult,
    PatchProposal,
    PatchStatus,
)
from mcoi_runtime.contracts.software_dev_loop import (
    AttemptStatus,
    QualityGateResult,
    WorkPlan,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.software_dev_loop import (
    UCJAOutcomeShape,
    governed_software_change,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkKind,
    SoftwareWorkMode,
)


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T10:00:05+00:00"


def _clock_factory():
    times = iter((T0, T1, T1, T1, T1, T1, T1, T1, T1, T1))
    return lambda: next(times)


def _setup_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (ws / "lib.py").write_text("VERSION = '1'\n", encoding="utf-8")
    return ws


def _adapter(ws: Path) -> LocalCodeAdapter:
    return LocalCodeAdapter(
        root_path=str(ws),
        clock=lambda: T0,
        command_policy=CommandPolicy.permissive_for_testing(),
    )


def _accept_ucja(payload: dict[str, Any]) -> UCJAOutcomeShape:
    return UCJAOutcomeShape(
        accepted=True, rejected=False,
        job_id="job-test-accept",
        halted_at_layer=None, reason="",
    )


def _reject_ucja(payload: dict[str, Any]) -> UCJAOutcomeShape:
    return UCJAOutcomeShape(
        accepted=False, rejected=True,
        job_id="job-test-reject",
        halted_at_layer="L0_purpose",
        reason="purpose statement empty",
    )


def _request(**overrides) -> SoftwareRequest:
    base = dict(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="rename hello to greet",
        repository="r-test",
        affected_files=("main.py",),
        acceptance_criteria=("function renamed",),
        quality_gates=(SoftwareQualityGate.UNIT_TESTS,),
        max_self_debug_iterations=1,
    )
    base.update(overrides)
    return SoftwareRequest(**base)


def _basic_plan(target_files=("main.py",)) -> WorkPlan:
    return WorkPlan(
        plan_id="plan-1",
        summary="rename hello",
        steps=("rewrite function definition",),
        target_files=target_files,
    )


def _basic_patch(*, body: str = "greet") -> PatchProposal:
    """Build a patch that renames hello → <body>."""
    diff = (
        "--- a/main.py\n"
        "+++ b/main.py\n"
        "@@ -1,2 +1,2 @@\n"
        f"-def hello():\n"
        f"+def {body}():\n"
        "     return 'world'\n"
    )
    return PatchProposal(
        patch_id=f"patch-{body}",
        target_file="main.py",
        description="rename function",
        unified_diff=diff,
    )


def _passing_gate(gate: SoftwareQualityGate):
    def runner(adapter, request, attempt):
        return QualityGateResult(
            gate=gate.value, passed=True,
            evidence_id=f"gate-{gate.value}-attempt-{attempt}",
            summary="ok",
        )
    return runner


def _failing_gate(gate: SoftwareQualityGate):
    def runner(adapter, request, attempt):
        return QualityGateResult(
            gate=gate.value, passed=False,
            evidence_id=f"gate-{gate.value}-attempt-{attempt}",
            summary="failed",
            exit_code=1,
        )
    return runner


# ---- Happy path ----


class TestHappyPath:
    def test_committed_when_plan_patch_and_gates_pass(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request()

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(),
            gate_runners={
                SoftwareQualityGate.UNIT_TESTS: _passing_gate(SoftwareQualityGate.UNIT_TESTS),
            },
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED
        assert outcome.evidence.ucja_accepted is True
        assert len(outcome.evidence.attempts) == 1
        assert outcome.evidence.attempts[0].status is AttemptStatus.GATES_PASSED
        # File reflects the patch
        assert "def greet():" in adapter.read_file("main.py")
        # Evidence refs include plan + patch + gate
        ref_text = " ".join(outcome.certificate.evidence_refs)
        assert "plan:plan-1" in ref_text
        assert "patch:patch-greet" in ref_text
        assert "gate:unit_tests" in ref_text


# ---- Self-debug retry ----


class TestSelfDebug:
    def test_first_attempt_fails_second_passes_yields_committed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(max_self_debug_iterations=2)

        # First attempt produces "greet"; second produces "salute"
        bodies = iter(("greet", "salute"))
        gate_calls = {"n": 0}

        def patch_gen(req, snap, plan, attempt, prior_failures):
            return _basic_patch(body=next(bodies))

        def gate_first_fail_then_pass(adapter, request, attempt):
            gate_calls["n"] += 1
            passed = attempt > 0
            return QualityGateResult(
                gate="unit_tests",
                passed=passed,
                evidence_id=f"gate-attempt-{attempt}",
                summary="ok" if passed else "boom",
                exit_code=0 if passed else 1,
            )

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=patch_gen,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: gate_first_fail_then_pass},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED
        assert len(outcome.evidence.attempts) == 2
        assert outcome.evidence.attempts[0].status is AttemptStatus.GATES_FAILED
        assert outcome.evidence.attempts[0].rolled_back is True
        assert outcome.evidence.attempts[1].status is AttemptStatus.GATES_PASSED
        # File reflects the SECOND patch (salute), proving the rollback of
        # attempt 0 occurred before attempt 1 applied
        assert "def salute():" in adapter.read_file("main.py")
        assert "def greet():" not in adapter.read_file("main.py")


# ---- Exhaust + rollback ----


class TestExhaustAndRollback:
    def test_all_attempts_fail_yields_compensated_and_restores_file(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        original = (ws / "main.py").read_text(encoding="utf-8")
        adapter = _adapter(ws)
        request = _request(max_self_debug_iterations=1)

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(
                body=f"variant{attempt}",
            ),
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _failing_gate(SoftwareQualityGate.UNIT_TESTS)},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.COMPENSATED
        assert outcome.certificate.compensation_outcome_id is not None
        assert outcome.evidence.rollback_succeeded is True
        assert len(outcome.evidence.attempts) == 2
        for attempt in outcome.evidence.attempts:
            assert attempt.status is AttemptStatus.GATES_FAILED
        # File is restored exactly
        assert adapter.read_file("main.py") == original


# ---- Rollback failure ----


class TestRollbackFailure:
    def test_rollback_failure_yields_requires_review(self, tmp_path: Path, monkeypatch):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(max_self_debug_iterations=0)

        # Force the final restore to fail by making write_file return False
        original_write = adapter.write_file
        call_count = {"n": 0}

        def flaky_write(self_or_path, *args, **kwargs):
            # First write_file call is the per-attempt rollback; let it pass.
            # Second is the final initial-snapshot rollback; fail it.
            call_count["n"] += 1
            if call_count["n"] >= 2:
                return False
            return original_write(self_or_path, *args, **kwargs)

        monkeypatch.setattr(adapter, "write_file", lambda *a, **kw: flaky_write(*a, **kw))

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(),
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _failing_gate(SoftwareQualityGate.UNIT_TESTS)},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.REQUIRES_REVIEW
        assert outcome.certificate.case_id is not None
        assert outcome.certificate.case_id.startswith("rollback-failed-")
        assert outcome.evidence.rollback_succeeded is False


# ---- UCJA rejection ----


class TestUCJARejection:
    def test_ucja_reject_yields_requires_review_with_job_id_in_case(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request()

        # plan/patch/gate runners must not be invoked when UCJA rejects
        sentinels = {"plan_called": 0, "patch_called": 0, "gate_called": 0}

        def plan_gen(req, snap):
            sentinels["plan_called"] += 1
            return _basic_plan()

        def patch_gen(req, snap, plan, attempt, prior):
            sentinels["patch_called"] += 1
            return _basic_patch()

        def gate(*a, **kw):
            sentinels["gate_called"] += 1
            return QualityGateResult(gate="unit_tests", passed=True, evidence_id="x", summary="x")

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=plan_gen,
            patch_generator=patch_gen,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: gate},
            clock=_clock_factory(),
            ucja_runner=_reject_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.REQUIRES_REVIEW
        assert outcome.certificate.case_id == "ucja-reject-job-test-reject"
        assert outcome.evidence.ucja_accepted is False
        assert outcome.evidence.ucja_halted_at_layer == "L0_purpose"
        assert sentinels == {"plan_called": 0, "patch_called": 0, "gate_called": 0}


# ---- Plan validation ----


class TestPlanValidation:
    def test_plan_targeting_files_outside_affected_yields_requires_review(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(affected_files=("main.py",))

        plan_outside = WorkPlan(
            plan_id="plan-bad",
            summary="touches lib.py too",
            steps=("rewrite",),
            target_files=("main.py", "lib.py"),
        )

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: plan_outside,
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(),
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate(SoftwareQualityGate.UNIT_TESTS)},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.REQUIRES_REVIEW
        assert outcome.certificate.case_id.startswith("plan-invalid-")

    def test_empty_affected_files_means_no_plan_bound(self, tmp_path: Path):
        """If the request declares no affected_files, plan can target anything."""
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(affected_files=())

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(target_files=("main.py",)),
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(),
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate(SoftwareQualityGate.UNIT_TESTS)},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED


# ---- Patch validation ----


class TestPatchValidation:
    def test_patch_target_outside_plan_is_rejected(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(max_self_debug_iterations=0)
        plan = _basic_plan(target_files=("main.py",))

        # Patch targets lib.py, which is NOT in plan.target_files
        bad_patch = PatchProposal(
            patch_id="patch-bad-target",
            target_file="lib.py",
            description="x",
            unified_diff=(
                "--- a/lib.py\n+++ b/lib.py\n@@ -1 +1 @@\n-VERSION = '1'\n+VERSION = '2'\n"
            ),
        )

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: plan,
            patch_generator=lambda req, snap, plan, attempt, prior: bad_patch,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate(SoftwareQualityGate.UNIT_TESTS)},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        # No attempt actually applied, no gate ran, exhausted → COMPENSATED
        # (rollback of an unchanged workspace should succeed)
        assert outcome.certificate.disposition is TerminalClosureDisposition.COMPENSATED
        assert all(a.status is AttemptStatus.PATCH_REJECTED for a in outcome.evidence.attempts)
        # lib.py is unchanged
        assert "VERSION = '1'" in adapter.read_file("lib.py")

    def test_malformed_patch_recorded_as_apply_failed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(max_self_debug_iterations=0)

        malformed_patch = PatchProposal(
            patch_id="patch-malformed",
            target_file="main.py",
            description="x",
            unified_diff="garbage diff",
        )

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=lambda req, snap, plan, attempt, prior: malformed_patch,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate(SoftwareQualityGate.UNIT_TESTS)},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.evidence.attempts[0].status is AttemptStatus.APPLY_FAILED
        assert outcome.evidence.attempts[0].patch_result is not None
        assert outcome.evidence.attempts[0].patch_result.status is PatchStatus.MALFORMED


# ---- Mode short-circuits ----


class TestModeShortCircuits:
    def test_plan_only_returns_committed_after_plan(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(mode=SoftwareWorkMode.PLAN_ONLY)

        sentinels = {"patch": 0, "gate": 0}

        def patch_gen(req, snap, plan, attempt, prior):
            sentinels["patch"] += 1
            return _basic_patch()

        def gate(*a, **kw):
            sentinels["gate"] += 1
            return QualityGateResult(gate="unit_tests", passed=True, evidence_id="x", summary="x")

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=patch_gen,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: gate},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED
        assert sentinels == {"patch": 0, "gate": 0}
        # File NOT modified
        assert "def hello():" in adapter.read_file("main.py")

    def test_dry_run_generates_patch_but_does_not_apply(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(mode=SoftwareWorkMode.DRY_RUN)

        sentinels = {"gate": 0}

        def gate(*a, **kw):
            sentinels["gate"] += 1
            return QualityGateResult(gate="unit_tests", passed=True, evidence_id="x", summary="x")

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(),
            gate_runners={SoftwareQualityGate.UNIT_TESTS: gate},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED
        assert sentinels == {"gate": 0}
        # File NOT modified (dry run never applied)
        assert "def hello():" in adapter.read_file("main.py")
        # But evidence shows the patch was generated
        ref_text = " ".join(outcome.certificate.evidence_refs)
        assert "patch:patch-greet" in ref_text
        assert "dry_run:true" in ref_text

    def test_patch_only_applies_but_does_not_run_gates(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(mode=SoftwareWorkMode.PATCH_ONLY)

        gate_was_run = {"called": False}

        def gate(*a, **kw):
            gate_was_run["called"] = True
            return QualityGateResult(gate="unit_tests", passed=True, evidence_id="x", summary="x")

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(),
            gate_runners={SoftwareQualityGate.UNIT_TESTS: gate},
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED
        assert gate_was_run["called"] is False
        # File IS modified (patch was applied)
        assert "def greet():" in adapter.read_file("main.py")


# ---- Missing gate runner ----


class TestMissingGateRunner:
    def test_missing_runner_fails_closed_without_crashing(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        request = _request(
            quality_gates=(
                SoftwareQualityGate.UNIT_TESTS,
                SoftwareQualityGate.LINT,  # no runner provided
            ),
            max_self_debug_iterations=0,
        )

        outcome = governed_software_change(
            request,
            adapter=adapter,
            plan_generator=lambda req, snap: _basic_plan(),
            patch_generator=lambda req, snap, plan, attempt, prior: _basic_patch(),
            gate_runners={
                SoftwareQualityGate.UNIT_TESTS: _passing_gate(SoftwareQualityGate.UNIT_TESTS),
                # SoftwareQualityGate.LINT intentionally absent
            },
            clock=_clock_factory(),
            ucja_runner=_accept_ucja,
        )

        # Lint gate has no runner, so it fails → exhaust → COMPENSATED
        assert outcome.certificate.disposition is TerminalClosureDisposition.COMPENSATED
        attempt = outcome.evidence.attempts[0]
        gate_results = attempt.gate_results
        lint = next(g for g in gate_results if g.gate == "lint")
        assert lint.passed is False
        assert "no runner registered" in lint.summary
