#!/usr/bin/env python3
"""
Persistence Tenant-Guard Coverage -- defense-in-depth against cross-tenant reads.

The router's ``enforce_tenant_scope`` is the primary tenant gate, but a future
by-id handler could forget it. ``request_tenant_guard.assert_owns`` is a second
line BELOW the router: a store's by-id read of a tenant-owned record calls
``assert_owns`` so it cannot hand another tenant's record to a non-operator
request (no-op in the default posture -- see
``mcoi_runtime/core/request_tenant_guard.py``).

This linter requires every persistence store method that reads a SINGLE
tenant-owned record by id -- a ``get_`` / ``find_`` / ``load_`` / ``fetch_`` /
``lookup_`` / ``read_`` method that takes an ``*_id`` parameter and returns a
record type declaring a ``tenant_id`` field -- to call ``assert_owns``. Listing
methods (returning ``tuple[...]`` / ``list[...]`` / etc.) are scoped by their
callers and are not flagged. New unguarded by-id reads fail CI. Inherited
exemptions are acknowledged in ``scripts/persistence_tenant_guard_baseline.txt``
(key ``relpath::Class.method`` per line) -- each should eventually call
``assert_owns`` or be confirmed not request-exposed.

Exit codes: 0 all guarded (or baselined); 1 unguarded by-id read(s); 2 scan error.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = REPO_ROOT / "mcoi" / "mcoi_runtime"
PERSIST_DIR = RUNTIME_ROOT / "persistence"
BASELINE_PATH = REPO_ROOT / "scripts" / "persistence_tenant_guard_baseline.txt"

READ_PREFIXES = ("get_", "find_", "load_", "fetch_", "lookup_", "read_")
GUARD_CALL = "assert_owns"


def _tenant_bearing_classes(runtime_root: Path) -> set[str]:
    """Names of classes anywhere in the runtime that declare a ``tenant_id`` field."""
    out: set[str] = set()
    for path in runtime_root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for stmt in node.body:
                    if (
                        isinstance(stmt, ast.AnnAssign)
                        and isinstance(stmt.target, ast.Name)
                        and stmt.target.id == "tenant_id"
                    ):
                        out.add(node.name)
                        break
    return out


def _singular_return_type(ann: ast.expr | None) -> str | None:
    """The single record type a return annotation resolves to.

    Returns None for a collection (``tuple[...]`` / ``list[...]`` / ...), for
    ``None``, or for anything unresolvable -- i.e. anything that is not a
    single-record by-id read.
    """
    if ann is None:
        return None
    if isinstance(ann, ast.Constant):
        # A string forward-ref annotation, e.g. ``-> "Owned | None"``. Parse and
        # recurse so quoted annotations are resolved like bare ones.
        if isinstance(ann.value, str):
            try:
                return _singular_return_type(ast.parse(ann.value, mode="eval").body)
            except SyntaxError:
                return None
        return None
    if isinstance(ann, ast.Name):
        return ann.id
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        # ``X | None`` -> resolve the non-None side.
        for side in (ann.left, ann.right):
            if isinstance(side, ast.Constant) and side.value is None:
                continue
            resolved = _singular_return_type(side)
            if resolved:
                return resolved
        return None
    if isinstance(ann, ast.Subscript):
        base = ann.value.id if isinstance(ann.value, ast.Name) else None
        if base == "Optional":
            return _singular_return_type(ann.slice)
        # tuple[...]/list[...]/Iterable[...]/dict[...] -> a listing, not a by-id read.
        return None
    return None


def _id_param(func: ast.FunctionDef) -> str | None:
    """The name of the first id-like positional/kw-only parameter, or None."""
    for arg in list(func.args.args)[1:] + list(func.args.kwonlyargs):
        if arg.arg == "id" or arg.arg.endswith("_id"):
            return arg.arg
    return None


def _calls_guard(func: ast.FunctionDef) -> bool:
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name) and target.id == GUARD_CALL:
                return True
            if isinstance(target, ast.Attribute) and target.attr == GUARD_CALL:
                return True
    return False


def scan(
    persist_dir: Path = PERSIST_DIR,
    runtime_root: Path = RUNTIME_ROOT,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Return the unguarded tenant-owned by-id reads as ``relpath::Class.method`` keys."""
    tenant_classes = _tenant_bearing_classes(runtime_root)
    findings: list[str] = []
    for path in sorted(persist_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        try:
            relpath = path.relative_to(repo_root).as_posix()
        except ValueError:
            relpath = path.name
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for fn in [m for m in cls.body if isinstance(m, ast.FunctionDef)]:
                if not fn.name.startswith(READ_PREFIXES):
                    continue
                if _id_param(fn) is None:
                    continue
                rtype = _singular_return_type(fn.returns)
                if not rtype or rtype not in tenant_classes:
                    continue
                if _calls_guard(fn):
                    continue
                findings.append(
                    f"{relpath}::{cls.name}.{fn.name}  (by-id read of {rtype}, no assert_owns)"
                )
    return findings


def _load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    out: set[str] = set()
    for raw in BASELINE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.add(line)
    return out


def main() -> int:
    if not PERSIST_DIR.is_dir():
        print(f"ERROR: persistence dir not found: {PERSIST_DIR}", file=sys.stderr)
        return 2
    findings = scan()
    baseline = _load_baseline()
    new = sorted(f for f in findings if f.split("  ")[0] not in baseline)
    deferred = [f for f in findings if f.split("  ")[0] in baseline]

    if new:
        print(
            "Persistence tenant-guard coverage FAILED -- unguarded by-id read(s):",
            file=sys.stderr,
        )
        for finding in new:
            print(f"  {finding}", file=sys.stderr)
        print(
            "\n  Each persistence store method that reads a single tenant-owned "
            "record by id must call request_tenant_guard.assert_owns(record.tenant_id), "
            f"or be added to {BASELINE_PATH.relative_to(REPO_ROOT).as_posix()} if it "
            "is genuinely not request-exposed.",
            file=sys.stderr,
        )
        if deferred:
            print(
                f"  ({len(deferred)} pre-existing exemptions deferred via baseline)",
                file=sys.stderr,
            )
        return 1

    print(
        f"Persistence tenant-guard coverage PASSED ({len(deferred)} exemptions deferred via baseline)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
