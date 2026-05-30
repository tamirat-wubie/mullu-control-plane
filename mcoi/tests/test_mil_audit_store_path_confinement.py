"""MIL-audit store paths must be confined to the permitted root.

Regression test for arbitrary file read/write/list: the MIL-audit endpoints
accept explicit store paths in the request. Without confinement a caller could
point them at any host directory. ``_confined_store_path`` rejects paths outside
the configured root (``MULLU_MIL_AUDIT_STORE_ROOT``; default: system temp).
"""

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.mil_audit import _confined_store_path


def test_path_inside_root_is_allowed(monkeypatch, tmp_path):
    monkeypatch.setenv("MULLU_MIL_AUDIT_STORE_ROOT", str(tmp_path))
    resolved = _confined_store_path(str(tmp_path / "runbooks"))
    assert resolved == (tmp_path / "runbooks").resolve()


def test_root_itself_is_allowed(monkeypatch, tmp_path):
    monkeypatch.setenv("MULLU_MIL_AUDIT_STORE_ROOT", str(tmp_path))
    assert _confined_store_path(str(tmp_path)) == tmp_path.resolve()


def test_absolute_path_outside_root_is_rejected(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    monkeypatch.setenv("MULLU_MIL_AUDIT_STORE_ROOT", str(root))
    with pytest.raises(HTTPException) as exc_info:
        _confined_store_path(str(tmp_path / "secrets"))
    assert exc_info.value.status_code == 400


def test_parent_traversal_is_rejected(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("MULLU_MIL_AUDIT_STORE_ROOT", str(root))
    with pytest.raises(HTTPException) as exc_info:
        _confined_store_path(str(root / ".." / "escape"))
    assert exc_info.value.status_code == 400


def test_default_root_is_system_temp(monkeypatch, tmp_path):
    # Unset env: paths under the system temp dir (where pytest tmp_path lives)
    # are allowed, so the existing suite that uses tmp_path keeps working.
    monkeypatch.delenv("MULLU_MIL_AUDIT_STORE_ROOT", raising=False)
    resolved = _confined_store_path(str(tmp_path / "store"))
    assert resolved == (tmp_path / "store").resolve()
