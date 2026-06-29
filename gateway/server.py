"""Gateway Webhook Server — FastAPI endpoints for channel webhooks.

Purpose: HTTP entry points that receive webhooks from WhatsApp, Telegram,
    Slack, Discord, and serve the web chat WebSocket. Routes all messages
    through the GatewayRouter → GovernedSession governance pipeline.

Run: uvicorn gateway.server:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import logging
import os
import socket
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from mcoi_runtime.governance.audit.decision_log import (
    GovernanceDecisionLog,
    GuardDecisionDetail,
)
from mcoi_runtime.contracts.change_assurance import ChangeCertificate
from mcoi_runtime.contracts.reflex import (
    ReflexCanaryHandoff,
    ReflexDeploymentWitness,
    ReflexEvidenceRef,
    ReflexPromotionDisposition,
    ReflexReplayResult,
    ReflexSandboxBundle,
    ReflexSandboxResult,
    RuntimeHealthSnapshot,
)
from mcoi_runtime.core.reflex import (
    build_canary_handoff,
    build_certification_handoff,
    build_sandbox_bundle,
    detect_anomalies,
    diagnose_anomaly,
    generate_eval_cases,
    propose_upgrade,
    verify_reflex_deployment_witness,
)
from mcoi_runtime.app.governed_execution import (
    universal_command_orchestration_record_view,
    universal_command_proof_view,
)
from mcoi_runtime.contracts.terminal_closure import (
    TerminalClosureCertificate,
    TerminalClosureDisposition,
)
from mcoi_runtime.personal_assistant import (
    ApprovalDecision,
    ApprovalProposedAction,
    ApprovalScope,
    MemoryConfidence,
    MemoryObservationSource,
    MemoryObservationType,
    MemoryRetentionPolicy,
    MemoryReviewDecision,
    MemoryScope,
    MemorySensitivity,
    NestedMindStatus,
    PersonalAssistantInvariantError,
    PersonalAssistantApprovalQueue,
    PersonalAssistantMemoryObservationLedger,
    RequestInterface,
    build_clarification_requests,
    build_personal_assistant_console_read_model,
    build_personal_assistant_preview_plan,
    draft_calendar_event,
    draft_email_response,
    draft_task,
    interpret_user_request,
    load_default_skill_registry,
    plan_github_codex_review,
    plan_math_reasoning,
    plan_research_source_compare,
    plan_schedule_optimization,
    plan_teamops_shared_inbox,
    prepare_approval_proposal_from_plan,
    prepare_memory_observation,
    preview_teamops_gmail_live_probe,
    render_personal_assistant_console_html,
    review_memory_observation_candidate,
    summarize_calendar_day_read_only,
    summarize_inbox_read_only,
)
from mcoi_runtime.personal_assistant.approval import ApprovalPlanProposal
from mcoi_runtime.personal_assistant.approval_matrix import load_default_personal_assistant_approval_matrix

from gateway.channels.discord import DiscordAdapter
from gateway.channels.phone import PhoneAdapter
from gateway.channels.slack import SlackAdapter
from gateway.channels.sms import SmsAdapter
from gateway.channels.teams import TeamsAdapter
from gateway.channels.telegram import TelegramAdapter
from gateway.channels.web import WebChatAdapter
from gateway.channels.whatsapp import WhatsAppAdapter
from gateway.authority_obligation_mesh import (
    AuthorityObligationMesh,
    build_authority_obligation_mesh_store_from_env,
)
from gateway.autonomous_capability_upgrade import (
    AutonomousCapabilityUpgradeLoop,
    CapabilityHealthSignal,
)
from gateway.agentic_service_harness_status import (
    AgenticServiceHarnessReadModelSource,
    build_agentic_service_harness_status_projection,
)
from gateway.agentic_service_harness_read_model_producer import (
    AgenticServiceHarnessRuntimeReadModelProducer,
)
from gateway.approval import ApprovalStatus
from gateway.capability_capsule_installer import install_certified_capsule_with_handoff_evidence
from gateway.capability_fabric import build_capability_admission_gate_from_env
from gateway.capability_isolation import build_isolated_capability_executor_from_env
from gateway.capability_forge import CapabilityCertificationHandoff
from gateway.capability_maturity import CapabilityCertificationEvidenceBundle
from gateway.case_management import build_operational_case_read_model
from gateway.code_intelligence_read_model import (
    build_code_intelligence_operator_read_model,
    parse_affected_files,
)
from gateway.command_spine import build_command_ledger_from_env, canonical_hash
from gateway.conformance import issue_conformance_certificate
from gateway.enterprise_authority import AuthorityDecision
from gateway.evidence_bundle import build_command_trust_bundle
from gateway.event_log import WebhookEventLog
from gateway.federated_control import FederatedControlPlane, federated_control_snapshot_to_json_dict
from gateway.governed_operations import (
    GovernedOperationsKernel,
    default_loop_registry,
    receipt_from_projection,
)
from gateway.github_operations_workroom import (
    GitHubActionsFailureEvidenceAdmissionRequest,
    GitHubPatchPlanDraftRequest,
    GitHubRepoStatusEvidenceAdmissionRequest,
    GitHubReadOnlyEvidenceFetchError,
    GitHubReadOnlyEvidenceFetcher,
    GitHubReadOnlyEvidenceAdmissionRequest,
    GitHubPrSafetyWorkroomRequest,
    admit_github_actions_failure_evidence_collection,
    admit_github_repo_status_evidence_collection,
    admit_github_read_only_evidence_collection,
    build_github_actions_failure_diagnosis_receipt,
    build_github_actions_failure_workroom_read_model,
    build_github_patch_plan_draft_receipt,
    build_github_patch_plan_workroom_read_model,
    build_github_repo_status_summary_receipt,
    build_github_repo_status_workroom_read_model,
    build_github_read_only_evidence_fetch_receipt,
    build_github_pr_safety_workroom_projection,
    build_github_pr_safety_workroom_read_model,
    build_pr_safety_projection_from_github_fetch_receipt,
    evaluate_github_actions_failure_diagnosis,
    evaluate_github_patch_plan_draft,
    evaluate_github_repo_status_summary,
    evaluate_github_pr_safety_judgment,
    persist_github_read_only_evidence_receipt_bundle,
    read_github_read_only_evidence_receipt_bundle,
    render_github_actions_failure_workroom_html,
    render_github_patch_plan_workroom_html,
    render_github_repo_status_workroom_html,
    render_github_pr_safety_workroom_html,
)
from gateway.axiomworld_api import register_axiomworld_routes
from gateway.mcp_capabilities import register_mcp_capabilities
from gateway.mcp_capability_fabric import MCPAuthorityRecords, build_mcp_gateway_import_from_env
from gateway.observability import GatewayObservabilityRecorder
from gateway.mcp_operator_read_model import build_mcp_operator_read_model
from gateway.operator_capability_console import (
    DEVELOPER_WORKFLOW_RUN_HREF,
    DEVELOPER_WORKFLOW_RUN_READ_MODEL_HREF,
    build_capability_friction_control_read_model,
    build_developer_workflow_v1_run_read_model,
    build_operator_capability_read_model,
    render_developer_workflow_v1_run_html,
    render_operator_capability_console,
    sandbox_to_pr_next_evidence,
)
from gateway.operator_control_tower import (
    OperatorControlTowerBuilder,
    OperatorPanelKind,
    developer_workflow_operator_action_banner,
    operator_control_tower_snapshot_to_json_dict,
    operator_control_tower_status_receipt,
    render_operator_control_tower,
)
from gateway.operator_sandbox_patch_readiness import sandbox_patch_readiness_compact_summary
from gateway.operator_goal_intake import (
    DEFAULT_GOAL_INTAKE_CHANNEL,
    DEFAULT_GOAL_INTAKE_SENDER_ID,
    GoalIntakePreviewRecord,
    GoalIntakePreviewStore,
    build_goal_intake_read_model,
    render_goal_intake_html,
)
from gateway.operator_receipt_viewer import (
    APPROVAL_HISTORY_SCHEMA_REF,
    CURRENT_TASK_SCHEMA_REF,
    PLAN_REVIEW_SCHEMA_REF,
    RECEIPT_VIEWER_SCHEMA_REF,
    build_current_task_read_model,
    build_operator_budget_report_read_model,
    build_operator_approval_history_read_model,
    build_operator_plan_receipt_bundle_read_model,
    build_operator_plan_receipt_export_read_model,
    build_operator_plan_review_read_model,
    build_operator_receipt_viewer_read_model,
    render_current_task_html,
    render_operator_budget_report_html,
    render_operator_approval_detail_html,
    render_operator_plan_receipt_bundle_html,
    render_operator_plan_receipt_export_html,
    render_operator_approval_history_html,
    render_operator_plan_review_detail_html,
    render_operator_plan_review_html,
    render_operator_receipt_detail_html,
    render_operator_receipt_viewer_html,
    valid_approval_statuses,
    valid_plan_budget_gates,
    valid_plan_review_statuses,
    valid_receipt_types,
    valid_task_statuses,
)
from gateway.orgos_kernel import (
    AuthorityRule,
    DepartmentPack,
    EffectClosureBinding,
    OrgCase,
    Organization,
    OrganizationKernel,
    OrgPlanStep,
    Role,
    build_orgos_case_event_log_from_env,
    default_mullu_orgos_departments,
    replay_orgos_kernel_from_events,
)
from gateway.plan_ledger import build_capability_plan_ledger_from_env
from gateway.plan import CapabilityPlanBuilder, preview_for_plan
from gateway.proxy_policy import assert_proxy_environment_allowed
from gateway.router import GatewayMessage, GatewayRouter
from gateway.session import SessionManager
from gateway.capability_dispatch import build_capability_dispatcher_from_platform
from scripts.emit_physical_capability_promotion_receipt import (
    DEFAULT_CAPABILITY_ID as DEFAULT_PHYSICAL_PROMOTION_CAPABILITY_ID,
    PHYSICAL_SAFETY_REF_FIELDS,
    emit_physical_capability_promotion_receipt,
)
from scripts.validate_developer_workflow_local_sandbox_proof_report import (
    validate_developer_workflow_local_sandbox_proof_report,
)
from scripts.validate_developer_workflow_local_rollback_summary_packet import (
    validate_developer_workflow_local_rollback_summary_packet,
)
from scripts.validate_developer_workflow_local_rollback_approval_packet import (
    validate_developer_workflow_local_rollback_approval_packet,
)
from scripts.validate_developer_workflow_local_rollback_execution_receipt import (
    validate_developer_workflow_local_rollback_execution_receipt,
)
from scripts.build_developer_workflow_operator_receipt import (
    validate_developer_workflow_operator_receipt,
)
from gateway.physical_capability_promotion_store import build_physical_capability_promotion_receipt_store_from_env
from gateway.signature_verification import (
    ChannelVerifierConfig, VerificationMethod, WebhookVerifier,
)
from gateway.tenant_identity import TenantMapping, build_tenant_identity_store_from_env
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule

_log = logging.getLogger(__name__)
LOCAL_SANDBOX_RECEIPT_BUNDLE_PATH = Path(".change_assurance") / "developer_workflow_sandbox_receipt_bundle.collected.json"
LOCAL_SANDBOX_PROOF_REPORT_PATH = (
    Path(".change_assurance") / "developer_workflow_local_sandbox_proof_report.generated.json"
)
LOCAL_ROLLBACK_SUMMARY_PACKET_PATH = (
    Path(".change_assurance") / "developer_workflow_local_rollback_summary_packet.generated.json"
)
LOCAL_ROLLBACK_APPROVAL_PACKET_PATH = (
    Path(".change_assurance") / "developer_workflow_local_rollback_approval_packet.generated.json"
)
LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH = (
    Path(".change_assurance") / "developer_workflow_local_rollback_execution_receipt.generated.json"
)
LOCAL_DEVELOPER_WORKFLOW_OPERATOR_RECEIPT_PATH = (
    Path(".change_assurance") / "developer_workflow_operator_receipt.generated.json"
)
LOCAL_ROLLBACK_RECEIPT_HREF_BASE = "/operator/control-tower/local-rollback-receipt"
PHYSICAL_ACTION_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:physical-action-receipt:1"
CAPABILITY_IMPROVEMENT_PORTFOLIO_SCHEMA_REF = "urn:mullusi:schema:capability-improvement-portfolio:1"
PHYSICAL_LIVE_SAFETY_EXTENSION_KEY = "physical_live_safety_evidence"
PHYSICAL_CAPABILITY_PREFIXES = ("physical.", "iot.", "robotics.")
GOVERN_CLOUD_PUBLIC_PROXY_PATHS = frozenset(("/v1/health", "/v1/version"))
GOVERN_CLOUD_PUBLIC_PROXY_TIMEOUT_SECONDS = 5.0
GOVERN_CLOUD_PUBLIC_PROXY_MAX_BYTES = 65_536
REQUIRED_PHYSICAL_LIVE_SAFETY_FIELDS = (
    "physical_action_receipt_ref",
    "simulation_ref",
    "operator_approval_ref",
    "manual_override_ref",
    "emergency_stop_ref",
    "sensor_confirmation_ref",
    "deployment_witness_ref",
)


def _redacted_request_validation_detail(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Return validation errors without echoing rejected request values."""
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        details.append(
            {
                "type": str(error.get("type", "validation_error")),
                "loc": list(error.get("loc", ())),
                "msg": str(error.get("msg", "request validation failed")),
            }
        )
    return details


class GatewayPersonalAssistantConnectorRef(BaseModel):
    """Connector proof reference accepted by the gateway preview boundary."""

    model_config = ConfigDict(extra="forbid")

    connector_id: str
    connector_name: str
    proof_state: str
    private_data_allowed: bool
    scopes: list[str] = Field(default_factory=list)


class GatewayPersonalAssistantPreviewRequest(BaseModel):
    """Preview-only personal-assistant request admitted by the public gateway."""

    model_config = ConfigDict(extra="forbid")

    user_request: str
    request_id: str = ""
    submitted_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    thread_id: str = "thread-personal-assistant-gateway-preview"
    requested_from_id: str = "operator"
    include_console_read_model: bool = False


class GatewayPersonalAssistantReadOnlyInboxMessage(BaseModel):
    """Redacted inbox projection accepted by the gateway read-only boundary."""

    model_config = ConfigDict(extra="forbid")

    message_ref: str
    received_at: str
    sender_label: str
    subject_digest: str
    snippet_digest: str
    priority_signals: list[str] = Field(default_factory=list)
    needs_reply: bool = False
    has_attachment: bool = False


class GatewayPersonalAssistantReadOnlyCalendarEvent(BaseModel):
    """Redacted calendar projection accepted by the gateway read-only boundary."""

    model_config = ConfigDict(extra="forbid")

    event_ref: str
    starts_at: str
    ends_at: str
    title_digest: str
    organizer_label: str
    location_label: str = ""
    attendee_count: int = 0
    conflict_ref: str = ""
    preparation_signals: list[str] = Field(default_factory=list)


class GatewayPersonalAssistantReadOnlyInboxPreviewRequest(BaseModel):
    """Preview-only inbox summary request over redacted operator evidence."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Check my inbox today and summarize important items."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    messages: list[GatewayPersonalAssistantReadOnlyInboxMessage] = Field(default_factory=list)
    thread_id: str = "thread-personal-assistant-read-only-inbox-preview"
    include_console_read_model: bool = False


class GatewayPersonalAssistantReadOnlyCalendarPreviewRequest(BaseModel):
    """Preview-only calendar brief request over redacted operator evidence."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Summarize my calendar today."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    events: list[GatewayPersonalAssistantReadOnlyCalendarEvent] = Field(default_factory=list)
    thread_id: str = "thread-personal-assistant-read-only-calendar-preview"
    include_console_read_model: bool = False


class GatewayPersonalAssistantEmailDraftInput(BaseModel):
    """Redacted email source projection accepted by the draft-only boundary."""

    model_config = ConfigDict(extra="forbid")

    message_ref: str
    recipient_label: str
    sender_label: str
    subject_digest: str
    thread_summary_digest: str
    response_goal: str
    tone: str = "clear"
    constraints: list[str] = Field(default_factory=list)


class GatewayPersonalAssistantCalendarEventDraftInput(BaseModel):
    """Redacted calendar source projection accepted by the draft-only boundary."""

    model_config = ConfigDict(extra="forbid")

    meeting_goal: str
    title_digest: str
    proposed_window: str
    duration_minutes: int
    attendee_labels: list[str] = Field(default_factory=list)
    location_label: str = ""
    agenda_digest: str = ""
    constraints: list[str] = Field(default_factory=list)


class GatewayPersonalAssistantTaskDraftInput(BaseModel):
    """Task proposal source projection accepted by the draft-only boundary."""

    model_config = ConfigDict(extra="forbid")

    task_goal: str
    source_ref: str
    title_digest: str
    priority: str
    due_hint: str = ""
    acceptance_digest: str = ""
    constraints: list[str] = Field(default_factory=list)


class GatewayPersonalAssistantEmailDraftPreviewRequest(BaseModel):
    """Preview-only email response draft request over redacted operator evidence."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Check my inbox and draft a reply today."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    draft_input: GatewayPersonalAssistantEmailDraftInput
    include_console_read_model: bool = False


class GatewayPersonalAssistantCalendarEventDraftPreviewRequest(BaseModel):
    """Preview-only calendar event draft request over redacted operator evidence."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Draft a calendar event for today."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    draft_input: GatewayPersonalAssistantCalendarEventDraftInput
    include_console_read_model: bool = False


class GatewayPersonalAssistantTaskDraftPreviewRequest(BaseModel):
    """Preview-only task draft request over operator evidence."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Create a task draft from this request."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    draft_input: GatewayPersonalAssistantTaskDraftInput
    include_console_read_model: bool = False


class GatewayPersonalAssistantApprovalAction(BaseModel):
    """One proposed personal-assistant action for approval queue preview."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    skill_id: str
    risk_level: str
    effect_boundary: str
    summary: str


class GatewayPersonalAssistantApprovalPreviewRequest(BaseModel):
    """Stateless approval queue preview request for public gateway evidence."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    plan_id: str
    approver_ref: str = "operator:gateway"
    approval_scope: str = ApprovalScope.PER_ACTION.value
    proposed_actions: list[GatewayPersonalAssistantApprovalAction]
    forbidden_without_approval: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str = ""
    approval_id: str = ""
    decision: str = ""
    reason_codes: list[str] = Field(default_factory=list)
    decided_at: str = ""
    decision_evidence_ref: str = ""
    revision_request: str = ""


class GatewayPersonalAssistantApprovalProposalPreviewRequest(BaseModel):
    """Stateless approval proposal preview request for public gateway evidence."""

    model_config = ConfigDict(extra="forbid")

    user_request: str
    plan: dict[str, Any] = Field(default_factory=dict)
    request_id: str = ""
    submitted_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    approval_scope: str = ApprovalScope.PER_PLAN.value
    thread_id: str = "thread-personal-assistant-approval-proposal-preview"
    requested_from_id: str = "operator"
    include_console_read_model: bool = False


class GatewayPersonalAssistantDraftApprovalSource(BaseModel):
    """Redacted draft reference that can be converted into an approval proposal."""

    model_config = ConfigDict(extra="forbid")

    draft_ref: str
    draft_type: str
    draft_skill_id: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)


class GatewayPersonalAssistantDraftApprovalPreviewRequest(BaseModel):
    """No-effect bridge from draft-only preview to approval proposal preview."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    draft: GatewayPersonalAssistantDraftApprovalSource
    plan_id: str = ""
    created_at: str = ""
    approval_scope: str = ApprovalScope.PER_ACTION.value
    approver_ref: str = "operator:gateway"
    include_console_read_model: bool = False


class GatewayPersonalAssistantSendWriteEligibilityPreviewRequest(BaseModel):
    """No-effect send/write eligibility preflight over approved draft evidence."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    draft: GatewayPersonalAssistantDraftApprovalSource
    plan_id: str = ""
    created_at: str = ""
    approval_scope: str = ApprovalScope.PER_ACTION.value
    approver_ref: str = "operator:gateway"
    approval_proposal_ref: str = ""
    approval_decision: str = ""
    approval_decision_ref: str = ""
    approval_receipt_ref: str = ""
    connector_boundary_ref: str = ""
    live_probe_receipt_ref: str = ""
    preparation_receipt_ref: str = ""
    post_action_receipt_plan_ref: str = ""
    include_console_read_model: bool = False


class GatewayPersonalAssistantMemorySource(BaseModel):
    """Evidence source for one memory observation preview."""

    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_ref: str
    observed_at: str


class GatewayPersonalAssistantMemoryPreviewRequest(BaseModel):
    """Stateless memory observation preview request for public gateway evidence."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    memory_observation_id: str
    memory_type: str = MemoryObservationType.PREFERENCE.value
    claim: str
    source: GatewayPersonalAssistantMemorySource
    confidence: str = MemoryConfidence.MEDIUM.value
    scope: str = MemoryScope.ASSISTANT_WORKFLOW.value
    mutable: bool = True
    receipt_id: str
    evidence_refs: list[str] = Field(default_factory=list)
    observed_at: str = ""
    sensitivity: str = MemorySensitivity.INTERNAL.value
    retention_policy: str = MemoryRetentionPolicy.OPERATOR_REVIEW.value
    nested_mind_status: str = NestedMindStatus.STAGING_ONLY.value
    metadata: dict[str, Any] = Field(default_factory=dict)


class GatewayPersonalAssistantMemoryReviewPreviewRequest(BaseModel):
    """Stateless memory review preview request for public gateway evidence."""

    model_config = ConfigDict(extra="forbid")

    candidate: GatewayPersonalAssistantMemoryPreviewRequest
    review_id: str
    decision: str = MemoryReviewDecision.KEPT_FOR_OPERATOR_REVIEW.value
    reviewer_ref: str = "operator:gateway"
    reason_codes: list[str] = Field(default_factory=list)
    reviewed_at: str = ""
    review_evidence_ref: str = ""
    revision_request: str = ""
    deferred_until: str = ""
    expires_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GatewayPersonalAssistantTeamOpsPreviewRequest(BaseModel):
    """Stateless TeamOps shared-inbox plan preview request."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Prepare a TeamOps shared inbox handoff."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    github_secret_names: list[str] = Field(default_factory=list)
    operator_approval_ref: str = ""
    repository: str = "tamirat-wubie/mullu-control-plane"


class GatewayPersonalAssistantTeamOpsLiveProbePreviewRequest(BaseModel):
    """Stateless TeamOps/Gmail presence-only live-probe preview request."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Verify TeamOps Gmail live probe readiness."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    github_secret_names: list[str] = Field(default_factory=list)
    operator_approval_ref: str = ""
    repository: str = "tamirat-wubie/mullu-control-plane"


class GatewayPersonalAssistantGitHubCodexPreviewRequest(BaseModel):
    """Stateless GitHub/Codex review preview request."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Review this GitHub pull request and draft the next Codex instruction."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    connector_refs: list[GatewayPersonalAssistantConnectorRef] = Field(default_factory=list)
    repository_ref: str = "tamirat-wubie/mullu-control-plane"
    pull_request_ref: str = ""
    change_summary: str
    changed_files: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    blocking_questions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    requested_instruction_goal: str = "prepare the next safe Codex instruction"


class GatewayGitHubPrSafetyWorkroomPreviewRequest(BaseModel):
    """Stateless governed GitHub Operations Workroom PR safety preview."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    pull_request_number: int
    surface_event_id: str = ""
    occurred_at: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    channel_id: str = ""
    trace_ref: str = ""
    authority_ref: str = "policy.github.pr_review.local_read_only"
    assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GatewayGitHubReadOnlyEvidenceAdmissionPreviewRequest(BaseModel):
    """Stateless live read-only GitHub evidence admission preview."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    pull_request_number: int
    requested_evidence_kinds: list[str] = Field(default_factory=lambda: ["pull_request", "diff", "checks", "changed_files"])
    requested_at: str = ""
    surface_event_id: str = ""
    authority_ref: str = "policy.github.pr_review.live_read_only"


class GatewayGitHubReadOnlyEvidenceExecutionRequest(BaseModel):
    """Execute admitted read-only GitHub evidence collection from operator token."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    pull_request_number: int
    requested_evidence_kinds: list[str] = Field(default_factory=lambda: ["pull_request", "diff", "checks", "changed_files"])
    requested_at: str = ""
    surface_event_id: str = ""
    authority_ref: str = "policy.github.pr_review.live_read_only"
    access_token: str = Field(repr=False)
    timeout_seconds: float = 10.0


class GatewayGitHubActionsFailureAdmissionPreviewRequest(BaseModel):
    """Stateless live read-only GitHub Actions failure admission preview."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    workflow_run_id: int
    requested_evidence_kinds: list[str] = Field(default_factory=lambda: ["workflow_run", "jobs", "failed_job_logs"])
    requested_at: str = ""
    surface_event_id: str = ""
    authority_ref: str = "policy.github.actions_failure.live_read_only"
    max_failed_job_logs: int = 3


class GatewayGitHubActionsFailureEvidenceExecutionRequest(BaseModel):
    """Execute admitted read-only GitHub Actions failure evidence collection."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    workflow_run_id: int
    requested_evidence_kinds: list[str] = Field(default_factory=lambda: ["workflow_run", "jobs", "failed_job_logs"])
    requested_at: str = ""
    surface_event_id: str = ""
    authority_ref: str = "policy.github.actions_failure.live_read_only"
    max_failed_job_logs: int = 3
    access_token: str = Field(repr=False)
    timeout_seconds: float = 10.0


class GatewayGitHubRepoStatusAdmissionPreviewRequest(BaseModel):
    """Stateless live read-only GitHub repository status admission preview."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    requested_evidence_kinds: list[str] = Field(
        default_factory=lambda: ["repository", "recent_commits", "open_pull_requests", "open_issues", "workflow_runs"]
    )
    requested_at: str = ""
    surface_event_id: str = ""
    authority_ref: str = "policy.github.repo_status.live_read_only"
    max_items_per_kind: int = 10


class GatewayGitHubRepoStatusEvidenceExecutionRequest(BaseModel):
    """Execute admitted read-only GitHub repository status evidence collection."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    requested_evidence_kinds: list[str] = Field(
        default_factory=lambda: ["repository", "recent_commits", "open_pull_requests", "open_issues", "workflow_runs"]
    )
    requested_at: str = ""
    surface_event_id: str = ""
    authority_ref: str = "policy.github.repo_status.live_read_only"
    max_items_per_kind: int = 10
    access_token: str = Field(repr=False)
    timeout_seconds: float = 10.0


class GatewayGitHubPatchPlanDraftRequest(BaseModel):
    """Draft a governed local GitHub patch plan from bounded evidence."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = "operator:gateway"
    workspace_id: str = "workspace:mullusi-control-plane"
    repo: str = "tamirat-wubie/mullu-control-plane"
    objective: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_summaries: list[str] = Field(default_factory=list)
    verification_expectations: list[str] = Field(default_factory=list)
    surface_event_id: str = ""
    requested_at: str = ""
    authority_ref: str = "policy.github.patch_plan.local_draft_only"
    assumptions: list[str] = Field(
        default_factory=lambda: [
            "Evidence summaries are bounded and authorized for this actor and workspace.",
            "Patch planning does not edit repository files, create branches, create pull requests, or write to GitHub.",
        ]
    )


class GatewayPersonalAssistantResearchSourceSummary(BaseModel):
    """Bounded public-source metadata for research preview."""

    model_config = ConfigDict(extra="forbid")

    source_ref: str
    title: str
    publisher: str
    published_at: str = ""
    summary: str
    trust_tier: str = "operator_supplied"
    citation_ref: str


class GatewayPersonalAssistantResearchPreviewRequest(BaseModel):
    """Stateless research source-compare preview request."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Research this topic, compare sources, and prepare citations."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    research_question: str
    source_summaries: list[GatewayPersonalAssistantResearchSourceSummary] = Field(default_factory=list)
    citation_refs: list[str] = Field(default_factory=list)
    freshness_notes: list[str] = Field(default_factory=list)
    conflict_notes: list[str] = Field(default_factory=list)
    blocking_questions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    requested_synthesis_goal: str = "prepare a source comparison with citations"


class GatewayPersonalAssistantMathKnownValue(BaseModel):
    """Bounded operator-supplied numeric value for math preview."""

    model_config = ConfigDict(extra="forbid")

    label: str
    scenario_ref: str
    value: float | int | str
    unit: str
    source_ref: str = "operator_supplied"
    notes: str = ""


class GatewayPersonalAssistantMathPreviewRequest(BaseModel):
    """Stateless math reasoning preview request."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Compare two monthly cost scenarios, check units, and explain assumptions."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    problem_statement: str
    known_values: list[GatewayPersonalAssistantMathKnownValue] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    requested_result: str = "compare scenarios, check units, and explain assumptions"


class GatewayPersonalAssistantPlanningWindow(BaseModel):
    """Bounded operator-supplied time window for schedule planning preview."""

    model_config = ConfigDict(extra="forbid")

    window_ref: str
    label: str
    start: str
    end: str
    capacity_minutes: int
    source_ref: str = "operator_supplied"
    notes: str = ""


class GatewayPersonalAssistantPlanningWorkItem(BaseModel):
    """Bounded operator-supplied work item for schedule planning preview."""

    model_config = ConfigDict(extra="forbid")

    item_ref: str
    title: str
    estimated_minutes: int
    priority: int = 3
    earliest_start: str = ""
    due: str = ""
    required_window_ref: str = ""
    source_ref: str = "operator_supplied"
    notes: str = ""


class GatewayPersonalAssistantPlanningPreviewRequest(BaseModel):
    """Stateless schedule planning preview request."""

    model_config = ConfigDict(extra="forbid")

    user_request: str = "Optimize schedule with operator supplied windows and work items."
    request_id: str = ""
    submitted_at: str = ""
    generated_at: str = ""
    objective: str
    time_windows: list[GatewayPersonalAssistantPlanningWindow] = Field(default_factory=list)
    work_items: list[GatewayPersonalAssistantPlanningWorkItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    requested_result: str = "assign work items to available windows and identify blockers"


def _explicit_dev_or_test_env(raw_env: str) -> bool:
    """Whether the authority dev/test bypass is permitted for this MULLU_ENV.

    The approval-webhook / authority-operator / deployment-authority routes
    skip their secret/identity check only in ``local_dev``/``test``. That
    bypass MUST require an EXPLICIT ``MULLU_ENV`` of ``local_dev`` or ``test``.
    An unset or blank value must NOT grant it: a forgotten ``MULLU_ENV`` in a
    production deployment previously defaulted to ``local_dev`` and opened
    every authority route with no secret. Mirrors the musia_auth "F16" rule —
    production must opt into dev mode, not fall into it.
    """
    return raw_env.strip().lower() in {"local_dev", "test"}


def _gateway_personal_assistant_request_id(user_request: str, submitted_at: str, interface: str) -> str:
    """Return a stable gateway request id for preview-only assistant planning."""
    return "pa_request_" + canonical_hash(
        {
            "namespace": "gateway-personal-assistant-request",
            "user_request": user_request,
            "submitted_at": submitted_at,
            "interface": interface,
        }
    )[:32]


def _gateway_personal_assistant_plan_id(request_id: str) -> str:
    """Return a stable gateway plan id for a preview request id."""
    return "pa_plan_" + canonical_hash(
        {
            "namespace": "gateway-personal-assistant-plan",
            "request_id": request_id,
        }
    )[:32]


def _gateway_personal_assistant_outcome(plan: Mapping[str, Any], clarification_complete: bool) -> str:
    """Map preview-only plan state to the Mullusi solver outcome taxonomy."""
    if not clarification_complete:
        return "AwaitingEvidence"
    if bool(plan.get("requires_approval")):
        return "AwaitingEvidence"
    return "SolvedVerified"


def _gateway_personal_assistant_read_only_projection_set(
    *,
    projection: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Return a schema-ready no-effect read-only projection set."""
    receipt = dict(projection["receipt"])
    projection_id = "pa_read_only_projection_item_" + canonical_hash(
        {
            "namespace": "gateway-personal-assistant-read-only-projection-item",
            "request_id": projection["request_id"],
            "skill_id": projection["skill_id"],
            "receipt_id": receipt.get("receipt_id", ""),
        }
    )[:32]
    projection_set_id = "pa_read_only_projection_" + canonical_hash(
        {
            "namespace": "gateway-personal-assistant-read-only-projection-set",
            "projection_id": projection_id,
        }
    )[:32]
    connectors_used = list(receipt.get("connectors_used", ()))
    summary = dict(projection["summary"])
    return {
        "projection_set_id": projection_set_id,
        "generated_at": generated_at,
        "governed": True,
        "source_projection": "operator_supplied_redacted_projection",
        "projection_count": 1,
        "projection_ids": [projection_id],
        "receipt_ids": [str(receipt.get("receipt_id", ""))],
        "connectors_used": connectors_used,
        "projections": [
            {
                "projection_id": projection_id,
                "request_id": projection["request_id"],
                "skill_id": projection["skill_id"],
                "summary_type": summary["summary_type"],
                "summary": summary,
                "receipt": receipt,
            }
        ],
        "effect_boundary": {
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "mailbox_read_allowed": False,
            "mailbox_mutation_allowed": False,
            "external_send_allowed": False,
            "calendar_write_allowed": False,
            "task_write_allowed": False,
            "memory_write_allowed": False,
            "connector_mutation_allowed": False,
            "deployment_mutation_allowed": False,
            "public_readiness_claim_allowed": False,
        },
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "redacted_summary",
            "body_projection": "redacted_summary",
        },
        "assurance": {
            "assurance_id": "personal_assistant_read_only_projection_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_supplied_redacted_projection",
                "no_live_connector_calls",
                "no_mailbox_or_calendar_mutation",
                "receipt_required",
            ],
            "blocking_reasons": [],
            "next_action": "review_projection_receipt_before_any_effect_bearing_follow_up",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "read_only_redacted_evidence",
            "runtime_boundary": "no_live_connector_calls",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "connector_count": len(connectors_used),
        },
    }


def _gateway_personal_assistant_draft_projection_set(
    *,
    projection: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Return a schema-ready no-effect draft projection set."""
    receipt = dict(projection["receipt"])
    draft = dict(projection["draft"])
    draft_id = "pa_draft_projection_item_" + canonical_hash(
        {
            "namespace": "gateway-personal-assistant-draft-projection-item",
            "request_id": projection["request_id"],
            "skill_id": projection["skill_id"],
            "receipt_id": receipt.get("receipt_id", ""),
        }
    )[:32]
    draft_set_id = "pa_draft_projection_" + canonical_hash(
        {
            "namespace": "gateway-personal-assistant-draft-projection-set",
            "draft_id": draft_id,
        }
    )[:32]
    connectors_used = list(receipt.get("connectors_used", ()))
    connector_payload_projection = "redacted_summary" if connectors_used else "mixed_redacted_or_no_connector"
    return {
        "draft_set_id": draft_set_id,
        "generated_at": generated_at,
        "governed": True,
        "source_projection": "operator_supplied_redacted_projection",
        "draft_count": 1,
        "draft_ids": [draft_id],
        "receipt_ids": [str(receipt.get("receipt_id", ""))],
        "connectors_used": connectors_used,
        "drafts": [
            {
                "draft_id": draft_id,
                "request_id": projection["request_id"],
                "skill_id": projection["skill_id"],
                "draft_type": draft["draft_type"],
                "draft": draft,
                "receipt": receipt,
            }
        ],
        "effect_boundary": {
            "draft_preparation_allowed": True,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "mailbox_mutation_allowed": False,
            "external_send_allowed": False,
            "calendar_write_allowed": False,
            "task_write_allowed": False,
            "memory_write_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "deployment_mutation_allowed": False,
            "public_readiness_claim_allowed": False,
        },
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": connector_payload_projection,
            "body_projection": "operator_visible_draft",
        },
        "approval_boundary": {
            "risk_level": "P2",
            "approval_required_before_external_action": True,
            "approval_required_before_system_write": True,
            "approval_required_before_connector_mutation": True,
        },
        "assurance": {
            "assurance_id": "personal_assistant_draft_projection_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_supplied_redacted_projection",
                "draft_only_boundary",
                "no_live_connector_calls",
                "approval_required_before_effect_bearing_action",
                "receipt_required",
            ],
            "blocking_reasons": [],
            "next_action": "review_draft_and_request_explicit_approval_before_any_external_or_system_write",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "draft_only_redacted_evidence",
            "runtime_boundary": "no_live_connector_calls",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "connector_count": len(connectors_used),
        },
    }


def _gateway_personal_assistant_draft_approval_proposal(
    *,
    request_id: str,
    plan_id: str,
    approval_scope: str,
    draft: GatewayPersonalAssistantDraftApprovalSource,
) -> ApprovalPlanProposal:
    """Return a no-effect approval proposal from a redacted draft reference."""
    draft_payload = _pydantic_payload(draft)
    target_by_draft_type = {
        "email_response": {
            "source_skill_id": "email.response.draft",
            "action_id": "send_prepared_email_draft",
            "skill_id": "email.send.with_approval",
            "risk_level": "P4",
            "effect_boundary": "external_email_send",
            "summary_prefix": "Send prepared email draft after explicit approval",
            "forbidden_without_approval": (
                "send",
                "send_without_approval",
                "recipient_unapproved",
                "connector_mutation_without_receipt",
            ),
        },
        "calendar_event": {
            "source_skill_id": "calendar.event.draft",
            "action_id": "create_prepared_calendar_event",
            "skill_id": "calendar.event.create.with_approval",
            "risk_level": "P3",
            "effect_boundary": "calendar_event_create",
            "summary_prefix": "Create prepared calendar event after explicit approval",
            "forbidden_without_approval": (
                "create_event",
                "invite_people",
                "connector_mutation",
            ),
        },
        "task": {
            "source_skill_id": "task.create_draft",
            "action_id": "create_prepared_task",
            "skill_id": "task.create.with_approval",
            "risk_level": "P3",
            "effect_boundary": "task_system_write",
            "summary_prefix": "Create prepared task after explicit approval",
            "forbidden_without_approval": (
                "system_of_record_write",
                "connector_mutation",
            ),
        },
    }
    target = target_by_draft_type.get(draft_payload["draft_type"])
    if target is None:
        raise PersonalAssistantInvariantError("draft_type does not have a registered approval proposal target")
    if draft_payload["draft_skill_id"] != target["source_skill_id"]:
        raise PersonalAssistantInvariantError("draft approval proposal source skill does not match draft_type")
    if not draft_payload["draft_ref"].startswith("pa_draft_projection_item_"):
        raise PersonalAssistantInvariantError("draft_ref must reference a draft projection item")

    action = ApprovalProposedAction.from_mapping(
        {
            "action_id": target["action_id"],
            "skill_id": target["skill_id"],
            "risk_level": target["risk_level"],
            "effect_boundary": target["effect_boundary"],
            "summary": f"{target['summary_prefix']}: {draft_payload['summary']}",
        }
    )

    registry = load_default_skill_registry()
    target_skill = registry.get(action.skill_id)
    if target_skill.risk_level.value != action.risk_level.value:
        raise PersonalAssistantInvariantError("approval target risk does not match registry")
    if target_skill.requires_approval is not True:
        raise PersonalAssistantInvariantError("approval target must require approval")

    matrix = load_default_personal_assistant_approval_matrix()
    forbidden = target["forbidden_without_approval"]
    matrix.assert_action_admitted(
        risk_level=action.risk_level,
        execution_mode="execute_with_approval",
        forbidden_without_approval=forbidden,
    )
    evidence_refs = tuple(dict.fromkeys((draft_payload["draft_ref"], *draft_payload["evidence_refs"])))
    return ApprovalPlanProposal(
        request_id=request_id,
        plan_id=plan_id,
        approval_scope=approval_scope,
        risk_level=action.risk_level,
        proposed_actions=(action,),
        forbidden_without_approval=forbidden,
        evidence_refs=evidence_refs,
        approval_matrix_ref=matrix.matrix_id,
        execution_allowed=False,
    )


_PERSONAL_ASSISTANT_PUBLIC_REF_PREFIXES = (
    "pa_",
    "proof://",
    "proof:",
    "receipt://",
    "receipt:",
    "approval://",
    "approval:",
    "witness://",
    "witness:",
    "policy://",
    "policy:",
)
_PERSONAL_ASSISTANT_PRIVATE_VALUE_MARKERS = (
    "bearer ",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "secret=",
    "token=",
    "private key",
    "raw_private",
    "raw_payload",
    "raw_body",
)


def _gateway_personal_assistant_assert_public_ref(value: str, field_name: str) -> None:
    """Validate that an evidence reference is bounded and secret-free."""
    if not value:
        return
    lowered = value.lower()
    if any(marker in lowered for marker in _PERSONAL_ASSISTANT_PRIVATE_VALUE_MARKERS):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain raw private or secret-like values")
    if len(value) > 512:
        raise PersonalAssistantInvariantError(f"{field_name} must be bounded to 512 characters")
    if not value.startswith(_PERSONAL_ASSISTANT_PUBLIC_REF_PREFIXES):
        raise PersonalAssistantInvariantError(f"{field_name} must be a governed public evidence reference")


def _gateway_personal_assistant_send_write_eligibility_preflight(
    *,
    request_id: str,
    plan_id: str,
    approval_scope: str,
    approver_ref: str,
    created_at: str,
    draft: GatewayPersonalAssistantDraftApprovalSource,
    approval_proposal_ref: str,
    approval_decision: str,
    approval_decision_ref: str,
    approval_receipt_ref: str,
    connector_boundary_ref: str,
    live_probe_receipt_ref: str,
    preparation_receipt_ref: str,
    post_action_receipt_plan_ref: str,
) -> dict[str, Any]:
    """Return a no-effect preflight for later send/write runtime eligibility."""
    proposal = _gateway_personal_assistant_draft_approval_proposal(
        request_id=request_id,
        plan_id=plan_id,
        approval_scope=approval_scope,
        draft=draft,
    )
    reference_values = {
        "draft_ref": draft.draft_ref,
        "approval_proposal_ref": approval_proposal_ref,
        "approval_decision_ref": approval_decision_ref,
        "approval_receipt_ref": approval_receipt_ref,
        "connector_boundary_ref": connector_boundary_ref,
        "live_probe_receipt_ref": live_probe_receipt_ref,
        "preparation_receipt_ref": preparation_receipt_ref,
        "post_action_receipt_plan_ref": post_action_receipt_plan_ref,
    }
    for field_name, reference_value in reference_values.items():
        _gateway_personal_assistant_assert_public_ref(reference_value, field_name)
    for index, evidence_ref in enumerate(draft.evidence_refs):
        _gateway_personal_assistant_assert_public_ref(evidence_ref, f"draft.evidence_refs[{index}]")
    if any(marker in draft.summary.lower() for marker in _PERSONAL_ASSISTANT_PRIVATE_VALUE_MARKERS):
        raise PersonalAssistantInvariantError("draft summary must not contain raw private or secret-like values")

    decision_normalized = approval_decision.strip().lower()
    required_evidence = {
        "draft_projection_ref": draft.draft_ref,
        "draft_projection_evidence": draft.evidence_refs[0] if draft.evidence_refs else "",
        "approval_proposal_ref": approval_proposal_ref,
        "approved_approval_decision": decision_normalized if decision_normalized == ApprovalDecision.APPROVED.value else "",
        "approval_decision_ref": approval_decision_ref,
        "approval_receipt_ref": approval_receipt_ref,
        "connector_boundary_ref": connector_boundary_ref,
        "live_probe_receipt_ref": live_probe_receipt_ref,
        "preparation_receipt_ref": preparation_receipt_ref,
        "post_action_receipt_plan_ref": post_action_receipt_plan_ref,
    }
    missing_evidence = [field_name for field_name, value in required_evidence.items() if not value]
    ready_for_runtime_gate = not missing_evidence
    outcome = "SolvedVerified" if ready_for_runtime_gate else "AwaitingEvidence"
    preflight_id = "pa_send_write_eligibility_" + sha256(
        json.dumps(
            {
                "request_id": request_id,
                "draft_ref": draft.draft_ref,
                "proposal_ref": approval_proposal_ref,
                "decision_ref": approval_decision_ref,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    action = proposal.proposed_actions[0]
    stages = [
        {
            "stage_id": "draft_projection_bound",
            "stage_type": "verification",
            "status": "passed",
            "evidence_refs": tuple(dict.fromkeys((draft.draft_ref, *draft.evidence_refs))),
            "effect_bearing": False,
        },
        {
            "stage_id": "approval_gate_checked",
            "stage_type": "approval_gate",
            "status": "passed" if decision_normalized == ApprovalDecision.APPROVED.value else "awaiting_evidence",
            "evidence_refs": tuple(
                ref for ref in (approval_proposal_ref, approval_decision_ref, approval_receipt_ref) if ref
            ),
            "effect_bearing": False,
        },
        {
            "stage_id": "connector_boundary_checked",
            "stage_type": "capability_probe",
            "status": "passed" if connector_boundary_ref and live_probe_receipt_ref else "awaiting_evidence",
            "evidence_refs": tuple(ref for ref in (connector_boundary_ref, live_probe_receipt_ref) if ref),
            "effect_bearing": False,
        },
        {
            "stage_id": "send_write_preparation_checked",
            "stage_type": "verification",
            "status": "passed" if preparation_receipt_ref else "awaiting_evidence",
            "evidence_refs": (preparation_receipt_ref,) if preparation_receipt_ref else (),
            "effect_bearing": False,
        },
        {
            "stage_id": "runtime_gate_not_opened",
            "stage_type": "wait_for_event",
            "status": "blocked_in_preview",
            "evidence_refs": (post_action_receipt_plan_ref,) if post_action_receipt_plan_ref else (),
            "effect_bearing": False,
        },
    ]
    effect_boundary = {
        "execution_allowed": False,
        "approval_is_execution": False,
        "approval_enqueued": False,
        "ready_for_separate_runtime_gate": ready_for_runtime_gate,
        "live_connector_execution_allowed": False,
        "external_send_allowed": False,
        "mailbox_mutation_allowed": False,
        "calendar_write_allowed": False,
        "connector_mutation_allowed": False,
        "memory_write_allowed": False,
        "deployment_mutation_allowed": False,
        "system_of_record_write_allowed": False,
    }
    actions_not_taken = [
        "external_message_not_sent",
        "provider_send_not_called",
        "provider_draft_not_created",
        "mailbox_not_read",
        "mailbox_not_mutated",
        "calendar_not_written",
        "connector_state_not_mutated",
        "system_of_record_not_written",
    ]
    receipt_payload = {
        "receipt_id": f"{preflight_id}_receipt",
        "receipt_type": "personal_assistant_send_write_eligibility_preflight_v0",
        "request_id": request_id,
        "plan_id": plan_id,
        "generated_at": created_at,
        "draft_ref": draft.draft_ref,
        "action_id": action.action_id,
        "skill_id": action.skill_id,
        "risk_level": action.risk_level.value,
        "action_effect_boundary": action.effect_boundary,
        "outcome": outcome,
        "decision": "ready_for_separate_runtime_gate" if ready_for_runtime_gate else "awaiting_required_evidence",
        "missing_evidence": missing_evidence,
        "actions_taken": [
            "draft_reference_checked",
            "approval_evidence_checked",
            "connector_boundary_evidence_checked",
            "runtime_gate_left_closed",
            "preflight_receipt_created",
        ],
        "actions_not_taken": actions_not_taken,
        "effect_boundary": effect_boundary,
        "governed": True,
    }
    receipt_hash = sha256(json.dumps(receipt_payload, sort_keys=True).encode("utf-8")).hexdigest()
    receipt_payload["receipt_hash"] = receipt_hash
    return {
        "send_write_eligibility": {
            "preflight_id": preflight_id,
            "request_id": request_id,
            "plan_id": plan_id,
            "draft_ref": draft.draft_ref,
            "draft_type": draft.draft_type,
            "approval_scope": approval_scope,
            "approver_ref": approver_ref,
            "target_action": {
                "action_id": action.action_id,
                "skill_id": action.skill_id,
                "risk_level": action.risk_level.value,
                "effect_boundary": action.effect_boundary,
            },
            "required_evidence": required_evidence,
            "missing_evidence": missing_evidence,
            "ready_for_runtime_gate": ready_for_runtime_gate,
            "execution_allowed": False,
            "outcome": outcome,
        },
        "approval_proposal": proposal.as_dict(),
        "stages": stages,
        "effect_boundary": effect_boundary,
        "actions_not_taken": actions_not_taken,
        "receipt": receipt_payload,
        "governed": True,
        "execution_allowed": False,
        "outcome": outcome,
    }


def _pydantic_payload(model: BaseModel) -> dict[str, Any]:
    """Return a stable dict across Pydantic major versions."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _valid_whqr_semver(version: str) -> bool:
    parts = version.split(".")
    return len(parts) == 3 and all(_valid_semver_core_identifier(part) for part in parts)


def _valid_semver_core_identifier(value: str) -> bool:
    if not value.isascii() or not value.isdecimal():
        return False
    return value == "0" or not value.startswith("0")


def _valid_sha256_digest_ref(value: str) -> bool:
    prefix = "sha256:"
    return value.startswith(prefix) and _valid_sha256_hex_suffix(value, prefix)


def _valid_whqr_replay_ref(value: str) -> bool:
    prefix = "whqr://replay/sha256:"
    return value.startswith(prefix) and _valid_sha256_hex_suffix(value, prefix)


def _valid_sha256_hex_suffix(value: str, prefix: str) -> bool:
    suffix = value[len(prefix):]
    return len(suffix) == 64 and all(char in "0123456789abcdef" for char in suffix)


_WHQR_REPLAY_BINDING_FIELDS = frozenset(
    {"replay_ref", "canonical_hash", "semantics_hash", "version"}
)


def _validated_whqr_replay_binding(source: Any) -> dict[str, str]:
    if not isinstance(source, Mapping):
        return {}
    if set(source) != _WHQR_REPLAY_BINDING_FIELDS:
        return {}
    replay_ref = source.get("replay_ref")
    canonical_hash = source.get("canonical_hash")
    semantics_hash = source.get("semantics_hash")
    version = source.get("version")
    if not (
        isinstance(replay_ref, str)
        and isinstance(canonical_hash, str)
        and isinstance(semantics_hash, str)
        and isinstance(version, str)
    ):
        return {}
    if not (
        _valid_sha256_digest_ref(canonical_hash)
        and _valid_sha256_digest_ref(semantics_hash)
        and _valid_whqr_replay_ref(replay_ref)
        and replay_ref == f"whqr://replay/{canonical_hash}"
        and _valid_whqr_semver(version)
    ):
        return {}
    return {
        "replay_ref": replay_ref,
        "canonical_hash": canonical_hash,
        "semantics_hash": semantics_hash,
        "version": version,
    }


def _capability_friction_control_panel_read_model(friction_control: Mapping[str, Any]) -> dict[str, Any]:
    """Project friction control into the generic operator control tower panel shape.

    Input contract: capability_friction_control read model.
    Output contract: read-only panel model with bounded summary metadata.
    Error contract: malformed fields degrade to empty values; no execution
    handles or raw capability internals are exposed.
    """
    summary = friction_control.get("summary", {})
    workflow = friction_control.get("developer_workflow_v1", {})
    if not isinstance(summary, Mapping):
        summary = {}
    if not isinstance(workflow, Mapping):
        workflow = {}
    source_refs = friction_control.get("source_refs", {})
    if not isinstance(source_refs, Mapping):
        source_refs = {}
    capabilities = friction_control.get("capabilities", ())
    capability_cards = [item for item in capabilities if isinstance(item, Mapping)] if isinstance(capabilities, list) else []
    safe_zones = tuple(str(zone) for zone in friction_control.get("safe_automatic_zones", ()) if str(zone).strip())
    dangerous_zones = tuple(str(zone) for zone in friction_control.get("dangerous_zones", ()) if str(zone).strip())
    rollback_default_count = sum(1 for item in capability_cards if item.get("rollback_default") is True)
    rollback_required_count = sum(
        1
        for item in capability_cards
        if isinstance(item.get("required_before_unlock"), list)
        and "rollback" in {str(value) for value in item.get("required_before_unlock", ())}
    )
    next_unlock_queue = _capability_next_unlock_queue(capability_cards, limit=5)
    capability_passports = _capability_passport_cards(capability_cards, limit=12)
    mode_selector = _capability_mode_selector(capability_cards, limit=12)
    friction_mode_summary = _friction_mode_summary(mode_selector)
    sandbox_to_pr_policy = _sandbox_to_pr_policy(capability_passports)
    safe_automatic_action_candidates = _safe_automatic_action_candidates(safe_zones)
    safe_local_action_queue_summary = _safe_local_action_queue_summary(
        safe_candidates=safe_automatic_action_candidates,
        friction_mode_summary=friction_mode_summary,
    )
    dangerous_zone_blockers = _dangerous_zone_blockers(dangerous_zones)
    dangerous_action_blocker_summary = _dangerous_action_blocker_summary(
        dangerous_blockers=dangerous_zone_blockers,
    )
    lab_real_world_summary = _lab_real_world_summary(
        workflow=workflow,
        safe_candidates=safe_automatic_action_candidates,
        dangerous_blockers=dangerous_zone_blockers,
        fast_mode_lab_ready_count=int(summary.get("fast_mode_lab_ready_count", 0) or 0),
        real_world_write_status=str(summary.get("real_world_write_status", "")),
    )
    approval_boundary_summary = _approval_boundary_summary(
        next_unlock_queue=next_unlock_queue,
        safe_candidates=safe_automatic_action_candidates,
        dangerous_blockers=dangerous_zone_blockers,
        sandbox_to_pr_policy=sandbox_to_pr_policy,
    )
    rollback_control_summary = _rollback_control_summary(
        rollback_default_count=rollback_default_count,
        rollback_required_count=rollback_required_count,
        capability_count=len(capability_cards),
        sandbox_to_pr_policy=sandbox_to_pr_policy,
    )
    unlock_readiness_summary = _unlock_readiness_summary(
        next_unlock_queue=next_unlock_queue,
        safe_candidates=safe_automatic_action_candidates,
        dangerous_blockers=dangerous_zone_blockers,
    )
    capability_registry_summary = _capability_registry_summary(
        capability_cards=capability_cards,
        next_unlock_queue=next_unlock_queue,
    )
    safe_vs_dangerous_summary = _safe_vs_dangerous_summary(
        safe_candidates=safe_automatic_action_candidates,
        dangerous_blockers=dangerous_zone_blockers,
    )
    control_system_summary = _control_system_summary(
        workflow=workflow,
        workflow_status=str(workflow.get("status") or "awaiting_evidence"),
        action_needed="",
        capability_registry_summary=capability_registry_summary,
        friction_mode_summary=friction_mode_summary,
        lab_real_world_summary=lab_real_world_summary,
        safe_vs_dangerous_summary=safe_vs_dangerous_summary,
        unlock_readiness_summary=unlock_readiness_summary,
    )
    workflow_status = str(workflow.get("status") or "awaiting_evidence")
    missing_capabilities = workflow.get("missing_capability_ids", ())
    if not isinstance(missing_capabilities, list):
        missing_capabilities = []
    if workflow_status == "preflight_ready":
        reason = "local lab workflow can prepare sandbox diff and receipt; pull request or external write remains approval-bound"
        action_needed = "review diff receipt before approving pull request candidate"
    elif missing_capabilities:
        reason = "developer workflow is missing registered capability records"
        action_needed = "register missing software_dev capability records"
    else:
        reason = "developer workflow needs lab-readiness evidence"
        action_needed = "supply sandbox, rollback, and dry-run receipt evidence"
    control_system_summary["status"] = workflow_status
    control_system_summary["action_needed"] = action_needed
    control_system_summary["operator_message"] = (
        f"Control system in {control_system_summary['recommended_mode']} mode; "
        f"{control_system_summary['safe_candidate_count']} safe local candidates; "
        f"next unlock {control_system_summary['next_unlock']}"
    )
    return {
        "source_surface": "capability_friction_control",
        "item_count": int(summary.get("capability_count", len(capability_cards)) or 0),
        "freshness_seconds": 0,
        "signal_count": 0,
        "blocked_count": sum(1 for item in capability_cards if int(item.get("blocked_action_count", 0) or 0) > 0),
        "review_count": int(summary.get("approval_required_count", 0) or 0),
        "evidence_refs": (
            str(friction_control.get("read_model_id") or "capability_friction_control.foundation.v1"),
            str(workflow.get("workflow_id") or "mullu_developer_workflow.v1"),
        ),
        "raw_tool_surface_exposed": False,
        "metadata": {
            "capability_surface": str(source_refs.get("capability_surface", "")),
            "default_boundary": "lab",
            "fast_mode_lab_ready_count": int(summary.get("fast_mode_lab_ready_count", 0) or 0),
            "real_world_write_status": str(summary.get("real_world_write_status", "")),
            "safe_automatic_zones": list(safe_zones),
            "safe_automatic_zone_count": len(safe_zones),
            "safe_automatic_action_candidates": safe_automatic_action_candidates,
            "safe_local_action_queue_summary": safe_local_action_queue_summary,
            "dangerous_zones": list(dangerous_zones),
            "dangerous_zone_count": len(dangerous_zones),
            "dangerous_zone_blockers": dangerous_zone_blockers,
            "dangerous_action_blocker_summary": dangerous_action_blocker_summary,
            "lab_real_world_summary": lab_real_world_summary,
            "approval_boundary_summary": approval_boundary_summary,
            "rollback_control_summary": rollback_control_summary,
            "capability_registry_summary": capability_registry_summary,
            "safe_vs_dangerous_summary": safe_vs_dangerous_summary,
            "unlock_readiness_summary": unlock_readiness_summary,
            "control_system_summary": control_system_summary,
            "next_unlock_queue": next_unlock_queue,
            "next_unlock_queue_count": len(next_unlock_queue),
            "capability_passports": capability_passports,
            "capability_passport_count": len(capability_passports),
            "mode_selector": mode_selector,
            "friction_mode_summary": friction_mode_summary,
            "sandbox_to_pr_policy": sandbox_to_pr_policy,
            "sandbox_to_pr_now": friction_control.get("sandbox_to_pr_now", {}),
            "rollback_summary": {
                "rollback_default_count": rollback_default_count,
                "rollback_required_count": rollback_required_count,
                "rollback_policy": "If Mullu can change it, Mullu must also know how to undo it.",
                "rollback_receipt_source": "developer_workflow_run.software_receipt_binding.stage_evidence.rollback_completed",
            },
            "developer_workflow_v1": {
                "workflow_id": str(workflow.get("workflow_id", "")),
                "status": workflow_status,
                "lab_mode_allowed": workflow.get("lab_mode_allowed") is True,
                "real_world_effects_allowed": workflow.get("real_world_effects_allowed") is True,
                "approval_boundary": str(workflow.get("approval_boundary", "")),
                "next_unlock": str(workflow.get("next_unlock", "")),
            },
            "developer_workflow_summary": {
                "task": "Mullu Developer Workflow v1",
                "status": workflow_status,
                "reason": reason,
                "next_unlock": str(workflow.get("next_unlock", "")),
                "risk": "low, local lab only",
                "action_needed": action_needed,
            },
        },
    }


def _safe_automatic_action_candidates(safe_zones: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return reusable no-effect action-card candidates for safe local zones."""

    labels = {
        "write_docs": "Prepare documentation update",
        "write_tests": "Prepare test update",
        "write_examples": "Prepare example update",
        "write_local_demo_files": "Prepare local demo file",
        "update_README": "Prepare README update",
        "generate_schemas": "Prepare schema generation",
        "generate_validators": "Prepare validator generation",
    }
    candidates: list[dict[str, Any]] = []
    for zone in safe_zones:
        zone_id = str(zone).strip()
        if not zone_id:
            continue
        title = labels.get(zone_id, f"Prepare {zone_id.replace('_', ' ')}")
        candidates.append({
            "candidate_id": f"safe_zone.{zone_id}",
            "zone": zone_id,
            "title": title,
            "status": "candidate",
            "primary_action": f"{title} in local sandbox",
            "primary_href": "/operator/control-tower?domain=software_dev",
            "risk": "low, local lab only",
            "execution_boundary": "local_lab_only",
            "approval_required": False,
            "external_effects_allowed": False,
        })
    return candidates[:8]


def _dangerous_zone_blockers(dangerous_zones: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return explicit blocked cards for dangerous zones."""

    labels = {
        "delete_files": "Delete files",
        "touch_secrets": "Touch secrets",
        "send_email": "Send email",
        "move_money": "Move money",
        "deploy": "Deploy",
        "merge_to_main": "Merge to main",
        "write_production_data": "Write production data",
    }
    blockers: list[dict[str, Any]] = []
    for zone in dangerous_zones:
        zone_id = str(zone).strip()
        if not zone_id:
            continue
        title = labels.get(zone_id, zone_id.replace("_", " ").title())
        blockers.append({
            "blocker_id": f"dangerous_zone.{zone_id}",
            "zone": zone_id,
            "title": title,
            "status": "blocked",
            "reason": "dangerous_zone_requires_explicit_approval",
            "required_evidence": [
                "operator_approval",
                "rollback_plan",
                "effect_receipt",
            ],
            "risk": "high, real-world boundary",
            "execution_boundary": "real_world",
            "approval_required": True,
            "external_effects_allowed": False,
        })
    return blockers[:8]


def _safe_local_action_queue_summary(
    *,
    safe_candidates: list[Mapping[str, Any]],
    friction_mode_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact queue summary for safe local-lab action candidates."""

    first_candidate = safe_candidates[0] if safe_candidates else {}
    recommended_mode = str(friction_mode_summary.get("foundation_recommended_mode") or "fast")
    candidate_count = len(safe_candidates)
    return {
        "summary_id": "safe_local_action_queue.foundation",
        "queue_status": "ready" if candidate_count else "empty",
        "candidate_count": candidate_count,
        "first_candidate_id": str(first_candidate.get("candidate_id") or ""),
        "first_zone": str(first_candidate.get("zone") or ""),
        "first_action": str(first_candidate.get("primary_action") or "prepare safe local sandbox work"),
        "recommended_mode": recommended_mode,
        "approval_required": False,
        "local_execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            f"{candidate_count} safe local actions queued for {recommended_mode} mode; "
            "approval not required for local preparation"
        ),
    }


def _dangerous_action_blocker_summary(
    *,
    dangerous_blockers: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a compact summary for dangerous real-world action blockers."""

    first_blocker = dangerous_blockers[0] if dangerous_blockers else {}
    blocker_count = len(dangerous_blockers)
    required_evidence = first_blocker.get("required_evidence", ()) if isinstance(first_blocker, Mapping) else ()
    if not isinstance(required_evidence, list):
        required_evidence = []
    required_evidence_ids = [str(item) for item in required_evidence if str(item).strip()][:8]
    return {
        "summary_id": "dangerous_action_blocker.foundation",
        "blocker_status": "blocked" if blocker_count else "clear",
        "blocker_count": blocker_count,
        "first_blocker_id": str(first_blocker.get("blocker_id") or ""),
        "first_zone": str(first_blocker.get("zone") or ""),
        "first_reason": str(
            first_blocker.get("reason") or "dangerous_zone_requires_explicit_approval"
        ),
        "required_evidence": required_evidence_ids,
        "approval_required": blocker_count > 0,
        "rollback_required": blocker_count > 0,
        "real_world_execution_boundary": "real_world",
        "external_effects_allowed": False,
        "operator_message": (
            f"{blocker_count} dangerous real-world zones blocked; "
            "approval, rollback, and effect receipt required before execution"
        ),
    }


def _safe_vs_dangerous_summary(
    *,
    safe_candidates: list[Mapping[str, Any]],
    dangerous_blockers: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return the compact safe-vs-dangerous dashboard headline."""

    first_safe = safe_candidates[0] if safe_candidates else {}
    first_blocker = dangerous_blockers[0] if dangerous_blockers else {}
    return {
        "summary_id": "safe_vs_dangerous.local_lab",
        "safe_candidate_count": len(safe_candidates),
        "dangerous_blocker_count": len(dangerous_blockers),
        "first_safe_zone": str(first_safe.get("zone") or ""),
        "first_safe_action": str(first_safe.get("primary_action") or "prepare safe local sandbox work"),
        "first_dangerous_zone": str(first_blocker.get("zone") or ""),
        "first_dangerous_reason": str(
            first_blocker.get("reason") or "dangerous_zone_requires_explicit_approval"
        ),
        "operator_message": (
            f"{len(safe_candidates)} local-lab candidates available; "
            f"{len(dangerous_blockers)} real-world zones blocked pending explicit approval"
        ),
        "safe_execution_boundary": "local_lab_only",
        "dangerous_execution_boundary": "real_world",
        "external_effects_allowed": False,
    }


def _control_system_summary(
    *,
    workflow: Mapping[str, Any],
    workflow_status: str,
    action_needed: str,
    capability_registry_summary: Mapping[str, Any],
    friction_mode_summary: Mapping[str, Any],
    lab_real_world_summary: Mapping[str, Any],
    safe_vs_dangerous_summary: Mapping[str, Any],
    unlock_readiness_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one product-facing control summary from existing projections."""

    next_required_evidence = unlock_readiness_summary.get("next_required_evidence", ())
    if not isinstance(next_required_evidence, list):
        next_required_evidence = []
    next_required_evidence = [
        str(item)
        for item in next_required_evidence
        if str(item).strip()
    ][:8]
    recommended_mode = str(friction_mode_summary.get("foundation_recommended_mode") or "fast")
    safe_candidate_count = int(safe_vs_dangerous_summary.get("safe_candidate_count") or 0)
    dangerous_blocker_count = int(safe_vs_dangerous_summary.get("dangerous_blocker_count") or 0)
    next_unlock = str(unlock_readiness_summary.get("next_unlock") or workflow.get("next_unlock") or "approval")
    return {
        "summary_id": "control_system.foundation",
        "task": "Mullu Developer Workflow v1",
        "status": workflow_status or "awaiting_evidence",
        "recommended_mode": recommended_mode,
        "lab_mode_allowed": lab_real_world_summary.get("lab_mode_allowed") is True,
        "capability_count": int(capability_registry_summary.get("capability_count") or 0),
        "pending_unlock_count": int(unlock_readiness_summary.get("pending_unlock_count") or 0),
        "safe_candidate_count": safe_candidate_count,
        "dangerous_blocker_count": dangerous_blocker_count,
        "next_capability_id": str(unlock_readiness_summary.get("next_capability_id") or ""),
        "next_unlock": next_unlock,
        "next_required_evidence": next_required_evidence,
        "next_required_evidence_count": len(next_required_evidence),
        "risk": "low, local lab only",
        "action_needed": action_needed or "inspect workflow receipts",
        "operator_message": (
            f"Control system in {recommended_mode} mode; "
            f"{safe_candidate_count} safe local candidates; next unlock {next_unlock}"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _capability_registry_summary(
    *,
    capability_cards: list[Mapping[str, Any]],
    next_unlock_queue: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a compact answer to what is unlocked, blocked, and needed next."""

    first_blocked = next_unlock_queue[0] if next_unlock_queue else {}
    required = first_blocked.get("required_evidence", ()) if isinstance(first_blocked, Mapping) else ()
    next_required_evidence = [
        str(value)
        for value in required
        if str(value).strip()
    ][:8] if isinstance(required, list) else []
    blocked_count = sum(
        1
        for item in capability_cards
        if int(item.get("blocked_action_count", 0) or 0) > 0
    )
    approval_required_count = sum(
        1
        for item in capability_cards
        if str(item.get("next_unlock") or "").strip() == "approval"
    )
    preflight_ready_count = sum(
        1
        for item in capability_cards
        if str(item.get("status") or item.get("friction_status") or "").strip() == "preflight_ready"
    )
    next_capability_id = str(first_blocked.get("capability_id") or "") if isinstance(first_blocked, Mapping) else ""
    next_blocked_reason = str(first_blocked.get("next_unlock") or "review") if isinstance(first_blocked, Mapping) else "review"
    return {
        "summary_id": "capability_registry.foundation",
        "capability_count": len(capability_cards),
        "preflight_ready_count": preflight_ready_count,
        "blocked_count": blocked_count,
        "approval_required_count": approval_required_count,
        "pending_unlock_count": len(next_unlock_queue),
        "next_blocked_capability_id": next_capability_id,
        "next_blocked_reason": next_blocked_reason,
        "next_required_evidence": next_required_evidence,
        "next_required_evidence_count": len(next_required_evidence),
        "operator_message": (
            f"{preflight_ready_count} capabilities preflight-ready; "
            f"{blocked_count} capabilities blocked; next evidence is "
            f"{next_blocked_reason} for {next_capability_id or 'capability review'}"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _lab_real_world_summary(
    *,
    workflow: Mapping[str, Any],
    safe_candidates: list[Mapping[str, Any]],
    dangerous_blockers: list[Mapping[str, Any]],
    fast_mode_lab_ready_count: int,
    real_world_write_status: str,
) -> dict[str, Any]:
    """Return the compact Lab vs Real-world operating boundary."""

    lab_mode_allowed = workflow.get("lab_mode_allowed") is True
    real_world_effects_allowed = workflow.get("real_world_effects_allowed") is True
    dangerous_approval_count = sum(
        1
        for item in dangerous_blockers
        if isinstance(item, Mapping) and item.get("approval_required") is True
    )
    real_world_status = real_world_write_status or "blocked"
    return {
        "summary_id": "lab_real_world.foundation",
        "lab_mode_allowed": lab_mode_allowed,
        "lab_safe_candidate_count": len(safe_candidates),
        "fast_mode_lab_ready_count": max(0, fast_mode_lab_ready_count),
        "real_world_effects_allowed": real_world_effects_allowed,
        "real_world_write_status": real_world_status,
        "dangerous_blocker_count": len(dangerous_blockers),
        "dangerous_approval_required_count": dangerous_approval_count,
        "operator_message": (
            f"Lab mode can prepare {len(safe_candidates)} local candidates; "
            f"real-world writes remain {real_world_status}; "
            f"{dangerous_approval_count} dangerous zones need approval"
        ),
        "lab_execution_boundary": "local_lab_only",
        "real_world_execution_boundary": "real_world",
        "external_effects_allowed": False,
    }


def _approval_boundary_summary(
    *,
    next_unlock_queue: list[Mapping[str, Any]],
    safe_candidates: list[Mapping[str, Any]],
    dangerous_blockers: list[Mapping[str, Any]],
    sandbox_to_pr_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the compact local automatic vs approval-required boundary."""

    approval_unlock_count = sum(
        1
        for item in next_unlock_queue
        if isinstance(item, Mapping) and str(item.get("next_unlock") or "") == "approval"
    )
    dangerous_approval_count = sum(
        1
        for item in dangerous_blockers
        if isinstance(item, Mapping) and item.get("approval_required") is True
    )
    pr_approval_required = sandbox_to_pr_policy.get("approval_required") is True
    return {
        "summary_id": "approval_boundary.foundation",
        "local_auto_candidate_count": len(safe_candidates),
        "approval_unlock_count": approval_unlock_count,
        "dangerous_approval_required_count": dangerous_approval_count,
        "pr_approval_required": pr_approval_required,
        "approval_boundary": "before_pr_or_real_world_effect",
        "next_approval_capability_id": str(
            next(
                (
                    item.get("capability_id")
                    for item in next_unlock_queue
                    if isinstance(item, Mapping) and str(item.get("next_unlock") or "") == "approval"
                ),
                "",
            )
            or ""
        ),
        "operator_message": (
            f"{len(safe_candidates)} local automatic candidates; "
            f"{approval_unlock_count} capability unlocks need approval; "
            f"{dangerous_approval_count} dangerous zones remain approval-bound"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _rollback_control_summary(
    *,
    rollback_default_count: int,
    rollback_required_count: int,
    capability_count: int,
    sandbox_to_pr_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the compact rollback-default coverage and receipt posture."""

    rollback_default_ready = rollback_default_count > 0 and rollback_default_count >= rollback_required_count
    pr_policy_ready = sandbox_to_pr_policy.get("policy_ready") is True
    return {
        "summary_id": "rollback_control.foundation",
        "rollback_default_count": max(0, rollback_default_count),
        "rollback_required_count": max(0, rollback_required_count),
        "capability_count": max(0, capability_count),
        "rollback_default_ready": rollback_default_ready,
        "sandbox_to_pr_policy_ready": pr_policy_ready,
        "rollback_policy": "If Mullu can change it, Mullu must also know how to undo it.",
        "rollback_receipt_source": "developer_workflow_run.software_receipt_binding.stage_evidence.rollback_completed",
        "operator_message": (
            f"{rollback_default_count} capabilities carry rollback default; "
            f"{rollback_required_count} unlocks require rollback evidence; "
            "rollback execution remains receipt-bound"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _unlock_readiness_summary(
    *,
    next_unlock_queue: list[Mapping[str, Any]],
    safe_candidates: list[Mapping[str, Any]],
    dangerous_blockers: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return the next unlock evidence bridge for the operator dashboard."""

    first_unlock = next_unlock_queue[0] if next_unlock_queue else {}
    required = first_unlock.get("required_evidence", ()) if isinstance(first_unlock, Mapping) else ()
    next_required_evidence = [
        str(value)
        for value in required
        if str(value).strip()
    ][:8] if isinstance(required, list) else []
    approval_blocker_count = sum(
        1
        for item in dangerous_blockers
        if isinstance(item, Mapping) and item.get("approval_required") is True
    )
    next_capability_id = str(first_unlock.get("capability_id") or "") if isinstance(first_unlock, Mapping) else ""
    next_unlock = str(first_unlock.get("next_unlock") or "approval") if isinstance(first_unlock, Mapping) else "approval"
    return {
        "summary_id": "unlock_readiness.local_lab",
        "pending_unlock_count": len(next_unlock_queue),
        "safe_candidate_count": len(safe_candidates),
        "dangerous_blocker_count": len(dangerous_blockers),
        "next_capability_id": next_capability_id,
        "next_unlock": next_unlock,
        "next_required_evidence": next_required_evidence,
        "next_required_evidence_count": len(next_required_evidence),
        "safe_candidates_ready": len(safe_candidates),
        "dangerous_blockers_requiring_approval": approval_blocker_count,
        "operator_message": (
            f"{len(next_unlock_queue)} pending unlocks; next evidence for "
            f"{next_capability_id or 'capability review'} is {next_unlock}; "
            f"{approval_blocker_count} dangerous zones require explicit approval"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _capability_next_unlock_queue(
    capability_cards: list[Mapping[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Return a bounded operator queue of next capability unlock evidence."""
    queue: list[dict[str, Any]] = []
    for item in capability_cards:
        next_unlock = str(item.get("next_unlock") or "").strip()
        required = item.get("required_before_unlock", ())
        blocked = item.get("blocked_actions", ())
        if next_unlock in {"", "none"} and not required and not blocked:
            continue
        required_evidence = tuple(str(value) for value in required if str(value).strip()) if isinstance(required, list) else ()
        blocked_actions = tuple(str(value) for value in blocked if str(value).strip()) if isinstance(blocked, list) else ()
        queue.append({
            "capability_id": str(item.get("capability_id") or ""),
            "unlock_level": str(item.get("unlock_level") or ""),
            "friction_status": str(item.get("friction_status") or ""),
            "next_unlock": next_unlock or (required_evidence[0] if required_evidence else "review"),
            "required_evidence": list(required_evidence),
            "blocked_action_count": len(blocked_actions),
            "operating_boundary": str(item.get("operating_boundary") or ""),
        })
    queue.sort(key=lambda entry: (
        0 if entry["next_unlock"] == "approval" else 1,
        str(entry["unlock_level"]),
        str(entry["capability_id"]),
    ))
    return queue[:max(0, limit)]


def _capability_passport_cards(
    capability_cards: list[Mapping[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Return bounded read-only capability passport cards for the operator tower."""
    passports: list[dict[str, Any]] = []
    for item in capability_cards:
        required = item.get("required_before_unlock", ())
        blocked = item.get("blocked_actions", ())
        passports.append({
            "capability_id": str(item.get("capability_id") or ""),
            "status": str(item.get("friction_status") or ""),
            "unlock_level": str(item.get("unlock_level") or ""),
            "unlock_label": str(item.get("unlock_label") or ""),
            "operating_boundary": str(item.get("operating_boundary") or ""),
            "fast_mode_admission": str(item.get("fast_mode_admission") or ""),
            "balanced_mode_admission": str(item.get("balanced_mode_admission") or ""),
            "strict_mode_admission": str(item.get("strict_mode_admission") or ""),
            "next_unlock": str(item.get("next_unlock") or ""),
            "required_evidence": [str(value) for value in required if str(value).strip()]
            if isinstance(required, list) else [],
            "blocked_action_count": len(blocked) if isinstance(blocked, list) else 0,
            "rollback_default": item.get("rollback_default") is True,
        })
    passports.sort(key=lambda entry: (str(entry["unlock_level"]), str(entry["capability_id"])))
    return passports[:max(0, limit)]


def _capability_mode_selector(
    capability_cards: list[Mapping[str, Any]],
    *,
    limit: int,
) -> dict[str, Any]:
    """Return a read-only Strict/Balanced/Fast capability mode projection."""
    modes = ("strict", "balanced", "fast")
    summary = {
        mode: {"allowed_count": 0, "approval_required_count": 0, "blocked_count": 0}
        for mode in modes
    }
    rows: list[dict[str, Any]] = []
    for item in capability_cards:
        admissions = {
            "strict": str(item.get("strict_mode_admission") or ""),
            "balanced": str(item.get("balanced_mode_admission") or ""),
            "fast": str(item.get("fast_mode_admission") or ""),
        }
        for mode, admission in admissions.items():
            if admission.startswith("allowed"):
                summary[mode]["allowed_count"] += 1
            elif "approval_required" in admission:
                summary[mode]["approval_required_count"] += 1
            else:
                summary[mode]["blocked_count"] += 1
        rows.append({
            "capability_id": str(item.get("capability_id") or ""),
            "unlock_level": str(item.get("unlock_level") or ""),
            "strict": admissions["strict"],
            "balanced": admissions["balanced"],
            "fast": admissions["fast"],
            "recommended_mode": "fast" if admissions["fast"].startswith("allowed") else "balanced",
            "next_unlock": str(item.get("next_unlock") or ""),
        })
    rows.sort(key=lambda entry: (str(entry["unlock_level"]), str(entry["capability_id"])))
    return {
        "default_mode": "balanced",
        "foundation_recommended_mode": "fast",
        "summary": summary,
        "capabilities": rows[:max(0, limit)],
    }


def _friction_mode_summary(mode_selector: Mapping[str, Any]) -> dict[str, Any]:
    """Return the compact Strict/Balanced/Fast posture for operator receipts."""

    summary = mode_selector.get("summary", {}) if isinstance(mode_selector, Mapping) else {}
    if not isinstance(summary, Mapping):
        summary = {}

    def counts(mode: str) -> tuple[int, int, int]:
        mode_counts = summary.get(mode, {})
        if not isinstance(mode_counts, Mapping):
            return (0, 0, 0)
        return (
            int(mode_counts.get("allowed_count", 0) or 0),
            int(mode_counts.get("approval_required_count", 0) or 0),
            int(mode_counts.get("blocked_count", 0) or 0),
        )

    strict_allowed, strict_approval, strict_blocked = counts("strict")
    balanced_allowed, balanced_approval, balanced_blocked = counts("balanced")
    fast_allowed, fast_approval, fast_blocked = counts("fast")
    default_mode = str(mode_selector.get("default_mode") or "balanced") if isinstance(mode_selector, Mapping) else "balanced"
    recommended_mode = (
        str(mode_selector.get("foundation_recommended_mode") or "fast")
        if isinstance(mode_selector, Mapping)
        else "fast"
    )
    return {
        "summary_id": "friction_mode.foundation",
        "default_mode": default_mode,
        "foundation_recommended_mode": recommended_mode,
        "strict_allowed_count": strict_allowed,
        "strict_approval_required_count": strict_approval,
        "strict_blocked_count": strict_blocked,
        "balanced_allowed_count": balanced_allowed,
        "balanced_approval_required_count": balanced_approval,
        "balanced_blocked_count": balanced_blocked,
        "fast_allowed_count": fast_allowed,
        "fast_approval_required_count": fast_approval,
        "fast_blocked_count": fast_blocked,
        "operator_message": (
            f"{recommended_mode} mode recommended for local lab; "
            f"fast allows {fast_allowed} capabilities; "
            f"balanced holds {balanced_approval} approvals"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _sandbox_to_pr_policy(capability_passports: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Return static policy readiness for the sandbox-to-PR developer path."""
    passports_by_id = {
        str(item.get("capability_id") or ""): item
        for item in capability_passports
        if isinstance(item, Mapping)
    }
    change_passport = passports_by_id.get("software_dev.change.run", {})
    pr_passport = passports_by_id.get("software_dev.pr_candidate.prepare", {})
    pr_required_evidence = pr_passport.get("required_evidence", ()) if isinstance(pr_passport, Mapping) else ()
    approval_required = (
        isinstance(pr_required_evidence, list)
        and "approval" in {str(value) for value in pr_required_evidence}
    ) or str(pr_passport.get("next_unlock") or "") == "approval"
    rollback_default = isinstance(change_passport, Mapping) and change_passport.get("rollback_default") is True
    change_passport_present = bool(change_passport)
    pr_passport_present = bool(pr_passport)
    return {
        "change_capability_id": "software_dev.change.run",
        "pr_capability_id": "software_dev.pr_candidate.prepare",
        "change_passport_present": change_passport_present,
        "pr_passport_present": pr_passport_present,
        "rollback_default": rollback_default,
        "approval_required": approval_required,
        "policy_ready": change_passport_present and pr_passport_present and rollback_default and approval_required,
        "policy_boundary": "lab_to_approval_bound_pr",
    }


def _approval_history_panel_read_model(approval_history: Mapping[str, Any]) -> dict[str, Any]:
    """Project approval history into a read-only control tower panel."""
    status_counts = approval_history.get("status_counts", {})
    if not isinstance(status_counts, Mapping):
        status_counts = {}
    pending_count = int(status_counts.get("pending", 0) or 0)
    denied_count = int(status_counts.get("denied", 0) or 0)
    expired_count = int(status_counts.get("expired", 0) or 0)
    return {
        "source_surface": "operator_approval_history",
        "item_count": int(approval_history.get("total", approval_history.get("count", 0)) or 0),
        "freshness_seconds": 0,
        "signal_count": 0,
        "blocked_count": denied_count + expired_count,
        "review_count": pending_count,
        "evidence_refs": (str(approval_history.get("schema_ref") or APPROVAL_HISTORY_SCHEMA_REF),),
        "raw_tool_surface_exposed": False,
        "metadata": {
            "pending_count": pending_count,
            "approved_count": int(status_counts.get("approved", 0) or 0),
            "denied_count": denied_count,
            "expired_count": expired_count,
            "approval_history_href": "/operator/approvals",
            "approval_history_read_model_href": "/operator/approvals/read-model",
        },
    }


def _receipt_viewer_panel_read_model(receipt_viewer: Mapping[str, Any]) -> dict[str, Any]:
    """Project receipt groups into a proof-explorer control tower panel."""
    groups = receipt_viewer.get("receipt_groups", ())
    receipt_groups = [item for item in groups if isinstance(item, Mapping)] if isinstance(groups, list) else []
    blocked_count = sum(1 for item in receipt_groups if item.get("task_status") == "blocked")
    review_count = sum(
        1
        for item in receipt_groups
        if item.get("task_status") in {"waiting_for_approval", "requires_review"}
    )
    return {
        "source_surface": "operator_receipt_viewer",
        "item_count": int(receipt_viewer.get("total_receipts", receipt_viewer.get("count", 0)) or 0),
        "freshness_seconds": 0,
        "signal_count": 0,
        "blocked_count": blocked_count,
        "review_count": review_count,
        "evidence_refs": (str(receipt_viewer.get("schema_ref") or RECEIPT_VIEWER_SCHEMA_REF),),
        "raw_tool_surface_exposed": False,
        "metadata": {
            "receipt_group_count": int(receipt_viewer.get("count", 0) or 0),
            "total_receipts": int(receipt_viewer.get("total_receipts", 0) or 0),
            "receipt_viewer_href": "/operator/receipts",
            "receipt_viewer_read_model_href": "/operator/receipts/read-model",
        },
    }


def _load_local_sandbox_receipt_bundle(*, include_local_sandbox_receipts: bool) -> dict[str, Any] | None:
    """Load the fixed local sandbox receipt bundle when explicitly requested."""
    if not include_local_sandbox_receipts:
        return None
    path = LOCAL_SANDBOX_RECEIPT_BUNDLE_PATH
    if not path.exists():
        raise HTTPException(status_code=404, detail="local_sandbox_receipt_bundle_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="local_sandbox_receipt_bundle_invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="local_sandbox_receipt_bundle_root_must_be_object")
    if payload.get("external_effects_allowed") is not False:
        raise HTTPException(status_code=422, detail="local_sandbox_receipt_bundle_external_effect_overclaim")
    if payload.get("execution_boundary") != "local_lab_only":
        raise HTTPException(status_code=422, detail="local_sandbox_receipt_bundle_boundary_invalid")
    receipts = payload.get("receipts")
    if not isinstance(receipts, list):
        raise HTTPException(status_code=422, detail="local_sandbox_receipt_bundle_receipts_invalid")
    return payload


def _load_local_sandbox_proof_report(*, include_local_sandbox_receipts: bool) -> dict[str, Any] | None:
    """Load the last local sandbox proof report when explicitly requested."""

    if not include_local_sandbox_receipts:
        return None
    path = LOCAL_SANDBOX_PROOF_REPORT_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="local_sandbox_proof_report_invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="local_sandbox_proof_report_root_must_be_object")
    validation = validate_developer_workflow_local_sandbox_proof_report(report_path=path)
    if not validation.ok:
        raise HTTPException(status_code=422, detail="local_sandbox_proof_report_contract_invalid")
    if payload.get("external_effects_allowed") is not False:
        raise HTTPException(status_code=422, detail="local_sandbox_proof_report_external_effect_overclaim")
    if payload.get("execution_performed") is not False:
        raise HTTPException(status_code=422, detail="local_sandbox_proof_report_execution_overclaim")
    artifacts = payload.get("generated_artifacts", {})
    if artifacts is not None and not isinstance(artifacts, dict):
        raise HTTPException(status_code=422, detail="local_sandbox_proof_report_artifacts_invalid")
    return payload


def _load_local_developer_workflow_operator_receipt() -> dict[str, Any]:
    """Load the generated Developer Workflow operator receipt for read-only status."""

    path = LOCAL_DEVELOPER_WORKFLOW_OPERATOR_RECEIPT_PATH
    if not path.exists():
        raise HTTPException(status_code=404, detail="developer_workflow_operator_receipt_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="developer_workflow_operator_receipt_invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="developer_workflow_operator_receipt_root_must_be_object")
    validation = validate_developer_workflow_operator_receipt(receipt=payload, receipt_path=path)
    if not validation.ok:
        raise HTTPException(status_code=422, detail="developer_workflow_operator_receipt_contract_invalid")
    if payload.get("execution_performed") is not False:
        raise HTTPException(status_code=422, detail="developer_workflow_operator_receipt_execution_overclaim")
    return payload


def _developer_workflow_status_read_model(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Return the compact product status row for Developer Workflow v1."""

    operator_status = _developer_workflow_operator_status_from_generated_receipt(receipt)
    readiness_status = str(operator_status["readiness_status"])
    first_next_evidence = str(operator_status["first_next_evidence"])
    next_evidence = operator_status.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    evidence_text = ", ".join(str(item) for item in next_evidence if str(item).strip()) or "none"
    action_banner = developer_workflow_operator_action_banner(
        external_ready=operator_status["ready_for_external_pr_execution"] is True,
        external_approval_status=str(operator_status["external_approval_status"]),
        command_preview_rendered=operator_status["command_preview_rendered"] is True,
        next_unlock=first_next_evidence,
        evidence_text=evidence_text,
    )
    return {
        "read_model_id": "operator_developer_workflow_status.read_model",
        "projection_only": True,
        "external_effects_allowed": False,
        "task": "Governed Developer Workflow v1",
        "status": readiness_status,
        "reason": _developer_workflow_status_reason(readiness_status, first_next_evidence),
        "next_unlock": first_next_evidence,
        "risk": _developer_workflow_status_risk(readiness_status),
        "action_needed": _developer_workflow_status_action(readiness_status, first_next_evidence),
        "summary": {
            "solver_outcome": operator_status["solver_outcome"],
            "workflow_run_id": operator_status["workflow_run_id"],
            "sandbox_receipts_completed": operator_status["sandbox_receipts_completed"],
            "sandbox_receipts_required": operator_status["sandbox_receipts_required"],
            "local_candidate_ready": operator_status["local_candidate_ready"],
            "pr_tool_admitted": operator_status["pr_tool_admitted"],
            "external_approval_status": operator_status["external_approval_status"],
            "action_banner": action_banner,
            "rollback_required": operator_status["rollback_required"],
            "rollback_command_count": operator_status["rollback_command_count"],
            "command_preview_rendered": operator_status["command_preview_rendered"],
            "execution_performed": False,
            "receipt_hash": operator_status["receipt_hash"],
        },
        "source_ref": str(LOCAL_DEVELOPER_WORKFLOW_OPERATOR_RECEIPT_PATH.as_posix()),
    }


def _developer_workflow_status_reason(readiness_status: str, next_evidence: str) -> str:
    if readiness_status == "awaiting_external_pr_approval":
        return "operator external PR approval missing"
    if readiness_status == "awaiting_operator_approval":
        return "local PR candidate approval missing"
    if readiness_status == "awaiting_sandbox_receipts":
        return "sandbox receipt evidence incomplete"
    if readiness_status == "ready_for_external_pr_execution":
        return "external PR execution evidence is prepared but not executed by this read model"
    return f"next evidence required: {next_evidence}"


def _developer_workflow_status_risk(readiness_status: str) -> str:
    if readiness_status in {"awaiting_external_pr_approval", "ready_for_external_pr_execution"}:
        return "external repository write"
    return "low, local lab only"


def _developer_workflow_status_action(readiness_status: str, next_evidence: str) -> str:
    if readiness_status == "awaiting_external_pr_approval":
        return "approve or defer external PR execution"
    if readiness_status == "awaiting_operator_approval":
        return "approve local PR candidate preparation"
    if readiness_status == "awaiting_sandbox_receipts":
        return "complete sandbox receipt bundle"
    if readiness_status == "ready_for_external_pr_execution":
        return "execute external PR commands only through explicit approved path"
    return f"provide {next_evidence}"


def _load_local_rollback_summary_packet(*, include_local_sandbox_receipts: bool) -> dict[str, Any] | None:
    """Load the last local rollback summary packet when explicitly requested."""

    if not include_local_sandbox_receipts:
        return None
    path = LOCAL_ROLLBACK_SUMMARY_PACKET_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="local_rollback_summary_packet_invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="local_rollback_summary_packet_root_must_be_object")
    validation = validate_developer_workflow_local_rollback_summary_packet(
        packet_path=path,
        proof_report_path=LOCAL_SANDBOX_PROOF_REPORT_PATH,
    )
    if not validation.ok:
        raise HTTPException(status_code=422, detail="local_rollback_summary_packet_contract_invalid")
    if payload.get("external_effects_allowed") is not False:
        raise HTTPException(status_code=422, detail="local_rollback_summary_packet_external_effect_overclaim")
    if payload.get("rollback_execution_performed") is not False:
        raise HTTPException(status_code=422, detail="local_rollback_summary_packet_execution_overclaim")
    return payload


def _load_local_rollback_approval_packet(*, include_local_sandbox_receipts: bool) -> dict[str, Any] | None:
    """Load the last local rollback approval packet when explicitly requested."""

    if not include_local_sandbox_receipts:
        return None
    path = LOCAL_ROLLBACK_APPROVAL_PACKET_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="local_rollback_approval_packet_invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="local_rollback_approval_packet_root_must_be_object")
    validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=path,
        rollback_summary_path=LOCAL_ROLLBACK_SUMMARY_PACKET_PATH,
    )
    if not validation.ok:
        raise HTTPException(status_code=422, detail="local_rollback_approval_packet_contract_invalid")
    if payload.get("external_effects_allowed") is not False:
        raise HTTPException(status_code=422, detail="local_rollback_approval_packet_external_effect_overclaim")
    if payload.get("rollback_execution_performed") is not False:
        raise HTTPException(status_code=422, detail="local_rollback_approval_packet_execution_overclaim")
    return payload


def _load_local_rollback_execution_receipt(*, include_local_sandbox_receipts: bool) -> dict[str, Any] | None:
    """Load the last local rollback execution receipt when explicitly requested."""

    if not include_local_sandbox_receipts:
        return None
    path = LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="local_rollback_execution_receipt_invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="local_rollback_execution_receipt_root_must_be_object")
    validation = validate_developer_workflow_local_rollback_execution_receipt(receipt_path=path)
    if not validation.ok:
        raise HTTPException(status_code=422, detail="local_rollback_execution_receipt_contract_invalid")
    if payload.get("external_effects_allowed") is not False:
        raise HTTPException(status_code=422, detail="local_rollback_execution_receipt_external_effect_overclaim")
    if payload.get("execution_boundary") != "local_lab_only":
        raise HTTPException(status_code=422, detail="local_rollback_execution_receipt_boundary_overclaim")
    return payload


def _local_rollback_receipt_view_model(receipt_id: str) -> dict[str, Any]:
    """Return a whitelisted local rollback receipt projection."""

    normalized_receipt_id = receipt_id.strip() or "execution"
    if normalized_receipt_id == "summary":
        payload = _load_local_rollback_summary_packet(include_local_sandbox_receipts=True)
        path = LOCAL_ROLLBACK_SUMMARY_PACKET_PATH
        label = "Local rollback summary packet"
        schema_ref = "schemas/developer_workflow_local_rollback_summary_packet.schema.json"
    elif normalized_receipt_id == "approval":
        payload = _load_local_rollback_approval_packet(include_local_sandbox_receipts=True)
        path = LOCAL_ROLLBACK_APPROVAL_PACKET_PATH
        label = "Local rollback approval packet"
        schema_ref = "schemas/developer_workflow_local_rollback_approval_packet.schema.json"
    elif normalized_receipt_id == "execution":
        payload = _load_local_rollback_execution_receipt(include_local_sandbox_receipts=True)
        path = LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH
        label = "Local rollback execution receipt"
        schema_ref = "schemas/developer_workflow_local_rollback_execution_receipt.schema.json"
    else:
        raise HTTPException(status_code=404, detail="local_rollback_receipt_id_unknown")
    if payload is None:
        raise HTTPException(status_code=404, detail="local_rollback_receipt_missing")
    return {
        "receipt_id": normalized_receipt_id,
        "label": label,
        "path": path.as_posix(),
        "schema_ref": schema_ref,
        "projection_only": True,
        "external_effects_allowed": False,
        "payload_hash": canonical_hash(payload),
        "payload": payload,
        "source_refs": {
            "path": path.as_posix(),
            "validator": schema_ref,
        },
    }


def _render_local_rollback_receipt_viewer(read_model: Mapping[str, Any]) -> str:
    """Render a local rollback receipt as an escaped read-only page."""

    from html import escape

    payload_text = json.dumps(read_model.get("payload", {}), indent=2, sort_keys=True)
    label = str(read_model.get("label") or "Local rollback receipt")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(label)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17202a; background: #f7f8fa; }}
    main {{ max-width: 1120px; margin: 0 auto; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 18px; }}
    a {{ color: #0969da; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }}
    .metric {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 8px 10px; background: #fff; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; border: 1px solid #d8dee4; border-radius: 6px; padding: 14px; background: #fff; }}
  </style>
</head>
<body>
<main>
  <nav>
    <a href="/operator/control-tower?domain=software_dev&include_local_sandbox_receipts=true">control tower</a>
    <a href="/operator/control-tower/local-rollback-receipt/read-model?receipt_id={escape(str(read_model.get("receipt_id") or ""))}">json read model</a>
  </nav>
  <h1>{escape(label)}</h1>
  <div class="metrics">
    <span class="metric">Receipt: {escape(str(read_model.get("receipt_id") or ""))}</span>
    <span class="metric">Path: {escape(str(read_model.get("path") or ""))}</span>
    <span class="metric">Projection only: {escape(str(read_model.get("projection_only", False)).lower())}</span>
    <span class="metric">External effects: {escape(str(read_model.get("external_effects_allowed", True)).lower())}</span>
    <span class="metric">Hash: {escape(str(read_model.get("payload_hash") or "")[:16])}</span>
  </div>
  <pre>{escape(payload_text)}</pre>
</main>
</body>
</html>"""


def _workflow_monitor_panel_read_model(
    *,
    current_task: Mapping[str, Any],
    plan_review: Mapping[str, Any],
    developer_workflow_run: Mapping[str, Any],
    developer_workflow_operator_receipt: Mapping[str, Any] | None = None,
    local_sandbox_proof_report: Mapping[str, Any] | None = None,
    local_rollback_summary_packet: Mapping[str, Any] | None = None,
    local_rollback_approval_packet: Mapping[str, Any] | None = None,
    local_rollback_execution_receipt: Mapping[str, Any] | None = None,
    sandbox_to_pr_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project current task and plan review state into a workflow monitor panel."""
    task_status_counts = current_task.get("status_counts", {})
    plan_status_counts = plan_review.get("status_counts", {})
    if not isinstance(task_status_counts, Mapping):
        task_status_counts = {}
    if not isinstance(plan_status_counts, Mapping):
        plan_status_counts = {}
    blocked_count = (
        int(task_status_counts.get("blocked", 0) or 0)
        + int(plan_status_counts.get("blocked", 0) or 0)
        + int(plan_status_counts.get("denied", 0) or 0)
        + int(plan_status_counts.get("failed", 0) or 0)
        + int(plan_status_counts.get("recovery_rejected", 0) or 0)
    )
    review_count = (
        int(task_status_counts.get("waiting_for_approval", 0) or 0)
        + int(task_status_counts.get("requires_review", 0) or 0)
        + int(plan_status_counts.get("preview_ready", 0) or 0)
        + int(plan_status_counts.get("recovery_pending", 0) or 0)
    )
    current_task_id = str(current_task.get("current_task_id", ""))
    developer_workflow_summary = _developer_workflow_run_summary(developer_workflow_run)
    sandbox_to_pr_packet = _sandbox_to_pr_preparation_packet(
        sandbox_to_pr_policy=sandbox_to_pr_policy or {},
        developer_workflow_summary=developer_workflow_summary,
    )
    sandbox_to_pr_focus = _sandbox_to_pr_next_evidence_focus(sandbox_to_pr_packet)
    workflow_monitor_summary = _workflow_monitor_summary(
        current_task_id=current_task_id,
        current_task_count=int(current_task.get("count", 0) or 0),
        plan_review_count=int(plan_review.get("count", 0) or 0),
        blocked_count=blocked_count,
        review_count=review_count,
        developer_workflow_summary=developer_workflow_summary,
        sandbox_to_pr_packet=sandbox_to_pr_packet,
    )
    developer_workflow_milestone_summary = _developer_workflow_milestone_summary(
        workflow_monitor_summary=workflow_monitor_summary,
        developer_workflow_summary=developer_workflow_summary,
        sandbox_to_pr_packet=sandbox_to_pr_packet,
    )
    operator_action_card = _operator_action_card(
        workflow_monitor_summary=workflow_monitor_summary,
        sandbox_to_pr_focus=sandbox_to_pr_focus,
    )
    next_action_summary = _next_action_summary(
        operator_action_card=operator_action_card,
        sandbox_to_pr_focus=sandbox_to_pr_focus,
        sandbox_to_pr_packet=sandbox_to_pr_packet,
    )
    approval_readiness_summary = _approval_readiness_summary(
        operator_action_card=operator_action_card,
        developer_workflow_milestone_summary=developer_workflow_milestone_summary,
        sandbox_to_pr_packet=sandbox_to_pr_packet,
    )
    sandbox_receipt_attachment_packet = _sandbox_receipt_attachment_packet_projection(
        sandbox_to_pr_packet=sandbox_to_pr_packet,
        developer_workflow_summary=developer_workflow_summary,
    )
    sandbox_receipt_bundle_summary = _sandbox_receipt_bundle_summary(developer_workflow_summary)
    sandbox_receipt_attachment_readiness_summary = _sandbox_receipt_attachment_readiness_summary(
        sandbox_receipt_attachment_packet
    )
    pr_readiness_bundle = _pr_readiness_bundle_projection(
        sandbox_to_pr_packet=sandbox_to_pr_packet,
        developer_workflow_summary=developer_workflow_summary,
    )
    pr_readiness_summary = _pr_readiness_summary(pr_readiness_bundle)
    generated_operator_receipt = _developer_workflow_operator_receipt_projection(
        pr_readiness_bundle=pr_readiness_bundle,
        developer_workflow_summary=developer_workflow_summary,
    )
    if developer_workflow_operator_receipt is not None:
        generated_operator_receipt = _developer_workflow_operator_receipt_from_generated_receipt(
            developer_workflow_operator_receipt
        )
    proof_report_summary = _local_sandbox_proof_report_summary(local_sandbox_proof_report)
    rollback_summary = _local_rollback_summary_packet_summary(local_rollback_summary_packet)
    rollback_approval = _local_rollback_approval_packet_summary(local_rollback_approval_packet)
    rollback_execution = _local_rollback_execution_receipt_summary(local_rollback_execution_receipt)
    rollback_flow_command = _local_rollback_flow_command_summary(
        approval=rollback_approval,
        summary=rollback_summary,
        execution=rollback_execution,
    )
    local_rollback_flow_readiness_summary = _local_rollback_flow_readiness_summary(rollback_flow_command)
    evidence_progress_summary = _evidence_progress_summary(
        next_action_summary=next_action_summary,
        sandbox_receipt_bundle_summary=sandbox_receipt_bundle_summary,
        sandbox_receipt_attachment_readiness_summary=sandbox_receipt_attachment_readiness_summary,
        local_rollback_flow_readiness_summary=local_rollback_flow_readiness_summary,
        pr_readiness_summary=pr_readiness_summary,
    )
    operator_decision_summary = _operator_decision_summary(
        next_action_summary=next_action_summary,
        approval_readiness_summary=approval_readiness_summary,
        developer_workflow_milestone_summary=developer_workflow_milestone_summary,
        evidence_progress_summary=evidence_progress_summary,
    )
    friction_reduction_summary = _friction_reduction_summary(
        operator_decision_summary=operator_decision_summary,
        evidence_progress_summary=evidence_progress_summary,
        developer_workflow_milestone_summary=developer_workflow_milestone_summary,
    )
    evidence_refs = (
        str(current_task.get("schema_ref") or CURRENT_TASK_SCHEMA_REF),
        str(plan_review.get("schema_ref") or PLAN_REVIEW_SCHEMA_REF),
        str(developer_workflow_run.get("workflow_run_id") or "developer_workflow_v1_foundation_run"),
    )
    return {
        "source_surface": "operator_workflow_monitor",
        "item_count": int(current_task.get("total", 0) or 0) + int(plan_review.get("total", 0) or 0),
        "freshness_seconds": 0,
        "signal_count": 0,
        "blocked_count": blocked_count,
        "review_count": review_count,
        "evidence_refs": evidence_refs,
        "raw_tool_surface_exposed": False,
        "metadata": {
            "current_task_id": current_task_id,
            "current_task_count": int(current_task.get("count", 0) or 0),
            "plan_review_count": int(plan_review.get("count", 0) or 0),
            "workflow_monitor_summary": workflow_monitor_summary,
            "operator_action_card": operator_action_card,
            "next_action_summary": next_action_summary,
            "approval_readiness_summary": approval_readiness_summary,
            "operator_decision_summary": operator_decision_summary,
            "friction_reduction_summary": friction_reduction_summary,
            "task_status_counts": dict(task_status_counts),
            "plan_status_counts": dict(plan_status_counts),
            "current_task_href": "/operator/current-task",
            "plan_review_href": "/operator/plan-review",
            "developer_workflow_run": developer_workflow_summary,
            "sandbox_receipt_bundle_summary": sandbox_receipt_bundle_summary,
            "developer_workflow_readiness_summary": _developer_workflow_readiness_summary(
                developer_workflow_summary,
                sandbox_to_pr_packet,
            ),
            "developer_workflow_milestone_summary": developer_workflow_milestone_summary,
            "sandbox_to_pr_packet": sandbox_to_pr_packet,
            "sandbox_to_pr_focus": sandbox_to_pr_focus,
            "sandbox_to_pr_summary": _sandbox_to_pr_summary(
                packet=sandbox_to_pr_packet,
                focus=sandbox_to_pr_focus,
            ),
            "sandbox_receipt_attachment_packet": sandbox_receipt_attachment_packet,
            "sandbox_receipt_attachment_readiness_summary": sandbox_receipt_attachment_readiness_summary,
            "pr_readiness_bundle": pr_readiness_bundle,
            "pr_readiness_summary": pr_readiness_summary,
            "evidence_progress_summary": evidence_progress_summary,
            "developer_workflow_operator_receipt": generated_operator_receipt,
            "developer_workflow_operator_receipt_summary": (
                _developer_workflow_operator_receipt_summary(generated_operator_receipt)
            ),
            "local_sandbox_proof_report": proof_report_summary,
            "local_sandbox_proof_readiness_summary": _local_sandbox_proof_readiness_summary(
                proof_report_summary
            ),
            "local_rollback_summary_packet": rollback_summary,
            "local_rollback_approval_packet": rollback_approval,
            "local_rollback_execution_receipt": rollback_execution,
            "local_rollback_receipts_summary": _local_rollback_receipts_summary(
                summary=rollback_summary,
                approval=rollback_approval,
                execution=rollback_execution,
            ),
            "local_rollback_flow_command": rollback_flow_command,
            "local_rollback_flow_readiness_summary": local_rollback_flow_readiness_summary,
            "developer_workflow_href": DEVELOPER_WORKFLOW_RUN_HREF,
            "developer_workflow_read_model_href": DEVELOPER_WORKFLOW_RUN_READ_MODEL_HREF,
        },
    }


def _operator_action_card(
    *,
    workflow_monitor_summary: Mapping[str, Any],
    sandbox_to_pr_focus: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the next bounded operator action card for the dashboard."""

    blocker = str(workflow_monitor_summary.get("blocker") or "sandbox_receipts_incomplete")
    next_action = str(workflow_monitor_summary.get("next_action") or "inspect workflow receipts")
    focus_id = str(sandbox_to_pr_focus.get("focus_id") or "sandbox_patch_receipt")
    focus_label = str(sandbox_to_pr_focus.get("label") or "Sandbox patch receipt")
    focus_status = str(sandbox_to_pr_focus.get("status") or "pending")
    action_href = f"/operator/control-tower/status-receipt?focus_id={focus_id}"
    if blocker == "operator_approval_missing":
        action_href = "/operator/approvals"
    elif blocker == "pr_candidate_not_prepared":
        action_href = DEVELOPER_WORKFLOW_RUN_HREF

    return {
        "card_id": "developer_workflow_next_action",
        "title": "Next developer workflow action",
        "status": str(workflow_monitor_summary.get("readiness_status") or "awaiting_receipts"),
        "reason": blocker,
        "primary_action": next_action,
        "primary_href": action_href,
        "focus_id": focus_id,
        "focus_label": focus_label,
        "focus_status": focus_status,
        "task_id": str(workflow_monitor_summary.get("current_task_id") or ""),
        "risk": "low, local lab only",
        "execution_boundary": str(workflow_monitor_summary.get("execution_boundary") or "local_lab_only"),
        "approval_required": blocker == "operator_approval_missing",
        "external_effects_allowed": False,
    }


def _next_action_summary(
    *,
    operator_action_card: Mapping[str, Any],
    sandbox_to_pr_focus: Mapping[str, Any],
    sandbox_to_pr_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one reusable next-action summary from existing workflow projections."""

    next_evidence = sandbox_to_pr_packet.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    required_evidence = [
        str(item.get("evidence_id") or item.get("receipt_id") or "")
        for item in next_evidence
        if isinstance(item, Mapping) and str(item.get("evidence_id") or item.get("receipt_id") or "").strip()
    ][:8]
    focus_id = str(operator_action_card.get("focus_id") or sandbox_to_pr_focus.get("focus_id") or "sandbox_patch_receipt")
    primary_action = str(
        operator_action_card.get("primary_action")
        or sandbox_to_pr_focus.get("action")
        or sandbox_to_pr_packet.get("next_action")
        or "inspect workflow receipts"
    )
    return {
        "summary_id": "next_action.foundation",
        "status": str(operator_action_card.get("status") or sandbox_to_pr_packet.get("status") or "awaiting_receipts"),
        "reason": str(operator_action_card.get("reason") or sandbox_to_pr_packet.get("blocker") or "sandbox_receipts_incomplete"),
        "primary_action": primary_action,
        "primary_href": str(
            operator_action_card.get("primary_href")
            or f"/operator/control-tower/status-receipt?focus_id={focus_id}"
        ),
        "focus_id": focus_id,
        "focus_label": str(operator_action_card.get("focus_label") or sandbox_to_pr_focus.get("label") or "Sandbox patch receipt"),
        "focus_status": str(operator_action_card.get("focus_status") or sandbox_to_pr_focus.get("status") or "pending"),
        "focus_source": str(sandbox_to_pr_focus.get("source") or ""),
        "required_evidence": required_evidence,
        "required_evidence_count": len(required_evidence),
        "approval_required": operator_action_card.get("approval_required") is True,
        "risk": "low, local lab only",
        "operator_message": f"Next action {primary_action}; focus {focus_id}",
        "execution_boundary": str(operator_action_card.get("execution_boundary") or "local_lab_only"),
        "external_effects_allowed": False,
    }


def _approval_readiness_summary(
    *,
    operator_action_card: Mapping[str, Any],
    developer_workflow_milestone_summary: Mapping[str, Any],
    sandbox_to_pr_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Return approval readiness without granting approval authority."""

    approval = sandbox_to_pr_packet.get("approval", {})
    if not isinstance(approval, Mapping):
        approval = {}
    pr_candidate = sandbox_to_pr_packet.get("pr_candidate", {})
    if not isinstance(pr_candidate, Mapping):
        pr_candidate = {}

    approval_required = approval.get("required") is True or operator_action_card.get("approval_required") is True
    operator_approval_status = str(
        approval.get("status")
        or developer_workflow_milestone_summary.get("operator_approval_status")
        or "pending"
    )
    pr_candidate_status = str(
        pr_candidate.get("status")
        or developer_workflow_milestone_summary.get("pr_candidate_status")
        or "pending"
    )
    current_blocker = str(
        sandbox_to_pr_packet.get("blocker")
        or operator_action_card.get("reason")
        or developer_workflow_milestone_summary.get("blocker")
        or "sandbox_receipts_incomplete"
    )
    approval_missing = approval_required and operator_approval_status != "complete"

    if current_blocker == "operator_approval_missing":
        next_approval_action = "request operator approval for PR candidate"
        approval_target_href = "/operator/approvals"
    elif not approval_missing:
        next_approval_action = "approval satisfied; continue PR candidate preparation"
        approval_target_href = DEVELOPER_WORKFLOW_RUN_HREF
    else:
        next_approval_action = "complete sandbox receipts before requesting approval"
        approval_target_href = str(
            operator_action_card.get("primary_href")
            or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
        )

    return {
        "summary_id": "approval_readiness.foundation",
        "approval_required": approval_required,
        "operator_approval_status": operator_approval_status,
        "approval_missing": approval_missing,
        "current_blocker": current_blocker,
        "approval_boundary": "before_pr_or_real_world_effect",
        "next_approval_action": next_approval_action,
        "approval_target_href": approval_target_href,
        "pr_candidate_status": pr_candidate_status,
        "ready_for_pr_candidate_preparation": (
            operator_approval_status == "complete" and pr_candidate_status != "complete"
        ),
        "external_pr_execution_allowed": False,
        "operator_message": f"Approval {'pending' if approval_missing else 'complete'}; {current_blocker} remains current blocker",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _evidence_progress_summary(
    *,
    next_action_summary: Mapping[str, Any],
    sandbox_receipt_bundle_summary: Mapping[str, Any],
    sandbox_receipt_attachment_readiness_summary: Mapping[str, Any],
    local_rollback_flow_readiness_summary: Mapping[str, Any],
    pr_readiness_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return compact local evidence progress across workflow receipt surfaces."""

    sandbox_completed = int(sandbox_receipt_attachment_readiness_summary.get("completed_count") or 0)
    sandbox_required = int(sandbox_receipt_attachment_readiness_summary.get("required_count") or 0)
    rollback_available = int(local_rollback_flow_readiness_summary.get("receipt_available_count") or 0)
    rollback_required = int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0)
    completed_count = sandbox_completed + rollback_available
    required_count = sandbox_required + rollback_required
    pending_count = max(required_count - completed_count, 0)
    next_evidence_id = str(
        sandbox_receipt_attachment_readiness_summary.get("next_receipt_id")
        or sandbox_receipt_bundle_summary.get("next_receipt_id")
        or next_action_summary.get("focus_id")
        or "sandbox_patch_receipt"
    )
    next_action = str(
        sandbox_receipt_attachment_readiness_summary.get("next_action")
        or next_action_summary.get("primary_action")
        or "inspect workflow receipts"
    )
    return {
        "summary_id": "evidence_progress.foundation",
        "status": "complete" if required_count and pending_count == 0 else "awaiting_evidence",
        "completed_count": completed_count,
        "required_count": required_count,
        "pending_count": pending_count,
        "next_evidence_id": next_evidence_id,
        "next_action": next_action,
        "blocker": str(next_action_summary.get("reason") or "sandbox_receipts_incomplete"),
        "sandbox_receipt_completed_count": sandbox_completed,
        "sandbox_receipt_required_count": sandbox_required,
        "sandbox_bundle_completed_count": int(sandbox_receipt_bundle_summary.get("completed_count") or 0),
        "sandbox_bundle_required_count": int(sandbox_receipt_bundle_summary.get("required_count") or 0),
        "rollback_receipt_available_count": rollback_available,
        "rollback_receipt_required_count": rollback_required,
        "pr_next_evidence_count": int(pr_readiness_summary.get("next_evidence_count") or 0),
        "operator_message": f"{completed_count}/{required_count} local evidence receipts complete; next {next_evidence_id}",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _operator_decision_summary(
    *,
    next_action_summary: Mapping[str, Any],
    approval_readiness_summary: Mapping[str, Any],
    developer_workflow_milestone_summary: Mapping[str, Any],
    evidence_progress_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the current operator decision without granting execution authority."""

    current_blocker = str(
        approval_readiness_summary.get("current_blocker")
        or next_action_summary.get("reason")
        or developer_workflow_milestone_summary.get("blocker")
        or "sandbox_receipts_incomplete"
    )
    current_milestone = str(
        developer_workflow_milestone_summary.get("current_milestone") or "collect_sandbox_receipts"
    )
    if current_blocker == "operator_approval_missing":
        decision_kind = "approval_request"
    elif current_blocker == "pr_candidate_not_prepared":
        decision_kind = "pr_preparation"
    elif current_blocker == "none":
        decision_kind = "closed"
    else:
        decision_kind = "evidence_collection"

    approval_status = str(approval_readiness_summary.get("operator_approval_status") or "pending")
    operator_review_required_now = current_blocker == "operator_approval_missing"
    operator_review_required_before_external_effect = approval_readiness_summary.get("approval_required") is True
    next_evidence_id = str(
        evidence_progress_summary.get("next_evidence_id")
        or next_action_summary.get("focus_id")
        or "sandbox_patch_receipt"
    )
    recommended_action = str(
        next_action_summary.get("primary_action")
        or developer_workflow_milestone_summary.get("next_action")
        or "inspect workflow receipts"
    )
    action_href = str(
        next_action_summary.get("primary_href")
        or approval_readiness_summary.get("approval_target_href")
        or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
    )
    if operator_review_required_now:
        operator_message = "Decision requires operator approval now; external effects remain blocked"
    else:
        operator_message = (
            f"Decision {current_milestone} can continue in local lab; "
            "approval pending before PR or real-world effect"
        )

    return {
        "summary_id": "operator_decision.foundation",
        "decision_status": str(next_action_summary.get("status") or "awaiting_receipts"),
        "decision_kind": decision_kind,
        "current_milestone": current_milestone,
        "current_blocker": current_blocker,
        "recommended_action": recommended_action,
        "action_href": action_href,
        "next_evidence_id": next_evidence_id,
        "operator_review_required_now": operator_review_required_now,
        "operator_review_required_before_external_effect": operator_review_required_before_external_effect,
        "approval_status": approval_status,
        "local_continuation_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": operator_message,
    }


def _friction_reduction_summary(
    *,
    operator_decision_summary: Mapping[str, Any],
    evidence_progress_summary: Mapping[str, Any],
    developer_workflow_milestone_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact friction-reduction headline for the local workflow."""

    pending_evidence_count = int(evidence_progress_summary.get("pending_count") or 0)
    current_milestone = str(
        operator_decision_summary.get("current_milestone")
        or developer_workflow_milestone_summary.get("current_milestone")
        or "collect_sandbox_receipts"
    )
    current_blocker = str(
        operator_decision_summary.get("current_blocker")
        or developer_workflow_milestone_summary.get("blocker")
        or "sandbox_receipts_incomplete"
    )
    local_continuation_allowed = (
        str(operator_decision_summary.get("decision_kind") or "") == "evidence_collection"
        and operator_decision_summary.get("operator_review_required_now") is not True
    )
    return {
        "summary_id": "friction_reduction.foundation",
        "reduction_status": "local_continuation_ready" if local_continuation_allowed else "awaiting_operator_review",
        "current_milestone": current_milestone,
        "current_blocker": current_blocker,
        "local_continuation_allowed": local_continuation_allowed,
        "pending_evidence_count": pending_evidence_count,
        "next_evidence_id": str(
            evidence_progress_summary.get("next_evidence_id")
            or operator_decision_summary.get("next_evidence_id")
            or "sandbox_patch_receipt"
        ),
        "approval_boundary": "before_pr_or_real_world_effect",
        "operator_review_required_now": operator_decision_summary.get("operator_review_required_now") is True,
        "external_effects_allowed": False,
        "operator_message": (
            f"Friction reduced to {current_milestone}; continue local evidence collection, "
            "while PR and real-world effects remain approval-bound"
        ),
    }


def _workflow_monitor_summary(
    *,
    current_task_id: str,
    current_task_count: int,
    plan_review_count: int,
    blocked_count: int,
    review_count: int,
    developer_workflow_summary: Mapping[str, Any],
    sandbox_to_pr_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact API-facing workflow monitor summary."""

    workflow_task_id = str(developer_workflow_summary.get("current_task_id") or "")
    headline_task_id = str(current_task_id or workflow_task_id)
    headline_task_count = int(current_task_count)
    if not headline_task_count and headline_task_id:
        headline_task_count = 1
    headline_plan_review_count = int(plan_review_count)
    if not headline_plan_review_count and str(developer_workflow_summary.get("status") or "") == "waiting_for_approval":
        headline_plan_review_count = 1

    return {
        "monitor_status": "blocked" if blocked_count else "review" if review_count else "monitoring",
        "current_task_id": headline_task_id,
        "current_task_count": headline_task_count,
        "plan_review_count": headline_plan_review_count,
        "blocked_count": int(blocked_count),
        "review_count": int(review_count),
        "workflow_status": str(developer_workflow_summary.get("status") or "waiting_for_approval"),
        "readiness_status": str(sandbox_to_pr_packet.get("status") or "awaiting_receipts"),
        "blocker": str(sandbox_to_pr_packet.get("blocker") or "sandbox_receipts_incomplete"),
        "next_action": str(sandbox_to_pr_packet.get("next_action") or "inspect workflow receipts"),
        "execution_boundary": str(sandbox_to_pr_packet.get("execution_boundary") or "local_lab_only"),
        "external_effects_allowed": False,
    }


def _developer_workflow_milestone_summary(
    *,
    workflow_monitor_summary: Mapping[str, Any],
    developer_workflow_summary: Mapping[str, Any],
    sandbox_to_pr_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the current local Developer Workflow v1 milestone."""

    receipts = sandbox_to_pr_packet.get("receipts", {})
    if not isinstance(receipts, Mapping):
        receipts = {}
    approval = sandbox_to_pr_packet.get("approval", {})
    if not isinstance(approval, Mapping):
        approval = {}
    pr_candidate = sandbox_to_pr_packet.get("pr_candidate", {})
    if not isinstance(pr_candidate, Mapping):
        pr_candidate = {}

    receipt_completed_count = int(receipts.get("completed_count", 0) or 0)
    receipt_required_count = int(receipts.get("required_count", 0) or 0)
    operator_approval_status = str(approval.get("status") or "pending")
    pr_candidate_status = str(pr_candidate.get("status") or "pending")
    workflow_status = str(workflow_monitor_summary.get("workflow_status") or developer_workflow_summary.get("status") or "")

    if receipt_completed_count < receipt_required_count:
        current_milestone = "collect_sandbox_receipts"
    elif operator_approval_status != "complete":
        current_milestone = "request_operator_approval"
    elif pr_candidate_status != "complete":
        current_milestone = "prepare_pr_candidate"
    elif workflow_status in {"complete", "closed", "terminal_closed"}:
        current_milestone = "closed"
    else:
        current_milestone = "review"

    return {
        "summary_id": "developer_workflow_milestone.foundation",
        "workflow_status": workflow_status or "waiting_for_approval",
        "readiness_status": str(workflow_monitor_summary.get("readiness_status") or sandbox_to_pr_packet.get("status") or "awaiting_receipts"),
        "current_task_id": str(workflow_monitor_summary.get("current_task_id") or developer_workflow_summary.get("current_task_id") or ""),
        "current_milestone": current_milestone,
        "blocker": str(workflow_monitor_summary.get("blocker") or sandbox_to_pr_packet.get("blocker") or "sandbox_receipts_incomplete"),
        "next_action": str(workflow_monitor_summary.get("next_action") or sandbox_to_pr_packet.get("next_action") or "inspect workflow receipts"),
        "receipt_completed_count": receipt_completed_count,
        "receipt_required_count": receipt_required_count,
        "operator_approval_status": operator_approval_status,
        "pr_candidate_status": pr_candidate_status,
        "operator_message": (
            f"Developer workflow milestone {current_milestone}; next action "
            f"{str(workflow_monitor_summary.get('next_action') or sandbox_to_pr_packet.get('next_action') or 'inspect workflow receipts')}"
        ),
        "execution_boundary": str(workflow_monitor_summary.get("execution_boundary") or sandbox_to_pr_packet.get("execution_boundary") or "local_lab_only"),
        "external_effects_allowed": False,
    }


def _local_sandbox_proof_report_summary(report: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a bounded summary of the last local proof runner report."""

    if not isinstance(report, Mapping):
        return {
            "status": "not_attached",
            "ok": False,
            "bundle_status": "unknown",
            "attachment_packet_status": "unknown",
            "next_attachment_id": "unknown",
            "pr_readiness_status": "unknown",
            "completed_count": 0,
            "required_count": 0,
            "execution_performed": False,
            "external_effects_allowed": False,
            "generated_artifacts": {},
        }
    generated_artifacts = report.get("generated_artifacts", {})
    if not isinstance(generated_artifacts, Mapping):
        generated_artifacts = {}
    return {
        "status": "attached",
        "ok": report.get("ok") is True,
        "bundle_status": str(report.get("bundle_status") or "unknown"),
        "attachment_packet_status": str(report.get("attachment_packet_status") or "unknown"),
        "next_attachment_id": str(report.get("next_attachment_id") or "unknown"),
        "pr_readiness_status": str(report.get("pr_readiness_status") or "unknown"),
        "completed_count": int(report.get("completed_count", 0) or 0),
        "required_count": int(report.get("required_count", 0) or 0),
        "execution_performed": False,
        "external_effects_allowed": False,
        "generated_artifacts": {
            str(key): str(value)
            for key, value in generated_artifacts.items()
            if str(key).strip() and str(value).strip()
        },
    }


def _local_sandbox_proof_readiness_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact API-facing local sandbox proof readiness summary."""

    return {
        "proof_status": str(report.get("status") or "not_attached"),
        "ok": report.get("ok") is True,
        "bundle_status": str(report.get("bundle_status") or "unknown"),
        "attachment_packet_status": str(report.get("attachment_packet_status") or "unknown"),
        "next_attachment_id": str(report.get("next_attachment_id") or "unknown"),
        "pr_readiness_status": str(report.get("pr_readiness_status") or "unknown"),
        "completed_count": int(report.get("completed_count", 0) or 0),
        "required_count": int(report.get("required_count", 0) or 0),
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _local_rollback_summary_packet_summary(packet: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a bounded summary of the last local rollback summary packet."""

    if not isinstance(packet, Mapping):
        return {
            "status": "not_attached",
            "packet_status": "rollback_unavailable",
            "generated_artifact_count": 0,
            "rollback_execution_performed": False,
            "external_effects_allowed": False,
            "artifacts": [],
        }
    artifacts = packet.get("artifacts", ())
    if not isinstance(artifacts, list):
        artifacts = []
    return {
        "status": "attached",
        "packet_status": str(packet.get("packet_status") or "rollback_unavailable"),
        "generated_artifact_count": int(packet.get("generated_artifact_count", 0) or 0),
        "rollback_execution_performed": False,
        "external_effects_allowed": False,
        "artifacts": [
            {
                "artifact_id": str(item.get("artifact_id") or ""),
                "path": str(item.get("path") or ""),
                "rollback_command": str(item.get("rollback_command") or ""),
                "required_confirmation": item.get("required_confirmation") is True,
            }
            for item in artifacts
            if isinstance(item, Mapping)
        ][:32],
    }


def _local_rollback_approval_packet_summary(packet: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a bounded summary of the last local rollback approval packet."""

    if not isinstance(packet, Mapping):
        return {
            "status": "not_attached",
            "packet_status": "awaiting_operator_approval",
            "approval_status": "pending",
            "approval_scope": "none",
            "selected_artifact_count": 0,
            "delete_execution_allowed": False,
            "rollback_execution_performed": False,
            "external_effects_allowed": False,
            "authorized_artifacts": [],
        }
    authorized_artifacts = packet.get("authorized_artifacts", ())
    if not isinstance(authorized_artifacts, list):
        authorized_artifacts = []
    return {
        "status": "attached",
        "packet_status": str(packet.get("packet_status") or "awaiting_operator_approval"),
        "approval_status": str(packet.get("approval_status") or "pending"),
        "approval_scope": str(packet.get("approval_scope") or "none"),
        "selected_artifact_count": int(packet.get("selected_artifact_count", 0) or 0),
        "delete_execution_allowed": packet.get("delete_execution_allowed") is True,
        "rollback_execution_performed": False,
        "external_effects_allowed": False,
        "authorized_artifacts": [
            {
                "artifact_id": str(item.get("artifact_id") or ""),
                "path": str(item.get("path") or ""),
                "rollback_command": str(item.get("rollback_command") or ""),
                "approval_status": str(item.get("approval_status") or "pending"),
                "execution_allowed": item.get("execution_allowed") is True,
                "required_confirmation": item.get("required_confirmation") is True,
            }
            for item in authorized_artifacts
            if isinstance(item, Mapping)
        ][:32],
    }


def _local_rollback_execution_receipt_summary(receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a bounded summary of the last local rollback execution receipt."""

    if not isinstance(receipt, Mapping):
        return {
            "status": "not_attached",
            "execution_status": "blocked_no_approval",
            "execution_mode": "dry_run",
            "rollback_execution_performed": False,
            "external_effects_allowed": False,
            "target_path_checks_performed": False,
            "selected_artifact_count": 0,
            "executed_artifact_count": 0,
            "skipped_artifact_count": 0,
            "failed_artifact_count": 0,
            "artifacts": [],
        }
    artifacts = receipt.get("artifacts", ())
    if not isinstance(artifacts, list):
        artifacts = []
    return {
        "status": "attached",
        "execution_status": str(receipt.get("execution_status") or "blocked_no_approval"),
        "execution_mode": str(receipt.get("execution_mode") or "dry_run"),
        "rollback_execution_performed": receipt.get("rollback_execution_performed") is True,
        "external_effects_allowed": False,
        "target_path_checks_performed": receipt.get("target_path_checks_performed") is True,
        "selected_artifact_count": int(receipt.get("selected_artifact_count", 0) or 0),
        "executed_artifact_count": int(receipt.get("executed_artifact_count", 0) or 0),
        "skipped_artifact_count": int(receipt.get("skipped_artifact_count", 0) or 0),
        "failed_artifact_count": int(receipt.get("failed_artifact_count", 0) or 0),
        "artifacts": [
            {
                "artifact_id": str(item.get("artifact_id") or ""),
                "path": str(item.get("path") or ""),
                "resolved_path": str(item.get("resolved_path") or ""),
                "action_status": str(item.get("action_status") or "skipped"),
                "path_within_workspace": item.get("path_within_workspace") is True,
                "pre_exists": item.get("pre_exists") is True,
                "post_exists": item.get("post_exists") is True,
                "error_message": str(item.get("error_message") or ""),
            }
            for item in artifacts
            if isinstance(item, Mapping)
        ][:32],
    }


def _local_rollback_receipts_summary(
    *,
    summary: Mapping[str, Any],
    approval: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact API-facing local rollback receipt trio summary."""

    attached_count = sum(
        1
        for receipt in (summary, approval, execution)
        if str(receipt.get("status") or "") == "attached"
    )
    return {
        "summary_status": str(summary.get("status") or "not_attached"),
        "approval_status": str(approval.get("approval_status") or "pending"),
        "execution_status": str(execution.get("execution_status") or "blocked_no_approval"),
        "execution_mode": str(execution.get("execution_mode") or "dry_run"),
        "generated_artifact_count": int(summary.get("generated_artifact_count", 0) or 0),
        "selected_artifact_count": int(approval.get("selected_artifact_count", 0) or 0),
        "attached_receipt_count": attached_count,
        "required_receipt_count": 3,
        "delete_execution_allowed": approval.get("delete_execution_allowed") is True,
        "rollback_execution_performed": False,
        "external_effects_allowed": False,
    }


def _local_rollback_flow_command_summary(
    *,
    approval: Mapping[str, Any],
    summary: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the one-command local rollback flow hint for the selected artifacts."""

    receipt_availability = _local_rollback_receipt_availability(
        summary=summary,
        approval=approval,
        execution=execution,
    )
    artifacts = approval.get("authorized_artifacts", ())
    if not isinstance(artifacts, list):
        artifacts = []
    selected_artifact_ids = [
        str(item.get("artifact_id") or "")
        for item in artifacts
        if isinstance(item, Mapping)
        and item.get("execution_allowed") is True
        and str(item.get("artifact_id") or "").strip()
    ][:32]
    command_artifact_args = " ".join(
        f"--artifact-id {_powershell_single_quoted_artifact_id(artifact_id)}"
        for artifact_id in selected_artifact_ids
    )
    if not command_artifact_args:
        command_artifact_args = "--artifact-id <artifact_id>"
    readiness_verdict = _local_rollback_readiness_verdict(
        selected_artifact_ids=selected_artifact_ids,
        receipt_availability=receipt_availability,
    )
    command = (
        "python scripts/run_developer_workflow_local_rollback_flow.py "
        "--rollback-summary .change_assurance/developer_workflow_local_rollback_summary_packet.generated.json "
        f"{command_artifact_args} "
        "--approved-by operator "
        "--approval-evidence-ref approval://local/rollback-flow/operator-command "
        "--json"
    )
    return {
        "status": (
            "ready"
            if approval.get("delete_execution_allowed") is True and selected_artifact_ids
            else "awaiting_selection"
        ),
        "action_label": "Run local rollback dry-run",
        "next_action": (
            "run dry-run rollback flow and inspect execution receipt before adding --execute"
            if selected_artifact_ids
            else "select at least one generated artifact before running rollback flow"
        ),
        "command": command,
        "execute_command": f"{command} --execute",
        "selected_artifact_ids": selected_artifact_ids,
        "rollback_summary_path": _path_command_ref(LOCAL_ROLLBACK_SUMMARY_PACKET_PATH),
        "approval_packet_path": _path_command_ref(LOCAL_ROLLBACK_APPROVAL_PACKET_PATH),
        "dry_run_receipt_path": _path_command_ref(LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH),
        "execution_receipt_path": _path_command_ref(LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH),
        "rollback_summary_href": _local_rollback_receipt_href("summary"),
        "approval_packet_href": _local_rollback_receipt_href("approval"),
        "dry_run_receipt_href": _local_rollback_receipt_href("execution"),
        "execution_receipt_href": _local_rollback_receipt_href("execution"),
        "receipt_availability": receipt_availability,
        "readiness_verdict": readiness_verdict,
        "dry_run_required": True,
        "execution_requires_execute_flag": True,
        "external_effects_allowed": False,
    }


def _local_rollback_flow_readiness_summary(command: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact API-facing rollback flow readiness summary."""

    receipt_availability = command.get("receipt_availability", {})
    if not isinstance(receipt_availability, Mapping):
        receipt_availability = {}
    selected_artifact_ids = command.get("selected_artifact_ids", ())
    if not isinstance(selected_artifact_ids, list):
        selected_artifact_ids = []
    return {
        "readiness_verdict": str(command.get("readiness_verdict") or "awaiting_selection"),
        "command_status": str(command.get("status") or "awaiting_selection"),
        "selected_artifact_count": len(
            [artifact_id for artifact_id in selected_artifact_ids if str(artifact_id).strip()]
        ),
        "receipt_available_count": int(receipt_availability.get("available_count", 0) or 0),
        "receipt_required_count": int(receipt_availability.get("required_count", 3) or 3),
        "next_action": str(command.get("next_action") or ""),
        "dry_run_required": command.get("dry_run_required") is True,
        "execution_requires_execute_flag": command.get("execution_requires_execute_flag") is True,
        "external_effects_allowed": False,
    }


def _local_rollback_readiness_verdict(
    *,
    selected_artifact_ids: list[str],
    receipt_availability: Mapping[str, Any],
) -> str:
    """Return the compact operator readiness verdict for the rollback flow."""

    if not selected_artifact_ids:
        return "awaiting_selection"
    if receipt_availability.get("summary") != "available":
        return "awaiting_summary_receipt"
    if receipt_availability.get("approval") != "available":
        return "awaiting_approval_receipt"
    return "ready_for_dry_run"


def _local_rollback_receipt_availability(
    *,
    summary: Mapping[str, Any],
    approval: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    """Return compact availability for local rollback receipt viewer links."""

    statuses = {
        "summary": "available" if summary.get("status") == "attached" else "unavailable",
        "approval": "available" if approval.get("status") == "attached" else "unavailable",
        "execution": "available" if execution.get("status") == "attached" else "unavailable",
    }
    return {
        **statuses,
        "available_count": sum(1 for status in statuses.values() if status == "available"),
        "required_count": len(statuses),
    }


def _path_command_ref(path: Path) -> str:
    """Return a stable repo-local path for operator command cards."""

    return path.as_posix()


def _local_rollback_receipt_href(receipt_id: str) -> str:
    """Return the local read-only rollback receipt viewer URL."""

    return f"{LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id={receipt_id}"


def _powershell_single_quoted_artifact_id(value: str) -> str:
    """Quote artifact ids for the PowerShell-oriented dashboard command."""

    return "'" + value.replace("'", "''") + "'"


def _developer_workflow_run_summary(developer_workflow_run: Mapping[str, Any]) -> dict[str, Any]:
    task_runs = developer_workflow_run.get("task_runs", ())
    metadata = developer_workflow_run.get("metadata", {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    receipt_binding = metadata.get("software_receipt_binding", {})
    if not isinstance(receipt_binding, Mapping):
        receipt_binding = {}
    stage_evidence = receipt_binding.get("stage_evidence", {})
    if not isinstance(stage_evidence, Mapping):
        stage_evidence = {}
    rollback_refs = tuple(str(ref) for ref in stage_evidence.get("rollback_completed", ()) if str(ref).strip())
    status_counts: dict[str, int] = {}
    current_task_id = ""
    task_statuses: dict[str, str] = {}
    if isinstance(task_runs, list):
        for task_run in task_runs:
            if not isinstance(task_run, Mapping):
                continue
            status = str(task_run.get("status") or "")
            task_id = str(task_run.get("task_id") or "")
            if task_id:
                task_statuses[task_id] = status
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1
            if not current_task_id and status not in {"committed", "compensated"}:
                current_task_id = task_id
    receipt_checklist = _developer_workflow_receipt_checklist(
        stage_evidence=stage_evidence,
        task_statuses=task_statuses,
    )
    required_items = [item for item in receipt_checklist if item["required"] is True]
    completed_required_count = sum(1 for item in required_items if item["status"] == "complete")
    rollback_receipt_status = "available" if rollback_refs else "not_recorded"
    sandbox_to_pr_readiness = _developer_workflow_sandbox_to_pr_readiness(
        receipt_checklist=receipt_checklist,
        rollback_receipt_status=rollback_receipt_status,
    )
    return {
        "workflow_run_id": str(developer_workflow_run.get("workflow_run_id") or ""),
        "workflow_id": str(developer_workflow_run.get("workflow_id") or ""),
        "status": str(developer_workflow_run.get("status") or ""),
        "current_task_id": current_task_id,
        "task_count": len(task_runs) if isinstance(task_runs, list) else 0,
        "status_counts": dict(sorted(status_counts.items())),
        "software_receipt_binding_status": str(receipt_binding.get("binding_status") or ""),
        "sandbox_receipt_bundle_status": str(receipt_binding.get("sandbox_receipt_bundle_status") or "not_attached"),
        "sandbox_receipt_bundle_completed_count": int(
            receipt_binding.get("sandbox_receipt_bundle_completed_count", 0) or 0
        ),
        "sandbox_receipt_bundle_required_count": int(
            receipt_binding.get("sandbox_receipt_bundle_required_count", 0) or 0
        ),
        "sandbox_receipt_bundle_receipts": _sandbox_receipt_bundle_receipt_rows(receipt_binding),
        "receipt_checklist": receipt_checklist,
        "receipt_checklist_required_count": len(required_items),
        "receipt_checklist_completed_required_count": completed_required_count,
        "receipt_checklist_pending_required_count": len(required_items) - completed_required_count,
        "sandbox_to_pr_readiness": sandbox_to_pr_readiness,
        "rollback_receipt_status": rollback_receipt_status,
        "rollback_receipt_count": len(rollback_refs),
        "rollback_receipt_refs": list(rollback_refs),
        "run_hash": str(developer_workflow_run.get("run_hash") or ""),
    }


def _developer_workflow_readiness_summary(
    developer_workflow_summary: Mapping[str, Any],
    sandbox_to_pr_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact API-facing Developer Workflow v1 readiness summary."""

    readiness = developer_workflow_summary.get("sandbox_to_pr_readiness", {})
    if not isinstance(readiness, Mapping):
        readiness = {}
    receipts = sandbox_to_pr_packet.get("receipts", {})
    if not isinstance(receipts, Mapping):
        receipts = {}
    approval = sandbox_to_pr_packet.get("approval", {})
    if not isinstance(approval, Mapping):
        approval = {}
    pr_candidate = sandbox_to_pr_packet.get("pr_candidate", {})
    if not isinstance(pr_candidate, Mapping):
        pr_candidate = {}
    return {
        "workflow_status": str(developer_workflow_summary.get("status") or ""),
        "current_task_id": str(developer_workflow_summary.get("current_task_id") or ""),
        "readiness_status": str(readiness.get("readiness_status") or "unknown"),
        "packet_status": str(sandbox_to_pr_packet.get("status") or "unknown"),
        "blocker": str(sandbox_to_pr_packet.get("blocker") or "unknown"),
        "receipt_completed_count": int(receipts.get("completed_count", 0) or 0),
        "receipt_required_count": int(receipts.get("required_count", 0) or 0),
        "checklist_completed_required_count": int(
            developer_workflow_summary.get("receipt_checklist_completed_required_count", 0) or 0
        ),
        "checklist_required_count": int(
            developer_workflow_summary.get("receipt_checklist_required_count", 0) or 0
        ),
        "operator_approval_status": str(approval.get("status") or "pending"),
        "pr_candidate_status": str(pr_candidate.get("status") or "pending"),
        "rollback_receipt_status": str(readiness.get("rollback_receipt_status") or "not_recorded"),
        "next_action": str(sandbox_to_pr_packet.get("next_action") or "inspect workflow receipts"),
        "execution_boundary": str(sandbox_to_pr_packet.get("execution_boundary") or "local_lab_only"),
        "external_effects_allowed": False,
    }


def _sandbox_receipt_bundle_receipt_rows(receipt_binding: Mapping[str, Any]) -> list[dict[str, Any]]:
    receipts = receipt_binding.get("sandbox_receipt_bundle_receipts", ())
    if not isinstance(receipts, list):
        return []
    rows: list[dict[str, Any]] = []
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            continue
        rows.append({
            "receipt_id": str(receipt.get("receipt_id") or ""),
            "label": str(receipt.get("label") or ""),
            "status": str(receipt.get("status") or ""),
            "stage": str(receipt.get("stage") or ""),
            "required": receipt.get("required") is True,
            "source": str(receipt.get("source") or ""),
            "evidence_refs": [
                str(ref)
                for ref in receipt.get("evidence_refs", ())
                if str(ref).strip()
            ],
        })
    return rows


def _sandbox_receipt_bundle_summary(developer_workflow_summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact API-facing local sandbox receipt bundle summary."""

    receipts = developer_workflow_summary.get("sandbox_receipt_bundle_receipts", ())
    if not isinstance(receipts, list):
        receipts = []
    next_receipt = next(
        (
            receipt
            for receipt in receipts
            if isinstance(receipt, Mapping) and str(receipt.get("status") or "") != "complete"
        ),
        {},
    )
    if not isinstance(next_receipt, Mapping):
        next_receipt = {}
    return {
        "status": str(developer_workflow_summary.get("sandbox_receipt_bundle_status") or "not_attached"),
        "completed_count": int(developer_workflow_summary.get("sandbox_receipt_bundle_completed_count", 0) or 0),
        "required_count": int(developer_workflow_summary.get("sandbox_receipt_bundle_required_count", 0) or 0),
        "receipt_count": len([receipt for receipt in receipts if isinstance(receipt, Mapping)]),
        "next_receipt_id": str(next_receipt.get("receipt_id") or "sandbox_patch_receipt"),
        "next_receipt_status": str(next_receipt.get("status") or "pending"),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _developer_workflow_receipt_checklist(
    *,
    stage_evidence: Mapping[str, Any],
    task_statuses: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Return read-only receipt obligations for Developer Workflow v1."""
    stage_items = (
        ("sandbox_patch_receipt", "Sandbox patch receipt", "patch_applied", "sandbox_change", True),
        ("test_gate_receipt", "Test gate receipt", "gate_evaluated", "test_run", True),
        ("diff_review_receipt", "Diff review receipt", "gate_evaluated", "diff_review", True),
        ("terminal_receipt", "Terminal receipt", "terminal_closed", "receipt_review", True),
        ("rollback_receipt", "Rollback receipt", "rollback_completed", "", False),
    )
    checklist: list[dict[str, Any]] = []
    for checklist_id, label, stage, task_id, required in stage_items:
        refs = tuple(str(ref) for ref in stage_evidence.get(checklist_id, ()) if str(ref).strip())
        if not refs:
            refs = tuple(str(ref) for ref in stage_evidence.get(stage, ()) if str(ref).strip())
        task_status = str(task_statuses.get(task_id, "")) if task_id else ""
        checklist.append({
            "checklist_id": checklist_id,
            "label": label,
            "status": "complete" if refs or task_status == "committed" else "pending",
            "required": required,
            "evidence_refs": list(refs),
            "task_id": task_id,
            "stage": stage,
        })
    approval_status = str(task_statuses.get("operator_approval", ""))
    checklist.append({
        "checklist_id": "operator_approval",
        "label": "Operator approval",
        "status": "complete" if approval_status == "committed" else "pending",
        "required": True,
        "evidence_refs": [],
        "task_id": "operator_approval",
        "stage": "approval",
    })
    pr_status = str(task_statuses.get("pr_candidate", ""))
    checklist.append({
        "checklist_id": "pr_candidate",
        "label": "PR candidate receipt",
        "status": "complete" if pr_status == "committed" else "pending",
        "required": True,
        "evidence_refs": [],
        "task_id": "pr_candidate",
        "stage": "pr_candidate",
    })
    return checklist


def _developer_workflow_sandbox_to_pr_readiness(
    *,
    receipt_checklist: list[Mapping[str, Any]],
    rollback_receipt_status: str,
) -> dict[str, Any]:
    """Compose receipt, approval, PR, and rollback state for sandbox-to-PR flow."""
    checklist_by_id = {
        str(item.get("checklist_id") or ""): item
        for item in receipt_checklist
        if isinstance(item, Mapping)
    }
    receipt_ids = (
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    )
    completed_receipt_count = sum(
        1
        for checklist_id in receipt_ids
        if str(checklist_by_id.get(checklist_id, {}).get("status") or "") == "complete"
    )
    receipt_checklist_ready = completed_receipt_count == len(receipt_ids)
    operator_approval_status = str(checklist_by_id.get("operator_approval", {}).get("status") or "pending")
    pr_candidate_status = str(checklist_by_id.get("pr_candidate", {}).get("status") or "pending")
    if not receipt_checklist_ready:
        readiness_status = "awaiting_receipts"
        next_action = "complete sandbox patch, test, diff, and terminal receipts"
    elif operator_approval_status != "complete":
        readiness_status = "awaiting_operator_approval"
        next_action = "request operator approval for PR candidate"
    elif pr_candidate_status != "complete":
        readiness_status = "ready_to_prepare_pr"
        next_action = "prepare PR candidate"
    else:
        readiness_status = "pr_candidate_ready"
        next_action = "review PR candidate"
    return {
        "readiness_status": readiness_status,
        "receipt_checklist_ready": receipt_checklist_ready,
        "receipt_checklist_completed_count": completed_receipt_count,
        "receipt_checklist_required_count": len(receipt_ids),
        "operator_approval_status": operator_approval_status,
        "pr_candidate_status": pr_candidate_status,
        "rollback_receipt_status": rollback_receipt_status,
        "next_action": next_action,
    }


def _sandbox_to_pr_preparation_packet(
    *,
    sandbox_to_pr_policy: Mapping[str, Any],
    developer_workflow_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the bounded operator packet for local sandbox-to-PR preparation."""
    readiness = developer_workflow_summary.get("sandbox_to_pr_readiness", {})
    if not isinstance(readiness, Mapping):
        readiness = {}
    policy_ready = sandbox_to_pr_policy.get("policy_ready") is True
    receipt_ready = readiness.get("receipt_checklist_ready") is True
    approval_status = str(readiness.get("operator_approval_status") or "pending")
    pr_status = str(readiness.get("pr_candidate_status") or "pending")
    readiness_status = str(readiness.get("readiness_status") or "unknown")
    if not policy_ready:
        blocker = "capability_policy_incomplete"
    elif not receipt_ready:
        blocker = "sandbox_receipts_incomplete"
    elif approval_status != "complete":
        blocker = "operator_approval_missing"
    elif pr_status != "complete":
        blocker = "pr_candidate_not_prepared"
    else:
        blocker = "none"
    return {
        "packet_id": "sandbox_to_pr_preparation_packet.v1",
        "status": readiness_status,
        "blocker": blocker,
        "next_action": str(readiness.get("next_action") or "inspect workflow receipts"),
        "next_evidence": sandbox_to_pr_next_evidence(status="complete" if receipt_ready else "pending"),
        "external_effects_allowed": False,
        "execution_boundary": "local_lab_only",
        "policy": {
            "ready": policy_ready,
            "change_capability_id": str(sandbox_to_pr_policy.get("change_capability_id") or ""),
            "pr_capability_id": str(sandbox_to_pr_policy.get("pr_capability_id") or ""),
            "rollback_default": sandbox_to_pr_policy.get("rollback_default") is True,
            "approval_required": sandbox_to_pr_policy.get("approval_required") is True,
        },
        "receipts": {
            "ready": receipt_ready,
            "completed_count": int(readiness.get("receipt_checklist_completed_count", 0) or 0),
            "required_count": int(readiness.get("receipt_checklist_required_count", 0) or 0),
            "rollback_receipt_status": str(readiness.get("rollback_receipt_status") or "not_recorded"),
        },
        "receipt_bundle_ref": {
            "schema_ref": "schemas/developer_workflow_sandbox_receipt_bundle.schema.json",
            "example_path": "examples/developer_workflow_sandbox_receipt_bundle.foundation.json",
            "validator": "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py",
            "builder": "python scripts/build_developer_workflow_sandbox_receipt_bundle.py",
        },
        "approval": {
            "required": sandbox_to_pr_policy.get("approval_required") is True,
            "status": approval_status,
        },
        "pr_candidate": {
            "status": pr_status,
            "prepared": pr_status == "complete",
        },
        "required_evidence": [
            {
                "evidence_id": "capability_passports",
                "status": "complete" if policy_ready else "pending",
                "source": "capability_health.metadata.sandbox_to_pr_policy",
            },
            {
                "evidence_id": "sandbox_receipts",
                "status": "complete" if receipt_ready else "pending",
                "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist",
            },
            {
                "evidence_id": "operator_approval",
                "status": approval_status,
                "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.operator_approval",
            },
            {
                "evidence_id": "pr_candidate",
                "status": pr_status,
                "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.pr_candidate",
            },
        ],
    }


def _sandbox_receipt_attachment_packet_projection(
    *,
    sandbox_to_pr_packet: Mapping[str, Any],
    developer_workflow_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return bounded operator rows for attaching sandbox receipt evidence."""

    bundle_receipts = developer_workflow_summary.get("sandbox_receipt_bundle_receipts", ())
    if not isinstance(bundle_receipts, list):
        bundle_receipts = []
    bundle_by_id = {
        str(receipt.get("receipt_id") or ""): receipt
        for receipt in bundle_receipts
        if isinstance(receipt, Mapping)
    }
    next_evidence = sandbox_to_pr_packet.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    evidence_by_id = {
        str(item.get("evidence_id") or ""): item
        for item in next_evidence
        if isinstance(item, Mapping)
    }
    receipt_order = (
        ("sandbox_patch_receipt", "Sandbox patch receipt", "write_files_in_sandbox"),
        ("test_gate_receipt", "Test gate receipt", "run_tests"),
        ("diff_review_receipt", "Diff review receipt", "show_diff"),
        ("terminal_receipt", "Terminal receipt", "show_receipt"),
    )
    attachments = [
        _sandbox_receipt_attachment_row(
            receipt_id=receipt_id,
            label=label,
            stage=stage,
            evidence=evidence_by_id.get(receipt_id, {}),
            bundle_receipt=bundle_by_id.get(receipt_id, {}),
        )
        for receipt_id, label, stage in receipt_order
    ]
    completed_count = sum(1 for item in attachments if item["status"] == "attached")
    next_attachment = next(
        (
            {
                "receipt_id": str(item["receipt_id"]),
                "label": str(item["label"]),
                "status": str(item["status"]),
                "action": str(item["action"]),
            }
            for item in attachments
            if item["status"] != "attached"
        ),
        {
            "receipt_id": "none",
            "label": "All sandbox receipts attached",
            "status": "complete",
            "action": "review sandbox receipt bundle before PR preparation approval",
        },
    )
    return {
        "packet_id": "developer_workflow_sandbox_receipt_attachment_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": str(
            developer_workflow_summary.get("workflow_run_id") or "developer_workflow_v1_foundation_run"
        ),
        "packet_status": "attachments_complete" if completed_count == len(receipt_order) else "awaiting_attachments",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "required_count": len(receipt_order),
        "completed_count": completed_count,
        "next_attachment": next_attachment,
        "source_refs": {
            "sandbox_to_pr_packet": "workflow_monitor.metadata.sandbox_to_pr_packet",
            "sandbox_receipt_bundle": "workflow_monitor.metadata.developer_workflow_run.sandbox_receipt_bundle_receipts",
            "builder": "python scripts/build_developer_workflow_sandbox_receipt_attachment_packet.py",
            "validator": "python scripts/validate_developer_workflow_sandbox_receipt_attachment_packet.py",
        },
        "attachments": attachments,
    }


def _sandbox_receipt_attachment_readiness_summary(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact API-facing sandbox receipt attachment summary."""

    next_attachment = packet.get("next_attachment", {})
    if not isinstance(next_attachment, Mapping):
        next_attachment = {}
    return {
        "packet_status": str(packet.get("packet_status") or "awaiting_attachments"),
        "completed_count": int(packet.get("completed_count", 0) or 0),
        "required_count": int(packet.get("required_count", 0) or 0),
        "next_receipt_id": str(next_attachment.get("receipt_id") or "sandbox_patch_receipt"),
        "next_label": str(next_attachment.get("label") or "Sandbox patch receipt"),
        "next_status": str(next_attachment.get("status") or "awaiting_attachment"),
        "next_action": str(
            next_attachment.get("action")
            or "attach before state, after state, diff, command, and rollback receipt"
        ),
        "execution_boundary": str(packet.get("execution_boundary") or "local_lab_only"),
        "external_effects_allowed": False,
    }


def _sandbox_to_pr_summary(
    *,
    packet: Mapping[str, Any],
    focus: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact API-facing sandbox-to-PR gate summary."""

    receipts = packet.get("receipts", {})
    if not isinstance(receipts, Mapping):
        receipts = {}
    approval = packet.get("approval", {})
    if not isinstance(approval, Mapping):
        approval = {}
    pr_candidate = packet.get("pr_candidate", {})
    if not isinstance(pr_candidate, Mapping):
        pr_candidate = {}
    next_evidence = packet.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    return {
        "status": str(packet.get("status") or "awaiting_receipts"),
        "blocker": str(packet.get("blocker") or "sandbox_receipts_incomplete"),
        "focus_id": str(focus.get("focus_id") or "sandbox_patch_receipt"),
        "focus_status": str(focus.get("status") or "pending"),
        "next_action": str(packet.get("next_action") or "inspect workflow receipts"),
        "next_evidence_count": len([item for item in next_evidence if isinstance(item, Mapping)]),
        "receipt_completed_count": int(receipts.get("completed_count", 0) or 0),
        "receipt_required_count": int(receipts.get("required_count", 0) or 0),
        "operator_approval_status": str(approval.get("status") or "pending"),
        "pr_candidate_status": str(pr_candidate.get("status") or "pending"),
        "execution_boundary": str(packet.get("execution_boundary") or "local_lab_only"),
        "external_effects_allowed": False,
    }


def _sandbox_receipt_attachment_row(
    *,
    receipt_id: str,
    label: str,
    stage: str,
    evidence: Mapping[str, Any],
    bundle_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    bundle_status = str(bundle_receipt.get("status") or "pending")
    status = "attached" if bundle_status == "complete" else "awaiting_attachment"
    evidence_refs = bundle_receipt.get("evidence_refs", ())
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    return {
        "receipt_id": receipt_id,
        "label": str(bundle_receipt.get("label") or evidence.get("label") or label),
        "stage": str(bundle_receipt.get("stage") or stage),
        "status": status,
        "action": str(evidence.get("action") or ""),
        "source": str(bundle_receipt.get("source") or evidence.get("source") or ""),
        "bundle_receipt_status": bundle_status,
        "required_inputs": [
            "before_state_hash",
            "after_state_hash",
            "diff_hash",
            "command",
            "rollback_command",
            "evidence_refs",
        ],
        "observed_inputs": {
            "before_state_hash": "pending",
            "after_state_hash": "pending",
            "diff_hash": "pending",
            "command": "pending",
            "rollback_command": "pending",
        },
        "evidence_refs": [str(ref) for ref in evidence_refs if str(ref).strip()],
    }


def _pr_readiness_bundle_projection(
    *,
    sandbox_to_pr_packet: Mapping[str, Any],
    developer_workflow_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the compact operator-facing PR readiness bundle projection."""

    receipts = sandbox_to_pr_packet.get("receipts", {})
    approval = sandbox_to_pr_packet.get("approval", {})
    pr_candidate = sandbox_to_pr_packet.get("pr_candidate", {})
    if not isinstance(receipts, Mapping):
        receipts = {}
    if not isinstance(approval, Mapping):
        approval = {}
    if not isinstance(pr_candidate, Mapping):
        pr_candidate = {}
    receipt_ready = receipts.get("ready") is True
    approval_complete = str(approval.get("status") or "pending") == "complete"
    candidate_prepared = pr_candidate.get("prepared") is True
    artifacts = {
        "sandbox_receipts": {
            "status": "receipts_complete" if receipt_ready else "awaiting_receipts",
            "ready": receipt_ready,
        },
        "approval_packet": {
            "status": "approved" if approval_complete else "pending",
            "ready": approval_complete,
        },
        "local_candidate": {
            "status": "ready_for_pr_tool" if candidate_prepared else "awaiting_receipts",
            "ready": candidate_prepared,
        },
        "pr_tool_admission": {
            "status": "local_tool_admitted" if candidate_prepared else "blocked_candidate_incomplete",
            "ready": candidate_prepared,
        },
        "external_approval_witness": {
            "status": "awaiting_operator_approval" if candidate_prepared else "awaiting_local_pr_tool_admission",
            "ready": False,
        },
        "command_preview": {
            "status": "blocked",
            "ready": False,
        },
        "metadata": {
            "status": "ready_for_preview" if candidate_prepared else "blocked_candidate_incomplete",
            "ready": candidate_prepared,
        },
    }
    if not receipt_ready:
        readiness_status = "awaiting_sandbox_receipts"
    elif not approval_complete or not candidate_prepared:
        readiness_status = "awaiting_operator_approval"
    else:
        readiness_status = "awaiting_external_pr_approval"
    next_evidence = [key for key, value in artifacts.items() if value["ready"] is not True]
    first_blocker = next_evidence[0] if next_evidence else "none"
    return {
        "bundle_id": "pr_readiness_bundle.v1",
        "schema_ref": "schemas/pr_readiness_bundle.schema.json",
        "readiness_status": readiness_status,
        "ready_for_external_pr_execution": False,
        "preview_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "first_blocker": first_blocker,
        "next_evidence": next_evidence,
        "artifacts": artifacts,
        "receipt_progress": {
            "completed_count": int(receipts.get("completed_count", 0) or 0),
            "required_count": int(receipts.get("required_count", 0) or 0),
        },
        "operator_summary": (
            "Sandbox receipt bundle is incomplete; PR execution remains blocked."
            if readiness_status == "awaiting_sandbox_receipts"
            else "PR execution remains blocked until approval witness, command preview, and metadata close."
        ),
        "source_refs": {
            "developer_workflow_run": str(developer_workflow_summary.get("workflow_run_id") or ""),
            "sandbox_to_pr_packet": "workflow_monitor.metadata.sandbox_to_pr_packet",
            "bundle_schema": "schemas/pr_readiness_bundle.schema.json",
            "bundle_validator": "python scripts/validate_pr_readiness_bundle.py",
        },
    }


def _pr_readiness_summary(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact API-facing PR readiness summary."""

    receipt_progress = bundle.get("receipt_progress", {})
    if not isinstance(receipt_progress, Mapping):
        receipt_progress = {}
    next_evidence = bundle.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    return {
        "readiness_status": str(bundle.get("readiness_status") or "awaiting_sandbox_receipts"),
        "ready_for_external_pr_execution": bundle.get("ready_for_external_pr_execution") is True,
        "first_blocker": str(bundle.get("first_blocker") or "unknown"),
        "next_evidence_count": len([item for item in next_evidence if str(item).strip()]),
        "receipt_completed_count": int(receipt_progress.get("completed_count", 0) or 0),
        "receipt_required_count": int(receipt_progress.get("required_count", 0) or 0),
        "preview_only": bundle.get("preview_only") is True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
    }


def _developer_workflow_operator_receipt_projection(
    *,
    pr_readiness_bundle: Mapping[str, Any],
    developer_workflow_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the compact no-execution operator receipt projection."""

    readiness_status = str(pr_readiness_bundle.get("readiness_status") or "awaiting_sandbox_receipts")
    ready_for_external = pr_readiness_bundle.get("ready_for_external_pr_execution") is True
    artifacts = pr_readiness_bundle.get("artifacts", {})
    if not isinstance(artifacts, Mapping):
        artifacts = {}
    command_preview = artifacts.get("command_preview", {})
    if not isinstance(command_preview, Mapping):
        command_preview = {}
    receipt = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "schema_ref": "schemas/developer_workflow_operator_receipt.schema.json",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": str(developer_workflow_summary.get("workflow_run_id") or "developer_workflow_v1_foundation_run"),
        "solver_outcome": "SolvedUnverified" if ready_for_external else "AwaitingEvidence",
        "readiness_status": readiness_status,
        "execution_performed": False,
        "ready_for_external_pr_execution": ready_for_external,
        "external_approval_status": "pending",
        "local_candidate_ready": ready_for_external,
        "pr_tool_admitted": ready_for_external,
        "rollback_required": True,
        "rollback_command_preview": "external PR rollback command unavailable until generated operator receipt is loaded",
        "rollback_command_count": 0,
        "evidence_chain": [
            {"stage": "sandbox_receipts", "status": "unknown", "ref": "workflow_monitor.metadata.developer_workflow_run"},
            {"stage": "pr_preparation_approval", "status": "pending", "ref": "workflow_monitor.metadata.pr_readiness_bundle"},
            {"stage": "local_pr_candidate", "status": "pending", "ref": "workflow_monitor.metadata.pr_readiness_bundle"},
            {"stage": "external_approval", "status": "pending", "ref": "external_approval_witness"},
        ],
        "command_preview_rendered": command_preview.get("ready") is True,
        "next_evidence": [
            str(item)
            for item in pr_readiness_bundle.get("next_evidence", ())
            if str(item).strip()
        ][:8],
        "external_effects_allowed": False,
        "source_refs": {
            "pr_readiness": "workflow_monitor.metadata.pr_readiness_bundle",
            "schema": "schemas/developer_workflow_operator_receipt.schema.json",
            "builder": "python scripts/build_developer_workflow_operator_receipt.py",
        },
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def _developer_workflow_operator_receipt_from_generated_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Return dashboard-safe fields from a validated generated operator receipt."""

    operator_status = _developer_workflow_operator_status_from_generated_receipt(receipt)
    return {
        "receipt_id": operator_status["receipt_id"],
        "schema_ref": "schemas/developer_workflow_operator_receipt.schema.json",
        "workflow_id": operator_status["workflow_id"],
        "workflow_run_id": operator_status["workflow_run_id"],
        "solver_outcome": operator_status["solver_outcome"],
        "readiness_status": operator_status["readiness_status"],
        "execution_performed": False,
        "ready_for_external_pr_execution": operator_status["ready_for_external_pr_execution"],
        "external_approval_status": operator_status["external_approval_status"],
        "local_candidate_ready": operator_status["local_candidate_ready"],
        "pr_tool_admitted": operator_status["pr_tool_admitted"],
        "rollback_required": operator_status["rollback_required"],
        "rollback_command_preview": operator_status["rollback_command_preview"],
        "rollback_command_count": operator_status["rollback_command_count"],
        "evidence_chain": operator_status["evidence_chain"],
        "command_preview_rendered": operator_status["command_preview_rendered"],
        "next_evidence": operator_status["next_evidence"],
        "external_effects_allowed": False,
        "source_refs": operator_status["source_refs"],
        "receipt_hash": operator_status["receipt_hash"],
    }


def _developer_workflow_operator_status_from_generated_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize generated Developer Workflow operator receipt fields for projections."""

    external_handoff = receipt.get("external_handoff", {})
    if not isinstance(external_handoff, Mapping):
        external_handoff = {}
    approvals = receipt.get("approvals", {})
    if not isinstance(approvals, Mapping):
        approvals = {}
    external_approval = approvals.get("external_pr_execution", {})
    if not isinstance(external_approval, Mapping):
        external_approval = {}
    local_candidate = receipt.get("local_pr_candidate", {})
    if not isinstance(local_candidate, Mapping):
        local_candidate = {}
    rollback = receipt.get("rollback", {})
    if not isinstance(rollback, Mapping):
        rollback = {}
    rollback_commands = rollback.get("commands", ())
    if not isinstance(rollback_commands, list):
        rollback_commands = []
    rollback_command_preview = next(
        (str(command) for command in rollback_commands if str(command).strip()),
        "rollback command unavailable",
    )
    sandbox_receipts = receipt.get("sandbox_receipts", {})
    if not isinstance(sandbox_receipts, Mapping):
        sandbox_receipts = {}
    pr_preparation = approvals.get("pr_preparation", {})
    if not isinstance(pr_preparation, Mapping):
        pr_preparation = {}
    source_refs = receipt.get("source_refs", {})
    if not isinstance(source_refs, Mapping):
        source_refs = {}
    evidence_chain = [
        {
            "stage": "sandbox_receipts",
            "status": str(sandbox_receipts.get("bundle_status") or "unknown"),
            "ref": str(source_refs.get("sandbox_receipt_bundle_path") or "sandbox_receipts"),
        },
        {
            "stage": "pr_preparation_approval",
            "status": str(pr_preparation.get("status") or "pending"),
            "ref": str(source_refs.get("approval_packet_path") or "pr_preparation_approval"),
        },
        {
            "stage": "local_pr_candidate",
            "status": str(local_candidate.get("candidate_status") or "pending"),
            "ref": str(source_refs.get("local_candidate_packet_path") or "local_pr_candidate"),
        },
        {
            "stage": "external_approval",
            "status": str(external_approval.get("status") or "pending"),
            "ref": str(source_refs.get("external_approval_witness_path") or "external_approval_witness"),
        },
    ]
    next_evidence = receipt.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    normalized_next_evidence = [str(item) for item in next_evidence if str(item).strip()][:8]
    return {
        "receipt_id": str(receipt.get("receipt_id") or "developer_workflow_operator_receipt.v1"),
        "workflow_id": str(receipt.get("workflow_id") or "mullu_developer_workflow.v1"),
        "workflow_run_id": str(receipt.get("workflow_run_id") or "developer_workflow_v1_foundation_run"),
        "solver_outcome": str(receipt.get("solver_outcome") or "AwaitingEvidence"),
        "readiness_status": str(receipt.get("readiness_status") or "awaiting_sandbox_receipts"),
        "ready_for_external_pr_execution": external_handoff.get("ready_for_external_pr_execution") is True,
        "external_approval_status": str(external_approval.get("status") or "pending"),
        "local_candidate_ready": local_candidate.get("candidate_ready") is True,
        "pr_tool_admitted": local_candidate.get("pr_tool_admitted") is True,
        "sandbox_receipts_completed": int(sandbox_receipts.get("completed_count", 0) or 0),
        "sandbox_receipts_required": int(sandbox_receipts.get("required_count", 0) or 0),
        "rollback_required": rollback.get("required") is True,
        "rollback_command_preview": rollback_command_preview,
        "rollback_command_count": len([command for command in rollback_commands if str(command).strip()]),
        "evidence_chain": evidence_chain,
        "command_preview_rendered": external_handoff.get("command_preview_rendered") is True,
        "next_evidence": normalized_next_evidence,
        "first_next_evidence": normalized_next_evidence[0] if normalized_next_evidence else "none",
        "source_refs": dict(source_refs),
        "receipt_hash": str(receipt.get("receipt_hash") or ""),
    }


def _developer_workflow_operator_receipt_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact API-facing Developer Workflow operator receipt summary."""

    next_evidence = receipt.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    return {
        "solver_outcome": str(receipt.get("solver_outcome") or "AwaitingEvidence"),
        "readiness_status": str(receipt.get("readiness_status") or "awaiting_sandbox_receipts"),
        "ready_for_external_pr_execution": receipt.get("ready_for_external_pr_execution") is True,
        "external_approval_status": str(receipt.get("external_approval_status") or "pending"),
        "local_candidate_ready": receipt.get("local_candidate_ready") is True,
        "pr_tool_admitted": receipt.get("pr_tool_admitted") is True,
        "rollback_required": receipt.get("rollback_required") is True,
        "rollback_command_count": int(receipt.get("rollback_command_count", 0) or 0),
        "evidence_chain_count": len(receipt.get("evidence_chain", ())) if isinstance(receipt.get("evidence_chain"), list) else 0,
        "command_preview_rendered": receipt.get("command_preview_rendered") is True,
        "next_evidence_count": len([item for item in next_evidence if str(item).strip()]),
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _sandbox_to_pr_next_evidence_focus(sandbox_to_pr_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the single operator-focus evidence item for sandbox-to-PR readiness."""
    blocker = str(sandbox_to_pr_packet.get("blocker") or "unknown")
    next_action = str(sandbox_to_pr_packet.get("next_action") or "inspect workflow receipts")
    if blocker == "sandbox_receipts_incomplete":
        next_evidence = sandbox_to_pr_packet.get("next_evidence", ())
        if isinstance(next_evidence, list):
            for item in next_evidence:
                if isinstance(item, Mapping) and item.get("status") != "complete":
                    evidence_id = str(item.get("evidence_id") or "")
                    return {
                        "focus_id": evidence_id,
                        "label": str(item.get("label") or evidence_id),
                        "status": str(item.get("status") or "pending"),
                        "action": str(item.get("action") or next_action),
                        "source": str(item.get("source") or ""),
                        "next_action": next_action,
                        "blocker": blocker,
                    }
    required_evidence = sandbox_to_pr_packet.get("required_evidence", ())
    required_by_id = {
        str(item.get("evidence_id") or ""): item
        for item in required_evidence
        if isinstance(required_evidence, list) and isinstance(item, Mapping)
    }
    focus_labels = {
        "capability_policy_incomplete": ("capability_passports", "Capability passports"),
        "operator_approval_missing": ("operator_approval", "Operator approval"),
        "pr_candidate_not_prepared": ("pr_candidate", "PR candidate"),
    }
    evidence_id, label = focus_labels.get(blocker, ("none", "No pending sandbox-to-PR evidence"))
    evidence = required_by_id.get(evidence_id, {})
    return {
        "focus_id": evidence_id,
        "label": label,
        "status": str(evidence.get("status") or ("complete" if evidence_id == "none" else "pending")),
        "action": next_action,
        "source": str(evidence.get("source") or ""),
        "next_action": next_action,
        "blocker": blocker,
    }


def create_gateway_app(
    platform: Any = None,
    *,
    capability_admission_gate_override: Any | None = None,
    command_ledger_override: Any | None = None,
    software_receipt_store_override: Any | None = None,
    tenant_budget_reporter: Any | None = None,
    mcp_capability_entries: tuple[Any, ...] = (),
    mcp_executor: Any | None = None,
    mcp_authority_records: MCPAuthorityRecords | None = None,
    axiomworld_adapter: Any | None = None,
) -> FastAPI:
    """Create the gateway FastAPI app.

    If platform is None, attempts to import from MCOI server.
    """
    if platform is None:
        try:
            from mcoi_runtime.core.governed_session import Platform
            platform = Platform.from_env()
        except Exception:
            platform = None

    from datetime import datetime, timezone
    import hmac

    def _clock() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _int_env(name: str, default: int = 0) -> int:
        try:
            return int(os.environ.get(name, str(default)))
        except ValueError:
            return default

    _raw_gateway_env = os.environ.get("MULLU_ENV", "").strip().lower()
    gateway_env = _raw_gateway_env or "local_dev"
    # Security: the authority bypass below requires an EXPLICIT dev/test env.
    # An unset MULLU_ENV must fail closed (see _explicit_dev_or_test_env).
    _dev_authority_bypass = _explicit_dev_or_test_env(_raw_gateway_env)
    approval_secret = os.environ.get("MULLU_GATEWAY_APPROVAL_SECRET", "")
    authority_operator_secret = os.environ.get("MULLU_AUTHORITY_OPERATOR_SECRET", "")
    authority_operator_roles = tuple(
        role.strip()
        for role in os.environ.get(
            "MULLU_AUTHORITY_OPERATOR_ROLES",
            "authority_operator,tenant_owner,platform_operator",
        ).split(",")
        if role.strip()
    )
    deployment_authority_secret = os.environ.get("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "")
    deployment_authority_roles = tuple(
        role.strip()
        for role in os.environ.get(
            "MULLU_DEPLOYMENT_AUTHORITY_ROLES",
            "deployment_authority,platform_operator",
        ).split(",")
        if role.strip()
    )
    authority_operator_audit_events: list[dict[str, Any]] = []
    capability_capsule_admission_receipts: list[dict[str, Any]] = []
    physical_capability_promotion_receipt_store = build_physical_capability_promotion_receipt_store_from_env()
    software_receipt_store = software_receipt_store_override
    if software_receipt_store is None:
        try:
            from mcoi_runtime.app.software_receipt_integration import select_software_receipt_store

            software_receipt_store = select_software_receipt_store(os.environ).store
        except Exception:
            software_receipt_store = None
    platform_decision_log = getattr(platform, "_decision_log", None)
    reflex_deployment_witness_log_backed = platform_decision_log is not None
    reflex_deployment_witness_log = platform_decision_log or GovernanceDecisionLog(clock=_clock)
    reflex_ephemeral_witness_log_allowed = gateway_env in {"local_dev", "test"} or (
        os.environ.get("MULLU_ALLOW_EPHEMERAL_REFLEX_WITNESS_LOG", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    defer_approved_execution = (
        os.environ.get("MULLU_GATEWAY_DEFER_APPROVED_EXECUTION", "0").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    def _approval_webhook_authorized(request: Request) -> bool:
        """Fail closed outside local and test unless an explicit approval secret matches."""
        if _dev_authority_bypass:
            return True
        provided = request.headers.get("X-Mullu-Approval-Secret", "")
        if not approval_secret:
            return False
        return hmac.compare_digest(provided, approval_secret)

    def _authority_operator_authorized(request: Request) -> bool:
        """Fail closed outside local and test unless operator identity or secret matches."""
        if _dev_authority_bypass:
            return True
        provided = request.headers.get("X-Mullu-Authority-Secret", "")
        if authority_operator_secret and hmac.compare_digest(provided, authority_operator_secret):
            return True
        channel = request.headers.get("X-Mullu-Authority-Channel", "").strip()
        sender_id = request.headers.get("X-Mullu-Authority-Sender-Id", "").strip()
        if not channel or not sender_id:
            return False
        mapping = tenant_identity_store.resolve(channel, sender_id)
        if mapping is None:
            return False
        tenant_id = request.headers.get("X-Mullu-Authority-Tenant-Id", "").strip()
        if tenant_id and mapping.tenant_id != tenant_id:
            return False
        roles = set(mapping.roles)
        return bool(roles.intersection(authority_operator_roles))

    def _require_authority_operator(request: Request) -> None:
        authorized = _authority_operator_authorized(request)
        _record_authority_operator_audit(request, authorized=authorized)
        if not authorized:
            raise HTTPException(403, detail="Authority operator access not authorized")

    def _deployment_authority_authorized(request: Request) -> bool:
        """Fail closed outside local and test unless deployment authority is explicit."""
        if _dev_authority_bypass:
            return True
        provided = request.headers.get("X-Mullu-Deployment-Secret", "")
        if deployment_authority_secret and hmac.compare_digest(provided, deployment_authority_secret):
            return True
        channel = request.headers.get("X-Mullu-Authority-Channel", "").strip()
        sender_id = request.headers.get("X-Mullu-Authority-Sender-Id", "").strip()
        if not channel or not sender_id:
            return False
        mapping = tenant_identity_store.resolve(channel, sender_id)
        if mapping is None:
            return False
        tenant_id = request.headers.get("X-Mullu-Authority-Tenant-Id", "").strip()
        if tenant_id and mapping.tenant_id != tenant_id:
            return False
        roles = set(mapping.roles)
        return bool(roles.intersection(deployment_authority_roles))

    def _require_deployment_authority(request: Request) -> None:
        authorized = _deployment_authority_authorized(request)
        if not authorized:
            raise HTTPException(403, detail="Deployment authority access not authorized")

    def _seed_platform_identity_for_mapping(
        mapping: TenantMapping,
        *,
        platform_roles: tuple[str, ...],
    ) -> dict[str, Any]:
        """Seed the current platform RBAC identity for a deployment mapping."""
        access_runtime = getattr(platform, "_access_runtime", None)
        if access_runtime is None:
            return {
                "available": False,
                "identity_registered": False,
                "identity_enabled": False,
                "roles_bound": [],
                "skipped_roles": list(platform_roles),
                "reason": "platform_access_runtime_not_available",
            }

        from mcoi_runtime.contracts.access_runtime import AuthContextKind, IdentityKind
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

        identity_registered = False
        identity_enabled = False
        try:
            identity = access_runtime.get_identity(mapping.identity_id)
        except RuntimeCoreInvariantError:
            identity = access_runtime.register_identity(
                mapping.identity_id,
                mapping.identity_id,
                kind=IdentityKind.SERVICE,
                tenant_id=mapping.tenant_id,
                enabled=True,
            )
            identity_registered = True

        identity_tenant_id = getattr(identity, "tenant_id", "")
        if identity_tenant_id and identity_tenant_id != mapping.tenant_id:
            raise HTTPException(409, detail="platform identity tenant mismatch")

        if getattr(identity, "enabled", False) is not True:
            identity = access_runtime.enable_identity(mapping.identity_id)
            identity_enabled = True

        existing_bindings = {
            (binding.role_id, binding.scope_kind, binding.scope_ref_id)
            for binding in access_runtime.bindings_for_identity(mapping.identity_id)
        }
        roles_bound: list[str] = []
        skipped_roles: list[str] = []
        for role in platform_roles:
            if not role:
                continue
            if not access_runtime.has_role(role):
                skipped_roles.append(role)
                continue
            binding_key = (role, AuthContextKind.TENANT, mapping.tenant_id)
            if binding_key in existing_bindings:
                continue
            binding_id = f"deploy-bind-{canonical_hash({
                'identity_id': mapping.identity_id,
                'role_id': role,
                'tenant_id': mapping.tenant_id,
            })[:16]}"
            access_runtime.bind_role(
                binding_id,
                mapping.identity_id,
                role,
                scope_kind=AuthContextKind.TENANT,
                scope_ref_id=mapping.tenant_id,
            )
            roles_bound.append(role)
            existing_bindings.add(binding_key)

        return {
            "available": True,
            "identity_registered": identity_registered,
            "identity_enabled": identity_enabled,
            "roles_bound": roles_bound,
            "skipped_roles": skipped_roles,
            "reason": "platform_identity_seeded",
        }

    def _seed_platform_tenant_gate_for_mapping(mapping: TenantMapping) -> dict[str, Any]:
        """Seed the current platform tenant gate for a deployment mapping."""
        tenant_gating = getattr(platform, "_tenant_gating", None)
        if tenant_gating is None:
            return {
                "available": False,
                "tenant_registered": False,
                "status_updated": False,
                "status": "unavailable",
                "reason": "platform_tenant_gating_not_available",
            }
        if not hasattr(tenant_gating, "get_status") or not hasattr(tenant_gating, "register"):
            return {
                "available": False,
                "tenant_registered": False,
                "status_updated": False,
                "status": "unavailable",
                "reason": "platform_tenant_gating_registry_not_available",
            }

        from mcoi_runtime.governance.guards.tenant_gating import TenantGatingError, TenantStatus

        gate = tenant_gating.get_status(mapping.tenant_id)
        tenant_registered = False
        status_updated = False
        try:
            if gate is None:
                gate = tenant_gating.register(
                    mapping.tenant_id,
                    status=TenantStatus.ACTIVE,
                    reason="deployment tenant mapping bootstrap",
                )
                tenant_registered = True
            elif gate.status == TenantStatus.ONBOARDING and hasattr(tenant_gating, "update_status"):
                gate = tenant_gating.update_status(
                    mapping.tenant_id,
                    TenantStatus.ACTIVE,
                    reason="deployment tenant mapping bootstrap",
                )
                status_updated = True
        except TenantGatingError as exc:
            raise HTTPException(409, detail="platform tenant gate bootstrap rejected") from exc

        if gate.status != TenantStatus.ACTIVE:
            raise HTTPException(409, detail="platform tenant gate not active")

        return {
            "available": True,
            "tenant_registered": tenant_registered,
            "status_updated": status_updated,
            "status": gate.status.value,
            "reason": "platform_tenant_gate_seeded",
        }

    def _require_reflex_deployment_witness_log_backed() -> None:
        if reflex_deployment_witness_log_backed or reflex_ephemeral_witness_log_allowed:
            return
        raise HTTPException(
            503,
            detail="Persistent Reflex deployment witness log required",
        )

    def _stable_payload_hash(payload: dict[str, Any]) -> str:
        """Return a deterministic hash for a JSON-compatible witness payload."""
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    def _signed_claim(payload: dict[str, Any], *, signing_secret: str, signature_key_id: str) -> dict[str, Any]:
        """Return a payload with a bounded HMAC claim signature."""
        claim = {**payload, "signature_key_id": signature_key_id}
        unsigned_hash = _stable_payload_hash(claim)
        signature = hmac.new(signing_secret.encode("utf-8"), unsigned_hash.encode("utf-8"), sha256).hexdigest()
        return {
            **claim,
            "claim_hash": unsigned_hash,
            "signature": f"hmac-sha256:{signature}",
        }

    def _signed_claim_valid(payload: dict[str, Any], *, signing_secret: str) -> bool:
        """Verify a signed claim emitted by this gateway."""
        signature = str(payload.get("signature", ""))
        if not signature.startswith("hmac-sha256:") or not signing_secret:
            return False
        unsigned = dict(payload)
        unsigned.pop("signature", None)
        observed_hash = str(unsigned.pop("claim_hash", ""))
        expected_hash = _stable_payload_hash(unsigned)
        if not hmac.compare_digest(observed_hash, expected_hash):
            return False
        expected_signature = hmac.new(
            signing_secret.encode("utf-8"),
            expected_hash.encode("utf-8"),
            sha256,
        ).hexdigest()
        return hmac.compare_digest(signature.removeprefix("hmac-sha256:"), expected_signature)

    def _hmac_certificate_signature_valid(payload: dict[str, Any], *, signing_secret: str) -> bool:
        """Verify conformance-style HMAC signatures without leaking certificate details."""
        signature = str(payload.get("signature", ""))
        if not signature.startswith("hmac-sha256:") or not signing_secret:
            return False
        unsigned = dict(payload)
        unsigned.pop("signature", None)
        expected_hash = _stable_payload_hash(unsigned)
        expected_signature = hmac.new(
            signing_secret.encode("utf-8"),
            expected_hash.encode("utf-8"),
            sha256,
        ).hexdigest()
        return hmac.compare_digest(signature.removeprefix("hmac-sha256:"), expected_signature)

    def _status_from_bool(passed: bool) -> str:
        """Map a witnessed boolean to public health status text."""
        return "pass" if passed else "missing"

    def _deployment_identity_token(value: str) -> str:
        """Return a public-safe deployment identity token."""
        normalized = "".join(character.lower() if character.isalnum() else "_" for character in value.strip())
        compact = "_".join(part for part in normalized.split("_") if part)
        return compact[:64]

    def _deployment_id() -> str:
        """Return configured deployment id or derive one from public Render metadata."""
        configured = os.environ.get("MULLU_DEPLOYMENT_ID", "").strip()
        if configured:
            return configured
        render_service_id = _deployment_identity_token(os.environ.get("RENDER_SERVICE_ID", ""))
        render_commit_sha = _deployment_identity_token(os.environ.get("RENDER_GIT_COMMIT", ""))[:12]
        if render_service_id and render_commit_sha:
            return f"dep_render_{render_service_id}_{render_commit_sha}"
        if render_service_id:
            return f"dep_render_{render_service_id}"
        return f"dep_{gateway_env}_unpublished"

    def _commit_sha() -> str:
        """Return configured commit sha without reading deployment host state."""
        for name in ("MULLU_DEPLOYED_COMMIT_SHA", "RENDER_GIT_COMMIT", "GITHUB_SHA", "COMMIT_SHA", "SOURCE_VERSION"):
            value = os.environ.get(name, "").strip()
            if value:
                return value
        return "unknown"

    def _truthy_env(name: str, default: bool = False) -> bool:
        """Return a bounded boolean interpretation for operator feature gates."""
        value = os.environ.get(name, "").strip().lower()
        if not value:
            return default
        return value in {"1", "true", "yes", "on"}

    def _govern_cloud_internal_base_url() -> str | None:
        """Return a validated Govern Cloud internal base URL or None."""
        internal_url = os.environ.get("MULLU_GOVERN_CLOUD_INTERNAL_URL", "").strip()
        if not internal_url:
            return None
        parsed_url = urlsplit(internal_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.path not in {"", "/"}
        ):
            return None
        return f"{parsed_url.scheme}://{parsed_url.netloc}".rstrip("/")

    def _govern_cloud_public_proxy_enabled() -> bool:
        """Return whether the public Govern Cloud proxy is explicitly enabled."""
        return _truthy_env("MULLU_GOVERN_CLOUD_STAGING_ENABLED") and _truthy_env(
            "MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED"
        )

    def _govern_cloud_public_json_proxy(path: str) -> JSONResponse:
        """Forward an allowlisted public Govern Cloud read-model route."""
        if path not in GOVERN_CLOUD_PUBLIC_PROXY_PATHS:
            raise HTTPException(status_code=404, detail="Govern Cloud route not published")
        if not _govern_cloud_public_proxy_enabled():
            raise HTTPException(status_code=404, detail="Govern Cloud public proxy not enabled")
        base_url = _govern_cloud_internal_base_url()
        if base_url is None:
            raise HTTPException(status_code=503, detail="Govern Cloud public proxy not configured")
        try:
            assert_proxy_environment_allowed()
        except RuntimeError as exc:
            _log.warning("Govern Cloud public proxy blocked by proxy policy: %s", exc)
            raise HTTPException(status_code=503, detail="Govern Cloud outbound proxy environment blocked") from exc

        request = urllib.request.Request(
            f"{base_url}{path}",
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "mullusi-govern-cloud-public-proxy/1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=GOVERN_CLOUD_PUBLIC_PROXY_TIMEOUT_SECONDS) as response:
                raw_status_code = getattr(response, "status", None)
                status_code = int(raw_status_code if raw_status_code is not None else response.getcode())
                if status_code != 200:
                    raise HTTPException(status_code=502, detail="Govern Cloud upstream returned non-OK status")
                headers = getattr(response, "headers", {}) or {}
                content_length = headers.get("Content-Length") if hasattr(headers, "get") else None
                if content_length:
                    try:
                        parsed_content_length = int(content_length)
                    except ValueError as exc:
                        raise HTTPException(
                            status_code=502,
                            detail="Govern Cloud upstream response length invalid",
                        ) from exc
                    if parsed_content_length > GOVERN_CLOUD_PUBLIC_PROXY_MAX_BYTES:
                        raise HTTPException(status_code=502, detail="Govern Cloud upstream response too large")
                raw_payload = response.read(GOVERN_CLOUD_PUBLIC_PROXY_MAX_BYTES + 1)
        except HTTPException:
            raise
        except urllib.error.HTTPError as exc:
            _log.warning("Govern Cloud public proxy upstream HTTP error: %s", exc.code)
            raise HTTPException(status_code=502, detail="Govern Cloud upstream rejected request") from exc
        except (TimeoutError, socket.timeout) as exc:
            _log.warning("Govern Cloud public proxy timed out")
            raise HTTPException(status_code=504, detail="Govern Cloud upstream timed out") from exc
        except (urllib.error.URLError, OSError) as exc:
            _log.warning("Govern Cloud public proxy transport failed: %s", exc)
            raise HTTPException(status_code=503, detail="Govern Cloud upstream unreachable") from exc

        if len(raw_payload) > GOVERN_CLOUD_PUBLIC_PROXY_MAX_BYTES:
            raise HTTPException(status_code=502, detail="Govern Cloud upstream response too large")
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=502, detail="Govern Cloud upstream response was not JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Govern Cloud upstream response was not an object")
        return JSONResponse(payload, status_code=200)

    def _govern_cloud_staging_read_model() -> dict[str, Any]:
        """Return a secret-free private Govern Cloud staging dependency witness."""
        enabled = _truthy_env("MULLU_GOVERN_CLOUD_STAGING_ENABLED")
        public_proxy_enabled = _truthy_env("MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED")
        internal_url = os.environ.get("MULLU_GOVERN_CLOUD_INTERNAL_URL", "").strip()
        parsed_url = urlsplit(internal_url) if internal_url else None
        internal_url_configured = bool(
            parsed_url
            and parsed_url.scheme in {"http", "https"}
            and parsed_url.netloc
            and not parsed_url.username
            and not parsed_url.password
            and not parsed_url.query
            and not parsed_url.fragment
        )
        checks = [
            {
                "check_id": "private_staging_enabled",
                "passed": enabled,
                "detail": "enabled" if enabled else "disabled",
            },
            {
                "check_id": "internal_url_configured",
                "passed": internal_url_configured,
                "detail": "configured" if internal_url_configured else "missing_or_invalid",
            },
            {
                "check_id": "public_proxy_disabled",
                "passed": not public_proxy_enabled,
                "detail": "disabled" if not public_proxy_enabled else "enabled",
            },
            {
                "check_id": "secret_values_omitted",
                "passed": True,
                "detail": "no secret values serialized",
            },
        ]
        configured = enabled and internal_url_configured
        return {
            "service": "mullusi-govern-cloud-staging",
            "dependency_type": "private_render_service",
            "runtime_env": gateway_env,
            "gateway_deployment_id": _deployment_id(),
            "gateway_commit_sha": _commit_sha(),
            "enabled": enabled,
            "internal_target": "configured" if internal_url_configured else "missing",
            "internal_scheme": parsed_url.scheme if internal_url_configured and parsed_url else "",
            "internal_host": parsed_url.hostname if internal_url_configured and parsed_url else "",
            "render_service_id": os.environ.get("MULLU_GOVERN_CLOUD_RENDER_SERVICE_ID", "").strip(),
            "render_deploy_id": os.environ.get("MULLU_GOVERN_CLOUD_RENDER_DEPLOY_ID", "").strip(),
            "image_tag": os.environ.get("MULLU_GOVERN_CLOUD_IMAGE_TAG", "").strip(),
            "database_plan": os.environ.get("MULLU_GOVERN_CLOUD_DATABASE_PLAN", "").strip(),
            "checks": checks,
            "checks_passed": [check["check_id"] for check in checks if check["passed"]],
            "checks_missing": [check["check_id"] for check in checks if not check["passed"]],
            "release_gate": (
                "private_staging_configured"
                if configured
                else "awaiting_private_staging_configuration"
            ),
            "solver_outcome": "AwaitingEvidence",
            "publication_allowed": False,
            "public_dns_mutation_allowed": False,
            "public_api_binding": "unchanged",
            "witness": "mullu_govern_cloud_private_staging_read_model_v1",
            "governed": True,
        }

    def _capability_evidence_projection() -> dict[str, Any]:
        """Return maturity-oriented capability evidence from the active fabric."""
        if capability_admission_gate is None:
            return {
                "enabled": False,
                "capability_count": 0,
                "capability_evidence": {},
                "live_capabilities": [],
                "sandbox_only_capabilities": [],
                "checks": [{
                    "check_id": "capability_registry_configured",
                    "passed": False,
                    "detail": "capability fabric admission is not configured",
                }],
            }
        read_model = capability_admission_gate.read_model()
        capabilities = tuple(read_model.get("capabilities", ()))
        evidence_by_capability: dict[str, str] = {}
        live_capabilities: list[str] = []
        sandbox_only_capabilities: list[str] = []
        for item in capabilities:
            if not isinstance(item, dict):
                continue
            capability_id = str(item.get("capability_id", "")).strip()
            if not capability_id:
                continue
            assessment = item.get("maturity_assessment", {})
            maturity_level = str(assessment.get("maturity_level", "C0")) if isinstance(assessment, dict) else "C0"
            production_ready = bool(assessment.get("production_ready")) if isinstance(assessment, dict) else False
            if production_ready:
                status = _capability_evidence_status(capability_id, item, production_ready=True)
                live_capabilities.append(capability_id)
            elif maturity_level in {"C4", "C5"}:
                status = "pilot"
            elif maturity_level == "C3":
                status = "sandbox"
                sandbox_only_capabilities.append(capability_id)
            elif maturity_level in {"C1", "C2"}:
                status = "tested"
            else:
                status = "described_only"
            evidence_by_capability[capability_id] = status
        return {
            "enabled": True,
            "capability_count": int(read_model.get("capability_count", len(evidence_by_capability))),
            "capsule_count": int(read_model.get("capsule_count", 0)),
            "require_certified": read_model.get("require_certified"),
            "capability_evidence": evidence_by_capability,
            "live_capabilities": live_capabilities,
            "sandbox_only_capabilities": sandbox_only_capabilities,
            "checks": [{
                "check_id": "capability_registry_configured",
                "passed": True,
                "detail": f"capability_count={len(evidence_by_capability)}",
            }],
        }

    def _capability_evidence_status(
        capability_id: str,
        capability_payload: Mapping[str, Any],
        *,
        production_ready: bool,
    ) -> str | dict[str, Any]:
        """Return public capability evidence without fabricating physical safety proof."""
        if not production_ready or not _is_physical_capability(capability_id):
            return "production"
        physical_evidence = _physical_live_safety_evidence_from_registry(capability_payload)
        return physical_evidence if physical_evidence is not None else "production"

    def _physical_live_safety_evidence_from_registry(
        capability_payload: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Derive live physical safety evidence from registry extensions."""
        extensions = capability_payload.get("extensions", {})
        if not isinstance(extensions, Mapping):
            return None
        safety_evidence = extensions.get(PHYSICAL_LIVE_SAFETY_EXTENSION_KEY, {})
        if not isinstance(safety_evidence, Mapping):
            return None
        refs: dict[str, str] = {}
        for field_name in REQUIRED_PHYSICAL_LIVE_SAFETY_FIELDS:
            ref = str(safety_evidence.get(field_name, "")).strip()
            if not ref:
                return None
            refs[field_name] = ref
        return {
            "maturity": "production",
            "effect_mode": "live",
            "production_admissible": True,
            "physical_action_receipt_schema_ref": PHYSICAL_ACTION_RECEIPT_SCHEMA_REF,
            **refs,
        }

    def _is_physical_capability(capability_id: str) -> bool:
        normalized = capability_id.strip().lower()
        return any(normalized.startswith(prefix) for prefix in PHYSICAL_CAPABILITY_PREFIXES)

    def _build_deployment_witness() -> dict[str, Any]:
        """Build the public production evidence witness for this gateway."""
        health_payload = health()
        conformance = runtime_conformance()
        capability_projection = _capability_evidence_projection()
        command_summary = command_ledger.summary()
        latest_anchors = command_ledger.list_anchors(limit=1)
        latest_anchor_id = latest_anchors[0].anchor_id if latest_anchors else ""
        latest_command_event_hash = str(
            command_summary.get("last_event_hash")
            or command_summary.get("latest_event_hash")
            or ""
        )
        checks = [
            {
                "check_id": "gateway_health",
                "passed": health_payload.get("status") == "healthy",
                "detail": str(health_payload.get("status", "unknown")),
            },
            {
                "check_id": "runtime_conformance",
                "passed": str(conformance.get("terminal_status", "")) in {
                    "conformant",
                    "conformant_with_gaps",
                },
                "detail": str(conformance.get("terminal_status", "missing")),
            },
            {
                "check_id": "capability_registry",
                "passed": capability_projection["enabled"],
                "detail": f"capability_count={capability_projection['capability_count']}",
            },
            {
                "check_id": "audit_anchor",
                "passed": bool(latest_anchor_id),
                "detail": latest_anchor_id or "anchor_missing",
            },
            {
                "check_id": "proof_store",
                "passed": int(command_summary.get("terminal_certificates", 0)) > 0,
                "detail": f"terminal_certificates={command_summary.get('terminal_certificates', 0)}",
            },
        ]
        passed_checks = [check["check_id"] for check in checks if check["passed"]]
        missing_checks = [check["check_id"] for check in checks if not check["passed"]]
        payload = {
            "deployment_id": _deployment_id(),
            "commit_sha": _commit_sha(),
            "runtime_env": gateway_env,
            "version": app.version,
            "gateway_health": _status_from_bool(health_payload.get("status") == "healthy"),
            "api_health": "pass",
            "db_health": _status_from_bool(command_summary.get("store", {}).get("available", True)),
            "policy_engine": "pass",
            "audit_store": _status_from_bool(bool(latest_command_event_hash or latest_anchor_id)),
            "proof_store": _status_from_bool(int(command_summary.get("terminal_certificates", 0)) > 0),
            "capability_evidence": capability_projection["capability_evidence"],
            "live_capabilities": capability_projection["live_capabilities"],
            "sandbox_only_capabilities": capability_projection["sandbox_only_capabilities"],
            "checks": checks,
            "checks_passed": passed_checks,
            "checks_missing": missing_checks,
            "runtime_conformance_certificate_id": conformance.get("certificate_id", ""),
            "signed_at": _clock(),
            "witness": "mullu_gateway_production_evidence_v1",
        }
        return _signed_claim(
            payload,
            signing_secret=os.environ.get("MULLU_DEPLOYMENT_WITNESS_SECRET", "local-deployment-witness-secret"),
            signature_key_id=os.environ.get("MULLU_DEPLOYMENT_WITNESS_KEY_ID", "deployment-witness-local"),
        )

    def _governed_operations_evidence_refs(
        *,
        conformance: Mapping[str, Any],
        deployment: Mapping[str, Any],
        authority_witness: Mapping[str, Any],
        latest_anchor_id: str,
    ) -> tuple[str, ...]:
        """Project existing read evidence into governed-operations refs."""
        refs: list[str] = []
        checks_missing = deployment.get("checks_missing", ())
        if isinstance(checks_missing, list) and not checks_missing and deployment.get("signature"):
            refs.append("deployment_witness:current")
        if deployment.get("gateway_health") == "pass":
            refs.append("runtime_health:pass")
        if deployment.get("proof_store") == "pass":
            refs.append("proof_verify:pass")
        deployment_id = str(deployment.get("deployment_id", "")).strip()
        if deployment_id and "unpublished" not in deployment_id:
            refs.append("domain:declared")
        if str(conformance.get("terminal_status", "")) in {"conformant", "conformant_with_gaps"}:
            refs.append("runtime_conformance:current")
        if latest_anchor_id:
            refs.append("audit_anchor:current")
        if bool(authority_witness.get("responsibility_debt_clear")):
            refs.append("authority:witness")
        return tuple(dict.fromkeys(refs))

    def _governed_operations_observed_states(
        *,
        conformance: Mapping[str, Any],
        deployment: Mapping[str, Any],
        authority_witness: Mapping[str, Any],
        latest_anchor_id: str,
    ) -> dict[str, str]:
        """Return conservative observed states for registered operations loops."""
        checks_missing = deployment.get("checks_missing", ())
        deployment_witnessed = (
            isinstance(checks_missing, list)
            and not checks_missing
            and bool(deployment.get("signature"))
        )
        terminal_status = str(conformance.get("terminal_status", "missing"))
        return {
            "deployment_witness": "witnessed" if deployment_witnessed else "awaiting_evidence",
            "runtime_conformance": "conformant" if terminal_status == "conformant" else terminal_status,
            "audit_proof_verification": "verified" if latest_anchor_id else "awaiting_evidence",
            "authority_obligations": "clear" if bool(authority_witness.get("responsibility_debt_clear")) else "debt_open",
            "cognitive_outcome_loop": "awaiting_evidence",
            "governed_code_change_loop": "awaiting_evidence",
            "adapter_promotion_loop": "awaiting_evidence",
        }

    def _unanchored_event_count() -> int:
        """Return unanchored command-event count when the ledger store exposes it."""
        store = getattr(command_ledger, "_store", None)
        if store is None or not hasattr(store, "unanchored_events"):
            return 0
        try:
            return len(store.unanchored_events())
        except Exception:
            return 0

    def _record_authority_operator_audit(request: Request, *, authorized: bool) -> None:
        """Record bounded authority operator access without storing bearer secrets."""
        channel = request.headers.get("X-Mullu-Authority-Channel", "").strip()
        sender_id = request.headers.get("X-Mullu-Authority-Sender-Id", "").strip()
        tenant_id = request.headers.get("X-Mullu-Authority-Tenant-Id", "").strip()
        provided_secret = request.headers.get("X-Mullu-Authority-Secret", "")
        credential_type = "none"
        if gateway_env in {"local_dev", "test"}:
            credential_type = "local_dev"
        elif provided_secret:
            credential_type = "operator_secret"
        elif channel or sender_id:
            credential_type = "tenant_identity"
        event_payload = {
            "event_type": "authority_operator_access_v1",
            "observed_at": _clock(),
            "method": request.method,
            "path": request.url.path,
            "authorized": authorized,
            "reason": "authorized" if authorized else "not_authorized",
            "credential_type": credential_type,
            "tenant_id": tenant_id,
            "channel": channel,
            "sender_id_hash": sha256(sender_id.encode()).hexdigest() if sender_id else "",
        }
        event_hash = sha256(
            json.dumps(event_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        authority_operator_audit_events.append({
            "event_id": f"authority-operator-access-{event_hash[:16]}",
            "event_hash": event_hash,
            **event_payload,
        })
        del authority_operator_audit_events[:-500]

    app = FastAPI(title="Mullu Gateway", version="1.0.0")
    bound_axiomworld_adapter = register_axiomworld_routes(app, adapter=axiomworld_adapter)

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": _redacted_request_validation_detail(exc),
                "governed": True,
                "error_code": "request_validation_failed",
            },
        )

    # G10.1 — install entry-point receipt middleware. Closes the
    # gap documented in docs/MAF_RECEIPT_COVERAGE.md §"Routes NOT
    # covered". Every webhook/authority POST now produces a
    # TransitionReceipt regardless of which handler runs.
    from gateway.receipt_middleware import install_gateway_receipt_middleware
    install_gateway_receipt_middleware(app, platform)

    event_log = WebhookEventLog(clock=_clock)
    orgos_case_event_log = build_orgos_case_event_log_from_env(clock=_clock)
    orgos_replay_page = orgos_case_event_log.list(limit=10000)
    orgos_kernel = (
        replay_orgos_kernel_from_events(orgos_replay_page.events)
        if orgos_replay_page.total
        else OrganizationKernel(departments=default_mullu_orgos_departments())
    )
    verifier = WebhookVerifier()
    capability_admission_gate = (
        capability_admission_gate_override
        if capability_admission_gate_override is not None
        else build_capability_admission_gate_from_env(clock=_clock)
    )
    mcp_gateway_import = build_mcp_gateway_import_from_env(clock=_clock)
    if mcp_gateway_import is not None:
        if capability_admission_gate is not None:
            raise ValueError("MCP capability manifest cannot be combined with configured capability admission")
        if mcp_capability_entries or mcp_authority_records is not None:
            raise ValueError("MCP capability manifest cannot be combined with explicit MCP overrides")
        capability_admission_gate = mcp_gateway_import.admission_gate
        mcp_capability_entries = mcp_gateway_import.entries
        mcp_authority_records = mcp_gateway_import.authority_records
    command_ledger = command_ledger_override
    if command_ledger is None:
        command_ledger = build_command_ledger_from_env(
            clock=_clock,
            capability_admission_gate=capability_admission_gate,
        )
    tenant_identity_store = build_tenant_identity_store_from_env(clock=_clock)
    authority_mesh_store = build_authority_obligation_mesh_store_from_env()
    authority_obligation_mesh = AuthorityObligationMesh(
        commands=command_ledger,
        clock=_clock,
        store=authority_mesh_store,
    )
    plan_ledger = build_capability_plan_ledger_from_env(clock=_clock)
    capability_dispatcher = build_capability_dispatcher_from_platform(platform)
    agentic_service_harness_read_model_source = AgenticServiceHarnessReadModelSource(
        runtime_producer=AgenticServiceHarnessRuntimeReadModelProducer()
    )
    if mcp_capability_entries and mcp_executor is not None:
        register_mcp_capabilities(
            capability_dispatcher,
            capabilities=mcp_capability_entries,
            executor=mcp_executor,
        )
    isolated_capability_executor = build_isolated_capability_executor_from_env()
    observability_recorder = GatewayObservabilityRecorder()
    federated_control_plane = FederatedControlPlane()
    goal_intake_preview_store = GoalIntakePreviewStore()
    router = GatewayRouter(
        platform=platform,
        command_ledger=command_ledger,
        tenant_identity_store=tenant_identity_store,
        authority_obligation_mesh=authority_obligation_mesh,
        plan_ledger=plan_ledger,
        capability_dispatcher=capability_dispatcher,
        defer_approved_execution=defer_approved_execution,
        environment=gateway_env,
        isolated_capability_executor=isolated_capability_executor,
        mcp_authority_records=mcp_authority_records,
        observability_recorder=observability_recorder,
    )
    session_mgr = SessionManager()

    # ── Channel Adapters (configured from env vars) ──

    whatsapp = None
    if os.environ.get("WHATSAPP_PHONE_NUMBER_ID"):
        if not os.environ.get("WHATSAPP_APP_SECRET"):
            _log.warning("WHATSAPP_APP_SECRET not set — signature verification will reject all requests")
        whatsapp = WhatsAppAdapter(
            phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
            access_token=os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
            verify_token=os.environ.get("WHATSAPP_VERIFY_TOKEN", ""),
            app_secret=os.environ.get("WHATSAPP_APP_SECRET", ""),
        )
        router.register_channel(whatsapp)

    telegram = None
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        telegram = TelegramAdapter(
            bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        )
        router.register_channel(telegram)

    slack = None
    if os.environ.get("SLACK_BOT_TOKEN"):
        if not os.environ.get("SLACK_SIGNING_SECRET"):
            _log.warning("SLACK_SIGNING_SECRET not set — signature verification will reject all requests")
        slack = SlackAdapter(
            bot_token=os.environ["SLACK_BOT_TOKEN"],
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
        )
        router.register_channel(slack)

    discord = None
    if os.environ.get("DISCORD_BOT_TOKEN"):
        if not os.environ.get("DISCORD_PUBLIC_KEY"):
            _log.warning("DISCORD_PUBLIC_KEY not set — signature verification will reject all requests")
        discord = DiscordAdapter(
            bot_token=os.environ["DISCORD_BOT_TOKEN"],
            public_key=os.environ.get("DISCORD_PUBLIC_KEY", ""),
        )
        router.register_channel(discord)

    web = WebChatAdapter()
    router.register_channel(web)

    sms = None
    if os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"):
        sms = SmsAdapter(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            sender=os.environ.get("TWILIO_SMS_SENDER", ""),
            webhook_url=os.environ.get("TWILIO_WEBHOOK_URL", ""),
        )
        router.register_channel(sms)

    teams = None
    if os.environ.get("MICROSOFT_TEAMS_ACCESS_TOKEN"):
        if not os.environ.get("MICROSOFT_TEAMS_SHARED_SECRET"):
            _log.warning("MICROSOFT_TEAMS_SHARED_SECRET not set — signature verification will reject all requests")
        teams = TeamsAdapter(
            access_token=os.environ["MICROSOFT_TEAMS_ACCESS_TOKEN"],
            shared_secret=os.environ.get("MICROSOFT_TEAMS_SHARED_SECRET", ""),
        )
        router.register_channel(teams)

    phone_channel = None
    if os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"):
        phone_channel = PhoneAdapter(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            caller_id=os.environ.get("TWILIO_VOICE_CALLER_ID", ""),
            webhook_url=os.environ.get("TWILIO_VOICE_WEBHOOK_URL", ""),
        )
        router.register_channel(phone_channel)

    # ── Register signature verifiers from env ──
    if os.environ.get("WHATSAPP_APP_SECRET"):
        verifier.register("whatsapp", ChannelVerifierConfig(
            channel="whatsapp", method=VerificationMethod.HMAC_SHA256,
            secret=os.environ["WHATSAPP_APP_SECRET"], signature_prefix="sha256=",
        ))
    if os.environ.get("SLACK_SIGNING_SECRET"):
        verifier.register("slack", ChannelVerifierConfig(
            channel="slack", method=VerificationMethod.HMAC_SHA256,
            secret=os.environ["SLACK_SIGNING_SECRET"], signature_prefix="v0=",
            replay_window_seconds=300.0,
        ))
    if os.environ.get("DISCORD_PUBLIC_KEY"):
        verifier.register("discord", ChannelVerifierConfig(
            channel="discord", method=VerificationMethod.ED25519,
            secret=os.environ["DISCORD_PUBLIC_KEY"],
        ))

    # ── Health ──

    @app.get("/health")
    def health():
        # Check dependency health
        deps = {}
        overall = "healthy"
        if platform is not None:
            try:
                components = getattr(platform, "bootstrap_components", {})
                if callable(getattr(components, "__call__", None)):
                    components = components()
                deps["platform_components"] = components
                if isinstance(components, dict):
                    for name, ok in components.items():
                        if not ok:
                            overall = "degraded"
            except Exception:
                overall = "degraded"

        # Check channel adapters
        channels_configured = []
        for ch_name in ["whatsapp", "telegram", "slack", "discord", "web", "sms", "teams", "phone"]:
            if ch_name in [a for a in router._channels]:
                channels_configured.append(ch_name)

        return {
            "status": overall,
            "gateway": router.summary(),
            "sessions": session_mgr.summary(),
            "event_log": event_log.summary(),
            "verifier": verifier.status(),
            "dependencies": deps,
            "channels_configured": channels_configured,
        }

    # ── WhatsApp Webhook ──

    @app.get("/webhook/whatsapp")
    def whatsapp_verify(request: Request):
        """WhatsApp webhook verification (GET)."""
        if whatsapp is None:
            raise HTTPException(503, detail="WhatsApp not configured")
        mode = request.query_params.get("hub.mode", "")
        token = request.query_params.get("hub.verify_token", "")
        challenge = request.query_params.get("hub.challenge", "")
        result = whatsapp.verify_webhook(mode, token, challenge)
        if result is None:
            raise HTTPException(403, detail="Verification failed")
        return PlainTextResponse(result)

    @app.post("/webhook/whatsapp")
    async def whatsapp_receive(request: Request):
        """WhatsApp webhook message receive (POST)."""
        if whatsapp is None:
            raise HTTPException(503, detail="WhatsApp not configured")
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not whatsapp.verify_signature(body, signature):
            raise HTTPException(403, detail="Invalid signature")
        import time as _time
        _t0 = _time.monotonic()
        payload = json.loads(body)
        msg = whatsapp.parse_message(payload)
        request_receipt = _gateway_request_receipt(
            channel="whatsapp",
            request=request,
            body=body,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="whatsapp", sender_id="", status="ignored",
                             body=body.decode("utf-8", errors="replace")[:200],
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        response = router.handle_message(msg)
        event_log.record(channel="whatsapp", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Telegram Webhook ──

    @app.post("/webhook/telegram")
    async def telegram_receive(request: Request):
        """Telegram Bot API webhook (POST)."""
        if telegram is None:
            raise HTTPException(503, detail="Telegram not configured")
        import time as _time
        _t0 = _time.monotonic()
        body_bytes = await request.body()
        # Verify Telegram secret token if configured (X-Telegram-Bot-Api-Secret-Token)
        if hasattr(telegram, "verify_signature"):
            secret_header = request.headers.get("x-telegram-bot-api-secret-token", "")
            if not telegram.verify_signature(body_bytes, secret_header):
                raise HTTPException(403, detail="Invalid Telegram signature")
        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        msg = telegram.parse_message(payload)
        request_receipt = _gateway_request_receipt(
            channel="telegram",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="telegram", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        response = router.handle_message(msg)
        event_log.record(channel="telegram", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Slack Events API ──

    @app.post("/webhook/slack")
    async def slack_receive(request: Request):
        """Slack Events API webhook (POST)."""
        if slack is None:
            raise HTTPException(503, detail="Slack not configured")
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        payload = json.loads(body_str)

        # URL verification challenge
        challenge = slack.handle_url_verification(payload)
        if challenge is not None:
            return JSONResponse({"challenge": challenge})

        # Verify signature
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        if not slack.verify_request(timestamp, body_str, signature):
            raise HTTPException(403, detail="Invalid signature")

        msg = slack.parse_message(payload)
        request_receipt = _gateway_request_receipt(
            channel="slack",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="slack", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        import time as _time
        _t0 = _time.monotonic()
        response = router.handle_message(msg)
        event_log.record(channel="slack", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Discord Interactions ──

    @app.post("/webhook/discord")
    async def discord_receive(request: Request):
        """Discord interaction webhook (POST)."""
        if discord is None:
            raise HTTPException(503, detail="Discord not configured")
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        payload = json.loads(body_str)

        # Verify interaction
        signature = request.headers.get("X-Signature-Ed25519", "")
        timestamp = request.headers.get("X-Signature-Timestamp", "")
        if not discord.verify_interaction(signature, timestamp, body_str):
            raise HTTPException(401, detail="Invalid interaction")

        # PING response (type 1)
        if payload.get("type") == 1:
            return JSONResponse({"type": 1})

        msg = discord.parse_interaction(payload)
        request_receipt = _gateway_request_receipt(
            channel="discord",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="discord", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        import time as _time
        _t0 = _time.monotonic()
        response = router.handle_message(msg)
        # Discord interaction response format
        event_log.record(channel="discord", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({
            "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
            "data": {"content": response.body},
            "request_receipt": request_receipt,
        })

    # ── Web Chat ──

    @app.post("/webhook/web")
    async def web_receive(request: Request):
        """Web chat message endpoint (POST)."""
        body = await request.body()
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        session_token = request.headers.get("X-Session-Token", "")
        if not session_token or len(session_token) > 512:
            raise HTTPException(401, detail="Missing or invalid session token")
        msg = web.parse_message(payload, session_token=session_token)
        if msg is None:
            raise HTTPException(400, detail="Invalid message")
        request_receipt = _gateway_request_receipt(
            channel="web",
            request=request,
            body=body,
            message=msg,
        )
        response = router.handle_message(msg)
        return JSONResponse({
            "status": "ok",
            "message_id": response.message_id,
            "body": response.body,
            "governed": response.governed,
            "request_receipt": request_receipt,
            "metadata": response.metadata,
        })

    # ── Twilio SMS Webhook ──

    @app.post("/webhook/sms")
    async def sms_receive(request: Request):
        """Twilio Programmable Messaging inbound webhook (POST, form-encoded)."""
        if sms is None:
            raise HTTPException(503, detail="SMS not configured")
        import time as _time
        import urllib.parse as _urllib_parse
        _t0 = _time.monotonic()
        body_bytes = await request.body()
        try:
            params = {
                key: values[0]
                for key, values in _urllib_parse.parse_qs(
                    body_bytes.decode("utf-8"), keep_blank_values=True,
                ).items()
                if values
            }
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid form payload")
        signature = request.headers.get("X-Twilio-Signature", "")
        canonical_url = os.environ.get("TWILIO_WEBHOOK_URL", "") or str(request.url)
        if not sms.verify_signature(canonical_url, params, signature):
            raise HTTPException(403, detail="Invalid signature")
        msg = sms.parse_message(params)
        request_receipt = _gateway_request_receipt(
            channel="sms",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="sms", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        response = router.handle_message(msg)
        event_log.record(channel="sms", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Microsoft Teams Webhook ──

    @app.post("/webhook/teams")
    async def teams_receive(request: Request):
        """Microsoft Teams Bot Framework inbound webhook (POST)."""
        if teams is None:
            raise HTTPException(503, detail="Teams not configured")
        import time as _time
        _t0 = _time.monotonic()
        body_bytes = await request.body()
        signature = request.headers.get("X-Mullu-Teams-Signature", "")
        if not teams.verify_signature(body_bytes, signature):
            raise HTTPException(403, detail="Invalid signature")
        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        msg = teams.parse_message(payload)
        request_receipt = _gateway_request_receipt(
            channel="teams",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="teams", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        response = router.handle_message(msg)
        event_log.record(channel="teams", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Twilio Voice Webhook ──

    @app.post("/webhook/phone")
    async def phone_receive(request: Request):
        """Twilio Voice inbound webhook (POST, form-encoded)."""
        if phone_channel is None:
            raise HTTPException(503, detail="Phone not configured")
        import time as _time
        import urllib.parse as _urllib_parse
        _t0 = _time.monotonic()
        body_bytes = await request.body()
        try:
            params = {
                key: values[0]
                for key, values in _urllib_parse.parse_qs(
                    body_bytes.decode("utf-8"), keep_blank_values=True,
                ).items()
                if values
            }
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid form payload")
        signature = request.headers.get("X-Twilio-Signature", "")
        canonical_url = os.environ.get("TWILIO_VOICE_WEBHOOK_URL", "") or str(request.url)
        if not phone_channel.verify_signature(canonical_url, params, signature):
            raise HTTPException(403, detail="Invalid signature")
        msg = phone_channel.parse_message(params)
        request_receipt = _gateway_request_receipt(
            channel="phone",
            request=request,
            body=body_bytes,
            message=msg,
        )
        if msg is None:
            event_log.record(channel="phone", sender_id="", status="ignored",
                             headers=dict(request.headers),
                             outcome_detail=request_receipt["receipt_id"])
            return JSONResponse({"status": "ignored", "request_receipt": request_receipt})
        response = router.handle_message(msg)
        event_log.record(channel="phone", sender_id=msg.sender_id,
                         message_id=msg.message_id, status="processed",
                         body=msg.body[:200], headers=dict(request.headers),
                         outcome_detail=request_receipt["receipt_id"],
                         processing_ms=(_time.monotonic() - _t0) * 1000)
        return JSONResponse({"status": "ok", "response": response.body, "request_receipt": request_receipt})

    # ── Approval Callback ──

    @app.post("/webhook/approve/{request_id}")
    async def approve_request(request_id: str, request: Request):
        """Approve a pending governance request."""
        import json
        if not _approval_webhook_authorized(request):
            raise HTTPException(403, detail="Approval callback not authorized")
        try:
            payload = json.loads(await request.body())
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(400, detail="Invalid JSON payload")
        approved = payload.get("approved", False)
        resolver_channel = str(payload.get("resolver_channel", "")).strip()
        resolver_sender_id = str(payload.get("resolver_sender_id", "")).strip()
        if not resolver_channel or not resolver_sender_id:
            raise HTTPException(400, detail="resolver_channel and resolver_sender_id are required")
        result = router.handle_external_approval_callback(
            request_id,
            approved=approved,
            resolver_channel=resolver_channel,
            resolver_sender_id=resolver_sender_id,
        )
        if result is None:
            raise HTTPException(404, detail="Request not found or already resolved")
        if result.metadata.get("error") in {"approval_context_denied", "approval_strength_denied"}:
            raise HTTPException(403, detail=result.metadata)
        return JSONResponse({
            "status": "resolved",
            "body": result.body,
            "governed": result.governed,
            "metadata": result.metadata,
        })

    # ── Gateway Status ──

    @app.get("/gateway/status")
    def gateway_status():
        return {
            "router": router.summary(),
            "sessions": session_mgr.summary(),
            "governed": True,
        }

    @app.get("/api/v1/harness/status")
    def agentic_service_harness_status():
        return build_agentic_service_harness_status_projection(
            read_model_source=agentic_service_harness_read_model_source,
        )

    @app.get("/api/v1/personal-assistant/skills")
    def personal_assistant_skill_read_model():
        registry = load_default_skill_registry()
        return {
            "registry": registry.read_model(),
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "governed": True,
        }

    @app.get("/api/v1/console/personal-assistant")
    def personal_assistant_console_read_model():
        return build_personal_assistant_console_read_model(generated_at=_clock())

    @app.get("/api/v1/console/personal-assistant/view", response_class=HTMLResponse)
    def personal_assistant_console_view():
        return HTMLResponse(
            render_personal_assistant_console_html(
                build_personal_assistant_console_read_model(generated_at=_clock())
            )
        )

    @app.post("/api/v1/personal-assistant/requests/preview")
    def preview_personal_assistant_request(req: GatewayPersonalAssistantPreviewRequest):
        try:
            now = req.submitted_at or _clock()
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                now,
                req.interface,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=now,
                interface=req.interface,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            clarification_bundle = build_clarification_requests(
                intent,
                thread_id=req.thread_id,
                requested_from_id=req.requested_from_id,
                requested_at=now,
            )
            envelope = build_personal_assistant_preview_plan(
                intent,
                plan_id=_gateway_personal_assistant_plan_id(request_id),
                created_at=now,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant preview",
                    "error_code": "invalid_personal_assistant_preview",
                    "governed": True,
                },
            ) from exc

        response: dict[str, Any] = {
            **envelope.as_dict(),
            "clarification_bundle": {
                "request_id": clarification_bundle.request_id,
                "clarifications": [
                    clarification.to_json_dict()
                    for clarification in clarification_bundle.clarifications
                ],
                "clarification_count": len(clarification_bundle.clarifications),
            },
            "outcome": _gateway_personal_assistant_outcome(
                envelope.plan,
                clarification_bundle.empty,
            ),
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "external_send_allowed": False,
                "connector_mutation_allowed": False,
                "memory_write_allowed": False,
                "deployment_mutation_allowed": False,
            },
        }
        if req.include_console_read_model:
            response["console_read_model"] = build_personal_assistant_console_read_model(
                generated_at=now,
                recent_requests=(
                    {
                        "request_id": envelope.request["request_id"],
                        "summary": envelope.request["user_goal"],
                        "status": envelope.plan["mode"],
                    },
                ),
                receipts=(envelope.receipt,),
            )
        return response

    @app.post("/api/v1/personal-assistant/read-only/inbox/preview")
    def preview_personal_assistant_read_only_inbox(
        req: GatewayPersonalAssistantReadOnlyInboxPreviewRequest,
    ):
        try:
            generated_at = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or generated_at
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                req.interface,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=req.interface,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = summarize_inbox_read_only(
                intent,
                tuple(_pydantic_payload(message) for message in req.messages),
                generated_at=generated_at,
            ).as_dict()
            projection_set = _gateway_personal_assistant_read_only_projection_set(
                projection=projection,
                generated_at=generated_at,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant read-only inbox preview",
                    "error_code": "invalid_personal_assistant_read_only_inbox_preview",
                    "governed": True,
                },
            ) from exc

        receipt = dict(projection["receipt"])
        response: dict[str, Any] = {
            "read_only_projection": projection_set,
            "receipt": receipt,
            "outcome": "SolvedVerified",
            "governed": True,
            "execution_allowed": False,
            "effect_boundary": projection_set["effect_boundary"],
        }
        if req.include_console_read_model:
            response["console_read_model"] = build_personal_assistant_console_read_model(
                generated_at=generated_at,
                recent_requests=(
                    {
                        "request_id": projection["request_id"],
                        "summary": req.user_request,
                        "status": "read_only_preview",
                    },
                ),
                receipts=(receipt,),
            )
        return response

    @app.post("/api/v1/personal-assistant/read-only/calendar/preview")
    def preview_personal_assistant_read_only_calendar(
        req: GatewayPersonalAssistantReadOnlyCalendarPreviewRequest,
    ):
        try:
            generated_at = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or generated_at
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                req.interface,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=req.interface,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = summarize_calendar_day_read_only(
                intent,
                tuple(_pydantic_payload(event) for event in req.events),
                generated_at=generated_at,
            ).as_dict()
            projection_set = _gateway_personal_assistant_read_only_projection_set(
                projection=projection,
                generated_at=generated_at,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant read-only calendar preview",
                    "error_code": "invalid_personal_assistant_read_only_calendar_preview",
                    "governed": True,
                },
            ) from exc

        receipt = dict(projection["receipt"])
        response: dict[str, Any] = {
            "read_only_projection": projection_set,
            "receipt": receipt,
            "outcome": "SolvedVerified",
            "governed": True,
            "execution_allowed": False,
            "effect_boundary": projection_set["effect_boundary"],
        }
        if req.include_console_read_model:
            response["console_read_model"] = build_personal_assistant_console_read_model(
                generated_at=generated_at,
                recent_requests=(
                    {
                        "request_id": projection["request_id"],
                        "summary": req.user_request,
                        "status": "read_only_preview",
                    },
                ),
                receipts=(receipt,),
            )
        return response

    @app.post("/api/v1/personal-assistant/drafts/email/preview")
    def preview_personal_assistant_email_draft(
        req: GatewayPersonalAssistantEmailDraftPreviewRequest,
    ):
        try:
            generated_at = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or generated_at
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                req.interface,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=req.interface,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = draft_email_response(
                intent,
                _pydantic_payload(req.draft_input),
                generated_at=generated_at,
            ).as_dict()
            draft_set = _gateway_personal_assistant_draft_projection_set(
                projection=projection,
                generated_at=generated_at,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant email draft preview",
                    "error_code": "invalid_personal_assistant_email_draft_preview",
                    "governed": True,
                },
            ) from exc

        receipt = dict(projection["receipt"])
        response: dict[str, Any] = {
            "draft_projection": draft_set,
            "receipt": receipt,
            "outcome": "SolvedVerified",
            "governed": True,
            "execution_allowed": False,
            "effect_boundary": draft_set["effect_boundary"],
            "approval_boundary": draft_set["approval_boundary"],
        }
        if req.include_console_read_model:
            response["console_read_model"] = build_personal_assistant_console_read_model(
                generated_at=generated_at,
                recent_requests=(
                    {
                        "request_id": projection["request_id"],
                        "summary": req.user_request,
                        "status": "draft_preview",
                    },
                ),
                receipts=(receipt,),
            )
        return response

    @app.post("/api/v1/personal-assistant/drafts/calendar-event/preview")
    def preview_personal_assistant_calendar_event_draft(
        req: GatewayPersonalAssistantCalendarEventDraftPreviewRequest,
    ):
        try:
            generated_at = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or generated_at
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                req.interface,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=req.interface,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = draft_calendar_event(
                intent,
                _pydantic_payload(req.draft_input),
                generated_at=generated_at,
            ).as_dict()
            draft_set = _gateway_personal_assistant_draft_projection_set(
                projection=projection,
                generated_at=generated_at,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant calendar event draft preview",
                    "error_code": "invalid_personal_assistant_calendar_event_draft_preview",
                    "governed": True,
                },
            ) from exc

        receipt = dict(projection["receipt"])
        return {
            "draft_projection": draft_set,
            "receipt": receipt,
            "outcome": "SolvedVerified",
            "governed": True,
            "execution_allowed": False,
            "effect_boundary": draft_set["effect_boundary"],
            "approval_boundary": draft_set["approval_boundary"],
        }

    @app.post("/api/v1/personal-assistant/drafts/task/preview")
    def preview_personal_assistant_task_draft(
        req: GatewayPersonalAssistantTaskDraftPreviewRequest,
    ):
        try:
            generated_at = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or generated_at
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                req.interface,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=req.interface,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = draft_task(
                intent,
                _pydantic_payload(req.draft_input),
                generated_at=generated_at,
            ).as_dict()
            draft_set = _gateway_personal_assistant_draft_projection_set(
                projection=projection,
                generated_at=generated_at,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant task draft preview",
                    "error_code": "invalid_personal_assistant_task_draft_preview",
                    "governed": True,
                },
            ) from exc

        receipt = dict(projection["receipt"])
        return {
            "draft_projection": draft_set,
            "receipt": receipt,
            "outcome": "SolvedVerified",
            "governed": True,
            "execution_allowed": False,
            "effect_boundary": draft_set["effect_boundary"],
            "approval_boundary": draft_set["approval_boundary"],
        }

    @app.get("/api/v1/personal-assistant/approval-queue")
    def personal_assistant_approval_queue_read_model():
        read_model = PersonalAssistantApprovalQueue().read_model()
        return {
            "approval_queue": read_model,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "governed": True,
        }

    @app.post("/api/v1/personal-assistant/approval-proposals/preview")
    def preview_personal_assistant_approval_proposal(req: GatewayPersonalAssistantApprovalProposalPreviewRequest):
        try:
            now = req.submitted_at or _clock()
            if req.plan:
                plan_payload = dict(req.plan)
                envelope_payload: dict[str, Any] = {
                    "request": {},
                    "plan": plan_payload,
                    "receipt": {},
                    "governed": True,
                    "execution_allowed": False,
                }
                clarification_payload = {
                    "request_id": str(plan_payload.get("request_id", "")),
                    "clarifications": [],
                    "clarification_count": 0,
                }
            else:
                request_id = req.request_id or _gateway_personal_assistant_request_id(
                    req.user_request,
                    now,
                    req.interface,
                )
                intent = interpret_user_request(
                    req.user_request,
                    request_id=request_id,
                    submitted_at=now,
                    interface=req.interface,
                    connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
                )
                clarification_bundle = build_clarification_requests(
                    intent,
                    thread_id=req.thread_id,
                    requested_from_id=req.requested_from_id,
                    requested_at=now,
                )
                envelope = build_personal_assistant_preview_plan(
                    intent,
                    plan_id=_gateway_personal_assistant_plan_id(request_id),
                    created_at=now,
                )
                plan_payload = dict(envelope.plan)
                envelope_payload = envelope.as_dict()
                clarification_payload = {
                    "request_id": clarification_bundle.request_id,
                    "clarifications": [
                        clarification.to_json_dict()
                        for clarification in clarification_bundle.clarifications
                    ],
                    "clarification_count": len(clarification_bundle.clarifications),
                }
            proposal = prepare_approval_proposal_from_plan(
                plan_payload,
                approval_scope=req.approval_scope,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant approval proposal preview",
                    "error_code": "invalid_personal_assistant_approval_proposal_preview",
                    "governed": True,
                },
            ) from exc

        proposal_payload = proposal.as_dict()
        review_packet = proposal.as_review_packet(
            generated_at=now,
            reviewer_ref=req.requested_from_id,
        )
        response: dict[str, Any] = {
            **envelope_payload,
            "approval_proposal": proposal_payload,
            "approval_review_packet": review_packet,
            "approval_queue": PersonalAssistantApprovalQueue().read_model(),
            "clarification_bundle": clarification_payload,
            "outcome": "AwaitingEvidence",
            "effect_boundary": {
                "execution_allowed": False,
                "approval_is_execution": False,
                "approval_enqueued": False,
                "live_connector_execution_allowed": False,
                "external_send_allowed": False,
                "connector_mutation_allowed": False,
                "memory_write_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }
        if req.include_console_read_model:
            request_row = {
                "request_id": str(plan_payload.get("request_id", "")),
                "summary": str(plan_payload.get("goal", req.user_request)),
                "status": str(plan_payload.get("mode", "preview")),
            }
            response["console_read_model"] = build_personal_assistant_console_read_model(
                generated_at=now,
                recent_requests=(request_row,),
                receipts=(envelope_payload["receipt"],) if envelope_payload.get("receipt") else (),
                approval_proposals=(proposal_payload,),
            )
        return response

    @app.post("/api/v1/personal-assistant/approval-proposals/from-draft/preview")
    def preview_personal_assistant_draft_approval_proposal(
        req: GatewayPersonalAssistantDraftApprovalPreviewRequest,
    ):
        try:
            now = req.created_at or _clock()
            request_id = req.request_id
            plan_id = req.plan_id or _gateway_personal_assistant_plan_id(request_id)
            proposal = _gateway_personal_assistant_draft_approval_proposal(
                request_id=request_id,
                plan_id=plan_id,
                approval_scope=req.approval_scope,
                draft=req.draft,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant draft approval proposal preview",
                    "error_code": "invalid_personal_assistant_draft_approval_proposal_preview",
                    "governed": True,
                },
            ) from exc

        proposal_payload = proposal.as_dict()
        review_packet = proposal.as_review_packet(
            generated_at=now,
            reviewer_ref=req.approver_ref,
        )
        response: dict[str, Any] = {
            "approval_proposal": proposal_payload,
            "approval_review_packet": review_packet,
            "approval_queue": PersonalAssistantApprovalQueue().read_model(),
            "draft_ref": req.draft.draft_ref,
            "source_draft": {
                "draft_ref": req.draft.draft_ref,
                "draft_type": req.draft.draft_type,
                "draft_skill_id": req.draft.draft_skill_id,
            },
            "outcome": "AwaitingEvidence",
            "effect_boundary": {
                "execution_allowed": False,
                "approval_is_execution": False,
                "approval_enqueued": False,
                "live_connector_execution_allowed": False,
                "external_send_allowed": False,
                "connector_mutation_allowed": False,
                "memory_write_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }
        if req.include_console_read_model:
            response["console_read_model"] = build_personal_assistant_console_read_model(
                generated_at=now,
                recent_requests=(
                    {
                        "request_id": request_id,
                        "summary": req.draft.summary,
                        "status": "draft_approval_preview",
                    },
                ),
                approval_proposals=(proposal_payload,),
            )
        return response

    @app.post("/api/v1/personal-assistant/send-write/eligibility/preview")
    def preview_personal_assistant_send_write_eligibility(
        req: GatewayPersonalAssistantSendWriteEligibilityPreviewRequest,
    ):
        try:
            now = req.created_at or _clock()
            request_id = req.request_id
            plan_id = req.plan_id or _gateway_personal_assistant_plan_id(request_id)
            response = _gateway_personal_assistant_send_write_eligibility_preflight(
                request_id=request_id,
                plan_id=plan_id,
                approval_scope=req.approval_scope,
                approver_ref=req.approver_ref,
                created_at=now,
                draft=req.draft,
                approval_proposal_ref=req.approval_proposal_ref,
                approval_decision=req.approval_decision,
                approval_decision_ref=req.approval_decision_ref,
                approval_receipt_ref=req.approval_receipt_ref,
                connector_boundary_ref=req.connector_boundary_ref,
                live_probe_receipt_ref=req.live_probe_receipt_ref,
                preparation_receipt_ref=req.preparation_receipt_ref,
                post_action_receipt_plan_ref=req.post_action_receipt_plan_ref,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant send/write eligibility preview",
                    "error_code": "invalid_personal_assistant_send_write_eligibility_preview",
                    "governed": True,
                },
            ) from exc

        if req.include_console_read_model:
            response["console_read_model"] = build_personal_assistant_console_read_model(
                generated_at=now,
                recent_requests=(
                    {
                        "request_id": request_id,
                        "summary": req.draft.summary,
                        "status": "send_write_eligibility_preview",
                    },
                ),
                receipts=(response["receipt"],),
                approval_proposals=(response["approval_proposal"],),
            )
        return response

    @app.post("/api/v1/personal-assistant/approval-queue/preview")
    def preview_personal_assistant_approval_queue(req: GatewayPersonalAssistantApprovalPreviewRequest):
        try:
            now = req.created_at or _clock()
            queue = PersonalAssistantApprovalQueue()
            record = queue.enqueue(
                request_id=req.request_id,
                plan_id=req.plan_id,
                approver_ref=req.approver_ref,
                approval_scope=req.approval_scope,
                proposed_actions=tuple(
                    ApprovalProposedAction.from_mapping(_pydantic_payload(action))
                    for action in req.proposed_actions
                ),
                forbidden_without_approval=tuple(req.forbidden_without_approval),
                evidence_refs=tuple(req.evidence_refs),
                created_at=now,
                approval_id=req.approval_id or None,
            )
            if req.decision:
                decision = ApprovalDecision.coerce(req.decision)
                record = queue.record_decision(
                    record.approval_id,
                    decision=decision,
                    reason_codes=tuple(req.reason_codes) or (f"operator_{decision.value}_preview",),
                    decided_at=req.decided_at or now,
                    decision_evidence_ref=req.decision_evidence_ref,
                    revision_request=req.revision_request,
                )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant approval queue preview",
                    "error_code": "invalid_personal_assistant_approval_queue_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "approval": record.as_dict(),
            "approval_queue": queue.read_model(),
            "receipt": dict(record.latest_receipt),
            "outcome": str(record.latest_receipt.get("outcome", "AwaitingEvidence")),
            "effect_boundary": {
                "execution_allowed": False,
                "approval_is_execution": False,
                "live_connector_execution_allowed": False,
                "external_send_allowed": False,
                "connector_mutation_allowed": False,
                "memory_write_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.get("/api/v1/personal-assistant/memory-observations")
    def personal_assistant_memory_observations_read_model():
        read_model = PersonalAssistantMemoryObservationLedger().read_model()
        return {
            "memory_read_model": read_model,
            "execution_allowed": False,
            "live_memory_write_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "raw_private_payload_storage_allowed": False,
            "secret_value_storage_allowed": False,
            "governed": True,
        }

    @app.post("/api/v1/personal-assistant/memory-observations/preview")
    def preview_personal_assistant_memory_observation(req: GatewayPersonalAssistantMemoryPreviewRequest):
        try:
            now = req.observed_at or _clock()
            candidate = prepare_memory_observation(
                request_id=req.request_id,
                memory_observation_id=req.memory_observation_id,
                memory_type=req.memory_type,
                claim=req.claim,
                source=MemoryObservationSource.from_mapping(_pydantic_payload(req.source)),
                confidence=req.confidence,
                scope=req.scope,
                mutable=req.mutable,
                receipt_id=req.receipt_id,
                evidence_refs=tuple(req.evidence_refs),
                observed_at=now,
                sensitivity=req.sensitivity,
                retention_policy=req.retention_policy,
                nested_mind_status=req.nested_mind_status,
                metadata=req.metadata,
            )
            ledger = PersonalAssistantMemoryObservationLedger()
            ledger.append(candidate)
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant memory observation preview",
                    "error_code": "invalid_personal_assistant_memory_observation_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "memory_observation": candidate.as_dict(),
            "memory_read_model": ledger.read_model(),
            "receipt": dict(candidate.receipt),
            "outcome": str(candidate.receipt.get("outcome", "SolvedVerified")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_memory_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
                "raw_private_payload_storage_allowed": False,
                "secret_value_storage_allowed": False,
                "connector_mutation_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.post("/api/v1/personal-assistant/memory-observations/review/preview")
    def preview_personal_assistant_memory_review(req: GatewayPersonalAssistantMemoryReviewPreviewRequest):
        try:
            now = req.reviewed_at or _clock()
            candidate_request = req.candidate
            candidate_observed_at = candidate_request.observed_at or now
            candidate = prepare_memory_observation(
                request_id=candidate_request.request_id,
                memory_observation_id=candidate_request.memory_observation_id,
                memory_type=candidate_request.memory_type,
                claim=candidate_request.claim,
                source=MemoryObservationSource.from_mapping(_pydantic_payload(candidate_request.source)),
                confidence=candidate_request.confidence,
                scope=candidate_request.scope,
                mutable=candidate_request.mutable,
                receipt_id=candidate_request.receipt_id,
                evidence_refs=tuple(candidate_request.evidence_refs),
                observed_at=candidate_observed_at,
                sensitivity=candidate_request.sensitivity,
                retention_policy=candidate_request.retention_policy,
                nested_mind_status=candidate_request.nested_mind_status,
                metadata=candidate_request.metadata,
            )
            decision = MemoryReviewDecision.coerce(req.decision)
            review = review_memory_observation_candidate(
                candidate=candidate,
                review_id=req.review_id,
                decision=decision,
                reviewer_ref=req.reviewer_ref,
                reason_codes=tuple(req.reason_codes) or (f"operator_{decision.value}_preview",),
                reviewed_at=now,
                review_evidence_ref=req.review_evidence_ref,
                revision_request=req.revision_request,
                deferred_until=req.deferred_until,
                expires_at=req.expires_at,
                metadata=req.metadata,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant memory review preview",
                    "error_code": "invalid_personal_assistant_memory_review_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "memory_review": review.as_dict(),
            "receipt": dict(review.receipt),
            "outcome": str(review.receipt.get("outcome", "SolvedVerified")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_memory_write_allowed": False,
                "memory_admission_allowed": False,
                "nested_mind_live_activation_allowed": False,
                "raw_private_payload_storage_allowed": False,
                "secret_value_storage_allowed": False,
                "connector_mutation_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.post("/api/v1/personal-assistant/teamops/shared-inbox/plan/preview")
    def preview_personal_assistant_teamops_shared_inbox(req: GatewayPersonalAssistantTeamOpsPreviewRequest):
        try:
            now = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or now
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                RequestInterface.API_ROUTE.value,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=RequestInterface.API_ROUTE,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = plan_teamops_shared_inbox(
                intent,
                generated_at=now,
                environment=req.environment,
                github_secret_names=set(req.github_secret_names),
                operator_approval_ref=req.operator_approval_ref,
                repository=req.repository,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant TeamOps shared inbox preview",
                    "error_code": "invalid_personal_assistant_teamops_shared_inbox_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "teamops_projection": projection.as_dict(),
            "receipt": dict(projection.receipt),
            "outcome": str(projection.receipt.get("outcome", "SolvedVerified")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "live_probe_execution_allowed": False,
                "mailbox_read_allowed": False,
                "mailbox_mutation_allowed": False,
                "draft_creation_allowed": False,
                "external_send_allowed": False,
                "connector_mutation_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.post("/api/v1/personal-assistant/teamops/gmail/live-probe/preview")
    def preview_personal_assistant_teamops_gmail_live_probe(
        req: GatewayPersonalAssistantTeamOpsLiveProbePreviewRequest,
    ):
        try:
            now = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or now
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                RequestInterface.API_ROUTE.value,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=RequestInterface.API_ROUTE,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = preview_teamops_gmail_live_probe(
                intent,
                generated_at=now,
                environment=req.environment,
                github_secret_names=set(req.github_secret_names),
                operator_approval_ref=req.operator_approval_ref,
                repository=req.repository,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant TeamOps Gmail live probe preview",
                    "error_code": "invalid_personal_assistant_teamops_gmail_live_probe_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "teamops_gmail_live_probe": projection.as_dict(),
            "receipt": dict(projection.receipt),
            "outcome": str(projection.receipt.get("outcome", "AwaitingEvidence")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "external_provider_call_allowed": False,
                "full_mailbox_read_allowed": False,
                "message_body_read_allowed": False,
                "message_search_allowed": False,
                "mailbox_mutation_allowed": False,
                "draft_creation_allowed": False,
                "external_send_allowed": False,
                "delete_allowed": False,
                "archive_allowed": False,
                "connector_mutation_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.post("/api/v1/personal-assistant/github-codex/review/preview")
    def preview_personal_assistant_github_codex_review(req: GatewayPersonalAssistantGitHubCodexPreviewRequest):
        try:
            now = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or now
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                RequestInterface.API_ROUTE.value,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=RequestInterface.API_ROUTE,
                connector_refs=tuple(_pydantic_payload(connector) for connector in req.connector_refs),
            )
            projection = plan_github_codex_review(
                intent,
                generated_at=now,
                repository_ref=req.repository_ref,
                pull_request_ref=req.pull_request_ref,
                change_summary=req.change_summary,
                changed_files=tuple(req.changed_files),
                risk_notes=tuple(req.risk_notes),
                blocking_questions=tuple(req.blocking_questions),
                evidence_refs=tuple(req.evidence_refs),
                requested_instruction_goal=req.requested_instruction_goal,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant GitHub/Codex review preview",
                    "error_code": "invalid_personal_assistant_github_codex_review_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "github_codex_projection": projection.as_dict(),
            "receipt": dict(projection.receipt),
            "outcome": str(projection.receipt.get("outcome", "SolvedVerified")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "github_call_allowed": False,
                "repository_read_allowed": False,
                "repository_mutation_allowed": False,
                "pull_request_mutation_allowed": False,
                "branch_push_allowed": False,
                "issue_creation_allowed": False,
                "review_submission_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.post("/api/v1/personal-assistant/research/source-compare/preview")
    def preview_personal_assistant_research_source_compare(req: GatewayPersonalAssistantResearchPreviewRequest):
        try:
            now = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or now
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                RequestInterface.API_ROUTE.value,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=RequestInterface.API_ROUTE,
            )
            projection = plan_research_source_compare(
                intent,
                generated_at=now,
                research_question=req.research_question,
                source_summaries=tuple(_pydantic_payload(source) for source in req.source_summaries),
                citation_refs=tuple(req.citation_refs),
                freshness_notes=tuple(req.freshness_notes),
                conflict_notes=tuple(req.conflict_notes),
                blocking_questions=tuple(req.blocking_questions),
                evidence_refs=tuple(req.evidence_refs),
                requested_synthesis_goal=req.requested_synthesis_goal,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant research source-compare preview",
                    "error_code": "invalid_personal_assistant_research_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "research_projection": projection.as_dict(),
            "receipt": dict(projection.receipt),
            "outcome": str(projection.receipt.get("outcome", "SolvedVerified")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "web_search_allowed": False,
                "web_search_performed": False,
                "source_contact_allowed": False,
                "external_submission_allowed": False,
                "public_post_allowed": False,
                "paid_subscription_allowed": False,
                "system_of_record_write_allowed": False,
                "memory_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.post("/api/v1/personal-assistant/math/reasoning/preview")
    def preview_personal_assistant_math_reasoning(req: GatewayPersonalAssistantMathPreviewRequest):
        try:
            now = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or now
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                RequestInterface.API_ROUTE.value,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=RequestInterface.API_ROUTE,
            )
            projection = plan_math_reasoning(
                intent,
                generated_at=now,
                problem_statement=req.problem_statement,
                known_values=tuple(_pydantic_payload(value) for value in req.known_values),
                assumptions=tuple(req.assumptions),
                constraints=tuple(req.constraints),
                evidence_refs=tuple(req.evidence_refs),
                requested_result=req.requested_result,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant math reasoning preview",
                    "error_code": "invalid_personal_assistant_math_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "math_projection": projection.as_dict(),
            "receipt": dict(projection.receipt),
            "outcome": str(projection.receipt.get("outcome", "SolvedVerified")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "money_movement_allowed": False,
                "paid_subscription_allowed": False,
                "system_of_record_write_allowed": False,
                "connector_mutation_allowed": False,
                "external_submission_allowed": False,
                "public_post_allowed": False,
                "deployment_allowed": False,
                "memory_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.post("/api/v1/personal-assistant/planning/schedule/preview")
    def preview_personal_assistant_schedule_planning(req: GatewayPersonalAssistantPlanningPreviewRequest):
        try:
            now = req.generated_at or req.submitted_at or _clock()
            submitted_at = req.submitted_at or now
            request_id = req.request_id or _gateway_personal_assistant_request_id(
                req.user_request,
                submitted_at,
                RequestInterface.API_ROUTE.value,
            )
            intent = interpret_user_request(
                req.user_request,
                request_id=request_id,
                submitted_at=submitted_at,
                interface=RequestInterface.API_ROUTE,
            )
            projection = plan_schedule_optimization(
                intent,
                generated_at=now,
                objective=req.objective,
                time_windows=tuple(_pydantic_payload(window) for window in req.time_windows),
                work_items=tuple(_pydantic_payload(item) for item in req.work_items),
                assumptions=tuple(req.assumptions),
                constraints=tuple(req.constraints),
                evidence_refs=tuple(req.evidence_refs),
                requested_result=req.requested_result,
            )
        except (PersonalAssistantInvariantError, ValueError) as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid personal assistant schedule planning preview",
                    "error_code": "invalid_personal_assistant_planning_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "planning_projection": projection.as_dict(),
            "receipt": dict(projection.receipt),
            "outcome": str(projection.receipt.get("outcome", "SolvedVerified")),
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "calendar_write_allowed": False,
                "task_write_allowed": False,
                "invite_allowed": False,
                "message_person_allowed": False,
                "system_of_record_write_allowed": False,
                "connector_mutation_allowed": False,
                "external_submission_allowed": False,
                "public_post_allowed": False,
                "money_movement_allowed": False,
                "paid_subscription_allowed": False,
                "deployment_allowed": False,
                "memory_write_allowed": False,
                "nested_mind_live_activation_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.get("/gateway/witness")
    def gateway_witness():
        return router.runtime_witness(
            environment=gateway_env,
            signature_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            signing_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )

    @app.get("/runtime/witness")
    def runtime_witness():
        return router.runtime_witness(
            environment=gateway_env,
            signature_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            signing_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )

    @app.get("/runtime/conformance")
    def runtime_conformance():
        certificate = issue_conformance_certificate(
            router=router,
            command_ledger=command_ledger,
            authority_obligation_mesh=authority_obligation_mesh,
            capability_admission_gate=capability_admission_gate,
            plan_ledger=plan_ledger,
            environment=gateway_env,
            signing_secret=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", "local-runtime-conformance-secret"),
            signature_key_id=os.environ.get("MULLU_RUNTIME_CONFORMANCE_KEY_ID", "runtime-conformance-local"),
            runtime_witness_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            runtime_witness_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )
        return certificate.to_json_dict()

    @app.get("/governed-operations/read-model")
    def governed_operations_read_model():
        conformance = issue_conformance_certificate(
            router=router,
            command_ledger=command_ledger,
            authority_obligation_mesh=authority_obligation_mesh,
            capability_admission_gate=capability_admission_gate,
            plan_ledger=plan_ledger,
            environment=gateway_env,
            signing_secret=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", "local-runtime-conformance-secret"),
            signature_key_id=os.environ.get("MULLU_RUNTIME_CONFORMANCE_KEY_ID", "runtime-conformance-local"),
            runtime_witness_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            runtime_witness_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        ).to_json_dict()
        deployment = _build_deployment_witness()
        authority_witness = asdict(authority_obligation_mesh.responsibility_witness())
        latest_anchors = command_ledger.list_anchors(limit=1)
        latest_anchor_id = latest_anchors[0].anchor_id if latest_anchors else ""

        evidence_refs = _governed_operations_evidence_refs(
            conformance=conformance,
            deployment=deployment,
            authority_witness=authority_witness,
            latest_anchor_id=latest_anchor_id,
        )
        receipts = ()
        if evidence_refs:
            receipts = (
                receipt_from_projection(
                    receipt_id="receipt://governed-operations-read-model",
                    action="governed_operations_read_model",
                    actor="gateway",
                    authority="read_only",
                    evidence_refs=evidence_refs,
                    policy_result="read_model_only",
                    timestamp=_clock(),
                    status="projected",
                    input_payload={"environment": gateway_env},
                    output_payload={
                        "evidence_ref_count": len(evidence_refs),
                        "runtime_conformance": conformance.get("terminal_status", ""),
                    },
                ),
            )
        snapshot = GovernedOperationsKernel().build_snapshot(
            loops=default_loop_registry(),
            receipts=receipts,
            observed_states=_governed_operations_observed_states(
                conformance=conformance,
                deployment=deployment,
                authority_witness=authority_witness,
                latest_anchor_id=latest_anchor_id,
            ),
            generated_at=_clock(),
        )
        return snapshot.to_json_dict()

    @app.get("/governed-operations/console", response_class=HTMLResponse)
    def governed_operations_console():
        return HTMLResponse(_governed_operations_console_html(governed_operations_read_model()))

    @app.get("/deployment/witness")
    def deployment_witness():
        return _build_deployment_witness()

    @app.get("/capabilities/evidence")
    def capabilities_evidence():
        projection = _capability_evidence_projection()
        return {
            "runtime_env": gateway_env,
            "commit_sha": _commit_sha(),
            "deployment_id": _deployment_id(),
            **projection,
        }

    @app.get("/audit/verify")
    def audit_verify():
        anchors = command_ledger.list_anchors(limit=1)
        if not anchors:
            return {
                "valid": False,
                "reason": "anchor_not_found",
                "entries_checked": 0,
                "latest_anchor_id": "",
                "unanchored_event_count": _unanchored_event_count(),
                "governed": True,
            }
        anchor = anchors[0]
        proof = command_ledger.export_anchor_proof(anchor.anchor_id)
        if proof is None:
            return {
                "valid": False,
                "reason": "anchor_proof_not_found",
                "entries_checked": 0,
                "latest_anchor_id": anchor.anchor_id,
                "unanchored_event_count": _unanchored_event_count(),
                "governed": True,
            }
        verification = command_ledger.verify_anchor_proof(
            proof,
            signing_secret=os.environ.get("MULLU_COMMAND_ANCHOR_SECRET", "local-command-anchor-secret"),
        )
        return {
            "valid": verification.valid,
            "reason": verification.reason,
            "entries_checked": len(proof.event_hashes),
            "latest_anchor_id": verification.anchor_id,
            "last_hash": anchor.to_event_hash[:16],
            "unanchored_event_count": _unanchored_event_count(),
            "governed": True,
        }

    @app.get("/proof/verify")
    def proof_verify():
        conformance = runtime_conformance()
        deployment = _build_deployment_witness()
        audit = audit_verify()
        conformance_valid = _hmac_certificate_signature_valid(
            conformance,
            signing_secret=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", "local-runtime-conformance-secret"),
        )
        deployment_valid = _signed_claim_valid(
            deployment,
            signing_secret=os.environ.get("MULLU_DEPLOYMENT_WITNESS_SECRET", "local-deployment-witness-secret"),
        )
        checks = [
            {
                "check_id": "runtime_conformance_signature",
                "passed": conformance_valid,
                "detail": str(conformance.get("certificate_id", "")),
            },
            {
                "check_id": "deployment_witness_signature",
                "passed": deployment_valid,
                "detail": str(deployment.get("deployment_id", "")),
            },
            {
                "check_id": "audit_anchor_verification",
                "passed": bool(audit.get("valid")),
                "detail": str(audit.get("reason", "")),
            },
        ]
        return {
            "valid": all(check["passed"] for check in checks),
            "runtime_env": gateway_env,
            "deployment_id": deployment.get("deployment_id", ""),
            "commit_sha": deployment.get("commit_sha", ""),
            "checks": checks,
            "checks_passed": [check["check_id"] for check in checks if check["passed"]],
            "checks_missing": [check["check_id"] for check in checks if not check["passed"]],
            "terminal_status": "verified" if all(check["passed"] for check in checks) else "verification_gaps",
            "governed": True,
        }

    @app.get("/govern-cloud/staging/witness")
    def govern_cloud_staging_witness(request: Request):
        _require_authority_operator(request)
        return _govern_cloud_staging_read_model()

    @app.get("/v1/health")
    def govern_cloud_public_health():
        return _govern_cloud_public_json_proxy("/v1/health")

    @app.get("/v1/version")
    def govern_cloud_public_version():
        return _govern_cloud_public_json_proxy("/v1/version")

    @app.get("/api/v1/federation/summary")
    def federation_summary(request: Request):
        _require_authority_operator(request)
        return federated_control_snapshot_to_json_dict(federated_control_plane.snapshot())

    def _reflex_snapshot() -> RuntimeHealthSnapshot:
        router_summary = router.summary()
        command_summary = router_summary.get("command_ledger", {})
        state_counts = command_summary.get("states", {}) if isinstance(command_summary, dict) else {}
        runtime_witness_payload = router.runtime_witness(
            environment=gateway_env,
            signature_key_id=os.environ.get("MULLU_RUNTIME_WITNESS_KEY_ID", "runtime-witness-local"),
            signing_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", "local-runtime-witness-secret"),
        )
        missing_deployment_witnesses = 0 if runtime_witness_payload.get("latest_anchor_id") else 1
        terminal_certificates = (
            int(command_summary.get("terminal_certificates", 0))
            if isinstance(command_summary, dict)
            else 0
        )
        pending_approval_count = int(router.pending_approvals)
        metrics = {
            "requests": int(router_summary.get("message_count", 0)),
            "failures": int(router_summary.get("error_count", 0)),
            "duplicate_messages": int(router_summary.get("duplicate_count", 0)),
            "missing_approvals": pending_approval_count,
            "approval_escalations": pending_approval_count,
            "unverified_executions": int(state_counts.get("requires_review", 0)),
            "deployment_witness_missing": missing_deployment_witnesses,
            "missing_deployment_witnesses": missing_deployment_witnesses,
            "premium_model_low_risk_requests": _int_env(
                "MULLU_REFLEX_PREMIUM_MODEL_LOW_RISK_REQUESTS"
            ),
            "terminal_certificates": terminal_certificates,
        }
        return RuntimeHealthSnapshot(
            snapshot_id=f"reflex-snapshot-{sha256(json.dumps(metrics, sort_keys=True).encode()).hexdigest()[:16]}",
            runtime=gateway_env,
            time_window="current_process",
            metrics=metrics,
            evidence_refs=(
                ReflexEvidenceRef(
                    kind="gateway_summary",
                    ref_id="gateway:router.summary",
                    evidence_hash=sha256(json.dumps(router_summary, sort_keys=True, default=str).encode()).hexdigest(),
                ),
                ReflexEvidenceRef(
                    kind="runtime_witness",
                    ref_id=str(runtime_witness_payload.get("witness_id", "runtime-witness:missing")),
                    evidence_hash=sha256(
                        json.dumps(runtime_witness_payload, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
            ),
            captured_at=_clock(),
        )

    def _reflex_pipeline() -> dict[str, Any]:
        snapshot = _reflex_snapshot()
        anomalies = detect_anomalies(snapshot)
        diagnoses = tuple(diagnose_anomaly(anomaly, snapshot) for anomaly in anomalies)
        eval_cases = tuple(eval_case for diagnosis in diagnoses for eval_case in generate_eval_cases(diagnosis))
        evals_by_diagnosis = {
            diagnosis.diagnosis_id: tuple(
                eval_case for eval_case in eval_cases
                if eval_case.diagnosis_id == diagnosis.diagnosis_id
            )
            for diagnosis in diagnoses
        }
        candidates = tuple(
            propose_upgrade(diagnosis, evals_by_diagnosis[diagnosis.diagnosis_id])
            for diagnosis in diagnoses
        )
        return {
            "snapshot": snapshot,
            "anomalies": anomalies,
            "diagnoses": diagnoses,
            "eval_cases": eval_cases,
            "candidates": candidates,
        }

    def _capability_portfolio_health_signals(snapshot: RuntimeHealthSnapshot) -> tuple[CapabilityHealthSignal, ...]:
        metrics = snapshot.metrics
        evidence_refs = tuple(
            f"{evidence.kind}:{evidence.ref_id}"
            for evidence in snapshot.evidence_refs
        ) or (f"runtime_health:{snapshot.snapshot_id}",)
        requests = max(1, int(metrics.get("requests", 0)))
        failures = int(metrics.get("failures", 0))
        success_rate = max(0.0, min(1.0, 1.0 - (failures / requests)))
        missing_approvals = int(metrics.get("missing_approvals", 0))
        deployment_witness_missing = int(metrics.get("deployment_witness_missing", 0))
        return (
            CapabilityHealthSignal(
                capability_id="gateway.command_execution",
                observed_at=snapshot.captured_at,
                maturity_level="C4",
                success_rate=success_rate,
                failure_count=failures,
                mean_latency_ms=0,
                cost_per_success=0.0,
                open_incidents=1 if failures else 0,
                blocker_codes=("gateway_failures_observed",) if failures else (),
                evidence_refs=evidence_refs,
                metadata={"source_snapshot_id": snapshot.snapshot_id},
            ),
            CapabilityHealthSignal(
                capability_id="gateway.approval_flow",
                observed_at=snapshot.captured_at,
                maturity_level="C4",
                success_rate=0.96 if missing_approvals else 1.0,
                failure_count=missing_approvals,
                mean_latency_ms=0,
                cost_per_success=0.0,
                open_incidents=1 if missing_approvals else 0,
                blocker_codes=("missing_approvals",) if missing_approvals else (),
                evidence_refs=evidence_refs,
                metadata={"source_snapshot_id": snapshot.snapshot_id},
            ),
            CapabilityHealthSignal(
                capability_id="gateway.deployment_witness",
                observed_at=snapshot.captured_at,
                maturity_level="C3" if deployment_witness_missing else "C6",
                success_rate=0.90 if deployment_witness_missing else 1.0,
                failure_count=deployment_witness_missing,
                mean_latency_ms=0,
                cost_per_success=0.0,
                open_incidents=1 if deployment_witness_missing else 0,
                blocker_codes=("deployment_witness_missing",) if deployment_witness_missing else (),
                evidence_refs=evidence_refs,
                metadata={"source_snapshot_id": snapshot.snapshot_id},
            ),
        )

    def _reflex_evidence_from_payload(payload: dict[str, Any]) -> ReflexEvidenceRef:
        return ReflexEvidenceRef(
            kind=str(payload.get("kind", "")).strip(),
            ref_id=str(payload.get("ref_id", "")).strip(),
            evidence_hash=payload.get("evidence_hash"),
        )

    def _reflex_sandbox_result_from_payload(payload: dict[str, Any]) -> ReflexSandboxResult:
        report_refs = tuple(
            _reflex_evidence_from_payload(report_ref)
            for report_ref in payload.get("report_refs", ())
            if isinstance(report_ref, dict)
        )
        return ReflexSandboxResult(
            candidate_id=str(payload.get("candidate_id", "")).strip(),
            passed=bool(payload.get("passed", False)),
            failed_checks=tuple(str(check) for check in payload.get("failed_checks", ())),
            report_refs=report_refs,
        )

    def _reflex_replay_from_payload(payload: dict[str, Any]) -> ReflexReplayResult:
        evidence_payload = payload.get("evidence_ref")
        if not isinstance(evidence_payload, dict):
            raise ValueError("replay evidence_ref must be an object")
        return ReflexReplayResult(
            replay_id=str(payload.get("replay_id", "")).strip(),
            passed=bool(payload.get("passed", False)),
            evidence_ref=_reflex_evidence_from_payload(evidence_payload),
            detail=str(payload.get("detail", "")).strip(),
        )

    def _reflex_sandbox_bundle_from_payload(
        candidate_id: str,
        payload: dict[str, Any],
    ) -> ReflexSandboxBundle:
        bundle_payload = payload.get("sandbox_bundle")
        if isinstance(bundle_payload, dict):
            sandbox_payload = bundle_payload.get("sandbox_result")
            if not isinstance(sandbox_payload, dict):
                raise ValueError("sandbox_bundle.sandbox_result must be an object")
            return ReflexSandboxBundle(
                bundle_id=str(bundle_payload.get("bundle_id", "")).strip(),
                candidate_id=str(bundle_payload.get("candidate_id", "")).strip(),
                eval_ids=tuple(str(eval_id) for eval_id in bundle_payload.get("eval_ids", ())),
                replay_results=tuple(
                    _reflex_replay_from_payload(replay_payload)
                    for replay_payload in bundle_payload.get("replay_results", ())
                    if isinstance(replay_payload, dict)
                ),
                sandbox_result=_reflex_sandbox_result_from_payload(sandbox_payload),
                mutation_applied=bool(bundle_payload.get("mutation_applied", False)),
            )
        sandbox_payload = payload.get("sandbox_result")
        if not isinstance(sandbox_payload, dict):
            raise ValueError("sandbox_bundle or sandbox_result is required before promotion")
        return ReflexSandboxBundle(
            bundle_id=f"sandbox:{candidate_id}",
            candidate_id=candidate_id,
            eval_ids=(),
            replay_results=(),
            sandbox_result=_reflex_sandbox_result_from_payload(sandbox_payload),
            mutation_applied=False,
        )

    def _build_reflex_deployment_witness(
        handoff: ReflexCanaryHandoff,
        snapshot: RuntimeHealthSnapshot,
        *,
        target_environment: str,
    ) -> ReflexDeploymentWitness:
        witness_core = {
            "candidate_id": handoff.candidate_id,
            "certificate_id": handoff.certificate.certificate_id,
            "promotion_decision_id": handoff.promotion_decision.decision_id,
            "target_environment": target_environment,
            "canary_status": "planned",
            "rollback_plan_ref": handoff.rollback_plan_ref,
            "signed_at": _clock(),
            "signature_key_id": os.environ.get(
                "MULLU_REFLEX_DEPLOYMENT_WITNESS_KEY_ID",
                "reflex-deployment-witness-local",
            ),
            "production_mutation_applied": False,
        }
        witness_id_seed = json.dumps(
            {
                **witness_core,
                "health_refs": [ref.to_json_dict() for ref in snapshot.evidence_refs],
            },
            sort_keys=True,
        )
        signature = hmac.new(
            os.environ.get(
                "MULLU_REFLEX_DEPLOYMENT_WITNESS_SECRET",
                "local-reflex-deployment-witness-secret",
            ).encode("utf-8"),
            witness_id_seed.encode("utf-8"),
            sha256,
        ).hexdigest()
        return ReflexDeploymentWitness(
            witness_id=f"reflex-deployment-witness-{sha256(witness_id_seed.encode()).hexdigest()[:16]}",
            health_refs=snapshot.evidence_refs,
            signature=f"hmac-sha256:{signature}",
            **witness_core,
        )

    def _record_reflex_deployment_witness(
        witness: dict[str, Any],
        request: Request,
    ) -> None:
        _require_reflex_deployment_witness_log_backed()
        reflex_deployment_witness_log.record(
            tenant_id=request.headers.get("X-Mullu-Authority-Tenant-Id", "platform") or "platform",
            identity_id=request.headers.get("X-Mullu-Authority-Sender-Id", "reflex") or "reflex",
            endpoint="/runtime/self/promote",
            method="POST",
            allowed=True,
            guards=[
                GuardDecisionDetail(
                    guard_name="deployment_authority",
                    allowed=True,
                    reason="deployment authority authorized canary witness persistence",
                ),
                GuardDecisionDetail(
                    guard_name="reflex_auto_canary_decision",
                    allowed=True,
                    reason="promotion decision allowed canary witness persistence",
                ),
            ],
            detail={
                "event_type": "reflex_deployment_witness_persisted_v1",
                "witness": witness,
            },
        )

    def _reflex_deployment_witness_records(limit: int = 1000) -> list[dict[str, Any]]:
        decisions = reflex_deployment_witness_log.query(
            endpoint="/runtime/self/promote",
            allowed=True,
            limit=limit,
        )
        records: list[dict[str, Any]] = []
        for decision in decisions:
            if decision.detail.get("event_type") != "reflex_deployment_witness_persisted_v1":
                continue
            witness = decision.detail.get("witness")
            if isinstance(witness, dict):
                records.append(witness)
        return records

    def _replay_reflex_deployment_witness(witness: dict[str, Any]) -> bool:
        return verify_reflex_deployment_witness(
            witness,
            signing_secret=os.environ.get(
                "MULLU_REFLEX_DEPLOYMENT_WITNESS_SECRET",
                "local-reflex-deployment-witness-secret",
            ),
        )

    def _bounded_query_limit(request: Request, *, default: int = 50, maximum: int = 500) -> int:
        raw_limit = request.query_params.get("limit", str(default))
        try:
            requested_limit = int(raw_limit)
        except ValueError:
            requested_limit = default
        return max(1, min(requested_limit, maximum))

    def _reflex_witness_validator_envelope(witness: dict[str, Any]) -> dict[str, Any]:
        return {
            "witness": witness,
            "validator": "scripts/validate_reflex_deployment_witness.py",
            "format": "reflex_deployment_witness_validator_envelope_v1",
        }

    @app.get("/runtime/self/health")
    def runtime_self_health(request: Request):
        _require_authority_operator(request)
        return _reflex_snapshot().to_json_dict()

    @app.get("/runtime/self/inspect")
    def runtime_self_inspect(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        return {
            "snapshot": pipeline["snapshot"].to_json_dict(),
            "anomalies": [anomaly.to_json_dict() for anomaly in pipeline["anomalies"]],
            "anomaly_count": len(pipeline["anomalies"]),
        }

    @app.post("/runtime/self/diagnose")
    def runtime_self_diagnose(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        return {
            "diagnoses": [diagnosis.to_json_dict() for diagnosis in pipeline["diagnoses"]],
            "diagnosis_count": len(pipeline["diagnoses"]),
        }

    @app.post("/runtime/self/evaluate")
    def runtime_self_evaluate(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        evals_by_diagnosis = {
            diagnosis.diagnosis_id: tuple(
                eval_case for eval_case in pipeline["eval_cases"]
                if eval_case.diagnosis_id == diagnosis.diagnosis_id
            )
            for diagnosis in pipeline["diagnoses"]
        }
        sandbox_bundles = tuple(
            build_sandbox_bundle(candidate, evals_by_diagnosis.get(candidate.diagnosis_id, ()))
            for candidate in pipeline["candidates"]
        )
        return {
            "eval_cases": [eval_case.to_json_dict() for eval_case in pipeline["eval_cases"]],
            "sandbox_bundles": [bundle.to_json_dict() for bundle in sandbox_bundles],
            "eval_count": len(pipeline["eval_cases"]),
            "sandbox_bundle_count": len(sandbox_bundles),
            "side_effects": "none",
        }

    @app.post("/runtime/self/propose-upgrade")
    def runtime_self_propose_upgrade(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        return {
            "candidates": [candidate.to_json_dict() for candidate in pipeline["candidates"]],
            "candidate_count": len(pipeline["candidates"]),
            "mutation_applied": False,
        }

    @app.get("/runtime/self/capability-improvement-portfolio")
    def runtime_self_capability_improvement_portfolio(request: Request, max_candidates: int = 3):
        _require_authority_operator(request)
        if max_candidates < 1:
            raise HTTPException(400, detail="max_candidates must be positive")
        snapshot = _reflex_snapshot()
        portfolio = AutonomousCapabilityUpgradeLoop().propose_portfolio(
            _capability_portfolio_health_signals(snapshot),
            generated_at=snapshot.captured_at,
            max_candidates=max_candidates,
        )
        return {
            "schema_ref": CAPABILITY_IMPROVEMENT_PORTFOLIO_SCHEMA_REF,
            "portfolio": portfolio.to_json_dict(),
            "portfolio_id": portfolio.portfolio_id,
            "plan_count": len(portfolio.plans),
            "mutation_applied": False,
            "activation_blocked": portfolio.activation_blocked,
            "operator_review_required": portfolio.operator_review_required,
        }

    @app.post("/runtime/self/certify")
    def runtime_self_certify(payload: dict[str, Any], request: Request):
        _require_authority_operator(request)
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            raise HTTPException(400, detail="candidate_id is required")
        pipeline = _reflex_pipeline()
        candidates = {candidate.candidate_id: candidate for candidate in pipeline["candidates"]}
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise HTTPException(404, detail="reflex candidate not found")
        handoff = build_certification_handoff(
            candidate,
            author_id=str(payload.get("author_id", "reflex@mullusi.com")).strip() or "reflex@mullusi.com",
            branch=str(payload.get("branch", "reflex/candidate")).strip() or "reflex/candidate",
            base_commit=str(payload.get("base_commit", "0" * 40)).strip() or "0" * 40,
            head_commit=str(payload.get("head_commit", "1" * 40)).strip() or "1" * 40,
            created_at=_clock(),
            base_ref=str(payload.get("base_ref", "HEAD^")).strip() or "HEAD^",
            head_ref=str(payload.get("head_ref", "HEAD")).strip() or "HEAD",
        )
        return {
            **handoff.to_json_dict(),
            "candidate_id": candidate_id,
            "status": "certification_required",
            "required_command": " ".join(handoff.command_args),
        }

    @app.post("/runtime/self/promote")
    def runtime_self_promote(payload: dict[str, Any], request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        candidates = {candidate.candidate_id: candidate for candidate in pipeline["candidates"]}
        candidate_id = str(payload.get("candidate_id", "")).strip()
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise HTTPException(404, detail="reflex candidate not found")
        certificate_payload = payload.get("certificate")
        if not isinstance(certificate_payload, dict) or (
            not isinstance(payload.get("sandbox_bundle"), dict)
            and not isinstance(payload.get("sandbox_result"), dict)
        ):
            return {
                "candidate_id": candidate_id,
                "disposition": "human_approval_required",
                "requires_human_approval": True,
                "mutation_applied": False,
                "reason": "sandbox bundle and certificate are required before promotion",
            }
        try:
            sandbox_bundle = _reflex_sandbox_bundle_from_payload(candidate_id, payload)
            certificate = ChangeCertificate(**certificate_payload)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                400,
                detail=f"invalid reflex promotion evidence: {exc}",
            ) from exc
        handoff = build_canary_handoff(candidate, sandbox_bundle, certificate)
        decision = handoff.promotion_decision
        deployment_witness = None
        witness_persisted = False
        if bool(payload.get("apply_canary", False)):
            _require_deployment_authority(request)
            if decision.disposition is not ReflexPromotionDisposition.AUTO_CANARY_ALLOWED:
                raise HTTPException(
                    409,
                    detail="reflex canary application requires auto-canary promotion decision",
                )
            target_environment = str(payload.get("target_environment", "canary")).strip() or "canary"
            deployment_witness = _build_reflex_deployment_witness(
                handoff,
                pipeline["snapshot"],
                target_environment=target_environment,
            ).to_json_dict()
            _record_reflex_deployment_witness(deployment_witness, request)
            witness_persisted = True
        return {
            **handoff.to_json_dict(),
            "mutation_applied": False,
            "disposition": decision.disposition.value,
            "requires_human_approval": decision.requires_human_approval,
            "deployment_witness": deployment_witness,
            "deployment_witness_persisted": witness_persisted,
        }

    @app.get("/runtime/self/deployment-witnesses")
    def runtime_self_deployment_witnesses(request: Request):
        _require_authority_operator(request)
        _require_reflex_deployment_witness_log_backed()
        limit = _bounded_query_limit(request)
        records = _reflex_deployment_witness_records(limit=limit)
        replayed_records = [
            {
                "witness": witness,
                "replay_passed": _replay_reflex_deployment_witness(witness),
                "validator_envelope": _reflex_witness_validator_envelope(witness),
            }
            for witness in records
        ]
        return {
            "records": replayed_records,
            "record_count": len(replayed_records),
            "limit": limit,
            "export_format": "reflex_deployment_witness_validator_envelope_v1",
            "validator": "scripts/validate_reflex_deployment_witness.py",
            "all_replay_passed": all(record["replay_passed"] for record in replayed_records),
            "mutation_applied": False,
        }

    @app.get("/runtime/self/witness")
    def runtime_self_witness(request: Request):
        _require_authority_operator(request)
        pipeline = _reflex_pipeline()
        deployment_witness_records = _reflex_deployment_witness_records()
        payload = {
            "witness_id": f"reflex-witness-{sha256(pipeline['snapshot'].to_json().encode()).hexdigest()[:16]}",
            "snapshot_id": pipeline["snapshot"].snapshot_id,
            "anomaly_count": len(pipeline["anomalies"]),
            "diagnosis_count": len(pipeline["diagnoses"]),
            "eval_count": len(pipeline["eval_cases"]),
            "candidate_count": len(pipeline["candidates"]),
            "mutation_applied": False,
            "protected_surfaces_auto_promote": False,
            "deployment_witness_log_backed": reflex_deployment_witness_log_backed,
            "ephemeral_deployment_witness_log_allowed": reflex_ephemeral_witness_log_allowed,
            "deployment_witness_count": len(deployment_witness_records),
            "deployment_witness_replay_passed": all(
                _replay_reflex_deployment_witness(witness)
                for witness in deployment_witness_records
            ),
            "latest_deployment_witness_id": (
                deployment_witness_records[0]["witness_id"]
                if deployment_witness_records
                else None
            ),
            "signed_at": _clock(),
            "signature_key_id": os.environ.get("MULLU_REFLEX_WITNESS_KEY_ID", "reflex-witness-local"),
        }
        signature_payload = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        signature = hmac.new(
            os.environ.get("MULLU_REFLEX_WITNESS_SECRET", "local-reflex-witness-secret").encode("utf-8"),
            signature_payload.encode("utf-8"),
            sha256,
        ).hexdigest()
        return {
            **payload,
            "signature": f"hmac-sha256:{signature}",
        }

    @app.get("/authority/witness")
    def authority_witness(request: Request):
        _require_authority_operator(request)
        return asdict(authority_obligation_mesh.responsibility_witness())

    @app.get("/authority/ownership")
    def authority_ownership(
        request: Request,
        tenant_id: str = "",
        resource_ref: str = "",
        owner_team: str = "",
        primary_owner_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        ownership = authority_mesh_store.list_ownership()
        if tenant_id:
            ownership = tuple(item for item in ownership if item.tenant_id == tenant_id)
        if resource_ref:
            ownership = tuple(item for item in ownership if item.resource_ref == resource_ref)
        if owner_team:
            ownership = tuple(item for item in ownership if item.owner_team == owner_team)
        if primary_owner_id:
            ownership = tuple(item for item in ownership if item.primary_owner_id == primary_owner_id)
        page, page_meta = _read_model_page(
            ownership,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "ownership": [asdict(item) for item in page],
            "count": len(page),
            **page_meta,
        }

    @app.get("/authority/policies")
    def authority_policies(
        request: Request,
        tenant_id: str = "",
        policy_id: str = "",
        capability: str = "",
        risk_tier: str = "",
        required_role: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        approval_policies = authority_mesh_store.list_approval_policies()
        escalation_policies = authority_mesh_store.list_escalation_policies()
        if tenant_id:
            approval_policies = tuple(policy for policy in approval_policies if policy.tenant_id == tenant_id)
            escalation_policies = tuple(policy for policy in escalation_policies if policy.tenant_id == tenant_id)
        if policy_id:
            approval_policies = tuple(policy for policy in approval_policies if policy.policy_id == policy_id)
            escalation_policies = tuple(policy for policy in escalation_policies if policy.policy_id == policy_id)
        if capability:
            approval_policies = tuple(policy for policy in approval_policies if policy.capability == capability)
            escalation_policies = ()
        if risk_tier:
            approval_policies = tuple(policy for policy in approval_policies if policy.risk_tier == risk_tier)
            escalation_policies = ()
        if required_role:
            approval_policies = tuple(policy for policy in approval_policies if required_role in policy.required_roles)
            escalation_policies = ()
        approval_page, approval_meta = _read_model_page(
            approval_policies,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        escalation_page, escalation_meta = _read_model_page(
            escalation_policies,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "approval_policies": [asdict(policy) for policy in approval_page],
            "escalation_policies": [asdict(policy) for policy in escalation_page],
            "approval_count": len(approval_page),
            "escalation_count": len(escalation_page),
            "approval_page": approval_meta,
            "escalation_page": escalation_meta,
        }

    @app.get("/authority/approval-chains")
    def authority_approval_chains(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        command_id: str = "",
        policy_id: str = "",
        required_role: str = "",
        overdue: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        chains = authority_mesh_store.list_approval_chains()
        if tenant_id:
            chains = tuple(chain for chain in chains if chain.tenant_id == tenant_id)
        if status:
            chains = tuple(chain for chain in chains if chain.status.value == status)
        if command_id:
            chains = tuple(chain for chain in chains if chain.command_id == command_id)
        if policy_id:
            chains = tuple(chain for chain in chains if chain.policy_id == policy_id)
        if required_role:
            chains = tuple(chain for chain in chains if required_role in chain.required_roles)
        if overdue:
            requested_overdue = overdue.strip().lower()
            if requested_overdue not in {"true", "false"}:
                raise HTTPException(400, detail="overdue must be true or false")
            now = datetime.fromisoformat(_clock().replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

            def _chain_overdue(chain: Any) -> bool:
                try:
                    due_at = datetime.fromisoformat(chain.due_at.replace("Z", "+00:00"))
                except ValueError:
                    return False
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
                return due_at <= now

            expected = requested_overdue == "true"
            chains = tuple(chain for chain in chains if _chain_overdue(chain) is expected)
        page, page_meta = _read_model_page(
            chains,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "approval_chains": [asdict(chain) for chain in page],
            "count": len(page),
            **page_meta,
        }

    @app.get("/commands/{command_id}/authority")
    def command_authority(command_id: str, request: Request):
        _require_authority_operator(request)
        chain = authority_obligation_mesh.approval_chain_for(command_id)
        obligations = authority_obligation_mesh.obligations_for(command_id)
        if chain is None and not obligations:
            raise HTTPException(404, detail="authority records not found")
        return {
            "command_id": command_id,
            "approval_chain": asdict(chain) if chain is not None else None,
            "obligations": [asdict(obligation) for obligation in obligations],
        }

    @app.post("/authority/approval-chains/expire-overdue")
    def expire_overdue_authority_approval_chains(request: Request):
        _require_authority_operator(request)
        chains = authority_obligation_mesh.expire_overdue_approval_chains()
        return {
            "status": "expired",
            "approval_chains": [asdict(chain) for chain in chains],
            "count": len(chains),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.post("/authority/approval-chains/close-expired")
    async def close_expired_authority_approval_chains(request: Request):
        _require_authority_operator(request)
        try:
            payload = await _request_json_mapping(request)
            evidence_refs = _payload_text_tuple(payload, "evidence_refs")
            chains = authority_obligation_mesh.close_expired_approval_chains(
                evidence_refs=evidence_refs,
                tenant_id=str(payload.get("tenant_id", "")).strip(),
                command_id=str(payload.get("command_id", "")).strip(),
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {
            "status": "closed",
            "approval_chains": [asdict(chain) for chain in chains],
            "count": len(chains),
            "evidence_refs": list(evidence_refs),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.get("/authority/obligations")
    def authority_obligations(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        command_id: str = "",
        owner_id: str = "",
        owner_team: str = "",
        obligation_type: str = "",
        overdue: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        obligations = authority_mesh_store.list_obligations(command_id)
        if tenant_id:
            obligations = tuple(obligation for obligation in obligations if obligation.tenant_id == tenant_id)
        if status:
            obligations = tuple(obligation for obligation in obligations if obligation.status.value == status)
        if owner_id:
            obligations = tuple(obligation for obligation in obligations if obligation.owner_id == owner_id)
        if owner_team:
            obligations = tuple(obligation for obligation in obligations if obligation.owner_team == owner_team)
        if obligation_type:
            obligations = tuple(
                obligation for obligation in obligations
                if obligation.obligation_type == obligation_type
            )
        if overdue:
            requested_overdue = overdue.strip().lower()
            if requested_overdue not in {"true", "false"}:
                raise HTTPException(400, detail="overdue must be true or false")
            now = datetime.fromisoformat(_clock().replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

            def _obligation_overdue(obligation: Any) -> bool:
                try:
                    due_at = datetime.fromisoformat(obligation.due_at.replace("Z", "+00:00"))
                except ValueError:
                    return False
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
                return due_at <= now

            expected = requested_overdue == "true"
            obligations = tuple(
                obligation for obligation in obligations
                if _obligation_overdue(obligation) is expected
            )
        page, page_meta = _read_model_page(
            obligations,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "obligations": [asdict(obligation) for obligation in page],
            "count": len(page),
            **page_meta,
        }

    @app.post("/authority/obligations/{obligation_id}/satisfy")
    def satisfy_authority_obligation(obligation_id: str, payload: dict[str, Any], request: Request):
        _require_authority_operator(request)
        raw_evidence_refs = payload.get("evidence_refs", ())
        if isinstance(raw_evidence_refs, str):
            raw_evidence_refs = (raw_evidence_refs,)
        if not isinstance(raw_evidence_refs, (list, tuple)):
            raise HTTPException(400, detail="evidence_refs must be a list of strings")
        evidence_refs = tuple(str(ref).strip() for ref in raw_evidence_refs)
        evidence_refs = tuple(ref for ref in evidence_refs if ref)
        try:
            obligation = authority_obligation_mesh.satisfy_obligation(
                obligation_id,
                evidence_refs=evidence_refs,
            )
        except KeyError as exc:
            raise HTTPException(404, detail="obligation not found") from exc
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {
            "status": "satisfied",
            "obligation": asdict(obligation),
            "evidence_refs": list(evidence_refs),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.post("/authority/obligations/escalate-overdue")
    def escalate_overdue_authority_obligations(request: Request):
        _require_authority_operator(request)
        obligations = authority_obligation_mesh.escalate_overdue()
        return {
            "status": "escalated",
            "obligations": [asdict(obligation) for obligation in obligations],
            "count": len(obligations),
            "authority_witness": asdict(authority_obligation_mesh.responsibility_witness()),
        }

    @app.get("/authority/escalations")
    def authority_escalations(
        request: Request,
        tenant_id: str = "",
        command_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        events = authority_mesh_store.list_escalation_events()
        if tenant_id:
            events = tuple(event for event in events if event.get("tenant_id") == tenant_id)
        if command_id:
            events = tuple(event for event in events if event.get("command_id") == command_id)
        page, page_meta = _read_model_page(
            events,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "escalation_events": list(page),
            "count": len(page),
            **page_meta,
        }

    @app.get("/authority/responsibility")
    def authority_responsibility(
        request: Request,
        tenant_id: str = "",
        limit: int = 25,
    ):
        _require_authority_operator(request)
        bounded_limit = _bounded_read_model_limit(limit, maximum=100)
        witness = asdict(authority_obligation_mesh.responsibility_witness())
        chains = authority_mesh_store.list_approval_chains()
        obligations = authority_mesh_store.list_obligations()
        escalation_events = authority_mesh_store.list_escalation_events()
        ownership = authority_mesh_store.list_ownership()
        approval_policies = authority_mesh_store.list_approval_policies()
        escalation_policies = authority_mesh_store.list_escalation_policies()
        if tenant_id:
            chains = tuple(chain for chain in chains if chain.tenant_id == tenant_id)
            obligations = tuple(obligation for obligation in obligations if obligation.tenant_id == tenant_id)
            escalation_events = tuple(event for event in escalation_events if event.get("tenant_id") == tenant_id)
            ownership = tuple(item for item in ownership if item.tenant_id == tenant_id)
            approval_policies = tuple(policy for policy in approval_policies if policy.tenant_id == tenant_id)
            escalation_policies = tuple(policy for policy in escalation_policies if policy.tenant_id == tenant_id)
        pending_chains = tuple(
            chain for chain in chains
            if chain.status.value == "pending"
        )
        unresolved_obligations = tuple(
            obligation for obligation in obligations
            if obligation.status.value in {"open", "escalated"}
        )
        priority_chains = tuple(sorted(
            pending_chains,
            key=lambda chain: (_due_sort_key(chain.due_at), chain.chain_id),
        ))[:bounded_limit]
        priority_obligations = tuple(sorted(
            unresolved_obligations,
            key=lambda obligation: (_due_sort_key(obligation.due_at), obligation.obligation_id),
        ))[:bounded_limit]
        priority_escalations = tuple(reversed(escalation_events))[:bounded_limit]
        debt_clear = (
            int(witness.get("overdue_approval_chain_count", 0)) == 0
            and int(witness.get("expired_approval_chain_count", 0)) == 0
            and int(witness.get("overdue_obligation_count", 0)) == 0
            and int(witness.get("escalated_obligation_count", 0)) == 0
            and int(witness.get("unowned_high_risk_capability_count", 0)) == 0
        )
        return {
            "tenant_id": tenant_id,
            "responsibility_debt_clear": debt_clear,
            "authority_witness": witness,
            "ownership_count": len(ownership),
            "approval_policy_count": len(approval_policies),
            "escalation_policy_count": len(escalation_policies),
            "pending_approval_chain_count": len(pending_chains),
            "unresolved_obligation_count": len(unresolved_obligations),
            "escalation_event_count": len(escalation_events),
            "priority_approval_chains": [asdict(chain) for chain in priority_chains],
            "priority_obligations": [asdict(obligation) for obligation in priority_obligations],
            "priority_escalation_events": list(priority_escalations),
            "limit": bounded_limit,
            "evidence_refs": [
                "authority:witness",
                "authority:approval_chains_read_model",
                "authority:obligations_read_model",
                "authority:escalations_read_model",
                "authority:ownership_read_model",
                "authority:policy_read_model",
            ],
        }

    @app.post("/api/v1/orgs")
    async def orgos_register_organization(request: Request):
        _require_authority_operator(request)
        try:
            payload = await _request_json_mapping(request)
            roles: list[Role] = []
            owner_role_payload = payload.get("owner_role")
            if isinstance(owner_role_payload, Mapping):
                roles.append(_orgos_role_from_payload(owner_role_payload))
            raw_roles = payload.get("roles", ())
            if isinstance(raw_roles, str) or not isinstance(raw_roles, (list, tuple)):
                raise ValueError("roles_must_be_array")
            for raw_role in raw_roles:
                roles.append(_orgos_role_from_payload(_mapping_item(raw_role, "roles")))
            authority_rules: list[AuthorityRule] = []
            raw_rules = payload.get("authority_rules", ())
            if isinstance(raw_rules, str) or not isinstance(raw_rules, (list, tuple)):
                raise ValueError("authority_rules_must_be_array")
            for raw_rule in raw_rules:
                authority_rules.append(
                    _orgos_authority_rule_from_payload(_mapping_item(raw_rule, "authority_rules"))
                )
            organization, registered_roles, registered_rules = orgos_kernel.register_organization_surface(
                _orgos_organization_from_payload(payload),
                roles=roles,
                authority_rules=authority_rules,
            )
            event = orgos_case_event_log.record(
                case_id=f"org:{organization.org_id}",
                tenant_id=organization.tenant_id,
                event_type="organization_registered",
                actor_id=organization.owner_role_id,
                payload={
                    "organization": organization.to_json_dict(),
                    "roles": [role.to_json_dict() for role in registered_roles],
                    "authority_rules": [rule.to_json_dict() for rule in registered_rules],
                },
                evidence_refs=organization.evidence_refs,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {"organization": organization.to_json_dict(), "event": event.to_json_dict()}

    @app.post("/api/v1/departments")
    async def orgos_register_department(request: Request):
        _require_authority_operator(request)
        try:
            payload = await _request_json_mapping(request)
            department = orgos_kernel.register_department(_orgos_department_from_payload(payload))
            event = orgos_case_event_log.record(
                case_id=f"department:{department.department_id}",
                tenant_id=_optional_text(payload, "tenant_id", default="tenant:*"),
                event_type="department_registered",
                actor_id=_optional_text(payload, "actor_id", default="orgos_operator"),
                payload=department.to_json_dict(),
                evidence_refs=department.required_evidence,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {"department": department.to_json_dict(), "event": event.to_json_dict()}

    @app.post("/api/v1/cases")
    async def orgos_open_case(request: Request):
        _require_authority_operator(request)
        try:
            payload = await _request_json_mapping(request)
            work_case = orgos_kernel.open_case(_orgos_case_from_payload(payload))
            event = orgos_case_event_log.record(
                case_id=work_case.case_id,
                tenant_id=work_case.tenant_id,
                event_type="case_opened",
                actor_id=work_case.owner_role_id,
                payload=work_case.to_json_dict(),
                evidence_refs=work_case.evidence_refs,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {"case": work_case.to_json_dict(), "event": event.to_json_dict()}

    @app.get("/api/v1/cases/{case_id}")
    def orgos_get_case(
        request: Request,
        case_id: str,
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        try:
            work_case = orgos_kernel.get_case(case_id)
            events = orgos_case_event_log.list(
                case_id=case_id,
                limit=_bounded_read_model_limit(limit),
                offset=_bounded_read_model_offset(offset),
            )
        except ValueError as exc:
            raise HTTPException(404, detail=str(exc)) from exc
        return {"case": work_case.to_json_dict(), "events": events.to_json_dict()}

    @app.post("/api/v1/cases/{case_id}/events")
    async def orgos_append_case_event(request: Request, case_id: str):
        _require_authority_operator(request)
        try:
            work_case = orgos_kernel.get_case(case_id)
            payload = await _request_json_mapping(request)
            event_payload = payload.get("payload", {})
            if not isinstance(event_payload, Mapping):
                raise ValueError("payload_must_be_object")
            event = orgos_case_event_log.record(
                case_id=case_id,
                tenant_id=work_case.tenant_id,
                event_type=_optional_text(payload, "event_type", default="operator_note"),
                actor_id=_required_text(payload, "actor_id"),
                payload=event_payload,
                evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {"event": event.to_json_dict()}

    @app.post("/api/v1/cases/{case_id}/plan")
    async def orgos_add_case_plan_step(request: Request, case_id: str):
        _require_authority_operator(request)
        try:
            payload = await _request_json_mapping(request)
            step_payload = dict(_required_mapping(payload, "step"))
            step_payload["case_id"] = case_id
            step = orgos_kernel.add_plan_step(_orgos_plan_step_from_payload(step_payload))
            event = orgos_case_event_log.record(
                case_id=case_id,
                tenant_id=orgos_kernel.get_case(case_id).tenant_id,
                event_type="plan_step_added",
                actor_id=_optional_text(payload, "actor_id", default=step.department_id),
                payload=step.to_json_dict(),
                evidence_refs=step.evidence_required,
            )
            gate_decision = None
            gate_payload = payload.get("gate")
            if isinstance(gate_payload, Mapping):
                gate_decision = orgos_kernel.evaluate_plan_step(
                    step.step_id,
                    authority_decision=_authority_decision_from_payload(
                        _required_mapping(gate_payload, "authority_decision")
                    ),
                    policy_allowed=_payload_bool(gate_payload, "policy_allowed", default=False),
                    world_refs=_payload_text_tuple(gate_payload, "world_refs", allow_empty=True),
                    certified_capabilities=_payload_text_tuple(
                        gate_payload,
                        "certified_capabilities",
                        allow_empty=True,
                    ),
                    evidence_refs=_payload_text_tuple(gate_payload, "evidence_refs", allow_empty=True),
                    approval_refs=_payload_text_tuple(gate_payload, "approval_refs", allow_empty=True),
                )
                orgos_case_event_log.record(
                    case_id=case_id,
                    tenant_id=orgos_kernel.get_case(case_id).tenant_id,
                    event_type="authority_decision_recorded",
                    actor_id=_optional_text(payload, "actor_id", default=step.department_id),
                    payload=gate_decision.to_json_dict(),
                    evidence_refs=gate_decision.evidence_refs,
                )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {
            "step": step.to_json_dict(),
            "event": event.to_json_dict(),
            "gate_decision": gate_decision.to_json_dict() if gate_decision is not None else None,
        }

    @app.post("/api/v1/cases/{case_id}/close")
    async def orgos_close_case(request: Request, case_id: str):
        _require_authority_operator(request)
        try:
            payload = await _request_json_mapping(request)
            closure_payload = dict(_required_mapping(payload, "closure"))
            closure_payload["case_id"] = case_id
            terminal_payload = payload.get("terminal_certificate")
            terminal_certificate = (
                _terminal_certificate_from_payload(terminal_payload)
                if isinstance(terminal_payload, Mapping)
                else None
            )
            closure = _orgos_effect_closure_from_payload(closure_payload)
            closure_event_payload = closure.to_json_dict()
            if terminal_certificate is not None and not closure_event_payload.get("terminal_certificate_ref"):
                closure_event_payload["terminal_certificate_ref"] = terminal_certificate.certificate_id
            attempt_event = orgos_case_event_log.record(
                case_id=case_id,
                tenant_id=orgos_kernel.get_case(case_id).tenant_id,
                event_type="closure_attempted",
                actor_id=_optional_text(payload, "actor_id", default="orgos_operator"),
                payload=closure_event_payload,
                evidence_refs=closure.evidence_refs,
            )
            decision = orgos_kernel.close_case(closure, terminal_certificate=terminal_certificate)
            decision_event = orgos_case_event_log.record(
                case_id=case_id,
                tenant_id=orgos_kernel.get_case(case_id).tenant_id,
                event_type="closure_decided",
                actor_id=_optional_text(payload, "actor_id", default="orgos_operator"),
                payload=decision.to_json_dict(),
                evidence_refs=decision.evidence_refs,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {
            "closure_decision": decision.to_json_dict(),
            "attempt_event": attempt_event.to_json_dict(),
            "decision_event": decision_event.to_json_dict(),
        }

    @app.get("/api/v1/orgos/read-model")
    def orgos_read_model(
        request: Request,
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        events = orgos_case_event_log.list(
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "orgos": orgos_kernel.read_model(),
            "events": events.to_json_dict(),
        }

    @app.post("/api/v1/orgos/replay")
    def orgos_replay_projection(request: Request):
        nonlocal orgos_kernel
        _require_authority_operator(request)
        try:
            events = orgos_case_event_log.list(limit=10000).events
            replayed = replay_orgos_kernel_from_events(events)
            orgos_kernel = replayed
            app.state.orgos_kernel = replayed
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        return {
            "replayed": True,
            "event_count": len(events),
            "orgos": replayed.read_model(),
        }

    @app.get("/cases/read-model")
    def operational_cases_read_model(
        request: Request,
        tenant_id: str = "",
        case_type: str = "",
        status: str = "",
        owner: str = "",
        severity: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        read_model = build_operational_case_read_model(
            approval_chains=authority_mesh_store.list_approval_chains(),
            obligations=authority_mesh_store.list_obligations(),
            escalation_events=authority_mesh_store.list_escalation_events(),
        )
        cases = tuple(read_model["cases"])
        if tenant_id:
            cases = tuple(case for case in cases if case["tenant_id"] == tenant_id)
        if case_type:
            cases = tuple(case for case in cases if case["case_type"] == case_type)
        if status:
            cases = tuple(case for case in cases if case["status"] == status)
        if owner:
            cases = tuple(case for case in cases if case["owner"] == owner)
        if severity:
            cases = tuple(case for case in cases if case["severity"] == severity)
        page, page_meta = _read_model_page(
            cases,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            **read_model,
            "cases": list(page),
            "case_count": len(page),
            "total_case_count": len(cases),
            **page_meta,
        }

    @app.get("/authority/operator-audit")
    def authority_operator_audit(
        request: Request,
        path: str = "",
        authorized: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        audit_events = tuple(authority_operator_audit_events)
        if path:
            audit_events = tuple(event for event in audit_events if event.get("path") == path)
        if authorized:
            requested_authorized = authorized.strip().lower()
            if requested_authorized not in {"true", "false"}:
                raise HTTPException(400, detail="authorized must be true or false")
            expected = requested_authorized == "true"
            audit_events = tuple(event for event in audit_events if event.get("authorized") is expected)
        page, page_meta = _read_model_page(
            audit_events,
            limit=_bounded_read_model_limit(limit),
            offset=_bounded_read_model_offset(offset),
        )
        return {
            "operator_audit_events": list(page),
            "count": len(page),
            **page_meta,
        }

    @app.get("/authority/operator", response_class=HTMLResponse)
    def authority_operator_console(request: Request):
        _require_authority_operator(request)
        witness = authority_obligation_mesh.responsibility_witness()
        chains = authority_mesh_store.list_approval_chains()
        obligations = authority_mesh_store.list_obligations()
        escalations = authority_mesh_store.list_escalation_events()
        return HTMLResponse(
            _authority_operator_console_html(
                witness=asdict(witness),
                approval_chains=[asdict(chain) for chain in chains],
                obligations=[asdict(obligation) for obligation in obligations],
                escalation_events=list(escalations),
                operator_audit_events=list(authority_operator_audit_events[-100:]),
            )
        )

    @app.get("/capability-fabric/read-model")
    def capability_fabric_read_model(request: Request):
        _require_authority_operator(request)
        if capability_admission_gate is None:
            return {
                "enabled": False,
                "require_certified": None,
                "capsule_count": 0,
                "capability_count": 0,
                "artifact_count": 0,
                "installations": (),
                "capabilities": (),
                "domains": (),
            }
        return {
            "enabled": True,
            **capability_admission_gate.read_model(),
        }

    @app.post("/capability-fabric/capsule-admissions")
    async def capability_fabric_capsule_admission(request: Request):
        _require_authority_operator(request)
        if capability_admission_gate is None:
            raise HTTPException(503, detail="Capability fabric admission is not enabled")
        try:
            payload = await request.json()
            capsule, registry_entries, handoffs, require_production_ready = _capsule_admission_request(payload)
            outcome = install_certified_capsule_with_handoff_evidence(
                capsule=capsule,
                registry_entries=registry_entries,
                handoffs=handoffs,
                registry=capability_admission_gate.registry,
                clock=_clock,
                require_production_ready=require_production_ready,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(400, detail=str(exc)) from exc

        receipt = asdict(outcome.receipt)
        capability_capsule_admission_receipts.append(receipt)
        del capability_capsule_admission_receipts[:-500]
        return {
            "admission_receipt": receipt,
            "installation_record": outcome.installation_record.to_json_dict(),
            "compilation_result": outcome.compilation_result.to_json_dict(),
            "evidence_batch": _handoff_evidence_batch_payload(outcome.evidence_batch),
        }

    _INTERPRETATION_RECEIPT_FIELDS = (
        "receipt_id",
        "request_id",
        "raw_message_hash",
        "interpreted_intent",
        "extracted_slots",
        "missing_slots",
        "confidence",
        "model_or_rule_used",
        "rejected_interpretations",
        "risk_precheck",
        "created_at",
    )
    _INTERPRETED_REQUEST_FIELDS = (
        "request_id",
        "tenant_id",
        "actor_id",
        "channel",
        "conversation_id",
        "raw_message_hash",
        "intent_class",
        "capability_id",
        "extracted_slots",
        "missing_slots",
        "constraints",
        "search_needed",
        "action_needed",
        "risk_estimate",
        "approval_required",
        "confidence",
        "interpreter_kind",
        "rejected_interpretations",
        "created_at",
    )
    _INTERPRETATION_RECEIPT_FORBIDDEN_KEYS = frozenset({
        "body",
        "message",
        "raw_body",
        "rawbody",
        "raw_message",
        "rawmessage",
        "raw_text",
        "rawtext",
    })

    def _interpretation_payload_key_name(key: Any) -> str:
        return str(key).strip().replace("-", "_").lower()

    def _redacted_interpretation_value(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): _redacted_interpretation_value(nested)
                for key, nested in value.items()
                if _interpretation_payload_key_name(key)
                not in _INTERPRETATION_RECEIPT_FORBIDDEN_KEYS
            }
        if isinstance(value, list):
            return [_redacted_interpretation_value(item) for item in value]
        if isinstance(value, tuple):
            return [_redacted_interpretation_value(item) for item in value]
        try:
            json.dumps(value, ensure_ascii=True, allow_nan=False)
        except (TypeError, ValueError):
            return str(type(value).__name__)
        return value

    def _bounded_mapping(source: Any, allowed_keys: tuple[str, ...]) -> dict[str, Any]:
        if not isinstance(source, Mapping):
            return {}
        return {
            key: _redacted_interpretation_value(source[key])
            for key in allowed_keys
            if key in source
        }

    @app.get("/commands/{command_id}/interpretation-receipt")
    def command_interpretation_receipt(command_id: str, request: Request):
        _require_authority_operator(request)
        command = command_ledger.get(command_id)
        if command is None:
            raise HTTPException(404, detail="command not found")
        receipt = command.redacted_payload.get("interpretation_receipt")
        interpreted = command.redacted_payload.get("interpreted_request")
        if not isinstance(receipt, Mapping) or not isinstance(interpreted, Mapping):
            raise HTTPException(404, detail="interpretation receipt not found")
        bounded_receipt = _bounded_mapping(receipt, _INTERPRETATION_RECEIPT_FIELDS)
        bounded_interpreted = _bounded_mapping(interpreted, _INTERPRETED_REQUEST_FIELDS)
        receipt_id = str(
            bounded_receipt.get("receipt_id")
            or command.redacted_payload.get("interpretation_receipt_id")
            or ""
        )
        return {
            "schema_ref": "urn:mullusi:schema:command-interpretation-receipt-read-model:1",
            "command_id": command_id,
            "tenant_id": command.tenant_id,
            "actor_id": command.actor_id,
            "interpretation_receipt_id": receipt_id,
            "interpretation_receipt": bounded_receipt,
            "interpreted_request": bounded_interpreted,
            "raw_message_exposed": False,
            "execution_allowed": False,
            "governed": True,
        }

    @app.get("/commands/{command_id}/closure")
    def command_closure(command_id: str):
        certificate = command_ledger.terminal_certificate_for(command_id)
        if certificate is None:
            raise HTTPException(404, detail="terminal closure certificate not found")
        events = [
            {
                "event_id": event.event_id,
                "previous_state": event.previous_state.value,
                "next_state": event.next_state.value,
                "event_hash": event.event_hash,
                "timestamp": event.timestamp,
            }
            for event in command_ledger.events_for(command_id)
        ]
        certificate_payload = asdict(certificate)
        whqr_replay_binding = _whqr_replay_binding_from_terminal_certificate_payload(
            certificate_payload
        )
        whqr_replay_ref = str(whqr_replay_binding.get("replay_ref", ""))
        return {
            "command_id": command_id,
            "terminal_certificate": certificate,
            "whqr_replay_binding": whqr_replay_binding,
            "whqr_replay_ref": whqr_replay_ref,
            "proof_coverage_witnesses": _closure_proof_coverage_witnesses(
                terminal_certificate=certificate_payload,
                events=events,
            ),
            "events": events,
        }

    @app.get("/commands/{command_id}/universal-action-proof")
    def command_universal_action_proof(command_id: str):
        proof = universal_command_proof_view(command_ledger, command_id)
        if proof is None:
            if command_ledger.get(command_id) is None:
                raise HTTPException(404, detail="command not found")
            raise HTTPException(404, detail="universal action proof not found")
        proof_payload = asdict(proof)
        whqr_replay_binding = _validated_whqr_replay_binding(
            proof_payload.get("whqr_replay_binding")
        )
        proof_payload["whqr_replay_binding"] = whqr_replay_binding
        whqr_replay_ref = str(whqr_replay_binding.get("replay_ref", ""))
        return {
            "command_id": command_id,
            "universal_action_proof": proof_payload,
            "event_count": len(proof.event_hashes),
            "state_sequence": list(proof.state_sequence),
            "proof_hash": proof.proof_hash,
            "whqr_replay_binding": whqr_replay_binding,
            "whqr_replay_ref": whqr_replay_ref,
        }

    @app.get("/commands/{command_id}/universal-action-orchestration")
    def command_universal_action_orchestration(command_id: str):
        record = universal_command_orchestration_record_view(command_ledger, command_id)
        if record is None:
            if command_ledger.get(command_id) is None:
                raise HTTPException(404, detail="command not found")
            raise HTTPException(404, detail="universal action orchestration record not found")
        decision = record.get("decision", {})
        decision_status = decision.get("status", "") if isinstance(decision, Mapping) else ""
        closure = record.get("closure", {})
        reconciliation_ref = (
            closure.get("reconciliation_ref") if isinstance(closure, Mapping) else None
        )
        memory_ref = closure.get("memory_ref") if isinstance(closure, Mapping) else None
        whqr_replay_binding = (
            closure.get("whqr_replay_binding")
            if isinstance(closure, Mapping)
            else None
        )
        whqr_replay_binding = _validated_whqr_replay_binding(whqr_replay_binding)
        whqr_replay_ref = str(whqr_replay_binding.get("replay_ref", ""))
        record_payload = dict(record)
        if isinstance(closure, Mapping):
            closure_payload = dict(closure)
            closure_payload["whqr_replay_binding"] = whqr_replay_binding
            record_payload["closure"] = closure_payload
        return {
            "command_id": command_id,
            "universal_action_orchestration": record_payload,
            "orchestration_id": record.get("orchestration_id", ""),
            "decision_status": decision_status,
            "closure_state": record.get("closure_state", ""),
            "reconciliation_ref": reconciliation_ref,
            "memory_ref": memory_ref,
            "whqr_replay_binding": whqr_replay_binding,
            "whqr_replay_ref": whqr_replay_ref,
        }

    def _operator_universal_actions_payload(
        *,
        tenant_id: str = "",
        blocked: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        requested_blocked = blocked.strip().lower()
        if requested_blocked and requested_blocked not in {"true", "false"}:
            raise HTTPException(400, detail="blocked must be true or false")
        bounded_limit = _bounded_read_model_limit(limit)
        bounded_offset = _bounded_read_model_offset(offset)
        scan_limit = _bounded_read_model_limit(bounded_limit + bounded_offset, maximum=1000)
        proofs = []
        for command in command_ledger.list_commands(tenant_id=tenant_id, limit=scan_limit):
            proof = universal_command_proof_view(command_ledger, command.command_id)
            if proof is None:
                continue
            if requested_blocked:
                expected_blocked = requested_blocked == "true"
                if proof.blocked is not expected_blocked:
                    continue
            payload = asdict(proof)
            payload["tenant_id"] = command.tenant_id
            payload["actor_id"] = command.actor_id
            payload["intent"] = command.intent
            payload["command_state"] = command.state.value
            payload["created_at"] = command.created_at
            whqr_replay_binding = _validated_whqr_replay_binding(
                payload.get("whqr_replay_binding")
            )
            payload["whqr_replay_binding"] = whqr_replay_binding
            payload["whqr_replay_ref"] = str(whqr_replay_binding.get("replay_ref", ""))
            proofs.append(payload)
        page, page_meta = _read_model_page(
            tuple(proofs),
            limit=bounded_limit,
            offset=bounded_offset,
        )
        return {
            "universal_action_proofs": list(page),
            "count": len(page),
            "total": len(proofs),
            "tenant_id_filter": tenant_id,
            "blocked_filter": requested_blocked,
            **page_meta,
        }

    @app.get("/operator/universal-actions/read-model")
    def operator_universal_actions_read_model(
        request: Request,
        tenant_id: str = "",
        blocked: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        return _operator_universal_actions_payload(
            tenant_id=tenant_id,
            blocked=blocked,
            limit=limit,
            offset=offset,
        )

    @app.get("/operator/universal-actions", response_class=HTMLResponse)
    def operator_universal_actions_console(
        request: Request,
        tenant_id: str = "",
        blocked: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        read_model = _operator_universal_actions_payload(
            tenant_id=tenant_id,
            blocked=blocked,
            limit=limit,
            offset=offset,
        )
        return HTMLResponse(_universal_actions_console_html(read_model))

    @app.get("/operator/plan-review/read-model")
    def operator_plan_review_read_model(
        request: Request,
        tenant_id: str = "",
        plan_id: str = "",
        status: str = "",
        budget_gate: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        _validate_operator_plan_review_filters(
            status=status,
            budget_gate=budget_gate,
            search=search,
        )
        return build_operator_plan_review_read_model(
            plan_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            tenant_id=tenant_id,
            plan_id=plan_id,
            status=status,
            budget_gate=budget_gate,
            search=search,
            limit=limit,
            offset=offset,
        )

    @app.get("/operator/plan-review", response_class=HTMLResponse)
    def operator_plan_review_console(
        request: Request,
        tenant_id: str = "",
        plan_id: str = "",
        status: str = "",
        budget_gate: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        _validate_operator_plan_review_filters(
            status=status,
            budget_gate=budget_gate,
            search=search,
        )
        read_model = build_operator_plan_review_read_model(
            plan_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            tenant_id=tenant_id,
            plan_id=plan_id,
            status=status,
            budget_gate=budget_gate,
            search=search,
            limit=limit,
            offset=offset,
        )
        return HTMLResponse(render_operator_plan_review_html(read_model))

    @app.get("/operator/plan-review/budget/{tenant_id}/read-model")
    def operator_plan_review_budget_read_model(
        request: Request,
        tenant_id: str,
    ):
        _require_authority_operator(request)
        return build_operator_budget_report_read_model(
            tenant_budget_reporter,
            tenant_id=tenant_id,
        )

    @app.get("/operator/plan-review/budget/{tenant_id}", response_class=HTMLResponse)
    def operator_plan_review_budget_console(
        request: Request,
        tenant_id: str,
    ):
        _require_authority_operator(request)
        read_model = build_operator_budget_report_read_model(
            tenant_budget_reporter,
            tenant_id=tenant_id,
        )
        return HTMLResponse(render_operator_budget_report_html(read_model))

    @app.get("/operator/plan-review/receipts/read-model")
    def operator_plan_receipt_bundle_read_model(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        budget_gate: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        return build_operator_plan_receipt_bundle_read_model(
            plan_ledger=plan_ledger,
            command_ledger=command_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            tenant_id=tenant_id,
            status=status,
            budget_gate=budget_gate,
            search=search,
            limit=limit,
            offset=offset,
        )

    @app.get("/operator/plan-review/receipts", response_class=HTMLResponse)
    def operator_plan_receipt_bundle_console(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        budget_gate: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        read_model = build_operator_plan_receipt_bundle_read_model(
            plan_ledger=plan_ledger,
            command_ledger=command_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            tenant_id=tenant_id,
            status=status,
            budget_gate=budget_gate,
            search=search,
            limit=limit,
            offset=offset,
        )
        return HTMLResponse(render_operator_plan_receipt_bundle_html(read_model))

    @app.get("/operator/plan-review/{plan_id}/receipts/read-model")
    def operator_plan_receipt_export_read_model(
        request: Request,
        plan_id: str,
    ):
        _require_authority_operator(request)
        read_model = build_operator_plan_receipt_export_read_model(
            plan_ledger=plan_ledger,
            command_ledger=command_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            plan_id=plan_id,
        )
        if read_model["status"] == "not_found":
            raise HTTPException(404, detail="plan review history not found")
        return read_model

    @app.get("/operator/plan-review/{plan_id}/receipts", response_class=HTMLResponse)
    def operator_plan_receipt_export_console(
        request: Request,
        plan_id: str,
    ):
        _require_authority_operator(request)
        read_model = build_operator_plan_receipt_export_read_model(
            plan_ledger=plan_ledger,
            command_ledger=command_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            plan_id=plan_id,
        )
        if read_model["status"] == "not_found":
            raise HTTPException(404, detail="plan review history not found")
        return HTMLResponse(render_operator_plan_receipt_export_html(read_model))

    @app.get("/operator/plan-review/{plan_id}", response_class=HTMLResponse)
    def operator_plan_review_detail(
        request: Request,
        plan_id: str,
        tenant_id: str = "",
    ):
        _require_authority_operator(request)
        read_model = build_operator_plan_review_read_model(
            plan_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            tenant_id=tenant_id,
            plan_id=plan_id,
            limit=100,
            offset=0,
        )
        if read_model["count"] < 1:
            raise HTTPException(404, detail="plan review history not found")
        return HTMLResponse(render_operator_plan_review_detail_html(read_model))

    @app.get("/operator/approvals/read-model")
    def operator_approvals_read_model(
        request: Request,
        tenant_id: str = "",
        request_id: str = "",
        command_id: str = "",
        status: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        _validate_operator_approval_filters(status=status, search=search)
        return build_operator_approval_history_read_model(
            command_ledger,
            tenant_id=tenant_id,
            request_id=request_id,
            command_id=command_id,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )

    @app.get("/operator/approvals", response_class=HTMLResponse)
    def operator_approvals_console(
        request: Request,
        tenant_id: str = "",
        request_id: str = "",
        command_id: str = "",
        status: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        _validate_operator_approval_filters(status=status, search=search)
        read_model = build_operator_approval_history_read_model(
            command_ledger,
            tenant_id=tenant_id,
            request_id=request_id,
            command_id=command_id,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )
        return HTMLResponse(render_operator_approval_history_html(read_model))

    @app.get("/operator/approvals/{request_id}", response_class=HTMLResponse)
    def operator_approval_detail(
        request: Request,
        request_id: str,
        tenant_id: str = "",
    ):
        _require_authority_operator(request)
        read_model = build_operator_approval_history_read_model(
            command_ledger,
            tenant_id=tenant_id,
            request_id=request_id,
            limit=1,
            offset=0,
        )
        if read_model["count"] < 1:
            raise HTTPException(404, detail="approval history not found")
        return HTMLResponse(render_operator_approval_detail_html(read_model))

    @app.get("/operator/receipts/read-model")
    def operator_receipts_read_model(
        request: Request,
        tenant_id: str = "",
        command_id: str = "",
        receipt_type: str = "",
        receipt_status: str = "",
        task_status: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        _validate_operator_receipt_filters(
            receipt_type=receipt_type,
            task_status=task_status,
            search=search,
        )
        return build_operator_receipt_viewer_read_model(
            command_ledger,
            tenant_id=tenant_id,
            command_id=command_id,
            receipt_type=receipt_type,
            receipt_status=receipt_status,
            task_status=task_status,
            search=search,
            limit=limit,
            offset=offset,
        )

    @app.get("/operator/receipts", response_class=HTMLResponse)
    def operator_receipts_console(
        request: Request,
        tenant_id: str = "",
        command_id: str = "",
        receipt_type: str = "",
        receipt_status: str = "",
        task_status: str = "",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        _validate_operator_receipt_filters(
            receipt_type=receipt_type,
            task_status=task_status,
            search=search,
        )
        read_model = build_operator_receipt_viewer_read_model(
            command_ledger,
            tenant_id=tenant_id,
            command_id=command_id,
            receipt_type=receipt_type,
            receipt_status=receipt_status,
            task_status=task_status,
            search=search,
            limit=limit,
            offset=offset,
        )
        return HTMLResponse(render_operator_receipt_viewer_html(read_model))

    @app.get("/operator/receipts/{command_id}", response_class=HTMLResponse)
    def operator_receipt_detail(
        request: Request,
        command_id: str,
        tenant_id: str = "",
    ):
        _require_authority_operator(request)
        read_model = build_operator_receipt_viewer_read_model(
            command_ledger,
            tenant_id=tenant_id,
            command_id=command_id,
            limit=1,
            offset=0,
        )
        if read_model["count"] == 0:
            raise HTTPException(404, detail="command receipt group not found")
        return HTMLResponse(render_operator_receipt_detail_html(read_model))

    def _validate_operator_receipt_filters(
        *,
        receipt_type: str,
        task_status: str,
        search: str,
    ) -> None:
        normalized_receipt_type = receipt_type.strip()
        normalized_task_status = task_status.strip()
        normalized_search = search.strip()
        if normalized_receipt_type and normalized_receipt_type not in valid_receipt_types():
            raise HTTPException(
                400,
                detail="receipt_type must be one of: "
                + ", ".join(valid_receipt_types()),
            )
        if normalized_task_status and normalized_task_status not in valid_task_statuses():
            raise HTTPException(
                400,
                detail="task_status must be one of: "
                + ", ".join(valid_task_statuses()),
            )
        if len(normalized_search) > 128:
            raise HTTPException(
                400,
                detail="search must be 128 characters or fewer",
            )

    def _validate_operator_approval_filters(
        *,
        status: str,
        search: str,
    ) -> None:
        normalized_status = status.strip()
        if normalized_status and normalized_status not in valid_approval_statuses():
            raise HTTPException(
                400,
                detail="status must be one of: "
                + ", ".join(valid_approval_statuses()),
            )
        if len(search.strip()) > 128:
            raise HTTPException(
                400,
                detail="search must be 128 characters or fewer",
            )

    def _validate_operator_plan_review_filters(
        *,
        status: str,
        budget_gate: str,
        search: str,
    ) -> None:
        normalized_status = status.strip()
        normalized_budget_gate = budget_gate.strip()
        if normalized_status and normalized_status not in valid_plan_review_statuses():
            raise HTTPException(
                400,
                detail="status must be one of: "
                + ", ".join(valid_plan_review_statuses()),
            )
        if (
            normalized_budget_gate
            and normalized_budget_gate not in valid_plan_budget_gates()
        ):
            raise HTTPException(
                400,
                detail="budget_gate must be one of: "
                + ", ".join(valid_plan_budget_gates()),
            )
        if len(search.strip()) > 128:
            raise HTTPException(
                400,
                detail="search must be 128 characters or fewer",
            )

    @app.get("/operator/current-task/read-model")
    def operator_current_task_read_model(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        normalized_status = status.strip()
        if normalized_status and normalized_status not in valid_task_statuses():
            raise HTTPException(
                400,
                detail="status must be one of: "
                + ", ".join(valid_task_statuses()),
            )
        return build_current_task_read_model(
            command_ledger,
            tenant_id=tenant_id,
            status=normalized_status,
            limit=limit,
            offset=offset,
        )

    @app.get("/operator/current-task", response_class=HTMLResponse)
    def operator_current_task_console(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        normalized_status = status.strip()
        if normalized_status and normalized_status not in valid_task_statuses():
            raise HTTPException(
                400,
                detail="status must be one of: "
                + ", ".join(valid_task_statuses()),
            )
        read_model = build_current_task_read_model(
            command_ledger,
            tenant_id=tenant_id,
            status=normalized_status,
            limit=limit,
            offset=offset,
        )
        return HTMLResponse(render_current_task_html(read_model))

    async def _urlencoded_form_values(request: Request) -> dict[str, list[str]]:
        raw_form = (await request.body()).decode("utf-8", errors="replace")
        return parse_qs(raw_form, keep_blank_values=True)

    def _form_value(
        form: Mapping[str, list[str]],
        name: str,
        default: str = "",
    ) -> str:
        values = form.get(name)
        if not values:
            return default
        return str(values[0])

    @app.post("/operator/current-task/approval", response_class=HTMLResponse)
    async def operator_current_task_approval(request: Request):
        _require_authority_operator(request)
        form = await _urlencoded_form_values(request)
        request_id = _form_value(form, "request_id").strip()
        decision = _form_value(form, "decision").strip().lower()
        if not request_id:
            raise HTTPException(400, detail="request_id is required")
        if decision not in {"approve", "deny"}:
            raise HTTPException(400, detail="decision must be approve or deny")

        approval_request = router.lookup_approval_request(request_id)
        if approval_request is None:
            raise HTTPException(404, detail="approval request not found")
        if approval_request.status != ApprovalStatus.PENDING:
            raise HTTPException(
                409,
                detail=f"approval request is {approval_request.status.value}",
            )

        command = (
            command_ledger.get(approval_request.command_id)
            if approval_request.command_id
            else None
        )
        command_metadata: Mapping[str, Any] = {}
        if command is not None:
            raw_metadata = command.redacted_payload.get("metadata")
            if isinstance(raw_metadata, Mapping):
                command_metadata = raw_metadata
        plan_id = str(command_metadata.get("plan_id") or "").strip()

        resolver_sender_id = (
            "operator-current-task:"
            + sha256(request_id.encode("utf-8")).hexdigest()[:16]
        )
        router.register_tenant_mapping(
            TenantMapping(
                channel=approval_request.channel,
                sender_id=resolver_sender_id,
                tenant_id=approval_request.tenant_id,
                identity_id=f"operator-current-task-approval:{request_id}",
                roles=("tenant_member", "operator", "operator_current_task"),
                approval_authority=True,
                metadata={
                    "approval_request_id": request_id,
                    "operator_surface": "current_task",
                },
            )
        )

        approved = decision == "approve"
        approval_response = router.handle_external_approval_callback(
            request_id,
            approved=approved,
            resolver_channel=approval_request.channel,
            resolver_sender_id=resolver_sender_id,
        )
        if approval_response is None:
            raise HTTPException(404, detail="approval request not found")
        if approval_response.metadata.get("error") == "approval_context_denied":
            raise HTTPException(
                403,
                detail={
                    "error": "approval_context_denied",
                    "authority_reason": approval_response.metadata.get(
                        "authority_reason",
                        "",
                    ),
                    "required_roles": list(
                        approval_response.metadata.get("required_roles", ())
                    ),
                    "resolver_roles": list(
                        approval_response.metadata.get("resolver_roles", ())
                    ),
                },
            )

        action_status = "approval_approved" if approved else "approval_denied"
        if approved and plan_id:
            try:
                recovery_response = router.recover_waiting_plan(plan_id)
            except (KeyError, ValueError) as exc:
                action_status = (
                    "approval_approved_plan_recovery_blocked:"
                    f"{type(exc).__name__}"
                )
            else:
                if recovery_response.metadata.get("plan_terminal_certificate_id"):
                    action_status = "approval_approved_plan_recovered"
                else:
                    action_status = "approval_approved_plan_recovery_pending"

        read_model = build_current_task_read_model(
            command_ledger,
            tenant_id=approval_request.tenant_id,
        )
        read_model["operator_action_status"] = action_status
        return HTMLResponse(render_current_task_html(read_model))

    def _goal_intake_read_model_for_record(
        record: GoalIntakePreviewRecord,
        *,
        status: str | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> dict[str, Any]:
        return build_goal_intake_read_model(
            preview_id=record.preview_id,
            tenant_id=record.tenant_id,
            identity_id=record.identity_id,
            channel=record.channel,
            sender_id_present=bool(record.sender_id),
            sender_id_hash=record.sender_id_hash,
            status=status or record.status,
            goal_hash=record.goal_hash,
            preview=record.preview,
            decision=record.decision,
            decision_reason=record.decision_reason,
            handoff_message_id=record.handoff_message_id,
            handoff_response_body=record.handoff_response_body,
            handoff_response_metadata=record.handoff_response_metadata,
            error_code=error_code,
            error_message=error_message,
        )

    def _render_goal_intake_record(
        record: GoalIntakePreviewRecord,
        *,
        status: str | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> HTMLResponse:
        return HTMLResponse(
            render_goal_intake_html(
                _goal_intake_read_model_for_record(
                    record,
                    status=status,
                    error_code=error_code,
                    error_message=error_message,
                )
            )
        )

    def _render_goal_intake_missing_preview(preview_id: str) -> HTMLResponse:
        return HTMLResponse(
            render_goal_intake_html(
                build_goal_intake_read_model(
                    preview_id=preview_id,
                    status="blocked",
                    error_code="preview_not_found",
                    error_message="preview_id is not available for handoff",
                )
            )
        )

    def _json_safe_scalar(value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (list, tuple)):
            return [
                item
                if item is None or isinstance(item, (bool, int, float, str))
                else str(item)
                for item in value
            ]
        return str(value)

    def _goal_intake_public_response_metadata(
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        allowed_keys = {
            "error",
            "plan_id",
            "plan_error",
            "plan_failure_witness_id",
            "approval_required",
            "request_id",
            "command_id",
            "risk_tier",
            "delivery_status",
            "plan_terminal_certificate_id",
            "terminal_certificate_id",
            "response_allowed",
            "safe_default",
        }
        return {
            key: _json_safe_scalar(value)
            for key, value in metadata.items()
            if key in allowed_keys
        }

    def _goal_intake_public_response_body(metadata: Mapping[str, Any]) -> str:
        if metadata.get("error") == "plan_execution_failed":
            return "Governed plan handoff stopped before terminal closure."
        if metadata.get("approval_required") is True:
            request_id = str(metadata.get("request_id", ""))
            if request_id:
                return f"Governed command handoff requires approval: {request_id}"
            return "Governed command handoff requires approval."
        if metadata.get("plan_terminal_certificate_id"):
            return "Governed plan handoff reached terminal closure."
        if metadata.get("terminal_certificate_id"):
            return "Governed command handoff reached terminal closure."
        if metadata.get("command_id"):
            return "Governed command handoff was admitted."
        return "Governed handoff submitted."

    @app.get("/operator/goal-intake", response_class=HTMLResponse)
    def operator_goal_intake_console(request: Request):
        _require_authority_operator(request)
        return HTMLResponse(render_goal_intake_html(build_goal_intake_read_model()))

    @app.post("/operator/goal-intake/preview", response_class=HTMLResponse)
    async def operator_goal_intake_preview(request: Request):
        _require_authority_operator(request)
        form = await _urlencoded_form_values(request)
        goal = _form_value(form, "goal").strip()
        tenant_id = _form_value(form, "tenant_id").strip()
        identity_id = _form_value(form, "identity_id").strip()
        channel = _form_value(form, "channel", DEFAULT_GOAL_INTAKE_CHANNEL).strip()
        sender_id = _form_value(form, "sender_id", DEFAULT_GOAL_INTAKE_SENDER_ID).strip()
        if not channel:
            channel = DEFAULT_GOAL_INTAKE_CHANNEL
        if not sender_id:
            sender_id = DEFAULT_GOAL_INTAKE_SENDER_ID
        goal_hash = canonical_hash({"goal": goal}) if goal else ""
        sender_id_hash = canonical_hash({"channel": channel, "sender_id": sender_id})

        def _render_intake(
            *,
            status: str,
            preview: Mapping[str, Any] | None = None,
            error_code: str = "",
            error_message: str = "",
        ) -> HTMLResponse:
            return HTMLResponse(
                render_goal_intake_html(
                    build_goal_intake_read_model(
                        tenant_id=tenant_id,
                        identity_id=identity_id,
                        channel=channel,
                        sender_id_present=bool(sender_id),
                        sender_id_hash=sender_id_hash,
                        status=status,
                        goal_hash=goal_hash,
                        preview=preview,
                        error_code=error_code,
                        error_message=error_message,
                    )
                )
            )

        if not tenant_id or not identity_id:
            return _render_intake(
                status="blocked",
                error_code="missing_identity",
                error_message="tenant_id and identity_id are required",
            )
        if not goal:
            return _render_intake(
                status="blocked",
                error_code="missing_goal",
                error_message="goal is required",
            )

        message = GatewayMessage(
            message_id=f"goal-intake-{goal_hash[:16]}",
            channel=channel,
            sender_id=sender_id,
            body=goal,
            conversation_id=f"goal-intake:{tenant_id}:{identity_id}",
        )
        builder = CapabilityPlanBuilder(
            capability_passport_loader=command_ledger.capability_passport_for_intent
        )
        try:
            plan = builder.build(
                message=message.body,
                tenant_id=tenant_id,
                identity_id=identity_id,
            )
        except ValueError as exc:
            return _render_intake(
                status="blocked",
                error_code="plan_compile_rejected",
                error_message=f"capability plan compile rejected: {type(exc).__name__}",
            )
        if plan is None:
            return _render_intake(
                status="blocked",
                error_code="goal_not_compilable",
                error_message="goal did not match a governed capability pattern",
            )
        created_at = _clock()
        preview = preview_for_plan(plan=plan, created_at=created_at).to_dict()
        record = GoalIntakePreviewRecord(
            preview_id=str(preview["preview_id"]),
            plan_id=str(preview["plan_id"]),
            tenant_id=tenant_id,
            identity_id=identity_id,
            channel=channel,
            sender_id=sender_id,
            sender_id_hash=sender_id_hash,
            goal=goal,
            goal_hash=goal_hash,
            preview=preview,
            status="preview_ready",
            created_at=created_at,
        )
        goal_intake_preview_store.save(record)
        return _render_goal_intake_record(record)

    @app.post("/operator/goal-intake/deny", response_class=HTMLResponse)
    async def operator_goal_intake_deny(request: Request):
        _require_authority_operator(request)
        form = await _urlencoded_form_values(request)
        preview_id = _form_value(form, "preview_id").strip()
        record = goal_intake_preview_store.get(preview_id)
        if record is None:
            return _render_goal_intake_missing_preview(preview_id)
        if record.status != "preview_ready":
            return _render_goal_intake_record(
                record,
                status="blocked",
                error_code="preview_already_decided",
                error_message="preview already has a terminal intake decision",
            )
        decided = goal_intake_preview_store.decide(
            preview_id,
            status="denied",
            decision="denied",
            decided_at=_clock(),
            decision_reason="operator_denied",
        )
        return _render_goal_intake_record(decided)

    @app.post("/operator/goal-intake/approve", response_class=HTMLResponse)
    async def operator_goal_intake_approve(request: Request):
        _require_authority_operator(request)
        form = await _urlencoded_form_values(request)
        preview_id = _form_value(form, "preview_id").strip()
        record = goal_intake_preview_store.get(preview_id)
        if record is None:
            return _render_goal_intake_missing_preview(preview_id)
        if record.status != "preview_ready":
            return _render_goal_intake_record(
                record,
                status="blocked",
                error_code="preview_already_decided",
                error_message="preview already has a terminal intake decision",
            )

        internal_sender_id = f"goal-intake:{record.preview_id}"
        router.register_tenant_mapping(
            TenantMapping(
                channel=DEFAULT_GOAL_INTAKE_CHANNEL,
                sender_id=internal_sender_id,
                tenant_id=record.tenant_id,
                identity_id=record.identity_id,
                roles=("operator_goal_intake",),
                approval_authority=False,
                metadata={
                    "source_channel": record.channel,
                    "source_sender_id_hash": record.sender_id_hash,
                    "goal_hash": record.goal_hash,
                    "preview_id": record.preview_id,
                },
            )
        )
        response = router.handle_message(
            GatewayMessage(
                message_id=f"goal-intake-approve-{record.preview_id}",
                channel=DEFAULT_GOAL_INTAKE_CHANNEL,
                sender_id=internal_sender_id,
                body=record.goal,
                conversation_id=f"goal-intake:{record.tenant_id}:{record.identity_id}",
                metadata={
                    "goal_intake_preview_id": record.preview_id,
                    "goal_hash": record.goal_hash,
                    "source_channel": record.channel,
                    "source_sender_id_hash": record.sender_id_hash,
                },
            )
        )
        decided = goal_intake_preview_store.decide(
            preview_id,
            status="handoff_submitted",
            decision="approved",
            decided_at=_clock(),
            decision_reason="operator_approved",
            handoff_message_id=response.message_id,
            handoff_response_body=_goal_intake_public_response_body(response.metadata),
            handoff_response_metadata=_goal_intake_public_response_metadata(response.metadata),
        )
        return _render_goal_intake_record(decided)

    @app.get("/capability-fabric/admission-audits")
    def capability_fabric_admission_audits(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        limit: int = 100,
    ):
        _require_authority_operator(request)
        audits = command_ledger.capability_admission_audits(
            tenant_id=tenant_id,
            status=status,
            limit=limit,
        )
        return {
            "admission_audits": audits,
            "count": len(audits),
        }

    @app.get("/capability-fabric/capsule-admission-receipts")
    def capability_fabric_capsule_admission_receipts(
        request: Request,
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        receipts = tuple(reversed(capability_capsule_admission_receipts))
        if status:
            receipts = tuple(
                receipt for receipt in receipts
                if receipt.get("admission_status") == status
            )
        bounded_limit = max(1, min(int(limit), 500))
        bounded_offset = max(0, int(offset))
        page_items = list(receipts)[bounded_offset:bounded_offset + bounded_limit]
        return {
            "capsule_admission_receipts": page_items,
            "count": len(page_items),
            "total": len(receipts),
            "status_filter": status,
            "limit": bounded_limit,
            "offset": bounded_offset,
        }

    @app.post("/operator/physical-capability-promotion-receipts")
    async def operator_physical_capability_promotion_receipt(request: Request):
        _require_authority_operator(request)
        try:
            payload = await request.json()
            emission_request = _physical_promotion_receipt_request(
                payload,
                recorded_at_default=_clock(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(400, detail=str(exc)) from exc

        receipt, errors = emit_physical_capability_promotion_receipt(**emission_request)
        if receipt is None or errors:
            raise HTTPException(
                409,
                detail={
                    "ready": False,
                    "capability_id": emission_request["capability_id"],
                    "errors": list(errors),
                },
            )

        receipt_payload = receipt.to_json_dict()
        try:
            physical_capability_promotion_receipt_store.append(receipt_payload)
        except (OSError, ValueError) as exc:
            raise HTTPException(
                503,
                detail="physical_promotion_receipt_store_unavailable",
            ) from exc
        return {
            "ready": True,
            "receipt_id": receipt.receipt_id,
            "errors": [],
            "receipt": receipt_payload,
        }

    @app.get("/operator/physical-capability-promotion-receipts")
    def operator_physical_capability_promotion_receipts(
        request: Request,
        capability_id: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        try:
            page = physical_capability_promotion_receipt_store.list(
                capability_id=capability_id,
                status=status,
                limit=limit,
                offset=offset,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(
                503,
                detail="physical_promotion_receipt_store_unavailable",
            ) from exc
        return {
            "physical_capability_promotion_receipts": list(page.receipts),
            "count": len(page.receipts),
            "capability_id_filter": capability_id,
            "status_filter": status,
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
            "next_offset": page.next_offset,
        }

    @app.get("/operator/physical-capability-promotion-receipts/console", response_class=HTMLResponse)
    def operator_physical_capability_promotion_receipts_console(
        request: Request,
        capability_id: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _require_authority_operator(request)
        try:
            page = physical_capability_promotion_receipt_store.list(
                capability_id=capability_id,
                status=status,
                limit=limit,
                offset=offset,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(
                503,
                detail="physical_promotion_receipt_store_unavailable",
            ) from exc
        read_model = {
            "physical_capability_promotion_receipts": list(page.receipts),
            "count": len(page.receipts),
            "capability_id_filter": capability_id,
            "status_filter": status,
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
            "next_offset": page.next_offset,
        }
        return HTMLResponse(_physical_promotion_receipts_console_html(read_model))

    @app.get("/operator/capabilities/read-model")
    def operator_capabilities_read_model(
        request: Request,
        domain: str = "",
        risk_level: str = "",
        admission_status: str = "",
        audit_limit: int = 100,
        audit_offset: int = 0,
        include_improvement_portfolio: bool = False,
        improvement_candidate_limit: int = 5,
    ):
        _require_authority_operator(request)
        return build_operator_capability_read_model(
            capability_admission_gate=capability_admission_gate,
            command_ledger=command_ledger,
            plan_ledger=plan_ledger,
            domain=domain,
            risk_level=risk_level,
            admission_status=admission_status,
            audit_limit=audit_limit,
            audit_offset=audit_offset,
            include_improvement_portfolio=include_improvement_portfolio,
            improvement_generated_at=_clock(),
            improvement_candidate_limit=improvement_candidate_limit,
        )

    @app.get("/operator/capabilities/friction-control/read-model")
    def operator_capability_friction_control_read_model(
        request: Request,
        domain: str = "",
        risk_level: str = "",
    ):
        _require_authority_operator(request)
        return build_capability_friction_control_read_model(
            capability_admission_gate=capability_admission_gate,
            domain=domain,
            risk_level=risk_level,
        )

    @app.get("/operator/developer-workflow/read-model")
    def operator_developer_workflow_read_model(
        request: Request,
        tenant_id: str = "operator",
        actor_id: str = "codex-local-operator",
        domain: str = "software_dev",
        risk_level: str = "",
        include_local_sandbox_receipts: bool = False,
    ):
        _require_authority_operator(request)
        sandbox_receipt_bundle = _load_local_sandbox_receipt_bundle(
            include_local_sandbox_receipts=include_local_sandbox_receipts,
        )
        return build_developer_workflow_v1_run_read_model(
            capability_admission_gate=capability_admission_gate,
            software_receipt_store=software_receipt_store,
            sandbox_receipt_bundle=sandbox_receipt_bundle,
            tenant_id=tenant_id,
            actor_id=actor_id,
            domain=domain,
            risk_level=risk_level,
        )

    @app.get("/operator/developer-workflow", response_class=HTMLResponse)
    def operator_developer_workflow_console(
        request: Request,
        tenant_id: str = "operator",
        actor_id: str = "codex-local-operator",
        domain: str = "software_dev",
        risk_level: str = "",
        include_local_sandbox_receipts: bool = False,
    ):
        _require_authority_operator(request)
        sandbox_receipt_bundle = _load_local_sandbox_receipt_bundle(
            include_local_sandbox_receipts=include_local_sandbox_receipts,
        )
        read_model = build_developer_workflow_v1_run_read_model(
            capability_admission_gate=capability_admission_gate,
            software_receipt_store=software_receipt_store,
            sandbox_receipt_bundle=sandbox_receipt_bundle,
            tenant_id=tenant_id,
            actor_id=actor_id,
            domain=domain,
            risk_level=risk_level,
        )
        return HTMLResponse(render_developer_workflow_v1_run_html(read_model))

    def _operator_control_tower_snapshot(
        *,
        tenant_id: str,
        domain: str,
        risk_level: str,
        include_local_sandbox_receipts: bool = False,
        include_developer_workflow_operator_receipt: bool = False,
    ):
        sandbox_receipt_bundle = _load_local_sandbox_receipt_bundle(
            include_local_sandbox_receipts=include_local_sandbox_receipts,
        )
        local_sandbox_proof_report = _load_local_sandbox_proof_report(
            include_local_sandbox_receipts=include_local_sandbox_receipts,
        )
        local_rollback_summary_packet = _load_local_rollback_summary_packet(
            include_local_sandbox_receipts=include_local_sandbox_receipts,
        )
        local_rollback_approval_packet = _load_local_rollback_approval_packet(
            include_local_sandbox_receipts=include_local_sandbox_receipts,
        )
        local_rollback_execution_receipt = _load_local_rollback_execution_receipt(
            include_local_sandbox_receipts=include_local_sandbox_receipts,
        )
        local_developer_workflow_operator_receipt = None
        if include_developer_workflow_operator_receipt:
            try:
                local_developer_workflow_operator_receipt = _load_local_developer_workflow_operator_receipt()
            except HTTPException as exc:
                if exc.status_code == 404:
                    local_developer_workflow_operator_receipt = None
                else:
                    raise
        friction_control = build_capability_friction_control_read_model(
            capability_admission_gate=capability_admission_gate,
            domain=domain,
            risk_level=risk_level,
        )
        developer_workflow_run = build_developer_workflow_v1_run_read_model(
            capability_admission_gate=capability_admission_gate,
            software_receipt_store=software_receipt_store,
            sandbox_receipt_bundle=sandbox_receipt_bundle,
            tenant_id=tenant_id,
            domain=domain,
            risk_level=risk_level,
        )
        approval_history = build_operator_approval_history_read_model(
            command_ledger,
            tenant_id=tenant_id,
            limit=50,
        )
        receipt_viewer = build_operator_receipt_viewer_read_model(
            command_ledger,
            tenant_id=tenant_id,
            limit=50,
        )
        current_task = build_current_task_read_model(
            command_ledger,
            tenant_id=tenant_id,
            limit=50,
        )
        plan_review = build_operator_plan_review_read_model(
            plan_ledger,
            preview_store=goal_intake_preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            tenant_id=tenant_id,
            limit=50,
        )
        builder = OperatorControlTowerBuilder()
        capability_panel = _capability_friction_control_panel_read_model(friction_control)
        capability_metadata = capability_panel.get("metadata", {})
        if not isinstance(capability_metadata, Mapping):
            capability_metadata = {}
        sandbox_to_pr_policy = capability_metadata.get("sandbox_to_pr_policy", {})
        if not isinstance(sandbox_to_pr_policy, Mapping):
            sandbox_to_pr_policy = {}
        builder.attach_panel(
            OperatorPanelKind.CAPABILITY_HEALTH,
            capability_panel,
        )
        builder.attach_panel(
            OperatorPanelKind.APPROVALS,
            _approval_history_panel_read_model(approval_history),
        )
        builder.attach_panel(
            OperatorPanelKind.PROOF_EXPLORER,
            _receipt_viewer_panel_read_model(receipt_viewer),
        )
        builder.attach_panel(
            OperatorPanelKind.WORKFLOW_MONITOR,
            _workflow_monitor_panel_read_model(
                current_task=current_task,
                plan_review=plan_review,
                developer_workflow_run=developer_workflow_run,
                developer_workflow_operator_receipt=local_developer_workflow_operator_receipt,
                local_sandbox_proof_report=local_sandbox_proof_report,
                local_rollback_summary_packet=local_rollback_summary_packet,
                local_rollback_approval_packet=local_rollback_approval_packet,
                local_rollback_execution_receipt=local_rollback_execution_receipt,
                sandbox_to_pr_policy=sandbox_to_pr_policy,
            ),
        )
        return builder.build(tenant_id=tenant_id, generated_at=_clock())

    @app.get("/operator/control-tower/read-model")
    def operator_control_tower_read_model(
        request: Request,
        tenant_id: str = "operator",
        domain: str = "software_dev",
        risk_level: str = "",
        include_local_sandbox_receipts: bool = False,
        include_developer_workflow_operator_receipt: bool = False,
    ):
        _require_authority_operator(request)
        snapshot = _operator_control_tower_snapshot(
            tenant_id=tenant_id,
            domain=domain,
            risk_level=risk_level,
            include_local_sandbox_receipts=include_local_sandbox_receipts,
            include_developer_workflow_operator_receipt=include_developer_workflow_operator_receipt,
        )
        return operator_control_tower_snapshot_to_json_dict(snapshot)

    @app.get("/operator/control-tower/status-receipt")
    def operator_control_tower_status_receipt_route(
        request: Request,
        tenant_id: str = "operator",
        domain: str = "software_dev",
        risk_level: str = "",
        include_local_sandbox_receipts: bool = False,
        include_developer_workflow_operator_receipt: bool = False,
    ):
        _require_authority_operator(request)
        snapshot = _operator_control_tower_snapshot(
            tenant_id=tenant_id,
            domain=domain,
            risk_level=risk_level,
            include_local_sandbox_receipts=include_local_sandbox_receipts,
            include_developer_workflow_operator_receipt=include_developer_workflow_operator_receipt,
        )
        return operator_control_tower_status_receipt(snapshot)

    @app.get("/operator/control-tower/sandbox-patch-readiness/read-model")
    def operator_control_tower_sandbox_patch_readiness_read_model(
        request: Request,
    ):
        _require_authority_operator(request)
        return {
            "read_model_id": "operator_sandbox_patch_readiness_compact.read_model",
            "projection_only": True,
            "external_effects_allowed": False,
            "summary": sandbox_patch_readiness_compact_summary(),
            "source_ref": (
                "gateway.operator_sandbox_patch_readiness.SANDBOX_PATCH_READINESS_REGISTRY "
                "compact first-blocker projection"
            ),
        }

    @app.get("/operator/control-tower/developer-workflow-status/read-model")
    def operator_control_tower_developer_workflow_status_read_model(
        request: Request,
    ):
        _require_authority_operator(request)
        return _developer_workflow_status_read_model(_load_local_developer_workflow_operator_receipt())

    @app.get("/operator/control-tower/local-rollback-receipt/read-model")
    def operator_control_tower_local_rollback_receipt_read_model(
        request: Request,
        receipt_id: str = "execution",
    ):
        _require_authority_operator(request)
        return _local_rollback_receipt_view_model(receipt_id)

    @app.get("/operator/control-tower/local-rollback-receipt", response_class=HTMLResponse)
    def operator_control_tower_local_rollback_receipt_console(
        request: Request,
        receipt_id: str = "execution",
    ):
        _require_authority_operator(request)
        return HTMLResponse(_render_local_rollback_receipt_viewer(_local_rollback_receipt_view_model(receipt_id)))

    @app.get("/operator/control-tower", response_class=HTMLResponse)
    def operator_control_tower_console(
        request: Request,
        tenant_id: str = "operator",
        domain: str = "software_dev",
        risk_level: str = "",
        include_local_sandbox_receipts: bool = False,
        include_developer_workflow_operator_receipt: bool = False,
    ):
        _require_authority_operator(request)
        snapshot = _operator_control_tower_snapshot(
            tenant_id=tenant_id,
            domain=domain,
            risk_level=risk_level,
            include_local_sandbox_receipts=include_local_sandbox_receipts,
            include_developer_workflow_operator_receipt=include_developer_workflow_operator_receipt,
        )
        return HTMLResponse(render_operator_control_tower(snapshot))

    @app.get("/operator/code-intelligence/read-model")
    def operator_code_intelligence_read_model(
        request: Request,
        affected_files: str = "",
        task_summary: str = "",
        max_symbol_count: int = 40,
        max_test_count: int = 20,
        max_dependency_edges: int = 60,
        target_model: str = "unspecified",
    ):
        _require_authority_operator(request)
        try:
            return build_code_intelligence_operator_read_model(
                repository_root=os.environ.get("MULLU_CODE_INTELLIGENCE_ROOT", os.getcwd()),
                affected_files=parse_affected_files(affected_files),
                task_summary=task_summary,
                max_symbol_count=max_symbol_count,
                max_test_count=max_test_count,
                max_dependency_edges=max_dependency_edges,
                target_model=target_model,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    @app.get("/operator/github-operations/repo-status/read-model")
    def operator_github_operations_repo_status_read_model(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = surface_event_id or f"operator-github-repo-status:{repo}:{now}"
            return build_github_repo_status_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    @app.get("/operator/github-operations/patch-plan/read-model")
    def operator_github_operations_patch_plan_read_model(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = surface_event_id or f"operator-github-patch-plan:{repo}:{now}"
            return build_github_patch_plan_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    @app.get("/operator/github-operations/patch-plan", response_class=HTMLResponse)
    def operator_github_operations_patch_plan_panel(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = surface_event_id or f"operator-github-patch-plan:{repo}:{now}"
            read_model = build_github_patch_plan_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return HTMLResponse(render_github_patch_plan_workroom_html(read_model))

    @app.post("/operator/github-operations/patch-plan/draft")
    def operator_github_operations_patch_plan_draft(
        request: Request,
        req: GatewayGitHubPatchPlanDraftRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.requested_at or _clock()
            surface_event_id = req.surface_event_id or f"operator-github-patch-plan-draft:{req.repo}:{now}"
            draft_request = GitHubPatchPlanDraftRequest(
                actor_id=req.actor_id,
                workspace_id=req.workspace_id,
                repo=req.repo,
                objective=req.objective,
                evidence_refs=tuple(req.evidence_refs),
                evidence_summaries=tuple(req.evidence_summaries),
                verification_expectations=tuple(req.verification_expectations),
                surface_event_id=surface_event_id,
                requested_at=now,
                authority_ref=req.authority_ref,
                assumptions=tuple(req.assumptions),
            )
            draft = evaluate_github_patch_plan_draft(request=draft_request, clock=lambda: now)
            receipt = build_github_patch_plan_draft_receipt(
                request=draft_request,
                draft=draft,
                occurred_at=now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub patch plan draft request",
                    "error_code": "invalid_github_patch_plan_draft",
                    "governed": True,
                },
            ) from exc

        return {
            "github_patch_plan_draft": draft.to_json_dict(),
            "github_patch_plan_receipt": receipt.to_json_dict(),
            "outcome": "SolvedUnverified" if draft.status == "drafted" else "AwaitingEvidence",
            "governed": True,
            "execution_allowed": True,
            "live_connector_call_performed": False,
            "write_authority_granted": False,
            "effect_boundary": {
                "execution_allowed": True,
                "live_connector_execution_allowed": False,
                "github_call_allowed": False,
                "repository_read_allowed": False,
                "repository_mutation_allowed": False,
                "pull_request_mutation_allowed": False,
                "branch_push_allowed": False,
                "issue_creation_allowed": False,
                "review_submission_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
        }

    @app.get("/operator/github-operations/repo-status", response_class=HTMLResponse)
    def operator_github_operations_repo_status_panel(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = surface_event_id or f"operator-github-repo-status:{repo}:{now}"
            read_model = build_github_repo_status_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return HTMLResponse(render_github_repo_status_workroom_html(read_model))

    @app.post("/operator/github-operations/repo-status/read-admission/preview")
    def operator_github_operations_repo_status_read_admission_preview(
        request: Request,
        req: GatewayGitHubRepoStatusAdmissionPreviewRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.requested_at or _clock()
            surface_event_id = req.surface_event_id or f"operator-github-repo-status-admission:{req.repo}:{now}"
            admission = admit_github_repo_status_evidence_collection(
                GitHubRepoStatusEvidenceAdmissionRequest(
                    actor_id=req.actor_id,
                    workspace_id=req.workspace_id,
                    repo=req.repo,
                    requested_evidence_kinds=tuple(req.requested_evidence_kinds),
                    requested_at=now,
                    surface_event_id=surface_event_id,
                    authority_ref=req.authority_ref,
                    max_items_per_kind=req.max_items_per_kind,
                ),
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub repository status evidence admission preview",
                    "error_code": "invalid_github_repo_status_admission_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "github_repo_status_evidence_admission": admission.to_json_dict(),
            "outcome": "AwaitingEvidence",
            "governed": True,
            "execution_allowed": False,
            "live_connector_call_performed": False,
            "write_authority_granted": False,
        }

    @app.post("/operator/github-operations/repo-status/read-evidence")
    def operator_github_operations_repo_status_read_evidence(
        request: Request,
        req: GatewayGitHubRepoStatusEvidenceExecutionRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.requested_at or _clock()
            surface_event_id = req.surface_event_id or f"operator-github-repo-status-read:{req.repo}:{now}"
            admission = admit_github_repo_status_evidence_collection(
                GitHubRepoStatusEvidenceAdmissionRequest(
                    actor_id=req.actor_id,
                    workspace_id=req.workspace_id,
                    repo=req.repo,
                    requested_evidence_kinds=tuple(req.requested_evidence_kinds),
                    requested_at=now,
                    surface_event_id=surface_event_id,
                    authority_ref=req.authority_ref,
                    max_items_per_kind=req.max_items_per_kind,
                ),
                clock=lambda: now,
            )
            fetch_result = GitHubReadOnlyEvidenceFetcher(
                access_token=req.access_token,
                timeout_seconds=req.timeout_seconds,
            ).fetch_repo_status(admission, clock=lambda: now)
            summary = evaluate_github_repo_status_summary(fetch_result=fetch_result, clock=lambda: now)
            receipt = build_github_repo_status_summary_receipt(
                fetch_result,
                summary=summary,
                actor_id=req.actor_id,
                surface_event_id=surface_event_id,
                occurred_at=now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub repository status evidence execution",
                    "error_code": "invalid_github_repo_status_evidence_execution",
                    "governed": True,
                },
            ) from exc
        except GitHubReadOnlyEvidenceFetchError as exc:
            raise HTTPException(
                502,
                detail={
                    "error": "GitHub repository status evidence execution failed",
                    "error_code": str(exc),
                    "governed": True,
                    "actions_blocked": [
                        "create_issue_without_explicit_approval",
                        "post_github_comment_without_write_admission",
                        "mutate_repository_without_write_admission",
                        "trigger_workflow_without_explicit_approval",
                        "claim_release_ready_without_required_evidence",
                    ],
                },
            ) from exc

        return {
            "github_repo_status_evidence_admission": admission.to_json_dict(),
            "github_repo_status_evidence_fetch_result": fetch_result.to_json_dict(),
            "github_repo_status_summary": summary.to_json_dict(),
            "github_repo_status_receipt": receipt.to_json_dict(),
            "outcome": fetch_result.solver_outcome,
            "governed": True,
            "execution_allowed": True,
            "live_connector_call_performed": True,
            "write_authority_granted": False,
            "effect_boundary": {
                "execution_allowed": True,
                "live_connector_execution_allowed": True,
                "github_call_allowed": True,
                "repository_read_allowed": True,
                "repository_mutation_allowed": False,
                "pull_request_mutation_allowed": False,
                "branch_push_allowed": False,
                "issue_creation_allowed": False,
                "review_submission_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
        }

    @app.get("/operator/github-operations/actions-failure/read-model")
    def operator_github_operations_actions_failure_read_model(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        workflow_run_id: int = 1,
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = (
                surface_event_id
                or f"operator-github-actions-failure:{repo}#{workflow_run_id}:{now}"
            )
            return build_github_actions_failure_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                workflow_run_id=workflow_run_id,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    @app.get("/operator/github-operations/actions-failure", response_class=HTMLResponse)
    def operator_github_operations_actions_failure_panel(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        workflow_run_id: int = 1,
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = (
                surface_event_id
                or f"operator-github-actions-failure:{repo}#{workflow_run_id}:{now}"
            )
            read_model = build_github_actions_failure_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                workflow_run_id=workflow_run_id,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return HTMLResponse(render_github_actions_failure_workroom_html(read_model))

    @app.post("/operator/github-operations/actions-failure/read-admission/preview")
    def operator_github_operations_actions_failure_read_admission_preview(
        request: Request,
        req: GatewayGitHubActionsFailureAdmissionPreviewRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.requested_at or _clock()
            surface_event_id = (
                req.surface_event_id
                or f"operator-github-actions-failure-admission:{req.repo}#{req.workflow_run_id}:{now}"
            )
            admission = admit_github_actions_failure_evidence_collection(
                GitHubActionsFailureEvidenceAdmissionRequest(
                    actor_id=req.actor_id,
                    workspace_id=req.workspace_id,
                    repo=req.repo,
                    workflow_run_id=req.workflow_run_id,
                    requested_evidence_kinds=tuple(req.requested_evidence_kinds),
                    requested_at=now,
                    surface_event_id=surface_event_id,
                    authority_ref=req.authority_ref,
                    max_failed_job_logs=req.max_failed_job_logs,
                ),
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub Actions failure evidence admission preview",
                    "error_code": "invalid_github_actions_failure_admission_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "github_actions_failure_evidence_admission": admission.to_json_dict(),
            "outcome": "AwaitingEvidence",
            "governed": True,
            "execution_allowed": False,
            "live_connector_call_performed": False,
            "write_authority_granted": False,
        }

    @app.post("/operator/github-operations/actions-failure/read-evidence")
    def operator_github_operations_actions_failure_read_evidence(
        request: Request,
        req: GatewayGitHubActionsFailureEvidenceExecutionRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.requested_at or _clock()
            surface_event_id = (
                req.surface_event_id
                or f"operator-github-actions-failure-read:{req.repo}#{req.workflow_run_id}:{now}"
            )
            admission = admit_github_actions_failure_evidence_collection(
                GitHubActionsFailureEvidenceAdmissionRequest(
                    actor_id=req.actor_id,
                    workspace_id=req.workspace_id,
                    repo=req.repo,
                    workflow_run_id=req.workflow_run_id,
                    requested_evidence_kinds=tuple(req.requested_evidence_kinds),
                    requested_at=now,
                    surface_event_id=surface_event_id,
                    authority_ref=req.authority_ref,
                    max_failed_job_logs=req.max_failed_job_logs,
                ),
                clock=lambda: now,
            )
            fetch_result = GitHubReadOnlyEvidenceFetcher(
                access_token=req.access_token,
                timeout_seconds=req.timeout_seconds,
            ).fetch_actions_failure(admission, clock=lambda: now)
            diagnosis = evaluate_github_actions_failure_diagnosis(
                fetch_result=fetch_result,
                clock=lambda: now,
            )
            receipt = build_github_actions_failure_diagnosis_receipt(
                fetch_result,
                diagnosis=diagnosis,
                actor_id=req.actor_id,
                surface_event_id=surface_event_id,
                occurred_at=now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub Actions failure evidence execution",
                    "error_code": "invalid_github_actions_failure_evidence_execution",
                    "governed": True,
                },
            ) from exc
        except GitHubReadOnlyEvidenceFetchError as exc:
            raise HTTPException(
                502,
                detail={
                    "error": "GitHub Actions failure evidence execution failed",
                    "error_code": str(exc),
                    "governed": True,
                    "actions_blocked": [
                        "rerun_workflow_without_explicit_approval",
                        "cancel_workflow_without_explicit_approval",
                        "dispatch_workflow_without_explicit_approval",
                        "post_github_comment_without_write_admission",
                        "mutate_repository_without_write_admission",
                    ],
                },
            ) from exc

        return {
            "github_actions_failure_evidence_admission": admission.to_json_dict(),
            "github_actions_failure_evidence_fetch_result": fetch_result.to_json_dict(),
            "github_actions_failure_diagnosis": diagnosis.to_json_dict(),
            "github_actions_failure_receipt": receipt.to_json_dict(),
            "outcome": fetch_result.solver_outcome,
            "governed": True,
            "execution_allowed": True,
            "live_connector_call_performed": True,
            "write_authority_granted": False,
            "effect_boundary": {
                "execution_allowed": True,
                "live_connector_execution_allowed": True,
                "github_call_allowed": True,
                "repository_read_allowed": True,
                "repository_mutation_allowed": False,
                "pull_request_mutation_allowed": False,
                "branch_push_allowed": False,
                "issue_creation_allowed": False,
                "review_submission_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
        }

    @app.get("/operator/github-operations/pr-safety/read-model")
    def operator_github_operations_pr_safety_read_model(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        pull_request_number: int = 1,
        evidence_refs: str = "",
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = (
                surface_event_id
                or f"operator-github-pr-safety:{repo}#{pull_request_number}:{now}"
            )
            return build_github_pr_safety_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                pull_request_number=pull_request_number,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                evidence_refs=_parse_github_workroom_evidence_refs(evidence_refs),
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    @app.get("/operator/github-operations/pr-safety", response_class=HTMLResponse)
    def operator_github_operations_pr_safety_panel(
        request: Request,
        repo: str = "tamirat-wubie/mullu-control-plane",
        pull_request_number: int = 1,
        evidence_refs: str = "",
        actor_id: str = "operator:gateway",
        workspace_id: str = "workspace:mullusi-control-plane",
        surface_event_id: str = "",
        occurred_at: str = "",
    ):
        _require_authority_operator(request)
        try:
            now = occurred_at or _clock()
            normalized_surface_event_id = (
                surface_event_id
                or f"operator-github-pr-safety:{repo}#{pull_request_number}:{now}"
            )
            read_model = build_github_pr_safety_workroom_read_model(
                actor_id=actor_id,
                workspace_id=workspace_id,
                repo=repo,
                pull_request_number=pull_request_number,
                surface_event_id=normalized_surface_event_id,
                occurred_at=now,
                evidence_refs=_parse_github_workroom_evidence_refs(evidence_refs),
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return HTMLResponse(render_github_pr_safety_workroom_html(read_model))

    @app.post("/operator/github-operations/pr-safety/read-admission/preview")
    def operator_github_operations_pr_safety_read_admission_preview(
        request: Request,
        req: GatewayGitHubReadOnlyEvidenceAdmissionPreviewRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.requested_at or _clock()
            surface_event_id = (
                req.surface_event_id
                or f"operator-github-read-admission:{req.repo}#{req.pull_request_number}:{now}"
            )
            admission_request = GitHubReadOnlyEvidenceAdmissionRequest(
                actor_id=req.actor_id,
                workspace_id=req.workspace_id,
                repo=req.repo,
                pull_request_number=req.pull_request_number,
                requested_evidence_kinds=tuple(req.requested_evidence_kinds),
                requested_at=now,
                surface_event_id=surface_event_id,
                authority_ref=req.authority_ref,
            )
            admission = admit_github_read_only_evidence_collection(
                admission_request,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub read-only evidence admission preview",
                    "error_code": "invalid_github_read_only_evidence_admission_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "github_read_only_evidence_admission": admission.to_json_dict(),
            "outcome": "AwaitingEvidence",
            "governed": True,
            "execution_allowed": False,
            "live_connector_call_performed": False,
            "write_authority_granted": False,
        }

    @app.post("/operator/github-operations/pr-safety/read-evidence")
    def operator_github_operations_pr_safety_read_evidence(
        request: Request,
        req: GatewayGitHubReadOnlyEvidenceExecutionRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.requested_at or _clock()
            surface_event_id = (
                req.surface_event_id
                or f"operator-github-read-evidence:{req.repo}#{req.pull_request_number}:{now}"
            )
            admission = admit_github_read_only_evidence_collection(
                GitHubReadOnlyEvidenceAdmissionRequest(
                    actor_id=req.actor_id,
                    workspace_id=req.workspace_id,
                    repo=req.repo,
                    pull_request_number=req.pull_request_number,
                    requested_evidence_kinds=tuple(req.requested_evidence_kinds),
                    requested_at=now,
                    surface_event_id=surface_event_id,
                    authority_ref=req.authority_ref,
                ),
                clock=lambda: now,
            )
            fetch_result = GitHubReadOnlyEvidenceFetcher(
                access_token=req.access_token,
                timeout_seconds=req.timeout_seconds,
            ).fetch(admission, clock=lambda: now)
            fetch_receipt = build_github_read_only_evidence_fetch_receipt(
                fetch_result,
                actor_id=req.actor_id,
                surface_event_id=surface_event_id,
                occurred_at=now,
            )
            pr_safety_projection = build_pr_safety_projection_from_github_fetch_receipt(
                fetch_receipt=fetch_receipt,
                actor_id=req.actor_id,
                workspace_id=req.workspace_id,
                repo=req.repo,
                pull_request_number=req.pull_request_number,
                surface_event_id=f"{surface_event_id}:pr-safety",
                occurred_at=now,
                clock=lambda: now,
            )
            pr_safety_judgment = evaluate_github_pr_safety_judgment(
                fetch_result=fetch_result,
                fetch_receipt=fetch_receipt,
                clock=lambda: now,
            )
            receipt_storage = persist_github_read_only_evidence_receipt_bundle(
                receipt_store_root=Path(
                    os.environ.get(
                        "MULLU_GITHUB_WORKROOM_RECEIPT_DIR",
                        ".tmp/github-operations-workroom/receipts",
                    )
                ),
                admission=admission,
                fetch_result=fetch_result,
                fetch_receipt=fetch_receipt,
                pr_safety_projection=pr_safety_projection,
                pr_safety_judgment=pr_safety_judgment,
                stored_at=now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub read-only evidence execution",
                    "error_code": "invalid_github_read_only_evidence_execution",
                    "governed": True,
                },
            ) from exc
        except GitHubReadOnlyEvidenceFetchError as exc:
            raise HTTPException(
                502,
                detail={
                    "error": "GitHub read-only evidence execution failed",
                    "error_code": str(exc),
                    "governed": True,
                    "actions_blocked": [
                        "merge_pull_request_without_explicit_approval",
                        "deploy_release_without_release_witness",
                        "delete_branch_without_explicit_approval",
                        "post_github_comment_without_write_admission",
                    ],
                },
            ) from exc

        return {
            "github_read_only_evidence_admission": admission.to_json_dict(),
            "github_read_only_evidence_fetch_result": fetch_result.to_json_dict(),
            "github_read_only_evidence_receipt": fetch_receipt.to_json_dict(),
            "github_read_only_evidence_receipt_storage": receipt_storage.to_json_dict(),
            "github_pr_safety_projection": pr_safety_projection.to_json_dict(),
            "github_pr_safety_judgment": pr_safety_judgment.to_json_dict(),
            "outcome": fetch_result.solver_outcome,
            "governed": True,
            "execution_allowed": True,
            "live_connector_call_performed": True,
            "write_authority_granted": False,
            "merge_authority_granted": False,
            "effect_boundary": {
                "execution_allowed": True,
                "live_connector_execution_allowed": True,
                "github_call_allowed": True,
                "repository_read_allowed": True,
                "repository_mutation_allowed": False,
                "pull_request_mutation_allowed": False,
                "branch_push_allowed": False,
                "issue_creation_allowed": False,
                "review_submission_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
        }

    @app.get("/operator/github-operations/pr-safety/read-evidence/receipts/{receipt_filename}")
    def operator_github_operations_pr_safety_read_evidence_receipt(
        request: Request,
        receipt_filename: str,
    ):
        _require_authority_operator(request)
        try:
            return read_github_read_only_evidence_receipt_bundle(
                receipt_store_root=Path(
                    os.environ.get(
                        "MULLU_GITHUB_WORKROOM_RECEIPT_DIR",
                        ".tmp/github-operations-workroom/receipts",
                    )
                ),
                receipt_filename=receipt_filename,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                404,
                detail={
                    "error": "GitHub read-only evidence receipt not found",
                    "error_code": "github_read_only_evidence_receipt_not_found",
                    "governed": True,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub read-only evidence receipt request",
                    "error_code": "invalid_github_read_only_evidence_receipt_request",
                    "governed": True,
                },
            ) from exc

    @app.post("/operator/github-operations/pr-safety/preview")
    def operator_github_operations_pr_safety_preview(
        request: Request,
        req: GatewayGitHubPrSafetyWorkroomPreviewRequest,
    ):
        _require_authority_operator(request)
        try:
            now = req.occurred_at or _clock()
            surface_event_id = (
                req.surface_event_id
                or f"operator-github-pr-safety:{req.repo}#{req.pull_request_number}:{now}"
            )
            workroom_request = GitHubPrSafetyWorkroomRequest(
                actor_id=req.actor_id,
                workspace_id=req.workspace_id,
                repo=req.repo,
                pull_request_number=req.pull_request_number,
                surface_event_id=surface_event_id,
                occurred_at=now,
                evidence_refs=tuple(req.evidence_refs),
                channel_id=req.channel_id,
                trace_ref=req.trace_ref,
                authority_ref=req.authority_ref,
                assumptions=tuple(req.assumptions)
                or (
                    "Evidence references are already authorized for this actor and workspace.",
                    "This projection does not perform live GitHub reads or writes.",
                ),
                metadata=req.metadata,
            )
            projection = build_github_pr_safety_workroom_projection(
                workroom_request,
                clock=lambda: now,
            )
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid GitHub Operations Workroom PR safety preview",
                    "error_code": "invalid_github_operations_pr_safety_preview",
                    "governed": True,
                },
            ) from exc

        return {
            "github_operations_workroom_projection": projection.to_json_dict(),
            "receipt": projection.receipt.to_json_dict(),
            "outcome": "AwaitingEvidence",
            "effect_boundary": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "github_call_allowed": False,
                "repository_read_allowed": False,
                "repository_mutation_allowed": False,
                "pull_request_mutation_allowed": False,
                "branch_push_allowed": False,
                "issue_creation_allowed": False,
                "review_submission_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
            },
            "governed": True,
            "execution_allowed": False,
        }

    @app.get("/operator/capabilities", response_class=HTMLResponse)
    def operator_capabilities_console(
        request: Request,
        domain: str = "",
        risk_level: str = "",
        admission_status: str = "",
        audit_limit: int = 100,
        audit_offset: int = 0,
        include_improvement_portfolio: bool = False,
        improvement_candidate_limit: int = 5,
    ):
        _require_authority_operator(request)
        read_model = build_operator_capability_read_model(
            capability_admission_gate=capability_admission_gate,
            command_ledger=command_ledger,
            plan_ledger=plan_ledger,
            domain=domain,
            risk_level=risk_level,
            admission_status=admission_status,
            audit_limit=audit_limit,
            audit_offset=audit_offset,
            include_improvement_portfolio=include_improvement_portfolio,
            improvement_generated_at=_clock(),
            improvement_candidate_limit=improvement_candidate_limit,
        )
        return HTMLResponse(render_operator_capability_console(read_model))

    @app.get("/commands/{command_id}/capability-admission")
    def command_capability_admission(command_id: str, request: Request):
        _require_authority_operator(request)
        audit = command_ledger.capability_admission_audit_for(command_id)
        if audit is None:
            raise HTTPException(404, detail="command capability admission audit not found")
        return audit

    @app.get("/mcp/operator/read-model")
    def mcp_operator_read_model(
        request: Request,
        capability_id: str = "",
        audit_status: str = "",
        audit_limit: int = 100,
        audit_offset: int = 0,
    ):
        _require_authority_operator(request)
        return build_mcp_operator_read_model(
            capability_admission_gate=capability_admission_gate,
            authority_mesh_store=authority_mesh_store,
            mcp_executor=mcp_executor,
            mcp_gateway_import=mcp_gateway_import,
            capability_id=capability_id,
            audit_status=audit_status,
            audit_limit=audit_limit,
            audit_offset=audit_offset,
        )

    @app.get("/mcp/operator/evidence-bundles/{command_id}")
    def mcp_operator_evidence_bundle(command_id: str, request: Request):
        _require_authority_operator(request)
        if mcp_executor is None or not hasattr(mcp_executor, "export_evidence_bundle"):
            raise HTTPException(404, detail="MCP executor evidence export is not available")
        try:
            bundle = mcp_executor.export_evidence_bundle(command_id=command_id)
        except KeyError as exc:
            raise HTTPException(404, detail="MCP execution evidence bundle not found") from exc
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return asdict(bundle)

    @app.get("/capability-plans/read-model")
    def capability_plans_read_model(
        request: Request,
        recovery_action: str = "",
        failed_witness_limit: int = 100,
        failed_witness_offset: int = 0,
        recovery_attempt_status: str = "",
        recovery_attempt_limit: int = 100,
        recovery_attempt_offset: int = 0,
    ):
        _require_authority_operator(request)
        return {
            "enabled": True,
            **plan_ledger.read_model(
                recovery_action=recovery_action,
                failed_witness_limit=_bounded_read_model_limit(failed_witness_limit),
                failed_witness_offset=_bounded_read_model_offset(failed_witness_offset),
                recovery_attempt_status=recovery_attempt_status,
                recovery_attempt_limit=_bounded_read_model_limit(recovery_attempt_limit),
                recovery_attempt_offset=_bounded_read_model_offset(recovery_attempt_offset),
            ),
        }

    @app.get("/capability-plans/{plan_id}/closure")
    def capability_plan_closure(plan_id: str, request: Request):
        _require_authority_operator(request)
        certificate = plan_ledger.certificate_for(plan_id)
        if certificate is None:
            raise HTTPException(404, detail="plan terminal certificate not found")
        witnesses = plan_ledger.witnesses_for(plan_id)
        recovery_attempts = plan_ledger.recovery_attempts_for(plan_id)
        return {
            "plan_id": plan_id,
            "plan_terminal_certificate": asdict(certificate),
            "plan_evidence_bundle": asdict(plan_ledger.export_evidence_bundle(plan_id=plan_id)),
            "plan_witnesses": [asdict(witness) for witness in witnesses],
            "plan_recovery_attempts": [asdict(attempt) for attempt in recovery_attempts],
            "witness_count": len(witnesses),
            "recovery_attempt_count": len(recovery_attempts),
        }

    @app.post("/capability-plans/{plan_id}/recover")
    def recover_capability_plan(plan_id: str, request: Request):
        _require_authority_operator(request)
        try:
            response = router.recover_waiting_plan(plan_id)
        except KeyError as exc:
            raise HTTPException(404, detail="failed plan witness not found") from exc
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        return {
            "status": "recovered" if response.metadata.get("plan_terminal_certificate_id") else "not_recovered",
            "response": asdict(response),
            "plan_id": plan_id,
            "plan_terminal_certificate_id": response.metadata.get("plan_terminal_certificate_id"),
            "plan_error": response.metadata.get("plan_error", ""),
        }

    @app.get("/observability/summary")
    def observability_summary(request: Request):
        _require_authority_operator(request)
        return router.observability_snapshot()

    @app.get("/observability/traces/{trace_id}")
    def observability_trace(trace_id: str, request: Request):
        _require_authority_operator(request)
        trace = router.observability_trace(trace_id)
        if trace is None:
            raise HTTPException(404, detail="trace not found")
        return trace

    @app.get("/anchors/latest")
    def latest_anchor():
        anchors = command_ledger.list_anchors(limit=1)
        if not anchors:
            return {
                "anchor_present": False,
                "anchor_id": "",
                "from_event_hash": "",
                "to_event_hash": "",
                "event_count": 0,
                "merkle_root": "",
                "signature": "",
                "signature_key_id": "",
                "anchored_at": "",
                "governed": True,
            }
        anchor = anchors[0]
        return {
            "anchor_present": True,
            "anchor_id": anchor.anchor_id,
            "from_event_hash": anchor.from_event_hash,
            "to_event_hash": anchor.to_event_hash,
            "event_count": anchor.event_count,
            "merkle_root": anchor.merkle_root,
            "signature": f"hmac-sha256:{anchor.signature}",
            "signature_key_id": anchor.signature_key_id,
            "anchored_at": anchor.anchored_at,
            "governed": True,
        }

    @app.post("/deployment/tenant-mappings")
    async def deployment_tenant_mapping(request: Request):
        """Persist a deployment-authorized channel-to-tenant binding."""
        _require_deployment_authority(request)
        payload = await _request_json_mapping(request)
        raw_roles = payload.get("roles", ())
        if isinstance(raw_roles, str) or not isinstance(raw_roles, (list, tuple)):
            raise HTTPException(400, detail="roles must be an array")
        raw_platform_roles = payload.get("platform_roles", raw_roles)
        if isinstance(raw_platform_roles, str) or not isinstance(raw_platform_roles, (list, tuple)):
            raise HTTPException(400, detail="platform_roles must be an array")
        try:
            mapping = TenantMapping(
                channel=_required_text(payload, "channel"),
                sender_id=_required_text(payload, "sender_id"),
                tenant_id=_required_text(payload, "tenant_id"),
                identity_id=_required_text(payload, "identity_id"),
                roles=tuple(str(role).strip() for role in raw_roles if str(role).strip()),
                approval_authority=_payload_bool(
                    payload,
                    "approval_authority",
                    default=False,
                ),
                policy_version=_optional_text(
                    payload,
                    "policy_version",
                    default="tenant-identity-v1",
                ),
                metadata=dict(_optional_mapping(payload, "metadata")),
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        platform_tenant = _seed_platform_tenant_gate_for_mapping(mapping)
        platform_identity = _seed_platform_identity_for_mapping(
            mapping,
            platform_roles=tuple(str(role).strip() for role in raw_platform_roles if str(role).strip()),
        )
        tenant_identity_store.save(mapping)
        resolved = tenant_identity_store.resolve(mapping.channel, mapping.sender_id)
        if resolved is None:
            raise HTTPException(500, detail="tenant mapping persistence failed")
        return {
            "status": "stored",
            "channel": resolved.channel,
            "sender_id": resolved.sender_id,
            "tenant_id": resolved.tenant_id,
            "identity_id": resolved.identity_id,
            "roles": list(resolved.roles),
            "approval_authority": resolved.approval_authority,
            "policy_version": resolved.policy_version,
            "created_at": resolved.created_at,
            "active_mappings": tenant_identity_store.count(),
            "platform_tenant": platform_tenant,
            "platform_identity": platform_identity,
            "governed": True,
        }

    @app.get("/evidence/bundles/{command_id}")
    def command_evidence_bundle(command_id: str, request: Request):
        _require_authority_operator(request)
        try:
            bundle = build_command_trust_bundle(
                command_ledger=command_ledger,
                command_id=command_id,
                deployment_id=_deployment_id(),
                commit_sha=_commit_sha(),
                signing_secret=os.environ.get("MULLU_TRUST_LEDGER_SECRET", "local-trust-ledger-secret"),
                signature_key_id=os.environ.get("MULLU_TRUST_LEDGER_KEY_ID", "trust-ledger-local"),
                clock=_clock,
            )
        except KeyError as exc:
            raise HTTPException(404, detail="command not found") from exc
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        return bundle.to_json_dict()

    # Store references for testing
    app.state.router = router
    app.state.command_ledger = command_ledger
    app.state.tenant_identity_store = tenant_identity_store
    app.state.authority_mesh_store = authority_mesh_store
    app.state.authority_obligation_mesh = authority_obligation_mesh
    app.state.authority_operator_audit_events = authority_operator_audit_events
    app.state.capability_capsule_admission_receipts = capability_capsule_admission_receipts
    app.state.physical_capability_promotion_receipt_store = physical_capability_promotion_receipt_store
    app.state.session_mgr = session_mgr
    app.state.event_log = event_log
    app.state.orgos_kernel = orgos_kernel
    app.state.orgos_case_event_log = orgos_case_event_log
    app.state.capability_admission_gate = capability_admission_gate
    app.state.mcp_capability_entries = mcp_capability_entries
    app.state.mcp_executor = mcp_executor
    app.state.mcp_authority_records = mcp_authority_records
    app.state.mcp_gateway_import = mcp_gateway_import
    app.state.axiomworld_adapter = bound_axiomworld_adapter
    app.state.plan_ledger = plan_ledger
    app.state.goal_intake_preview_store = goal_intake_preview_store
    app.state.tenant_budget_reporter = tenant_budget_reporter
    app.state.observability_recorder = observability_recorder
    app.state.federated_control_plane = federated_control_plane
    app.state.verifier = verifier
    app.state.agentic_service_harness_read_model_source = agentic_service_harness_read_model_source

    return app


def _capsule_admission_request(
    payload: Any,
) -> tuple[DomainCapsule, tuple[CapabilityRegistryEntry, ...], tuple[CapabilityCertificationHandoff, ...], bool]:
    if not isinstance(payload, Mapping):
        raise ValueError("capsule_admission_request_must_be_object")
    capsule_payload = _required_mapping(payload, "capsule")
    raw_entries = payload.get("registry_entries")
    raw_handoffs = payload.get("handoffs")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("capsule_admission_registry_entries_required")
    if not isinstance(raw_handoffs, list) or not raw_handoffs:
        raise ValueError("capsule_admission_handoffs_required")
    return (
        DomainCapsule.from_mapping(capsule_payload),
        tuple(CapabilityRegistryEntry.from_mapping(_mapping_item(raw_entry, "registry_entries")) for raw_entry in raw_entries),
        tuple(_certification_handoff_from_mapping(_mapping_item(raw_handoff, "handoffs")) for raw_handoff in raw_handoffs),
        _payload_bool(payload, "require_production_ready", default=True),
    )


def _certification_handoff_from_mapping(payload: Mapping[str, Any]) -> CapabilityCertificationHandoff:
    bundle_payload = _required_mapping(payload, "maturity_evidence_bundle")
    raw_evidence_refs = payload.get("required_evidence_refs", ())
    if not isinstance(raw_evidence_refs, (list, tuple)):
        raise ValueError("capsule_admission_handoff_required_evidence_refs_must_be_array")
    raw_physical_safety_refs = payload.get("physical_live_safety_evidence_refs", {})
    if not isinstance(raw_physical_safety_refs, Mapping):
        raise ValueError("capsule_admission_handoff_physical_safety_refs_must_be_object")
    return CapabilityCertificationHandoff(
        package_id=_required_text(payload, "package_id"),
        capability_id=_required_text(payload, "capability_id"),
        package_hash=_required_text(payload, "package_hash"),
        maturity_evidence_bundle=CapabilityCertificationEvidenceBundle.from_mapping(bundle_payload),
        required_evidence_refs=tuple(str(value) for value in raw_evidence_refs),
        physical_live_safety_evidence_refs={
            str(key): str(value) for key, value in raw_physical_safety_refs.items()
        },
        handoff_hash=_required_text(payload, "handoff_hash"),
    )


def _handoff_evidence_batch_payload(batch: Any) -> dict[str, Any]:
    return {
        "registry_entries": tuple(entry.to_json_dict() for entry in batch.registry_entries),
        "installed_capability_ids": tuple(batch.installed_capability_ids),
        "handoff_hashes": tuple(batch.handoff_hashes),
        "batch_hash": batch.batch_hash,
    }


def _physical_promotion_receipt_request(
    payload: Any,
    *,
    recorded_at_default: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("physical_promotion_receipt_request_must_be_object")
    raw_physical_safety_refs = payload.get("physical_live_safety_evidence_refs", {})
    if not isinstance(raw_physical_safety_refs, Mapping):
        raise ValueError("physical_promotion_receipt_physical_safety_refs_must_be_object")

    return {
        "capability_id": _optional_text(
            payload,
            "capability_id",
            default=DEFAULT_PHYSICAL_PROMOTION_CAPABILITY_ID,
        ),
        "live_read_receipt_ref": _optional_text(payload, "live_read_receipt_ref"),
        "live_write_receipt_ref": _optional_text(payload, "live_write_receipt_ref"),
        "worker_deployment_ref": _optional_text(payload, "worker_deployment_ref"),
        "recovery_evidence_ref": _optional_text(payload, "recovery_evidence_ref"),
        "physical_live_safety_evidence_refs": {
            field_name: _optional_text(raw_physical_safety_refs, field_name)
            or _optional_text(payload, field_name)
            for field_name in PHYSICAL_SAFETY_REF_FIELDS
        },
        "use_fixture_refs": _payload_bool(payload, "use_fixture_refs", default=False),
        "recorded_at": _optional_text(payload, "recorded_at", default=recorded_at_default),
    }


def _required_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_must_be_object")
    return value


def _mapping_item(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_items_must_be_objects")
    return value


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    if not value:
        raise ValueError(f"{field_name}_required")
    return value


def _optional_text(payload: Mapping[str, Any], field_name: str, *, default: str = "") -> str:
    value = payload.get(field_name, default)
    if value is None:
        return default
    return str(value).strip()


def _payload_bool(payload: Mapping[str, Any], field_name: str, *, default: bool) -> bool:
    value = payload.get(field_name, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}_must_be_boolean")
    return value


async def _request_json_mapping(request: Request) -> Mapping[str, Any]:
    payload = await request.json()
    if not isinstance(payload, Mapping):
        raise ValueError("request_body_must_be_object")
    return payload


def _payload_text_tuple(
    payload: Mapping[str, Any],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    value = payload.get(field_name, ())
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}_must_be_array")
    normalized = tuple(str(item).strip() for item in value)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name}_required")
    if any(not item for item in normalized):
        raise ValueError(f"{field_name}_items_required")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name}_duplicates_forbidden")
    return normalized


def _optional_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_must_be_object")
    return value


def _orgos_organization_from_payload(payload: Mapping[str, Any]) -> Organization:
    return Organization(
        org_id=_required_text(payload, "org_id"),
        tenant_id=_required_text(payload, "tenant_id"),
        name=_required_text(payload, "name"),
        owner_role_id=_required_text(payload, "owner_role_id"),
        evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _orgos_department_from_payload(payload: Mapping[str, Any]) -> DepartmentPack:
    return DepartmentPack(
        department_id=_required_text(payload, "department_id"),
        name=_required_text(payload, "name"),
        mission=_required_text(payload, "mission"),
        owns=_payload_text_tuple(payload, "owns"),
        allowed_case_types=_payload_text_tuple(payload, "allowed_case_types"),
        allowed_capabilities=_payload_text_tuple(payload, "allowed_capabilities"),
        required_evidence=_payload_text_tuple(payload, "required_evidence"),
        approval_roles=_payload_text_tuple(payload, "approval_roles", allow_empty=True),
        escalation_departments=_payload_text_tuple(payload, "escalation_departments", allow_empty=True),
        metrics=_payload_text_tuple(payload, "metrics"),
        failure_modes=_payload_text_tuple(payload, "failure_modes"),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _orgos_role_from_payload(payload: Mapping[str, Any]) -> Role:
    return Role(
        role_id=_required_text(payload, "role_id"),
        department_id=_required_text(payload, "department_id"),
        permissions=_payload_text_tuple(payload, "permissions"),
        approval_limit_risk=_required_text(payload, "approval_limit_risk"),
        evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _orgos_authority_rule_from_payload(payload: Mapping[str, Any]) -> AuthorityRule:
    return AuthorityRule(
        rule_id=_required_text(payload, "rule_id"),
        role_id=_required_text(payload, "role_id"),
        action=_required_text(payload, "action"),
        resource_type=_required_text(payload, "resource_type"),
        max_risk=_required_text(payload, "max_risk"),
        requires_dual_control=_payload_bool(payload, "requires_dual_control", default=False),
        separation_of_duty=_payload_text_tuple(payload, "separation_of_duty", allow_empty=True),
        evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _orgos_case_from_payload(payload: Mapping[str, Any]) -> OrgCase:
    return OrgCase(
        case_id=_required_text(payload, "case_id"),
        org_id=_required_text(payload, "org_id"),
        tenant_id=_required_text(payload, "tenant_id"),
        department_id=_required_text(payload, "department_id"),
        case_type=_required_text(payload, "case_type"),
        goal=_required_text(payload, "goal"),
        risk_tier=_required_text(payload, "risk_tier"),
        owner_role_id=_required_text(payload, "owner_role_id"),
        status=_optional_text(payload, "status", default="open"),
        evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
        authority_decision_refs=_payload_text_tuple(payload, "authority_decision_refs", allow_empty=True),
        plan_certificate_ref=_optional_text(payload, "plan_certificate_ref"),
        closure_certificate_ref=_optional_text(payload, "closure_certificate_ref"),
        learning_admission_ref=_optional_text(payload, "learning_admission_ref"),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _orgos_plan_step_from_payload(payload: Mapping[str, Any]) -> OrgPlanStep:
    return OrgPlanStep(
        step_id=_required_text(payload, "step_id"),
        case_id=_required_text(payload, "case_id"),
        department_id=_required_text(payload, "department_id"),
        capability_id=_required_text(payload, "capability_id"),
        risk_tier=_required_text(payload, "risk_tier"),
        preconditions=_payload_text_tuple(payload, "preconditions"),
        postconditions=_payload_text_tuple(payload, "postconditions"),
        evidence_required=_payload_text_tuple(payload, "evidence_required"),
        approvals_required=_payload_text_tuple(payload, "approvals_required", allow_empty=True),
        expected_effects=_payload_text_tuple(payload, "expected_effects"),
        forbidden_effects=_payload_text_tuple(payload, "forbidden_effects"),
        rollback_plan_id=_optional_text(payload, "rollback_plan_id") or None,
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _orgos_effect_closure_from_payload(payload: Mapping[str, Any]) -> EffectClosureBinding:
    return EffectClosureBinding(
        case_id=_required_text(payload, "case_id"),
        expected_effects=_payload_text_tuple(payload, "expected_effects"),
        observed_effects=_payload_text_tuple(payload, "observed_effects"),
        forbidden_effects_checked=_payload_bool(payload, "forbidden_effects_checked", default=False),
        evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
        effect_reconciliation_ref=_required_text(payload, "effect_reconciliation_ref"),
        terminal_disposition=_required_text(payload, "terminal_disposition"),
        terminal_certificate_ref=_optional_text(payload, "terminal_certificate_ref"),
        compensation_ref=_optional_text(payload, "compensation_ref"),
        accepted_risk_ref=_optional_text(payload, "accepted_risk_ref"),
        review_case_ref=_optional_text(payload, "review_case_ref"),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _authority_decision_from_payload(payload: Mapping[str, Any]) -> AuthorityDecision:
    return AuthorityDecision(
        decision_id=_required_text(payload, "decision_id"),
        request_id=_required_text(payload, "request_id"),
        actor_id=_required_text(payload, "actor_id"),
        tenant_id=_required_text(payload, "tenant_id"),
        verdict=_required_text(payload, "verdict"),
        reason=_required_text(payload, "reason"),
        required_controls=_payload_text_tuple(payload, "required_controls", allow_empty=True),
        matched_grant_ids=_payload_text_tuple(payload, "matched_grant_ids", allow_empty=True),
        evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _terminal_certificate_from_payload(payload: Mapping[str, Any]) -> TerminalClosureCertificate:
    return TerminalClosureCertificate(
        certificate_id=_required_text(payload, "certificate_id"),
        command_id=_required_text(payload, "command_id"),
        execution_id=_required_text(payload, "execution_id"),
        disposition=TerminalClosureDisposition(_required_text(payload, "disposition")),
        verification_result_id=_required_text(payload, "verification_result_id"),
        effect_reconciliation_id=_required_text(payload, "effect_reconciliation_id"),
        evidence_refs=_payload_text_tuple(payload, "evidence_refs"),
        closed_at=_required_text(payload, "closed_at"),
        response_closure_ref=_optional_text(payload, "response_closure_ref") or None,
        memory_entry_id=_optional_text(payload, "memory_entry_id") or None,
        compensation_outcome_id=_optional_text(payload, "compensation_outcome_id") or None,
        accepted_risk_id=_optional_text(payload, "accepted_risk_id") or None,
        case_id=_optional_text(payload, "case_id") or None,
        graph_refs=_payload_text_tuple(payload, "graph_refs", allow_empty=True),
        metadata=dict(_optional_mapping(payload, "metadata")),
    )


def _authority_operator_console_html(
    *,
    witness: dict[str, Any],
    approval_chains: list[dict[str, Any]],
    obligations: list[dict[str, Any]],
    escalation_events: list[dict[str, Any]],
    operator_audit_events: list[dict[str, Any]],
) -> str:
    """Render authority responsibility state as a small governed read model."""
    from html import escape

    def _cell(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        return escape(rendered)

    def _rows(records: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
        if not records:
            return f'<tr><td colspan="{len(columns)}">No records</td></tr>'
        return "\n".join(
            "<tr>" + "".join(f"<td>{_cell(record.get(column, ''))}</td>" for column in columns) + "</tr>"
            for record in records
        )

    chain_columns = ("chain_id", "command_id", "tenant_id", "status", "required_roles", "approvals_received")
    obligation_columns = (
        "obligation_id",
        "command_id",
        "tenant_id",
        "owner_team",
        "obligation_type",
        "status",
        "due_at",
    )
    escalation_columns = ("event_id", "obligation_id", "command_id", "tenant_id", "owner_team", "escalated_at")
    operator_audit_columns = (
        "event_id",
        "observed_at",
        "method",
        "path",
        "authorized",
        "credential_type",
        "tenant_id",
    )
    metric_items = "\n".join(
        f"<li><span>{escape(key.replace('_', ' ').title())}</span><strong>{_cell(value)}</strong></li>"
        for key, value in witness.items()
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Authority Operator Console</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f6f7f9; color: #1b1f24; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 32px 0 12px; font-size: 18px; }}
    p {{ margin: 0 0 20px; color: #57606a; }}
    ul {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; padding: 0; }}
    li {{ display: flex; justify-content: space-between; gap: 16px; list-style: none; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #eef1f4; font-weight: 700; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 20px; }}
    a {{ color: #0969da; }}
  </style>
</head>
<body>
<main>
  <h1>Mullu Authority Operator Console</h1>
  <p>Organizational responsibility witness for approval chains, obligations, and escalation debt.</p>
  <nav>
    <a href="/authority/responsibility">responsibility json</a>
    <a href="/authority/witness">witness json</a>
    <a href="/authority/approval-chains">approval chains json</a>
    <a href="/authority/obligations">obligations json</a>
    <a href="/authority/escalations">escalations json</a>
    <a href="/authority/operator-audit">operator audit json</a>
  </nav>
  <h2>Responsibility Witness</h2>
  <ul>{metric_items}</ul>
  <h2>Approval Chains</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in chain_columns)}</tr></thead>
    <tbody>{_rows(approval_chains, chain_columns)}</tbody>
  </table>
  <h2>Obligations</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in obligation_columns)}</tr></thead>
    <tbody>{_rows(obligations, obligation_columns)}</tbody>
  </table>
  <h2>Escalations</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in escalation_columns)}</tr></thead>
    <tbody>{_rows(escalation_events, escalation_columns)}</tbody>
  </table>
  <h2>Operator Audit</h2>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in operator_audit_columns)}</tr></thead>
    <tbody>{_rows(operator_audit_events, operator_audit_columns)}</tbody>
  </table>
</main>
</body>
</html>"""


def _governed_operations_console_html(read_model: Mapping[str, Any]) -> str:
    """Render governed operations readiness as a read-only operator console."""
    from html import escape

    def _cell(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value)
        elif isinstance(value, Mapping):
            rendered = json.dumps(value, sort_keys=True)
        else:
            rendered = str(value)
        return escape(rendered)

    def _table(items: Any, columns: tuple[str, ...], *, empty_label: str) -> str:
        rows: list[str] = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, Mapping):
                    rows.append(
                        "<tr>"
                        + "".join(f"<td>{_cell(item.get(column, ''))}</td>" for column in columns)
                        + "</tr>"
                    )
        if not rows:
            rows.append(f'<tr><td colspan="{len(columns)}">{escape(empty_label)}</td></tr>')
        headings = "".join(f"<th>{escape(column)}</th>" for column in columns)
        return f"<table><thead><tr>{headings}</tr></thead><tbody>{''.join(rows)}</tbody></table>"

    metrics = (
        ("readiness class", read_model.get("readiness_class", "")),
        ("readiness status", read_model.get("readiness_status", "")),
        ("loops", read_model.get("loop_count", 0)),
        ("closed loops", read_model.get("closed_loop_count", 0)),
        ("gaps", read_model.get("gap_count", 0)),
        ("blocking gaps", read_model.get("blocking_gap_count", 0)),
        ("drift checks", read_model.get("drift_count", 0)),
        ("snapshot hash", read_model.get("snapshot_hash", "")),
    )
    metric_items = "\n".join(
        f"<li><span>{escape(label.title())}</span><strong>{_cell(value)}</strong></li>"
        for label, value in metrics
    )
    loops = _table(
        read_model.get("loops", ()),
        ("loop_id", "system_ref", "owner", "declared_state", "evidence_refs"),
        empty_label="No loops registered",
    )
    gaps = _table(
        read_model.get("gaps", ()),
        ("gap_id", "severity", "source", "blocker_type", "evidence_missing", "closure_condition"),
        empty_label="No gaps",
    )
    closure_results = _table(
        read_model.get("closure_results", ()),
        ("loop_id", "status", "closed", "missing_evidence_refs", "drift_status", "closure_evidence_refs"),
        empty_label="No closure results",
    )
    drift_checks = _table(
        read_model.get("drift_checks", ()),
        ("drift_id", "loop_id", "declared_state", "observed_state", "status", "evidence_refs"),
        empty_label="No drift checks",
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Governed Operations</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f7f8fa; color: #1b1f24; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 28px 0 12px; font-size: 20px; }}
    p {{ margin: 0 0 20px; color: #57606a; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 24px; }}
    a {{ color: #0969da; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; padding: 0; margin: 0 0 24px; }}
    .metrics li {{ display: flex; justify-content: space-between; gap: 16px; list-style: none; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; margin-bottom: 24px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; font-size: 13px; overflow-wrap: anywhere; }}
    th {{ background: #eef1f4; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>Mullu Governed Operations</h1>
  <p>Read-only closure, gap, drift, receipt, and readiness projection for registered control-plane loops.</p>
  <nav>
    <a href="/governed-operations/read-model">read model json</a>
    <a href="/runtime/conformance">runtime conformance</a>
    <a href="/deployment/witness">deployment witness</a>
    <a href="/authority/operator">authority console</a>
  </nav>
  <ul class="metrics">{metric_items}</ul>
  <h2>Registered Loops</h2>
  {loops}
  <h2>Gaps</h2>
  {gaps}
  <h2>Closure Results</h2>
  {closure_results}
  <h2>Drift Checks</h2>
  {drift_checks}
</main>
</body>
</html>"""


def _physical_promotion_receipts_console_html(read_model: Mapping[str, Any]) -> str:
    """Render persisted physical promotion receipt state for operators."""
    from html import escape
    from urllib.parse import urlencode

    def _cell(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value)
        elif isinstance(value, dict):
            rendered = json.dumps(value, sort_keys=True)
        else:
            rendered = str(value)
        return escape(rendered)

    receipts = tuple(read_model.get("physical_capability_promotion_receipts", ()))
    columns = (
        "receipt_id",
        "capability_id",
        "promotion_status",
        "preflight_ready",
        "preflight_readiness_level",
        "recorded_at",
        "receipt_hash",
    )
    if receipts:
        rows = "\n".join(
            "<tr>"
            + "".join(f"<td>{_cell(receipt.get(column, ''))}</td>" for column in columns)
            + "</tr>"
            for receipt in receipts
            if isinstance(receipt, Mapping)
        )
    else:
        rows = f'<tr><td colspan="{len(columns)}">No receipts</td></tr>'
    query = {
        key: value
        for key, value in {
            "capability_id": read_model.get("capability_id_filter", ""),
            "status": read_model.get("status_filter", ""),
            "limit": read_model.get("limit", 100),
            "offset": read_model.get("offset", 0),
        }.items()
        if value not in ("", None)
    }
    json_href = "/operator/physical-capability-promotion-receipts"
    if query:
        json_href = f"{json_href}?{urlencode(query)}"
    metrics = (
        ("visible", read_model.get("count", 0)),
        ("total", read_model.get("total", 0)),
        ("limit", read_model.get("limit", 0)),
        ("offset", read_model.get("offset", 0)),
        ("next offset", read_model.get("next_offset", "")),
        ("capability filter", read_model.get("capability_id_filter", "")),
        ("status filter", read_model.get("status_filter", "")),
    )
    metric_items = "\n".join(
        f"<span class=\"metric\"><strong>{escape(label)}</strong>{_cell(value)}</span>"
        for label, value in metrics
    )
    headings = "".join(f"<th>{escape(column)}</th>" for column in columns)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Physical Promotion Receipts</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17202a; }}
    header {{ margin-bottom: 20px; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 20px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #f6f8fa; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0 20px; }}
    .metric {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 8px 10px; background: #fff; }}
    .metric strong {{ display: block; font-size: 12px; color: #57606a; }}
    a {{ color: #0969da; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu Physical Promotion Receipts</h1>
    <nav>
      <a href="{escape(json_href)}">json read model</a>
      <a href="/operator/capabilities">capability console</a>
      <a href="/authority/operator">authority console</a>
    </nav>
    <div class="metrics">{metric_items}</div>
  </header>
  <main>
    <table>
      <thead><tr>{headings}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </main>
</body>
</html>"""


def _universal_actions_console_html(read_model: Mapping[str, Any]) -> str:
    """Render universal action proof replay state for operators."""
    from html import escape

    records = read_model.get("universal_action_proofs", ())
    if not isinstance(records, list):
        records = []
    columns = (
        "command_id",
        "tenant_id",
        "command_state",
        "blocked",
        "block_reason",
        "capability_id",
        "closure_state",
        "reconciliation_ref",
        "memory_ref",
        "whqr_replay_ref",
        "proof_hash",
        "terminal_certificate_id",
        "learning_status",
    )

    def _cell(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return escape(", ".join(str(item) for item in value))
        return escape(str(value))

    def _rows() -> str:
        if not records:
            return f'<tr><td colspan="{len(columns)}">No universal action proofs</td></tr>'
        rendered_rows: list[str] = []
        for record in records:
            if not isinstance(record, Mapping):
                continue
            rendered_rows.append(
                "<tr>"
                + "".join(f"<td>{_cell(record.get(column, ''))}</td>" for column in columns)
                + "</tr>"
            )
        if not rendered_rows:
            return f'<tr><td colspan="{len(columns)}">No universal action proofs</td></tr>'
        return "\n".join(rendered_rows)

    total = _cell(read_model.get("total", 0))
    count = _cell(read_model.get("count", 0))
    tenant_filter = _cell(read_model.get("tenant_id_filter", ""))
    blocked_filter = _cell(read_model.get("blocked_filter", ""))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Universal Action Proofs</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f7f8fa; color: #1b1f24; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ margin: 0 0 20px; color: #57606a; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 24px; }}
    a {{ color: #0969da; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; padding: 0; margin: 0 0 24px; }}
    .metrics li {{ display: flex; justify-content: space-between; gap: 16px; list-style: none; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; font-size: 13px; overflow-wrap: anywhere; }}
    th {{ background: #eef1f4; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>Mullu Universal Action Proofs</h1>
  <p>Replayable command proofs for dispatch, blocked outcomes, terminal closure, and learning admission.</p>
  <nav>
    <a href="/operator/universal-actions/read-model">read model json</a>
    <a href="/gateway/status">gateway status</a>
    <a href="/authority/operator">authority console</a>
    <a href="/operator/capabilities">capability console</a>
  </nav>
  <ul class="metrics">
    <li><span>Visible</span><strong>{count}</strong></li>
    <li><span>Total</span><strong>{total}</strong></li>
    <li><span>Tenant Filter</span><strong>{tenant_filter}</strong></li>
    <li><span>Blocked Filter</span><strong>{blocked_filter}</strong></li>
  </ul>
  <table>
    <thead><tr>{''.join(f'<th>{escape(column)}</th>' for column in columns)}</tr></thead>
    <tbody>{_rows()}</tbody>
  </table>
</main>
</body>
</html>"""


def _closure_proof_coverage_witnesses(
    *,
    terminal_certificate: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bind closure proof matrix claims to runtime witness references."""
    event_hashes = tuple(
        str(event["event_hash"])
        for event in events
        if event.get("event_hash")
    )
    witnesses: list[dict[str, Any]] = [
        {
            "matrix_surface_id": "gateway_capability_fabric",
            "invariant_id": "command_lifecycle_events_are_hash_linked",
            "witness_type": "command_event_hash_chain",
            "witness_refs": event_hashes,
        },
        {
            "matrix_surface_id": "gateway_capability_fabric",
            "invariant_id": "terminal_closure_requires_evidence_refs",
            "witness_type": "terminal_closure_certificate",
            "witness_ref": terminal_certificate["certificate_id"],
            "evidence_refs": tuple(terminal_certificate["evidence_refs"]),
        },
    ]
    response_evidence_closure_id = terminal_certificate.get("response_evidence_closure_id")
    if response_evidence_closure_id:
        witnesses.append({
            "matrix_surface_id": "gateway_capability_fabric",
            "invariant_id": "successful_response_is_bound_to_response_evidence_closure",
            "witness_type": "response_evidence_closure",
            "witness_ref": response_evidence_closure_id,
        })
    whqr_replay_binding = _whqr_replay_binding_from_terminal_certificate_payload(
        terminal_certificate
    )
    if whqr_replay_binding:
        witnesses.append({
            "matrix_surface_id": "gateway_capability_fabric",
            "invariant_id": "terminal_closure_exposes_whqr_replay_ref",
            "witness_type": "whqr_replay_binding",
            "witness_ref": whqr_replay_binding["replay_ref"],
            "canonical_hash": whqr_replay_binding["canonical_hash"],
            "semantics_hash": whqr_replay_binding["semantics_hash"],
            "version": whqr_replay_binding["version"],
        })
    return witnesses


def _whqr_replay_binding_from_terminal_certificate_payload(
    terminal_certificate: Mapping[str, Any],
) -> dict[str, str]:
    """Project verified WHQR terminal metadata into a replay binding."""
    metadata = terminal_certificate.get("metadata")
    if not isinstance(metadata, Mapping):
        return {}
    canonical_hash = metadata.get("whqr_canonical_hash")
    semantics_hash = metadata.get("whqr_semantics_hash")
    version = metadata.get("whqr_version")
    if not (
        isinstance(canonical_hash, str)
        and canonical_hash
        and isinstance(semantics_hash, str)
        and semantics_hash
        and isinstance(version, str)
        and version
    ):
        return {}
    return _validated_whqr_replay_binding({
        "replay_ref": f"whqr://replay/{canonical_hash}",
        "canonical_hash": canonical_hash,
        "semantics_hash": semantics_hash,
        "version": version,
    })


def _gateway_request_receipt(
    *,
    channel: str,
    request: Request,
    body: bytes,
    message: Any | None,
) -> dict[str, Any]:
    """Normalize a request-bound proof envelope for gateway ingress."""
    safe_header_names = tuple(sorted(
        name.lower()
        for name in request.headers
        if not _sensitive_header_name(name)
    ))
    message_id = str(getattr(message, "message_id", "") or "")
    sender_id = str(getattr(message, "sender_id", "") or "")
    body_hash = sha256(body).hexdigest()
    receipt_payload = {
        "channel": channel,
        "method": request.method,
        "path": request.url.path,
        "message_id": message_id,
        "sender_id_hash": sha256(sender_id.encode()).hexdigest() if sender_id else "",
        "body_hash": body_hash,
        "safe_header_names": safe_header_names,
        "receipt_type": "gateway_request_receipt_v1",
    }
    receipt_hash = sha256(
        json.dumps(receipt_payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    return {
        "receipt_id": f"gateway-request-{receipt_hash[:16]}",
        "receipt_hash": receipt_hash,
        **receipt_payload,
    }


def _sensitive_header_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("authorization", "secret", "signature", "token", "cookie"))


def _bounded_read_model_limit(limit: int, *, maximum: int = 500) -> int:
    """Return a positive bounded read-model page size."""
    return max(1, min(int(limit), maximum))


def _bounded_read_model_offset(offset: int) -> int:
    """Return a non-negative read-model offset."""
    return max(0, int(offset))


def _parse_github_workroom_evidence_refs(evidence_refs: str) -> tuple[str, ...]:
    """Parse comma or newline separated Workroom evidence references."""
    if not evidence_refs:
        return ()
    normalized = evidence_refs.replace("\r", "\n").replace(",", "\n")
    return tuple(ref.strip() for ref in normalized.split("\n") if ref.strip())


def _read_model_page(items: tuple[Any, ...], *, limit: int, offset: int) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Return a bounded read-model page and pagination metadata."""
    total = len(items)
    page = items[offset:offset + limit]
    next_offset = offset + len(page)
    return page, {
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset if next_offset < total else None,
    }


def _due_sort_key(timestamp: str) -> str:
    """Return a stable sortable timestamp key for responsibility read models."""
    from datetime import datetime, timezone

    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.max.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


# Default app instance
app = create_gateway_app()
