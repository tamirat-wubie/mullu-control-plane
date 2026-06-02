"""Robustness regression: a RecursionError -> bounded 400, not 500.

A maliciously deep JSON body (thousands of nested objects) made FastAPI's
jsonable_encoder exceed the interpreter recursion limit while encoding, which the
generic handler turned into a 500. No legitimate request reaches the recursion
limit, so install_global_exception_handler now maps RecursionError to a bounded
400. RuntimeError (its non-recursion sibling) and everything else still map to 500.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.server_http import install_global_exception_handler


class _Metrics:
    def inc(self, *args, **kwargs) -> None:
        pass


class _Logger:
    def log(self, *args, **kwargs) -> None:
        pass


class _LogLevels:
    ERROR = 40


def _client() -> TestClient:
    app = FastAPI()
    install_global_exception_handler(
        app=app, metrics=_Metrics(), platform_logger=_Logger(), log_levels=_LogLevels(),
    )

    @app.get("/raise/recursion")
    def _recursion():
        raise RecursionError("maximum recursion depth exceeded")

    @app.get("/raise/runtime")
    def _runtime():
        raise RuntimeError("server fault")

    return TestClient(app, raise_server_exceptions=False)


def test_recursion_error_maps_to_400():
    resp = _client().get("/raise/recursion")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "request_too_deeply_nested"
    assert body["governed"] is True


def test_runtime_error_still_500():
    # RecursionError is a RuntimeError subclass; the generic RuntimeError must
    # NOT be caught by the recursion handler (it is a server fault, not input).
    assert _client().get("/raise/runtime").status_code == 500
