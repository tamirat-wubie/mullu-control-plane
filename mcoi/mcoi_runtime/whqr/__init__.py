"""Purpose: expose pure WHQR semantic helpers.
Governance scope: side-effect-free semantic query evaluation, binding preflight, clarification, connector compilation, static checks, and MIL compilation.
Dependencies: WHQR helper modules that are part of the tracked runtime surface.
Invariants: package exports do not initialize runtime state or perform effects.
"""

from .binding_preflight import BindingPreflightIssue, BindingPreflightReport, validate_binding_preflight
from .clarification import WHQRClarificationBundle, build_binding_clarification_requests
from .connectors import (
    AssertionKind,
    ConnectorCompilation,
    SemanticAssertion,
    compile_connector,
)
from .evaluator import WHQREvaluationContext, evaluate
from .entity_binder import (
    EntityBindingCandidate,
    EntityBindingIssue,
    EntityBindingReport,
    EntityBindingStatus,
    bind_entities,
)
from .mil_compiler import compile_and_verify_mil_from_policy_decision, compile_mil_from_policy_decision
from .static_checks import StaticCheckIssue, StaticCheckReport, validate_static

__all__ = [
    "AssertionKind",
    "BindingPreflightIssue",
    "BindingPreflightReport",
    "ConnectorCompilation",
    "EntityBindingCandidate",
    "EntityBindingIssue",
    "EntityBindingReport",
    "EntityBindingStatus",
    "SemanticAssertion",
    "StaticCheckIssue",
    "StaticCheckReport",
    "WHQREvaluationContext",
    "WHQRClarificationBundle",
    "bind_entities",
    "build_binding_clarification_requests",
    "compile_and_verify_mil_from_policy_decision",
    "compile_connector",
    "compile_mil_from_policy_decision",
    "evaluate",
    "validate_static",
    "validate_binding_preflight",
]
