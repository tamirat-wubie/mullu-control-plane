"""Purpose: assistant kernel public contract exports.
Governance scope: stable import surface for identity, goals, consent, planning,
    effects, memory, inbox, scheduling, and closure contracts.
Dependencies: assistant kernel modules.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Public exports remain contract-only.
  - Importing the package performs no runtime side effects.
  - Execution authority still resides in governed capability workers.
"""

from __future__ import annotations

from mcoi_runtime.assistant_kernel.capability_selection import CapabilitySelection, select_capabilities
from mcoi_runtime.assistant_kernel.closure import (
    ClosureContract,
    ClosureEvaluation,
    ClosureObservation,
    closure_observation,
    evaluate_closure,
    finance_ops_payment_closure_contract,
)
from mcoi_runtime.assistant_kernel.consent import ConsentDecision, ConsentGrant, ConsentLedger, consent_grant_id
from mcoi_runtime.assistant_kernel.effects import (
    EffectExpectation,
    EffectReceipt,
    EffectVerification,
    expectation_for_predicate,
    verify_effect_receipts,
)
from mcoi_runtime.assistant_kernel.goals import (
    FINANCE_OPS_INVOICE_PAYMENT_CAPABILITIES,
    FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES,
    AssistantGoal,
    finance_ops_invoice_payment_goal,
)
from mcoi_runtime.assistant_kernel.identity import (
    AssistantIdentityBinding,
    AssistantProfile,
    bind_assistant_identity,
    builtin_assistant_profiles,
    corporate_admin_default_profile,
    executive_ops_default_profile,
    finance_ops_default_profile,
    founder_default_profile,
    personal_default_profile,
    team_ops_default_profile,
)
from mcoi_runtime.assistant_kernel.inbox import AssistantInboxItem, make_inbox_item
from mcoi_runtime.assistant_kernel.memory import (
    AssistantMemoryAdmission,
    AssistantMemoryCandidate,
    admit_memory_candidate,
)
from mcoi_runtime.assistant_kernel.planner import AssistantExecutionPlan, AssistantKernel, AssistantPlanStep
from mcoi_runtime.assistant_kernel.scheduler import (
    AssistantScheduleRequest,
    ScheduledAssistantAction,
    schedule_assistant_action,
)


__all__ = [
    "AssistantExecutionPlan",
    "AssistantGoal",
    "AssistantIdentityBinding",
    "AssistantInboxItem",
    "AssistantKernel",
    "AssistantMemoryAdmission",
    "AssistantMemoryCandidate",
    "AssistantPlanStep",
    "AssistantProfile",
    "AssistantScheduleRequest",
    "CapabilitySelection",
    "ClosureContract",
    "ClosureEvaluation",
    "ClosureObservation",
    "ConsentDecision",
    "ConsentGrant",
    "ConsentLedger",
    "EffectExpectation",
    "EffectReceipt",
    "EffectVerification",
    "FINANCE_OPS_INVOICE_PAYMENT_CAPABILITIES",
    "FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES",
    "ScheduledAssistantAction",
    "admit_memory_candidate",
    "bind_assistant_identity",
    "builtin_assistant_profiles",
    "closure_observation",
    "consent_grant_id",
    "corporate_admin_default_profile",
    "evaluate_closure",
    "executive_ops_default_profile",
    "expectation_for_predicate",
    "finance_ops_default_profile",
    "finance_ops_invoice_payment_goal",
    "finance_ops_payment_closure_contract",
    "founder_default_profile",
    "make_inbox_item",
    "personal_default_profile",
    "schedule_assistant_action",
    "select_capabilities",
    "team_ops_default_profile",
    "verify_effect_receipts",
]
