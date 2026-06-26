#!/usr/bin/env python3
"""Validate the Agentic Service Harness readiness map.

Purpose: keep the readiness-map-only closure artifact explicit, ordered, and
planning-only before any read-model, UI, mutation endpoint, or live adapter
implementation begins.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md.
Invariants:
  - The map contains the required readiness sections and scale.
  - RepositoryConnection remains closed as a read-only READY surface.
  - AgentRun remains closed as a read-only lifecycle READY surface.
  - ApprovalRequest remains closed as a read-only gateway binding surface.
  - Receipt remains closed as a read-only append-disabled projection.
  - EvidenceBundle remains closed as a read-only AgentRun-indexed projection.
  - LoopStatus remains closed as a read-only projection.
  - Task creation admission remains closed as an admission-only READY surface.
  - Task record write UAO admission remains closed as an admission-only
    READY surface.
  - Receipt-store append preflight remains closed as an admission-only
    READY surface.
  - The first next PR advances to executed test receipt admission after
    receipt-store append preflight closes.
  - Dashboard, mutation endpoint, external adapter, and high-risk authority
    remain denied by default.
  - The map does not contain API mutation route strings or route decorators.
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
DEFAULT_MAP = REPO_ROOT / "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"

REQUIRED_SECTIONS = (
    "# Mullusi Agentic Service Harness Readiness Map",
    "## Closure Evidence",
    "## Readiness Scale",
    "## Area Summary",
    "## 1. Public API Foundation - READY",
    "## 2. User/Project/Tenant Model - PARTIAL",
    "## 3. Agent Service Harness Contract - PARTIAL",
    "## 4. First MVP Adapter Path - PARTIAL",
    "## 5. Permission And Authority Model - READY",
    "## 6. Sandbox/Workspace Safety - PARTIAL",
    "## 7. Receipt And Evidence Model - PARTIAL",
    "## 8. Dashboard/UI Requirements - PARTIAL",
    "## 9. Explicit Non-Goals For The First Harness Phase - READY",
    "## Smallest Next PR Sequence",
    "## Governance Decision",
)
REQUIRED_STATUSES = ("READY", "PARTIAL", "MISSING")
REQUIRED_READY_SYMBOLS = (
    "RepositoryConnection",
    "AgentRun",
    "ApprovalRequest",
    "Receipt",
    "AgentAdapter",
    "EvidenceBundle",
    "LoopStatus",
)
REQUIRED_PARTIAL_SYMBOLS = (
    "WorkspaceSandbox",
    "AgentRunReceipt",
    "LoopStatus",
    "ResultSummary",
)
REQUIRED_DENIALS = (
    "Do not start the dashboard yet.",
    "Do not add mutation endpoints yet.",
    "Do not integrate Claude Code or OpenClaw yet.",
    "Do not allow merge, deploy, DNS, secret, destructive operation, unrestricted automation, or email-send authority by default.",
)
REQUIRED_REFRESH_FIELDS = (
    "Current `origin/main`:",
    "Open PRs after readiness-map refresh:",
)
REQUIRED_REPOSITORY_CONNECTION_TERMS = (
    "durable GitHub App installation",
    "revocation",
    "redacted credential bindings",
    "provider",
    "repository id/name",
    "installation ref",
    "scopes",
    "revocation state",
    "default branch",
    "no secret serialization",
)
REQUIRED_AGENT_RUN_TERMS = (
    "lifecycle state",
    "created and updated timestamps",
    "transition receipt refs",
    "terminal-state flag",
    "read-only query ref",
    "no adapter execution",
    "no branch creation",
    "no pull-request creation",
    "no external-effect authority",
)
REQUIRED_APPROVAL_REQUEST_TERMS = (
    "approval request id/ref",
    "gateway approval ref",
    "requested evidence ref",
    "response-record requirement",
    "no collected approval",
    "no granted authority",
)
REQUIRED_GITHUB_TASK_INTAKE_TERMS = (
    "GitHub repo task intake PR",
    "agentic_service_harness_github_repo_task_intake",
    "repository connection and read-only task scope",
    "denying adapter execution",
    "receipt append",
    "terminal closure",
)
REQUIRED_DASHBOARD_DATA_CONTRACT_TERMS = (
    "Dashboard data contract PR",
    "agentic_service_harness_dashboard_data_contract",
    "read-only dashboard data contract",
    "seven display-only widget contracts",
    "dashboard UI creation remains blocked",
    "route registration remains blocked",
)
REQUIRED_ADAPTER_REGISTRY_CONTRACT_TERMS = (
    "Adapter registry contract PR",
    "agentic_service_harness_adapter_registry_contract",
    "contract-only GitHub/Codex-style adapter entries",
    "subprocess execution",
    "connector calls",
    "external model execution",
    "branch writes",
    "PR creation",
    "receipt append",
    "terminal closure remain blocked",
)
REQUIRED_EVIDENCE_BUNDLE_PROJECTION_TERMS = (
    "EvidenceBundle projection PR",
    "agentic_service_harness_evidence_bundle_projection",
    "groups command logs, test logs, diff refs, policy refs, receipt refs, and source read-model refs by AgentRun id",
    "log ingestion",
    "receipt-store append",
    "adapter execution",
    "connector calls",
    "branch writes",
    "PR creation",
    "terminal closure remain blocked",
)
REQUIRED_LOOPSTATUS_PROJECTION_TERMS = (
    "LoopStatus",
    "Harness LoopStatus projection",
    "holistic loop read-model output",
    "loop registration",
    "status transition",
    "task creation routes",
    "mutation endpoints",
    "terminal closure remain denied",
)
REQUIRED_TASK_CREATION_ADMISSION_TERMS = (
    "Task creation admission preflight PR",
    "agentic_service_harness_task_creation_admission_preflight",
    "source task, read-model, approval, and evidence refs",
    "task creation route",
    "task record write",
    "branch workspace creation",
    "receipt append",
    "secret serialization",
    "terminal closure remain blocked",
    "denying user-facing task route admission and task writes",
)
REQUIRED_APPROVED_BRANCH_WORKSPACE_TERMS = (
    "Approved branch workspace creation preflight PR",
    "agentic_service_harness_approved_branch_workspace_creation_preflight",
    "task creation admission, temporary branch workspace, workspace sandbox, approval, UAO, cleanup, and next evidence refs",
    "branch workspace creation",
    "filesystem writes",
    "adapter execution",
    "connector calls",
    "receipt append",
    "secret serialization",
    "terminal closure remain blocked",
    "dry-run test runner plan receipt",
)
REQUIRED_DRY_RUN_TEST_RUNNER_PLAN_TERMS = (
    "Dry-run test runner plan receipt PR",
    "agentic_service_harness_dry_run_test_runner_plan_receipt",
    "selected validator and pytest commands",
    "command execution",
    "subprocess execution",
    "test result claims",
    "coverage claims",
    "filesystem writes",
    "adapter execution",
    "connector calls",
    "receipt append",
    "secret serialization",
    "terminal closure remain blocked",
    "task record write UAO admission preflight",
)
REQUIRED_TASK_RECORD_WRITE_UAO_TERMS = (
    "Task record write UAO admission preflight PR",
    "agentic_service_harness_task_record_write_uao_admission_preflight",
    "tenant/project identity",
    "idempotency",
    "rollback",
    "receipt-store write-path",
    "task record writes",
    "runtime state writes",
    "mutation routes",
    "terminal closure remain blocked",
)
REQUIRED_RECEIPT_STORE_APPEND_PREFLIGHT_TERMS = (
    "Receipt-store append preflight PR",
    "agentic_service_harness_receipt_store_append_preflight",
    "append audit",
    "writer registration",
    "write-path",
    "idempotency",
    "durability replay",
    "redaction",
    "receipt-store append",
    "raw payloads",
    "terminal closure remain blocked",
)
FORBIDDEN_PATTERNS = (
    ("mutation_route", re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)),
    ("fastapi_mutation_decorator", re.compile(r"@\w+\.(?:post|put|patch|delete)\(", re.IGNORECASE)),
    ("route_implementation", re.compile(r"\b(?:router|app)\.(?:post|put|patch|delete)\(", re.IGNORECASE)),
    ("ui_enablement", re.compile(r"\bui_created=true\b", re.IGNORECASE)),
    ("mutation_enablement", re.compile(r"\bmutation_endpoints_admitted=true\b", re.IGNORECASE)),
    ("external_adapter_enablement", re.compile(r"\bexternal_adapter_integrated=true\b", re.IGNORECASE)),
    ("high_risk_enablement", re.compile(r"\bdefault_high_risk_authority=true\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ReadinessMapValidation:
    """Deterministic validation result for the readiness map."""

    ok: bool
    errors: tuple[str, ...]
    map_path: str
    required_section_count: int
    required_status_count: int
    required_ready_symbol_count: int
    required_partial_symbol_count: int
    required_denial_count: int

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_readiness_map(map_path: Path = DEFAULT_MAP) -> ReadinessMapValidation:
    """Validate that the readiness map is complete and planning-only."""
    errors: list[str] = []
    try:
        map_text = map_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ReadinessMapValidation(
            ok=False,
            errors=(f"map load failed: {exc}",),
            map_path=_path_label(map_path),
            required_section_count=0,
            required_status_count=0,
            required_ready_symbol_count=0,
            required_partial_symbol_count=0,
            required_denial_count=0,
        )

    _require_all(map_text, REQUIRED_SECTIONS, "section", errors)
    _require_all(map_text, REQUIRED_STATUSES, "status", errors)
    _require_all(map_text, REQUIRED_READY_SYMBOLS, "ready_symbol", errors)
    _require_all(map_text, REQUIRED_PARTIAL_SYMBOLS, "partial_symbol", errors)
    _require_all(map_text, REQUIRED_DENIALS, "denial", errors)
    _require_all(map_text, REQUIRED_REFRESH_FIELDS, "refresh_field", errors)
    _require_all(
        map_text,
        REQUIRED_REPOSITORY_CONNECTION_TERMS,
        "repository_connection_term",
        errors,
    )
    _require_all(map_text, REQUIRED_AGENT_RUN_TERMS, "agent_run_term", errors)
    _require_all(map_text, REQUIRED_APPROVAL_REQUEST_TERMS, "approval_request_term", errors)
    _require_all(map_text, REQUIRED_GITHUB_TASK_INTAKE_TERMS, "github_task_intake_term", errors)
    _require_all(
        map_text,
        REQUIRED_DASHBOARD_DATA_CONTRACT_TERMS,
        "dashboard_data_contract_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_ADAPTER_REGISTRY_CONTRACT_TERMS,
        "adapter_registry_contract_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_EVIDENCE_BUNDLE_PROJECTION_TERMS,
        "evidence_bundle_projection_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_LOOPSTATUS_PROJECTION_TERMS,
        "loopstatus_projection_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_TASK_CREATION_ADMISSION_TERMS,
        "task_creation_admission_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_APPROVED_BRANCH_WORKSPACE_TERMS,
        "approved_branch_workspace_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_DRY_RUN_TEST_RUNNER_PLAN_TERMS,
        "dry_run_test_runner_plan_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_TASK_RECORD_WRITE_UAO_TERMS,
        "task_record_write_uao_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_RECEIPT_STORE_APPEND_PREFLIGHT_TERMS,
        "receipt_store_append_preflight_term",
        errors,
    )
    _validate_forbidden_patterns(map_text, errors)
    _validate_repository_connection_ready(map_text, errors)
    _validate_agent_run_ready(map_text, errors)
    _validate_approval_request_ready(map_text, errors)
    _validate_receipt_ready(map_text, errors)
    _validate_agent_adapter_ready(map_text, errors)
    _validate_evidence_bundle_ready(map_text, errors)
    _validate_loopstatus_ready(map_text, errors)
    _validate_receipt_projection_pr_ready(map_text, errors)
    _validate_task_creation_admission_ready(map_text, errors)
    _validate_approved_branch_workspace_ready(map_text, errors)
    _validate_dry_run_test_runner_plan_ready(map_text, errors)
    _validate_task_record_write_uao_ready(map_text, errors)
    _validate_receipt_store_append_preflight_ready(map_text, errors)
    _validate_next_pr_sequence(map_text, errors)
    _validate_current_main_ref(map_text, errors)
    _validate_open_pr_queue_boundary(map_text, errors)

    return ReadinessMapValidation(
        ok=not errors,
        errors=tuple(errors),
        map_path=_path_label(map_path),
        required_section_count=len(REQUIRED_SECTIONS),
        required_status_count=len(REQUIRED_STATUSES),
        required_ready_symbol_count=len(REQUIRED_READY_SYMBOLS),
        required_partial_symbol_count=len(REQUIRED_PARTIAL_SYMBOLS),
        required_denial_count=len(REQUIRED_DENIALS),
    )


def _require_all(
    map_text: str,
    required_values: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    for required_value in required_values:
        if required_value not in map_text:
            errors.append(f"missing {label}: {required_value}")


def _validate_forbidden_patterns(map_text: str, errors: list[str]) -> None:
    for pattern_name, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(map_text):
            errors.append(f"forbidden {pattern_name}")


def _validate_repository_connection_ready(map_text: str, errors: list[str]) -> None:
    ready_row = re.search(
        r"^\| RepositoryConnection \| READY \| .+ \| None\. \|$",
        map_text,
        re.MULTILINE,
    )
    if ready_row is None:
        errors.append("missing ready row: RepositoryConnection read model")


def _validate_agent_run_ready(map_text: str, errors: list[str]) -> None:
    ready_row = re.search(
        r"^\| AgentRun \| READY \| .+ \| None\. \|$",
        map_text,
        re.MULTILINE,
    )
    if ready_row is None:
        errors.append("missing ready row: AgentRun lifecycle read model")


def _validate_approval_request_ready(map_text: str, errors: list[str]) -> None:
    ready_row = re.search(
        r"^\| ApprovalRequest \| READY \| .+ \| None\. \|$",
        map_text,
        re.MULTILINE,
    )
    if ready_row is None:
        errors.append("missing ready row: ApprovalRequest projection binding")


def _validate_agent_adapter_ready(map_text: str, errors: list[str]) -> None:
    ready_row = re.search(
        r"^\| AgentAdapter \| READY \| .+ \| None for contract-only registry\. \|$",
        map_text,
        re.MULTILINE,
    )
    if ready_row is None:
        errors.append("missing ready row: AgentAdapter contract-only registry")


def _validate_evidence_bundle_ready(map_text: str, errors: list[str]) -> None:
    ready_row = re.search(
        r"^\| EvidenceBundle \| READY \| .+ \| None for read-only projection\. \|$",
        map_text,
        re.MULTILINE,
    )
    if ready_row is None:
        errors.append("missing ready row: EvidenceBundle read-only projection")


def _validate_receipt_ready(map_text: str, errors: list[str]) -> None:
    ready_row = re.search(
        r"^\| Receipt \| READY \| .+ \| None for read-only projection\..+ \|$",
        map_text,
        re.MULTILINE,
    )
    if ready_row is None:
        errors.append("missing ready row: Receipt read-only projection")


def _validate_loopstatus_ready(map_text: str, errors: list[str]) -> None:
    ready_row = re.search(
        r"^\| LoopStatus \| READY \| .+ \| None for read-only projection\. \|$",
        map_text,
        re.MULTILINE,
    )
    if ready_row is None:
        errors.append("missing ready row: LoopStatus read-only projection")


def _validate_receipt_projection_pr_ready(map_text: str, errors: list[str]) -> None:
    receipt_projection_row = re.search(
        r"^\| Receipt projection PR \| READY \| .+receipt-store append.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if receipt_projection_row is None:
        errors.append("missing ready row: Receipt projection PR")


def _validate_task_creation_admission_ready(map_text: str, errors: list[str]) -> None:
    closure_row = re.search(
        r"^\| Task creation admission preflight PR \| READY \| .+task creation route.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Task creation admission preflight PR")

    dashboard_row = re.search(
        r"^\| create agent task \| READY \| .+denying user-facing task route admission and task writes\. \| None for admission preflight\..+ \|$",
        map_text,
        re.MULTILINE,
    )
    if dashboard_row is None:
        errors.append("missing ready row: create agent task admission preflight")


def _validate_approved_branch_workspace_ready(map_text: str, errors: list[str]) -> None:
    closure_row = re.search(
        r"^\| Approved branch workspace creation preflight PR \| READY \| .+branch workspace creation.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Approved branch workspace creation preflight PR")


def _validate_dry_run_test_runner_plan_ready(map_text: str, errors: list[str]) -> None:
    closure_row = re.search(
        r"^\| Dry-run test runner plan receipt PR \| READY \| .+selected validator and pytest commands.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Dry-run test runner plan receipt PR")

    test_runner_row = re.search(
        r"^\| Test runner \| READY \| .+agentic_service_harness_dry_run_test_runner_plan_receipt.+ \| None for plan-only command selection\..+ \|$",
        map_text,
        re.MULTILINE,
    )
    if test_runner_row is None:
        errors.append("missing ready row: Test runner dry-run plan receipt")


def _validate_task_record_write_uao_ready(map_text: str, errors: list[str]) -> None:
    closure_row = re.search(
        r"^\| Task record write UAO admission preflight PR \| READY \| .+task record writes.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Task record write UAO admission preflight PR")


def _validate_receipt_store_append_preflight_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Receipt-store append preflight PR \| READY \| .+receipt-store append.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Receipt-store append preflight PR")


def _validate_next_pr_sequence(map_text: str, errors: list[str]) -> None:
    sequence_markers = (
        "harness(tests): add executed test receipt admission preflight",
        "harness(diffs): add non-empty diff receipt admission preflight",
    )
    positions: list[int] = []
    for marker in sequence_markers:
        position = map_text.find(marker)
        if position == -1:
            errors.append(f"missing next PR marker: {marker}")
        else:
            positions.append(position)
    if positions and positions != sorted(positions):
        errors.append("next PR sequence is not ordered")


def _validate_current_main_ref(map_text: str, errors: list[str]) -> None:
    current_main = re.search(
        r"^Current `origin/main`: `[0-9a-f]{40}`$",
        map_text,
        re.MULTILINE,
    )
    if current_main is None:
        errors.append("missing current origin main ref")


def _validate_open_pr_queue_boundary(map_text: str, errors: list[str]) -> None:
    open_pr_queue = re.search(
        r"^Open PRs after readiness-map refresh: .+ outside this map-only closure\.$",
        map_text,
        re.MULTILINE,
    )
    if open_pr_queue is None:
        errors.append("missing open PR queue map-only boundary")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the readiness map validator."""
    args = build_arg_parser().parse_args(argv)
    validation = validate_readiness_map(args.map)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READINESS MAP VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READINESS MAP INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
