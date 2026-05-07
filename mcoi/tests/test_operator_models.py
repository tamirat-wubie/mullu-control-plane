"""Purpose: verify bounded request-model contracts for the app layer.
Governance scope: operator request model tests only.
Dependencies: operator models and runtime invariant contracts.
Invariants: identity-field validation stays bounded and does not reflect field names.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app.operator_models import OperatorRequest, SkillRequest
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def test_operator_request_bounds_identity_validation() -> None:
    with pytest.raises(
        RuntimeCoreInvariantError,
        match="^request identity fields must be non-empty strings$",
    ) as exc_info:
        OperatorRequest(
            request_id="",
            subject_id="subject-1",
            goal_id="goal-1",
            template={},
            bindings={},
        )

    message = str(exc_info.value)
    assert message == "request identity fields must be non-empty strings"
    assert "request_id" not in message
    assert "subject_id" not in message


def test_skill_request_bounds_identity_validation() -> None:
    with pytest.raises(
        RuntimeCoreInvariantError,
        match="^request identity fields must be non-empty strings$",
    ) as exc_info:
        SkillRequest(
            request_id="request-1",
            subject_id="",
            goal_id="goal-1",
        )

    message = str(exc_info.value)
    assert message == "request identity fields must be non-empty strings"
    assert "subject_id" not in message
    assert "goal_id" not in message
