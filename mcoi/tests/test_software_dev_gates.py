"""Tests for default gate runner factories.

Verifies the runners returned by make_default_gate_runners produce
correctly typed QualityGateResult records, surface stdout/stderr tails,
and read pass/fail directly from the underlying CodeEngine result.

Tests monkeypatch subprocess.run via the code_adapter module so no real
test/build/lint commands execute — the focus here is the wrapping layer.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from mcoi_runtime.adapters.code_adapter import CommandPolicy, LocalCodeAdapter
from mcoi_runtime.contracts.software_dev_loop import QualityGateResult
from mcoi_runtime.core.code import CodeEngine
from mcoi_runtime.core.software_dev_gates import (
    SoftwareDevRunnerConfig,
    make_default_gate_runners,
    make_default_software_dev_runner,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkKind,
)


T0 = "2025-01-15T10:00:00+00:00"


def _adapter(tmp_path: Path) -> LocalCodeAdapter:
    ws = tmp_path / "ws"
    ws.mkdir()
    return LocalCodeAdapter(
        root_path=str(ws),
        clock=lambda: T0,
        command_policy=CommandPolicy.permissive_for_testing(),
    )


def _engine(adapter: LocalCodeAdapter) -> CodeEngine:
    return CodeEngine(adapter=adapter, clock=lambda: T0)


def _request() -> SoftwareRequest:
    return SoftwareRequest(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="x",
        repository="r",
    )


def _stub_subprocess(monkeypatch, *, stdout: str, stderr: str, returncode: int):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(
        "mcoi_runtime.adapters.code_adapter.subprocess.run", fake_run,
    )


# ---- Unit tests gate ----


class TestUnitTestGate:
    def test_pass_when_engine_reports_all_passed(self, tmp_path, monkeypatch):
        _stub_subprocess(
            monkeypatch,
            stdout="===== 5 passed in 0.1s =====",
            stderr="",
            returncode=0,
        )
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(engine=engine)

        result = runners[SoftwareQualityGate.UNIT_TESTS](adapter, _request(), 0)

        assert isinstance(result, QualityGateResult)
        assert result.passed is True
        assert result.gate == "unit_tests"
        assert result.exit_code == 0
        assert result.metadata["passed"] == 5

    def test_fail_when_exit_code_nonzero(self, tmp_path, monkeypatch):
        _stub_subprocess(
            monkeypatch,
            stdout="1 failed, 2 passed in 0.1s",
            stderr="",
            returncode=1,
        )
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(engine=engine)

        result = runners[SoftwareQualityGate.UNIT_TESTS](adapter, _request(), 0)

        assert result.passed is False
        assert result.metadata["failed"] == 1
        assert result.metadata["passed"] == 2

    def test_command_can_be_overridden(self, tmp_path, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_run(*args, **kwargs):
            captured["argv"] = args[0]
            return subprocess.CompletedProcess(args[0], 0, stdout="0 passed", stderr="")

        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run", fake_run,
        )
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(
            engine=engine,
            unit_test_command=("pytest", "tests/unit", "-q", "-x"),
        )

        runners[SoftwareQualityGate.UNIT_TESTS](adapter, _request(), 0)

        assert captured["argv"] == ["pytest", "tests/unit", "-q", "-x"]


# ---- Integration tests gate ----


class TestIntegrationTestGate:
    def test_only_present_when_command_provided(self, tmp_path, monkeypatch):
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(
            engine=engine,
            integration_test_command=None,
        )
        assert SoftwareQualityGate.INTEGRATION_TESTS not in runners

        runners_with = make_default_gate_runners(
            engine=engine,
            integration_test_command=("pytest", "tests/integration"),
        )
        assert SoftwareQualityGate.INTEGRATION_TESTS in runners_with


# ---- Lint gate ----


class TestLintGate:
    def test_lint_pass_on_zero_exit(self, tmp_path, monkeypatch):
        _stub_subprocess(monkeypatch, stdout="", stderr="", returncode=0)
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(engine=engine)

        result = runners[SoftwareQualityGate.LINT](adapter, _request(), 0)

        assert result.passed is True
        assert result.gate == "lint"
        assert result.exit_code == 0

    def test_lint_fail_on_nonzero_exit(self, tmp_path, monkeypatch):
        _stub_subprocess(
            monkeypatch,
            stdout="src/foo.py:3:1: E501 line too long\n",
            stderr="",
            returncode=1,
        )
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(engine=engine)

        result = runners[SoftwareQualityGate.LINT](adapter, _request(), 0)

        assert result.passed is False
        assert "E501" in result.metadata["stdout_tail"]


# ---- Typecheck gate ----


class TestTypecheckGate:
    def test_default_command_is_mypy_dot(self, tmp_path, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_run(*args, **kwargs):
            captured["argv"] = args[0]
            return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run", fake_run,
        )
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(engine=engine)

        runners[SoftwareQualityGate.TYPECHECK](adapter, _request(), 0)

        assert captured["argv"] == ["mypy", "."]


# ---- Build gate ----


class TestBuildGate:
    def test_only_present_when_command_provided(self, tmp_path):
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(engine=engine, build_command=None)
        assert SoftwareQualityGate.BUILD not in runners

        runners_with = make_default_gate_runners(
            engine=engine, build_command=("make", "build"),
        )
        assert SoftwareQualityGate.BUILD in runners_with

    def test_build_runner_uses_engine_run_build(self, tmp_path, monkeypatch):
        _stub_subprocess(monkeypatch, stdout="ok", stderr="", returncode=0)
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(
            engine=engine, build_command=("make",),
        )

        result = runners[SoftwareQualityGate.BUILD](adapter, _request(), 0)

        assert result.passed is True
        assert result.summary.startswith("build succeeded")


# ---- Disable specific gates by passing None ----


class TestDisablingGates:
    def test_unit_test_command_none_omits_unit_tests(self, tmp_path):
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(
            engine=engine, unit_test_command=None,
        )
        assert SoftwareQualityGate.UNIT_TESTS not in runners

    def test_lint_command_none_omits_lint(self, tmp_path):
        adapter = _adapter(tmp_path)
        engine = _engine(adapter)
        runners = make_default_gate_runners(
            engine=engine, lint_command=None,
        )
        assert SoftwareQualityGate.LINT not in runners


# ---- Default runner factory ----


class TestDefaultSoftwareDevRunnerFactory:
    """make_default_software_dev_runner bundles adapter + gate runners +
    UCJA into one SoftwareDevRunnerConfig the operator can pass straight
    to MulluMCPServer or governed_software_change.
    """

    def _plan_gen(self, req, snap):
        from mcoi_runtime.contracts.software_dev_loop import WorkPlan
        return WorkPlan(
            plan_id="p", summary="s", steps=("a",), target_files=("x.py",),
        )

    def _patch_gen(self, req, snap, plan, attempt, prior):
        from mcoi_runtime.contracts.code import PatchProposal
        return PatchProposal(
            patch_id="pp", target_file="x.py", description="d",
            unified_diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n",
        )

    def test_factory_returns_runner_config_with_default_gates(self, tmp_path):
        adapter = _adapter(tmp_path)
        config = make_default_software_dev_runner(
            adapter=adapter,
            plan_generator=self._plan_gen,
            patch_generator=self._patch_gen,
            clock=lambda: T0,
        )
        assert isinstance(config, SoftwareDevRunnerConfig)
        assert SoftwareQualityGate.UNIT_TESTS in config.gate_runners
        assert SoftwareQualityGate.LINT in config.gate_runners
        assert SoftwareQualityGate.TYPECHECK in config.gate_runners
        # Off by default
        assert SoftwareQualityGate.INTEGRATION_TESTS not in config.gate_runners
        assert SoftwareQualityGate.BUILD not in config.gate_runners

    def test_factory_threads_ucja_runner(self, tmp_path):
        adapter = _adapter(tmp_path)
        sentinel = object()
        config = make_default_software_dev_runner(
            adapter=adapter,
            plan_generator=self._plan_gen,
            patch_generator=self._patch_gen,
            clock=lambda: T0,
            ucja_runner=sentinel,
        )
        assert config.ucja_runner is sentinel

    def test_factory_disables_specific_gates_via_none(self, tmp_path):
        adapter = _adapter(tmp_path)
        config = make_default_software_dev_runner(
            adapter=adapter,
            plan_generator=self._plan_gen,
            patch_generator=self._patch_gen,
            clock=lambda: T0,
            unit_test_command=None,
            lint_command=None,
        )
        assert SoftwareQualityGate.UNIT_TESTS not in config.gate_runners
        assert SoftwareQualityGate.LINT not in config.gate_runners
        # Typecheck still on by default
        assert SoftwareQualityGate.TYPECHECK in config.gate_runners

    def test_runner_can_drive_governed_software_change_directly(self, tmp_path, monkeypatch):
        """Smoke test: the bundled config plugs straight into the loop."""
        from mcoi_runtime.core.software_dev_loop import (
            UCJAOutcomeShape,
            governed_software_change,
        )
        adapter = _adapter(tmp_path)
        # Set up a real workspace file so the patch can apply
        (adapter.root / "x.py").write_text("old\n", encoding="utf-8")

        # Stub subprocess so the gate command "succeeds" without a real pytest
        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout="1 passed", stderr=""),
        )

        config = make_default_software_dev_runner(
            adapter=adapter,
            plan_generator=self._plan_gen,
            patch_generator=self._patch_gen,
            clock=lambda: T0,
            ucja_runner=lambda payload: UCJAOutcomeShape(
                accepted=True, rejected=False, job_id="j",
                halted_at_layer=None, reason="",
            ),
            # Disable lint+typecheck so we don't need ruff/mypy installed
            lint_command=None,
            typecheck_command=None,
        )

        from mcoi_runtime.domain_adapters.software_dev import (
            SoftwareRequest, SoftwareWorkKind,
        )
        req = SoftwareRequest(
            kind=SoftwareWorkKind.BUG_FIX,
            summary="x", repository="r",
            affected_files=("x.py",),
            quality_gates=(SoftwareQualityGate.UNIT_TESTS,),
            max_self_debug_iterations=0,
        )
        outcome = governed_software_change(
            req,
            adapter=config.adapter,
            plan_generator=config.plan_generator,
            patch_generator=config.patch_generator,
            gate_runners=config.gate_runners,
            clock=config.clock,
            ucja_runner=config.ucja_runner,
        )
        assert outcome.solved is True
