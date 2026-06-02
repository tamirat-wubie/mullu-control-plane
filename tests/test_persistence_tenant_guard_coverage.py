"""Tests for scripts/validate_persistence_tenant_guard_coverage.py.

The linter flags persistence store methods that read a single tenant-owned record
by id without calling request_tenant_guard.assert_owns (defense-in-depth). These
tests pin the AST heuristic on synthetic fixtures, unit-test the helpers, and add
a regression guard that the real tree has no un-baselined unguarded by-id reads.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_persistence_tenant_guard_coverage.py"

_spec = importlib.util.spec_from_file_location("persistence_tenant_guard_cov", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
sys.modules["persistence_tenant_guard_cov"] = mod
_spec.loader.exec_module(mod)


_FIXTURE_CONTRACTS = '''
from dataclasses import dataclass

@dataclass
class Owned:
    record_id: str
    tenant_id: str

@dataclass
class Unowned:
    blob_id: str
    payload: str
'''

_FIXTURE_STORE = '''
class GoodStore:
    def get_thing(self, thing_id):
        rec = self._things.get(thing_id)
        if rec is not None:
            assert_owns(rec.tenant_id)
        return rec

class BadStore:
    def get_thing(self, thing_id) -> "Owned | None":
        return self._things.get(thing_id)

class ListStore:
    def list_things(self, tenant_id=""):
        return tuple(self._things.values())

class UnownedStore:
    def get_blob(self, blob_id) -> "Unowned | None":
        return self._blobs.get(blob_id)

class NoIdStore:
    def get_summary(self) -> "Owned | None":
        return self._summary
'''


def _annotated_store(returns: str) -> str:
    # Build BadStore-like code with a concrete (non-string) return annotation so
    # the scanner resolves the type via ast.Name/BinOp/Subscript, not a string.
    return f'''
class S:
    def get_thing(self, thing_id) -> {returns}:
        return self._things.get(thing_id)
'''


def _write_tree(tmp_path: Path, store_src: str) -> Path:
    (tmp_path / "contracts.py").write_text(_FIXTURE_CONTRACTS, encoding="utf-8")
    persist = tmp_path / "persistence"
    persist.mkdir()
    (persist / "store.py").write_text(store_src, encoding="utf-8")
    return persist


def test_scan_flags_only_unguarded_tenant_owned_by_id_reads(tmp_path: Path):
    persist = _write_tree(tmp_path, _FIXTURE_STORE)
    findings = mod.scan(persist_dir=persist, runtime_root=tmp_path, repo_root=tmp_path)
    keys = {f.split("  ")[0] for f in findings}
    # Only BadStore.get_thing is an unguarded tenant-owned by-id read.
    assert keys == {"persistence/store.py::BadStore.get_thing"}
    # Guarded read, listing, unowned record, and no-id reader are all excluded.
    joined = " ".join(findings)
    assert "GoodStore" not in joined
    assert "ListStore" not in joined
    assert "UnownedStore" not in joined
    assert "NoIdStore" not in joined


def test_guarded_method_with_concrete_annotation_passes(tmp_path: Path):
    src = '''
class S:
    def get_thing(self, thing_id) -> Owned | None:
        rec = self._things.get(thing_id)
        if rec is not None:
            assert_owns(rec.tenant_id)
        return rec
'''
    persist = _write_tree(tmp_path, src)
    findings = mod.scan(persist_dir=persist, runtime_root=tmp_path, repo_root=tmp_path)
    assert findings == []


def test_collection_return_is_not_flagged(tmp_path: Path):
    persist = _write_tree(tmp_path, _annotated_store("tuple[Owned, ...]"))
    findings = mod.scan(persist_dir=persist, runtime_root=tmp_path, repo_root=tmp_path)
    assert findings == []  # listing, scoped by caller


def test_optional_record_return_is_flagged(tmp_path: Path):
    persist = _write_tree(tmp_path, _annotated_store("Optional[Owned]"))
    findings = mod.scan(persist_dir=persist, runtime_root=tmp_path, repo_root=tmp_path)
    assert len(findings) == 1 and "S.get_thing" in findings[0]


def _return_ann(src: str) -> ast.expr | None:
    fn = ast.parse(src).body[0]
    assert isinstance(fn, ast.FunctionDef)
    return fn.returns


def test_singular_return_type_resolution():
    assert mod._singular_return_type(_return_ann("def f() -> Owned: ...")) == "Owned"
    assert mod._singular_return_type(_return_ann("def f() -> Owned | None: ...")) == "Owned"
    assert mod._singular_return_type(_return_ann("def f() -> None | Owned: ...")) == "Owned"
    assert mod._singular_return_type(_return_ann("def f() -> Optional[Owned]: ...")) == "Owned"
    # String forward-ref annotations resolve like bare ones.
    assert mod._singular_return_type(_return_ann('def f() -> "Owned | None": ...')) == "Owned"
    assert mod._singular_return_type(_return_ann('def f() -> "Owned": ...')) == "Owned"
    assert mod._singular_return_type(_return_ann("def f() -> tuple[Owned, ...]: ...")) is None
    assert mod._singular_return_type(_return_ann("def f() -> list[Owned]: ...")) is None
    assert mod._singular_return_type(_return_ann("def f() -> None: ...")) is None
    assert mod._singular_return_type(None) is None


def _func(src: str) -> ast.FunctionDef:
    fn = ast.parse(src).body[0]
    assert isinstance(fn, ast.FunctionDef)
    return fn


def test_id_param_detection():
    assert mod._id_param(_func("def f(self, case_id): ...")) == "case_id"
    assert mod._id_param(_func("def f(self, id): ...")) == "id"
    assert mod._id_param(_func("def f(self, *, schedule_id): ...")) == "schedule_id"
    assert mod._id_param(_func("def f(self): ...")) is None
    assert mod._id_param(_func("def f(self, name): ...")) is None


def test_calls_guard_detection():
    assert mod._calls_guard(_func("def f(self): assert_owns(x.tenant_id)"))
    assert mod._calls_guard(_func("def f(self): guard.assert_owns(x.tenant_id)"))
    assert not mod._calls_guard(_func("def f(self): return x"))


def test_tenant_bearing_classes(tmp_path: Path):
    _write_tree(tmp_path, _FIXTURE_STORE)
    classes = mod._tenant_bearing_classes(tmp_path)
    assert "Owned" in classes
    assert "Unowned" not in classes


def test_real_tree_has_no_unbaselined_unguarded_reads():
    # The regression guard: every unguarded tenant-owned by-id read in the real
    # persistence layer must be acknowledged in the baseline. A NEW one fails here
    # (and in CI) until it calls assert_owns or is explicitly baselined.
    findings = mod.scan()
    baseline = mod._load_baseline()
    unbaselined = sorted(f for f in findings if f.split("  ")[0] not in baseline)
    assert unbaselined == [], (
        "New unguarded tenant-owned by-id read(s) -- add assert_owns or baseline:\n  "
        + "\n  ".join(unbaselined)
    )
