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
from .console import render_personal_assistant_console_html
from .console_first_demo import build_personal_assistant_console_read_model
from .approval import (
    ApprovalDecision,
    ApprovalPlanProposal,
    ApprovalProposedAction,
    ApprovalQueueRecord,
    PersonalAssistantApprovalQueue,
    prepare_approval_proposal_from_plan,
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
from .intake import (
    ApprovalScope,
    ConnectorProofRef,
    GovernedIntent,
    MissingBinding,
    RequestExecutionMode,
    RequestInterface,
    interpret_user_request,
)
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
    "build_personal_assistant_console_read_model",
    "build_personal_assistant_preview_plan",
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
