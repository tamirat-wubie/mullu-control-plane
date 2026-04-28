"""Purpose: default GateRunner implementations for the autonomy loop.
Governance scope: each runner is a thin wrapper that turns a CodeEngine
result (TestResult / BuildResult) or a raw run_command outcome into a
typed QualityGateResult, so plug-and-play gates exist without callers
having to write their own per-test-runner glue.

Runners returned by these factories satisfy the GateRunner protocol from
software_dev_loop. The factories take the CodeEngine plus per-gate
command tuples and return runners that ignore `request` and `attempt` —
gate evidence is keyed by the engine's stable_identifier so retries
get distinct evidence_ids automatically.
"""
from __future__ import annotations

from typing import Callable

from mcoi_runtime.adapters.code_adapter import LocalCodeAdapter
from mcoi_runtime.contracts.code import BuildResult, TestResult
from mcoi_runtime.contracts.software_dev_loop import QualityGateResult
from mcoi_runtime.core.code import CodeEngine
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
)


# Public type alias matching software_dev_loop.GateRunner shape.
GateRunner = Callable[[LocalCodeAdapter, SoftwareRequest, int], QualityGateResult]


_TAIL_BYTES: int = 1024


def _tail(text: str | None) -> str:
    if not text:
        return ""
    return text[-_TAIL_BYTES:]


def _summarize_test_result(result: TestResult) -> str:
    return (
        f"{result.passed} passed, {result.failed} failed, "
        f"{result.errors} errors, exit={result.exit_code}"
    )


def _summarize_build_result(result: BuildResult) -> str:
    return f"build {result.status.value}, exit={result.exit_code}"


def _wrap_test_runner(
    engine: CodeEngine,
    *,
    gate: SoftwareQualityGate,
    command: tuple[str, ...],
    timeout_seconds: int,
) -> GateRunner:
    """Wrap CodeEngine.run_tests as a GateRunner."""

    def runner(
        adapter: LocalCodeAdapter, request: SoftwareRequest, attempt: int,
    ) -> QualityGateResult:
        result: TestResult = engine.run_tests(
            list(command), timeout_seconds=timeout_seconds,
        )
        return QualityGateResult(
            gate=gate.value,
            passed=result.all_passed,
            evidence_id=result.test_id,
            summary=_summarize_test_result(result),
            exit_code=result.exit_code,
            metadata={
                "command": " ".join(command),
                "duration_ms": result.duration_ms,
                "passed": result.passed,
                "failed": result.failed,
                "errors": result.errors,
                "stdout_tail": _tail(result.stdout),
                "stderr_tail": _tail(result.stderr),
                "attempt": attempt,
            },
        )

    return runner


def _wrap_build_runner(
    engine: CodeEngine,
    *,
    gate: SoftwareQualityGate,
    command: tuple[str, ...],
    timeout_seconds: int,
) -> GateRunner:
    """Wrap CodeEngine.run_build as a GateRunner."""

    def runner(
        adapter: LocalCodeAdapter, request: SoftwareRequest, attempt: int,
    ) -> QualityGateResult:
        result: BuildResult = engine.run_build(
            list(command), timeout_seconds=timeout_seconds,
        )
        return QualityGateResult(
            gate=gate.value,
            passed=result.succeeded,
            evidence_id=result.build_id,
            summary=_summarize_build_result(result),
            exit_code=result.exit_code,
            metadata={
                "command": " ".join(command),
                "duration_ms": result.duration_ms,
                "stdout_tail": _tail(result.stdout),
                "stderr_tail": _tail(result.stderr),
                "attempt": attempt,
            },
        )

    return runner


def _wrap_command_runner(
    engine: CodeEngine,
    *,
    gate: SoftwareQualityGate,
    command: tuple[str, ...],
    timeout_seconds: int,
    label: str,
) -> GateRunner:
    """Wrap a raw run_command call as a GateRunner.

    Used for gates whose semantics are simply "exit code 0 = pass" and where
    the test/build typed runners would be misleading (lint, typecheck,
    security scan).
    """

    def runner(
        adapter: LocalCodeAdapter, request: SoftwareRequest, attempt: int,
    ) -> QualityGateResult:
        command_id = f"{label}-{gate.value}-attempt-{attempt}"
        exit_code, stdout, stderr, duration_ms = adapter.run_command(
            command_id, list(command), timeout_seconds=timeout_seconds,
        )
        return QualityGateResult(
            gate=gate.value,
            passed=exit_code == 0,
            evidence_id=command_id,
            summary=f"{label} exit={exit_code}",
            exit_code=exit_code,
            metadata={
                "command": " ".join(command),
                "duration_ms": duration_ms,
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
                "attempt": attempt,
            },
        )

    return runner


def make_default_gate_runners(
    *,
    engine: CodeEngine,
    unit_test_command: tuple[str, ...] | None = ("pytest", "-q"),
    integration_test_command: tuple[str, ...] | None = None,
    lint_command: tuple[str, ...] | None = ("ruff", "check", "."),
    typecheck_command: tuple[str, ...] | None = ("mypy", "."),
    security_scan_command: tuple[str, ...] | None = None,
    build_command: tuple[str, ...] | None = None,
    unit_test_timeout: int = 300,
    integration_test_timeout: int = 600,
    lint_timeout: int = 60,
    typecheck_timeout: int = 120,
    security_scan_timeout: int = 300,
    build_timeout: int = 600,
) -> dict[SoftwareQualityGate, GateRunner]:
    """Construct the standard library of GateRunners for an engine.

    Pass `None` for any command to omit that gate's runner — the loop will
    record a missing-runner failure for any quality gate the request asks
    for that doesn't have a runner here. Pass an explicit tuple to override
    the default command. Returned runners are stateless callables; the
    engine they capture is the only mutable handle.
    """
    runners: dict[SoftwareQualityGate, GateRunner] = {}

    if unit_test_command:
        runners[SoftwareQualityGate.UNIT_TESTS] = _wrap_test_runner(
            engine,
            gate=SoftwareQualityGate.UNIT_TESTS,
            command=unit_test_command,
            timeout_seconds=unit_test_timeout,
        )
    if integration_test_command:
        runners[SoftwareQualityGate.INTEGRATION_TESTS] = _wrap_test_runner(
            engine,
            gate=SoftwareQualityGate.INTEGRATION_TESTS,
            command=integration_test_command,
            timeout_seconds=integration_test_timeout,
        )
    if lint_command:
        runners[SoftwareQualityGate.LINT] = _wrap_command_runner(
            engine,
            gate=SoftwareQualityGate.LINT,
            command=lint_command,
            timeout_seconds=lint_timeout,
            label="lint",
        )
    if typecheck_command:
        runners[SoftwareQualityGate.TYPECHECK] = _wrap_command_runner(
            engine,
            gate=SoftwareQualityGate.TYPECHECK,
            command=typecheck_command,
            timeout_seconds=typecheck_timeout,
            label="typecheck",
        )
    if security_scan_command:
        runners[SoftwareQualityGate.SECURITY_SCAN] = _wrap_command_runner(
            engine,
            gate=SoftwareQualityGate.SECURITY_SCAN,
            command=security_scan_command,
            timeout_seconds=security_scan_timeout,
            label="security_scan",
        )
    if build_command:
        runners[SoftwareQualityGate.BUILD] = _wrap_build_runner(
            engine,
            gate=SoftwareQualityGate.BUILD,
            command=build_command,
            timeout_seconds=build_timeout,
        )

    return runners
