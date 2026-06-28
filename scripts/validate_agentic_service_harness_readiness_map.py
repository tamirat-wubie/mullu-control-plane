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
  - Executed-test receipt admission remains closed as an admission-only
    READY surface.
  - Non-empty diff receipt admission remains closed as an admission-only
    READY surface.
  - GitHub PR admission remains closed as an admission-only READY surface.
  - GitHub PR CI gate before ready-for-review remains closed as a
    non-authorizing witness surface.
  - GitHub PR effect reconciliation remains closed as a read-only evidence
    surface.
  - GitHub PR terminal closure remains closed as a bounded certificate/gate/
    decision/rejection/request/minting/read-model evidence chain.
  - Approved branch workspace creation authority is bound before observed
    workspace creation, filesystem write, adapter execution, receipt append,
    pull-request creation, or terminal closure evidence.
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
REQUIRED_APPROVED_BRANCH_WORKSPACE_AUTHORITY_TERMS = (
    "Approved branch workspace creation authority binding PR",
    "agentic_service_harness_approved_branch_workspace_creation_authority_binding",
    "one-workspace confined creation authority envelope",
    "operator approval",
    "UAO",
    "cleanup",
    "rollback",
    "redaction",
    "path-confinement evidence",
    "actual workspace creation",
    "filesystem writes",
    "branch pushes",
    "pull-request creation",
    "adapter execution",
    "connector calls",
    "receipt append",
    "mutation routes",
    "secret serialization",
    "destructive operations",
    "terminal closure remain blocked",
    "approved branch workspace creation observation receipt",
)
REQUIRED_APPROVED_BRANCH_WORKSPACE_OBSERVATION_TERMS = (
    "Approved branch workspace creation observation receipt PR",
    "agentic_service_harness_approved_branch_workspace_creation_observation_receipt",
    "created one confined branch workspace",
    "source authority binding",
    "workspace path confinement",
    "post-create observation",
    "filesystem writes",
    "branch pushes",
    "pull-request creation",
    "adapter execution",
    "connector calls",
    "receipt append",
    "mutation routes",
    "secret serialization",
    "destructive operations",
    "terminal closure remain blocked",
    "dry-run test execution observation",
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
    "dry-run test execution observation",
)
REQUIRED_DRY_RUN_TEST_EXECUTION_OBSERVATION_TERMS = (
    "Dry-run test execution observation receipt PR",
    "agentic_service_harness_dry_run_test_execution_observation_receipt",
    "four selected dry-run commands",
    "zero exit-code evidence",
    "redacted output refs",
    "output digest refs",
    "executed-test receipt admission",
    "receipt append",
    "filesystem-write authority",
    "branch pushes",
    "pull-request creation",
    "adapter execution",
    "connector calls",
    "mutation routes",
    "secret serialization",
    "terminal closure remain blocked",
    "filesystem write admission",
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
REQUIRED_EXECUTED_TEST_RECEIPT_ADMISSION_TERMS = (
    "Executed test receipt admission preflight PR",
    "agentic_service_harness_executed_test_receipt_admission_preflight",
    "dry-run test runner plan",
    "approved branch workspace preflight",
    "receipt-store append preflight",
    "command timeout",
    "subprocess redaction",
    "exit-code",
    "output-digest",
    "executed test receipt",
    "test result claims",
    "coverage claims",
    "raw test output",
    "terminal closure remain blocked",
)
REQUIRED_NON_EMPTY_DIFF_RECEIPT_ADMISSION_TERMS = (
    "Non-empty diff receipt admission preflight PR",
    "agentic_service_harness_non_empty_diff_receipt_admission_preflight",
    "zero-diff actual diff collection receipt",
    "branch/workspace authority",
    "cleanup",
    "redaction",
    "UAO admission",
    "receipt-store write-path",
    "non-empty diff receipt",
    "raw diff bodies",
    "raw file content",
    "connector calls",
    "terminal closure remain blocked",
)
REQUIRED_FILESYSTEM_WRITE_ADMISSION_TERMS = (
    "Filesystem write admission preflight PR",
    "agentic_service_harness_filesystem_write_admission_preflight",
    "dry-run test execution observation",
    "workspace authority",
    "rollback",
    "cleanup",
    "redaction",
    "UAO admission",
    "receipt-store write-path",
    "filesystem-write admission",
    "raw diff bodies",
    "raw file content",
    "connector calls",
    "terminal closure remain blocked",
)
REQUIRED_CONCRETE_FILESYSTEM_WRITE_EVIDENCE_CANDIDATE_TERMS = (
    "Concrete filesystem write evidence candidate PR",
    "agentic_service_harness_concrete_filesystem_write_evidence_candidate",
    "non-empty redacted changed-file and diff-summary evidence refs",
    "filesystem-write admission preflight",
    "non-empty diff admission preflight",
    "cleanup",
    "redaction",
    "UAO admission",
    "rollback",
    "receipt-store write-path",
    "filesystem-write admission",
    "filesystem write execution",
    "raw diff bodies",
    "raw file content",
    "PR creation",
    "terminal closure remain blocked",
)
REQUIRED_ACTUAL_FILESYSTEM_WRITE_RECEIPT_ADMISSION_TERMS = (
    "Actual filesystem write receipt admission PR",
    "agentic_service_harness_actual_filesystem_write_receipt_admission",
    "concrete filesystem-write evidence candidate",
    "cleanup",
    "rollback",
    "redaction",
    "UAO",
    "receipt-store write-path",
    "terminal certificate",
    "filesystem write execution",
    "raw diff bodies",
    "raw file content",
    "connector calls",
    "terminal closure remain blocked",
)
REQUIRED_REDACTED_FILESYSTEM_WRITE_EXECUTION_RECEIPT_TERMS = (
    "Redacted filesystem write execution receipt PR",
    "agentic_service_harness_redacted_filesystem_write_execution_receipt",
    "actual filesystem-write receipt admission",
    "concrete filesystem-write evidence candidate",
    "redacted execution output",
    "non-empty changed-file refs",
    "redacted diff bundle",
    "receipt-store write-path",
    "terminal certificate evidence",
    "filesystem-write receipt emission",
    "raw command output",
    "raw diff bodies",
    "raw file content",
    "connector calls",
    "terminal closure remain blocked",
)
REQUIRED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_BINDING_TERMS = (
    "Actual non-empty diff receipt binding PR",
    "agentic_service_harness_actual_non_empty_diff_receipt_binding",
    "redacted non-empty changed-file and diff refs",
    "redacted filesystem-write execution receipt",
    "non-empty diff file summary receipt",
    "actual non-empty diff receipt",
    "raw diff bodies",
    "raw file content",
    "receipt append",
    "PR creation",
    "terminal closure remain blocked",
)
REQUIRED_ACTUAL_DIFF_COLLECTION_RECEIPT_TERMS = (
    "Actual diff collection receipt admission PR",
    "agentic_service_harness_actual_diff_collection_receipt",
    "filesystem-write admission preflight",
    "actual diff collection admission preflight",
    "zero-diff actual diff receipt",
    "branch/workspace authority",
    "cleanup",
    "redaction",
    "UAO admission",
    "receipt-store write-path",
    "non-empty diff authority",
    "raw diff bodies",
    "raw file content",
    "terminal closure remain blocked",
)
REQUIRED_NON_EMPTY_DIFF_FILE_SUMMARY_RECEIPT_TERMS = (
    "Non-empty diff file summary receipt PR",
    "agentic_service_harness_non_empty_diff_file_summary_receipt",
    "non-empty diff admission",
    "filesystem-write admission",
    "zero-diff actual diff receipt evidence",
    "cleanup",
    "redaction",
    "UAO admission",
    "receipt-store write-path",
    "redacted diff bundle refs",
    "non-empty file summary emission",
    "raw diff bodies",
    "raw file content",
    "PR creation",
    "terminal closure remain blocked",
)
REQUIRED_GITHUB_PR_ADMISSION_TERMS = (
    "GitHub PR admission preflight PR",
    "agentic_service_harness_github_pr_admission_preflight",
    "GitHub task receipt-emitter dry-run",
    "operator approval",
    "branch-write authority",
    "UAO admission",
    "rollback",
    "CI evidence",
    "PR admission is denied",
    "branch writes",
    "PR creation",
    "repository writes",
    "adapter execution",
    "connector calls",
    "mutation routes",
    "secret material",
    "terminal closure fail closed",
)
REQUIRED_GITHUB_PR_ACTUAL_NON_EMPTY_DIFF_ADMISSION_BINDING_TERMS = (
    "GitHub PR actual non-empty diff admission binding PR",
    "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding",
    "GitHub PR admission preflight",
    "actual non-empty diff receipt binding",
    "redacted changed-file and diff refs",
    "PR admission input",
    "operator approval",
    "branch-write authority",
    "UAO admission",
    "terminal certificate evidence",
    "PR creation",
    "raw diff bodies",
    "raw file content",
    "terminal closure fail closed",
)
REQUIRED_GITHUB_PR_OPERATOR_APPROVAL_ACTUAL_DIFF_BINDING_TERMS = (
    "GitHub PR operator approval request actual-diff binding PR",
    "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding",
    "agentic_service_harness_github_pr_operator_approval_request",
    "GitHub PR actual non-empty diff admission binding",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "Approval remains AwaitingEvidence",
    "PR creation",
    "receipt-store append",
    "terminal closure fail closed",
)
REQUIRED_GITHUB_PR_OPERATOR_RESPONSE_ACTUAL_DIFF_BINDING_TERMS = (
    "GitHub PR operator response actual-diff binding PR",
    "agentic_service_harness_github_pr_operator_response_witness",
    "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "Operator response remains AwaitingEvidence",
    "branch-write authority",
    "PR creation",
    "raw diff bodies",
    "raw file content",
    "terminal closure fail closed",
)
REQUIRED_GITHUB_PR_BRANCH_WRITE_ACTUAL_DIFF_RESPONSE_BINDING_TERMS = (
    "GitHub PR branch-write authority actual-diff response binding PR",
    "agentic_service_harness_github_pr_branch_write_authority_binding",
    "actual-diff operator response witness",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "Branch-write authority remains AwaitingEvidence",
    "response satisfaction",
    "UAO admission",
    "PR creation",
    "raw diff bodies",
    "raw file content",
    "terminal closure fail closed",
)
REQUIRED_GITHUB_PR_BRANCH_WRITE_COMMAND_PREVIEW_RESPONSE_BINDING_TERMS = (
    "GitHub PR branch-write authority command-preview response binding PR",
    "agentic_service_harness_github_pr_branch_write_authority_binding",
    "command-preview-bound operator response witness",
    "operator response witness ref",
    "command-preview approval request binding ref",
    "redacted command preview",
    "argument vector template",
    "placeholder refs",
    "branch-write evidence ref",
    "Branch-write authority remains AwaitingEvidence",
    "PR command execution",
    "pull-request creation",
    "repository writes",
    "connector calls",
    "mutation routes",
    "receipt-store append",
    "secret material",
    "terminal closure remain blocked",
)
REQUIRED_GITHUB_PR_UAO_ACTUAL_DIFF_BRANCH_WRITE_BINDING_TERMS = (
    "GitHub PR UAO admission command-preview branch-write binding PR",
    "agentic_service_harness_github_pr_uao_admission_witness",
    "command-preview branch-write authority binding",
    "command-preview operator response binding",
    "redacted command preview",
    "argument vector template",
    "placeholder refs",
    "actual-diff branch-write authority binding",
    "actual-diff operator response witness",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "UAO PR admission remains AwaitingEvidence",
    "rollback planning",
    "PR creation",
    "raw diff bodies",
    "raw file content",
    "terminal closure fail closed",
)
REQUIRED_GITHUB_PR_ROLLBACK_ACTUAL_DIFF_UAO_BINDING_TERMS = (
    "GitHub PR repository-effect rollback command-preview UAO binding PR",
    "agentic_service_harness_github_pr_repository_effect_rollback_plan_witness",
    "command-preview UAO admission witness",
    "command-preview branch-write binding",
    "command-preview operator response binding",
    "redacted command preview",
    "argument vector template",
    "placeholder refs",
    "actual-diff UAO admission witness",
    "actual-diff branch-write authority binding",
    "actual-diff operator response witness",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "Repository-effect rollback remains AwaitingEvidence",
    "CI evidence",
    "PR creation",
    "raw diff bodies",
    "raw file content",
    "terminal closure fail closed",
)
REQUIRED_GITHUB_PR_CI_GATE_TERMS = (
    "GitHub PR CI gate before ready-for-review command-preview rollback binding PR",
    "agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness",
    "command-preview repository-effect rollback witness",
    "command-preview UAO admission witness",
    "command-preview branch-write binding",
    "command-preview operator response binding",
    "redacted command preview",
    "argument vector template",
    "placeholder refs",
    "actual-diff repository-effect rollback witness",
    "actual-diff UAO admission witness",
    "actual-diff branch-write authority binding",
    "actual-diff operator response witness",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "requested CI evidence ref",
    "required check result",
    "effect_reconciliation",
    "CI gate authority remains AwaitingEvidence",
    "no branch, PR, ready-for-review, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority",
)
REQUIRED_GITHUB_PR_EFFECT_RECONCILIATION_TERMS = (
    "GitHub PR effect reconciliation command-preview CI gate binding PR",
    "agentic_service_harness_github_pr_effect_reconciliation_witness",
    "command-preview CI gate before ready-for-review witness",
    "command-preview repository-effect rollback witness",
    "command-preview UAO admission witness",
    "command-preview branch-write binding",
    "command-preview operator response binding",
    "redacted command preview",
    "argument vector template",
    "placeholder refs",
    "actual-diff CI gate before ready-for-review witness",
    "actual-diff repository-effect rollback witness",
    "actual-diff UAO admission witness",
    "actual-diff branch-write authority binding",
    "actual-diff operator response witness",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "GitHub PR effect reconciliation evidence contract PR",
    "agentic_service_harness_github_pr_effect_reconciliation_evidence_contract",
    "GitHub PR effect reconciliation live evidence PR",
    "agentic_service_harness_github_pr_effect_reconciliation_live_evidence",
    "effect reconciliation remains AwaitingEvidence",
    "read-only GitHub PR state observation",
    "branch state, pull request state, required checks, merge state, and branch deletion state",
    "no branch, PR, ready-for-review, merge, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority",
    "granting no repository mutation, secret, destructive, or terminal closure authority",
)
REQUIRED_GITHUB_PR_TERMINAL_CLOSURE_TERMS = (
    "GitHub PR terminal closure certificate command-preview effect reconciliation binding PR",
    "agentic_service_harness_github_pr_terminal_closure_certificate_witness",
    "command-preview effect reconciliation witness",
    "command-preview CI gate before ready-for-review witness",
    "command-preview repository-effect rollback witness",
    "command-preview UAO admission witness",
    "command-preview branch-write binding",
    "command-preview operator response binding",
    "redacted command preview",
    "argument vector template",
    "placeholder refs",
    "actual-diff effect reconciliation witness",
    "actual-diff CI gate before ready-for-review witness",
    "actual-diff repository-effect rollback witness",
    "actual-diff UAO admission witness",
    "actual-diff branch-write authority binding",
    "actual-diff operator response witness",
    "actual non-empty diff receipt ref",
    "redacted changed-file refs",
    "redacted diff refs",
    "redacted output ref",
    "redacted diff bundle ref",
    "GitHub PR terminal closure certificate candidate actual-diff witness binding PR",
    "agentic_service_harness_github_pr_terminal_closure_certificate_candidate",
    "actual-diff terminal closure certificate witness",
    "actual-diff approval request binding",
    "GitHub PR terminal closure operator approval gate actual-diff candidate binding PR",
    "agentic_service_harness_github_pr_terminal_closure_operator_approval_gate",
    "GitHub PR terminal closure operator decision contract actual-diff approval gate binding PR",
    "agentic_service_harness_github_pr_terminal_closure_operator_decision_contract",
    "actual-diff operator approval gate evidence",
    "source approval gate binding id/ref",
    "GitHub PR terminal closure generic continuation rejection actual-diff decision contract binding PR",
    "agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection",
    "actual-diff decision contract evidence",
    "source decision contract binding id/ref",
    "actual-diff-bound generic rejection evidence",
    "GitHub PR terminal closure operator decision value request actual-diff generic rejection binding PR",
    "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request",
    "actual-diff-bound decision value request evidence",
    "GitHub PR terminal closure operator decision value record actual-diff request binding PR",
    "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record",
    "actual-diff-bound decision value record evidence",
    "GitHub PR terminal closure certificate minting actual-diff decision value record binding PR",
    "agentic_service_harness_github_pr_terminal_closure_certificate_minting",
    "terminal closure status remains AwaitingEvidence",
    "Candidate status remains AwaitingEvidence/operator-approval-bound",
    "certificate minting, repository mutation, connector calls, receipt-store append, secret serialization, destructive operation, and terminal closure remain blocked",
    "Operator approval remains required and uncollected",
    "Explicit operator decision remains uncollected",
    "actual-diff-bound decision contract evidence",
    "approve_terminal_certificate",
    "deny_terminal_certificate",
    "Generic continuation remains rejected",
    "records no operator decision value",
    "records the explicit operator value",
    "satisfies only the operator decision gate",
    "mints no certificate",
    "certificate minting remains blocked",
    "actual-diff decision value record evidence",
    "actual-diff-bound certificate minting evidence",
    "limited to the GitHub PR proof thread",
    "grants no repository mutation, connector call, receipt-store append, deployment, secret serialization, or destructive-operation authority",
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
        REQUIRED_APPROVED_BRANCH_WORKSPACE_AUTHORITY_TERMS,
        "approved_branch_workspace_authority_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_APPROVED_BRANCH_WORKSPACE_OBSERVATION_TERMS,
        "approved_branch_workspace_observation_term",
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
        REQUIRED_DRY_RUN_TEST_EXECUTION_OBSERVATION_TERMS,
        "dry_run_test_execution_observation_term",
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
    _require_all(
        map_text,
        REQUIRED_EXECUTED_TEST_RECEIPT_ADMISSION_TERMS,
        "executed_test_receipt_admission_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_NON_EMPTY_DIFF_RECEIPT_ADMISSION_TERMS,
        "non_empty_diff_receipt_admission_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_FILESYSTEM_WRITE_ADMISSION_TERMS,
        "filesystem_write_admission_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_CONCRETE_FILESYSTEM_WRITE_EVIDENCE_CANDIDATE_TERMS,
        "concrete_filesystem_write_evidence_candidate_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_ACTUAL_FILESYSTEM_WRITE_RECEIPT_ADMISSION_TERMS,
        "actual_filesystem_write_receipt_admission_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_REDACTED_FILESYSTEM_WRITE_EXECUTION_RECEIPT_TERMS,
        "redacted_filesystem_write_execution_receipt_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_BINDING_TERMS,
        "actual_non_empty_diff_receipt_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_ACTUAL_DIFF_COLLECTION_RECEIPT_TERMS,
        "actual_diff_collection_receipt_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_NON_EMPTY_DIFF_FILE_SUMMARY_RECEIPT_TERMS,
        "non_empty_diff_file_summary_receipt_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_ADMISSION_TERMS,
        "github_pr_admission_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_ACTUAL_NON_EMPTY_DIFF_ADMISSION_BINDING_TERMS,
        "github_pr_actual_non_empty_diff_admission_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_OPERATOR_APPROVAL_ACTUAL_DIFF_BINDING_TERMS,
        "github_pr_operator_approval_actual_diff_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_OPERATOR_RESPONSE_ACTUAL_DIFF_BINDING_TERMS,
        "github_pr_operator_response_actual_diff_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_BRANCH_WRITE_ACTUAL_DIFF_RESPONSE_BINDING_TERMS,
        "github_pr_branch_write_actual_diff_response_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_BRANCH_WRITE_COMMAND_PREVIEW_RESPONSE_BINDING_TERMS,
        "github_pr_branch_write_command_preview_response_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_UAO_ACTUAL_DIFF_BRANCH_WRITE_BINDING_TERMS,
        "github_pr_uao_actual_diff_branch_write_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_ROLLBACK_ACTUAL_DIFF_UAO_BINDING_TERMS,
        "github_pr_rollback_actual_diff_uao_binding_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_CI_GATE_TERMS,
        "github_pr_ci_gate_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_EFFECT_RECONCILIATION_TERMS,
        "github_pr_effect_reconciliation_term",
        errors,
    )
    _require_all(
        map_text,
        REQUIRED_GITHUB_PR_TERMINAL_CLOSURE_TERMS,
        "github_pr_terminal_closure_term",
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
    _validate_approved_branch_workspace_authority_ready(map_text, errors)
    _validate_approved_branch_workspace_observation_ready(map_text, errors)
    _validate_dry_run_test_runner_plan_ready(map_text, errors)
    _validate_dry_run_test_execution_observation_ready(map_text, errors)
    _validate_task_record_write_uao_ready(map_text, errors)
    _validate_receipt_store_append_preflight_ready(map_text, errors)
    _validate_executed_test_receipt_admission_ready(map_text, errors)
    _validate_non_empty_diff_receipt_admission_ready(map_text, errors)
    _validate_filesystem_write_admission_ready(map_text, errors)
    _validate_concrete_filesystem_write_evidence_candidate_ready(map_text, errors)
    _validate_actual_filesystem_write_receipt_admission_ready(map_text, errors)
    _validate_redacted_filesystem_write_execution_receipt_ready(map_text, errors)
    _validate_actual_non_empty_diff_receipt_binding_ready(map_text, errors)
    _validate_actual_diff_collection_receipt_ready(map_text, errors)
    _validate_non_empty_diff_file_summary_receipt_ready(map_text, errors)
    _validate_github_pr_admission_ready(map_text, errors)
    _validate_github_pr_actual_non_empty_diff_admission_binding_ready(map_text, errors)
    _validate_github_pr_operator_approval_actual_diff_binding_ready(map_text, errors)
    _validate_github_pr_operator_response_actual_diff_binding_ready(map_text, errors)
    _validate_github_pr_branch_write_actual_diff_response_binding_ready(map_text, errors)
    _validate_github_pr_branch_write_command_preview_response_binding_ready(map_text, errors)
    _validate_github_pr_uao_actual_diff_branch_write_binding_ready(map_text, errors)
    _validate_github_pr_rollback_actual_diff_uao_binding_ready(map_text, errors)
    _validate_github_pr_ci_gate_ready(map_text, errors)
    _validate_github_pr_effect_reconciliation_ready(map_text, errors)
    _validate_github_pr_terminal_closure_ready(map_text, errors)
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


def _validate_approved_branch_workspace_authority_ready(map_text: str, errors: list[str]) -> None:
    closure_row = re.search(
        r"^\| Approved branch workspace creation authority binding PR \| READY \| .+one-workspace confined creation authority envelope.+actual workspace creation.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Approved branch workspace creation authority binding PR")


def _validate_approved_branch_workspace_observation_ready(map_text: str, errors: list[str]) -> None:
    closure_row = re.search(
        r"^\| Approved branch workspace creation observation receipt PR \| READY \| .+created one confined branch workspace.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Approved branch workspace creation observation receipt PR")


def _validate_dry_run_test_runner_plan_ready(map_text: str, errors: list[str]) -> None:
    closure_row = re.search(
        r"^\| Dry-run test runner plan receipt PR \| READY \| .+selected validator and pytest commands.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Dry-run test runner plan receipt PR")

    test_runner_row = re.search(
        r"^\| Test runner \| READY \| .+agentic_service_harness_dry_run_test_runner_plan_receipt.+agentic_service_harness_dry_run_test_execution_observation_receipt.+agentic_service_harness_executed_test_receipt_admission_preflight.+terminal closure remain blocked\. \| None for dry-run observation\..+ \|$",
        map_text,
        re.MULTILINE,
    )
    if test_runner_row is None:
        errors.append("missing ready row: Test runner dry-run plan receipt")


def _validate_dry_run_test_execution_observation_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Dry-run test execution observation receipt PR \| READY \| .+four selected dry-run commands.+zero exit-code evidence.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Dry-run test execution observation receipt PR")


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


def _validate_executed_test_receipt_admission_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Executed test receipt admission preflight PR \| READY \| .+executed test receipt.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Executed test receipt admission preflight PR")


def _validate_non_empty_diff_receipt_admission_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Non-empty diff receipt admission preflight PR \| READY \| .+non-empty diff receipt.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Non-empty diff receipt admission preflight PR")


def _validate_filesystem_write_admission_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Filesystem write admission preflight PR \| READY \| .+filesystem-write admission.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Filesystem write admission preflight PR")


def _validate_concrete_filesystem_write_evidence_candidate_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Concrete filesystem write evidence candidate PR \| READY \| .+non-empty redacted changed-file and diff-summary evidence refs.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Concrete filesystem write evidence candidate PR")


def _validate_actual_filesystem_write_receipt_admission_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Actual filesystem write receipt admission PR \| READY \| .+concrete filesystem-write evidence candidate.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Actual filesystem write receipt admission PR")


def _validate_redacted_filesystem_write_execution_receipt_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Redacted filesystem write execution receipt PR \| READY \| .+actual filesystem-write receipt admission.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Redacted filesystem write execution receipt PR")


def _validate_actual_non_empty_diff_receipt_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Actual non-empty diff receipt binding PR \| READY \| .+redacted non-empty changed-file and diff refs.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Actual non-empty diff receipt binding PR")


def _validate_actual_diff_collection_receipt_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Actual diff collection receipt admission PR \| READY \| .+zero-diff actual diff receipt.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Actual diff collection receipt admission PR")


def _validate_non_empty_diff_file_summary_receipt_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| Non-empty diff file summary receipt PR \| READY \| .+zero-diff actual diff receipt evidence.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: Non-empty diff file summary receipt PR")


def _validate_github_pr_admission_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR admission preflight PR \| READY \| .+PR admission is denied.+terminal closure fail closed\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR admission preflight PR")


def _validate_github_pr_actual_non_empty_diff_admission_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR actual non-empty diff admission binding PR \| READY \| .+PR admission input.+terminal closure fail closed\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR actual non-empty diff admission binding PR")


def _validate_github_pr_operator_approval_actual_diff_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR operator approval request actual-diff binding PR \| READY \| .+actual non-empty diff receipt ref.+terminal closure fail closed\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR operator approval request actual-diff binding PR")


def _validate_github_pr_operator_response_actual_diff_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR operator response actual-diff binding PR \| READY \| .+actual non-empty diff receipt ref.+terminal closure fail closed\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR operator response actual-diff binding PR")


def _validate_github_pr_branch_write_actual_diff_response_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR branch-write authority actual-diff response binding PR \| READY \| .+actual non-empty diff receipt ref.+terminal closure fail closed\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR branch-write authority actual-diff response binding PR")


def _validate_github_pr_branch_write_command_preview_response_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR branch-write authority command-preview response binding PR \| READY \| .+command-preview-bound operator response witness.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR branch-write authority command-preview response binding PR")


def _validate_github_pr_uao_actual_diff_branch_write_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR UAO admission command-preview branch-write binding PR \| READY \| .+command-preview branch-write authority binding.+actual non-empty diff receipt ref.+terminal closure fail closed\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR UAO admission command-preview branch-write binding PR")


def _validate_github_pr_rollback_actual_diff_uao_binding_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR repository-effect rollback command-preview UAO binding PR \| READY \| .+command-preview UAO admission witness.+actual-diff UAO admission witness.+terminal closure fail closed\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR repository-effect rollback command-preview UAO binding PR")


def _validate_github_pr_ci_gate_ready(
    map_text: str,
    errors: list[str],
) -> None:
    closure_row = re.search(
        r"^\| GitHub PR CI gate before ready-for-review command-preview rollback binding PR \| READY \| .+command-preview repository-effect rollback witness.+actual-diff repository-effect rollback witness.+terminal authority is granted\. \|$",
        map_text,
        re.MULTILINE,
    )
    if closure_row is None:
        errors.append("missing ready row: GitHub PR CI gate before ready-for-review command-preview rollback binding PR")


def _validate_github_pr_effect_reconciliation_ready(
    map_text: str,
    errors: list[str],
) -> None:
    witness_row = re.search(
        r"^\| GitHub PR effect reconciliation command-preview CI gate binding PR \| READY \| .+command-preview CI gate before ready-for-review witness.+actual-diff CI gate before ready-for-review witness.+effect reconciliation remains AwaitingEvidence.+terminal authority is granted\. \|$",
        map_text,
        re.MULTILINE,
    )
    if witness_row is None:
        errors.append("missing ready row: GitHub PR effect reconciliation command-preview CI gate binding PR")

    contract_row = re.search(
        r"^\| GitHub PR effect reconciliation evidence contract PR \| READY \| .+read-only GitHub PR state observation.+terminal authority is granted\. \|$",
        map_text,
        re.MULTILINE,
    )
    if contract_row is None:
        errors.append("missing ready row: GitHub PR effect reconciliation evidence contract PR")

    live_row = re.search(
        r"^\| GitHub PR effect reconciliation live evidence PR \| READY \| .+read-only GitHub metadata observations.+terminal closure authority\. \|$",
        map_text,
        re.MULTILINE,
    )
    if live_row is None:
        errors.append("missing ready row: GitHub PR effect reconciliation live evidence PR")


def _validate_github_pr_terminal_closure_ready(
    map_text: str,
    errors: list[str],
) -> None:
    witness_row = re.search(
        r"^\| GitHub PR terminal closure certificate command-preview effect reconciliation binding PR \| READY \| .+command-preview effect reconciliation witness.+actual-diff effect reconciliation witness.+terminal closure status remains AwaitingEvidence.+terminal authority is granted\. \|$",
        map_text,
        re.MULTILINE,
    )
    if witness_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure certificate command-preview effect reconciliation binding PR"
        )

    candidate_row = re.search(
        r"^\| GitHub PR terminal closure certificate candidate actual-diff witness binding PR \| READY \| .+actual-diff terminal closure certificate witness.+actual-diff approval request binding.+Candidate status remains AwaitingEvidence/operator-approval-bound.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if candidate_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure certificate candidate actual-diff witness binding PR"
        )

    approval_gate_row = re.search(
        r"^\| GitHub PR terminal closure operator approval gate actual-diff candidate binding PR \| READY \| .+actual-diff terminal closure certificate witness.+Operator approval remains required and uncollected.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if approval_gate_row is None:
        errors.append("missing ready row: GitHub PR terminal closure operator approval gate actual-diff candidate binding PR")

    decision_contract_row = re.search(
        r"^\| GitHub PR terminal closure operator decision contract actual-diff approval gate binding PR \| READY \| .+actual-diff operator approval gate evidence.+source approval gate binding id/ref.+Explicit operator decision remains uncollected.+terminal closure authority is granted\. \|$",
        map_text,
        re.MULTILINE,
    )
    if decision_contract_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure operator decision contract actual-diff approval gate binding PR"
        )

    generic_rejection_row = re.search(
        r"^\| GitHub PR terminal closure generic continuation rejection actual-diff decision contract binding PR \| READY \| .+actual-diff decision contract evidence.+source decision contract binding id/ref.+Generic continuation remains rejected.+terminal closure authority is granted\. \|$",
        map_text,
        re.MULTILINE,
    )
    if generic_rejection_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure generic continuation rejection actual-diff decision contract binding PR"
        )

    decision_value_request_row = re.search(
        r"^\| GitHub PR terminal closure operator decision value request actual-diff generic rejection binding PR \| READY \| .+actual-diff generic rejection evidence.+source rejection binding id/ref.+approve_terminal_certificate.+deny_terminal_certificate.+records no operator decision value.+terminal closure authority\. \|$",
        map_text,
        re.MULTILINE,
    )
    if decision_value_request_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure operator decision value request actual-diff generic rejection binding PR"
        )

    decision_value_record_row = re.search(
        r"^\| GitHub PR terminal closure operator decision value record actual-diff request binding PR \| READY \| .+actual-diff decision value request evidence.+source request id/ref/status.+approve_terminal_certificate.+satisfies only the operator decision gate.+terminal closure authority\. \|$",
        map_text,
        re.MULTILINE,
    )
    if decision_value_record_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure operator decision value record actual-diff request binding PR"
        )

    certificate_minting_row = re.search(
        r"^\| GitHub PR terminal closure certificate minting actual-diff decision value record binding PR \| READY \| .+actual-diff decision value record evidence.+source decision value record id/ref.+source request id/ref/status.+approve_terminal_certificate.+actual non-empty diff receipt ref.+GitHub PR proof thread.+destructive-operation authority\. \|$",
        map_text,
        re.MULTILINE,
    )
    if certificate_minting_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure certificate minting actual-diff decision value record binding PR"
        )

    certificate_read_model_row = re.search(
        r"^\| GitHub PR terminal closure certificate read model actual-diff minting binding PR \| READY \| .+actual-diff certificate minting evidence.+source minting id/ref/time.+approve_terminal_certificate.+actual non-empty diff receipt ref.+read-only, projection-only, reference-only.+new terminal-closure authority\. \|$",
        map_text,
        re.MULTILINE,
    )
    if certificate_read_model_row is None:
        errors.append(
            "missing ready row: GitHub PR terminal closure certificate read model actual-diff minting binding PR"
        )

    pr_creation_read_model_binding_row = re.search(
        r"^\| GitHub PR creation admission terminal certificate read-model binding PR \| READY \| .+agentic_service_harness_github_pr_admission_preflight.+actual-diff terminal certificate read-model evidence.+certificate read-model example ref.+schema ref.+validator ref.+projection-only status.+pull-request creation.+new terminal-closure authority\. \|$",
        map_text,
        re.MULTILINE,
    )
    if pr_creation_read_model_binding_row is None:
        errors.append(
            "missing ready row: GitHub PR creation admission terminal certificate read-model binding PR"
        )

    pr_creation_dry_run_receipt_row = re.search(
        r"^\| GitHub PR creation dry-run receipt terminal certificate admission binding PR \| READY \| .+agentic_service_harness_github_pr_creation_dry_run_receipt.+certificate-read-model-bound admission preflight.+terminal certificate read model.+dry-run-only PR creation.+runtime PR execution.+pull-request opened.+branch creation.+repository writes.+receipt-store append.+adapter execution.+connector calls.+mutation routes.+secret material.+terminal closure\. \|$",
        map_text,
        re.MULTILINE,
    )
    if pr_creation_dry_run_receipt_row is None:
        errors.append(
            "missing ready row: GitHub PR creation dry-run receipt terminal certificate admission binding PR"
        )

    pr_creation_execution_admission_row = re.search(
        r"^\| GitHub PR creation execution admission dry-run binding PR \| READY \| .+agentic_service_harness_github_pr_creation_execution_admission.+PR creation dry-run receipt.+execution admission.+operator approval.+branch-write authority.+UAO.+rollback.+receipt-store write-path.+effect reconciliation.+pull-request creation.+repository writes.+connector calls.+mutation routes.+secret material.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if pr_creation_execution_admission_row is None:
        errors.append(
            "missing ready row: GitHub PR creation execution admission dry-run binding PR"
        )

    pr_creation_command_preview_row = re.search(
        r"^\| GitHub PR creation command preview execution-admission binding PR \| READY \| .+agentic_service_harness_github_pr_creation_command_preview.+execution-admission evidence.+redacted `gh pr create` command preview.+command execution.+adapter execution.+branch pushes.+pull-request creation.+repository writes.+receipt-store append.+connector calls.+mutation routes.+secret material.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if pr_creation_command_preview_row is None:
        errors.append(
            "missing ready row: GitHub PR creation command preview execution-admission binding PR"
        )

    pr_operator_approval_command_preview_row = re.search(
        r"^\| GitHub PR operator approval request command-preview binding PR \| READY \| .+agentic_service_harness_github_pr_operator_approval_request_command_preview_binding.+operator approval request evidence.+command preview.+operator response.+command execution.+branch writes.+pull-request creation.+repository writes.+connector calls.+mutation routes.+receipt-store append.+secret material.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if pr_operator_approval_command_preview_row is None:
        errors.append(
            "missing ready row: GitHub PR operator approval request command-preview binding PR"
        )

    pr_operator_response_command_preview_row = re.search(
        r"^\| GitHub PR operator response command-preview binding PR \| READY \| .+agentic_service_harness_github_pr_operator_response_command_preview_binding.+operator response witness.+command-preview-bound approval request.+operator response.+command execution.+branch writes.+pull-request creation.+repository writes.+connector calls.+mutation routes.+receipt-store append.+secret material.+terminal closure remain blocked\. \|$",
        map_text,
        re.MULTILINE,
    )
    if pr_operator_response_command_preview_row is None:
        errors.append(
            "missing ready row: GitHub PR operator response command-preview binding PR"
        )


def _validate_next_pr_sequence(map_text: str, errors: list[str]) -> None:
    sequence_markers = (
        "harness(pr): bind terminal closure candidate to command-preview certificate",
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
        r"^Open PRs after readiness-map refresh: .+ outside this PR terminal closure readiness-map closure; .+does not grant harness execution authority\.$",
        map_text,
        re.MULTILINE,
    )
    if open_pr_queue is None:
        errors.append("missing open PR queue execution-authority boundary")


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
