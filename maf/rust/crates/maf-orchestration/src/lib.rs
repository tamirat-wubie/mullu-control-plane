//! Orchestration contracts: jobs, workflows, goals, teams/functions, and roles.
//!
//! Mirrors the Python MCOI contracts in:
//! - `mcoi_runtime/contracts/job.py`
//! - `mcoi_runtime/contracts/workflow.py`
//! - `mcoi_runtime/contracts/goal.py`
//! - `mcoi_runtime/contracts/function.py`
//! - `mcoi_runtime/contracts/roles.py`
//!
//! Invariants:
//! - Jobs have explicit lifecycle states with no silent transitions.
//! - Workflows are DAGs of typed stages with bindings.
//! - Goals decompose into sub-goals with dependency tracking.
//! - Functions bind policy, SLA, queue, and autonomy configuration.
//! - Worker capacity never reports negative available slots.
//! - No handoff without source and destination worker IDs.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ===========================================================================
// Jobs
// ===========================================================================

pub mod job {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum JobStatus {
        Created,
        Queued,
        Assigned,
        InProgress,
        Waiting,
        Paused,
        Completed,
        Failed,
        Cancelled,
        Archived,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum JobPriority {
        Critical,
        High,
        Normal,
        Low,
        Background,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum PauseReason {
        AwaitingApproval,
        AwaitingResponse,
        AwaitingReview,
        BlockedDependency,
        OperatorHold,
        SystemError,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum SlaStatus {
        OnTrack,
        AtRisk,
        Breached,
        NotApplicable,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct JobDescriptor {
        pub job_id: String,
        pub name: String,
        pub description: String,
        pub priority: JobPriority,
        pub created_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub goal_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub workflow_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub deadline: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub sla_target_minutes: Option<u64>,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkQueueEntry {
        pub entry_id: String,
        pub job_id: String,
        pub priority: JobPriority,
        pub enqueued_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub assigned_to_person_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub assigned_to_team_id: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct AssignmentRecord {
        pub assignment_id: String,
        pub job_id: String,
        pub assigned_to_id: String,
        pub assigned_by_id: String,
        pub assigned_at: String,
        pub reason: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct JobState {
        pub job_id: String,
        pub status: JobStatus,
        pub sla_status: SlaStatus,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub current_assignment_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub pause_reason: Option<PauseReason>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub thread_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub goal_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub workflow_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub started_at: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub updated_at: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct FollowUpRecord {
        pub follow_up_id: String,
        pub job_id: String,
        pub reason: String,
        pub scheduled_at: String,
        pub resolved: bool,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub executed_at: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct DeadlineRecord {
        pub job_id: String,
        pub deadline: String,
        pub sla_status: SlaStatus,
        pub evaluated_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub sla_target_minutes: Option<u64>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct JobExecutionRecord {
        pub job_id: String,
        pub execution_id: String,
        pub status: JobStatus,
        pub started_at: String,
        pub outcome_summary: String,
        #[serde(default)]
        pub errors: Vec<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub completed_at: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct JobPauseRecord {
        pub job_id: String,
        pub paused_at: String,
        pub reason: PauseReason,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub resumed_at: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct JobResumeRecord {
        pub job_id: String,
        pub resumed_at: String,
        pub resumed_by_id: String,
        pub reason: String,
    }
}

// ===========================================================================
// Workflows
// ===========================================================================

pub mod workflow {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum WorkflowStatus {
        Draft,
        Validated,
        Running,
        Completed,
        Failed,
        Suspended,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum StageType {
        SkillExecution,
        ApprovalGate,
        Observation,
        Communication,
        WaitForEvent,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum StageStatus {
        Pending,
        Running,
        Completed,
        Failed,
        Skipped,
        Blocked,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum TransitionType {
        Sequential,
        Conditional,
        OnFailure,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkflowStage {
        pub stage_id: String,
        pub stage_type: StageType,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub skill_id: Option<String>,
        pub description: String,
        #[serde(default)]
        pub predecessors: Vec<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub timeout_seconds: Option<u64>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkflowBinding {
        pub binding_id: String,
        pub source_stage_id: String,
        pub source_output_key: String,
        pub target_stage_id: String,
        pub target_input_key: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkflowDescriptor {
        pub workflow_id: String,
        pub name: String,
        pub description: String,
        pub stages: Vec<WorkflowStage>,
        pub bindings: Vec<WorkflowBinding>,
        #[serde(default, skip_serializing_if = "String::is_empty")]
        pub created_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkflowTransition {
        pub from_stage_id: String,
        pub to_stage_id: String,
        pub transition_type: TransitionType,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub condition: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct StageExecutionResult {
        pub stage_id: String,
        pub status: StageStatus,
        pub output: HashMap<String, serde_json::Value>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub error: Option<serde_json::Value>,
        #[serde(default, skip_serializing_if = "String::is_empty")]
        pub started_at: String,
        #[serde(default, skip_serializing_if = "String::is_empty")]
        pub completed_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct WorkflowExecutionRecord {
        pub workflow_id: String,
        pub execution_id: String,
        pub status: WorkflowStatus,
        pub stage_results: Vec<StageExecutionResult>,
        pub started_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub completed_at: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkflowVerificationRecord {
        pub execution_id: String,
        pub verified: bool,
        pub mismatch_reasons: Vec<String>,
        pub verified_at: String,
    }
}

// ===========================================================================
// Goals
// ===========================================================================

pub mod goal {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum GoalStatus {
        Proposed,
        Accepted,
        Planning,
        Executing,
        Completed,
        Failed,
        Replanning,
        Archived,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum GoalPriority {
        Critical,
        High,
        Normal,
        Low,
        Background,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum SubGoalStatus {
        Pending,
        Executing,
        Completed,
        Failed,
        Skipped,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct GoalDescriptor {
        pub goal_id: String,
        pub description: String,
        pub priority: GoalPriority,
        pub created_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub deadline: Option<String>,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct GoalDependency {
        pub goal_id: String,
        pub depends_on_goal_id: String,
        pub dependency_type: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct SubGoal {
        pub sub_goal_id: String,
        pub goal_id: String,
        pub description: String,
        pub status: SubGoalStatus,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub skill_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub workflow_id: Option<String>,
        #[serde(default)]
        pub predecessors: Vec<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct GoalPlan {
        pub plan_id: String,
        pub goal_id: String,
        pub sub_goals: Vec<SubGoal>,
        pub created_at: String,
        pub version: u64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct GoalExecutionState {
        pub goal_id: String,
        pub status: GoalStatus,
        pub updated_at: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub current_plan_id: Option<String>,
        #[serde(default)]
        pub completed_sub_goals: Vec<String>,
        #[serde(default)]
        pub failed_sub_goals: Vec<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct GoalReplanRecord {
        pub goal_id: String,
        pub previous_plan_id: String,
        pub new_plan_id: String,
        pub reason: String,
        pub replanned_at: String,
    }
}

// ===========================================================================
// Functions (Service Functions)
// ===========================================================================

pub mod function {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum FunctionStatus {
        Draft,
        Active,
        Paused,
        Retired,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum FunctionType {
        IncidentResponse,
        DeploymentReview,
        DocumentIntake,
        ApprovalDesk,
        CodeReview,
        Custom,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum CommunicationStyle {
        Formal,
        Standard,
        Urgent,
        Silent,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct ServiceFunctionTemplate {
        pub function_id: String,
        pub name: String,
        pub function_type: FunctionType,
        pub description: String,
        pub created_at: String,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct FunctionPolicyBinding {
        pub binding_id: String,
        pub function_id: String,
        pub policy_pack_id: String,
        pub autonomy_mode: String,
        pub review_required: bool,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub deployment_profile_id: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct FunctionSlaProfile {
        pub function_id: String,
        pub target_completion_minutes: u64,
        pub approval_latency_minutes: u64,
        pub escalation_threshold_minutes: u64,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct FunctionQueueProfile {
        pub function_id: String,
        pub team_id: String,
        pub default_role_id: String,
        pub communication_style: CommunicationStyle,
        pub max_concurrent_jobs: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub escalation_chain_id: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct FunctionOutcomeRecord {
        pub outcome_id: String,
        pub function_id: String,
        pub job_id: String,
        pub completed: bool,
        pub completion_minutes: u64,
        pub escalated: bool,
        pub drift_detected: bool,
        pub recorded_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct FunctionMetricsSnapshot {
        pub function_id: String,
        pub period_start: String,
        pub period_end: String,
        pub total_jobs: u64,
        pub completed_jobs: u64,
        pub failed_jobs: u64,
        pub avg_completion_minutes: f64,
        pub escalation_count: u64,
        pub drift_count: u64,
        pub captured_at: String,
    }
}

// ===========================================================================
// Roles (Teams / Workers)
// ===========================================================================

pub mod roles {
    use super::*;

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
    #[serde(rename_all = "snake_case")]
    pub enum WorkerStatus {
        #[default]
        Available,
        Busy,
        Overloaded,
        Offline,
        OnHold,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum AssignmentStrategy {
        LeastLoaded,
        RoundRobin,
        Explicit,
        Escalate,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
    #[serde(rename_all = "snake_case")]
    pub enum HandoffReason {
        CapacityExceeded,
        RoleChange,
        Escalation,
        OperatorOverride,
        ShiftChange,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct RoleDescriptor {
        pub role_id: String,
        pub name: String,
        pub description: String,
        pub required_skills: Vec<String>,
        #[serde(default)]
        pub approval_required: bool,
        #[serde(default = "default_max_concurrent")]
        pub max_concurrent_per_worker: u64,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    fn default_max_concurrent() -> u64 {
        5
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
    pub struct WorkerProfile {
        pub worker_id: String,
        pub name: String,
        pub roles: Vec<String>,
        #[serde(default = "default_max_concurrent")]
        pub max_concurrent_jobs: u64,
        #[serde(default)]
        pub status: WorkerStatus,
        #[serde(default)]
        pub metadata: HashMap<String, serde_json::Value>,
    }

    // Default derived via #[default] on Available variant

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkerCapacity {
        pub worker_id: String,
        pub max_concurrent: u64,
        pub current_load: u64,
        pub available_slots: u64,
        pub updated_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct AssignmentPolicy {
        pub policy_id: String,
        pub role_id: String,
        pub strategy: AssignmentStrategy,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub fallback_team_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub escalation_chain_id: Option<String>,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct AssignmentDecision {
        pub decision_id: String,
        pub job_id: String,
        pub worker_id: String,
        pub role_id: String,
        pub reason: String,
        pub decided_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct HandoffRecord {
        pub handoff_id: String,
        pub job_id: String,
        pub from_worker_id: String,
        pub to_worker_id: String,
        pub reason: HandoffReason,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        pub thread_id: Option<String>,
        #[serde(default, skip_serializing_if = "String::is_empty")]
        pub handoff_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct WorkloadSnapshot {
        pub snapshot_id: String,
        pub team_id: String,
        pub worker_capacities: Vec<WorkerCapacity>,
        #[serde(default, skip_serializing_if = "String::is_empty")]
        pub captured_at: String,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
    pub struct TeamQueueState {
        pub team_id: String,
        pub queued_jobs: u64,
        pub assigned_jobs: u64,
        pub waiting_jobs: u64,
        pub overloaded_workers: u64,
        pub captured_at: String,
    }
}

// ===========================================================================
// Tests
// ===========================================================================

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

    // --- Jobs ---

    #[test]
    fn job_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&job::JobStatus::InProgress).unwrap();
        assert_eq!(json, r#""in_progress""#);
    }

    #[test]
    fn job_priority_serializes_to_snake_case() {
        let json = serde_json::to_string(&job::JobPriority::Critical).unwrap();
        assert_eq!(json, r#""critical""#);
    }

    #[test]
    fn pause_reason_serializes_to_snake_case() {
        let json = serde_json::to_string(&job::PauseReason::AwaitingApproval).unwrap();
        assert_eq!(json, r#""awaiting_approval""#);
    }

    #[test]
    fn job_descriptor_round_trips() {
        let jd = job::JobDescriptor {
            job_id: "j-1".into(),
            name: "Deploy service".into(),
            description: "Deploy the new version".into(),
            priority: job::JobPriority::High,
            created_at: "2025-01-01T00:00:00+00:00".into(),
            goal_id: Some("g-1".into()),
            workflow_id: None,
            deadline: Some("2025-01-02T00:00:00+00:00".into()),
            sla_target_minutes: Some(60),
            metadata: HashMap::new(),
        };
        let json = serde_json::to_string(&jd).unwrap();
        let back: job::JobDescriptor = serde_json::from_str(&json).unwrap();
        assert_eq!(jd, back);
    }

    // --- Workflows ---

    #[test]
    fn workflow_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&workflow::WorkflowStatus::Suspended).unwrap();
        assert_eq!(json, r#""suspended""#);
    }

    #[test]
    fn stage_type_serializes_to_snake_case() {
        let json = serde_json::to_string(&workflow::StageType::SkillExecution).unwrap();
        assert_eq!(json, r#""skill_execution""#);
    }

    #[test]
    fn workflow_descriptor_round_trips() {
        let wd = workflow::WorkflowDescriptor {
            workflow_id: "wf-1".into(),
            name: "Deploy pipeline".into(),
            description: "Standard deploy".into(),
            stages: vec![workflow::WorkflowStage {
                stage_id: "s-1".into(),
                stage_type: workflow::StageType::SkillExecution,
                skill_id: Some("deploy".into()),
                description: "run deploy".into(),
                predecessors: vec![],
                timeout_seconds: Some(300),
            }],
            bindings: vec![],
            created_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&wd).unwrap();
        let back: workflow::WorkflowDescriptor = serde_json::from_str(&json).unwrap();
        assert_eq!(wd, back);
    }

    #[test]
    fn canonical_workflow_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/workflow.json"
        ));
        assert_fixture_round_trip::<workflow::WorkflowDescriptor>(fixture_json);
    }

    // --- Goals ---

    #[test]
    fn goal_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&goal::GoalStatus::Replanning).unwrap();
        assert_eq!(json, r#""replanning""#);
    }

    #[test]
    fn goal_plan_round_trips() {
        let plan = goal::GoalPlan {
            plan_id: "p-1".into(),
            goal_id: "g-1".into(),
            sub_goals: vec![goal::SubGoal {
                sub_goal_id: "sg-1".into(),
                goal_id: "g-1".into(),
                description: "build component".into(),
                status: goal::SubGoalStatus::Pending,
                skill_id: None,
                workflow_id: Some("wf-1".into()),
                predecessors: vec![],
            }],
            created_at: "2025-01-01T00:00:00+00:00".into(),
            version: 1,
        };
        let json = serde_json::to_string(&plan).unwrap();
        let back: goal::GoalPlan = serde_json::from_str(&json).unwrap();
        assert_eq!(plan, back);
    }

    // --- Functions ---

    #[test]
    fn function_type_serializes_to_snake_case() {
        let json = serde_json::to_string(&function::FunctionType::IncidentResponse).unwrap();
        assert_eq!(json, r#""incident_response""#);
    }

    #[test]
    fn communication_style_serializes_to_snake_case() {
        let json = serde_json::to_string(&function::CommunicationStyle::Urgent).unwrap();
        assert_eq!(json, r#""urgent""#);
    }

    #[test]
    fn function_sla_profile_round_trips() {
        let sla = function::FunctionSlaProfile {
            function_id: "fn-1".into(),
            target_completion_minutes: 30,
            approval_latency_minutes: 5,
            escalation_threshold_minutes: 15,
        };
        let json = serde_json::to_string(&sla).unwrap();
        let back: function::FunctionSlaProfile = serde_json::from_str(&json).unwrap();
        assert_eq!(sla, back);
    }

    // --- Roles ---

    #[test]
    fn worker_status_serializes_to_snake_case() {
        let json = serde_json::to_string(&roles::WorkerStatus::OnHold).unwrap();
        assert_eq!(json, r#""on_hold""#);
    }

    #[test]
    fn assignment_strategy_serializes_to_snake_case() {
        let json = serde_json::to_string(&roles::AssignmentStrategy::LeastLoaded).unwrap();
        assert_eq!(json, r#""least_loaded""#);
    }

    #[test]
    fn handoff_reason_serializes_to_snake_case() {
        let json = serde_json::to_string(&roles::HandoffReason::CapacityExceeded).unwrap();
        assert_eq!(json, r#""capacity_exceeded""#);
    }

    #[test]
    fn role_descriptor_round_trips() {
        let rd = roles::RoleDescriptor {
            role_id: "r-1".into(),
            name: "Reviewer".into(),
            description: "Code reviewer".into(),
            required_skills: vec!["rust".into(), "review".into()],
            approval_required: false,
            max_concurrent_per_worker: 3,
            metadata: HashMap::new(),
        };
        let json = serde_json::to_string(&rd).unwrap();
        let back: roles::RoleDescriptor = serde_json::from_str(&json).unwrap();
        assert_eq!(rd, back);
    }

    #[test]
    fn worker_capacity_round_trips() {
        let wc = roles::WorkerCapacity {
            worker_id: "w-1".into(),
            max_concurrent: 5,
            current_load: 3,
            available_slots: 2,
            updated_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&wc).unwrap();
        let back: roles::WorkerCapacity = serde_json::from_str(&json).unwrap();
        assert_eq!(wc, back);
    }

    #[test]
    fn team_queue_state_round_trips() {
        let tqs = roles::TeamQueueState {
            team_id: "t-1".into(),
            queued_jobs: 5,
            assigned_jobs: 3,
            waiting_jobs: 2,
            overloaded_workers: 0,
            captured_at: "2025-01-01T00:00:00+00:00".into(),
        };
        let json = serde_json::to_string(&tqs).unwrap();
        let back: roles::TeamQueueState = serde_json::from_str(&json).unwrap();
        assert_eq!(tqs, back);
    }

    // --- Cross-format compatibility ---

    #[test]
    fn job_status_deserializes_from_python_format() {
        let js: job::JobStatus = serde_json::from_str(r#""in_progress""#).unwrap();
        assert_eq!(js, job::JobStatus::InProgress);
    }

    #[test]
    fn goal_status_deserializes_from_python_format() {
        let gs: goal::GoalStatus = serde_json::from_str(r#""replanning""#).unwrap();
        assert_eq!(gs, goal::GoalStatus::Replanning);
    }
}
