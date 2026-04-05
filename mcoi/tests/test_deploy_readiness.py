"""Tests for Phase 230A — Deployment Readiness Checker."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.deploy_readiness import (
    DeployReadinessChecker, CheckResult, CheckStatus,
)


class TestDeployReadinessChecker:
    def test_all_pass(self):
        checker = DeployReadinessChecker()
        checker.register_check("db", lambda: CheckResult("db", CheckStatus.PASS))
        checker.register_check("config", lambda: CheckResult("config", CheckStatus.PASS))
        report = checker.run_all()
        assert report.ready
        assert len(report.checks) == 2

    def test_fail_blocks_deploy(self):
        checker = DeployReadinessChecker()
        checker.register_check("ok", lambda: CheckResult("ok", CheckStatus.PASS))
        checker.register_check("broken", lambda: CheckResult("broken", CheckStatus.FAIL, "DB down"))
        report = checker.run_all()
        assert not report.ready

    def test_warn_allows_deploy(self):
        checker = DeployReadinessChecker()
        checker.register_check("warn", lambda: CheckResult("warn", CheckStatus.WARN, "Slow"))
        report = checker.run_all()
        assert report.ready

    def test_skip_allows_deploy(self):
        checker = DeployReadinessChecker()
        checker.register_check("skip", lambda: CheckResult("skip", CheckStatus.SKIP))
        report = checker.run_all()
        assert report.ready

    def test_exception_in_check(self):
        def bad_check():
            raise RuntimeError("boom")
        checker = DeployReadinessChecker()
        checker.register_check("bad", bad_check)
        report = checker.run_all()
        assert not report.ready
        assert report.checks[0].message == "check raised exception (RuntimeError)"

    def test_report_to_dict(self):
        checker = DeployReadinessChecker()
        checker.register_check("ok", lambda: CheckResult("ok", CheckStatus.PASS))
        report = checker.run_all()
        d = report.to_dict()
        assert d["ready"] is True
        assert d["passed"] == 1

    def test_summary(self):
        checker = DeployReadinessChecker()
        checker.register_check("c1", lambda: CheckResult("c1", CheckStatus.PASS))
        checker.run_all()
        s = checker.summary()
        assert s["registered_checks"] == 1
        assert s["total_runs"] == 1

    def test_empty_checker(self):
        checker = DeployReadinessChecker()
        report = checker.run_all()
        assert report.ready  # no checks = ready
