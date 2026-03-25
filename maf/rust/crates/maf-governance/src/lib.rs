//! Canonical governance DSL contracts for declarative policy rules,
//! conditions, actions, scopes, bundles, versioning, conflict detection,
//! and compilation/evaluation trace records.
//!
//! Mirrors `mcoi_runtime/contracts/governance.py` with full type parity.
//!
//! Invariants:
//! - Governance rules are declarative — compiled, not interpreted ad-hoc.
//! - Every policy evaluation produces an auditable trace.
//! - Conflicts between rules are detected at compile time, not runtime.
//! - Scopes bind rules to deployment/function/job/team boundaries.
//! - Bundles version governance state for rollback and audit.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ===========================================================================
// Enums
// ===========================================================================

/// What a governance rule does when it matches.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum PolicyEffect {
    Allow,
    Deny,
    Escalate,
    RequireApproval,
    RequireReview,
    Replan,
}

/// Operators for governance condition evaluation.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum PolicyConditionOperator {
    Eq,
    Neq,
    Gt,
    Gte,
    Lt,
    Lte,
    Contains,
    In,
    Exists,
    NotExists,
    Matches,
}

/// Boundary types that governance rules can be scoped to.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum PolicyScopeKind {
    Global,
    Deployment,
    Team,
    Function,
    Job,
    Workflow,
    Provider,
    Capability,
}

/// What a governance rule instructs the runtime to do.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum PolicyActionKind {
    SetAutonomy,
    SetApprovalRequired,
    SetReviewRequired,
    AllowProvider,
    DenyProvider,
    AllowReaction,
    DenyReaction,
    SetRetention,
    SetExportRule,
    SetSimulationThreshold,
    SetUtilityThreshold,
    SetMetaThreshold,
    SetEscalationThreshold,
    EmitEvent,
    Custom,
}

/// Classification of conflicts between governance rules.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum PolicyConflictKind {
    ContradictoryEffects,
    OverlappingScopes,
    PriorityTie,
    CircularDependency,
}

/// How severe a governance conflict is.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum PolicyConflictSeverity {
    Warning,
    Error,
    Fatal,
}

/// Outcome of compiling a governance bundle.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum CompilationStatus {
    Success,
    SuccessWithWarnings,
    Failed,
}

// ===========================================================================
// Condition and scope types
// ===========================================================================

/// A single predicate in a governance rule.
///
/// `field_path` is a dot-separated path into the evaluation context
/// (e.g. "subject.role", "action.class", "provider.id").
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PolicyCondition {
    pub field_path: String,
    pub operator: PolicyConditionOperator,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expected_value: Option<serde_json::Value>,
}

/// Binds a governance rule to a specific boundary.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct PolicyScope {
    pub scope_id: String,
    pub kind: PolicyScopeKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ref_id: Option<String>,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub description: String,
}

/// What a governance rule instructs the runtime to do when it fires.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PolicyAction {
    pub action_id: String,
    pub kind: PolicyActionKind,
    #[serde(default)]
    pub parameters: HashMap<String, serde_json::Value>,
}

// ===========================================================================
// Policy rule — the core governance DSL primitive
// ===========================================================================

/// A single declarative governance rule.
///
/// Binds: conditions -> effect + actions, scoped to a boundary.
/// Rules are compiled into bundles and evaluated deterministically.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PolicyRule {
    pub rule_id: String,
    pub name: String,
    pub description: String,
    pub effect: PolicyEffect,
    pub conditions: Vec<PolicyCondition>,
    pub actions: Vec<PolicyAction>,
    pub scope: PolicyScope,
    #[serde(default)]
    pub priority: i64,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

fn default_true() -> bool {
    true
}

// ===========================================================================
// Bundle + versioning
// ===========================================================================

/// Version metadata for a governance bundle.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct PolicyVersion {
    pub version_id: String,
    pub major: u32,
    pub minor: u32,
    pub patch: u32,
    pub created_at: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub description: String,
}

impl PolicyVersion {
    pub fn semver(&self) -> String {
        format!("{}.{}.{}", self.major, self.minor, self.patch)
    }
}

/// A versioned collection of governance rules forming a deployable governance unit.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PolicyBundle {
    pub bundle_id: String,
    pub name: String,
    pub version: PolicyVersion,
    pub rules: Vec<PolicyRule>,
    pub created_at: String,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

impl PolicyBundle {
    pub fn enabled_rules(&self) -> Vec<&PolicyRule> {
        self.rules.iter().filter(|r| r.enabled).collect()
    }

    pub fn rule_count(&self) -> usize {
        self.rules.len()
    }
}

// ===========================================================================
// Conflict detection
// ===========================================================================

/// A detected conflict between two or more governance rules.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct PolicyConflict {
    pub conflict_id: String,
    pub kind: PolicyConflictKind,
    pub severity: PolicyConflictSeverity,
    pub rule_ids: Vec<String>,
    pub description: String,
    pub detected_at: String,
}

impl PolicyConflict {
    pub fn is_fatal(&self) -> bool {
        self.severity == PolicyConflictSeverity::Fatal
    }
}

// ===========================================================================
// Compilation result
// ===========================================================================

/// Outcome of compiling a governance bundle — includes conflict analysis.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PolicyCompilationResult {
    pub compilation_id: String,
    pub bundle_id: String,
    pub status: CompilationStatus,
    pub conflicts: Vec<PolicyConflict>,
    #[serde(default)]
    pub warnings: Vec<String>,
    pub compiled_at: String,
    #[serde(default)]
    pub rule_count: u64,
    #[serde(default)]
    pub enabled_rule_count: u64,
}

impl PolicyCompilationResult {
    pub fn succeeded(&self) -> bool {
        matches!(
            self.status,
            CompilationStatus::Success | CompilationStatus::SuccessWithWarnings
        )
    }

    pub fn has_fatal_conflicts(&self) -> bool {
        self.conflicts.iter().any(|c| c.is_fatal())
    }
}

// ===========================================================================
// Evaluation trace
// ===========================================================================

/// Auditable trace of evaluating governance rules against a request context.
///
/// Records which rules matched, which fired, what effect was produced,
/// and the final decision.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PolicyEvaluationTrace {
    pub trace_id: String,
    pub bundle_id: String,
    pub subject_id: String,
    pub context_snapshot: HashMap<String, serde_json::Value>,
    pub rules_evaluated: u64,
    pub rules_matched: u64,
    pub rules_fired: u64,
    pub matched_rule_ids: Vec<String>,
    pub fired_rule_ids: Vec<String>,
    pub final_effect: PolicyEffect,
    pub actions_produced: Vec<PolicyAction>,
    pub evaluated_at: String,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn policy_effect_serializes_to_snake_case() {
        let json = serde_json::to_string(&PolicyEffect::RequireApproval).unwrap();
        assert_eq!(json, r#""require_approval""#);

        let json = serde_json::to_string(&PolicyEffect::Deny).unwrap();
        assert_eq!(json, r#""deny""#);
    }

    #[test]
    fn policy_condition_operator_serializes_to_snake_case() {
        let json = serde_json::to_string(&PolicyConditionOperator::NotExists).unwrap();
        assert_eq!(json, r#""not_exists""#);
    }

    #[test]
    fn policy_scope_kind_serializes_to_snake_case() {
        let json = serde_json::to_string(&PolicyScopeKind::Capability).unwrap();
        assert_eq!(json, r#""capability""#);
    }

    #[test]
    fn policy_action_kind_serializes_to_snake_case() {
        let json = serde_json::to_string(&PolicyActionKind::SetSimulationThreshold).unwrap();
        assert_eq!(json, r#""set_simulation_threshold""#);
    }

    #[test]
    fn compilation_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&CompilationStatus::SuccessWithWarnings).unwrap();
        assert_eq!(json, r#""success_with_warnings""#);
    }

    #[test]
    fn policy_version_semver() {
        let v = PolicyVersion {
            version_id: "v1".to_string(),
            major: 2,
            minor: 3,
            patch: 1,
            created_at: "2025-01-01T00:00:00+00:00".to_string(),
            description: String::new(),
        };
        assert_eq!(v.semver(), "2.3.1");
    }

    #[test]
    fn policy_condition_round_trips() {
        let cond = PolicyCondition {
            field_path: "subject.role".to_string(),
            operator: PolicyConditionOperator::Eq,
            expected_value: Some(serde_json::json!("admin")),
        };
        let json = serde_json::to_string(&cond).unwrap();
        let back: PolicyCondition = serde_json::from_str(&json).unwrap();
        assert_eq!(cond, back);
    }

    #[test]
    fn policy_rule_round_trips() {
        let rule = PolicyRule {
            rule_id: "r-1".to_string(),
            name: "Test rule".to_string(),
            description: "A test governance rule".to_string(),
            effect: PolicyEffect::Allow,
            conditions: vec![PolicyCondition {
                field_path: "action.class".to_string(),
                operator: PolicyConditionOperator::Eq,
                expected_value: Some(serde_json::json!("read")),
            }],
            actions: vec![PolicyAction {
                action_id: "a-1".to_string(),
                kind: PolicyActionKind::SetAutonomy,
                parameters: HashMap::new(),
            }],
            scope: PolicyScope {
                scope_id: "s-1".to_string(),
                kind: PolicyScopeKind::Global,
                ref_id: None,
                description: String::new(),
            },
            priority: 10,
            enabled: true,
            metadata: HashMap::new(),
        };
        let json = serde_json::to_string(&rule).unwrap();
        let back: PolicyRule = serde_json::from_str(&json).unwrap();
        assert_eq!(rule, back);
    }

    #[test]
    fn policy_bundle_round_trips() {
        let bundle = PolicyBundle {
            bundle_id: "b-1".to_string(),
            name: "Test bundle".to_string(),
            version: PolicyVersion {
                version_id: "v-1".to_string(),
                major: 1,
                minor: 0,
                patch: 0,
                created_at: "2025-01-01T00:00:00+00:00".to_string(),
                description: String::new(),
            },
            rules: vec![],
            created_at: "2025-01-01T00:00:00+00:00".to_string(),
            metadata: HashMap::new(),
        };
        let json = serde_json::to_string(&bundle).unwrap();
        let back: PolicyBundle = serde_json::from_str(&json).unwrap();
        assert_eq!(bundle, back);
    }

    #[test]
    fn policy_conflict_fatal_check() {
        let conflict = PolicyConflict {
            conflict_id: "c-1".to_string(),
            kind: PolicyConflictKind::ContradictoryEffects,
            severity: PolicyConflictSeverity::Fatal,
            rule_ids: vec!["r1".to_string(), "r2".to_string()],
            description: "rules contradict".to_string(),
            detected_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        assert!(conflict.is_fatal());

        let warning = PolicyConflict {
            severity: PolicyConflictSeverity::Warning,
            ..conflict
        };
        assert!(!warning.is_fatal());
    }

    #[test]
    fn compilation_result_round_trips() {
        let result = PolicyCompilationResult {
            compilation_id: "comp-1".to_string(),
            bundle_id: "b-1".to_string(),
            status: CompilationStatus::Success,
            conflicts: vec![],
            warnings: vec![],
            compiled_at: "2025-01-01T00:00:00+00:00".to_string(),
            rule_count: 5,
            enabled_rule_count: 4,
        };
        assert!(result.succeeded());
        assert!(!result.has_fatal_conflicts());

        let json = serde_json::to_string(&result).unwrap();
        let back: PolicyCompilationResult = serde_json::from_str(&json).unwrap();
        assert_eq!(result, back);
    }

    #[test]
    fn evaluation_trace_round_trips() {
        let trace = PolicyEvaluationTrace {
            trace_id: "t-1".to_string(),
            bundle_id: "b-1".to_string(),
            subject_id: "subj-1".to_string(),
            context_snapshot: HashMap::new(),
            rules_evaluated: 10,
            rules_matched: 3,
            rules_fired: 2,
            matched_rule_ids: vec!["r1".to_string(), "r2".to_string(), "r3".to_string()],
            fired_rule_ids: vec!["r1".to_string(), "r2".to_string()],
            final_effect: PolicyEffect::Allow,
            actions_produced: vec![],
            evaluated_at: "2025-01-01T00:00:00+00:00".to_string(),
            metadata: HashMap::new(),
        };
        let json = serde_json::to_string(&trace).unwrap();
        let back: PolicyEvaluationTrace = serde_json::from_str(&json).unwrap();
        assert_eq!(trace, back);
    }

    // --- Cross-format compatibility ---

    #[test]
    fn policy_effect_deserializes_from_python_format() {
        let pe: PolicyEffect = serde_json::from_str(r#""require_approval""#).unwrap();
        assert_eq!(pe, PolicyEffect::RequireApproval);
    }

    #[test]
    fn compilation_status_deserializes_from_python_format() {
        let cs: CompilationStatus = serde_json::from_str(r#""success_with_warnings""#).unwrap();
        assert_eq!(cs, CompilationStatus::SuccessWithWarnings);
    }
}
