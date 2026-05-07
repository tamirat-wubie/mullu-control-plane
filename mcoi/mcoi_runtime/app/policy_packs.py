"""Purpose: reusable policy packs for deterministic policy configuration.
Governance scope: policy pack loading only.
Dependencies: policy contracts.
Invariants:
  - Policy packs are explicit and named.
  - Pack loading is deterministic.
  - No pack silently grants execution permissions.
  - Packs compose — multiple packs can be applied in order.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """A single policy rule within a pack."""

    rule_id: str
    description: str
    condition: str
    action: str  # allow, deny, escalate

    def __post_init__(self) -> None:
        if not self.rule_id or not self.rule_id.strip():
            raise ValueError("rule_id must be non-empty")
        if not self.description or not self.description.strip():
            raise ValueError("description must be non-empty")
        if not self.condition or not self.condition.strip():
            raise ValueError("condition must be non-empty")
        if self.action not in ("allow", "deny", "escalate"):
            raise ValueError("action must be one of: allow, deny, escalate")


@dataclass(frozen=True, slots=True)
class PolicyPack:
    """A named, reusable set of policy rules."""

    pack_id: str
    name: str
    description: str
    rules: tuple[PolicyRule, ...]

    def __post_init__(self) -> None:
        if not self.pack_id or not self.pack_id.strip():
            raise ValueError("pack_id must be non-empty")
        if not self.name or not self.name.strip():
            raise ValueError("name must be non-empty")
        if not self.rules:
            raise ValueError("rules must contain at least one rule")
        rule_ids = [r.rule_id for r in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule_ids must be unique within a pack")


@dataclass(frozen=True, slots=True)
class PolicyPackLoadResult:
    """Result of loading policy packs."""

    packs_loaded: tuple[str, ...]
    total_rules: int


# Built-in policy packs
_BUILTIN_PACKS: dict[str, PolicyPack] = {
    "default-safe": PolicyPack(
        pack_id="default-safe",
        name="Default Safe Policy",
        description="Conservative defaults — deny unknown, escalate ambiguous",
        rules=(
            PolicyRule(
                rule_id="deny-blocked-knowledge",
                description="Deny execution when blocked knowledge is present",
                condition="blocked_knowledge_present",
                action="deny",
            ),
            PolicyRule(
                rule_id="escalate-missing-capabilities",
                description="Escalate when required capabilities are missing",
                condition="missing_capabilities",
                action="escalate",
            ),
            PolicyRule(
                rule_id="escalate-operator-review",
                description="Escalate when operator review is requested",
                condition="operator_review_required",
                action="escalate",
            ),
            PolicyRule(
                rule_id="allow-satisfied",
                description="Allow when all policy conditions are satisfied",
                condition="all_conditions_satisfied",
                action="allow",
            ),
        ),
    ),
    "strict-approval": PolicyPack(
        pack_id="strict-approval",
        name="Strict Approval Policy",
        description="All executions require explicit operator approval",
        rules=(
            PolicyRule(
                rule_id="escalate-all",
                description="Escalate all execution requests for operator approval",
                condition="always",
                action="escalate",
            ),
        ),
    ),
    "readonly-only": PolicyPack(
        pack_id="readonly-only",
        name="Read-Only Policy",
        description="Deny all write operations, allow only read observations",
        rules=(
            PolicyRule(
                rule_id="deny-writes",
                description="Deny any execution with write effects",
                condition="has_write_effects",
                action="deny",
            ),
            PolicyRule(
                rule_id="allow-reads",
                description="Allow read-only observations and queries",
                condition="read_only",
                action="allow",
            ),
        ),
    ),
}


class PolicyPackRegistry:
    """Registry for loading and managing policy packs."""

    def __init__(self) -> None:
        self._packs: dict[str, PolicyPack] = dict(_BUILTIN_PACKS)

    def register(self, pack: PolicyPack) -> PolicyPack:
        if pack.pack_id in self._packs:
            raise ValueError("policy pack already registered")
        self._packs[pack.pack_id] = pack
        return pack

    def get(self, pack_id: str) -> PolicyPack | None:
        return self._packs.get(pack_id)

    def list_packs(self) -> tuple[PolicyPack, ...]:
        return tuple(sorted(self._packs.values(), key=lambda p: p.pack_id))

    def load_packs(self, pack_ids: tuple[str, ...]) -> PolicyPackLoadResult:
        """Load named policy packs. Unknown pack IDs fail closed."""
        for pid in pack_ids:
            if pid not in self._packs:
                raise ValueError("policy pack unavailable")
        total_rules = sum(len(self._packs[pid].rules) for pid in pack_ids)
        return PolicyPackLoadResult(
            packs_loaded=pack_ids,
            total_rules=total_rules,
        )
