"""Purpose: expose pure WHQR semantic helpers.
Governance scope: side-effect-free semantic query evaluation, connector compilation, and static checks.
Dependencies: WHQR helper modules that are part of the tracked runtime surface.
Invariants: package exports do not initialize runtime state or perform effects.
"""

from .connectors import (
    AssertionKind,
    ConnectorCompilation,
    SemanticAssertion,
    compile_connector,
)
from .evaluator import WHQREvaluationContext, evaluate
from .static_checks import StaticCheckIssue, StaticCheckReport, validate_static

__all__ = [
    "AssertionKind",
    "ConnectorCompilation",
    "SemanticAssertion",
    "StaticCheckIssue",
    "StaticCheckReport",
    "WHQREvaluationContext",
    "compile_connector",
    "evaluate",
    "validate_static",
]
