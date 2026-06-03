"""Persistence-layer tenant defense-in-depth -- organization-kernel cases.

Organization cases carry an org_id, not a tenant_id; the owning tenant is
resolved through the organization (case.org_id -> OrganizationProfile.tenant_id).
OrganizationKernel.get_case now resolves that tenant and calls
request_tenant_guard.assert_owns, so a case cannot be handed to a different
tenant even if a caller forgot the router's _enforce_case_tenant. No-op for
operators / unauthenticated / unbound requests, and for a case whose org has no
resolvable tenant (matching the router's ``if tenant_id`` guard).

State is injected directly into the kernel's maps -- this exercises the get_case
guard, not the (heavily-invarianted) case-opening path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.organization_kernel import (
    OrganizationCase,
    OrganizationCaseStatus,
    OrganizationProfile,
    OrganizationRisk,
)
from mcoi_runtime.core.organization_kernel import OrganizationKernel
from mcoi_runtime.core.request_tenant_guard import (
    CrossTenantRecordError,
    bind_request_tenant,
    reset_request_tenant,
)

NOW = "2026-06-02T00:00:00+00:00"


def _kernel(*, org_id: str = "org-a", tenant_id: str = "tenant-a", with_org: bool = True) -> OrganizationKernel:
    kernel = OrganizationKernel(clock=lambda: NOW)
    if with_org:
        kernel._organizations[org_id] = OrganizationProfile(
            org_id=org_id, tenant_id=tenant_id, name="Org A", created_at=NOW,
        )
    kernel._cases["case-1"] = OrganizationCase(
        case_id="case-1",
        org_id=org_id,
        department_id="engineering",
        case_type="launch_gateway_pilot",
        goal="ship",
        risk=OrganizationRisk.LOW,
        owner_role_id="owner",
        status=OrganizationCaseStatus.OPEN,
        assigned_department_ids=("engineering",),
        created_at=NOW,
    )
    return kernel


@pytest.fixture(autouse=True)
def _isolate_binding():
    yield
    bind_request_tenant(None)


def test_get_case_blocks_cross_tenant():
    kernel = _kernel(tenant_id="tenant-a")
    token = bind_request_tenant("tenant-b", frozenset())  # non-operator B
    try:
        with pytest.raises(CrossTenantRecordError):
            kernel.get_case("case-1")  # A's case (via org) must not reach B
    finally:
        reset_request_tenant(token)


def test_get_case_allows_same_tenant():
    kernel = _kernel(tenant_id="tenant-a")
    token = bind_request_tenant("tenant-a", frozenset())
    try:
        case = kernel.get_case("case-1")
        assert case is not None and case.org_id == "org-a"
    finally:
        reset_request_tenant(token)


def test_get_case_operator_bypass():
    kernel = _kernel(tenant_id="tenant-a")
    token = bind_request_tenant("tenant-b", frozenset({"*"}))
    try:
        assert kernel.get_case("case-1") is not None
    finally:
        reset_request_tenant(token)


def test_get_case_unbound_returns_case():
    kernel = _kernel(tenant_id="tenant-a")
    assert kernel.get_case("case-1") is not None  # default posture -> no-op


def test_get_case_unknown_org_is_unguarded():
    # Case whose org has no resolvable tenant -> no enforcement (matches the
    # router's ``if tenant_id`` guard); must not raise even for a bound foreigner.
    kernel = _kernel(org_id="org-orphan", with_org=False)
    token = bind_request_tenant("tenant-b", frozenset())
    try:
        assert kernel.get_case("case-1") is not None
    finally:
        reset_request_tenant(token)


def test_get_missing_case_returns_none():
    kernel = _kernel(tenant_id="tenant-a")
    token = bind_request_tenant("tenant-b", frozenset())
    try:
        assert kernel.get_case("nope") is None  # no record -> guard never fires
    finally:
        reset_request_tenant(token)
