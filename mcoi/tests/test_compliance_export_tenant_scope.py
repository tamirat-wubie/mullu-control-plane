"""Cross-tenant IDOR regression for compliance export endpoints.

export_audit_package / export_incident_package / export_compliance_mapping took
the tenant from the request body and built a package for that tenant -- and an
empty tenant_id exported ALL tenants' data -- with no check against the
authenticated tenant. They now call scoped_listing_tenant: an authenticated
non-operator tenant cannot export another tenant's (or all tenants') data, while
operators (wildcard scope) and unauthenticated/dev requests are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers._tenant_scope import scoped_listing_tenant
from mcoi_runtime.app.routers.compliance import (
    AuditPackageRequest,
    ComplianceMappingRequest,
    IncidentPackageRequest,
    export_audit_package,
    export_compliance_mapping,
    export_incident_package,
)


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def _authed_a() -> _Req:
    return _Req({"authenticated_tenant_id": "tenant-a"})


def test_export_audit_package_denies_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        export_audit_package(AuditPackageRequest(tenant_id="tenant-b"), _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_export_incident_package_denies_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        export_incident_package(IncidentPackageRequest(tenant_id="tenant-b"), _authed_a())
    assert exc.value.status_code == 403


def test_export_compliance_mapping_denies_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        export_compliance_mapping(ComplianceMappingRequest(tenant_id="tenant-b"), _authed_a())
    assert exc.value.status_code == 403


def test_authenticated_tenant_export_forced_to_own_tenant():
    # The "empty tenant_id -> all tenants" export is forced to the caller's tenant.
    assert scoped_listing_tenant(_authed_a(), None) == "tenant-a"


def test_operator_wildcard_may_export_all_tenants():
    operator = _Req({"authenticated_tenant_id": "tenant-a", "jwt_scopes": frozenset({"*"})})
    assert scoped_listing_tenant(operator, None) is None
