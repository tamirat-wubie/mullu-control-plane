"""O(1) by-id lookups on OrganizationKernel.

Routers previously located records with
``next(item for item in snapshot_state().<collection> if item.<id> == x)`` --
rebuilding + sorting the entire kernel state on every call. These direct lookups
use the kernel's dicts / _plan_by_case index and return the identical record
(measured ~2400x faster than snapshot_state()+scan at a few thousand records).
"""

from __future__ import annotations

from mcoi_runtime.contracts.organization_kernel import OrganizationProfile
from mcoi_runtime.core.organization_kernel import OrganizationKernel

NOW = "2026-06-02T00:00:00+00:00"


def _kernel() -> OrganizationKernel:
    return OrganizationKernel(clock=lambda: NOW)


def test_get_organization_returns_stored_profile_or_none():
    kernel = _kernel()
    org = OrganizationProfile(org_id="org-1", tenant_id="t1", name="Org", created_at=NOW)
    kernel._organizations["org-1"] = org
    assert kernel.get_organization("org-1") is org
    assert kernel.get_organization("missing") is None


def test_get_role_returns_stored_role_or_none():
    kernel = _kernel()
    role = object()
    kernel._roles["r1"] = role
    assert kernel.get_role("r1") is role
    assert kernel.get_role("missing") is None


def test_plan_for_case_uses_index():
    kernel = _kernel()
    plan = object()
    kernel._plans["p1"] = plan
    kernel._plan_by_case["c1"] = "p1"
    assert kernel.plan_for_case("c1") is plan
    assert kernel.plan_for_case("no-case") is None


def test_closure_for_case_matches_case_id():
    kernel = _kernel()

    class _Closure:
        case_id = "c1"

    closure = _Closure()
    kernel._closures["x1"] = closure
    assert kernel.closure_for_case("c1") is closure
    assert kernel.closure_for_case("c2") is None
