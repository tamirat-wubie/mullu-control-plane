#!/usr/bin/env python3
"""
Tenant-Scope Coverage — structural guard against cross-tenant IDORs.

The data-plane HTTP handlers run behind ``GovernanceMiddleware``, which binds
the request tenant from the query/header only. A handler that instead takes the
tenant from the URL **path** (``{tenant_id}``) or the request **body** (a model
with a ``tenant_id`` field) bypasses that binding — an authenticated caller for
tenant A could read or mutate tenant B's data unless the handler re-checks it.

This linter requires every such handler to call one of the tenant-scope helpers
(``enforce_tenant_scope`` / ``scoped_listing_tenant`` in
``mcoi_runtime/app/routers/_tenant_scope.py``). New unscoped tenant routes fail
CI. Inherited exemptions are acknowledged in
``scripts/tenant_scope_coverage_baseline.txt`` (key ``relpath::handler`` per
line) — each should eventually be scoped or confirmed not-tenant-scoped.

Exit codes: 0 all covered (or baselined); 1 unscoped tenant route(s); 2 scan error.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTERS_DIR = REPO_ROOT / "mcoi" / "mcoi_runtime" / "app" / "routers"
BASELINE_PATH = REPO_ROOT / "scripts" / "tenant_scope_coverage_baseline.txt"

SCOPE_HELPERS = frozenset({"enforce_tenant_scope", "scoped_listing_tenant"})
# musia_auth FastAPI dependencies that bind/authorize the tenant from the token
# (used as ``param = Depends(require_admin)`` etc.). A handler guarded by one of
# these is access-controlled and not an open cross-tenant route.
MUSIA_SCOPE_DEPS = frozenset({
    "require_admin", "require_read", "require_write", "require_scope",
    "resolve_musia_tenant", "resolve_musia_auth",
})
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})


def _route_path(decorator: ast.expr) -> str | None:
    """Return the route path string from an ``@router.<method>("...")`` decorator."""
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not (isinstance(func, ast.Attribute) and func.attr in HTTP_METHODS):
        return None
    if not (isinstance(func.value, ast.Name) and func.value.id == "router"):
        return None
    if decorator.args and isinstance(decorator.args[0], ast.Constant):
        value = decorator.args[0].value
        if isinstance(value, str):
            return value
    return ""  # router method decorator, but path not a literal


def _tenant_bearing_models(tree: ast.Module) -> set[str]:
    """Names of pydantic models in this module that declare a ``tenant_id`` field."""
    models: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    if stmt.target.id == "tenant_id":
                        models.add(node.name)
                        break
    return models


def _is_scoped(func: ast.FunctionDef) -> bool:
    """True if the handler scopes the tenant — either by calling a scope helper
    in its body, or by depending on a musia_auth scope dependency in its
    signature (``= Depends(require_admin)`` etc.)."""
    for node in ast.walk(func):
        # Body call to enforce_tenant_scope / scoped_listing_tenant
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in SCOPE_HELPERS:
                return True
        # Signature dependency on a musia_auth scope guard
        if isinstance(node, ast.Name) and node.id in MUSIA_SCOPE_DEPS:
            return True
    return False


def _param_annotation_names(func: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for arg in list(func.args.args) + list(func.args.kwonlyargs):
        ann = arg.annotation
        if isinstance(ann, ast.Name):
            names.add(ann.id)
    return names


def _load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    out: set[str] = set()
    for raw in BASELINE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.add(line)
    return out


def scan() -> list[str]:
    findings: list[str] = []
    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        tenant_models = _tenant_bearing_models(tree)
        relpath = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            paths = [p for p in (_route_path(d) for d in node.decorator_list) if p is not None]
            if not paths:
                continue  # not an HTTP route handler
            needs_path = any("{tenant_id}" in p for p in paths)
            needs_body = bool(_param_annotation_names(node) & tenant_models)
            if not (needs_path or needs_body):
                continue
            if _is_scoped(node):
                continue
            reason = "path {tenant_id}" if needs_path else "body tenant_id model"
            findings.append(f"{relpath}::{node.name}  ({reason})")
    return findings


def main() -> int:
    if not ROUTERS_DIR.is_dir():
        print(f"ERROR: routers dir not found: {ROUTERS_DIR}", file=sys.stderr)
        return 2
    findings = scan()
    baseline = _load_baseline()
    new = sorted(f for f in findings if f.split("  ")[0] not in baseline)
    deferred = [f for f in findings if f.split("  ")[0] in baseline]

    if new:
        print("Tenant-scope coverage FAILED — unscoped tenant route(s):", file=sys.stderr)
        for f in new:
            print(f"  {f}", file=sys.stderr)
        print(
            "\n  Each handler taking a tenant from the path/body must call "
            "enforce_tenant_scope / scoped_listing_tenant, or be added to "
            f"{BASELINE_PATH.relative_to(REPO_ROOT).as_posix()} if it is genuinely "
            "not tenant-scoped.",
            file=sys.stderr,
        )
        if deferred:
            print(f"  ({len(deferred)} pre-existing exemptions deferred via baseline)", file=sys.stderr)
        return 1

    print(
        f"Tenant-scope coverage PASSED ({len(deferred)} exemptions deferred via baseline)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
