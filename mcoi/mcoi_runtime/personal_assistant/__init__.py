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
from .console import (
    build_personal_assistant_console_read_model,
    build_personal_assistant_readiness_demo,
    render_personal_assistant_console_html,
)
from .approval import (
    ApprovalDecision,
    ApprovalProposedAction,
    ApprovalQueueRecord,
    PersonalAssistantApprovalQueue,
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
    TEAMOPS_GMAIL_LIVE_PROBE_READINESS_ROUTE,
    TeamOpsSharedInboxProjection,
    build_teamops_gmail_live_probe_readiness,
    plan_teamops_shared_inbox,
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
    "PersonalAssistantSkillRegistry",
    "ApprovalDecision",
    "ApprovalProposedAction",
    "ApprovalQueueRecord",
    "PersonalAssistantApprovalQueue",
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
    "TeamOpsSharedInboxProjection",
    "TEAMOPS_GMAIL_LIVE_PROBE_READINESS_ROUTE",
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
    "build_personal_assistant_readiness_demo",
    "build_personal_assistant_preview_plan",
    "draft_calendar_event",
    "draft_email_response",
    "draft_task",
    "build_teamops_gmail_live_probe_readiness",
    "interpret_user_request",
    "load_default_skill_registry",
    "load_skill_registry",
    "prepare_memory_observation",
    "review_memory_observation_candidate",
    "plan_teamops_shared_inbox",
    "plan_github_codex_review",
    "plan_math_reasoning",
    "plan_schedule_optimization",
    "plan_research_source_compare",
    "render_personal_assistant_console_html",
    "summarize_calendar_day_read_only",
    "summarize_inbox_read_only",
)
