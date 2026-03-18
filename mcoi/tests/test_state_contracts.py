"""Purpose: verify explicit state category separation in MCOI contracts.
Governance scope: Milestone 1 contract invariant tests.
Dependencies: the MCOI state contract layer.
Invariants: state categories remain explicit, distinct, and non-overlapping.
"""

from mcoi_runtime.contracts import StateCategory, StateReference


def test_state_category_values_are_explicit_and_distinct() -> None:
    assert StateCategory.KERNEL.value == "kernel"
    assert StateCategory.RUNTIME.value == "runtime"
    assert StateCategory.ENVIRONMENT.value == "environment"
    assert len({category.value for category in StateCategory}) == 3
    assert list(StateCategory) == [StateCategory.KERNEL, StateCategory.RUNTIME, StateCategory.ENVIRONMENT]


def test_state_reference_preserves_category_separation() -> None:
    kernel_state = StateReference(
        state_id="state-kernel-1",
        category=StateCategory.KERNEL,
        state_hash="hash-kernel",
        captured_at="2026-03-18T12:00:00+00:00",
    )
    environment_state = StateReference(
        state_id="state-env-1",
        category=StateCategory.ENVIRONMENT,
        state_hash="hash-environment",
        captured_at="2026-03-18T12:00:01+00:00",
    )

    assert kernel_state.category is StateCategory.KERNEL
    assert environment_state.category is StateCategory.ENVIRONMENT
    assert kernel_state.category is not environment_state.category
    assert kernel_state.state_hash != environment_state.state_hash
