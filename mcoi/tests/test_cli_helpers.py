"""Tests for bounded CLI helper contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.app.cli import CLIDemoError, _load_demo_json_object


def test_load_demo_json_object_bounds_invalid_root_type() -> None:
    with pytest.raises(CLIDemoError, match="^invalid JSON response root$") as exc_info:
        _load_demo_json_object(b"[]")
    assert "list" not in str(exc_info.value).lower()
