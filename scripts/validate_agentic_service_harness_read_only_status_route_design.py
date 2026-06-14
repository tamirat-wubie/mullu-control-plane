#!/usr/bin/env python3
"""Validate Agentic Service Harness read-only status route design.

Purpose: keep the first harness status route artifact design-only and bounded
to a read-model projection before any route implementation, UI, mutation
endpoint, external adapter, or high-risk authority is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: MULLUSI_AGENTIC_SERVICE_HARNESS_READ_ONLY_STATUS_ROUTE_DESIGN.md.
Invariants:
  - The design names exactly one read-only GET route path.
  - The design binds response fields to existing read-model and persistence
    rehearsal artifacts.
  - The design does not contain route decorators, mutation route strings, or
    enablement flags for implementation, UI, external adapters, or high-risk
    authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESIGN = REPO_ROOT / "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_ONLY_STATUS_ROUTE_DESIGN.md"

REQUIRED_SECTIONS = (
    "# Mullusi Agentic Service Harness Read-Only Status Route Design",
    "## Objective",
    "## Route Contract",
    "## Source Bindings",
    "## Response Projection",
    "## State Behavior",
    "## Authority Boundary",
    "## Error And Staleness Behavior",
    "## Non-Goals",
    "## Validation",
    "## Status",
)
REQUIRED_SOURCE_REFS = (
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md",
    "examples/agentic_service_harness_read_models.foundation.json",
    "schemas/agentic_service_harness_read_models.schema.json",
    "scripts/validate_agentic_service_harness_read_models.py",
    "scripts/validate_agentic_service_harness_read_model_projections.py",
    "scripts/validate_agentic_service_harness_read_model_integrity.py",
    "scripts/validate_agentic_service_harness_read_model_persistence.py",
    "docs/FOUNDATION_MODE.md",
)
REQUIRED_ROUTE_TERMS = (
    "`agentic_service_harness_status_read_model`",
    "`GET`",
    "`/api/v1/harness/status`",
    "`HEAD`",
    "`read_model`",
    "`read_only`",
)
REQUIRED_RESPONSE_FIELDS = (
    "`route_id`",
    "`route_version`",
    "`generated_at`",
    "`tenant_id`",
    "`organization_id`",
    "`project_id`",
    "`read_only`",
    "`report_is_not_terminal_closure`",
    "`terminal_closure_required`",
    "`status`",
    "`blockers`",
    "`accounts`",
    "`projects`",
    "`repositories`",
    "`runs`",
    "`approvals`",
    "`receipts`",
    "`evidence`",
    "`result_summaries`",
    "`permission_snapshot`",
    "`validators`",
    "`next_action`",
)
REQUIRED_BLOCKERS = (
    "`read_only_status_route_implementation_pending`",
    "`missing_read_model_source`",
    "`missing_persistence_rehearsal`",
    "`missing_tenant_or_project_scope`",
    "`high_risk_authority_not_allowed`",
    "`secret_value_serialization_not_allowed`",
    "`terminal_closure_claim_not_allowed`",
)
REQUIRED_FALSE_FLAGS = (
    "route_design_only=true",
    "route_implemented=false",
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
    "Route implementation",
    "Dashboard UI",
    "Mutation endpoint",
    "Task creation endpoint",
    "Dry-run execution endpoint",
    "Branch write endpoint",
    "Pull-request creation endpoint",
    "External adapter integration",
    "Deployment approval",
    "DNS mutation",
    "Secret mutation",
    "Billing or marketplace behavior",
)
FORBIDDEN_PATTERNS = (
    ("route_decorator", re.compile(r"@\w+\.(?:get|post|put|patch|delete|head)\(", re.IGNORECASE)),
    ("route_registration", re.compile(r"\b(?:router|app)\.(?:get|post|put|patch|delete|head)\(", re.IGNORECASE)),
    ("mutation_route_string", re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)),
    ("route_implementation_enablement", re.compile(r"\broute_implemented=true\b", re.IGNORECASE)),
    ("ui_enablement", re.compile(r"\bui_created=true\b", re.IGNORECASE)),
    ("mutation_enablement", re.compile(r"\bmutation_endpoints_admitted=true\b", re.IGNORECASE)),
    ("external_adapter_enablement", re.compile(r"\bexternal_adapter_integrated=true\b", re.IGNORECASE)),
    ("high_risk_enablement", re.compile(r"\bdefault_high_risk_authority=true\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ReadOnlyStatusRouteDesignValidation:
    """Deterministic validation result for the read-only status route design."""

    ok: bool
    errors: tuple[str, ...]
    design_path: str
    required_section_count: int
    required_source_ref_count: int
    required_response_field_count: int
    required_false_flag_count: int

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_read_only_status_route_design(
    design_path: Path = DEFAULT_DESIGN,
) -> ReadOnlyStatusRouteDesignValidation:
    """Validate that the status route artifact is complete and design-only."""
    errors: list[str] = []
    try:
        design_text = design_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ReadOnlyStatusRouteDesignValidation(
            ok=False,
            errors=(f"design load failed: {exc}",),
            design_path=_path_label(design_path),
            required_section_count=0,
            required_source_ref_count=0,
            required_response_field_count=0,
            required_false_flag_count=0,
        )

    _require_all(design_text, REQUIRED_SECTIONS, "section", errors)
    _require_all(design_text, REQUIRED_SOURCE_REFS, "source_ref", errors)
    _require_all(design_text, REQUIRED_ROUTE_TERMS, "route_term", errors)
    _require_all(design_text, REQUIRED_RESPONSE_FIELDS, "response_field", errors)
    _require_all(design_text, REQUIRED_BLOCKERS, "blocker", errors)
    _require_all(design_text, REQUIRED_FALSE_FLAGS, "false_flag", errors)
    _require_all(design_text, REQUIRED_NON_GOALS, "non_goal", errors)
    _validate_route_occurrence(design_text, errors)
    _validate_forbidden_patterns(design_text, errors)

    return ReadOnlyStatusRouteDesignValidation(
        ok=not errors,
        errors=tuple(errors),
        design_path=_path_label(design_path),
        required_section_count=len(REQUIRED_SECTIONS),
        required_source_ref_count=len(REQUIRED_SOURCE_REFS),
        required_response_field_count=len(REQUIRED_RESPONSE_FIELDS),
        required_false_flag_count=len(REQUIRED_FALSE_FLAGS),
    )


def _require_all(
    design_text: str,
    required_values: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    for required_value in required_values:
        if required_value not in design_text:
            errors.append(f"missing {label}: {required_value}")


def _validate_route_occurrence(design_text: str, errors: list[str]) -> None:
    route_count = design_text.count("/api/v1/harness/status")
    if route_count != 1:
        errors.append(f"route path must appear exactly once, observed {route_count}")
    if "GET /api/v1/harness/status" in design_text:
        errors.append("route path must stay in the route contract table, not command syntax")


def _validate_forbidden_patterns(design_text: str, errors: list[str]) -> None:
    for pattern_name, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(design_text):
            errors.append(f"forbidden {pattern_name}")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the read-only status route design validator."""
    args = build_arg_parser().parse_args(argv)
    validation = validate_read_only_status_route_design(args.design)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ ONLY STATUS ROUTE DESIGN VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READ ONLY STATUS ROUTE DESIGN INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
