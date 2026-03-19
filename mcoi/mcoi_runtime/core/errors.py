"""Purpose: canonical typed error taxonomy for the MCOI runtime.
Governance scope: all MCOI runtime error signaling.
Dependencies: Python standard library only.
Invariants: every error is classifiable, attributable, and actionable. Unclassified errors are platform defects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ErrorFamily(StrEnum):
    """Canonical error families per docs/08_error_taxonomy.md."""

    VALIDATION = "ValidationError"
    OBSERVATION = "ObservationError"
    ADMISSIBILITY = "AdmissibilityError"
    POLICY = "PolicyError"
    EXECUTION = "ExecutionError"
    VERIFICATION = "VerificationError"
    REPLAY = "ReplayError"
    PERSISTENCE = "PersistenceError"
    INTEGRATION = "IntegrationError"
    CAPABILITY = "CapabilityError"
    CONFIGURATION = "ConfigurationError"


class Recoverability(StrEnum):
    """How the caller should respond to this error."""

    RETRYABLE = "retryable"
    REOBSERVE_REQUIRED = "reobserve_required"
    REPLAN_REQUIRED = "replan_required"
    APPROVAL_REQUIRED = "approval_required"
    FATAL_FOR_RUN = "fatal_for_run"
    UNSUPPORTED = "unsupported"


class SourcePlane(StrEnum):
    """Which capability plane produced the error."""

    GOVERNANCE = "governance"
    PERCEPTION = "perception"
    WORLD_STATE = "world_state"
    CAPABILITY = "capability"
    PLANNING = "planning"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    MEMORY = "memory"
    COMMUNICATION = "communication"
    EXTERNAL_INTEGRATION = "external_integration"
    TEMPORAL = "temporal"
    COORDINATION = "coordination"
    META_REASONING = "meta_reasoning"


@dataclass(frozen=True, slots=True)
class StructuredError:
    """Canonical error record per docs/08_error_taxonomy.md.

    Every structured error carries:
    - error_code: machine-readable error identifier
    - family: one of the canonical error families
    - message: human-readable description
    - source_plane: which capability plane produced the error
    - recoverability: how the caller should respond
    - related_ids: identity chain for locating the failure point
    - context: additional machine-readable context
    """

    error_code: str
    family: ErrorFamily
    message: str
    source_plane: SourcePlane
    recoverability: Recoverability
    related_ids: tuple[str, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.error_code, str) or not self.error_code.strip():
            raise ValueError("error_code must be a non-empty string")
        if not isinstance(self.family, ErrorFamily):
            raise ValueError("family must be an ErrorFamily value")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        if not isinstance(self.source_plane, SourcePlane):
            raise ValueError("source_plane must be a SourcePlane value")
        if not isinstance(self.recoverability, Recoverability):
            raise ValueError("recoverability must be a Recoverability value")
        if isinstance(self.context, dict):
            object.__setattr__(self, "context", MappingProxyType(dict(self.context)))
        object.__setattr__(self, "related_ids", tuple(self.related_ids))


# --- Convenience constructors for common error patterns ---


def validation_error(
    error_code: str,
    message: str,
    *,
    source_plane: SourcePlane = SourcePlane.EXECUTION,
    recoverability: Recoverability = Recoverability.RETRYABLE,
    related_ids: tuple[str, ...] = (),
    context: Mapping[str, Any] | None = None,
) -> StructuredError:
    return StructuredError(
        error_code=error_code,
        family=ErrorFamily.VALIDATION,
        message=message,
        source_plane=source_plane,
        recoverability=recoverability,
        related_ids=related_ids,
        context=context or {},
    )


def admissibility_error(
    error_code: str,
    message: str,
    *,
    related_ids: tuple[str, ...] = (),
    context: Mapping[str, Any] | None = None,
) -> StructuredError:
    return StructuredError(
        error_code=error_code,
        family=ErrorFamily.ADMISSIBILITY,
        message=message,
        source_plane=SourcePlane.PLANNING,
        recoverability=Recoverability.APPROVAL_REQUIRED,
        related_ids=related_ids,
        context=context or {},
    )


def policy_error(
    error_code: str,
    message: str,
    *,
    recoverability: Recoverability = Recoverability.APPROVAL_REQUIRED,
    related_ids: tuple[str, ...] = (),
    context: Mapping[str, Any] | None = None,
) -> StructuredError:
    return StructuredError(
        error_code=error_code,
        family=ErrorFamily.POLICY,
        message=message,
        source_plane=SourcePlane.GOVERNANCE,
        recoverability=recoverability,
        related_ids=related_ids,
        context=context or {},
    )


def execution_error(
    error_code: str,
    message: str,
    *,
    recoverability: Recoverability = Recoverability.RETRYABLE,
    related_ids: tuple[str, ...] = (),
    context: Mapping[str, Any] | None = None,
) -> StructuredError:
    return StructuredError(
        error_code=error_code,
        family=ErrorFamily.EXECUTION,
        message=message,
        source_plane=SourcePlane.EXECUTION,
        recoverability=recoverability,
        related_ids=related_ids,
        context=context or {},
    )


def observation_error(
    error_code: str,
    message: str,
    *,
    related_ids: tuple[str, ...] = (),
    context: Mapping[str, Any] | None = None,
) -> StructuredError:
    return StructuredError(
        error_code=error_code,
        family=ErrorFamily.OBSERVATION,
        message=message,
        source_plane=SourcePlane.PERCEPTION,
        recoverability=Recoverability.REOBSERVE_REQUIRED,
        related_ids=related_ids,
        context=context or {},
    )


def verification_error(
    error_code: str,
    message: str,
    *,
    recoverability: Recoverability = Recoverability.REOBSERVE_REQUIRED,
    related_ids: tuple[str, ...] = (),
    context: Mapping[str, Any] | None = None,
) -> StructuredError:
    return StructuredError(
        error_code=error_code,
        family=ErrorFamily.VERIFICATION,
        message=message,
        source_plane=SourcePlane.VERIFICATION,
        recoverability=recoverability,
        related_ids=related_ids,
        context=context or {},
    )
