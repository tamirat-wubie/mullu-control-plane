"""Purpose: verify frozen contract behavior for representative MCOI records.
Governance scope: Milestone 1 contract invariant tests.
Dependencies: pytest and the MCOI contract layer.
Invariants: contract mutation is explicit and nested mappings do not mutate silently.
"""

from dataclasses import FrozenInstanceError

import pytest

from mcoi_runtime.contracts import CapabilityDescriptor, ExecutionOutcome, ExecutionResult


def test_representative_contracts_are_frozen() -> None:
    capability = CapabilityDescriptor(
        capability_id="cap-1",
        subject_id="subject-1",
        name="filesystem-observe",
        version="1.0.0",
        scope="workspace",
        constraints=("read-only",),
    )

    assert capability.name == "filesystem-observe"
    assert capability.scope == "workspace"
    assert capability.constraints == ("read-only",)

    with pytest.raises(FrozenInstanceError):
        capability.name = "mutated"

    assert capability.name == "filesystem-observe"


def test_nested_contract_mappings_do_not_allow_silent_mutation() -> None:
    result = ExecutionResult(
        execution_id="exec-1",
        goal_id="goal-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(),
        assumed_effects=(),
        started_at="2026-03-18T12:00:00+00:00",
        finished_at="2026-03-18T12:01:00+00:00",
        metadata={"source": {"kind": "observer"}},
    )

    assert result.status is ExecutionOutcome.SUCCEEDED
    assert result.metadata["source"]["kind"] == "observer"
    assert result.to_dict()["metadata"]["source"]["kind"] == "observer"

    with pytest.raises(TypeError):
        result.metadata["source"] = "mutated"

    assert result.metadata["source"]["kind"] == "observer"
