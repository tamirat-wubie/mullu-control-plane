"""Tests for Phase 195A -- DispatchGuard and coverage gate.

Purpose: validate guard recording, counts, ratio, report, legacy callers,
         empty state, mixed usage, and golden lifecycle.
Governance scope: execution path migration enforcement verification.
Dependencies: dispatch_guard.
Invariants: 8 tests, all deterministic.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.core.dispatch_guard import DispatchGuard, DispatchAuditEntry


class TestDispatchGuardEmpty:
    """Empty-state behaviour."""

    def test_empty_total_is_zero(self) -> None:
        guard = DispatchGuard()
        assert guard.total_dispatches == 0

    def test_empty_governed_ratio_is_one(self) -> None:
        """An unused guard reports 100% governed (vacuous truth)."""
        guard = DispatchGuard()
        assert guard.governed_ratio == 1.0


class TestDispatchGuardRecording:
    """Core recording and counting."""

    def test_record_governed_dispatch(self) -> None:
        guard = DispatchGuard()
        guard.record_governed_dispatch("operator_loop", "shell")
        assert guard.total_dispatches == 1
        assert guard.governed_count == 1
        assert guard.legacy_count == 0

    def test_record_legacy_dispatch(self) -> None:
        guard = DispatchGuard()
        guard.record_legacy_dispatch("bootstrap", "shell")
        assert guard.total_dispatches == 1
        assert guard.governed_count == 0
        assert guard.legacy_count == 1

    def test_governed_ratio_mixed(self) -> None:
        guard = DispatchGuard()
        guard.record_governed_dispatch("a", "shell")
        guard.record_governed_dispatch("b", "shell")
        guard.record_legacy_dispatch("c", "shell")
        assert guard.governed_ratio == pytest.approx(2 / 3)

    def test_legacy_callers_deduplication(self) -> None:
        guard = DispatchGuard()
        guard.record_legacy_dispatch("bootstrap", "shell")
        guard.record_legacy_dispatch("bootstrap", "api")
        guard.record_legacy_dispatch("operator_loop", "shell")
        callers = guard.legacy_callers()
        assert sorted(callers) == ["bootstrap", "operator_loop"]


class TestDispatchGuardReport:
    """Coverage report structure."""

    def test_coverage_report_keys(self) -> None:
        guard = DispatchGuard()
        guard.record_governed_dispatch("x", "shell")
        report = guard.coverage_report()
        assert set(report.keys()) == {"total", "governed", "legacy", "ratio", "legacy_callers"}
        assert report["total"] == 1
        assert report["governed"] == 1
        assert report["legacy"] == 0
        assert report["ratio"] == 1.0
        assert report["legacy_callers"] == []


class TestDispatchGuardGoldenLifecycle:
    """Full lifecycle: governed, legacy, report, verify."""

    def test_golden_lifecycle(self) -> None:
        guard = DispatchGuard()

        # Phase 1: governed dispatches only
        guard.record_governed_dispatch("governed_dispatcher", "shell")
        guard.record_governed_dispatch("governed_dispatcher", "api")
        assert guard.governed_ratio == 1.0

        # Phase 2: legacy path appears
        guard.record_legacy_dispatch("operator_loop", "shell")
        assert guard.governed_ratio == pytest.approx(2 / 3)
        assert guard.legacy_callers() == ["operator_loop"]

        # Phase 3: more governed dispatches shift ratio back
        guard.record_governed_dispatch("governed_dispatcher", "shell")
        guard.record_governed_dispatch("governed_dispatcher", "api")
        assert guard.governed_ratio == pytest.approx(4 / 5)

        # Phase 4: report reflects final state
        report = guard.coverage_report()
        assert report["total"] == 5
        assert report["governed"] == 4
        assert report["legacy"] == 1
        assert report["ratio"] == 0.8
        assert report["legacy_callers"] == ["operator_loop"]
