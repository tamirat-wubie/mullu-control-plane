#!/usr/bin/env python3
"""Validate the Agentic Service Harness read-model binding plan.

Purpose: keep the post-readiness-map harness binding artifact planning-only,
read-only, and free of UI, mutation endpoints, external adapter integrations,
or default high-risk authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md.
Invariants:
  - The plan names every required harness symbol and source contract.
  - The plan keeps UI, mutation endpoints, external adapters, and high-risk
    authority explicitly false.
  - The plan does not contain API mutation route strings or route decorators.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = REPO_ROOT / "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md"

REQUIRED_SECTIONS = (
    "# Mullusi Agentic Service Harness Read Model Binding Plan",
    "## Objective",
    "## Scope",
    "## Source Contracts",
    "## Read Model Bindings",
    "## State Machine",
    "## Authority Boundary",
    "## Evidence And Receipt Binding",
    "## Persistence Plan",
    "## Non-Goals",
    "## Smallest Next PR Sequence",
    "## Acceptance Gates",
    "## Status",
)
REQUIRED_SYMBOLS = (
    "User",
    "Organization",
    "Project",
    "RepositoryConnection",
    "AgentTask",
    "AgentAdapter",
    "WorkspaceSandbox",
    "AgentRun",
    "ApprovalGate",
    "AgentRunReceipt",
    "EvidenceBundle",
    "ResultSummary",
    "PermissionModel",
    "Receipt",
    "LoopStatus",
)
REQUIRED_SOURCE_REFS = (
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_LIVE_TASK_RUN_PRODUCER_EVIDENCE.md",
    "schemas/agentic_service_harness.schema.json",
    "docs/maps/MULLUSI_ASK_TO_RECEIPT_FLOW_MAP.md",
    "docs/maps/MULLUSI_EVIDENCE_RECEIPT_MAP.md",
    "docs/FOUNDATION_MODE.md",
)
REQUIRED_FALSE_FLAGS = (
    "planning_only=true",
    "ui_created=false",
    "mutation_endpoints_admitted=false",
    "external_adapter_integrated=false",
    "default_high_risk_authority=false",
    "merge=false",
    "deploy=false",
    "dns_mutation=false",
    "secret_mutation=false",
    "destructive_operation=false",
)
REQUIRED_NON_GOALS = (
    "Dashboard UI",
    "Mutation endpoints",
    "GitHub branch creation",
    "Pull request creation",
    "Claude Code integration",
    "OpenClaw integration",
    "Email sending",
    "Deployment approval",
    "DNS mutation",
    "Secret mutation",
    "Billing",
    "Marketplace",
)
FORBIDDEN_PATTERNS = (
    ("mutation_route", re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)),
    ("fastapi_mutation_decorator", re.compile(r"@\w+\.(?:post|put|patch|delete)\(", re.IGNORECASE)),
    ("route_implementation", re.compile(r"\b(?:router|app)\.(?:post|put|patch|delete)\(", re.IGNORECASE)),
    ("external_adapter_enablement", re.compile(r"\bexternal_adapter_integrated=true\b", re.IGNORECASE)),
    ("ui_enablement", re.compile(r"\bui_created=true\b", re.IGNORECASE)),
    ("mutation_enablement", re.compile(r"\bmutation_endpoints_admitted=true\b", re.IGNORECASE)),
    ("high_risk_enablement", re.compile(r"\bdefault_high_risk_authority=true\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ReadModelBindingPlanValidation:
    """Deterministic validation result for the read-model binding plan."""

    ok: bool
    errors: tuple[str, ...]
    plan_path: str
    required_section_count: int
    required_symbol_count: int
    required_false_flag_count: int
    required_non_goal_count: int

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_read_model_binding_plan(
    plan_path: Path = DEFAULT_PLAN,
) -> ReadModelBindingPlanValidation:
    """Validate that the binding plan is complete and planning-only."""
    errors: list[str] = []
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ReadModelBindingPlanValidation(
            ok=False,
            errors=(f"plan load failed: {exc}",),
            plan_path=_path_label(plan_path),
            required_section_count=0,
            required_symbol_count=0,
            required_false_flag_count=0,
            required_non_goal_count=0,
        )

    _require_all(plan_text, REQUIRED_SECTIONS, "section", errors)
    _require_all(plan_text, REQUIRED_SYMBOLS, "symbol", errors)
    _require_all(plan_text, REQUIRED_SOURCE_REFS, "source_ref", errors)
    _require_all(plan_text, REQUIRED_FALSE_FLAGS, "false_flag", errors)
    _require_all(plan_text, REQUIRED_NON_GOALS, "non_goal", errors)
    _validate_forbidden_patterns(plan_text, errors)
    _validate_next_pr_sequence(plan_text, errors)

    return ReadModelBindingPlanValidation(
        ok=not errors,
        errors=tuple(errors),
        plan_path=_path_label(plan_path),
        required_section_count=len(REQUIRED_SECTIONS),
        required_symbol_count=len(REQUIRED_SYMBOLS),
        required_false_flag_count=len(REQUIRED_FALSE_FLAGS),
        required_non_goal_count=len(REQUIRED_NON_GOALS),
    )


def _require_all(
    plan_text: str,
    required_values: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    for required_value in required_values:
        if required_value not in plan_text:
            errors.append(f"missing {label}: {required_value}")


def _validate_forbidden_patterns(plan_text: str, errors: list[str]) -> None:
    for pattern_name, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(plan_text):
            errors.append(f"forbidden {pattern_name}")


def _validate_next_pr_sequence(plan_text: str, errors: list[str]) -> None:
    sequence_markers = (
        "read-model binding plan",
        "read-only harness read-model schemas",
        "read-only harness fixture projections",
        "local read-only persistence rehearsal",
        "read-only status route design",
    )
    positions: list[int] = []
    for marker in sequence_markers:
        position = plan_text.find(marker)
        if position == -1:
            errors.append(f"missing next PR marker: {marker}")
        else:
            positions.append(position)
    if positions and positions != sorted(positions):
        errors.append("next PR sequence is not ordered")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the read-model binding plan validator."""
    args = build_arg_parser().parse_args(argv)
    validation = validate_read_model_binding_plan(args.plan)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ MODEL BINDING PLAN VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READ MODEL BINDING PLAN INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
