"""Purpose: verify bounded helper contracts in the governed server boundary.
Governance scope: helper validation tests only.
Dependencies: server helper functions and pytest monkeypatch support.
Invariants: environment flag validation stays bounded and does not reflect caller names.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app import server


def test_env_flag_bounds_invalid_boolean_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCOI_TEST_FLAG", "sometimes")

    with pytest.raises(ValueError, match="^value must be a boolean flag$") as exc_info:
        server._env_flag("MCOI_TEST_FLAG")

    message = str(exc_info.value)
    assert message == "value must be a boolean flag"
    assert "MCOI_TEST_FLAG" not in message
    assert "boolean flag" in message
