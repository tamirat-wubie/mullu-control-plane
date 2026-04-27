"""
Action → construct type mapping for proof object v1 → v2 migration.

Versioned. Loaded by the bulk migration tool to synthesize v2 fields
(`construct_id`, `tier`) from v1 action strings.

The mapping table is the data side of the v1→v2 migration spec. See
`mcoi/mcoi_runtime/migration/PROOF_V1_TO_V2.md` §4 for the rules.

Migration tooling itself ships in Phase 2; this module is the static reference
that the tool will read.
"""
from __future__ import annotations

from typing import Mapping


MAPPING_VERSION = "1"


# Prefix → (construct_type, tier) pairs.
# Order matters: longest prefix wins. The tool iterates this dict in declared
# order and falls back to the catch-all entry for unknown prefixes.
ACTION_PREFIX_MAP: Mapping[str, tuple[str, int]] = {
    "budget.":            ("constraint",     1),
    "tenant.":            ("boundary",       1),
    "agent.invoke.":      ("execution",      5),
    "llm.call.":          ("execution",      5),
    "audit.write.":       ("validation",     4),
    "governance.guard.":  ("validation",     4),
    "workflow.step.":     ("transformation", 2),
    "policy.":            ("constraint",     1),
    "circuit.":           ("constraint",     1),
    "health.":            ("observation",    5),
}

# Catch-all for unknown prefixes. Conservative default: classify as Tier 5
# Execution. Reason: most legacy actions are agent-initiated work, which is
# semantically Execution; if we're wrong, the post-migration audit can rebin.
DEFAULT_MAPPING: tuple[str, int] = ("execution", 5)


def map_action_to_construct(action: str) -> tuple[str, int]:
    """Map a v1 action string to (construct_type, tier) for v2 synthesis.

    Longest-prefix-wins. Falls back to DEFAULT_MAPPING for unknown actions.
    """
    if not action:
        return DEFAULT_MAPPING
    matches = sorted(
        (prefix for prefix in ACTION_PREFIX_MAP if action.startswith(prefix)),
        key=len,
        reverse=True,
    )
    if matches:
        return ACTION_PREFIX_MAP[matches[0]]
    return DEFAULT_MAPPING


def known_prefixes() -> tuple[str, ...]:
    return tuple(ACTION_PREFIX_MAP.keys())
