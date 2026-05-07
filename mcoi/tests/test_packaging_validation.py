"""Purpose: verify packaging environment validation bounds startup helper failures.
Governance scope: packaging validation boundary tests only.
Dependencies: app.packaging.
Invariants: profile/bootstrap validation failures remain visible, deterministic, and free of raw backend detail.
"""

from __future__ import annotations

import builtins
from unittest.mock import patch

import mcoi_runtime.app.packaging as packaging


def test_validate_environment_bounds_profile_load_error(monkeypatch) -> None:
    class ExplodingProfiles:
        def __len__(self):
            raise RuntimeError("secret profile failure")

    monkeypatch.setattr(packaging, "BUILTIN_PROFILES", ExplodingProfiles())

    result = packaging.validate_environment()
    check = next(c for c in result.checks if c.name == "profiles_loaded")

    assert result.status is packaging.ValidationStatus.INVALID
    assert check.passed is False
    assert check.message == "profile load error (RuntimeError)"
    assert "secret profile failure" not in check.message


def test_validate_environment_bounds_bootstrap_import_error() -> None:
    original_import = builtins.__import__

    def crashing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mcoi_runtime.app.bootstrap":
            raise ImportError("secret bootstrap failure")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=crashing_import):
        result = packaging.validate_environment()

    check = next(c for c in result.checks if c.name == "bootstrap_importable")

    assert result.status is packaging.ValidationStatus.INVALID
    assert check.passed is False
    assert check.message == "import error (ImportError)"
    assert "secret bootstrap failure" not in check.message
