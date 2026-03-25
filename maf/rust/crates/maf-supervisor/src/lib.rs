//! Canonical continuous supervisor runtime contracts.
//!
//! Mirrors `mcoi_runtime/contracts/supervisor.py` with full type parity.
//!
//! Invariants:
//! - The supervisor advances one deterministic tick at a time.
//! - Every tick produces an immutable record of what was evaluated and decided.
//! - Checkpoints are serializable for resume; no hidden state.
//! - Heartbeats are periodic health signals emitted into the event spine.
//! - Livelock detection is explicit — stall loops are surfaced, never silent.
//! - Governance is never bypassed; every action passes through policy evaluation.
//! - Backpressure and pacing are policy-driven, not hardcoded.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ===========================================================================
// Enums
// ===========================================================================

/// What the supervisor is currently doing within a tick.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum SupervisorPhase {
    Idle,
    Polling,
    EvaluatingObligations,
    EvaluatingDeadlines,
    WakingWork,
    RunningReactions,
    Reasoning,
    Acting,
    Checkpointing,
    EmittingHeartbeat,
    Paused,
    Degraded,
    Halted,
}

/// Summary outcome of a single supervisor tick.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum TickOutcome {
    Healthy,
    WorkDone,
    IdleTick,
    BackpressureApplied,
    LivelockDetected,
    GovernanceBlocked,
    Error,
    Halted,
}

/// How to respond when livelock is detected.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum LivelockStrategy {
    Escalate,
    Pause,
    Halt,
    SkipAndLog,
}

/// Status of a supervisor checkpoint.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum CheckpointStatus {
    Valid,
    Stale,
    Corrupted,
}

// ===========================================================================
// Policy contracts
// ===========================================================================

/// Configuration governing supervisor tick behavior.
///
/// Defines pacing, backpressure thresholds, livelock detection,
/// and heartbeat intervals. All values are bounded and validated.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct SupervisorPolicy {
    pub policy_id: String,
    pub tick_interval_ms: u64,
    pub max_events_per_tick: u64,
    pub max_actions_per_tick: u64,
    pub backpressure_threshold: u64,
    pub livelock_repeat_threshold: u64,
    pub livelock_strategy: LivelockStrategy,
    pub heartbeat_every_n_ticks: u64,
    pub checkpoint_every_n_ticks: u64,
    pub max_consecutive_errors: u64,
    pub created_at: String,
}

// ===========================================================================
// Tick records
// ===========================================================================

/// One action decided during a supervisor tick.
///
/// Records what was decided, why, and whether governance approved it.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SupervisorDecision {
    pub decision_id: String,
    pub action_type: String,
    pub target_id: String,
    pub reason: String,
    pub governance_approved: bool,
    pub decided_at: String,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Immutable record of one supervisor tick cycle.
///
/// Captures what was polled, evaluated, decided, and the resulting outcome.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SupervisorTick {
    pub tick_id: String,
    pub tick_number: u64,
    pub phase_sequence: Vec<SupervisorPhase>,
    pub events_polled: u64,
    pub obligations_evaluated: u64,
    pub deadlines_checked: u64,
    pub reactions_fired: u64,
    pub decisions: Vec<SupervisorDecision>,
    pub outcome: TickOutcome,
    #[serde(default)]
    pub errors: Vec<String>,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub started_at: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub completed_at: String,
    #[serde(default)]
    pub duration_ms: u64,
}

// ===========================================================================
// Health and heartbeat
// ===========================================================================

/// Health assessment of the supervisor at a point in time.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SupervisorHealth {
    pub health_id: String,
    pub tick_number: u64,
    pub phase: SupervisorPhase,
    pub consecutive_errors: u64,
    pub consecutive_idle_ticks: u64,
    pub backpressure_active: bool,
    pub livelock_detected: bool,
    pub open_obligations: u64,
    pub pending_events: u64,
    pub overall_confidence: f64,
    pub assessed_at: String,
}

/// Periodic health signal emitted into the event spine.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct RuntimeHeartbeat {
    pub heartbeat_id: String,
    pub tick_number: u64,
    pub phase: SupervisorPhase,
    pub outcome_of_last_tick: TickOutcome,
    pub open_obligations: u64,
    pub pending_events: u64,
    pub uptime_ticks: u64,
    pub emitted_at: String,
}

// ===========================================================================
// Checkpoint and livelock
// ===========================================================================

/// Serializable snapshot for supervisor resume.
///
/// Contains enough state to restart the supervisor from this point
/// without replaying the full event history.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct SupervisorCheckpoint {
    pub checkpoint_id: String,
    pub tick_number: u64,
    pub phase: SupervisorPhase,
    pub status: CheckpointStatus,
    pub open_obligation_ids: Vec<String>,
    pub pending_event_count: u64,
    pub consecutive_errors: u64,
    pub consecutive_idle_ticks: u64,
    pub recent_tick_outcomes: Vec<TickOutcome>,
    pub state_hash: String,
    pub created_at: String,
}

/// Explicit record of a detected stall/loop condition.
///
/// Livelock is surfaced, never silent. The record includes the
/// repeated pattern and the strategy applied to break it.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct LivelockRecord {
    pub livelock_id: String,
    pub tick_number: u64,
    pub repeated_pattern: String,
    pub repeat_count: u64,
    pub strategy_applied: LivelockStrategy,
    pub resolved: bool,
    pub detected_at: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub resolution_detail: String,
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn supervisor_phase_serializes_to_snake_case() {
        let json = serde_json::to_string(&SupervisorPhase::EvaluatingObligations).unwrap();
        assert_eq!(json, r#""evaluating_obligations""#);

        let json = serde_json::to_string(&SupervisorPhase::EmittingHeartbeat).unwrap();
        assert_eq!(json, r#""emitting_heartbeat""#);
    }

    #[test]
    fn tick_outcome_serializes_to_snake_case() {
        let json = serde_json::to_string(&TickOutcome::BackpressureApplied).unwrap();
        assert_eq!(json, r#""backpressure_applied""#);

        let json = serde_json::to_string(&TickOutcome::LivelockDetected).unwrap();
        assert_eq!(json, r#""livelock_detected""#);
    }

    #[test]
    fn livelock_strategy_serializes_to_snake_case() {
        let json = serde_json::to_string(&LivelockStrategy::SkipAndLog).unwrap();
        assert_eq!(json, r#""skip_and_log""#);
    }

    #[test]
    fn checkpoint_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&CheckpointStatus::Corrupted).unwrap();
        assert_eq!(json, r#""corrupted""#);
    }

    #[test]
    fn supervisor_policy_round_trips() {
        let policy = SupervisorPolicy {
            policy_id: "p-1".to_string(),
            tick_interval_ms: 100,
            max_events_per_tick: 10,
            max_actions_per_tick: 10,
            backpressure_threshold: 5,
            livelock_repeat_threshold: 3,
            livelock_strategy: LivelockStrategy::Escalate,
            heartbeat_every_n_ticks: 5,
            checkpoint_every_n_ticks: 10,
            max_consecutive_errors: 3,
            created_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&policy).unwrap();
        let back: SupervisorPolicy = serde_json::from_str(&json).unwrap();
        assert_eq!(policy, back);
    }

    #[test]
    fn supervisor_decision_round_trips() {
        let decision = SupervisorDecision {
            decision_id: "d-1".to_string(),
            action_type: "activate_obligation".to_string(),
            target_id: "obl-1".to_string(),
            reason: "pending obligation".to_string(),
            governance_approved: true,
            decided_at: "2025-01-01T00:00:00+00:00".to_string(),
            metadata: HashMap::new(),
        };
        let json = serde_json::to_string(&decision).unwrap();
        let back: SupervisorDecision = serde_json::from_str(&json).unwrap();
        assert_eq!(decision, back);
    }

    #[test]
    fn supervisor_tick_round_trips() {
        let tick = SupervisorTick {
            tick_id: "t-1".to_string(),
            tick_number: 42,
            phase_sequence: vec![
                SupervisorPhase::Polling,
                SupervisorPhase::EvaluatingObligations,
                SupervisorPhase::Idle,
            ],
            events_polled: 3,
            obligations_evaluated: 2,
            deadlines_checked: 1,
            reactions_fired: 0,
            decisions: vec![],
            outcome: TickOutcome::WorkDone,
            errors: vec![],
            started_at: "2025-01-01T00:00:00+00:00".to_string(),
            completed_at: "2025-01-01T00:00:01+00:00".to_string(),
            duration_ms: 15,
        };
        let json = serde_json::to_string(&tick).unwrap();
        let back: SupervisorTick = serde_json::from_str(&json).unwrap();
        assert_eq!(tick, back);
    }

    #[test]
    fn supervisor_health_round_trips() {
        let health = SupervisorHealth {
            health_id: "h-1".to_string(),
            tick_number: 100,
            phase: SupervisorPhase::Idle,
            consecutive_errors: 0,
            consecutive_idle_ticks: 2,
            backpressure_active: false,
            livelock_detected: false,
            open_obligations: 5,
            pending_events: 3,
            overall_confidence: 0.95,
            assessed_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&health).unwrap();
        let back: SupervisorHealth = serde_json::from_str(&json).unwrap();
        assert_eq!(health, back);
    }

    #[test]
    fn runtime_heartbeat_round_trips() {
        let hb = RuntimeHeartbeat {
            heartbeat_id: "hb-1".to_string(),
            tick_number: 50,
            phase: SupervisorPhase::Idle,
            outcome_of_last_tick: TickOutcome::WorkDone,
            open_obligations: 3,
            pending_events: 0,
            uptime_ticks: 50,
            emitted_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&hb).unwrap();
        let back: RuntimeHeartbeat = serde_json::from_str(&json).unwrap();
        assert_eq!(hb, back);
    }

    #[test]
    fn supervisor_checkpoint_round_trips() {
        let cp = SupervisorCheckpoint {
            checkpoint_id: "cp-1".to_string(),
            tick_number: 100,
            phase: SupervisorPhase::Idle,
            status: CheckpointStatus::Valid,
            open_obligation_ids: vec!["obl-1".to_string()],
            pending_event_count: 0,
            consecutive_errors: 0,
            consecutive_idle_ticks: 0,
            recent_tick_outcomes: vec![TickOutcome::WorkDone, TickOutcome::IdleTick],
            state_hash: "abc123".to_string(),
            created_at: "2025-01-01T00:00:00+00:00".to_string(),
        };
        let json = serde_json::to_string(&cp).unwrap();
        let back: SupervisorCheckpoint = serde_json::from_str(&json).unwrap();
        assert_eq!(cp, back);
    }

    #[test]
    fn livelock_record_round_trips() {
        let ll = LivelockRecord {
            livelock_id: "ll-1".to_string(),
            tick_number: 50,
            repeated_pattern: "idle_tick".to_string(),
            repeat_count: 5,
            strategy_applied: LivelockStrategy::Escalate,
            resolved: false,
            detected_at: "2025-01-01T00:00:00+00:00".to_string(),
            resolution_detail: String::new(),
        };
        let json = serde_json::to_string(&ll).unwrap();
        let back: LivelockRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(ll, back);
    }

    // --- Cross-format compatibility ---

    #[test]
    fn supervisor_phase_deserializes_from_python_format() {
        let sp: SupervisorPhase =
            serde_json::from_str(r#""evaluating_obligations""#).unwrap();
        assert_eq!(sp, SupervisorPhase::EvaluatingObligations);
    }

    #[test]
    fn tick_outcome_deserializes_from_python_format() {
        let to: TickOutcome =
            serde_json::from_str(r#""backpressure_applied""#).unwrap();
        assert_eq!(to, TickOutcome::BackpressureApplied);
    }
}
