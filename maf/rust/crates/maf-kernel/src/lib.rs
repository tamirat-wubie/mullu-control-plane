#![forbid(unsafe_code)]
//! MAF Core kernel types — cross-domain abstractions matching shared contracts.
//!
//! Purpose: define generic types for policy, trace, replay, verification, and execution
//! that are not specific to any single vertical (MCOI, MCCI, MXI, etc.).
//!
//! Governance: MAF generalizes what verticals prove. These types map to `schemas/`.
//! Invariants: types are serialization-stable and match docs/15_deterministic_serialization_policy.md.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

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
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    pub message: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyDecision {
    pub decision_id: String,
    pub subject_id: String,
    pub goal_id: String,
    pub status: PolicyStatus,
    pub reasons: Vec<PolicyReason>,
    pub issued_at: String,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extensions: BTreeMap<String, serde_json::Value>,
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
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extensions: BTreeMap<String, serde_json::Value>,
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
pub struct EvidenceRecord {
    pub description: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub uri: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct VerificationResult {
    pub verification_id: String,
    pub execution_id: String,
    pub status: VerificationStatus,
    pub checks: Vec<VerificationCheck>,
    pub evidence: Vec<EvidenceRecord>,
    pub closed_at: String,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extensions: BTreeMap<String, serde_json::Value>,
}

// ---------------------------------------------------------------------------
// Trace
// ---------------------------------------------------------------------------

/// Trace entry. Maps to schemas/trace_entry.schema.json.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TraceEntry {
    pub trace_id: String,
    pub parent_trace_id: Option<String>,
    pub event_type: String,
    pub subject_id: String,
    pub goal_id: String,
    pub state_hash: String,
    pub registry_hash: String,
    pub timestamp: String,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extensions: BTreeMap<String, serde_json::Value>,
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
pub struct ReplayEffect {
    pub effect_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReplayRecord {
    pub replay_id: String,
    pub trace_id: String,
    pub source_hash: String,
    pub approved_effects: Vec<ReplayEffect>,
    pub blocked_effects: Vec<ReplayEffect>,
    pub mode: ReplayMode,
    pub recorded_at: String,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extensions: BTreeMap<String, serde_json::Value>,
}

// ---------------------------------------------------------------------------
// Learning admission
// ---------------------------------------------------------------------------

/// Learning admission status. Maps to schemas/learning_admission.schema.json.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LearningAdmissionStatus {
    Admit,
    Reject,
    Defer,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LearningAdmissionDecision {
    pub admission_id: String,
    pub knowledge_id: String,
    pub status: LearningAdmissionStatus,
    pub reasons: Vec<PolicyReason>,
    pub issued_at: String,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extensions: BTreeMap<String, serde_json::Value>,
}

// ---------------------------------------------------------------------------
// Error taxonomy
// ---------------------------------------------------------------------------

/// Error family. Maps to docs/08_error_taxonomy.md.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
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

// ---------------------------------------------------------------------------
// State machine formalization
// ---------------------------------------------------------------------------

/// Outcome of checking whether a transition is legal.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TransitionVerdict {
    Allowed,
    DeniedIllegalEdge,
    DeniedTerminalState,
    DeniedGuardFailed,
}

/// A single legal edge in a state machine.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TransitionRule {
    pub from_state: String,
    pub to_state: String,
    pub action: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub guard_label: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub emits: String,
}

/// A formal, versioned specification of a lifecycle state machine.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StateMachineSpec {
    pub machine_id: String,
    pub name: String,
    pub version: String,
    pub states: Vec<String>,
    pub initial_state: String,
    pub terminal_states: Vec<String>,
    pub transitions: Vec<TransitionRule>,
}

impl StateMachineSpec {
    /// Check whether a specific transition is legal.
    pub fn is_legal(&self, from_state: &str, to_state: &str, action: &str) -> TransitionVerdict {
        if self.terminal_states.iter().any(|s| s == from_state) {
            return TransitionVerdict::DeniedTerminalState;
        }
        for t in &self.transitions {
            if t.from_state == from_state && t.to_state == to_state && t.action == action {
                return TransitionVerdict::Allowed;
            }
        }
        TransitionVerdict::DeniedIllegalEdge
    }

    /// Return all transitions legal from current_state.
    pub fn legal_actions(&self, current_state: &str) -> Vec<&TransitionRule> {
        self.transitions
            .iter()
            .filter(|t| t.from_state == current_state)
            .collect()
    }

    /// Return all states directly reachable from the given state.
    pub fn reachable_from(&self, state: &str) -> Vec<&str> {
        let mut result: Vec<&str> = self
            .transitions
            .iter()
            .filter(|t| t.from_state == state)
            .map(|t| t.to_state.as_str())
            .collect();
        result.sort();
        result.dedup();
        result
    }
}

/// Immutable record of a state transition that occurred at runtime.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TransitionAuditRecord {
    pub audit_id: String,
    pub machine_id: String,
    pub entity_id: String,
    pub from_state: String,
    pub to_state: String,
    pub action: String,
    pub verdict: TransitionVerdict,
    pub actor_id: String,
    pub reason: String,
    pub transitioned_at: String,
    #[serde(default)]
    pub metadata: std::collections::HashMap<String, serde_json::Value>,
}

// ---------------------------------------------------------------------------
// Proof substrate — transition receipts and causal lineage
// ---------------------------------------------------------------------------

/// Cryptographic proof of a state transition.
///
/// A receipt is generated for every certified transition and can be
/// verified independently. It captures the before/after state, the
/// guards evaluated, and a replay token for deterministic re-execution.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TransitionReceipt {
    pub receipt_id: String,
    pub machine_id: String,
    pub entity_id: String,
    pub from_state: String,
    pub to_state: String,
    pub action: String,
    pub before_state_hash: String,
    pub after_state_hash: String,
    pub guard_verdicts: Vec<GuardVerdict>,
    pub verdict: TransitionVerdict,
    pub replay_token: String,
    pub causal_parent: String,
    pub issued_at: String,
    pub receipt_hash: String,
}

/// Record of a guard evaluation during transition certification.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GuardVerdict {
    pub guard_id: String,
    pub passed: bool,
    pub reason: String,
}

/// Causal lineage — links transitions into a provable chain.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CausalLineage {
    pub lineage_id: String,
    pub entity_id: String,
    pub receipt_chain: Vec<String>,
    pub root_receipt_id: String,
    pub current_state: String,
    pub depth: u32,
}

/// A complete proof capsule for a transition — everything needed to
/// verify that a state change was legal, governed, and reproducible.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProofCapsule {
    pub receipt: TransitionReceipt,
    pub audit_record: TransitionAuditRecord,
    pub lineage_depth: u32,
}

/// Parameters for certifying a state transition.
#[derive(Debug, Clone)]
pub struct CertifyParams<'a> {
    pub entity_id: &'a str,
    pub from_state: &'a str,
    pub to_state: &'a str,
    pub action: &'a str,
    pub before_state_hash: &'a str,
    pub after_state_hash: &'a str,
    pub guards: &'a [GuardVerdict],
    pub actor_id: &'a str,
    pub reason: &'a str,
    pub causal_parent: &'a str,
    pub timestamp: &'a str,
}

impl StateMachineSpec {
    /// Certify a transition: check legality, produce a receipt.
    ///
    /// This is the core substrate certification function. Every governed
    /// transition should go through this rather than raw `is_legal()`.
    ///
    /// Behavior:
    ///   * Illegal transition → returns `Err(TransitionVerdict::Denied*)`.
    ///     No receipt is produced because there is no legal edge to prove.
    ///   * Legal transition, all guards passing → `Ok(ProofCapsule)` with
    ///     `verdict = Allowed`.
    ///   * Legal transition, one or more failed guards → `Ok(ProofCapsule)`
    ///     with `verdict = DeniedGuardFailed`, including the full guard
    ///     list (passing AND failing). The receipt IS the proof of the
    ///     denial; stripping failed guards would erase the audit trail of
    ///     the rejected decision.
    ///
    /// Callers that previously matched on `Err(DeniedGuardFailed)` should
    /// instead inspect `capsule.receipt.verdict`.
    pub fn certify_transition(
        &self,
        p: &CertifyParams<'_>,
    ) -> Result<ProofCapsule, TransitionVerdict> {
        // Check legality (always Err for illegal edges; no receipt to emit).
        let mut verdict = self.is_legal(p.from_state, p.to_state, p.action);
        if verdict != TransitionVerdict::Allowed {
            return Err(verdict);
        }

        // Failed guards downgrade verdict to DeniedGuardFailed but the
        // receipt is still produced with the full guard list.
        if p.guards.iter().any(|g| !g.passed) {
            verdict = TransitionVerdict::DeniedGuardFailed;
        }

        // Build receipt
        let receipt_content = format!(
            "{}:{}:{}:{}:{}:{}:{}",
            p.entity_id,
            p.from_state,
            p.to_state,
            p.action,
            p.before_state_hash,
            p.after_state_hash,
            p.causal_parent,
        );
        let receipt_hash = sha256_hex(&receipt_content);
        let receipt_id = format!("rcpt-{}", &receipt_hash[..16]);
        let replay_token = format!(
            "replay-{}",
            &sha256_hex(&format!("{}:{}", receipt_content, p.timestamp))[..16]
        );

        let receipt = TransitionReceipt {
            receipt_id: receipt_id.clone(),
            machine_id: self.machine_id.clone(),
            entity_id: p.entity_id.to_string(),
            from_state: p.from_state.to_string(),
            to_state: p.to_state.to_string(),
            action: p.action.to_string(),
            before_state_hash: p.before_state_hash.to_string(),
            after_state_hash: p.after_state_hash.to_string(),
            guard_verdicts: p.guards.to_vec(),
            verdict,
            replay_token,
            causal_parent: p.causal_parent.to_string(),
            issued_at: p.timestamp.to_string(),
            receipt_hash: receipt_hash.clone(),
        };

        let audit_record = TransitionAuditRecord {
            audit_id: format!("audit-{}", &receipt_hash[..12]),
            machine_id: self.machine_id.clone(),
            entity_id: p.entity_id.to_string(),
            from_state: p.from_state.to_string(),
            to_state: p.to_state.to_string(),
            action: p.action.to_string(),
            verdict,
            actor_id: p.actor_id.to_string(),
            reason: p.reason.to_string(),
            transitioned_at: p.timestamp.to_string(),
            metadata: std::collections::HashMap::new(),
        };

        Ok(ProofCapsule {
            receipt,
            audit_record,
            lineage_depth: 0,
        })
    }
}

/// Compute SHA-256 hex digest of the input string. Matches Python's
/// `hashlib.sha256(input.encode()).hexdigest()` byte-for-byte: this equality
/// is the cross-language receipt-hash contract enforced by
/// `receipt_hash_matches_python_sha256` in this crate's tests and
/// `tests/test_proof_hash_contract.py` on the Python side.
fn sha256_hex(input: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    format!("{:x}", hasher.finalize())
}

// ---------------------------------------------------------------------------
// Lifecycle state enums (match Python canonical machines)
// ---------------------------------------------------------------------------

/// States in the checkpoint/restore lifecycle machine.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CheckpointLifecycleState {
    Idle,
    Capturing,
    VerifyingCapture,
    Committed,
    Restoring,
    VerifyingRestore,
    Verified,
    RollingBack,
    Failed,
}

/// States in the reaction pipeline lifecycle machine.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReactionPipelineState {
    Received,
    Matching,
    IdempotencyCheck,
    BackpressureCheck,
    Gating,
    Executed,
    Emitted,
    Deferred,
    Rejected,
    Recorded,
}

/// States in the obligation lifecycle machine.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ObligationLifecycleState {
    Pending,
    Active,
    Escalated,
    Completed,
    Expired,
    Cancelled,
}

// ---------------------------------------------------------------------------
// Canonical machine constructors
// ---------------------------------------------------------------------------

fn tr(from: &str, to: &str, action: &str, guard: &str, emits: &str) -> TransitionRule {
    TransitionRule {
        from_state: from.into(),
        to_state: to.into(),
        action: action.into(),
        guard_label: guard.into(),
        emits: emits.into(),
    }
}

/// Construct the canonical obligation lifecycle machine (v2.0.0, 16 edges).
pub fn obligation_machine() -> StateMachineSpec {
    StateMachineSpec {
        machine_id: "obligation-lifecycle".into(),
        name: "Obligation Lifecycle".into(),
        version: "2.0.0".into(),
        states: vec![
            "pending".into(),
            "active".into(),
            "escalated".into(),
            "completed".into(),
            "expired".into(),
            "cancelled".into(),
        ],
        initial_state: "pending".into(),
        terminal_states: vec!["completed".into(), "expired".into(), "cancelled".into()],
        transitions: vec![
            tr("pending", "active", "activate", "", "obligation_activated"),
            tr(
                "pending",
                "completed",
                "close",
                "final_state=completed",
                "obligation_closed",
            ),
            tr(
                "pending",
                "expired",
                "close",
                "final_state=expired",
                "obligation_expired",
            ),
            tr(
                "pending",
                "cancelled",
                "close",
                "final_state=cancelled",
                "obligation_cancelled",
            ),
            tr(
                "pending",
                "escalated",
                "escalate",
                "",
                "obligation_escalated",
            ),
            tr(
                "pending",
                "pending",
                "transfer",
                "owner_changes",
                "obligation_transferred",
            ),
            tr(
                "active",
                "completed",
                "close",
                "final_state=completed",
                "obligation_closed",
            ),
            tr(
                "active",
                "expired",
                "close",
                "final_state=expired",
                "obligation_expired",
            ),
            tr(
                "active",
                "cancelled",
                "close",
                "final_state=cancelled",
                "obligation_cancelled",
            ),
            tr(
                "active",
                "escalated",
                "escalate",
                "",
                "obligation_escalated",
            ),
            tr(
                "active",
                "active",
                "transfer",
                "owner_changes",
                "obligation_transferred",
            ),
            tr(
                "escalated",
                "completed",
                "close",
                "final_state=completed",
                "obligation_closed",
            ),
            tr(
                "escalated",
                "expired",
                "close",
                "final_state=expired",
                "obligation_expired",
            ),
            tr(
                "escalated",
                "cancelled",
                "close",
                "final_state=cancelled",
                "obligation_cancelled",
            ),
            tr(
                "escalated",
                "escalated",
                "escalate",
                "re-escalation to higher authority",
                "obligation_escalated",
            ),
            tr(
                "escalated",
                "escalated",
                "transfer",
                "owner_changes",
                "obligation_transferred",
            ),
        ],
    }
}

/// Construct the canonical supervisor tick lifecycle machine (v2.0.0, 33 edges).
/// 13 states, includes error from all non-terminal/non-halted phases including paused.
pub fn supervisor_machine() -> StateMachineSpec {
    StateMachineSpec {
        machine_id: "supervisor-tick-lifecycle".into(),
        name: "Supervisor Tick Lifecycle".into(),
        version: "2.0.0".into(),
        states: vec![
            "idle".into(),
            "polling".into(),
            "evaluating_obligations".into(),
            "evaluating_deadlines".into(),
            "waking_work".into(),
            "running_reactions".into(),
            "reasoning".into(),
            "acting".into(),
            "checkpointing".into(),
            "emitting_heartbeat".into(),
            "paused".into(),
            "degraded".into(),
            "halted".into(),
        ],
        initial_state: "idle".into(),
        terminal_states: vec!["halted".into()],
        transitions: vec![
            // Normal tick flow
            tr(
                "idle",
                "polling",
                "tick_start",
                "",
                "supervisor_tick_started",
            ),
            tr(
                "polling",
                "evaluating_obligations",
                "poll_complete",
                "",
                "supervisor_poll_complete",
            ),
            tr(
                "polling",
                "degraded",
                "backpressure_triggered",
                "",
                "supervisor_backpressure",
            ),
            tr(
                "evaluating_obligations",
                "evaluating_deadlines",
                "obligations_evaluated",
                "",
                "",
            ),
            tr(
                "evaluating_deadlines",
                "waking_work",
                "deadlines_evaluated",
                "",
                "",
            ),
            tr("waking_work", "running_reactions", "work_woken", "", ""),
            tr(
                "running_reactions",
                "reasoning",
                "reactions_complete",
                "",
                "",
            ),
            tr("reasoning", "acting", "reasoning_complete", "", ""),
            tr(
                "acting",
                "checkpointing",
                "actions_complete",
                "checkpoint_interval_reached",
                "supervisor_checkpointing",
            ),
            tr(
                "acting",
                "emitting_heartbeat",
                "actions_complete_no_checkpoint",
                "checkpoint_interval_not_reached",
                "",
            ),
            tr(
                "acting",
                "idle",
                "tick_complete",
                "",
                "supervisor_tick_complete",
            ),
            tr(
                "checkpointing",
                "emitting_heartbeat",
                "checkpoint_complete",
                "heartbeat_interval_reached",
                "supervisor_checkpoint_complete",
            ),
            tr(
                "checkpointing",
                "idle",
                "checkpoint_complete_no_heartbeat",
                "heartbeat_interval_not_reached",
                "supervisor_checkpoint_complete",
            ),
            tr(
                "emitting_heartbeat",
                "idle",
                "heartbeat_complete",
                "",
                "supervisor_heartbeat_emitted",
            ),
            // Pause/resume
            tr("idle", "paused", "pause", "", "supervisor_paused"),
            tr("paused", "idle", "resume", "", "supervisor_resumed"),
            tr(
                "paused",
                "halted",
                "halt",
                "operator_halt_while_paused",
                "supervisor_halted",
            ),
            tr("paused", "degraded", "error", "", "supervisor_error"),
            // Degraded paths
            tr(
                "degraded",
                "idle",
                "tick_complete",
                "backpressure/livelock resolved",
                "",
            ),
            tr(
                "degraded",
                "halted",
                "halt",
                "livelock strategy=HALT or max_errors exceeded",
                "supervisor_halted",
            ),
            tr(
                "degraded",
                "paused",
                "pause",
                "operator_pause_in_degraded",
                "supervisor_paused",
            ),
            // Livelock
            tr(
                "acting",
                "degraded",
                "livelock_detected",
                "",
                "supervisor_livelock",
            ),
            // Error from all working phases → degraded
            tr("idle", "degraded", "error", "", "supervisor_error"),
            tr("polling", "degraded", "error", "", "supervisor_error"),
            tr(
                "evaluating_obligations",
                "degraded",
                "error",
                "",
                "supervisor_error",
            ),
            tr(
                "evaluating_deadlines",
                "degraded",
                "error",
                "",
                "supervisor_error",
            ),
            tr("waking_work", "degraded", "error", "", "supervisor_error"),
            tr(
                "running_reactions",
                "degraded",
                "error",
                "",
                "supervisor_error",
            ),
            tr("reasoning", "degraded", "error", "", "supervisor_error"),
            tr("acting", "degraded", "error", "", "supervisor_error"),
            tr("checkpointing", "degraded", "error", "", "supervisor_error"),
            tr(
                "emitting_heartbeat",
                "degraded",
                "error",
                "",
                "supervisor_error",
            ),
            tr("degraded", "degraded", "error", "", "supervisor_error"),
        ],
    }
}

/// Construct the canonical reaction pipeline machine (v2.0.0, 17 edges).
pub fn reaction_pipeline_machine() -> StateMachineSpec {
    StateMachineSpec {
        machine_id: "reaction-pipeline".into(),
        name: "Reaction Pipeline".into(),
        version: "2.0.0".into(),
        states: vec![
            "received".into(),
            "matching".into(),
            "idempotency_check".into(),
            "backpressure_check".into(),
            "gating".into(),
            "executed".into(),
            "emitted".into(),
            "deferred".into(),
            "rejected".into(),
            "recorded".into(),
        ],
        initial_state: "received".into(),
        terminal_states: vec!["recorded".into()],
        transitions: vec![
            tr("received", "matching", "begin_react", "", ""),
            tr("matching", "idempotency_check", "rules_matched", "", ""),
            tr(
                "matching",
                "recorded",
                "no_rules_matched",
                "zero matched rules",
                "",
            ),
            tr(
                "idempotency_check",
                "rejected",
                "duplicate_detected",
                "",
                "reaction_rejected",
            ),
            tr(
                "idempotency_check",
                "backpressure_check",
                "not_duplicate",
                "",
                "",
            ),
            tr(
                "backpressure_check",
                "deferred",
                "backpressure_limit",
                "",
                "reaction_deferred",
            ),
            tr("backpressure_check", "gating", "backpressure_ok", "", ""),
            tr(
                "gating",
                "executed",
                "verdict_proceed",
                "",
                "reaction_executed",
            ),
            tr(
                "gating",
                "deferred",
                "verdict_defer",
                "",
                "reaction_deferred",
            ),
            tr(
                "gating",
                "rejected",
                "verdict_reject",
                "",
                "reaction_rejected",
            ),
            tr(
                "gating",
                "rejected",
                "verdict_escalate",
                "",
                "reaction_rejected",
            ),
            tr(
                "gating",
                "rejected",
                "verdict_requires_approval",
                "",
                "reaction_rejected",
            ),
            tr(
                "executed",
                "emitted",
                "emit_event",
                "",
                "reaction_event_emitted",
            ),
            tr("emitted", "recorded", "record", "", ""),
            tr("executed", "recorded", "record", "no_event_emission", ""),
            tr("deferred", "recorded", "record", "", ""),
            tr("rejected", "recorded", "record", "", ""),
        ],
    }
}

/// Construct the canonical checkpoint lifecycle machine (v1.0.0, 13 edges).
pub fn checkpoint_lifecycle_machine() -> StateMachineSpec {
    StateMachineSpec {
        machine_id: "checkpoint-lifecycle".into(),
        name: "Checkpoint Lifecycle".into(),
        version: "1.0.0".into(),
        states: vec![
            "idle".into(),
            "capturing".into(),
            "verifying_capture".into(),
            "committed".into(),
            "restoring".into(),
            "verifying_restore".into(),
            "verified".into(),
            "rolling_back".into(),
            "failed".into(),
        ],
        initial_state: "idle".into(),
        terminal_states: vec!["failed".into()],
        transitions: vec![
            // Capture flow
            tr(
                "idle",
                "capturing",
                "begin_capture",
                "",
                "checkpoint_capture_started",
            ),
            tr(
                "capturing",
                "verifying_capture",
                "snapshots_complete",
                "",
                "checkpoint_snapshots_captured",
            ),
            tr(
                "verifying_capture",
                "committed",
                "hash_verified",
                "",
                "checkpoint_committed",
            ),
            tr(
                "verifying_capture",
                "failed",
                "hash_mismatch",
                "",
                "checkpoint_capture_failed",
            ),
            tr(
                "committed",
                "idle",
                "capture_finalized",
                "",
                "checkpoint_capture_complete",
            ),
            // Restore flow
            tr(
                "idle",
                "restoring",
                "begin_restore",
                "",
                "checkpoint_restore_started",
            ),
            tr(
                "restoring",
                "verifying_restore",
                "subsystems_restored",
                "",
                "checkpoint_subsystems_restored",
            ),
            tr(
                "verifying_restore",
                "verified",
                "restore_hash_verified",
                "",
                "checkpoint_restore_verified",
            ),
            tr(
                "verified",
                "idle",
                "restore_finalized",
                "",
                "checkpoint_restore_complete",
            ),
            // Rollback paths
            tr(
                "verifying_restore",
                "rolling_back",
                "restore_hash_mismatch",
                "",
                "checkpoint_rollback_triggered",
            ),
            tr(
                "restoring",
                "rolling_back",
                "restore_error",
                "",
                "checkpoint_rollback_triggered",
            ),
            tr(
                "rolling_back",
                "idle",
                "rollback_complete",
                "",
                "checkpoint_rollback_complete",
            ),
            tr(
                "rolling_back",
                "failed",
                "rollback_failed",
                "",
                "checkpoint_rollback_failed",
            ),
        ],
    }
}

// ---------------------------------------------------------------------------
// Checkpoint journal types
// ---------------------------------------------------------------------------

/// What kind of event a journal entry records.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JournalEntryKind {
    Tick,
    Transition,
    Checkpoint,
    EventEmitted,
    ObligationChanged,
    ReactionDecided,
    Heartbeat,
    Livelock,
    Halt,
    Resume,
}

/// A single append-only journal entry for deterministic replay.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct JournalEntry {
    pub entry_id: String,
    pub epoch_id: String,
    pub sequence: u64,
    pub kind: JournalEntryKind,
    pub subject_id: String,
    pub payload: serde_json::Value,
    pub recorded_at: String,
}

/// What subsystems a checkpoint covers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CheckpointScope {
    Supervisor,
    EventSpine,
    ObligationRuntime,
    ReactionEngine,
    Composite,
}

/// Snapshot of a single subsystem's state at a checkpoint boundary.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SubsystemSnapshot {
    pub snapshot_id: String,
    pub scope: CheckpointScope,
    pub state_hash: String,
    pub record_count: u64,
    pub captured_at: String,
    #[serde(default, skip_serializing_if = "std::collections::HashMap::is_empty")]
    pub payload: std::collections::HashMap<String, serde_json::Value>,
}

/// A unified checkpoint spanning all subsystems at a single boundary.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CompositeCheckpoint {
    pub checkpoint_id: String,
    pub epoch_id: String,
    pub tick_number: u64,
    pub snapshots: Vec<SubsystemSnapshot>,
    pub journal_sequence: u64,
    pub composite_hash: String,
    pub created_at: String,
}

impl CompositeCheckpoint {
    /// Return the snapshot for a specific subsystem scope, if present.
    pub fn snapshot_for(&self, scope: CheckpointScope) -> Option<&SubsystemSnapshot> {
        self.snapshots.iter().find(|s| s.scope == scope)
    }
}

// ---------------------------------------------------------------------------
// Restore verification types
// ---------------------------------------------------------------------------

/// Outcome of a checkpoint restoration verification.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RestoreVerdict {
    Verified,
    HashMismatch,
    SubsystemMissing,
    RollbackTriggered,
}

/// Immutable record of a checkpoint restore and its verification outcome.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RestoreVerification {
    pub verification_id: String,
    pub checkpoint_id: String,
    pub epoch_id: String,
    pub tick_number: u64,
    pub verdict: RestoreVerdict,
    pub expected_composite_hash: String,
    pub actual_composite_hash: String,
    #[serde(default, skip_serializing_if = "std::collections::HashMap::is_empty")]
    pub subsystem_results:
        std::collections::HashMap<String, std::collections::HashMap<String, String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub verified_at: Option<String>,
}

// ---------------------------------------------------------------------------
// Journal validation types
// ---------------------------------------------------------------------------

/// Outcome of journal integrity validation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JournalValidationVerdict {
    Valid,
    SequenceGap,
    EpochMismatch,
    OrderingViolation,
    EmptyJournal,
}

/// Result of validating a journal segment's integrity.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct JournalValidationResult {
    pub validation_id: String,
    pub epoch_id: String,
    pub entry_count: u64,
    pub first_sequence: u64,
    pub last_sequence: u64,
    pub verdict: JournalValidationVerdict,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub gap_positions: Vec<u64>,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub detail: String,
}

// ---------------------------------------------------------------------------
// Journal replay types
// ---------------------------------------------------------------------------

/// Outcome of a single replayed journal entry.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReplayStepVerdict {
    Match,
    OutcomeDiverged,
    TickNumberDiverged,
    Skipped,
    Error,
}

/// Overall outcome of a replay session.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReplaySessionVerdict {
    Success,
    DivergenceDetected,
    EmptyJournal,
    Aborted,
}

/// Result of replaying a single journal entry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReplayStepResult {
    pub step_id: String,
    pub sequence: u64,
    pub kind: JournalEntryKind,
    pub verdict: ReplayStepVerdict,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expected_payload: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actual_payload: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub detail: String,
}

/// Overall result of a replay session.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReplaySessionResult {
    pub session_id: String,
    pub epoch_id: String,
    pub entries_replayed: u64,
    pub entries_matched: u64,
    pub entries_diverged: u64,
    pub entries_skipped: u64,
    pub verdict: ReplaySessionVerdict,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub steps: Vec<ReplayStepResult>,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub started_at: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub completed_at: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::de::DeserializeOwned;

    fn assert_fixture_round_trip<T>(fixture_json: &str)
    where
        T: DeserializeOwned + Serialize,
    {
        let fixture_value: serde_json::Value = serde_json::from_str(fixture_json).unwrap();
        let parsed: T = serde_json::from_str(fixture_json).unwrap();
        let round_trip_value = serde_json::to_value(parsed).unwrap();
        assert_eq!(fixture_value, round_trip_value);
    }

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
    fn learning_admission_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&LearningAdmissionStatus::Admit).unwrap();
        assert_eq!(json, r#""admit""#);
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
            metadata: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        let json = serde_json::to_string(&entry).unwrap();
        let restored: TraceEntry = serde_json::from_str(&json).unwrap();
        assert_eq!(entry, restored);
        assert!(json.contains("\"parent_trace_id\":\"trace-0\""));
    }

    #[test]
    fn policy_decision_round_trips() {
        let decision = PolicyDecision {
            decision_id: "d-1".into(),
            subject_id: "s-1".into(),
            goal_id: "g-1".into(),
            status: PolicyStatus::Allow,
            reasons: vec![PolicyReason {
                code: Some("ok".into()),
                message: "all good".into(),
                details: Some(serde_json::json!({"kind": "audit"})),
            }],
            issued_at: "2026-03-19T00:00:00+00:00".into(),
            metadata: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        let json = serde_json::to_string(&decision).unwrap();
        let restored: PolicyDecision = serde_json::from_str(&json).unwrap();
        assert_eq!(decision, restored);
        assert!(json.contains("\"details\":{\"kind\":\"audit\"}"));
    }

    #[test]
    fn verification_result_round_trips() {
        let verification = VerificationResult {
            verification_id: "v-1".into(),
            execution_id: "e-1".into(),
            status: VerificationStatus::Pass,
            checks: vec![VerificationCheck {
                name: "stdout".into(),
                status: VerificationStatus::Pass,
                details: Some(serde_json::json!({"matched": true})),
            }],
            evidence: vec![EvidenceRecord {
                description: "captured stdout".into(),
                uri: Some("memory://stdout".into()),
                details: None,
            }],
            closed_at: "2026-03-19T00:00:00+00:00".into(),
            metadata: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        let json = serde_json::to_string(&verification).unwrap();
        let restored: VerificationResult = serde_json::from_str(&json).unwrap();
        assert_eq!(verification, restored);
        assert!(json.contains("\"evidence\""));
    }

    #[test]
    fn replay_record_round_trips() {
        let replay = ReplayRecord {
            replay_id: "r-1".into(),
            trace_id: "t-1".into(),
            source_hash: "sha256:abc".into(),
            approved_effects: vec![ReplayEffect {
                effect_id: "eff-1".into(),
                description: Some("approved".into()),
                details: None,
            }],
            blocked_effects: vec![ReplayEffect {
                effect_id: "eff-2".into(),
                description: Some("blocked".into()),
                details: Some(serde_json::json!({"reason": "unsafe"})),
            }],
            mode: ReplayMode::ObservationOnly,
            recorded_at: "2026-03-19T00:00:00+00:00".into(),
            metadata: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        let json = serde_json::to_string(&replay).unwrap();
        let restored: ReplayRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(replay, restored);
        assert!(json.contains("\"approved_effects\""));
    }

    #[test]
    fn learning_admission_round_trips() {
        let decision = LearningAdmissionDecision {
            admission_id: "adm-1".into(),
            knowledge_id: "know-1".into(),
            status: LearningAdmissionStatus::Admit,
            reasons: vec![PolicyReason {
                code: None,
                message: "verified observation".into(),
                details: None,
            }],
            issued_at: "2026-03-19T00:00:00+00:00".into(),
            metadata: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        let json = serde_json::to_string(&decision).unwrap();
        let restored: LearningAdmissionDecision = serde_json::from_str(&json).unwrap();
        assert_eq!(decision, restored);
        assert!(json.contains("\"status\":\"admit\""));
    }

    #[test]
    fn canonical_policy_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/policy_decision.json"
        ));
        assert_fixture_round_trip::<PolicyDecision>(fixture_json);
    }

    #[test]
    fn canonical_execution_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/execution_result.json"
        ));
        assert_fixture_round_trip::<ExecutionResult>(fixture_json);
    }

    #[test]
    fn canonical_trace_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/trace_entry.json"
        ));
        assert_fixture_round_trip::<TraceEntry>(fixture_json);
    }

    #[test]
    fn canonical_replay_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/replay_record.json"
        ));
        assert_fixture_round_trip::<ReplayRecord>(fixture_json);
    }

    #[test]
    fn canonical_verification_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/verification_result.json"
        ));
        assert_fixture_round_trip::<VerificationResult>(fixture_json);
    }

    #[test]
    fn canonical_learning_admission_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/learning_admission.json"
        ));
        assert_fixture_round_trip::<LearningAdmissionDecision>(fixture_json);
    }

    // -------------------------------------------------------------------
    // State machine tests
    // -------------------------------------------------------------------

    #[test]
    fn transition_verdict_serializes_to_snake_case() {
        assert_eq!(
            serde_json::to_string(&TransitionVerdict::Allowed).unwrap(),
            r#""allowed""#
        );
        assert_eq!(
            serde_json::to_string(&TransitionVerdict::DeniedIllegalEdge).unwrap(),
            r#""denied_illegal_edge""#
        );
        assert_eq!(
            serde_json::to_string(&TransitionVerdict::DeniedTerminalState).unwrap(),
            r#""denied_terminal_state""#
        );
    }

    #[test]
    fn state_machine_legal_transition() {
        let m = obligation_machine();
        assert_eq!(
            m.is_legal("pending", "active", "activate"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("active", "completed", "close"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn state_machine_illegal_transition() {
        let m = obligation_machine();
        // pending→escalated via "close" is illegal (close goes to terminal states)
        assert_eq!(
            m.is_legal("pending", "escalated", "close"),
            TransitionVerdict::DeniedIllegalEdge
        );
    }

    #[test]
    fn state_machine_terminal_state_blocks_all() {
        let m = obligation_machine();
        assert_eq!(
            m.is_legal("completed", "active", "activate"),
            TransitionVerdict::DeniedTerminalState
        );
        assert_eq!(
            m.is_legal("expired", "pending", "reset"),
            TransitionVerdict::DeniedTerminalState
        );
    }

    #[test]
    fn state_machine_legal_actions() {
        let m = obligation_machine();
        let actions = m.legal_actions("pending");
        // v2: pending has activate, close(×3 guards), escalate, transfer = 6 edges
        assert_eq!(actions.len(), 6);
        assert!(actions.iter().any(|t| t.to_state == "active"));
        assert!(actions.iter().any(|t| t.to_state == "completed"));
        assert!(actions.iter().any(|t| t.to_state == "escalated"));
        assert!(actions
            .iter()
            .any(|t| t.to_state == "pending" && t.action == "transfer"));
    }

    #[test]
    fn state_machine_reachable_from() {
        let m = obligation_machine();
        let reachable = m.reachable_from("active");
        // v2: active → completed, expired, cancelled, escalated, active(transfer)
        assert_eq!(
            reachable,
            vec!["active", "cancelled", "completed", "escalated", "expired"]
        );
    }

    #[test]
    fn state_machine_spec_round_trips() {
        let m = obligation_machine();
        let json = serde_json::to_string(&m).unwrap();
        let restored: StateMachineSpec = serde_json::from_str(&json).unwrap();
        assert_eq!(m, restored);
    }

    #[test]
    fn transition_audit_record_round_trips() {
        let mut metadata = std::collections::HashMap::new();
        metadata.insert("context".into(), serde_json::json!("test"));
        let rec = TransitionAuditRecord {
            audit_id: "a-1".into(),
            machine_id: "obligation-lifecycle".into(),
            entity_id: "obl-1".into(),
            from_state: "pending".into(),
            to_state: "active".into(),
            action: "activate".into(),
            verdict: TransitionVerdict::Allowed,
            actor_id: "supervisor".into(),
            reason: "deadline approaching".into(),
            transitioned_at: "2026-03-20T00:00:00+00:00".into(),
            metadata,
        };
        let json = serde_json::to_string(&rec).unwrap();
        let restored: TransitionAuditRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(rec, restored);
    }

    // -------------------------------------------------------------------
    // Journal and checkpoint tests
    // -------------------------------------------------------------------

    #[test]
    fn journal_entry_kind_serializes() {
        assert_eq!(
            serde_json::to_string(&JournalEntryKind::Tick).unwrap(),
            r#""tick""#
        );
        assert_eq!(
            serde_json::to_string(&JournalEntryKind::Transition).unwrap(),
            r#""transition""#
        );
        assert_eq!(
            serde_json::to_string(&JournalEntryKind::Checkpoint).unwrap(),
            r#""checkpoint""#
        );
        assert_eq!(
            serde_json::to_string(&JournalEntryKind::Livelock).unwrap(),
            r#""livelock""#
        );
    }

    #[test]
    fn checkpoint_scope_serializes() {
        assert_eq!(
            serde_json::to_string(&CheckpointScope::Supervisor).unwrap(),
            r#""supervisor""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointScope::EventSpine).unwrap(),
            r#""event_spine""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointScope::Composite).unwrap(),
            r#""composite""#
        );
    }

    #[test]
    fn composite_checkpoint_round_trips() {
        let cp = CompositeCheckpoint {
            checkpoint_id: "cp-1".into(),
            epoch_id: "epoch-1".into(),
            tick_number: 42,
            snapshots: vec![
                SubsystemSnapshot {
                    snapshot_id: "snap-1".into(),
                    scope: CheckpointScope::Supervisor,
                    state_hash: "abc123".into(),
                    record_count: 10,
                    captured_at: "2026-03-20T00:00:00+00:00".into(),
                    payload: std::collections::HashMap::new(),
                },
                SubsystemSnapshot {
                    snapshot_id: "snap-2".into(),
                    scope: CheckpointScope::EventSpine,
                    state_hash: "def456".into(),
                    record_count: 100,
                    captured_at: "2026-03-20T00:00:00+00:00".into(),
                    payload: std::collections::HashMap::new(),
                },
            ],
            journal_sequence: 500,
            composite_hash: "composite-hash-1".into(),
            created_at: "2026-03-20T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&cp).unwrap();
        let restored: CompositeCheckpoint = serde_json::from_str(&json).unwrap();
        assert_eq!(cp, restored);
    }

    #[test]
    fn composite_checkpoint_snapshot_for() {
        let cp = CompositeCheckpoint {
            checkpoint_id: "cp-1".into(),
            epoch_id: "epoch-1".into(),
            tick_number: 1,
            snapshots: vec![SubsystemSnapshot {
                snapshot_id: "s-1".into(),
                scope: CheckpointScope::Supervisor,
                state_hash: "h".into(),
                record_count: 0,
                captured_at: "2026-03-20T00:00:00+00:00".into(),
                payload: std::collections::HashMap::new(),
            }],
            journal_sequence: 0,
            composite_hash: "h".into(),
            created_at: "2026-03-20T00:00:00+00:00".into(),
        };
        assert!(cp.snapshot_for(CheckpointScope::Supervisor).is_some());
        assert!(cp.snapshot_for(CheckpointScope::EventSpine).is_none());
    }

    #[test]
    fn journal_entry_round_trips() {
        let entry = JournalEntry {
            entry_id: "j-1".into(),
            epoch_id: "epoch-1".into(),
            sequence: 0,
            kind: JournalEntryKind::Tick,
            subject_id: "supervisor".into(),
            payload: serde_json::json!({"tick": 1, "outcome": "work_done"}),
            recorded_at: "2026-03-20T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&entry).unwrap();
        let restored: JournalEntry = serde_json::from_str(&json).unwrap();
        assert_eq!(entry, restored);
    }

    // -------------------------------------------------------------------
    // Restore verification tests
    // -------------------------------------------------------------------

    #[test]
    fn restore_verdict_serializes_to_snake_case() {
        assert_eq!(
            serde_json::to_string(&RestoreVerdict::Verified).unwrap(),
            r#""verified""#
        );
        assert_eq!(
            serde_json::to_string(&RestoreVerdict::HashMismatch).unwrap(),
            r#""hash_mismatch""#
        );
        assert_eq!(
            serde_json::to_string(&RestoreVerdict::SubsystemMissing).unwrap(),
            r#""subsystem_missing""#
        );
        assert_eq!(
            serde_json::to_string(&RestoreVerdict::RollbackTriggered).unwrap(),
            r#""rollback_triggered""#
        );
    }

    #[test]
    fn restore_verification_round_trips() {
        let rv = RestoreVerification {
            verification_id: "rv-1".into(),
            checkpoint_id: "cp-1".into(),
            epoch_id: "epoch-1".into(),
            tick_number: 10,
            verdict: RestoreVerdict::Verified,
            expected_composite_hash: "abc123".into(),
            actual_composite_hash: "abc123".into(),
            subsystem_results: std::collections::HashMap::new(),
            verified_at: Some("2026-03-20T00:00:00+00:00".into()),
        };
        let json = serde_json::to_string(&rv).unwrap();
        let restored: RestoreVerification = serde_json::from_str(&json).unwrap();
        assert_eq!(rv, restored);
    }

    #[test]
    fn journal_validation_verdict_serializes() {
        assert_eq!(
            serde_json::to_string(&JournalValidationVerdict::Valid).unwrap(),
            r#""valid""#
        );
        assert_eq!(
            serde_json::to_string(&JournalValidationVerdict::SequenceGap).unwrap(),
            r#""sequence_gap""#
        );
        assert_eq!(
            serde_json::to_string(&JournalValidationVerdict::EpochMismatch).unwrap(),
            r#""epoch_mismatch""#
        );
        assert_eq!(
            serde_json::to_string(&JournalValidationVerdict::OrderingViolation).unwrap(),
            r#""ordering_violation""#
        );
        assert_eq!(
            serde_json::to_string(&JournalValidationVerdict::EmptyJournal).unwrap(),
            r#""empty_journal""#
        );
    }

    #[test]
    fn journal_validation_result_round_trips() {
        let jvr = JournalValidationResult {
            validation_id: "jv-1".into(),
            epoch_id: "epoch-1".into(),
            entry_count: 50,
            first_sequence: 0,
            last_sequence: 49,
            verdict: JournalValidationVerdict::Valid,
            gap_positions: vec![],
            detail: String::new(),
        };
        let json = serde_json::to_string(&jvr).unwrap();
        let restored: JournalValidationResult = serde_json::from_str(&json).unwrap();
        assert_eq!(jvr, restored);
    }

    #[test]
    fn journal_validation_result_with_gaps_round_trips() {
        let jvr = JournalValidationResult {
            validation_id: "jv-2".into(),
            epoch_id: "epoch-1".into(),
            entry_count: 8,
            first_sequence: 0,
            last_sequence: 10,
            verdict: JournalValidationVerdict::SequenceGap,
            gap_positions: vec![3, 7],
            detail: "2 gap(s) detected".into(),
        };
        let json = serde_json::to_string(&jvr).unwrap();
        let restored: JournalValidationResult = serde_json::from_str(&json).unwrap();
        assert_eq!(jvr, restored);
    }

    // -------------------------------------------------------------------
    // Replay types tests
    // -------------------------------------------------------------------

    #[test]
    fn replay_step_verdict_serializes() {
        assert_eq!(
            serde_json::to_string(&ReplayStepVerdict::Match).unwrap(),
            r#""match""#
        );
        assert_eq!(
            serde_json::to_string(&ReplayStepVerdict::OutcomeDiverged).unwrap(),
            r#""outcome_diverged""#
        );
        assert_eq!(
            serde_json::to_string(&ReplayStepVerdict::TickNumberDiverged).unwrap(),
            r#""tick_number_diverged""#
        );
        assert_eq!(
            serde_json::to_string(&ReplayStepVerdict::Skipped).unwrap(),
            r#""skipped""#
        );
        assert_eq!(
            serde_json::to_string(&ReplayStepVerdict::Error).unwrap(),
            r#""error""#
        );
    }

    #[test]
    fn replay_session_verdict_serializes() {
        assert_eq!(
            serde_json::to_string(&ReplaySessionVerdict::Success).unwrap(),
            r#""success""#
        );
        assert_eq!(
            serde_json::to_string(&ReplaySessionVerdict::DivergenceDetected).unwrap(),
            r#""divergence_detected""#
        );
        assert_eq!(
            serde_json::to_string(&ReplaySessionVerdict::EmptyJournal).unwrap(),
            r#""empty_journal""#
        );
        assert_eq!(
            serde_json::to_string(&ReplaySessionVerdict::Aborted).unwrap(),
            r#""aborted""#
        );
    }

    #[test]
    fn replay_step_result_round_trips() {
        let step = ReplayStepResult {
            step_id: "rs-1".into(),
            sequence: 5,
            kind: JournalEntryKind::Tick,
            verdict: ReplayStepVerdict::Match,
            expected_payload: Some(serde_json::json!({"tick_number": 5, "outcome": "idle_tick"})),
            actual_payload: Some(serde_json::json!({"tick_number": 5, "outcome": "idle_tick"})),
            detail: String::new(),
        };
        let json = serde_json::to_string(&step).unwrap();
        let restored: ReplayStepResult = serde_json::from_str(&json).unwrap();
        assert_eq!(step, restored);
    }

    #[test]
    fn replay_session_result_round_trips() {
        let session = ReplaySessionResult {
            session_id: "rses-1".into(),
            epoch_id: "epoch-1".into(),
            entries_replayed: 20,
            entries_matched: 15,
            entries_diverged: 0,
            entries_skipped: 5,
            verdict: ReplaySessionVerdict::Success,
            steps: vec![],
            started_at: "2026-03-20T00:00:00+00:00".into(),
            completed_at: "2026-03-20T00:01:00+00:00".into(),
        };
        let json = serde_json::to_string(&session).unwrap();
        let restored: ReplaySessionResult = serde_json::from_str(&json).unwrap();
        assert_eq!(session, restored);
    }

    // -------------------------------------------------------------------
    // Lifecycle state enum tests
    // -------------------------------------------------------------------

    #[test]
    fn checkpoint_lifecycle_state_serializes() {
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::Idle).unwrap(),
            r#""idle""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::Capturing).unwrap(),
            r#""capturing""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::VerifyingCapture).unwrap(),
            r#""verifying_capture""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::Committed).unwrap(),
            r#""committed""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::Restoring).unwrap(),
            r#""restoring""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::VerifyingRestore).unwrap(),
            r#""verifying_restore""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::Verified).unwrap(),
            r#""verified""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::RollingBack).unwrap(),
            r#""rolling_back""#
        );
        assert_eq!(
            serde_json::to_string(&CheckpointLifecycleState::Failed).unwrap(),
            r#""failed""#
        );
    }

    #[test]
    fn reaction_pipeline_state_serializes() {
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Received).unwrap(),
            r#""received""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Matching).unwrap(),
            r#""matching""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::IdempotencyCheck).unwrap(),
            r#""idempotency_check""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::BackpressureCheck).unwrap(),
            r#""backpressure_check""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Gating).unwrap(),
            r#""gating""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Executed).unwrap(),
            r#""executed""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Emitted).unwrap(),
            r#""emitted""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Deferred).unwrap(),
            r#""deferred""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Rejected).unwrap(),
            r#""rejected""#
        );
        assert_eq!(
            serde_json::to_string(&ReactionPipelineState::Recorded).unwrap(),
            r#""recorded""#
        );
    }

    #[test]
    fn obligation_lifecycle_state_serializes() {
        assert_eq!(
            serde_json::to_string(&ObligationLifecycleState::Pending).unwrap(),
            r#""pending""#
        );
        assert_eq!(
            serde_json::to_string(&ObligationLifecycleState::Active).unwrap(),
            r#""active""#
        );
        assert_eq!(
            serde_json::to_string(&ObligationLifecycleState::Escalated).unwrap(),
            r#""escalated""#
        );
        assert_eq!(
            serde_json::to_string(&ObligationLifecycleState::Completed).unwrap(),
            r#""completed""#
        );
        assert_eq!(
            serde_json::to_string(&ObligationLifecycleState::Expired).unwrap(),
            r#""expired""#
        );
        assert_eq!(
            serde_json::to_string(&ObligationLifecycleState::Cancelled).unwrap(),
            r#""cancelled""#
        );
    }

    // -------------------------------------------------------------------
    // Canonical machine constructor tests
    // -------------------------------------------------------------------

    #[test]
    fn obligation_machine_v2_structure() {
        let m = obligation_machine();
        assert_eq!(m.machine_id, "obligation-lifecycle");
        assert_eq!(m.version, "2.0.0");
        assert_eq!(m.states.len(), 6);
        assert_eq!(m.terminal_states.len(), 3);
        assert_eq!(m.transitions.len(), 16);
        assert_eq!(m.initial_state, "pending");
    }

    #[test]
    fn obligation_machine_v2_transfer_self_loop() {
        let m = obligation_machine();
        // Transfer from pending → pending is legal
        assert_eq!(
            m.is_legal("pending", "pending", "transfer"),
            TransitionVerdict::Allowed
        );
        // Transfer from active → active is legal
        assert_eq!(
            m.is_legal("active", "active", "transfer"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn supervisor_machine_v2_structure() {
        let m = supervisor_machine();
        assert_eq!(m.machine_id, "supervisor-tick-lifecycle");
        assert_eq!(m.version, "2.0.0");
        assert_eq!(m.states.len(), 13);
        assert_eq!(m.terminal_states, vec!["halted"]);
        assert_eq!(m.transitions.len(), 33);
        assert_eq!(m.initial_state, "idle");
    }

    #[test]
    fn supervisor_machine_v2_normal_tick_path() {
        let m = supervisor_machine();
        assert_eq!(
            m.is_legal("idle", "polling", "tick_start"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("polling", "evaluating_obligations", "poll_complete"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal(
                "evaluating_obligations",
                "evaluating_deadlines",
                "obligations_evaluated"
            ),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("evaluating_deadlines", "waking_work", "deadlines_evaluated"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("waking_work", "running_reactions", "work_woken"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("running_reactions", "reasoning", "reactions_complete"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("reasoning", "acting", "reasoning_complete"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("acting", "idle", "tick_complete"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn supervisor_machine_v2_pause_resume() {
        let m = supervisor_machine();
        assert_eq!(
            m.is_legal("idle", "paused", "pause"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("paused", "idle", "resume"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("paused", "halted", "halt"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn supervisor_machine_v2_halted_is_terminal() {
        let m = supervisor_machine();
        assert_eq!(
            m.is_legal("halted", "idle", "resume"),
            TransitionVerdict::DeniedTerminalState
        );
    }

    #[test]
    fn supervisor_machine_v2_error_from_all_phases() {
        let m = supervisor_machine();
        let working_phases = [
            "idle",
            "polling",
            "evaluating_obligations",
            "evaluating_deadlines",
            "waking_work",
            "running_reactions",
            "reasoning",
            "acting",
            "checkpointing",
            "emitting_heartbeat",
            "paused",
            "degraded",
        ];
        for phase in &working_phases {
            assert_eq!(
                m.is_legal(phase, "degraded", "error"),
                TransitionVerdict::Allowed,
                "error from {} should be allowed",
                phase,
            );
        }
    }

    #[test]
    fn reaction_pipeline_machine_structure() {
        let m = reaction_pipeline_machine();
        assert_eq!(m.machine_id, "reaction-pipeline");
        assert_eq!(m.version, "2.0.0");
        assert_eq!(m.states.len(), 10);
        assert_eq!(m.terminal_states, vec!["recorded"]);
        assert_eq!(m.transitions.len(), 17);
    }

    #[test]
    fn reaction_pipeline_machine_emission_path() {
        let m = reaction_pipeline_machine();
        // Happy path through emission
        assert_eq!(
            m.is_legal("executed", "emitted", "emit_event"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("emitted", "recorded", "record"),
            TransitionVerdict::Allowed
        );
        // Direct record (no emission)
        assert_eq!(
            m.is_legal("executed", "recorded", "record"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn checkpoint_lifecycle_machine_structure() {
        let m = checkpoint_lifecycle_machine();
        assert_eq!(m.machine_id, "checkpoint-lifecycle");
        assert_eq!(m.version, "1.0.0");
        assert_eq!(m.states.len(), 9);
        assert_eq!(m.terminal_states, vec!["failed"]);
        assert_eq!(m.transitions.len(), 13);
    }

    #[test]
    fn checkpoint_lifecycle_capture_flow() {
        let m = checkpoint_lifecycle_machine();
        assert_eq!(
            m.is_legal("idle", "capturing", "begin_capture"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("capturing", "verifying_capture", "snapshots_complete"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("verifying_capture", "committed", "hash_verified"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("committed", "idle", "capture_finalized"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn checkpoint_lifecycle_restore_flow() {
        let m = checkpoint_lifecycle_machine();
        assert_eq!(
            m.is_legal("idle", "restoring", "begin_restore"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("restoring", "verifying_restore", "subsystems_restored"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("verifying_restore", "verified", "restore_hash_verified"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("verified", "idle", "restore_finalized"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn checkpoint_lifecycle_rollback_path() {
        let m = checkpoint_lifecycle_machine();
        assert_eq!(
            m.is_legal("verifying_restore", "rolling_back", "restore_hash_mismatch"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("restoring", "rolling_back", "restore_error"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("rolling_back", "idle", "rollback_complete"),
            TransitionVerdict::Allowed
        );
        assert_eq!(
            m.is_legal("rolling_back", "failed", "rollback_failed"),
            TransitionVerdict::Allowed
        );
    }

    #[test]
    fn checkpoint_lifecycle_failed_is_terminal() {
        let m = checkpoint_lifecycle_machine();
        assert_eq!(
            m.is_legal("failed", "idle", "retry"),
            TransitionVerdict::DeniedTerminalState
        );
    }

    #[test]
    fn all_four_machines_round_trip() {
        let machines = vec![
            obligation_machine(),
            supervisor_machine(),
            reaction_pipeline_machine(),
            checkpoint_lifecycle_machine(),
        ];
        for m in &machines {
            let json = serde_json::to_string(m).unwrap();
            let restored: StateMachineSpec = serde_json::from_str(&json).unwrap();
            assert_eq!(*m, restored, "round-trip failed for {}", m.machine_id);
        }
    }

    // ── Proof substrate tests ─────────────────────────────────────────────

    fn example_machine() -> StateMachineSpec {
        StateMachineSpec {
            machine_id: "test-machine".into(),
            name: "Test".into(),
            version: "1.0".into(),
            states: vec!["idle".into(), "running".into(), "done".into()],
            initial_state: "idle".into(),
            terminal_states: vec!["done".into()],
            transitions: vec![
                tr("idle", "running", "start", "", ""),
                tr("running", "done", "finish", "", ""),
                tr("running", "idle", "reset", "", ""),
            ],
        }
    }

    #[test]
    fn certify_legal_transition_produces_receipt() {
        let m = example_machine();
        let result = m.certify_transition(&CertifyParams {
            entity_id: "entity-1",
            from_state: "idle",
            to_state: "running",
            action: "start",
            before_state_hash: "hash-before",
            after_state_hash: "hash-after",
            guards: &[],
            actor_id: "actor-1",
            reason: "starting work",
            causal_parent: "genesis",
            timestamp: "2026-03-27T12:00:00Z",
        });
        assert!(result.is_ok());
        let capsule = result.unwrap();
        assert_eq!(capsule.receipt.from_state, "idle");
        assert_eq!(capsule.receipt.to_state, "running");
        assert_eq!(capsule.receipt.verdict, TransitionVerdict::Allowed);
        assert!(!capsule.receipt.receipt_hash.is_empty());
        assert!(!capsule.receipt.replay_token.is_empty());
        assert_eq!(capsule.audit_record.actor_id, "actor-1");
    }

    #[test]
    fn certify_illegal_transition_returns_error() {
        let m = example_machine();
        let result = m.certify_transition(&CertifyParams {
            entity_id: "entity-1",
            from_state: "idle",
            to_state: "done",
            action: "skip",
            before_state_hash: "h1",
            after_state_hash: "h2",
            guards: &[],
            actor_id: "actor",
            reason: "trying to skip",
            causal_parent: "genesis",
            timestamp: "2026-03-27T12:00:00Z",
        });
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), TransitionVerdict::DeniedIllegalEdge);
    }

    #[test]
    fn certify_terminal_state_transition_returns_error() {
        let m = example_machine();
        let result = m.certify_transition(&CertifyParams {
            entity_id: "entity-1",
            from_state: "done",
            to_state: "idle",
            action: "reset",
            before_state_hash: "h1",
            after_state_hash: "h2",
            guards: &[],
            actor_id: "actor",
            reason: "reset from done",
            causal_parent: "genesis",
            timestamp: "2026-03-27T12:00:00Z",
        });
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), TransitionVerdict::DeniedTerminalState);
    }

    /// A failed guard does NOT return Err. Instead, certify_transition
    /// emits Ok(ProofCapsule) with verdict=DeniedGuardFailed that contains
    /// the full guard list (passing AND failing). The receipt IS the
    /// proof of the denial — stripping failed verdicts would erase the
    /// audit-trail reason for the rejection.
    #[test]
    fn certify_with_failed_guard_emits_denied_receipt() {
        let m = example_machine();
        let guards = vec![
            GuardVerdict {
                guard_id: "budget".into(),
                passed: true,
                reason: "ok".into(),
            },
            GuardVerdict {
                guard_id: "auth".into(),
                passed: false,
                reason: "unauthorized".into(),
            },
        ];
        let result = m.certify_transition(&CertifyParams {
            entity_id: "entity-1",
            from_state: "idle",
            to_state: "running",
            action: "start",
            before_state_hash: "h1",
            after_state_hash: "h2",
            guards: &guards,
            actor_id: "actor",
            reason: "start with guards",
            causal_parent: "genesis",
            timestamp: "2026-03-27T12:00:00Z",
        });
        let capsule = result.expect("failed-guard transition emits a receipt, not Err");
        assert_eq!(
            capsule.receipt.verdict,
            TransitionVerdict::DeniedGuardFailed
        );
        assert_eq!(
            capsule.audit_record.verdict,
            TransitionVerdict::DeniedGuardFailed
        );
        // Full guard list preserved on receipt — both pass and fail entries.
        assert_eq!(capsule.receipt.guard_verdicts.len(), 2);
        assert_eq!(capsule.receipt.guard_verdicts[0].guard_id, "budget");
        assert!(capsule.receipt.guard_verdicts[0].passed);
        assert_eq!(capsule.receipt.guard_verdicts[1].guard_id, "auth");
        assert!(!capsule.receipt.guard_verdicts[1].passed);
        assert_eq!(capsule.receipt.guard_verdicts[1].reason, "unauthorized");
    }

    /// Cross-language contract: the Rust receipt_hash MUST equal the Python
    /// receipt_hash for the same canonical inputs. Both sides hash the same
    /// `entity:from:to:action:before:after:causal` content with SHA-256.
    /// The mirror test lives at `mcoi/tests/test_proof_hash_contract.py`.
    /// If you change the canonical-content recipe on either side, both tests
    /// must be updated in lockstep.
    #[test]
    fn receipt_hash_matches_python_sha256() {
        // SHA-256 of "contract-test-entity:idle:running:start:before-h:after-h:genesis"
        const EXPECTED: &str = "27bf13eff30cd9fd5fc334eff381e9b2349037bd0ef9dc88c2ca15d114a77fe5";
        let m = example_machine();
        let capsule = m
            .certify_transition(&CertifyParams {
                entity_id: "contract-test-entity",
                from_state: "idle",
                to_state: "running",
                action: "start",
                before_state_hash: "before-h",
                after_state_hash: "after-h",
                guards: &[],
                actor_id: "actor",
                reason: "contract test",
                causal_parent: "genesis",
                timestamp: "2026-04-27T00:00:00Z",
            })
            .unwrap();
        assert_eq!(capsule.receipt.receipt_hash, EXPECTED);
        assert_eq!(
            capsule.receipt.receipt_id,
            format!("rcpt-{}", &EXPECTED[..16])
        );
        assert_eq!(
            capsule.audit_record.audit_id,
            format!("audit-{}", &EXPECTED[..12])
        );
        // replay_token is sha256(content + ":" + timestamp)[..16] on both sides.
        // Locking it in addition to receipt_hash catches any drift in the
        // replay-token derivation that the receipt_hash alone wouldn't surface.
        assert_eq!(capsule.receipt.replay_token, "replay-4c4180b2fd61031d");
    }

    #[test]
    fn receipt_hash_is_deterministic() {
        let m = example_machine();
        let r1 = m
            .certify_transition(&CertifyParams {
                entity_id: "e1",
                from_state: "idle",
                to_state: "running",
                action: "start",
                before_state_hash: "h1",
                after_state_hash: "h2",
                guards: &[],
                actor_id: "a",
                reason: "r",
                causal_parent: "g",
                timestamp: "t",
            })
            .unwrap();
        let r2 = m
            .certify_transition(&CertifyParams {
                entity_id: "e1",
                from_state: "idle",
                to_state: "running",
                action: "start",
                before_state_hash: "h1",
                after_state_hash: "h2",
                guards: &[],
                actor_id: "a",
                reason: "r",
                causal_parent: "g",
                timestamp: "t",
            })
            .unwrap();
        assert_eq!(r1.receipt.receipt_hash, r2.receipt.receipt_hash);
    }

    #[test]
    fn receipt_serialization_round_trip() {
        let m = example_machine();
        let capsule = m
            .certify_transition(&CertifyParams {
                entity_id: "e1",
                from_state: "idle",
                to_state: "running",
                action: "start",
                before_state_hash: "h1",
                after_state_hash: "h2",
                guards: &[GuardVerdict {
                    guard_id: "g1".into(),
                    passed: true,
                    reason: "ok".into(),
                }],
                actor_id: "actor",
                reason: "reason",
                causal_parent: "parent",
                timestamp: "2026-03-27T12:00:00Z",
            })
            .unwrap();
        let json = serde_json::to_string(&capsule).unwrap();
        let restored: ProofCapsule = serde_json::from_str(&json).unwrap();
        assert_eq!(capsule, restored);
    }

    #[test]
    fn python_denied_guard_fixture_deserializes_to_rust_proof_capsule() {
        let json = include_str!(
            "../../../../../tests/fixtures/python_proof_capsule_denied_guard.json"
        );
        let restored: ProofCapsule = serde_json::from_str(json).unwrap();

        assert_eq!(
            restored.receipt.verdict,
            TransitionVerdict::DeniedGuardFailed
        );
        assert_eq!(
            restored.audit_record.verdict,
            TransitionVerdict::DeniedGuardFailed
        );
        assert_eq!(restored.receipt.guard_verdicts.len(), 2);
        assert_eq!(restored.receipt.guard_verdicts[0].guard_id, "budget");
        assert!(restored.receipt.guard_verdicts[0].passed);
        assert_eq!(restored.receipt.guard_verdicts[1].guard_id, "auth");
        assert!(!restored.receipt.guard_verdicts[1].passed);
        assert_eq!(restored.receipt.guard_verdicts[1].reason, "unauthorized");
        assert_eq!(
            restored.receipt.receipt_hash,
            "9edcb9a064faccb74122fd9612deecad6fb2868df2d90aaf7f2a51f283097ea1"
        );
        assert_eq!(restored.receipt.replay_token, "replay-0506f724eeee49e2");
        assert_eq!(restored.lineage_depth, 0);
    }

    #[test]
    fn causal_lineage_serialization() {
        let lineage = CausalLineage {
            lineage_id: "lin-1".into(),
            entity_id: "e1".into(),
            receipt_chain: vec!["rcpt-a".into(), "rcpt-b".into()],
            root_receipt_id: "rcpt-a".into(),
            current_state: "running".into(),
            depth: 2,
        };
        let json = serde_json::to_string(&lineage).unwrap();
        let restored: CausalLineage = serde_json::from_str(&json).unwrap();
        assert_eq!(lineage, restored);
    }
}
