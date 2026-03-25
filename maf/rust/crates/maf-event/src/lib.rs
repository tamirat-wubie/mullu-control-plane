//! Canonical event spine and obligation runtime contracts.
//!
//! Mirrors the Python MCOI contracts in `mcoi_runtime/contracts/event.py`
//! and `mcoi_runtime/contracts/obligation.py` with full type parity.
//!
//! Invariants:
//! - Events are append-only and immutable once emitted.
//! - Every event has a source, type, and correlation ID.
//! - Obligations have owners, deadlines, and explicit lifecycle states.
//! - Transfers preserve history; closures are never silent.
//! - All timestamps are ISO-8601 strings.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ===========================================================================
// Event enums
// ===========================================================================

/// Classification of events emitted into the spine.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    JobStateTransition,
    WorkflowStageTransition,
    ApprovalRequested,
    ApprovalDecided,
    ReviewRequested,
    ReviewDecided,
    IncidentOpened,
    IncidentEscalated,
    IncidentResolved,
    CommunicationSent,
    CommunicationReplied,
    CommunicationTimedOut,
    ObligationCreated,
    ObligationClosed,
    ObligationEscalated,
    ObligationTransferred,
    ObligationExpired,
    WorldStateChanged,
    ReactionExecuted,
    ReactionDeferred,
    ReactionRejected,
    SupervisorHeartbeat,
    SupervisorLivelock,
    SupervisorCheckpoint,
    SupervisorHalted,
    Custom,
}

/// Origin plane or subsystem that emitted the event.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum EventSource {
    JobRuntime,
    WorkflowRuntime,
    TeamRuntime,
    FunctionRuntime,
    ApprovalSystem,
    ReviewSystem,
    IncidentSystem,
    CommunicationSystem,
    ObligationRuntime,
    WorldStateEngine,
    SimulationEngine,
    ReactionEngine,
    Supervisor,
    Dashboard,
    External,
}

// ===========================================================================
// Event records
// ===========================================================================

/// A single typed event emitted into the spine. Immutable once created.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EventRecord {
    pub event_id: String,
    pub event_type: EventType,
    pub source: EventSource,
    pub correlation_id: String,
    pub payload: HashMap<String, serde_json::Value>,
    pub emitted_at: String,
}

/// Routing wrapper around an EventRecord with delivery metadata.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EventEnvelope {
    pub envelope_id: String,
    pub event: EventRecord,
    pub target_subsystems: Vec<String>,
    pub priority: u32,
    #[serde(default)]
    pub delivered: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub delivered_at: Option<String>,
}

/// A deterministic subscription binding an event type to a reaction.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct EventSubscription {
    pub subscription_id: String,
    pub event_type: EventType,
    pub subscriber_id: String,
    pub reaction_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub filter_source: Option<EventSource>,
    #[serde(default = "default_true")]
    pub active: bool,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub created_at: String,
}

fn default_true() -> bool {
    true
}

/// A reaction triggered by an event — records what was done and why.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct EventReaction {
    pub reaction_id: String,
    pub event_id: String,
    pub subscription_id: String,
    pub action_taken: String,
    pub result: String,
    pub reacted_at: String,
}

/// A bounded temporal window for event correlation.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct EventWindow {
    pub window_id: String,
    pub correlation_id: String,
    pub window_start: String,
    pub window_end: String,
    pub event_count: u64,
}

/// Links causally related events under a shared correlation ID.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct EventCorrelation {
    pub correlation_id: String,
    pub event_ids: Vec<String>,
    pub root_event_id: String,
    pub description: String,
    pub created_at: String,
}

// ===========================================================================
// Obligation enums
// ===========================================================================

/// Lifecycle state of an obligation.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum ObligationState {
    Pending,
    Active,
    Completed,
    Expired,
    Escalated,
    Transferred,
    Cancelled,
}

impl ObligationState {
    /// Terminal states from which no further transitions are allowed.
    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            ObligationState::Completed | ObligationState::Expired | ObligationState::Cancelled
        )
    }
}

/// What created this obligation.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum ObligationTrigger {
    ApprovalRequest,
    JobAssignment,
    ReviewRequest,
    CommunicationFollowUp,
    IncidentSla,
    EscalationAck,
    WorkflowStage,
    Custom,
}

// ===========================================================================
// Obligation records
// ===========================================================================

/// Identifies who owns an obligation.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq, Hash)]
pub struct ObligationOwner {
    pub owner_id: String,
    pub owner_type: String,
    pub display_name: String,
}

/// Deadline specification for an obligation.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct ObligationDeadline {
    pub deadline_id: String,
    pub due_at: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub warn_at: Option<String>,
    #[serde(default = "default_true")]
    pub hard: bool,
}

/// A first-class obligation owed by an owner, traceable to its trigger.
///
/// Obligations are never silently resolved — closure, transfer, escalation,
/// and expiry are all explicit typed operations.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ObligationRecord {
    pub obligation_id: String,
    pub trigger: ObligationTrigger,
    pub trigger_ref_id: String,
    pub state: ObligationState,
    pub owner: ObligationOwner,
    pub deadline: ObligationDeadline,
    pub description: String,
    pub correlation_id: String,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
    pub created_at: String,
    pub updated_at: String,
}

/// Explicit closure of an obligation — satisfied, cancelled, or expired.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct ObligationClosure {
    pub closure_id: String,
    pub obligation_id: String,
    pub final_state: ObligationState,
    pub reason: String,
    pub closed_by: String,
    pub closed_at: String,
}

/// Transfer of an obligation from one owner to another.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct ObligationTransfer {
    pub transfer_id: String,
    pub obligation_id: String,
    pub from_owner: ObligationOwner,
    pub to_owner: ObligationOwner,
    pub reason: String,
    pub transferred_at: String,
}

/// Escalation of an obligation — deadline breach or explicit escalation.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct ObligationEscalation {
    pub escalation_id: String,
    pub obligation_id: String,
    pub escalated_to: ObligationOwner,
    pub reason: String,
    pub severity: String,
    pub escalated_at: String,
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // --- Event enum serialization ---

    #[test]
    fn event_type_serializes_to_snake_case() {
        let json = serde_json::to_string(&EventType::JobStateTransition).unwrap();
        assert_eq!(json, r#""job_state_transition""#);

        let json = serde_json::to_string(&EventType::SupervisorHeartbeat).unwrap();
        assert_eq!(json, r#""supervisor_heartbeat""#);

        let json = serde_json::to_string(&EventType::ObligationCreated).unwrap();
        assert_eq!(json, r#""obligation_created""#);
    }

    #[test]
    fn event_source_serializes_to_snake_case() {
        let json = serde_json::to_string(&EventSource::ObligationRuntime).unwrap();
        assert_eq!(json, r#""obligation_runtime""#);

        let json = serde_json::to_string(&EventSource::Supervisor).unwrap();
        assert_eq!(json, r#""supervisor""#);
    }

    #[test]
    fn event_record_round_trips() {
        let mut payload = HashMap::new();
        payload.insert("key".to_string(), serde_json::json!("value"));

        let record = EventRecord {
            event_id: "evt-1".to_string(),
            event_type: EventType::Custom,
            source: EventSource::External,
            correlation_id: "corr-1".to_string(),
            payload,
            emitted_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&record).unwrap();
        let back: EventRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(record, back);
    }

    #[test]
    fn event_envelope_round_trips() {
        let record = EventRecord {
            event_id: "evt-2".to_string(),
            event_type: EventType::IncidentOpened,
            source: EventSource::IncidentSystem,
            correlation_id: "corr-2".to_string(),
            payload: HashMap::new(),
            emitted_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let envelope = EventEnvelope {
            envelope_id: "env-1".to_string(),
            event: record,
            target_subsystems: vec!["obligation_runtime".to_string()],
            priority: 5,
            delivered: false,
            delivered_at: None,
        };
        let json = serde_json::to_string(&envelope).unwrap();
        let back: EventEnvelope = serde_json::from_str(&json).unwrap();
        assert_eq!(envelope, back);
    }

    #[test]
    fn event_subscription_round_trips() {
        let sub = EventSubscription {
            subscription_id: "sub-1".to_string(),
            event_type: EventType::ApprovalRequested,
            subscriber_id: "worker-1".to_string(),
            reaction_id: "react-1".to_string(),
            filter_source: Some(EventSource::ApprovalSystem),
            active: true,
            created_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&sub).unwrap();
        let back: EventSubscription = serde_json::from_str(&json).unwrap();
        assert_eq!(sub, back);
    }

    #[test]
    fn event_reaction_round_trips() {
        let reaction = EventReaction {
            reaction_id: "r-1".to_string(),
            event_id: "evt-1".to_string(),
            subscription_id: "sub-1".to_string(),
            action_taken: "created_obligation".to_string(),
            result: "success".to_string(),
            reacted_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&reaction).unwrap();
        let back: EventReaction = serde_json::from_str(&json).unwrap();
        assert_eq!(reaction, back);
    }

    #[test]
    fn event_correlation_round_trips() {
        let corr = EventCorrelation {
            correlation_id: "corr-1".to_string(),
            event_ids: vec!["evt-1".to_string(), "evt-2".to_string()],
            root_event_id: "evt-1".to_string(),
            description: "test correlation".to_string(),
            created_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&corr).unwrap();
        let back: EventCorrelation = serde_json::from_str(&json).unwrap();
        assert_eq!(corr, back);
    }

    // --- Obligation enum serialization ---

    #[test]
    fn obligation_state_serializes_to_snake_case() {
        let json = serde_json::to_string(&ObligationState::Pending).unwrap();
        assert_eq!(json, r#""pending""#);

        let json = serde_json::to_string(&ObligationState::Escalated).unwrap();
        assert_eq!(json, r#""escalated""#);
    }

    #[test]
    fn obligation_state_terminal_check() {
        assert!(ObligationState::Completed.is_terminal());
        assert!(ObligationState::Expired.is_terminal());
        assert!(ObligationState::Cancelled.is_terminal());
        assert!(!ObligationState::Pending.is_terminal());
        assert!(!ObligationState::Active.is_terminal());
        assert!(!ObligationState::Escalated.is_terminal());
        assert!(!ObligationState::Transferred.is_terminal());
    }

    #[test]
    fn obligation_trigger_serializes_to_snake_case() {
        let json = serde_json::to_string(&ObligationTrigger::ApprovalRequest).unwrap();
        assert_eq!(json, r#""approval_request""#);

        let json = serde_json::to_string(&ObligationTrigger::IncidentSla).unwrap();
        assert_eq!(json, r#""incident_sla""#);
    }

    // --- Obligation record round trips ---

    #[test]
    fn obligation_owner_round_trips() {
        let owner = ObligationOwner {
            owner_id: "team-1".to_string(),
            owner_type: "team".to_string(),
            display_name: "Platform Team".to_string(),
        };
        let json = serde_json::to_string(&owner).unwrap();
        let back: ObligationOwner = serde_json::from_str(&json).unwrap();
        assert_eq!(owner, back);
    }

    #[test]
    fn obligation_deadline_round_trips() {
        let dl = ObligationDeadline {
            deadline_id: "dl-1".to_string(),
            due_at: "2026-01-01T00:00:00+00:00".to_string(),
            warn_at: Some("2025-12-31T00:00:00+00:00".to_string()),
            hard: true,
        };
        let json = serde_json::to_string(&dl).unwrap();
        let back: ObligationDeadline = serde_json::from_str(&json).unwrap();
        assert_eq!(dl, back);
    }

    #[test]
    fn obligation_deadline_optional_warn_at() {
        let dl = ObligationDeadline {
            deadline_id: "dl-2".to_string(),
            due_at: "2026-01-01T00:00:00+00:00".to_string(),
            warn_at: None,
            hard: false,
        };
        let json = serde_json::to_string(&dl).unwrap();
        assert!(!json.contains("warn_at"));
        let back: ObligationDeadline = serde_json::from_str(&json).unwrap();
        assert_eq!(dl, back);
    }

    #[test]
    fn obligation_record_round_trips() {
        let record = ObligationRecord {
            obligation_id: "obl-1".to_string(),
            trigger: ObligationTrigger::Custom,
            trigger_ref_id: "ref-1".to_string(),
            state: ObligationState::Pending,
            owner: ObligationOwner {
                owner_id: "team-1".to_string(),
                owner_type: "team".to_string(),
                display_name: "Test".to_string(),
            },
            deadline: ObligationDeadline {
                deadline_id: "dl-1".to_string(),
                due_at: "2026-01-01T00:00:00+00:00".to_string(),
                warn_at: None,
                hard: true,
            },
            description: "test obligation".to_string(),
            correlation_id: "corr-1".to_string(),
            metadata: HashMap::new(),
            created_at: "2025-01-01T00:00:00+00:00".to_string(),
            updated_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&record).unwrap();
        let back: ObligationRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(record, back);
    }

    #[test]
    fn obligation_closure_round_trips() {
        let closure = ObligationClosure {
            closure_id: "cls-1".to_string(),
            obligation_id: "obl-1".to_string(),
            final_state: ObligationState::Completed,
            reason: "done".to_string(),
            closed_by: "admin".to_string(),
            closed_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&closure).unwrap();
        let back: ObligationClosure = serde_json::from_str(&json).unwrap();
        assert_eq!(closure, back);
    }

    #[test]
    fn obligation_transfer_round_trips() {
        let xfr = ObligationTransfer {
            transfer_id: "xfr-1".to_string(),
            obligation_id: "obl-1".to_string(),
            from_owner: ObligationOwner {
                owner_id: "a".to_string(),
                owner_type: "team".to_string(),
                display_name: "Team A".to_string(),
            },
            to_owner: ObligationOwner {
                owner_id: "b".to_string(),
                owner_type: "team".to_string(),
                display_name: "Team B".to_string(),
            },
            reason: "reassign".to_string(),
            transferred_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&xfr).unwrap();
        let back: ObligationTransfer = serde_json::from_str(&json).unwrap();
        assert_eq!(xfr, back);
    }

    #[test]
    fn obligation_escalation_round_trips() {
        let esc = ObligationEscalation {
            escalation_id: "esc-1".to_string(),
            obligation_id: "obl-1".to_string(),
            escalated_to: ObligationOwner {
                owner_id: "mgr-1".to_string(),
                owner_type: "manager".to_string(),
                display_name: "Manager".to_string(),
            },
            reason: "deadline breach".to_string(),
            severity: "high".to_string(),
            escalated_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&esc).unwrap();
        let back: ObligationEscalation = serde_json::from_str(&json).unwrap();
        assert_eq!(esc, back);
    }

    // --- Cross-format compatibility ---

    #[test]
    fn event_type_deserializes_from_python_format() {
        // Python emits snake_case strings — verify Rust can consume them
        let et: EventType = serde_json::from_str(r#""supervisor_heartbeat""#).unwrap();
        assert_eq!(et, EventType::SupervisorHeartbeat);

        let et: EventType = serde_json::from_str(r#""obligation_created""#).unwrap();
        assert_eq!(et, EventType::ObligationCreated);
    }

    #[test]
    fn obligation_state_deserializes_from_python_format() {
        let os: ObligationState = serde_json::from_str(r#""escalated""#).unwrap();
        assert_eq!(os, ObligationState::Escalated);
    }
}
