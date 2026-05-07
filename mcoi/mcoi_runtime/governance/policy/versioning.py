"""Purpose: versioned policy artifacts and shadow governance evaluation.

Governance scope: policy artifact registration, diff, promotion, rollback, and
shadow-mode verdict comparison without mutating runtime execution decisions.
Dependencies: runtime policy engine contracts and deterministic identifiers.
Invariants: artifacts are immutable; active versions are explicit; rollback
targets must be known; shadow evaluation never promotes a version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier
from .engine import PolicyEngine, PolicyInput, PolicyReason, PolicyStatus

PolicyChangeKind = Literal["added", "removed", "changed", "unchanged"]


class VersionedPolicyRuleLike(Protocol):
    """Read-only rule subset required for policy version artifacts."""

    rule_id: str
    description: str
    condition: str
    action: str


@dataclass(frozen=True, slots=True)
class VersionedPolicyRule:
    """Immutable policy rule snapshot."""

    rule_id: str
    description: str
    condition: str
    action: PolicyStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", ensure_non_empty_text("rule_id", self.rule_id))
        object.__setattr__(self, "description", ensure_non_empty_text("description", self.description))
        object.__setattr__(self, "condition", ensure_non_empty_text("condition", self.condition))
        if self.action not in ("allow", "deny", "escalate"):
            raise ValueError("action must be one of: allow, deny, escalate")

    @classmethod
    def from_rule(cls, rule: VersionedPolicyRuleLike) -> VersionedPolicyRule:
        return cls(
            rule_id=rule.rule_id,
            description=rule.description,
            condition=rule.condition,
            action=rule.action,  # type: ignore[arg-type]
        )

    def fingerprint_payload(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "condition": self.condition,
            "action": self.action,
        }


@dataclass(frozen=True, slots=True)
class PolicyArtifact:
    """Versioned policy artifact used by the registry and shadow evaluator."""

    policy_id: str
    version: str
    rules: tuple[VersionedPolicyRule, ...]
    created_at: str
    artifact_hash: str = ""

    @classmethod
    def create(
        cls,
        *,
        policy_id: str,
        version: str,
        rules: tuple[VersionedPolicyRule, ...],
        created_at: str,
    ) -> PolicyArtifact:
        artifact = cls(
            policy_id=policy_id,
            version=version,
            rules=rules,
            created_at=created_at,
        )
        return artifact.with_hash()

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", ensure_non_empty_text("policy_id", self.policy_id))
        object.__setattr__(self, "version", ensure_non_empty_text("version", self.version))
        object.__setattr__(self, "created_at", ensure_non_empty_text("created_at", self.created_at))
        if not self.rules:
            raise ValueError("rules must contain at least one rule")
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule ids must be unique within a policy artifact")

    @property
    def pack_id(self) -> str:
        return self.policy_id

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "rules": [rule.fingerprint_payload() for rule in self.rules],
        }

    def with_hash(self) -> PolicyArtifact:
        artifact_hash = stable_identifier("policy-artifact", self.fingerprint_payload())
        return PolicyArtifact(
            policy_id=self.policy_id,
            version=self.version,
            rules=self.rules,
            created_at=self.created_at,
            artifact_hash=artifact_hash,
        )


@dataclass(frozen=True, slots=True)
class PolicyRuleDiff:
    """Single rule-level diff entry between two policy versions."""

    rule_id: str
    change: PolicyChangeKind
    before: dict[str, str] | None = None
    after: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class PolicyVersionDiff:
    """Deterministic diff between two policy artifacts."""

    policy_id: str
    from_version: str
    to_version: str
    changed: bool
    rule_diffs: tuple[PolicyRuleDiff, ...]


@dataclass(frozen=True, slots=True)
class PolicyDecisionSnapshot:
    """Minimal typed decision emitted during shadow evaluation."""

    decision_id: str
    subject_id: str
    goal_id: str
    status: PolicyStatus
    reasons: tuple[PolicyReason, ...]
    issued_at: str


@dataclass(frozen=True, slots=True)
class ShadowGovernanceResult:
    """Comparison between active and shadow policy verdicts."""

    policy_id: str
    active_version: str
    shadow_version: str
    active_status: PolicyStatus
    shadow_status: PolicyStatus
    verdict_changed: bool
    active_reason_codes: tuple[str, ...]
    shadow_reason_codes: tuple[str, ...]
    promoted: bool = False


class PolicyVersionRegistry:
    """In-memory versioned policy registry with explicit active pointers."""

    def __init__(self) -> None:
        self._artifacts: dict[tuple[str, str], PolicyArtifact] = {}
        self._active_versions: dict[str, str] = {}
        self._previous_versions: dict[str, tuple[str, ...]] = {}

    def register(self, artifact: PolicyArtifact) -> PolicyArtifact:
        key = (artifact.policy_id, artifact.version)
        if key in self._artifacts:
            raise ValueError("policy artifact version already registered")
        stored = artifact.with_hash()
        self._artifacts[key] = stored
        self._previous_versions.setdefault(artifact.policy_id, ())
        return stored

    def get_version(self, policy_id: str, version: str) -> PolicyArtifact | None:
        return self._artifacts.get((policy_id, version))

    def get(self, policy_id: str) -> PolicyArtifact | None:
        active_version = self._active_versions.get(policy_id)
        if active_version is None:
            return None
        return self.get_version(policy_id, active_version)

    def promote(self, policy_id: str, version: str) -> PolicyArtifact:
        artifact = self.get_version(policy_id, version)
        if artifact is None:
            raise ValueError("policy artifact version unavailable")
        current = self._active_versions.get(policy_id)
        if current is not None and current != version:
            self._previous_versions[policy_id] = (*self._previous_versions.get(policy_id, ()), current)
        self._active_versions[policy_id] = version
        return artifact

    def rollback(self, policy_id: str) -> PolicyArtifact:
        history = self._previous_versions.get(policy_id, ())
        if not history:
            raise ValueError("policy rollback target unavailable")
        target = history[-1]
        self._previous_versions[policy_id] = history[:-1]
        self._active_versions[policy_id] = target
        artifact = self.get_version(policy_id, target)
        if artifact is None:
            raise ValueError("policy rollback target unavailable")
        return artifact

    def diff(self, policy_id: str, from_version: str, to_version: str) -> PolicyVersionDiff:
        before = self.get_version(policy_id, from_version)
        after = self.get_version(policy_id, to_version)
        if before is None or after is None:
            raise ValueError("policy artifact version unavailable")
        before_rules = {rule.rule_id: rule for rule in before.rules}
        after_rules = {rule.rule_id: rule for rule in after.rules}
        diffs: list[PolicyRuleDiff] = []
        for rule_id in sorted(set(before_rules) | set(after_rules)):
            before_rule = before_rules.get(rule_id)
            after_rule = after_rules.get(rule_id)
            if before_rule is None and after_rule is not None:
                diffs.append(PolicyRuleDiff(rule_id=rule_id, change="added", after=after_rule.fingerprint_payload()))
            elif before_rule is not None and after_rule is None:
                diffs.append(PolicyRuleDiff(rule_id=rule_id, change="removed", before=before_rule.fingerprint_payload()))
            elif before_rule is not None and after_rule is not None:
                before_payload = before_rule.fingerprint_payload()
                after_payload = after_rule.fingerprint_payload()
                diffs.append(
                    PolicyRuleDiff(
                        rule_id=rule_id,
                        change="unchanged" if before_payload == after_payload else "changed",
                        before=before_payload,
                        after=after_payload,
                    )
                )
        return PolicyVersionDiff(
            policy_id=policy_id,
            from_version=from_version,
            to_version=to_version,
            changed=any(diff.change != "unchanged" for diff in diffs),
            rule_diffs=tuple(diffs),
        )


class ShadowGovernanceEvaluator:
    """Evaluate active and shadow policy versions without promotion."""

    def __init__(self, registry: PolicyVersionRegistry) -> None:
        self._registry = registry

    def evaluate(
        self,
        policy_input: PolicyInput,
        *,
        policy_id: str,
        shadow_version: str,
    ) -> ShadowGovernanceResult:
        active_artifact = self._registry.get(policy_id)
        shadow_artifact = self._registry.get_version(policy_id, shadow_version)
        if active_artifact is None or shadow_artifact is None:
            raise ValueError("policy artifact version unavailable")

        active_decision = _evaluate_artifact(policy_input, active_artifact)
        shadow_decision = _evaluate_artifact(policy_input, shadow_artifact)
        return ShadowGovernanceResult(
            policy_id=policy_id,
            active_version=active_artifact.version,
            shadow_version=shadow_artifact.version,
            active_status=active_decision.status,
            shadow_status=shadow_decision.status,
            verdict_changed=active_decision.status != shadow_decision.status,
            active_reason_codes=tuple(reason.code for reason in active_decision.reasons),
            shadow_reason_codes=tuple(reason.code for reason in shadow_decision.reasons),
            promoted=False,
        )


def _decision_factory(**kwargs: object) -> PolicyDecisionSnapshot:
    return PolicyDecisionSnapshot(**kwargs)  # type: ignore[arg-type]


def _evaluate_artifact(policy_input: PolicyInput, artifact: PolicyArtifact) -> PolicyDecisionSnapshot:
    engine: PolicyEngine[PolicyDecisionSnapshot] = PolicyEngine(pack_resolver=_SingleArtifactResolver(artifact))
    scoped_input = PolicyInput(
        subject_id=policy_input.subject_id,
        goal_id=policy_input.goal_id,
        issued_at=policy_input.issued_at,
        blocked_knowledge_ids=policy_input.blocked_knowledge_ids,
        missing_capability_ids=policy_input.missing_capability_ids,
        requires_operator_review=policy_input.requires_operator_review,
        policy_pack_id=artifact.policy_id,
        policy_pack_version=artifact.version,
        has_write_effects=policy_input.has_write_effects,
    )
    return engine.evaluate(scoped_input, _decision_factory)


@dataclass(frozen=True, slots=True)
class _SingleArtifactResolver:
    artifact: PolicyArtifact

    def get(self, pack_id: str) -> PolicyArtifact | None:
        if pack_id != self.artifact.policy_id:
            return None
        return self.artifact
