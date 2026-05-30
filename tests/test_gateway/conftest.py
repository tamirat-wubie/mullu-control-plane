"""Shared fixtures for the gateway test suite.

``create_gateway_app``'s approval-webhook / authority-operator /
deployment-authority bypass requires an EXPLICIT ``MULLU_ENV`` of
``local_dev``/``test`` (an unset value fails closed so a production deployment
that forgets to set ``MULLU_ENV`` does not silently open every authority route
— see ``gateway.server._explicit_dev_or_test_env``).

The gateway suite builds apps without setting ``MULLU_ENV`` and historically
relied on the old unset→``local_dev`` default for that bypass. Declare the
development environment explicitly here so that assumption is visible and
stable. Tests that need a different environment (e.g. production fail-closed
cases) override it with ``monkeypatch.setenv`` in the test body, which runs
after this autouse fixture.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _default_gateway_test_env(monkeypatch):
    if "MULLU_ENV" not in os.environ:
        # Reproduce the historical unset default explicitly (zero behavior
        # change for the suite) while keeping production-unset fail-closed.
        monkeypatch.setenv("MULLU_ENV", "local_dev")
