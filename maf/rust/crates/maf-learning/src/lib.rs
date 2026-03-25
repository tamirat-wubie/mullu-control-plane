//! Decision learning, provider routing, and meta-reasoning contracts.
//!
//! Mirrors the Python MCOI contracts in:
//! - `mcoi_runtime/contracts/decision_learning.py`
//! - `mcoi_runtime/contracts/provider_routing.py`
//! - `mcoi_runtime/contracts/meta_reasoning.py`
//!
//! Invariants:
//! - Learning is bounded: weight changes are small per cycle.
//! - Learning is auditable: every change produces a record.
//! - No auto-execution: learning records are advisory.
//! - Routing decisions are explainable and auditable.
//! - Meta-reasoning degrades gracefully under uncertainty.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};

// ===========================================================================
// Decision Learning
// ===========================================================================

pub mod decision_learning {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum OutcomeQuality {
        Success,
        PartialSuccess,
        Failure,
        Unknown,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum AdjustmentType {
        WeightIncrease,
        WeightDecrease,
        ConfidenceBoost,
        ConfidencePenalty,
        PreferenceUpdate,
        Calibration,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct DecisionOutcomeRecord {
        pub outcome_id: String,
        pub comparison_id: String,
        pub chosen_option_id: String,
        pub quality: OutcomeQuality,
        pub actual_cost: f64,
        pub actual_duration_seconds: f64,
        pub success_observed: bool,
        pub notes: String,
        pub recorded_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct PreferenceSignal {
        pub signal_id: String,
        pub context_type: String,
        pub context_id: String,
        pub factor_kind: String,
        pub direction: String,
        pub magnitude: f64,
        pub reason: String,
        pub observed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct TradeoffOutcome {
        pub outcome_id: String,
        pub tradeoff_id: String,
        pub chosen_option_id: String,
        pub quality: OutcomeQuality,
        pub regret_score: f64,
        pub alternative_would_have_been_better: bool,
        pub explanation: String,
        pub assessed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct DecisionAdjustment {
        pub adjustment_id: String,
        pub adjustment_type: AdjustmentType,
        pub target_factor_kind: String,
        pub old_value: f64,
        pub new_value: f64,
        pub delta: f64,
        pub reason: String,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct UtilityLearningRecord {
        pub record_id: String,
        pub comparison_id: String,
        pub outcome: DecisionOutcomeRecord,
        pub signals: Vec<PreferenceSignal>,
        pub adjustments: Vec<DecisionAdjustment>,
        pub learned_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct ProviderPreference {
        pub preference_id: String,
        pub provider_id: String,
        pub context_type: String,
        pub score: f64,
        pub sample_count: u64,
        pub last_updated: String,
    }
}

// ===========================================================================
// Provider Routing
// ===========================================================================

pub mod provider_routing {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum RoutingStrategy {
        Cheapest,
        MostReliable,
        Balanced,
        Learned,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct RoutingConstraints {
        pub constraints_id: String,
        pub max_cost_per_invocation: f64,
        pub min_provider_health_score: f64,
        pub min_preference_score: f64,
        pub min_sample_count: u64,
        pub strategy: RoutingStrategy,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct ProviderCandidate {
        pub candidate_id: String,
        pub provider_id: String,
        pub context_type: String,
        pub estimated_cost: f64,
        pub health_score: f64,
        pub preference_score: f64,
        pub composite_score: f64,
        pub rank: u64,
        pub scored_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct RoutingDecision {
        pub decision_id: String,
        pub constraints_id: String,
        pub candidates: Vec<ProviderCandidate>,
        pub selected_provider_id: String,
        pub selected_cost: f64,
        pub rationale: String,
        pub decided_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct RoutingOutcome {
        pub outcome_id: String,
        pub decision_id: String,
        pub provider_id: String,
        pub actual_cost: f64,
        pub success: bool,
        pub recorded_at: String,
    }
}

// ===========================================================================
// Meta-Reasoning
// ===========================================================================

pub mod meta_reasoning {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum HealthStatus {
        Healthy,
        Degraded,
        Unavailable,
        Unknown,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum EscalationSeverity {
        Low,
        Medium,
        High,
        Critical,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum UncertaintySource {
        MissingEvidence,
        LowConfidence,
        ContradictedState,
        IncompleteObservation,
        UnverifiedAssumption,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum ReplanReason {
        ConfidenceTooLow,
        AmbiguityTooHigh,
        ProviderVolatility,
        SlaRisk,
        LearningUnreliable,
        SubsystemDegraded,
        MultipleFailures,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct CapabilityConfidence {
        pub capability_id: String,
        pub success_rate: f64,
        pub verification_pass_rate: f64,
        pub timeout_rate: f64,
        pub error_rate: f64,
        pub sample_count: u64,
        pub assessed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct UncertaintyReport {
        pub report_id: String,
        pub subject: String,
        pub source: UncertaintySource,
        pub description: String,
        pub affected_ids: Vec<String>,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct DegradedModeRecord {
        pub record_id: String,
        pub capability_id: String,
        pub reason: String,
        pub confidence_at_entry: f64,
        pub threshold: f64,
        pub entered_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub exited_at: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct EscalationRecommendation {
        pub recommendation_id: String,
        pub reason: String,
        pub severity: EscalationSeverity,
        pub affected_ids: Vec<String>,
        pub suggested_action: String,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct SubsystemHealth {
        pub subsystem: String,
        pub status: HealthStatus,
        pub details: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct SelfHealthSnapshot {
        pub snapshot_id: String,
        pub subsystems: Vec<SubsystemHealth>,
        pub assessed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct ConfidenceEnvelope {
        pub assessment_id: String,
        pub subject: String,
        pub point_estimate: f64,
        pub lower_bound: f64,
        pub upper_bound: f64,
        pub sample_count: u64,
        pub assessed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct DecisionReliability {
        pub reliability_id: String,
        pub decision_context: String,
        pub confidence_envelope: ConfidenceEnvelope,
        pub uncertainty_factors: Vec<String>,
        pub dominant_risk: String,
        pub recommendation: String,
        pub assessed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct ReplanRecommendation {
        pub recommendation_id: String,
        pub reason: ReplanReason,
        pub description: String,
        pub affected_entity_id: String,
        pub severity: EscalationSeverity,
        #[serde(default)]
        pub confidence_at_assessment: f64,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct MetaReasoningSnapshot {
        pub snapshot_id: String,
        pub captured_at: String,
        pub health: SelfHealthSnapshot,
        pub degraded_capabilities: Vec<DegradedModeRecord>,
        pub active_uncertainties: Vec<UncertaintyReport>,
        pub decision_reliabilities: Vec<DecisionReliability>,
        pub replan_recommendations: Vec<ReplanRecommendation>,
        pub escalation_recommendations: Vec<EscalationRecommendation>,
        pub overall_confidence: f64,
    }
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // --- Decision Learning ---

    #[test]
    fn outcome_quality_serializes_to_snake_case() {
        let json =
            serde_json::to_string(&decision_learning::OutcomeQuality::PartialSuccess).unwrap();
        assert_eq!(json, r#""partial_success""#);
    }

    #[test]
    fn adjustment_type_serializes_to_snake_case() {
        let json =
            serde_json::to_string(&decision_learning::AdjustmentType::ConfidenceBoost).unwrap();
        assert_eq!(json, r#""confidence_boost""#);
    }

    #[test]
    fn decision_outcome_record_round_trips() {
        let r = decision_learning::DecisionOutcomeRecord {
            outcome_id: "o-1".into(),
            comparison_id: "c-1".into(),
            chosen_option_id: "opt-1".into(),
            quality: decision_learning::OutcomeQuality::Success,
            actual_cost: 5.0,
            actual_duration_seconds: 30.0,
            success_observed: true,
            notes: "all good".into(),
            recorded_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&r).unwrap();
        let back: decision_learning::DecisionOutcomeRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(r, back);
    }

    #[test]
    fn tradeoff_outcome_round_trips() {
        let to = decision_learning::TradeoffOutcome {
            outcome_id: "to-1".into(),
            tradeoff_id: "t-1".into(),
            chosen_option_id: "opt-a".into(),
            quality: decision_learning::OutcomeQuality::Failure,
            regret_score: 1.0,
            alternative_would_have_been_better: true,
            explanation: "should have chosen B".into(),
            assessed_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&to).unwrap();
        let back: decision_learning::TradeoffOutcome = serde_json::from_str(&json).unwrap();
        assert_eq!(to, back);
    }

    // --- Provider Routing ---

    #[test]
    fn routing_strategy_serializes_to_snake_case() {
        let json = serde_json::to_string(&provider_routing::RoutingStrategy::MostReliable).unwrap();
        assert_eq!(json, r#""most_reliable""#);
    }

    #[test]
    fn routing_decision_round_trips() {
        let rd = provider_routing::RoutingDecision {
            decision_id: "rd-1".into(),
            constraints_id: "c-1".into(),
            candidates: vec![provider_routing::ProviderCandidate {
                candidate_id: "pc-1".into(),
                provider_id: "p-1".into(),
                context_type: "deploy".into(),
                estimated_cost: 2.0,
                health_score: 0.95,
                preference_score: 0.8,
                composite_score: 0.87,
                rank: 1,
                scored_at: "2025-01-01T00:00:00+00:00".into(),
            }],
            selected_provider_id: "p-1".into(),
            selected_cost: 2.0,
            rationale: "highest composite score".into(),
            decided_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&rd).unwrap();
        let back: provider_routing::RoutingDecision = serde_json::from_str(&json).unwrap();
        assert_eq!(rd, back);
    }

    // --- Meta-Reasoning ---

    #[test]
    fn health_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&meta_reasoning::HealthStatus::Degraded).unwrap();
        assert_eq!(json, r#""degraded""#);
    }

    #[test]
    fn uncertainty_source_serializes_to_snake_case() {
        let json =
            serde_json::to_string(&meta_reasoning::UncertaintySource::ContradictedState).unwrap();
        assert_eq!(json, r#""contradicted_state""#);
    }

    #[test]
    fn replan_reason_serializes_to_snake_case() {
        let json = serde_json::to_string(&meta_reasoning::ReplanReason::ConfidenceTooLow).unwrap();
        assert_eq!(json, r#""confidence_too_low""#);
    }

    #[test]
    fn capability_confidence_round_trips() {
        let cc = meta_reasoning::CapabilityConfidence {
            capability_id: "cap-1".into(),
            success_rate: 0.92,
            verification_pass_rate: 0.88,
            timeout_rate: 0.02,
            error_rate: 0.05,
            sample_count: 100,
            assessed_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&cc).unwrap();
        let back: meta_reasoning::CapabilityConfidence = serde_json::from_str(&json).unwrap();
        assert_eq!(cc, back);
    }

    #[test]
    fn subsystem_health_round_trips() {
        let sh = meta_reasoning::SubsystemHealth {
            subsystem: "event_spine".into(),
            status: meta_reasoning::HealthStatus::Healthy,
            details: "all clear".into(),
        };
        let json = serde_json::to_string(&sh).unwrap();
        let back: meta_reasoning::SubsystemHealth = serde_json::from_str(&json).unwrap();
        assert_eq!(sh, back);
    }

    #[test]
    fn escalation_recommendation_round_trips() {
        let er = meta_reasoning::EscalationRecommendation {
            recommendation_id: "esc-1".into(),
            reason: "deadline approaching".into(),
            severity: meta_reasoning::EscalationSeverity::High,
            affected_ids: vec!["obl-1".into()],
            suggested_action: "notify team lead".into(),
            created_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&er).unwrap();
        let back: meta_reasoning::EscalationRecommendation = serde_json::from_str(&json).unwrap();
        assert_eq!(er, back);
    }

    // --- Cross-format compatibility ---

    #[test]
    fn outcome_quality_deserializes_from_python_format() {
        let oq: decision_learning::OutcomeQuality =
            serde_json::from_str(r#""partial_success""#).unwrap();
        assert_eq!(oq, decision_learning::OutcomeQuality::PartialSuccess);
    }

    #[test]
    fn routing_strategy_deserializes_from_python_format() {
        let rs: provider_routing::RoutingStrategy =
            serde_json::from_str(r#""most_reliable""#).unwrap();
        assert_eq!(rs, provider_routing::RoutingStrategy::MostReliable);
    }
}
