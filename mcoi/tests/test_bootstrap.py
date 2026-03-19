"""Purpose: verify side-effect-free operator-loop bootstrap wiring.
Governance scope: operator-loop tests only.
Dependencies: the local app bootstrap module and execution-slice adapters.
Invariants: bootstrap wires components and adapters explicitly without executing commands or observing the machine.
"""

from __future__ import annotations

from mcoi_runtime.adapters.filesystem_observer import FilesystemObserver
from mcoi_runtime.adapters.process_observer import ProcessObserver
from mcoi_runtime.adapters.shell_executor import ShellExecutor
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.core.verification_engine import VerificationEngine


def test_bootstrap_runtime_returns_wired_components_without_side_effects() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(),
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )

    assert runtime.dispatcher.template_validator is runtime.template_validator
    assert runtime.runtime_kernel.registry_store is runtime.registry_store
    assert runtime.verification_engine.__class__ is VerificationEngine
    assert runtime.executors["shell_command"].__class__ is ShellExecutor
    assert runtime.observers["filesystem"].__class__ is FilesystemObserver
    assert runtime.observers["process"].__class__ is ProcessObserver


def test_bootstrap_runtime_respects_explicit_adapter_overrides() -> None:
    class FakeExecutor:
        def execute(self, request):  # pragma: no cover - execution is not allowed in bootstrap
            raise AssertionError("bootstrap must not execute adapters")

    class FakeObserver:
        def observe(self, request):  # pragma: no cover - observation is not allowed in bootstrap
            raise AssertionError("bootstrap must not observe during wiring")

    runtime = bootstrap_runtime(
        executors={"shell_command": FakeExecutor()},
        observers={"filesystem": FakeObserver()},
    )

    assert runtime.executors["shell_command"].__class__ is FakeExecutor
    assert runtime.observers["filesystem"].__class__ is FakeObserver
    assert runtime.verification_engine.__class__ is VerificationEngine
    assert runtime.clock() != ""
