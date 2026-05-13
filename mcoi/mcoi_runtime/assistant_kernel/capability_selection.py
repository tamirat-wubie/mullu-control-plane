"""Purpose: deterministic assistant capability selection.
Governance scope: profile-scoped capability admission, forbidden capability
    denial, and approval-control projection for external effects.
Dependencies: dataclasses and assistant profile contracts.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Selection never executes a capability.
  - Missing and forbidden capabilities fail closed before planning.
  - Capabilities ending in with_approval require explicit approval controls.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.assistant_kernel.identity import AssistantProfile
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


APPROVAL_REQUIRED_SUFFIX = ".with_approval"


@dataclass(frozen=True, slots=True)
class CapabilitySelection:
    """Result of selecting capabilities for an assistant goal."""

    accepted: bool
    reason: str
    selected_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    approval_required_capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_capabilities", tuple(self.selected_capabilities))
        object.__setattr__(self, "missing_capabilities", tuple(self.missing_capabilities))
        object.__setattr__(self, "forbidden_capabilities", tuple(self.forbidden_capabilities))
        object.__setattr__(self, "approval_required_capabilities", tuple(self.approval_required_capabilities))


def select_capabilities(
    profile: AssistantProfile,
    required_capabilities: tuple[str, ...],
) -> CapabilitySelection:
    """Select required capabilities from one assistant profile."""
    required = _normalize_text_tuple(required_capabilities, "required_capabilities")
    allowed = set(profile.allowed_capabilities)
    forbidden = set(profile.forbidden_capabilities)
    missing = tuple(capability for capability in required if capability not in allowed)
    blocked = tuple(capability for capability in required if capability in forbidden)
    approval_required = tuple(capability for capability in required if capability.endswith(APPROVAL_REQUIRED_SUFFIX))
    if blocked:
        return CapabilitySelection(
            accepted=False,
            reason="forbidden_capability",
            selected_capabilities=(),
            missing_capabilities=missing,
            forbidden_capabilities=blocked,
            approval_required_capabilities=approval_required,
        )
    if missing:
        return CapabilitySelection(
            accepted=False,
            reason="missing_capability",
            selected_capabilities=(),
            missing_capabilities=missing,
            forbidden_capabilities=(),
            approval_required_capabilities=approval_required,
        )
    return CapabilitySelection(
        accepted=True,
        reason="capability_selection_passed",
        selected_capabilities=required,
        missing_capabilities=(),
        forbidden_capabilities=(),
        approval_required_capabilities=approval_required,
    )


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized
