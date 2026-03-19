#![forbid(unsafe_code)]
//! MAF Core kernel types — cross-domain abstractions matching shared contracts.
//!
//! Purpose: define generic types for policy, trace, replay, verification, and execution
//! that are not specific to any single vertical (MCOI, MCCI, MXI, etc.).
//!
//! Governance: MAF generalizes what verticals prove. These types map to `schemas/`.
//! Invariants: types are serialization-stable and match docs/15_deterministic_serialization_policy.md.

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Policy
// ---------------------------------------------------------------------------

/// Policy gate outcome. Maps to schemas/policy_decision.schema.json.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PolicyStatus {
    Allow,
    Deny,
    Escalate,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyReason {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyDecision {
    pub decision_id: String,
    pub subject_id: String,
    pub goal_id: String,
    pub status: PolicyStatus,
    pub reasons: Vec<PolicyReason>,
    pub issued_at: String,
}

// ---------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------

/// Execution outcome. Maps to schemas/execution_result.schema.json.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionOutcome {
    Succeeded,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EffectRecord {
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub execution_id: String,
    pub goal_id: String,
    pub status: ExecutionOutcome,
    pub actual_effects: Vec<EffectRecord>,
    pub assumed_effects: Vec<EffectRecord>,
    pub started_at: String,
    pub finished_at: String,
}

// ---------------------------------------------------------------------------
// Verification
// ---------------------------------------------------------------------------

/// Verification closure status. Maps to schemas/verification_result.schema.json.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VerificationStatus {
    Pass,
    Fail,
    Inconclusive,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VerificationCheck {
    pub name: String,
    pub status: VerificationStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct VerificationResult {
    pub verification_id: String,
    pub execution_id: String,
    pub status: VerificationStatus,
    pub checks: Vec<VerificationCheck>,
    pub closed_at: String,
}

// ---------------------------------------------------------------------------
// Trace
// ---------------------------------------------------------------------------

/// Trace entry. Maps to schemas/trace_entry.schema.json.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TraceEntry {
    pub trace_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent_trace_id: Option<String>,
    pub event_type: String,
    pub subject_id: String,
    pub goal_id: String,
    pub state_hash: String,
    pub registry_hash: String,
    pub timestamp: String,
}

// ---------------------------------------------------------------------------
// Replay
// ---------------------------------------------------------------------------

/// Replay mode. Maps to schemas/replay_record.schema.json.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReplayMode {
    ObservationOnly,
    EffectBearing,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReplayRecord {
    pub replay_id: String,
    pub trace_id: String,
    pub source_hash: String,
    pub mode: ReplayMode,
    pub recorded_at: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub state_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub environment_digest: Option<String>,
}

// ---------------------------------------------------------------------------
// Error taxonomy
// ---------------------------------------------------------------------------

/// Error family. Maps to docs/08_error_taxonomy.md.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ErrorFamily {
    ValidationError,
    ObservationError,
    AdmissibilityError,
    PolicyError,
    ExecutionError,
    VerificationError,
    ReplayError,
    PersistenceError,
    IntegrationError,
    CapabilityError,
    ConfigurationError,
}

/// Recoverability class. Maps to docs/08_error_taxonomy.md.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Recoverability {
    Retryable,
    ReobserveRequired,
    ReplanRequired,
    ApprovalRequired,
    FatalForRun,
    Unsupported,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn policy_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&PolicyStatus::Allow).unwrap();
        assert_eq!(json, r#""allow""#);
        let json = serde_json::to_string(&PolicyStatus::Deny).unwrap();
        assert_eq!(json, r#""deny""#);
        let json = serde_json::to_string(&PolicyStatus::Escalate).unwrap();
        assert_eq!(json, r#""escalate""#);
    }

    #[test]
    fn execution_outcome_serializes_to_snake_case() {
        let json = serde_json::to_string(&ExecutionOutcome::Succeeded).unwrap();
        assert_eq!(json, r#""succeeded""#);
    }

    #[test]
    fn verification_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&VerificationStatus::Pass).unwrap();
        assert_eq!(json, r#""pass""#);
    }

    #[test]
    fn replay_mode_serializes_to_snake_case() {
        let json = serde_json::to_string(&ReplayMode::ObservationOnly).unwrap();
        assert_eq!(json, r#""observation_only""#);
    }

    #[test]
    fn trace_entry_round_trips() {
        let entry = TraceEntry {
            trace_id: "trace-1".into(),
            parent_trace_id: Some("trace-0".into()),
            event_type: "test".into(),
            subject_id: "s-1".into(),
            goal_id: "g-1".into(),
            state_hash: "h-1".into(),
            registry_hash: "r-1".into(),
            timestamp: "2026-03-19T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&entry).unwrap();
        let restored: TraceEntry = serde_json::from_str(&json).unwrap();
        assert_eq!(entry, restored);
    }

    #[test]
    fn policy_decision_round_trips() {
        let decision = PolicyDecision {
            decision_id: "d-1".into(),
            subject_id: "s-1".into(),
            goal_id: "g-1".into(),
            status: PolicyStatus::Allow,
            reasons: vec![PolicyReason {
                code: "ok".into(),
                message: "all good".into(),
            }],
            issued_at: "2026-03-19T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&decision).unwrap();
        let restored: PolicyDecision = serde_json::from_str(&json).unwrap();
        assert_eq!(decision, restored);
    }
}
