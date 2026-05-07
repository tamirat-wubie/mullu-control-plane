"""Purpose: test deterministic app-builder planning pipeline.
Governance scope: validates ProductSpec, ArchitectureSpec, AppTaskGraph,
    bounded software-change request candidates, and deployment exclusion.
Dependencies: pytest plus MCOI app-builder contracts and planning helpers.
Invariants:
  - App builder output is declarative and side-effect free.
  - Task graphs are acyclic and every task carries gates and acceptance checks.
  - Generated software requests use patch_test_review mode only.
  - Direct production deployment is never emitted by PR6 planning.
"""

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.app_builder import AppTask, AppTaskGraph, AppTaskKind, AppTaskRisk, ProductSpec
from mcoi_runtime.core.app_builder.architecture_spec import draft_architecture_spec
from mcoi_runtime.core.app_builder.codegen_pipeline import plan_app_build
from mcoi_runtime.core.app_builder.product_spec import product_spec_from_mapping
from mcoi_runtime.core.app_builder.task_graph import build_app_task_graph, software_requests_from_task_graph
from mcoi_runtime.domain_adapters.software_dev import SoftwareQualityGate, SoftwareWorkKind, SoftwareWorkMode


def _invoice_product_spec() -> ProductSpec:
    return ProductSpec(
        app_name="Invoice Dashboard",
        users=("finance operator", "accounting manager"),
        jobs_to_be_done=("review invoices", "flag overdue invoices"),
        core_flows=("list invoices", "create invoice", "mark invoice paid"),
        non_goals=("production deployment", "payment processing"),
        security_requirements=("tenant scoped access", "role based approval"),
        metadata={"source": "unit_test"},
    )


def _minimal_task(task_id: str, *, dependencies: tuple[str, ...] = ()) -> AppTask:
    return AppTask(task_id, f"Task {task_id}", AppTaskKind.DATA_MODEL, (f"app/{task_id}.py",), ("criterion one", "criterion two", "criterion three"), dependencies, ("unit_tests", "lint", "review"), AppTaskRisk.LOW)


def test_product_and_architecture_specs_are_explicit_frozen_and_json_safe() -> None:
    product = product_spec_from_mapping(_invoice_product_spec().to_json_dict())
    architecture = draft_architecture_spec(product)

    assert product.app_name == "Invoice Dashboard"
    assert product.users == ("finance operator", "accounting manager")
    assert isinstance(product.metadata, MappingProxyType)
    assert architecture.data_entities == ("Invoice",)
    assert architecture.api_routes == ("/api/invoices", "/api/invoices/{id}")
    assert architecture.metadata["direct_deployment_allowed"] is False
    assert "tenant scoped access" in architecture.security_controls
    with pytest.raises(ValueError):
        product_spec_from_mapping({"app_name": "Missing fields"})
    with pytest.raises(Exception):
        product.users += ("auditor",)  # type: ignore[misc]


def test_task_graph_emits_small_acyclic_review_bound_tasks() -> None:
    graph = build_app_task_graph(_invoice_product_spec())
    task_ids = tuple(task.task_id for task in graph.tasks)

    assert len(graph.tasks) == 7
    assert graph.root_task_ids == ("task-001-data-model",)
    assert graph.terminal_task_ids == ("task-007-preview-review",)
    assert task_ids == tuple(sorted(task_ids))
    assert all(task.affected_files for task in graph.tasks)
    assert all(len(task.acceptance_criteria) >= 3 for task in graph.tasks)
    assert graph.metadata["direct_deployment_allowed"] is False
    assert graph.tasks[-1].affected_files == ("docs/review/invoice-dashboard_review_packet.md",)
    assert "No production deployment instruction is present" in graph.tasks[-1].acceptance_criteria


def test_app_task_graph_contract_rejects_cycles_unknown_deps_and_deployment() -> None:
    with pytest.raises(ValueError) as cycle_info:
        AppTaskGraph("graph-cycle", "Cycle App", (_minimal_task("task-a", dependencies=("task-b",)), _minimal_task("task-b", dependencies=("task-a",))), evidence_refs=("test:evidence",), metadata={"direct_deployment_allowed": False, "commit_candidate_allowed": False})
    with pytest.raises(ValueError) as missing_info:
        AppTaskGraph("graph-missing", "Missing App", (_minimal_task("task-c", dependencies=("missing-task",)),), evidence_refs=("test:evidence",), metadata={"direct_deployment_allowed": False, "commit_candidate_allowed": False})
    with pytest.raises(ValueError) as deployment_info:
        AppTaskGraph("graph-deploy", "Deploy App", (_minimal_task("task-root"),), evidence_refs=("test:evidence",), metadata={"direct_deployment_allowed": True, "commit_candidate_allowed": False})

    assert "app_task_dependency_cycle" in str(cycle_info.value)
    assert "missing_app_task_dependency:missing-task" in str(missing_info.value)
    assert "direct_deployment_allowed_must_be_false" in str(deployment_info.value)


def test_software_requests_are_patch_test_review_candidates_only() -> None:
    graph = build_app_task_graph(_invoice_product_spec())
    requests = software_requests_from_task_graph(graph, repository="invoice-service", target_branch="feature/invoice-dashboard")

    assert len(requests) == len(graph.tasks)
    assert all(request.mode is SoftwareWorkMode.PATCH_TEST_REVIEW for request in requests)
    assert all(request.target_branch == "feature/invoice-dashboard" for request in requests)
    assert all(request.sandbox_profile == "workspace_network_none" for request in requests)
    assert all("Direct deployment remains out of scope for this task" in request.acceptance_criteria for request in requests)
    assert requests[5].blast_radius == "service"
    assert SoftwareQualityGate.INTEGRATION_TESTS in requests[5].quality_gates
    assert requests[6].kind is SoftwareWorkKind.DOCS
    assert requests[6].quality_gates == (SoftwareQualityGate.REVIEW,)


def test_plan_app_build_composes_architecture_graph_and_requests() -> None:
    product = _invoice_product_spec()
    architecture, graph, requests = plan_app_build(product, repository="invoice-service", target_branch="feature/invoice-dashboard")

    assert architecture.app_name == product.app_name
    assert graph.app_name == product.app_name
    assert len(requests) == graph.metadata["task_count"]
    assert requests[0].repository == "invoice-service"
    assert requests[0].affected_files == ("app/models/invoice.py", "schemas/invoice.schema.json")
    assert requests[-1].affected_files == ("docs/review/invoice-dashboard_review_packet.md",)
    assert graph.metadata["software_request_mode"] == "patch_test_review"
    assert all(request.rollback_required for request in requests)
