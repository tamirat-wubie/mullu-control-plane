"""Purpose: verify versioned policy artifacts and shadow governance.

Governance scope: policy artifact registration, diff, promotion, rollback, and
shadow-mode verdict comparison.
Dependencies: policy_versioning core module and policy engine inputs.
Invariants: artifact hashes are deterministic; rollback targets are explicit;
shadow evaluation never promotes a policy version.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.governance.policy.engine import PolicyInput
from mcoi_runtime.governance.policy.versioning import (
    PolicyArtifact,
    PolicyVersionRegistry,
    ShadowGovernanceEvaluator,
    VersionedPolicyRule,
)


_CLOCK = "2026-04-25T12:00:00+00:00"


def _artifact(version: str, rules: tuple[VersionedPolicyRule, ...]) -> PolicyArtifact:
    return PolicyArtifact.create(
        policy_id="tenant-governance",
        version=version,
        rules=rules,
        created_at=_CLOCK,
    )


def _allow_read_rule() -> VersionedPolicyRule:
    return VersionedPolicyRule(
        rule_id="allow-reads",
        description="Allow read-only requests",
        condition="read_only",
        action="allow",
    )


def _deny_write_rule() -> VersionedPolicyRule:
    return VersionedPolicyRule(
        rule_id="deny-writes",
        description="Deny write requests",
        condition="has_write_effects",
        action="deny",
    )


def _escalate_write_rule() -> VersionedPolicyRule:
    return VersionedPolicyRule(
        rule_id="deny-writes",
        description="Escalate write requests",
        condition="has_write_effects",
        action="escalate",
    )


def _input(*, has_write_effects: bool) -> PolicyInput:
    return PolicyInput(
        subject_id="subject-1",
        goal_id="goal-1",
        issued_at=_CLOCK,
        has_write_effects=has_write_effects,
    )


def test_policy_artifact_hash_is_deterministic() -> None:
    first = _artifact("v1", (_deny_write_rule(), _allow_read_rule()))
    second = _artifact("v1", (_deny_write_rule(), _allow_read_rule()))

    assert first.artifact_hash == second.artifact_hash
    assert first.artifact_hash.startswith("policy-artifact-")
    assert first.pack_id == "tenant-governance"


def test_policy_registry_promotes_and_rolls_back_versions() -> None:
    registry = PolicyVersionRegistry()
    registry.register(_artifact("v1", (_deny_write_rule(), _allow_read_rule())))
    registry.register(_artifact("v2", (_escalate_write_rule(), _allow_read_rule())))

    promoted = registry.promote("tenant-governance", "v1")
    next_promoted = registry.promote("tenant-governance", "v2")
    rolled_back = registry.rollback("tenant-governance")

    assert promoted.version == "v1"
    assert next_promoted.version == "v2"
    assert rolled_back.version == "v1"


def test_policy_diff_reports_changed_and_added_rules() -> None:
    registry = PolicyVersionRegistry()
    registry.register(_artifact("v1", (_deny_write_rule(),)))
    registry.register(_artifact("v2", (_escalate_write_rule(), _allow_read_rule())))

    diff = registry.diff("tenant-governance", "v1", "v2")
    change_by_rule = {entry.rule_id: entry.change for entry in diff.rule_diffs}

    assert diff.changed is True
    assert change_by_rule["deny-writes"] == "changed"
    assert change_by_rule["allow-reads"] == "added"


def test_shadow_governance_compares_without_promoting() -> None:
    registry = PolicyVersionRegistry()
    registry.register(_artifact("v1", (_deny_write_rule(), _allow_read_rule())))
    registry.register(_artifact("v2", (_escalate_write_rule(), _allow_read_rule())))
    registry.promote("tenant-governance", "v1")
    evaluator = ShadowGovernanceEvaluator(registry)

    result = evaluator.evaluate(_input(has_write_effects=True), policy_id="tenant-governance", shadow_version="v2")
    active_after_shadow = registry.get("tenant-governance")

    assert result.active_status == "deny"
    assert result.shadow_status == "escalate"
    assert result.verdict_changed is True
    assert result.promoted is False
    assert active_after_shadow is not None
    assert active_after_shadow.version == "v1"


def test_registry_fails_closed_on_unknown_versions() -> None:
    registry = PolicyVersionRegistry()
    registry.register(_artifact("v1", (_deny_write_rule(),)))

    with pytest.raises(ValueError, match="unavailable"):
        registry.promote("tenant-governance", "v2")

    with pytest.raises(ValueError, match="rollback target"):
        registry.rollback("tenant-governance")

    assert registry.get("tenant-governance") is None
