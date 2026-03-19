#![forbid(unsafe_code)]
//! MAF Core agent types — cross-domain abstractions for observation, world-state,
//! temporal, coordination, communication, and meta-reasoning.
//!
//! Purpose: define generic types that verticals specialize but do not redefine.
//! These complement maf-kernel (execution/policy/trace/replay) and
//! maf-capability (capability classification).
//!
//! Governance: MAF generalizes what verticals prove. No shell/filesystem/process specifics.

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Observation (Perception Plane)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ObservationStatus {
    Succeeded,
    Failed,
    Unsupported,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ObservationResult {
    pub observer_id: String,
    pub status: ObservationStatus,
    pub evidence_count: u32,
    pub timestamp: String,
}

// ---------------------------------------------------------------------------
// World State
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StateEntity {
    pub entity_id: String,
    pub entity_type: String,
    pub confidence: f64,
    pub evidence_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntityRelation {
    pub relation_id: String,
    pub source_entity_id: String,
    pub target_entity_id: String,
    pub relation_type: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContradictionStrategy {
    PreferLatest,
    PreferHighestConfidence,
    Escalate,
    Manual,
}

// ---------------------------------------------------------------------------
// Temporal
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TemporalState {
    Pending,
    Waiting,
    Due,
    Running,
    Completed,
    Expired,
    Cancelled,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TriggerType {
    AtTime,
    AfterDelay,
    OnEvent,
    Recurring,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TemporalTask {
    pub task_id: String,
    pub goal_id: String,
    pub state: TemporalState,
    pub trigger_type: TriggerType,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub deadline: Option<String>,
}

// ---------------------------------------------------------------------------
// Coordination
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DelegationStatus {
    Accepted,
    Rejected,
    Expired,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MergeOutcome {
    Merged,
    ConflictDetected,
    Deferred,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConflictResolutionStrategy {
    PreferLatest,
    PreferHighestConfidence,
    Escalate,
    Manual,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DelegationRequest {
    pub delegation_id: String,
    pub delegator_id: String,
    pub delegate_id: String,
    pub goal_id: String,
    pub action_scope: String,
}

// ---------------------------------------------------------------------------
// Communication
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CommunicationChannel {
    Approval,
    Escalation,
    Notification,
    Explanation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DeliveryStatus {
    Delivered,
    Failed,
    Pending,
}

// ---------------------------------------------------------------------------
// Meta-Reasoning
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unavailable,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EscalationSeverity {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum UncertaintySource {
    MissingEvidence,
    LowConfidence,
    ContradictedState,
    IncompleteObservation,
    UnverifiedAssumption,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CapabilityConfidence {
    pub capability_id: String,
    pub success_rate: f64,
    pub verification_pass_rate: f64,
    pub timeout_rate: f64,
    pub error_rate: f64,
    pub sample_count: u32,
    pub assessed_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SubsystemHealth {
    pub subsystem: String,
    pub status: HealthStatus,
    pub details: String,
}

// ---------------------------------------------------------------------------
// Integration
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectorStatus {
    Succeeded,
    Failed,
    Timeout,
}

// ---------------------------------------------------------------------------
// Model Orchestration
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelStatus {
    Succeeded,
    Failed,
    Timeout,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ValidationStatus {
    Passed,
    Failed,
    Pending,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn temporal_state_serializes() {
        assert_eq!(serde_json::to_string(&TemporalState::Pending).unwrap(), r#""pending""#);
        assert_eq!(serde_json::to_string(&TemporalState::Expired).unwrap(), r#""expired""#);
    }

    #[test]
    fn delegation_status_serializes() {
        assert_eq!(serde_json::to_string(&DelegationStatus::Accepted).unwrap(), r#""accepted""#);
    }

    #[test]
    fn communication_channel_serializes() {
        assert_eq!(serde_json::to_string(&CommunicationChannel::Approval).unwrap(), r#""approval""#);
        assert_eq!(serde_json::to_string(&CommunicationChannel::Escalation).unwrap(), r#""escalation""#);
    }

    #[test]
    fn health_status_serializes() {
        assert_eq!(serde_json::to_string(&HealthStatus::Degraded).unwrap(), r#""degraded""#);
    }

    #[test]
    fn uncertainty_source_serializes() {
        assert_eq!(
            serde_json::to_string(&UncertaintySource::ContradictedState).unwrap(),
            r#""contradicted_state""#
        );
    }

    #[test]
    fn capability_confidence_round_trips() {
        let conf = CapabilityConfidence {
            capability_id: "shell".into(),
            success_rate: 0.95,
            verification_pass_rate: 0.9,
            timeout_rate: 0.02,
            error_rate: 0.03,
            sample_count: 100,
            assessed_at: "2026-03-19T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&conf).unwrap();
        let restored: CapabilityConfidence = serde_json::from_str(&json).unwrap();
        assert_eq!(conf, restored);
    }

    #[test]
    fn temporal_task_round_trips() {
        let task = TemporalTask {
            task_id: "t-1".into(),
            goal_id: "g-1".into(),
            state: TemporalState::Due,
            trigger_type: TriggerType::AtTime,
            deadline: Some("2027-01-01T00:00:00+00:00".into()),
        };
        let json = serde_json::to_string(&task).unwrap();
        let restored: TemporalTask = serde_json::from_str(&json).unwrap();
        assert_eq!(task, restored);
    }

    #[test]
    fn delegation_request_round_trips() {
        let req = DelegationRequest {
            delegation_id: "d-1".into(),
            delegator_id: "agent-a".into(),
            delegate_id: "agent-b".into(),
            goal_id: "g-1".into(),
            action_scope: "execute".into(),
        };
        let json = serde_json::to_string(&req).unwrap();
        let restored: DelegationRequest = serde_json::from_str(&json).unwrap();
        assert_eq!(req, restored);
    }

    #[test]
    fn connector_and_model_status_serializes() {
        assert_eq!(serde_json::to_string(&ConnectorStatus::Timeout).unwrap(), r#""timeout""#);
        assert_eq!(serde_json::to_string(&ModelStatus::Succeeded).unwrap(), r#""succeeded""#);
        assert_eq!(serde_json::to_string(&ValidationStatus::Pending).unwrap(), r#""pending""#);
    }
}
