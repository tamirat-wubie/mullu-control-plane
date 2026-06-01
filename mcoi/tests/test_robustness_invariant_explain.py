"""Robustness regressions found by the schema-aware POST fuzz sweep.

Two defects:
1. Core RuntimeCoreInvariantError (the platform's explicit input/contract
   violation type, a ValueError subclass raised by every ensure_*/require_*
   guard) escaped handlers and became a generic 500 instead of a bounded 400.
   A dedicated exception handler now maps it to 400. Plain ValueError and other
   exceptions must STILL map to 500 -- a bare ValueError may be a server fault,
   not client input, and silently 400-ing it would hide bugs.
2. ExplanationEngine.explain_action read result.guard_name on a GuardChainResult,
   which exposes blocking_guard -- so explaining ANY denied action raised
   AttributeError -> 500. The denied-guard path was previously untested.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.server_http import install_global_exception_handler
from mcoi_runtime.core.explanation_engine import ExplanationEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.governance.guards.chain import GuardChainResult


# --- 1. invariant-error -> 400 (without masking other errors) ---------------


class _Metrics:
    def inc(self, *args, **kwargs) -> None:
        pass


class _Logger:
    def log(self, *args, **kwargs) -> None:
        pass


class _LogLevels:
    ERROR = 40
    WARNING = 30


def _app_with_handlers() -> TestClient:
    app = FastAPI()
    install_global_exception_handler(
        app=app, metrics=_Metrics(), platform_logger=_Logger(), log_levels=_LogLevels(),
    )

    @app.get("/raise/invariant")
    def _invariant():
        raise RuntimeCoreInvariantError("checkpoint_id must be a non-empty string")

    @app.get("/raise/value")
    def _value():
        raise ValueError("a plain value error")

    @app.get("/raise/runtime")
    def _runtime():
        raise RuntimeError("an internal failure")

    return TestClient(app, raise_server_exceptions=False)


def test_invariant_error_maps_to_400():
    resp = _app_with_handlers().get("/raise/invariant")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "invariant_violation"
    assert body["governed"] is True


def test_plain_value_error_still_500_not_masked():
    # RuntimeCoreInvariantError subclasses ValueError; the handler must NOT
    # catch generic ValueErrors (which can be server faults).
    assert _app_with_handlers().get("/raise/value").status_code == 500


def test_other_exceptions_still_500():
    assert _app_with_handlers().get("/raise/runtime").status_code == 500


# --- 2. explain_action must not crash when a guard denies -------------------


class _DenyingGuardChain:
    def evaluate(self, ctx: dict) -> GuardChainResult:
        return GuardChainResult(
            allowed=False, results=(), blocking_guard="content_safety", reason="unsafe content",
        )

    def guard_names(self) -> list[str]:
        return ["content_safety", "budget"]


def test_explain_action_denied_reports_blocking_guard():
    engine = ExplanationEngine(
        clock=lambda: "2026-01-01T00:00:00+00:00", guard_chain=_DenyingGuardChain(),
    )
    # Previously raised AttributeError ('GuardChainResult' has no 'guard_name').
    explanation = engine.explain_action(
        "execute", "target", tenant_id="t", budget_id="b", actor_id="a",
    )
    assert explanation.decision == "denied"
    assert "content_safety" in " ".join(explanation.reasons)
    assert any(
        step.get("result") == "deny" and step.get("guard") == "content_safety"
        for step in explanation.guard_chain_path
    )
