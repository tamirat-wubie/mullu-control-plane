"""Purpose: canonical shared enum definitions used across multiple contract modules.
Governance scope: shared classification enums only.
Dependencies: Python standard library only.
Invariants: single source of truth for EffectClass and TrustClass enums.
"""

from __future__ import annotations

from enum import StrEnum


class EffectClass(StrEnum):
    """What kind of side effects an operation may produce."""

    INTERNAL_PURE = "internal_pure"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    HUMAN_MEDIATED = "human_mediated"
    PRIVILEGED = "privileged"


class TrustClass(StrEnum):
    """How much the platform trusts the operation's source."""

    TRUSTED_INTERNAL = "trusted_internal"
    BOUNDED_EXTERNAL = "bounded_external"
    UNTRUSTED_EXTERNAL = "untrusted_external"
