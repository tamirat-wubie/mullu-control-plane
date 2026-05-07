"""Purpose: compose app-builder product, architecture, and task graph planning.
Governance scope: declarative app build planning and bounded software-change
    request candidate emission.
Dependencies: app-builder contracts and deterministic app-builder helpers.
Invariants:
  - Pipeline planning is side-effect free.
  - Generated software requests are patch_test_review candidates only.
  - Direct deployment and commit-candidate requests are excluded.
"""

from __future__ import annotations

from mcoi_runtime.contracts.app_builder import AppTaskGraph, ArchitectureSpec, ProductSpec
from mcoi_runtime.core.app_builder.architecture_spec import draft_architecture_spec
from mcoi_runtime.core.app_builder.task_graph import build_app_task_graph, software_requests_from_task_graph
from mcoi_runtime.domain_adapters.software_dev import SoftwareRequest


def plan_app_build(product_spec: ProductSpec, *, repository: str, target_branch: str = "main", architecture_spec: ArchitectureSpec | None = None) -> tuple[ArchitectureSpec, AppTaskGraph, tuple[SoftwareRequest, ...]]:
    """Return architecture, task graph, and software-change request candidates."""
    architecture = architecture_spec or draft_architecture_spec(product_spec)
    graph = build_app_task_graph(product_spec, architecture)
    requests = software_requests_from_task_graph(graph, repository=repository, target_branch=target_branch)
    return architecture, graph, requests
