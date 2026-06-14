"""Purpose: personal-assistant foundation runtime package.
Governance scope: governed skill registry, risk boundaries, and read-only
registry projections for the personal-assistant layer.
Dependencies: personal-assistant contracts and skill registry modules.
Invariants: registry loading is deterministic, receipt and UAO requirements are
preserved, and no live connector execution is exposed from this package.
"""

from __future__ import annotations

from .contracts import (
    EffectBoundary,
    PersonalAssistantInvariantError,
    PersonalAssistantSkill,
    SkillMode,
    SkillRiskLevel,
)
from .skill_registry import (
    PersonalAssistantSkillRegistry,
    load_default_skill_registry,
    load_skill_registry,
)

__all__ = (
    "EffectBoundary",
    "PersonalAssistantInvariantError",
    "PersonalAssistantSkill",
    "PersonalAssistantSkillRegistry",
    "SkillMode",
    "SkillRiskLevel",
    "load_default_skill_registry",
    "load_skill_registry",
)
