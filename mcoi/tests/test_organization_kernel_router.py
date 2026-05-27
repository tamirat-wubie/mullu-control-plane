"""Purpose: verify Organization Kernel HTTP routes.
Governance scope: organization bootstrap, pilot case plan, evidence, approvals,
gate decisions, terminal closure, learning admission, and default router mounting.
Dependencies: FastAPI TestClient, router deps, OrganizationKernel, and file store.
Invariants:
  - API writes pass through OrganizationKernel methods.
  - Case events are kernel-emitted and visible in read models.
  - Configured persistence receives each mutation snapshot.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.organization_kernel import (
    reset_organization_kernel_for_tests,
    router,
)
from mcoi_runtime.app.server_http import include_default_routers
from mcoi_runtime.core.organization_kernel import OrganizationKernel
from mcoi_runtime.persistence.organization_kernel_store import FileOrganizationKernelStore


FIXED_CLOCK = "2026-05-27T12:00:00+00:00"


class MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


class FixedClock:
    def __call__(self) -> str:
        return FIXED_CLOCK


def _client(tmp_path: Path) -> tuple[TestClient, FileOrganizationKernelStore]:
    reset_organization_kernel_for_tests()
    clock = FixedClock()
    store = FileOrganizationKernelStore(tmp_path / "organization-kernel.json")
    deps.set("clock", clock)
    deps.set("metrics", MetricsStub())
    deps.set("organization_kernel", OrganizationKernel(clock=clock))
    deps.set("organization_kernel_store", store)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), store


def _bootstrap_and_open_pilot(client: TestClient) -> None:
    bootstrap = client.post(
        "/api/v1/orgs/org-mullu/bootstrap-minimum",
        json={"tenant_id": "tenant-mullu", "name": "Mullu"},
    )
    pilot = client.post(
        "/api/v1/cases/launch-gateway-pilot",
        json={"org_id": "org-mullu", "case_id": "case.launch_gateway_pilot"},
    )

    assert bootstrap.status_code == 200
    assert bootstrap.json()["department_count"] == 5
    assert pilot.status_code == 200
    assert pilot.json()["case"]["status"] == "planned"


def _admit_all_pilot_evidence(client: TestClient) -> None:
    requirements = (
        "executive_objective",
        "product_launch_boundary",
        "engineering_health_endpoint",
        "engineering_gateway_witness",
        "engineering_runtime_conformance",
        "security_public_claim_boundary",
        "security_approval",
        "finance_budget_check",
    )
    for requirement_id in requirements:
        response = client.post(
            "/api/v1/cases/case.launch_gateway_pilot/evidence",
            json={
                "evidence_ref": f"evidence:{requirement_id}",
                "requirement_id": requirement_id,
                "submitted_by": "operator",
            },
        )
        assert response.status_code == 200
        assert response.json()["evidence"]["requirement_id"] == requirement_id


def _allow_all_plan_steps(client: TestClient) -> None:
    preconditions = {
        "executive_objective_freeze": ["objective_received"],
        "product_launch_boundary": ["objective_frozen"],
        "engineering_runtime_witness": ["launch_boundary_defined"],
        "security_claim_boundary": ["runtime_witness_collected"],
        "finance_budget_check": ["runtime_witness_collected"],
    }
    for step_id, checked in preconditions.items():
        response = client.post(
            f"/api/v1/cases/case.launch_gateway_pilot/plan-steps/{step_id}/gate",
            json={"checked_preconditions": checked},
        )
        assert response.status_code == 200
        assert response.json()["decision"]["status"] == "allowed"


def test_bootstrap_open_pilot_read_model_and_persistence(tmp_path: Path) -> None:
    client, store = _client(tmp_path)

    _bootstrap_and_open_pilot(client)
    departments = client.get("/api/v1/orgs/org-mullu/departments")
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")
    events = client.get("/api/v1/cases/case.launch_gateway_pilot/events")
    restored = OrganizationKernel(clock=FixedClock())
    store.restore_kernel(restored)

    assert departments.status_code == 200
    assert departments.json()["count"] == 5
    assert fetched.status_code == 200
    assert fetched.json()["case"]["plan_id"] == "plan.launch_gateway_pilot.v1"
    assert fetched.json()["plan"]["steps"][0]["step_id"] == "executive_objective_freeze"
    assert events.status_code == 200
    assert events.json()["count"] == 2
    assert store.exists() is True
    assert restored.get_case("case.launch_gateway_pilot") is not None


def test_gateway_pilot_can_close_and_bind_learning(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": ["evidence:closure:gateway-pilot"],
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
        },
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert approval.status_code == 200
    assert approval.json()["approval"]["role_id"] == "executive.owner"
    assert closure.status_code == 200
    assert closure.json()["closure"]["terminal_disposition"] == "committed"
    assert learning.status_code == 200
    assert learning.json()["learning_admission"]["admitted"] is True
    assert fetched.json()["case"]["status"] == "closed"
    assert fetched.json()["closure"]["terminal_certificate_id"] == "terminal:gateway-pilot"


def test_default_routers_include_organization_kernel_paths() -> None:
    app = FastAPI()
    include_default_routers(app)
    paths = {route.path for route in app.routes}

    assert "/api/v1/orgs" in paths
    assert "/api/v1/cases" in paths
    assert "/api/v1/cases/{case_id}/close" in paths
