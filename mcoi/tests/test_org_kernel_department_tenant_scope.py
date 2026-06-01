"""Cross-tenant scoping for organization-kernel department endpoints.

Organization department routes bind to an org_id path/body value, so the route
must resolve that organization to its tenant before returning department
surfaces or registering department packs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import organization_kernel as ok


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(tenant_id: str, *, operator: bool = False) -> _Req:
    scopes = frozenset({"*"}) if operator else frozenset({"musia.write", "musia.read"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


@dataclass(frozen=True)
class _Organization:
    org_id: str = "org-x"
    tenant_id: str = "tenant-b"
    name: str = "Tenant B"
    created_at: str = "2026-05-27T12:00:00+00:00"

    def to_json_dict(self):
        return {
            "org_id": self.org_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "created_at": self.created_at,
            "metadata": {},
        }


@dataclass(frozen=True)
class _Snapshot:
    organizations: tuple[_Organization, ...] = (_Organization(),)
    departments: tuple = ()
    roles: tuple = ()
    authority_rules: tuple = ()
    capabilities: tuple = ()
    evidence_requirements: tuple = ()
    cases: tuple = ()


class _Kernel:
    """Minimal kernel: org-x is owned by tenant-b."""

    def organization_tenant(self, org_id):
        return "tenant-b" if org_id == "org-x" else None

    def snapshot_state(self):
        return _Snapshot()

    def list_departments(self):
        return ()


class _Body:
    org_id = "org-x"


@pytest.fixture
def cross_tenant_kernel(monkeypatch):
    monkeypatch.setattr(ok, "_kernel", lambda: _Kernel())


def test_list_organization_departments_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.list_organization_departments("org-x", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_department_registry_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_organization_department_registry("org-x", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_department_registry_view_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_organization_department_registry_view("org-x", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_authority_map_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_organization_authority_map("org-x", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_authority_map_view_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_organization_authority_map_view("org-x", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_create_department_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.create_department(_Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_department_registry_operator_passes_tenant_gate(cross_tenant_kernel):
    result = ok.get_organization_department_registry("org-x", _authed("tenant-a", operator=True))
    assert result["org_id"] == "org-x"
    assert result["summary"]["department_count"] == 0
    assert result["governed"] is True


def test_authority_map_operator_passes_tenant_gate(cross_tenant_kernel):
    result = ok.get_organization_authority_map("org-x", _authed("tenant-a", operator=True))
    assert result["org_id"] == "org-x"
    assert result["summary"]["department_count"] == 0
    assert result["summary"]["map_gap_count"] == 0
    assert result["governed"] is True
