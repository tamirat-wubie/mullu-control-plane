"""Purpose: compile app-builder specs into small governed software tasks.
Governance scope: task DAG generation, affected-file boundaries, quality
    gates, review obligations, and software-change request candidates.
Dependencies: hashlib, json, app-builder contracts, and software-dev adapter.
Invariants:
  - Generated task graphs are acyclic and deterministic.
  - Every task has explicit acceptance criteria and quality gates.
  - Software requests are bounded to patch_test_review mode.
  - No direct deploy, commit-candidate, push, or production action is emitted.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.app_builder import AppTask, AppTaskGraph, AppTaskKind, AppTaskRisk, ArchitectureSpec, ProductSpec
from mcoi_runtime.core.app_builder.architecture_spec import draft_architecture_spec
from mcoi_runtime.domain_adapters.software_dev import SoftwareQualityGate, SoftwareRequest, SoftwareWorkKind, SoftwareWorkMode


_DIRECT_DEPLOYMENT_CRITERION = "Direct deployment remains out of scope for this task"
_SOFTWARE_CHANGE_EVIDENCE = ("workspace_snapshot", "patch_result", "test_result", "review_record", "app_task_graph")
_GATE_TO_SOFTWARE_GATE = {gate.value: gate for gate in SoftwareQualityGate}


def build_app_task_graph(product_spec: ProductSpec, architecture_spec: ArchitectureSpec | None = None) -> AppTaskGraph:
    """Create a deterministic app task DAG from product and architecture specs."""
    if not isinstance(product_spec, ProductSpec):
        raise ValueError("product_spec must be a ProductSpec")
    architecture = architecture_spec or draft_architecture_spec(product_spec)
    if not isinstance(architecture, ArchitectureSpec):
        raise ValueError("architecture_spec must be an ArchitectureSpec")
    if architecture.app_name != product_spec.app_name:
        raise ValueError("architecture_app_name_must_match_product_spec")
    entity_name = architecture.data_entities[0]
    entity_slug = str(architecture.metadata.get("primary_entity_slug") or _slug(entity_name))
    app_slug = _slug(product_spec.app_name)
    tasks = _tasks_for(product_spec, architecture, entity_name, entity_slug, app_slug)
    graph_id = f"app-task-graph-{_hash_payload({'app_name': product_spec.app_name, 'task_ids': [task.task_id for task in tasks]})[:16]}"
    return AppTaskGraph(
        graph_id=graph_id,
        app_name=product_spec.app_name,
        tasks=tasks,
        evidence_refs=(f"product_spec:{_hash_payload(product_spec.to_json_dict())[:16]}", f"architecture_spec:{_hash_payload(architecture.to_json_dict())[:16]}", "direct_deployment:false"),
        metadata={"generated_from": "product_spec_and_architecture_spec", "runtime_stack": architecture.runtime_stack, "software_request_mode": SoftwareWorkMode.PATCH_TEST_REVIEW.value, "direct_deployment_allowed": False, "commit_candidate_allowed": False, "task_count": len(tasks)},
    )


def software_requests_from_task_graph(graph: AppTaskGraph, *, repository: str, target_branch: str = "main") -> tuple[SoftwareRequest, ...]:
    """Convert app tasks into bounded software-change request candidates."""
    if not isinstance(graph, AppTaskGraph):
        raise ValueError("graph must be an AppTaskGraph")
    repository_name = repository.strip()
    branch_name = target_branch.strip()
    if not repository_name:
        raise ValueError("repository must be non-empty")
    if not branch_name:
        raise ValueError("target_branch must be non-empty")
    return tuple(
        SoftwareRequest(
            kind=_software_kind_for(task),
            summary=f"{graph.app_name}: {task.title}",
            repository=repository_name,
            target_branch=branch_name,
            affected_files=task.affected_files,
            acceptance_criteria=tuple(dict.fromkeys((*task.acceptance_criteria, _DIRECT_DEPLOYMENT_CRITERION))),
            blast_radius="service" if task.kind is AppTaskKind.INTEGRATION_WIRING else "module",
            reviewer_required=task.review_required,
            mode=SoftwareWorkMode.PATCH_TEST_REVIEW,
            quality_gates=_software_quality_gates_for(task),
            max_self_debug_iterations=2,
            rollback_required=True,
            sandbox_profile="workspace_network_none",
            evidence_required=_SOFTWARE_CHANGE_EVIDENCE,
        )
        for task in graph.tasks
    )


def _tasks_for(product_spec: ProductSpec, architecture: ArchitectureSpec, entity_name: str, entity_slug: str, app_slug: str) -> tuple[AppTask, ...]:
    entity_title = "".join(part.capitalize() for part in entity_slug.split("-"))
    frontend_root = f"dashboard/src/features/{entity_slug}"
    return (
        AppTask("task-001-data-model", f"Create {entity_title} data model", AppTaskKind.DATA_MODEL, (f"app/models/{entity_slug}.py", f"schemas/{entity_slug}.schema.json"), (f"{entity_name} entity fields are explicit and typed", "Schema contract is serializable and versioned", "Rollback boundary covers generated model and schema files"), (), ("unit_tests", "lint", "typecheck", "security_scan", "schema_compatibility_check"), AppTaskRisk.MEDIUM, metadata={"core_flows": product_spec.core_flows}),
        AppTask("task-002-api-contract", f"Create {entity_title} API contract", AppTaskKind.API_CONTRACT, (f"app/api/{entity_slug}.py", f"app/services/{entity_slug}.py"), (f"API exposes {architecture.api_routes[0]} and {architecture.api_routes[1]}", "Route inputs are validated before service execution", "Route errors are explicit and auditable"), ("task-001-data-model",), ("unit_tests", "lint", "typecheck", "security_scan", "changed_route_contract_check"), AppTaskRisk.MEDIUM, metadata={"api_routes": architecture.api_routes}),
        AppTask("task-003-ui-surface", f"Create {entity_title} UI surface", AppTaskKind.UI_SURFACE, (f"{frontend_root}/{entity_name}Dashboard.tsx", f"{frontend_root}/{entity_name}Form.tsx"), (f"UI supports {architecture.ui_surfaces[0]} and {architecture.ui_surfaces[1]}", "User inputs have visible validation states", "Core flows can be completed without direct backend credentials"), ("task-001-data-model",), ("unit_tests", "lint", "build", "review"), AppTaskRisk.MEDIUM, metadata={"ui_surfaces": architecture.ui_surfaces}),
        AppTask("task-004-validation-security", "Add validation and security controls", AppTaskKind.VALIDATION_SECURITY, (f"app/services/{entity_slug}.py", f"{frontend_root}/{entity_name}Form.tsx"), ("Security controls are traceable to architecture requirements", "Invalid requests fail before state mutation", "Tenant and role checks are visible at the boundary"), ("task-002-api-contract", "task-003-ui-surface"), ("unit_tests", "lint", "typecheck", "security_scan", "review"), AppTaskRisk.HIGH, metadata={"security_controls": architecture.security_controls}),
        AppTask("task-005-tests", "Add app behavior tests", AppTaskKind.TESTS, (f"tests/test_{entity_slug}_api.py", f"{frontend_root}/{entity_name}Dashboard.test.tsx"), ("Happy path is covered by executable tests", "Boundary validation failures are covered by executable tests", "Rollback-sensitive behavior has regression coverage"), ("task-002-api-contract", "task-003-ui-surface", "task-004-validation-security"), ("unit_tests", "lint", "typecheck", "security_scan"), AppTaskRisk.MEDIUM),
        AppTask("task-006-integration-wiring", "Wire app integration boundaries", AppTaskKind.INTEGRATION_WIRING, ("app/main.py", "dashboard/src/routes.tsx"), ("Backend route registration is explicit", "Frontend routing reaches the new app surface", "Integration keeps deployment action out of scope"), ("task-005-tests",), ("unit_tests", "integration_tests", "lint", "typecheck", "security_scan", "review"), AppTaskRisk.HIGH, metadata={"integration_points": architecture.integration_points}),
        AppTask("task-007-preview-review", "Create preview and review packet", AppTaskKind.PREVIEW_REVIEW, (f"docs/review/{app_slug}_review_packet.md",), ("Review packet lists product scope, changed files, gates, and residual risk", "Preview instructions are local or sandbox-only", "No production deployment instruction is present"), ("task-006-integration-wiring",), ("review",), AppTaskRisk.LOW, metadata={"direct_deployment_allowed": False}),
    )


def _software_kind_for(task: AppTask) -> SoftwareWorkKind:
    if task.kind is AppTaskKind.TESTS:
        return SoftwareWorkKind.TEST_GENERATION
    if task.kind is AppTaskKind.PREVIEW_REVIEW:
        return SoftwareWorkKind.DOCS
    if task.kind is AppTaskKind.VALIDATION_SECURITY:
        return SoftwareWorkKind.SECURITY_FIX
    return SoftwareWorkKind.FEATURE


def _software_quality_gates_for(task: AppTask) -> tuple[SoftwareQualityGate, ...]:
    gates = tuple(_GATE_TO_SOFTWARE_GATE[gate] for gate in task.quality_gates if gate in _GATE_TO_SOFTWARE_GATE)
    return tuple(dict.fromkeys(gates)) or (SoftwareQualityGate.REVIEW,)


def _slug(value: str) -> str:
    return "-".join(part for part in value.lower().replace("_", "-").split() if part) or "app"


def _hash_payload(payload: Any) -> str:
    return sha256(json.dumps(_json_ready(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _json_ready(value: Any) -> Any:
    if hasattr(value, "to_json_dict"):
        return value.to_json_dict()
    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
