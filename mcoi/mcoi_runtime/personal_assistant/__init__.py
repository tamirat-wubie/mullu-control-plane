"""Purpose: personal-assistant foundation runtime package.
Governance scope: governed skill registry, risk boundaries, read-only
projections, and draft-only projections for the personal-assistant layer.
Dependencies: personal-assistant contracts and skill registry modules.
Invariants: registry loading is deterministic, receipt and UAO requirements are
preserved, and no live connector execution is exposed from this package.
"""

from __future__ import annotations

from .contracts import (
    EffectBoundary,
    PersonalAssistantInvariantError,
    PersonalAssistantSkill,
    SkillMode,
    SkillRiskLevel,
)
from .capability_pack import (
    PersonalAssistantCapabilityPackEntry,
    PersonalAssistantCapabilityPackIndex,
    PersonalAssistantSkillCapabilityBindingReport,
    load_default_personal_assistant_capability_pack,
    load_personal_assistant_capability_pack,
)
from .console_first_demo_html import render_personal_assistant_console_html
from .console_first_demo import build_personal_assistant_console_read_model
from .approval import (
    ApprovalDecision,
    ApprovalPlanProposal,
    ApprovalProposedAction,
    ApprovalQueueRecord,
    PersonalAssistantApprovalQueue,
    prepare_approval_proposal_from_plan,
)
from .approval_decision_evidence import (
    DEFAULT_APPROVAL_DECISION_CREATED_AT,
    DEFAULT_APPROVAL_DECISION_DECIDED_AT,
    DEFAULT_APPROVAL_DECISION_SET_ID,
    build_default_personal_assistant_approval_decision_evidence,
    build_personal_assistant_approval_decision_evidence_envelope,
)
from .approval_matrix import (
    ApprovalRiskPolicy,
    PersonalAssistantApprovalMatrix,
    load_default_personal_assistant_approval_matrix,
    load_personal_assistant_approval_matrix,
)
from .drafts import (
    CalendarEventDraftInput,
    DraftAssistantProjection,
    EmailDraftInput,
    TaskDraftInput,
    draft_calendar_event,
    draft_email_response,
    draft_task,
)
from .draft_projection import (
    DEFAULT_DRAFT_PROJECTION_GENERATED_AT,
    DEFAULT_DRAFT_PROJECTION_SET_ID,
    build_default_personal_assistant_draft_projection,
    build_personal_assistant_draft_projection_envelope,
)
from .execution_gate import (
    DEFAULT_EXECUTION_GATE_GENERATED_AT,
    DEFAULT_EXECUTION_GATE_SET_ID,
    build_default_personal_assistant_execution_gate,
    build_personal_assistant_execution_gate_envelope,
)
from .worker_replay_preflight import (
    DEFAULT_WORKER_REPLAY_PREFLIGHT_GENERATED_AT,
    DEFAULT_WORKER_REPLAY_PREFLIGHT_SET_ID,
    build_default_personal_assistant_worker_replay_preflight,
    build_personal_assistant_worker_replay_preflight_envelope,
)
from .replay_rollback_witness import (
    DEFAULT_REPLAY_ROLLBACK_WITNESS_GENERATED_AT,
    DEFAULT_REPLAY_ROLLBACK_WITNESS_SET_ID,
    build_default_personal_assistant_replay_rollback_witness,
    build_personal_assistant_replay_rollback_witness_envelope,
)
from .connector_lease_witness import (
    DEFAULT_CONNECTOR_LEASE_WITNESS_GENERATED_AT,
    DEFAULT_CONNECTOR_LEASE_WITNESS_SET_ID,
    build_default_personal_assistant_connector_lease_witness,
    build_personal_assistant_connector_lease_witness_envelope,
)
from .operator_reapproval_gate import (
    DEFAULT_OPERATOR_REAPPROVAL_GATE_GENERATED_AT,
    DEFAULT_OPERATOR_REAPPROVAL_GATE_SET_ID,
    build_default_personal_assistant_operator_reapproval_gate,
    build_personal_assistant_operator_reapproval_gate_envelope,
)
from .intake import (
    ApprovalScope,
    ConnectorProofRef,
    GovernedIntent,
    MissingBinding,
    RequestExecutionMode,
    RequestInterface,
    interpret_user_request,
)
from .intake_chain import build_personal_assistant_intake_chain_read_model
from .github_codex import (
    GitHubCodexReviewProjection,
    plan_github_codex_review,
)
from .math_reasoning import (
    MathReasoningProjection,
    plan_math_reasoning,
)
from .planning import (
    PlanningScheduleProjection,
    plan_schedule_optimization,
)
from .research import (
    ResearchSourceCompareProjection,
    plan_research_source_compare,
)
from .memory import (
    MemoryConfidence,
    MemoryObservationCandidate,
    MemoryObservationReview,
    MemoryObservationSource,
    MemoryObservationType,
    MemoryRetentionPolicy,
    MemoryReviewDecision,
    MemoryScope,
    MemorySensitivity,
    NestedMindStatus,
    PersonalAssistantMemoryObservationLedger,
    prepare_memory_observation,
    review_memory_observation_candidate,
)
from .planner import (
    PersonalAssistantPlanningEnvelope,
    build_personal_assistant_preview_plan,
)
from .read_only import (
    ReadOnlyAssistantProjection,
    RedactedCalendarEvent,
    RedactedInboxMessage,
    summarize_calendar_day_read_only,
    summarize_inbox_read_only,
)
from .read_only_projection import (
    DEFAULT_READ_ONLY_PROJECTION_GENERATED_AT,
    DEFAULT_READ_ONLY_PROJECTION_SET_ID,
    build_default_personal_assistant_read_only_projection,
    build_personal_assistant_read_only_projection_envelope,
)
from .skill_registry import (
    PersonalAssistantSkillRegistry,
    load_default_skill_registry,
    load_skill_registry,
)
from .teamops import (
    TeamOpsGmailLiveProbeProjection,
    TeamOpsSharedInboxProjection,
    plan_teamops_shared_inbox,
    preview_teamops_gmail_live_probe,
)
from .whqr_bridge import (
    PersonalAssistantClarificationBundle,
    build_clarification_requests,
)

__all__ = (
    "EffectBoundary",
    "PersonalAssistantInvariantError",
    "PersonalAssistantClarificationBundle",
    "PersonalAssistantSkill",
    "PersonalAssistantCapabilityPackEntry",
    "PersonalAssistantCapabilityPackIndex",
    "PersonalAssistantSkillCapabilityBindingReport",
    "PersonalAssistantSkillRegistry",
    "ApprovalDecision",
    "ApprovalPlanProposal",
    "ApprovalProposedAction",
    "ApprovalQueueRecord",
    "ApprovalRiskPolicy",
    "DEFAULT_APPROVAL_DECISION_CREATED_AT",
    "DEFAULT_APPROVAL_DECISION_DECIDED_AT",
    "DEFAULT_APPROVAL_DECISION_SET_ID",
    "DEFAULT_CONNECTOR_LEASE_WITNESS_GENERATED_AT",
    "DEFAULT_CONNECTOR_LEASE_WITNESS_SET_ID",
    "DEFAULT_OPERATOR_REAPPROVAL_GATE_GENERATED_AT",
    "DEFAULT_OPERATOR_REAPPROVAL_GATE_SET_ID",
    "PersonalAssistantApprovalQueue",
    "PersonalAssistantApprovalMatrix",
    "CalendarEventDraftInput",
    "DraftAssistantProjection",
    "EmailDraftInput",
    "MemoryConfidence",
    "MemoryObservationCandidate",
    "MemoryObservationReview",
    "MemoryObservationSource",
    "MemoryObservationType",
    "MemoryRetentionPolicy",
    "MemoryReviewDecision",
    "MemoryScope",
    "MemorySensitivity",
    "NestedMindStatus",
    "PersonalAssistantMemoryObservationLedger",
    "PersonalAssistantPlanningEnvelope",
    "PlanningScheduleProjection",
    "DEFAULT_DRAFT_PROJECTION_GENERATED_AT",
    "DEFAULT_DRAFT_PROJECTION_SET_ID",
    "DEFAULT_EXECUTION_GATE_GENERATED_AT",
    "DEFAULT_EXECUTION_GATE_SET_ID",
    "DEFAULT_READ_ONLY_PROJECTION_GENERATED_AT",
    "DEFAULT_READ_ONLY_PROJECTION_SET_ID",
    "DEFAULT_REPLAY_ROLLBACK_WITNESS_GENERATED_AT",
    "DEFAULT_REPLAY_ROLLBACK_WITNESS_SET_ID",
    "DEFAULT_WORKER_REPLAY_PREFLIGHT_GENERATED_AT",
    "DEFAULT_WORKER_REPLAY_PREFLIGHT_SET_ID",
    "MathReasoningProjection",
    "ReadOnlyAssistantProjection",
    "RedactedCalendarEvent",
    "RedactedInboxMessage",
    "ResearchSourceCompareProjection",
    "TaskDraftInput",
    "TeamOpsGmailLiveProbeProjection",
    "TeamOpsSharedInboxProjection",
    "ApprovalScope",
    "ConnectorProofRef",
    "GovernedIntent",
    "GitHubCodexReviewProjection",
    "MissingBinding",
    "RequestExecutionMode",
    "RequestInterface",
    "SkillMode",
    "SkillRiskLevel",
    "build_clarification_requests",
    "build_personal_assistant_intake_chain_read_model",
    "build_personal_assistant_console_read_model",
    "build_default_personal_assistant_approval_decision_evidence",
    "build_default_personal_assistant_connector_lease_witness",
    "build_default_personal_assistant_operator_reapproval_gate",
    "build_personal_assistant_preview_plan",
    "build_default_personal_assistant_draft_projection",
    "build_default_personal_assistant_execution_gate",
    "build_default_personal_assistant_read_only_projection",
    "build_default_personal_assistant_replay_rollback_witness",
    "build_default_personal_assistant_worker_replay_preflight",
    "build_personal_assistant_draft_projection_envelope",
    "build_personal_assistant_approval_decision_evidence_envelope",
    "build_personal_assistant_connector_lease_witness_envelope",
    "build_personal_assistant_operator_reapproval_gate_envelope",
    "build_personal_assistant_execution_gate_envelope",
    "build_personal_assistant_read_only_projection_envelope",
    "build_personal_assistant_replay_rollback_witness_envelope",
    "build_personal_assistant_worker_replay_preflight_envelope",
    "draft_calendar_event",
    "draft_email_response",
    "draft_task",
    "interpret_user_request",
    "load_default_skill_registry",
    "load_default_personal_assistant_capability_pack",
    "load_default_personal_assistant_approval_matrix",
    "load_skill_registry",
    "load_personal_assistant_capability_pack",
    "load_personal_assistant_approval_matrix",
    "prepare_memory_observation",
    "prepare_approval_proposal_from_plan",
    "review_memory_observation_candidate",
    "plan_teamops_shared_inbox",
    "preview_teamops_gmail_live_probe",
    "plan_github_codex_review",
    "plan_math_reasoning",
    "plan_schedule_optimization",
    "plan_research_source_compare",
    "render_personal_assistant_console_html",
    "summarize_calendar_day_read_only",
    "summarize_inbox_read_only",
)
