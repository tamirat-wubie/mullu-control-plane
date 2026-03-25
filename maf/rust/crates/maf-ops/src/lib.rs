//! Operational reasoning contracts: simulation, utility, benchmark, and
//! operational graph.
//!
//! Mirrors the Python MCOI contracts in:
//! - `mcoi_runtime/contracts/simulation.py`
//! - `mcoi_runtime/contracts/utility.py`
//! - `mcoi_runtime/contracts/benchmark.py`
//! - `mcoi_runtime/contracts/graph.py`
//!
//! Invariants:
//! - Simulation outcomes are immutable records.
//! - Utility scores are bounded [0.0, 1.0].
//! - Benchmark results are deterministic and auditable.
//! - Graph nodes/edges are typed and traceable.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ===========================================================================
// Simulation
// ===========================================================================

pub mod simulation {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum SimulationStatus {
        Pending,
        Running,
        Completed,
        Failed,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum RiskLevel {
        Minimal,
        Low,
        Moderate,
        High,
        Critical,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum VerdictType {
        Proceed,
        ProceedWithCaution,
        ApprovalRequired,
        Escalate,
        Abort,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct SimulationOption {
        pub option_id: String,
        pub label: String,
        pub risk_level: RiskLevel,
        pub estimated_cost: f64,
        pub estimated_duration_seconds: f64,
        pub success_probability: f64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct SimulationRequest {
        pub request_id: String,
        pub context_type: String,
        pub context_id: String,
        pub description: String,
        pub options: Vec<SimulationOption>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct ConsequenceEstimate {
        pub estimate_id: String,
        pub option_id: String,
        pub affected_node_ids: Vec<String>,
        pub new_edges_count: u64,
        pub new_obligations_count: u64,
        pub blocked_nodes_count: u64,
        pub unblocked_nodes_count: u64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct RiskEstimate {
        pub estimate_id: String,
        pub option_id: String,
        pub risk_level: RiskLevel,
        pub incident_probability: f64,
        pub review_burden: u64,
        pub provider_exposure_count: u64,
        pub verification_difficulty: String,
        pub rationale: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct ObligationProjection {
        pub projection_id: String,
        pub option_id: String,
        pub new_obligations: Vec<String>,
        pub fulfilled_obligations: Vec<String>,
        pub deadline_pressure: u64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct SimulationOutcome {
        pub outcome_id: String,
        pub option_id: String,
        pub consequence: ConsequenceEstimate,
        pub risk: RiskEstimate,
        pub obligation_projection: ObligationProjection,
        pub simulated_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct SimulationComparison {
        pub comparison_id: String,
        pub request_id: String,
        pub ranked_option_ids: Vec<String>,
        pub scores: HashMap<String, f64>,
        pub top_risk_level: RiskLevel,
        pub review_burden: f64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct SimulationVerdict {
        pub verdict_id: String,
        pub comparison_id: String,
        pub verdict_type: VerdictType,
        pub recommended_option_id: String,
        pub confidence: f64,
        pub reasons: Vec<String>,
    }
}

// ===========================================================================
// Utility
// ===========================================================================

pub mod utility {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum ResourceType {
        Compute,
        Memory,
        Network,
        Storage,
        ApiCalls,
        Time,
        Budget,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum DecisionFactorKind {
        Risk,
        Obligation,
        Confidence,
        ProviderHealth,
        DeadlinePressure,
        Cost,
        Time,
        Custom,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum TradeoffDirection {
        FavorSpeed,
        FavorCost,
        FavorSafety,
        Balanced,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct ResourceBudget {
        pub resource_id: String,
        pub resource_type: ResourceType,
        pub total: f64,
        pub consumed: f64,
        pub reserved: f64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct DecisionFactor {
        pub factor_id: String,
        pub kind: DecisionFactorKind,
        pub weight: f64,
        pub value: f64,
        pub label: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct UtilityProfile {
        pub profile_id: String,
        pub context_type: String,
        pub context_id: String,
        pub factors: Vec<DecisionFactor>,
        pub tradeoff_direction: TradeoffDirection,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct OptionUtility {
        pub option_id: String,
        pub raw_score: f64,
        pub weighted_score: f64,
        pub factor_contributions: HashMap<String, f64>,
        pub rank: u64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct DecisionComparison {
        pub comparison_id: String,
        pub profile_id: String,
        pub option_utilities: Vec<OptionUtility>,
        pub best_option_id: String,
        pub spread: f64,
        pub decided_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct TradeoffRecord {
        pub tradeoff_id: String,
        pub comparison_id: String,
        pub chosen_option_id: String,
        pub rejected_option_ids: Vec<String>,
        pub tradeoff_direction: TradeoffDirection,
        pub rationale: String,
        pub recorded_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct DecisionPolicy {
        pub policy_id: String,
        pub name: String,
        pub min_confidence: f64,
        pub max_risk_tolerance: f64,
        pub max_cost: f64,
        pub deadline_weight: f64,
        pub require_human_above_risk: f64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct UtilityVerdict {
        pub verdict_id: String,
        pub comparison_id: String,
        pub policy_id: String,
        pub approved: bool,
        pub recommended_option_id: String,
        pub confidence: f64,
        pub reasons: Vec<String>,
        pub decided_at: String,
    }
}

// ===========================================================================
// Benchmark
// ===========================================================================

pub mod benchmark {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum BenchmarkCategory {
        Governance,
        Simulation,
        Utility,
        Reaction,
        JobRuntime,
        TeamFunction,
        ProviderRouting,
        RecoveryPlaybook,
        WorldState,
        MetaReasoning,
        Obligation,
        EventSpine,
        CrossPlane,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum BenchmarkOutcome {
        Pass,
        Fail,
        Error,
        Skip,
        Timeout,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum AdversarialSeverity {
        Benign,
        Moderate,
        Aggressive,
        Catastrophic,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum AdversarialCategory {
        ConflictingPolicies,
        MalformedInput,
        DeceptivePayload,
        AmbiguousApproval,
        StaleWorldState,
        HighEventChurn,
        OverloadedWorkers,
        ProviderVolatility,
        SimulationUtilityDisagreement,
        ReplayIdempotency,
        ResourceExhaustion,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum MetricKind {
        Accuracy,
        Correctness,
        Latency,
        Throughput,
        RecoveryRate,
        FalsePositiveRate,
        FalseNegativeRate,
        Coverage,
        Stability,
        Custom,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum RegressionDirection {
        Improved,
        Degraded,
        Stable,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum ScorecardStatus {
        Healthy,
        Degraded,
        Failing,
        Unknown,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct BenchmarkScenario {
        pub scenario_id: String,
        pub name: String,
        pub description: String,
        pub category: BenchmarkCategory,
        pub inputs: HashMap<String, serde_json::Value>,
        pub expected_outcome: BenchmarkOutcome,
        #[serde(default)]
        pub expected_properties: HashMap<String, serde_json::Value>,
        #[serde(default)]
        pub tags: Vec<String>,
        #[serde(default = "default_timeout")]
        pub timeout_ms: u64,
    }

    fn default_timeout() -> u64 {
        30000
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct BenchmarkSuite {
        pub suite_id: String,
        pub name: String,
        pub category: BenchmarkCategory,
        pub scenarios: Vec<BenchmarkScenario>,
        pub version: String,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct BenchmarkMetric {
        pub metric_id: String,
        pub kind: MetricKind,
        pub name: String,
        pub value: f64,
        pub threshold: f64,
        pub passed: bool,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct BenchmarkResult {
        pub result_id: String,
        pub scenario_id: String,
        pub outcome: BenchmarkOutcome,
        pub metrics: Vec<BenchmarkMetric>,
        pub actual_properties: HashMap<String, serde_json::Value>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub error_message: Option<String>,
        #[serde(default)]
        pub duration_ms: u64,
        #[serde(default, skip_serializing_if = "String::is_empty")]
        pub executed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct BenchmarkRun {
        pub run_id: String,
        pub suite_id: String,
        pub results: Vec<BenchmarkResult>,
        pub started_at: String,
        pub finished_at: String,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct AdversarialCase {
        pub case_id: String,
        pub name: String,
        pub description: String,
        pub category: AdversarialCategory,
        pub severity: AdversarialSeverity,
        pub target_subsystem: BenchmarkCategory,
        pub attack_vector: String,
        pub inputs: HashMap<String, serde_json::Value>,
        pub expected_behavior: String,
        #[serde(default)]
        pub tags: Vec<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct RegressionRecord {
        pub regression_id: String,
        pub metric_name: String,
        pub category: BenchmarkCategory,
        pub baseline_value: f64,
        pub current_value: f64,
        pub direction: RegressionDirection,
        pub delta: f64,
        pub baseline_run_id: String,
        pub current_run_id: String,
        pub detected_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct CapabilityScorecard {
        pub scorecard_id: String,
        pub category: BenchmarkCategory,
        pub status: ScorecardStatus,
        pub pass_rate: f64,
        pub metric_count: u64,
        pub metrics_passing: u64,
        pub adversarial_pass_rate: f64,
        pub regressions: Vec<RegressionRecord>,
        pub confidence_trend: String,
        pub assessed_at: String,
    }
}

// ===========================================================================
// Operational Graph
// ===========================================================================

pub mod graph {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum NodeType {
        Goal,
        Workflow,
        Skill,
        Job,
        Incident,
        Approval,
        Review,
        Runbook,
        ProviderAction,
        Verification,
        CommunicationThread,
        Document,
        Function,
        Person,
        Team,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum EdgeType {
        CausedBy,
        DependsOn,
        Owns,
        ObligatedTo,
        DecidedBy,
        BlockedBy,
        EscalatedTo,
        Produced,
        VerifiedBy,
        AssignedTo,
        CommunicatesVia,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct OperationalNode {
        pub node_id: String,
        pub node_type: NodeType,
        pub label: String,
        pub created_at: String,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct OperationalEdge {
        pub edge_id: String,
        pub edge_type: EdgeType,
        pub source_node_id: String,
        pub target_node_id: String,
        pub label: String,
        pub created_at: String,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct EvidenceLink {
        pub edge_id: String,
        pub source_node_id: String,
        pub target_node_id: String,
        pub evidence_type: String,
        pub confidence: f64,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct DecisionLink {
        pub edge_id: String,
        pub source_node_id: String,
        pub target_node_id: String,
        pub decision: String,
        pub decided_by_id: String,
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct ObligationLink {
        pub edge_id: String,
        pub source_node_id: String,
        pub target_node_id: String,
        pub obligation: String,
        pub fulfilled: bool,
        pub created_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub deadline: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct StateDelta {
        pub delta_id: String,
        pub node_id: String,
        pub field_name: String,
        pub old_value: String,
        pub new_value: String,
        pub changed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct CausalPath {
        pub path_id: String,
        pub node_ids: Vec<String>,
        pub edge_ids: Vec<String>,
        pub description: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct GraphSnapshot {
        pub snapshot_id: String,
        pub node_count: u64,
        pub edge_count: u64,
        pub captured_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct GraphQueryResult {
        pub query_id: String,
        pub matched_nodes: Vec<OperationalNode>,
        pub matched_edges: Vec<OperationalEdge>,
        pub executed_at: String,
    }
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // --- Simulation ---

    #[test]
    fn simulation_risk_level_serializes_to_snake_case() {
        let json = serde_json::to_string(&simulation::RiskLevel::Critical).unwrap();
        assert_eq!(json, r#""critical""#);
    }

    #[test]
    fn simulation_verdict_type_serializes_to_snake_case() {
        let json = serde_json::to_string(&simulation::VerdictType::ProceedWithCaution).unwrap();
        assert_eq!(json, r#""proceed_with_caution""#);
    }

    #[test]
    fn simulation_option_round_trips() {
        let opt = simulation::SimulationOption {
            option_id: "o-1".into(),
            label: "Deploy v2".into(),
            risk_level: simulation::RiskLevel::Moderate,
            estimated_cost: 10.5,
            estimated_duration_seconds: 120.0,
            success_probability: 0.85,
        };
        let json = serde_json::to_string(&opt).unwrap();
        let back: simulation::SimulationOption = serde_json::from_str(&json).unwrap();
        assert_eq!(opt, back);
    }

    #[test]
    fn simulation_verdict_round_trips() {
        let v = simulation::SimulationVerdict {
            verdict_id: "v-1".into(),
            comparison_id: "c-1".into(),
            verdict_type: simulation::VerdictType::Proceed,
            recommended_option_id: "o-1".into(),
            confidence: 0.9,
            reasons: vec!["low risk".into()],
        };
        let json = serde_json::to_string(&v).unwrap();
        let back: simulation::SimulationVerdict = serde_json::from_str(&json).unwrap();
        assert_eq!(v, back);
    }

    // --- Utility ---

    #[test]
    fn utility_resource_type_serializes_to_snake_case() {
        let json = serde_json::to_string(&utility::ResourceType::ApiCalls).unwrap();
        assert_eq!(json, r#""api_calls""#);
    }

    #[test]
    fn utility_tradeoff_direction_serializes_to_snake_case() {
        let json = serde_json::to_string(&utility::TradeoffDirection::FavorSafety).unwrap();
        assert_eq!(json, r#""favor_safety""#);
    }

    #[test]
    fn utility_decision_factor_round_trips() {
        let f = utility::DecisionFactor {
            factor_id: "f-1".into(),
            kind: utility::DecisionFactorKind::Risk,
            weight: 0.8,
            value: 0.3,
            label: "risk factor".into(),
        };
        let json = serde_json::to_string(&f).unwrap();
        let back: utility::DecisionFactor = serde_json::from_str(&json).unwrap();
        assert_eq!(f, back);
    }

    #[test]
    fn utility_verdict_round_trips() {
        let v = utility::UtilityVerdict {
            verdict_id: "v-1".into(),
            comparison_id: "c-1".into(),
            policy_id: "p-1".into(),
            approved: true,
            recommended_option_id: "o-1".into(),
            confidence: 0.95,
            reasons: vec!["within budget".into()],
            decided_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&v).unwrap();
        let back: utility::UtilityVerdict = serde_json::from_str(&json).unwrap();
        assert_eq!(v, back);
    }

    // --- Benchmark ---

    #[test]
    fn benchmark_category_serializes_to_snake_case() {
        let json = serde_json::to_string(&benchmark::BenchmarkCategory::MetaReasoning).unwrap();
        assert_eq!(json, r#""meta_reasoning""#);
    }

    #[test]
    fn benchmark_adversarial_category_serializes_to_snake_case() {
        let json =
            serde_json::to_string(&benchmark::AdversarialCategory::SimulationUtilityDisagreement)
                .unwrap();
        assert_eq!(json, r#""simulation_utility_disagreement""#);
    }

    #[test]
    fn benchmark_scorecard_round_trips() {
        let sc = benchmark::CapabilityScorecard {
            scorecard_id: "sc-1".into(),
            category: benchmark::BenchmarkCategory::Governance,
            status: benchmark::ScorecardStatus::Healthy,
            pass_rate: 0.95,
            metric_count: 10,
            metrics_passing: 9,
            adversarial_pass_rate: 0.85,
            regressions: vec![],
            confidence_trend: "stable".into(),
            assessed_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&sc).unwrap();
        let back: benchmark::CapabilityScorecard = serde_json::from_str(&json).unwrap();
        assert_eq!(sc, back);
    }

    // --- Graph ---

    #[test]
    fn graph_node_type_serializes_to_snake_case() {
        let json = serde_json::to_string(&graph::NodeType::CommunicationThread).unwrap();
        assert_eq!(json, r#""communication_thread""#);
    }

    #[test]
    fn graph_edge_type_serializes_to_snake_case() {
        let json = serde_json::to_string(&graph::EdgeType::ObligatedTo).unwrap();
        assert_eq!(json, r#""obligated_to""#);
    }

    #[test]
    fn graph_node_round_trips() {
        let node = graph::OperationalNode {
            node_id: "n-1".into(),
            node_type: graph::NodeType::Job,
            label: "Deploy service".into(),
            created_at: "2025-01-01T00:00:00+00:00".into(),
            metadata: HashMap::new(),
        };
        let json = serde_json::to_string(&node).unwrap();
        let back: graph::OperationalNode = serde_json::from_str(&json).unwrap();
        assert_eq!(node, back);
    }

    #[test]
    fn graph_causal_path_round_trips() {
        let path = graph::CausalPath {
            path_id: "p-1".into(),
            node_ids: vec!["n-1".into(), "n-2".into(), "n-3".into()],
            edge_ids: vec!["e-1".into(), "e-2".into()],
            description: "incident causal chain".into(),
        };
        let json = serde_json::to_string(&path).unwrap();
        let back: graph::CausalPath = serde_json::from_str(&json).unwrap();
        assert_eq!(path, back);
    }

    // --- Cross-format compatibility ---

    #[test]
    fn risk_level_deserializes_from_python_format() {
        let rl: simulation::RiskLevel = serde_json::from_str(r#""critical""#).unwrap();
        assert_eq!(rl, simulation::RiskLevel::Critical);
    }

    #[test]
    fn benchmark_outcome_deserializes_from_python_format() {
        let bo: benchmark::BenchmarkOutcome = serde_json::from_str(r#""timeout""#).unwrap();
        assert_eq!(bo, benchmark::BenchmarkOutcome::Timeout);
    }
}
