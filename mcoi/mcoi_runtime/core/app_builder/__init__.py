"""Purpose: app-builder planning helpers for governed software tasks.
Governance scope: product specs, architecture specs, task graphs, pull-request
    candidates, and bounded software-change request candidates.
Dependencies: app-builder helpers and software-dev domain adapter contracts.
Invariants:
  - Helpers are deterministic and side-effect free.
  - Generated software requests use patch_test_review mode.
  - Direct deployment, git push, and unapproved PR opening are excluded.
"""

from .architecture_spec import draft_architecture_spec
from .codegen_pipeline import plan_app_build
from .pr_candidate import (
    apply_pull_request_review_decision,
    build_pull_request_candidate,
    create_pull_request_review_request,
    github_pull_request_open_payload,
)
from .product_spec import product_spec_from_mapping
from .task_graph import build_app_task_graph, software_requests_from_task_graph

__all__ = [
    "apply_pull_request_review_decision",
    "build_app_task_graph",
    "build_pull_request_candidate",
    "create_pull_request_review_request",
    "draft_architecture_spec",
    "github_pull_request_open_payload",
    "plan_app_build",
    "product_spec_from_mapping",
    "software_requests_from_task_graph",
]
