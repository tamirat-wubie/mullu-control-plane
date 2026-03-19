"""Purpose: verify canonical typed error taxonomy and structured error records.
Governance scope: error taxonomy tests only.
Dependencies: core/errors module.
Invariants: every error is classifiable, attributable, and actionable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.errors import (
    ErrorFamily,
    Recoverability,
    SourcePlane,
    StructuredError,
    admissibility_error,
    execution_error,
    observation_error,
    policy_error,
    validation_error,
    verification_error,
)


def test_structured_error_carries_all_required_fields() -> None:
    error = StructuredError(
        error_code="test_code",
        family=ErrorFamily.VALIDATION,
        message="test message",
        source_plane=SourcePlane.EXECUTION,
        recoverability=Recoverability.RETRYABLE,
        related_ids=("id-1", "id-2"),
        context={"key": "value"},
    )
    assert error.error_code == "test_code"
    assert error.family is ErrorFamily.VALIDATION
    assert error.message == "test message"
    assert error.source_plane is SourcePlane.EXECUTION
    assert error.recoverability is Recoverability.RETRYABLE
    assert error.related_ids == ("id-1", "id-2")
    assert error.context == {"key": "value"}


def test_structured_error_rejects_empty_error_code() -> None:
    with pytest.raises(ValueError, match="error_code"):
        StructuredError(
            error_code="",
            family=ErrorFamily.VALIDATION,
            message="test",
            source_plane=SourcePlane.EXECUTION,
            recoverability=Recoverability.RETRYABLE,
        )


def test_structured_error_rejects_empty_message() -> None:
    with pytest.raises(ValueError, match="message"):
        StructuredError(
            error_code="code",
            family=ErrorFamily.VALIDATION,
            message="",
            source_plane=SourcePlane.EXECUTION,
            recoverability=Recoverability.RETRYABLE,
        )


def test_structured_error_defaults() -> None:
    error = StructuredError(
        error_code="code",
        family=ErrorFamily.EXECUTION,
        message="msg",
        source_plane=SourcePlane.EXECUTION,
        recoverability=Recoverability.FATAL_FOR_RUN,
    )
    assert error.related_ids == ()
    assert error.context == {}


def test_all_error_families_are_distinct() -> None:
    values = [f.value for f in ErrorFamily]
    assert len(values) == len(set(values))
    assert len(values) == 11


def test_all_recoverability_classes_are_distinct() -> None:
    values = [r.value for r in Recoverability]
    assert len(values) == len(set(values))
    assert len(values) == 6


def test_all_source_planes_are_distinct() -> None:
    values = [s.value for s in SourcePlane]
    assert len(values) == len(set(values))
    assert len(values) == 13


def test_validation_error_convenience() -> None:
    err = validation_error("bad_input", "input failed validation")
    assert err.family is ErrorFamily.VALIDATION
    assert err.source_plane is SourcePlane.EXECUTION
    assert err.recoverability is Recoverability.RETRYABLE


def test_admissibility_error_convenience() -> None:
    err = admissibility_error(
        "knowledge_rejected", "rejected",
        related_ids=("k-1",),
    )
    assert err.family is ErrorFamily.ADMISSIBILITY
    assert err.source_plane is SourcePlane.PLANNING
    assert err.recoverability is Recoverability.APPROVAL_REQUIRED
    assert err.related_ids == ("k-1",)


def test_policy_error_convenience() -> None:
    err = policy_error("policy_deny", "denied")
    assert err.family is ErrorFamily.POLICY
    assert err.source_plane is SourcePlane.GOVERNANCE


def test_execution_error_convenience() -> None:
    err = execution_error("timeout", "timed out")
    assert err.family is ErrorFamily.EXECUTION
    assert err.source_plane is SourcePlane.EXECUTION


def test_observation_error_convenience() -> None:
    err = observation_error("path_missing", "file not found")
    assert err.family is ErrorFamily.OBSERVATION
    assert err.source_plane is SourcePlane.PERCEPTION
    assert err.recoverability is Recoverability.REOBSERVE_REQUIRED


def test_verification_error_convenience() -> None:
    err = verification_error("mismatch", "verification failed")
    assert err.family is ErrorFamily.VERIFICATION
    assert err.source_plane is SourcePlane.VERIFICATION
