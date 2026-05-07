"""Purpose: canonical governance DSL contracts for declarative policy rules,
conditions, actions, scopes, bundles, versioning, conflict detection, and
compilation/evaluation trace records.
Governance scope: governance plane contract typing only.
Dependencies: shared contract base helpers, autonomy contracts.
Invariants:
  - Governance rules are declarative — compiled, not interpreted ad-hoc.
  - Every policy evaluation produces an auditable trace.
  - Conflicts between rules are detected at compile time, not runtime.
  - Scopes bind rules to deployment/function/job/team boundaries.
  - Bundles version governance state for rollback and audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PolicyEffect(StrEnum):
    """What a governance rule does when it matches."""

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_REVIEW = "require_review"
    REPLAN = "replan"


class PolicyConditionOperator(StrEnum):
    """Operators for governance condition evaluation."""

    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    IN = "in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    MATCHES = "matches"


class PolicyScopeKind(StrEnum):
    """Boundary types that governance rules can be scoped to."""

    GLOBAL = "global"
    DEPLOYMENT = "deployment"
    TEAM = "team"
    FUNCTION = "function"
    JOB = "job"
    WORKFLOW = "workflow"
    PROVIDER = "provider"
    CAPABILITY = "capability"


class PolicyActionKind(StrEnum):
    """What a governance rule instructs the runtime to do."""

    SET_AUTONOMY = "set_autonomy"
    SET_APPROVAL_REQUIRED = "set_approval_required"
    SET_REVIEW_REQUIRED = "set_review_required"
    ALLOW_PROVIDER = "allow_provider"
    DENY_PROVIDER = "deny_provider"
    ALLOW_REACTION = "allow_reaction"
    DENY_REACTION = "deny_reaction"
    SET_RETENTION = "set_retention"
    SET_EXPORT_RULE = "set_export_rule"
    SET_SIMULATION_THRESHOLD = "set_simulation_threshold"
    SET_UTILITY_THRESHOLD = "set_utility_threshold"
    SET_META_THRESHOLD = "set_meta_threshold"
    SET_ESCALATION_THRESHOLD = "set_escalation_threshold"
    EMIT_EVENT = "emit_event"
    CUSTOM = "custom"


class PolicyConflictKind(StrEnum):
    """Classification of conflicts between governance rules."""

    CONTRADICTORY_EFFECTS = "contradictory_effects"
    OVERLAPPING_SCOPES = "overlapping_scopes"
    PRIORITY_TIE = "priority_tie"
    CIRCULAR_DEPENDENCY = "circular_dependency"


class PolicyConflictSeverity(StrEnum):
    """How severe a governance conflict is."""

    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class CompilationStatus(StrEnum):
    """Outcome of compiling a governance bundle."""

    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Conditions and targets
# ---------------------------------------------------------------------------


_VALID_CONDITION_OPERATORS = frozenset(op.value for op in PolicyConditionOperator)


@dataclass(frozen=True, slots=True)
class PolicyCondition(ContractRecord):
    """A single predicate in a governance rule.

    field_path is a dot-separated path into the evaluation context
    (e.g. 'subject.role', 'action.class', 'provider.id').
    """

    field_path: str
    operator: str
    expected_value: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_path", require_non_empty_text(self.field_path, "field_path"))
        object.__setattr__(self, "operator", require_non_empty_text(self.operator, "operator"))
        if self.operator not in _VALID_CONDITION_OPERATORS:
            raise ValueError(
                "operator has unsupported value"
            )
        object.__setattr__(self, "expected_value", freeze_value(self.expected_value))


@dataclass(frozen=True, slots=True)
class PolicyScope(ContractRecord):
    """Binds a governance rule to a specific boundary."""

    scope_id: str
    kind: PolicyScopeKind
    ref_id: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope_id", require_non_empty_text(self.scope_id, "scope_id"))
        if not isinstance(self.kind, PolicyScopeKind):
            raise ValueError("kind must be a PolicyScopeKind value")
        if self.kind != PolicyScopeKind.GLOBAL and self.ref_id is None:
            raise ValueError("ref_id is required for non-GLOBAL scopes")
        if self.ref_id is not None:
            object.__setattr__(self, "ref_id", require_non_empty_text(self.ref_id, "ref_id"))


@dataclass(frozen=True, slots=True)
class PolicyAction(ContractRecord):
    """What a governance rule instructs the runtime to do when it fires."""

    action_id: str
    kind: PolicyActionKind
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        if not isinstance(self.kind, PolicyActionKind):
            raise ValueError("kind must be a PolicyActionKind value")
        object.__setattr__(self, "parameters", freeze_value(self.parameters))


# ---------------------------------------------------------------------------
# Policy rule — the core governance DSL primitive
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicyRule(ContractRecord):
    """A single declarative governance rule.

    Binds: conditions → effect + actions, scoped to a boundary.
    Rules are compiled into bundles and evaluated deterministically.
    """

    rule_id: str
    name: str
    description: str
    effect: PolicyEffect
    conditions: tuple[PolicyCondition, ...]
    actions: tuple[PolicyAction, ...]
    scope: PolicyScope
    priority: int = 0
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.effect, PolicyEffect):
            raise ValueError("effect must be a PolicyEffect value")
        object.__setattr__(self, "conditions", freeze_value(list(self.conditions)))
        for c in self.conditions:
            if not isinstance(c, PolicyCondition):
                raise ValueError("each condition must be a PolicyCondition instance")
        object.__setattr__(self, "actions", freeze_value(list(self.actions)))
        for a in self.actions:
            if not isinstance(a, PolicyAction):
                raise ValueError("each action must be a PolicyAction instance")
        if not isinstance(self.scope, PolicyScope):
            raise ValueError("scope must be a PolicyScope instance")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Bundle + versioning
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicyVersion(ContractRecord):
    """Version metadata for a governance bundle."""

    version_id: str
    major: int
    minor: int
    patch: int
    created_at: str
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "version_id", require_non_empty_text(self.version_id, "version_id"))
        object.__setattr__(self, "major", require_non_negative_int(self.major, "major"))
        object.__setattr__(self, "minor", require_non_negative_int(self.minor, "minor"))
        object.__setattr__(self, "patch", require_non_negative_int(self.patch, "patch"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))

    @property
    def semver(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True, slots=True)
class PolicyBundle(ContractRecord):
    """A versioned collection of governance rules that forms a deployable governance unit."""

    bundle_id: str
    name: str
    version: PolicyVersion
    rules: tuple[PolicyRule, ...]
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.version, PolicyVersion):
            raise ValueError("version must be a PolicyVersion instance")
        object.__setattr__(self, "rules", freeze_value(list(self.rules)))
        for r in self.rules:
            if not isinstance(r, PolicyRule):
                raise ValueError("each rule must be a PolicyRule instance")
        # Validate unique rule IDs within bundle
        rule_ids = [r.rule_id for r in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule_id values must be unique within a bundle")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    @property
    def enabled_rules(self) -> tuple[PolicyRule, ...]:
        return tuple(r for r in self.rules if r.enabled)

    @property
    def rule_count(self) -> int:
        return len(self.rules)


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicyConflict(ContractRecord):
    """A detected conflict between two or more governance rules."""

    conflict_id: str
    kind: PolicyConflictKind
    severity: PolicyConflictSeverity
    rule_ids: tuple[str, ...]
    description: str
    detected_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_id", require_non_empty_text(self.conflict_id, "conflict_id"))
        if not isinstance(self.kind, PolicyConflictKind):
            raise ValueError("kind must be a PolicyConflictKind value")
        if not isinstance(self.severity, PolicyConflictSeverity):
            raise ValueError("severity must be a PolicyConflictSeverity value")
        object.__setattr__(self, "rule_ids", require_non_empty_tuple(self.rule_ids, "rule_ids"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "detected_at", require_datetime_text(self.detected_at, "detected_at"))

    @property
    def is_fatal(self) -> bool:
        return self.severity is PolicyConflictSeverity.FATAL


# ---------------------------------------------------------------------------
# Compilation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicyCompilationResult(ContractRecord):
    """Outcome of compiling a governance bundle — includes conflict analysis."""

    compilation_id: str
    bundle_id: str
    status: CompilationStatus
    conflicts: tuple[PolicyConflict, ...]
    warnings: tuple[str, ...]
    compiled_at: str
    rule_count: int = 0
    enabled_rule_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "compilation_id", require_non_empty_text(self.compilation_id, "compilation_id"))
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        if not isinstance(self.status, CompilationStatus):
            raise ValueError("status must be a CompilationStatus value")
        object.__setattr__(self, "conflicts", freeze_value(list(self.conflicts)))
        for c in self.conflicts:
            if not isinstance(c, PolicyConflict):
                raise ValueError("each conflict must be a PolicyConflict instance")
        object.__setattr__(self, "warnings", freeze_value(list(self.warnings)))
        object.__setattr__(self, "compiled_at", require_datetime_text(self.compiled_at, "compiled_at"))
        object.__setattr__(self, "rule_count", require_non_negative_int(self.rule_count, "rule_count"))
        object.__setattr__(self, "enabled_rule_count", require_non_negative_int(self.enabled_rule_count, "enabled_rule_count"))

    @property
    def succeeded(self) -> bool:
        return self.status in (CompilationStatus.SUCCESS, CompilationStatus.SUCCESS_WITH_WARNINGS)

    @property
    def has_fatal_conflicts(self) -> bool:
        return any(c.is_fatal for c in self.conflicts)


# ---------------------------------------------------------------------------
# Evaluation trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicyEvaluationTrace(ContractRecord):
    """Auditable trace of evaluating governance rules against a request context.

    Records which rules matched, which fired, what effect was produced,
    and the final decision.
    """

    trace_id: str
    bundle_id: str
    subject_id: str
    context_snapshot: Mapping[str, Any]
    rules_evaluated: int
    rules_matched: int
    rules_fired: int
    matched_rule_ids: tuple[str, ...]
    fired_rule_ids: tuple[str, ...]
    final_effect: PolicyEffect
    actions_produced: tuple[PolicyAction, ...]
    evaluated_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "subject_id", require_non_empty_text(self.subject_id, "subject_id"))
        object.__setattr__(self, "context_snapshot", freeze_value(self.context_snapshot))
        object.__setattr__(self, "rules_evaluated", require_non_negative_int(self.rules_evaluated, "rules_evaluated"))
        object.__setattr__(self, "rules_matched", require_non_negative_int(self.rules_matched, "rules_matched"))
        object.__setattr__(self, "rules_fired", require_non_negative_int(self.rules_fired, "rules_fired"))
        object.__setattr__(self, "matched_rule_ids", freeze_value(list(self.matched_rule_ids)))
        object.__setattr__(self, "fired_rule_ids", freeze_value(list(self.fired_rule_ids)))
        if not isinstance(self.final_effect, PolicyEffect):
            raise ValueError("final_effect must be a PolicyEffect value")
        # fired_rule_ids must be a subset of matched_rule_ids
        if set(self.fired_rule_ids) - set(self.matched_rule_ids):
            raise ValueError("fired_rule_ids must be a subset of matched_rule_ids")
        object.__setattr__(self, "actions_produced", freeze_value(list(self.actions_produced)))
        for a in self.actions_produced:
            if not isinstance(a, PolicyAction):
                raise ValueError("each actions_produced element must be a PolicyAction instance")
        object.__setattr__(self, "evaluated_at", require_datetime_text(self.evaluated_at, "evaluated_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
