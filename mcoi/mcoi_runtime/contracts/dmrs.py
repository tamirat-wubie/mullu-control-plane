"""Purpose: DMRS (Dynamic Memory Routing Substrate) contract definitions.
Governance scope: context, demand, version, rule, constraint, proof, and routing result types.
Dependencies: Python standard library only (dataclasses, enum, hashlib).
Invariants:
  - All contracts are frozen and immutable after creation.
  - __post_init__ validates every field; silent invalid state is rejected.
  - Proof hashes are deterministic SHA-256.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

_VALID_LOADS = ("low", "medium", "high", "critical")
_VALID_FLAGS = frozenset({"archive_mode", "readonly", "trace_enabled"})


class DMRSDemand(enum.Enum):
    """Demand signal describing the memory operation requested."""

    RECALL = "recall"
    REASONING = "reasoning"
    ANALYSIS = "analysis"
    ARCHIVE = "archive"


class DMRSMemoryVersion(enum.Enum):
    """Memory version tier selected by the routing kernel."""

    V1_LIGHT = "v1_light"
    V2_STD = "v2_std"
    V3_DEEP = "v3_deep"
    VA_ARCH = "va_arch"


class DMRSRule(enum.Enum):
    """Named routing rule that justified a version selection."""

    RULE_ARCHIVE = "rule_archive"
    RULE_RECALL_LIGHT = "rule_recall_light"
    RULE_RECALL_STD = "rule_recall_std"
    RULE_ANALYSIS_STD = "rule_analysis_std"
    RULE_ANALYSIS_DEEP = "rule_analysis_deep"
    RULE_REASONING_STD = "rule_reasoning_std"
    RULE_FALLBACK = "rule_fallback"


class DMRSConstraint(enum.Enum):
    """Constraint that must hold for a route to be valid."""

    IMMUTABLE = "immutable"
    SCHEMA_VALID = "schema_valid"
    RECURSION_CAP = "recursion_cap"
    VERSION_EXISTS = "version_exists"
    RULE_MATCH = "rule_match"
    LOAD_BALANCE = "load_balance"


# ---------------------------------------------------------------------------
# Data contracts (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DMRSContext:
    """Immutable snapshot of current routing context."""

    depth: int
    load: str
    flags: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.depth, int):
            raise TypeError("depth must be an int")
        if self.depth < 0 or self.depth > 3:
            raise ValueError("depth must be between 0 and 3 inclusive")
        if not isinstance(self.load, str):
            raise TypeError("load must be a str")
        if self.load not in _VALID_LOADS:
            raise ValueError("load must be one of the supported values")
        if not isinstance(self.flags, tuple):
            raise TypeError("flags must be a tuple of str")
        for flag in self.flags:
            if not isinstance(flag, str):
                raise TypeError("each flag must be a str")
            if flag not in _VALID_FLAGS:
                raise ValueError("invalid flag; must use a supported value")


@dataclass(frozen=True, slots=True)
class DMRSProof:
    """Cryptographic proof of a routing decision.

    All governance-critical fields use enum types so that proofs are
    verifiable at the type level — an arbitrary string cannot masquerade
    as a valid rule or demand.
    """

    version_id: DMRSMemoryVersion
    rule_id: DMRSRule
    constraints_verified: tuple[DMRSConstraint, ...]
    recursion_depth: int
    context_hash: str
    demand: DMRSDemand
    precedence_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.version_id, DMRSMemoryVersion):
            raise TypeError("version_id must be a DMRSMemoryVersion")
        if not isinstance(self.rule_id, DMRSRule):
            raise TypeError("rule_id must be a DMRSRule")
        if not isinstance(self.constraints_verified, tuple):
            raise TypeError("constraints_verified must be a tuple")
        for c in self.constraints_verified:
            if not isinstance(c, DMRSConstraint):
                raise TypeError("each constraint must be a DMRSConstraint")
        if not isinstance(self.recursion_depth, int):
            raise TypeError("recursion_depth must be an int")
        if self.recursion_depth < 0:
            raise ValueError("recursion_depth must be non-negative")
        if not isinstance(self.context_hash, str) or not self.context_hash.strip():
            raise ValueError("context_hash must be a non-empty string")
        if not isinstance(self.demand, DMRSDemand):
            raise TypeError("demand must be a DMRSDemand")
        if not isinstance(self.precedence_hash, str) or not self.precedence_hash.strip():
            raise ValueError("precedence_hash must be a non-empty string")


@dataclass(frozen=True, slots=True)
class DMRSRouteResult:
    """Successful routing outcome."""

    version: DMRSMemoryVersion
    proof: DMRSProof
    routed_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.version, DMRSMemoryVersion):
            raise TypeError("version must be a DMRSMemoryVersion")
        if not isinstance(self.proof, DMRSProof):
            raise TypeError("proof must be a DMRSProof")
        if not isinstance(self.routed_at, str) or not self.routed_at.strip():
            raise ValueError("routed_at must be a non-empty string")


@dataclass(frozen=True, slots=True)
class DMRSRouteError:
    """Routing failure descriptor."""

    error_code: str
    detail: str
    context_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.error_code, str) or not self.error_code.strip():
            raise ValueError("error_code must be a non-empty string")
        if not isinstance(self.detail, str):
            raise TypeError("detail must be a string")
        if not isinstance(self.context_hash, str) or not self.context_hash.strip():
            raise ValueError("context_hash must be a non-empty string")
