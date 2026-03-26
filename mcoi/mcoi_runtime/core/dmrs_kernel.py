"""Purpose: DMRS Kernel -- pure-function routing engine for memory version selection.
Governance scope: deterministic routing logic, proof construction, no state mutation.
Dependencies: Python standard library only (hashlib, datetime, json).
Invariants:
  - The kernel is stateless: route() is a pure function with no side effects.
  - Every successful route produces a cryptographic proof (SHA-256).
  - Flag overrides take precedence over demand-based selection.
  - Context depth and load are validated before routing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from mcoi_runtime.contracts.dmrs import (
    DMRSConstraint,
    DMRSContext,
    DMRSDemand,
    DMRSMemoryVersion,
    DMRSProof,
    DMRSRouteError,
    DMRSRouteResult,
    DMRSRule,
)


class DMRSKernel:
    """Pure-function routing kernel for the Dynamic Memory Routing Substrate.

    All methods are stateless. The kernel holds no mutable state and performs
    no I/O. Every routing decision is accompanied by a deterministic SHA-256
    proof that can be independently verified.
    """

    # -- public API ----------------------------------------------------------

    @staticmethod
    def route(context: DMRSContext, demand: DMRSDemand) -> DMRSRouteResult | DMRSRouteError:
        """Route a memory demand to the appropriate version tier.

        Selection logic:
          1. Flag overrides (highest precedence):
             - archive_mode  -> VA_ARCH
             - readonly      -> V1_LIGHT
          2. Demand-based selection:
             - ARCHIVE                   -> VA_ARCH
             - RECALL  + load=="low"     -> V1_LIGHT
             - RECALL  + other load      -> V2_STD
             - ANALYSIS + depth >= 2     -> V3_DEEP
             - ANALYSIS + other          -> V2_STD
             - REASONING                 -> V2_STD
          3. Fallback                    -> V2_STD

        Returns DMRSRouteResult on success, DMRSRouteError on invalid input.
        """
        # Validate inputs
        if not isinstance(context, DMRSContext):
            return _error("INVALID_CONTEXT", "context must be a DMRSContext", "n/a")
        if not isinstance(demand, DMRSDemand):
            return _error("INVALID_DEMAND", "demand must be a DMRSDemand", "n/a")

        context_hash = _hash_context(context)

        # Flag overrides (highest precedence)
        if "archive_mode" in context.flags:
            return _build_result(
                DMRSMemoryVersion.VA_ARCH,
                DMRSRule.RULE_ARCHIVE,
                context,
                demand,
                context_hash,
            )

        if "readonly" in context.flags:
            return _build_result(
                DMRSMemoryVersion.V1_LIGHT,
                DMRSRule.RULE_RECALL_LIGHT,
                context,
                demand,
                context_hash,
            )

        # Demand-based selection
        version, rule = _select_by_demand(context, demand)

        return _build_result(version, rule, context, demand, context_hash)


# ---------------------------------------------------------------------------
# Internal helpers (module-private)
# ---------------------------------------------------------------------------


def _select_by_demand(
    context: DMRSContext, demand: DMRSDemand
) -> tuple[DMRSMemoryVersion, DMRSRule]:
    """Determine version and rule from demand + context without flag overrides."""
    if demand is DMRSDemand.ARCHIVE:
        return DMRSMemoryVersion.VA_ARCH, DMRSRule.RULE_ARCHIVE

    if demand is DMRSDemand.RECALL:
        if context.load == "low":
            return DMRSMemoryVersion.V1_LIGHT, DMRSRule.RULE_RECALL_LIGHT
        return DMRSMemoryVersion.V2_STD, DMRSRule.RULE_RECALL_STD

    if demand is DMRSDemand.ANALYSIS:
        if context.depth >= 2:
            return DMRSMemoryVersion.V3_DEEP, DMRSRule.RULE_ANALYSIS_DEEP
        return DMRSMemoryVersion.V2_STD, DMRSRule.RULE_ANALYSIS_STD

    if demand is DMRSDemand.REASONING:
        return DMRSMemoryVersion.V2_STD, DMRSRule.RULE_REASONING_STD

    # Fallback (should not happen with current enum, but defensive)
    return DMRSMemoryVersion.V2_STD, DMRSRule.RULE_FALLBACK


def _hash_context(context: DMRSContext) -> str:
    """Compute deterministic SHA-256 hash of a DMRSContext."""
    payload = json.dumps(
        {"depth": context.depth, "load": context.load, "flags": list(context.flags)},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash_precedence(version: DMRSMemoryVersion, rule: DMRSRule, demand: DMRSDemand) -> str:
    """Compute deterministic SHA-256 hash of the precedence chain."""
    payload = json.dumps(
        {"version": version.value, "rule": rule.value, "demand": demand.value},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_result(
    version: DMRSMemoryVersion,
    rule: DMRSRule,
    context: DMRSContext,
    demand: DMRSDemand,
    context_hash: str,
) -> DMRSRouteResult:
    """Construct a DMRSRouteResult with full proof."""
    constraints_verified = tuple(c.value for c in DMRSConstraint)
    precedence_hash = _hash_precedence(version, rule, demand)

    proof = DMRSProof(
        version_id=version.value,
        rule_id=rule.value,
        constraints_verified=constraints_verified,
        recursion_depth=context.depth,
        context_hash=context_hash,
        demand=demand.value,
        precedence_hash=precedence_hash,
    )

    return DMRSRouteResult(
        version=version,
        proof=proof,
        routed_at=datetime.now(timezone.utc).isoformat(),
    )


def _error(code: str, detail: str, context_hash: str) -> DMRSRouteError:
    """Build a DMRSRouteError."""
    return DMRSRouteError(error_code=code, detail=detail, context_hash=context_hash)
