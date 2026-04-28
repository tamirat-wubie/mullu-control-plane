"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.content_safety`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.content_safety`` path or the new ``governance.guards.content_safety`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.content_safety import (  # noqa: F401
    ContentSafetyChain,
    ContentSafetyFilter,
    ContentSafetyResult,
    LAMBDA_INPUT_SAFETY,
    LAMBDA_OUTPUT_SAFETY,
    OutputSafetyResult,
    PROMPT_INJECTION_PATTERNS,
    SafetyFilterResult,
    SafetyPattern,
    SafetyVerdict,
    ThreatCategory,
    build_default_safety_chain,
    create_content_safety_guard,
    create_input_safety_guard,
    create_output_safety_guard,
    evaluate_output_safety,
    normalize_content,
)

__all__ = (
    "ContentSafetyChain",
    "ContentSafetyFilter",
    "ContentSafetyResult",
    "LAMBDA_INPUT_SAFETY",
    "LAMBDA_OUTPUT_SAFETY",
    "OutputSafetyResult",
    "PROMPT_INJECTION_PATTERNS",
    "SafetyFilterResult",
    "SafetyPattern",
    "SafetyVerdict",
    "ThreatCategory",
    "build_default_safety_chain",
    "create_content_safety_guard",
    "create_input_safety_guard",
    "create_output_safety_guard",
    "evaluate_output_safety",
    "normalize_content",
)
