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
    build_personal_assistant_readiness_demo,
    interpret_user_request,
    load_default_skill_registry,
    plan_github_codex_review,
    plan_math_reasoning,
    plan_research_source_compare,
    plan_schedule_optimization,
    plan_teamops_shared_inbox,
    prepare_memory_observation,
    render_personal_assistant_console_html,
    review_memory_observation_candidate,
)

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
from gateway.mcp_capabilities import register_mcp_capabilities
from gateway.mcp_capability_fabric import MCPAuthorityRecords, build_mcp_gateway_import_from_env
from gateway.observability import GatewayObservabilityRecorder
from gateway.mcp_operator_read_model import build_mcp_operator_read_model
from gateway.operator_capability_console import (
    build_operator_capability_read_model,
    render_operator_capability_console,
)
from gateway.operator_goal_intake import (
    DEFAULT_GOAL_INTAKE_CHANNEL,
    DEFAULT_GOAL_INTAKE_SENDER_ID,
    GoalIntakePreviewRecord,
    GoalIntakePreviewStore,
    build_goal_intake_read_model,
    render_goal_intake_html,
)
from gateway.operator_receipt_viewer import (
    build_current_task_read_model,
    build_operator_budget_report_read_model,
    build_operator_approval_history_read_model,
    build_operator_plan_receipt_export_read_model,
    build_operator_plan_receipt_bundle_read_model,
    build_operator_plan_review_read_model,
    build_operator_receipt_viewer_read_model,
    render_current_task_html,
    render_operator_budget_report_html,
    render_operator_approval_detail_html,
    render_operator_plan_receipt_export_html,
    render_operator_plan_receipt_bundle_html,
    render_operator_approval_history_html,
    render_operator_plan_review_detail_html,
    render_operator_plan_review_html,
    render_operator_receipt_detail_html,
    render_operator_receipt_viewer_html,
    valid_approval_statuses,
    valid_current_task_response_evidence_states,
    valid_current_task_waiting_for_filters,
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
from gateway.physical_capability_promotion_store import build_physical_capability_promotion_receipt_store_from_env
from gateway.signature_verification import (
    ChannelVerifierConfig, VerificationMethod, WebhookVerifier,
)
from gateway.tenant_identity import TenantMapping, build_tenant_identity_store_from_env
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule

_log = logging.getLogger(__name__)
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


def _personal_assistant_approval_queue_v0_projection(
    approval_record: Mapping[str, Any],
    approval_queue_read_model: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the compact Approval Queue v0 operator projection."""

    packet = approval_record.get("packet")
    if not isinstance(packet, Mapping):
        packet = {}
    receipts = approval_record.get("receipts")
    receipt = receipts[-1] if isinstance(receipts, list) and receipts and isinstance(receipts[-1], Mapping) else {}
    proposed_actions = packet.get("proposed_actions")
    actions = (
        [dict(action) for action in proposed_actions if isinstance(action, Mapping)]
        if isinstance(proposed_actions, list)
        else []
    )
    state_counts = approval_queue_read_model.get("state_counts")
    return {
        "queue_version": "v0",
        "approval_id": str(packet.get("approval_id", approval_record.get("approval_id", ""))),
        "draft_actions": actions,
        "draft_action_count": len(actions),
        "risk_class": str(packet.get("risk_level", "")),
        "requested_approval": {
            "approval_state": str(packet.get("approval_state", "")),
            "approver_ref": str(packet.get("approver_ref", "")),
            "approval_scope": str(packet.get("approval_scope", "")),
            "explicit_approval_required": packet.get("explicit_approval_required") is True,
        },
        "decision_controls": {
            "approve": "record approved decision without executing the action",
            "reject": "record rejected decision and keep execution blocked",
            "revise": "record revision request and keep execution blocked",
        },
        "state_counts": dict(state_counts) if isinstance(state_counts, Mapping) else {},
        "receipt": {
            "receipt_id": str(receipt.get("receipt_id", "")),
            "decision": str(receipt.get("decision", "")),
            "actions_taken": (
                list(receipt.get("actions_taken", ()))
                if isinstance(receipt.get("actions_taken"), list)
                else []
            ),
            "actions_not_taken": (
                list(receipt.get("actions_not_taken", ()))
                if isinstance(receipt.get("actions_not_taken"), list)
                else []
            ),
        },
        "effect_boundary": {
            "execution_allowed": False,
            "approval_is_execution": False,
            "live_connector_execution_allowed": False,
            "external_send_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
        },
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


def create_gateway_app(
    platform: Any = None,
    *,
    capability_admission_gate_override: Any | None = None,
    command_ledger_override: Any | None = None,
    tenant_budget_reporter: Any | None = None,
    mcp_capability_entries: tuple[Any, ...] = (),
    mcp_executor: Any | None = None,
    mcp_authority_records: MCPAuthorityRecords | None = None,
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

    @app.get("/api/v1/console/personal-assistant/readiness")
    def personal_assistant_readiness_demo():
        generated_at = _clock()
        return build_personal_assistant_readiness_demo(
            generated_at=generated_at,
            console_payload=build_personal_assistant_console_read_model(generated_at=generated_at),
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

    @app.get("/api/v1/personal-assistant/approval-queue")
    def personal_assistant_approval_queue_read_model():
        read_model = PersonalAssistantApprovalQueue().read_model()
        return {
            "approval_queue": read_model,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "governed": True,
        }

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
            "approval_queue_v0": _personal_assistant_approval_queue_v0_projection(
                record.as_dict(),
                queue.read_model(),
            ),
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
        _validate_operator_plan_review_filters(
            status=status,
            budget_gate=budget_gate,
            search=search,
        )
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
        _validate_operator_plan_review_filters(
            status=status,
            budget_gate=budget_gate,
            search=search,
        )
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
        response_evidence_state: str = "",
        waiting_for: str = "",
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
        normalized_response_evidence_state = response_evidence_state.strip()
        if (
            normalized_response_evidence_state
            and normalized_response_evidence_state
            not in valid_current_task_response_evidence_states()
        ):
            raise HTTPException(
                400,
                detail="response_evidence_state must be one of: "
                + ", ".join(valid_current_task_response_evidence_states()),
            )
        normalized_waiting_for = waiting_for.strip()
        if (
            normalized_waiting_for
            and normalized_waiting_for not in valid_current_task_waiting_for_filters()
        ):
            raise HTTPException(
                400,
                detail="waiting_for must be one of: "
                + ", ".join(valid_current_task_waiting_for_filters()),
            )
        return build_current_task_read_model(
            command_ledger,
            tenant_id=tenant_id,
            status=normalized_status,
            response_evidence_state=normalized_response_evidence_state,
            waiting_for=normalized_waiting_for,
            limit=limit,
            offset=offset,
        )

    @app.get("/operator/current-task", response_class=HTMLResponse)
    def operator_current_task_console(
        request: Request,
        tenant_id: str = "",
        status: str = "",
        response_evidence_state: str = "",
        waiting_for: str = "",
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
        normalized_response_evidence_state = response_evidence_state.strip()
        if (
            normalized_response_evidence_state
            and normalized_response_evidence_state
            not in valid_current_task_response_evidence_states()
        ):
            raise HTTPException(
                400,
                detail="response_evidence_state must be one of: "
                + ", ".join(valid_current_task_response_evidence_states()),
            )
        normalized_waiting_for = waiting_for.strip()
        if (
            normalized_waiting_for
            and normalized_waiting_for not in valid_current_task_waiting_for_filters()
        ):
            raise HTTPException(
                400,
                detail="waiting_for must be one of: "
                + ", ".join(valid_current_task_waiting_for_filters()),
            )
        read_model = build_current_task_read_model(
            command_ledger,
            tenant_id=tenant_id,
            status=normalized_status,
            response_evidence_state=normalized_response_evidence_state,
            waiting_for=normalized_waiting_for,
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
