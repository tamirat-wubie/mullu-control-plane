"""The tenant-scope coverage gate must stay green and recognize scoping.

This gate fails CI when a NEW router handler takes a tenant from the path
(``{tenant_id}``) or a tenant-bearing request body but doesn't call a
tenant-scope helper. Inherited unscoped routes are acknowledged in
``scripts/tenant_scope_coverage_baseline.txt``.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_tenant_scope_coverage.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_tenant_scope_coverage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_passes_with_baseline():
    """All current findings are baselined, so the gate exits 0."""
    assert _load().main() == 0


def test_musia_auth_dependency_counts_as_scoped():
    """musia_tenants routes are operator-gated via Depends(require_admin) and
    must not be flagged as unscoped (regression guard against false positives)."""
    keys = {f.split("  ")[0] for f in _load().scan()}
    assert not any("musia_tenants.py" in k for k in keys)


def test_scan_returns_relpath_handler_keys():
    """Every finding key is a ``relpath::handler`` string the baseline can match."""
    for finding in _load().scan():
        key = finding.split("  ")[0]
        assert "::" in key and key.endswith(tuple("abcdefghijklmnopqrstuvwxyz_0123456789"))
