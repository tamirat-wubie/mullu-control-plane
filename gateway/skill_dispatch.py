"""Gateway skill dispatch compatibility module.

Purpose: Preserve legacy imports while the gateway center moves from
    skill-specific dispatch to domain-neutral capability dispatch.
Governance scope: compatibility aliases only.
Dependencies: gateway capability dispatcher and intent resolver.
Invariants:
  - CapabilityDispatcher is the execution implementation.
  - SkillIntent remains an alias for persisted command compatibility.
  - detect_intent delegates to CapabilityIntentResolver.
"""

from __future__ import annotations

from gateway.capability_dispatch import (
    CapabilityDispatcher,
    CapabilityExecutionContext,
    CapabilityHandler,
    CapabilityIntent,
    FunctionCapabilityHandler,
    SkillDispatcher,
    SkillIntent,
    build_capability_dispatcher_from_platform,
    build_skill_dispatcher_from_platform,
    register_creative_capabilities,
    register_enterprise_capabilities,
    register_financial_capabilities,
)
from gateway.intent_resolver import (
    CapabilityIntentResolver,
    CapabilityPattern,
    DEFAULT_CAPABILITY_PATTERNS,
    detect_intent,
)

__all__ = [
    "CapabilityDispatcher",
    "CapabilityExecutionContext",
    "CapabilityHandler",
    "CapabilityIntent",
    "CapabilityIntentResolver",
    "CapabilityPattern",
    "DEFAULT_CAPABILITY_PATTERNS",
    "FunctionCapabilityHandler",
    "SkillDispatcher",
    "SkillIntent",
    "build_capability_dispatcher_from_platform",
    "build_skill_dispatcher_from_platform",
    "detect_intent",
    "register_creative_capabilities",
    "register_enterprise_capabilities",
    "register_financial_capabilities",
]
