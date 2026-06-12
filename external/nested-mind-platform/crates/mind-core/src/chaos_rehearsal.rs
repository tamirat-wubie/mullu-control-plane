use crate::{hash_serializable, EventId, MindId, MindResult};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ChaosExperimentKind {
    AppendStoreFailure,
    UnsignedCommit,
    BrokenEventHashChain,
    StaleConsensusTerm,
    DuplicateSchedulerLease,
    ProviderReceiptHashMismatch,
    ProjectionSecretLeak,
    UnsafeLawbookMigration,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ChaosSeverity {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChaosRehearsalExperiment {
    pub experiment_id: EventId,
    pub kind: ChaosExperimentKind,
    pub name: String,
    pub invariant_under_test: String,
    pub injection_point: String,
    pub expected_containment: String,
    pub expected_signal: String,
    pub rollback_guard: String,
    #[serde(default)]
    pub evidence_required: Vec<String>,
    pub severity: ChaosSeverity,
}

impl ChaosRehearsalExperiment {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        kind: ChaosExperimentKind,
        name: impl Into<String>,
        invariant_under_test: impl Into<String>,
        injection_point: impl Into<String>,
        expected_containment: impl Into<String>,
        expected_signal: impl Into<String>,
        rollback_guard: impl Into<String>,
        evidence_required: Vec<String>,
        severity: ChaosSeverity,
    ) -> Self {
        Self {
            experiment_id: EventId::new(),
            kind,
            name: name.into(),
            invariant_under_test: invariant_under_test.into(),
            injection_point: injection_point.into(),
            expected_containment: expected_containment.into(),
            expected_signal: expected_signal.into(),
            rollback_guard: rollback_guard.into(),
            evidence_required,
            severity,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChaosRehearsalPlan {
    pub plan_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    #[serde(default)]
    pub experiments: Vec<ChaosRehearsalExperiment>,
    pub safety_boundary: String,
    pub rehearsal_hash: String,
    pub generated_at: OffsetDateTime,
}

impl ChaosRehearsalPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.plan_id,
            self.mind_id,
            &self.experiments,
            &self.safety_boundary,
            self.generated_at,
        ))?;
        if expected != self.rehearsal_hash {
            return Err(crate::MindError::Store(
                "chaos rehearsal hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn production_chaos_rehearsal_plan(mind_id: Option<MindId>) -> MindResult<ChaosRehearsalPlan> {
    let experiments = vec![
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::AppendStoreFailure,
            "append-before-apply failure rehearsal",
            "Σ must not change unless H accepted the commit record",
            "event-store append returns an error after EvolutionPlan creation",
            "live mind state and history remain unchanged",
            "store error + no new commit in mind.history",
            "drop the plan and require operator retry from original proposal",
            vec![
                "before_state_hash".to_owned(),
                "after_state_hash".to_owned(),
            ],
            ChaosSeverity::Critical,
        ),
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::UnsignedCommit,
            "required-signature rejection rehearsal",
            "unsigned commits are never appended when signatures are required",
            "strip Commit.signature before append",
            "append fails before sequence allocation",
            "CommitUnsigned error or equivalent rejection",
            "restore signing backend or mark node read-only",
            vec!["commit_id".to_owned(), "signature_requirement".to_owned()],
            ChaosSeverity::Critical,
        ),
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::BrokenEventHashChain,
            "event hash-chain fracture rehearsal",
            "H is causal and tamper evident",
            "mutate previous_record_hash or record_hash in a replicated record",
            "replay and follower ingestion reject the tail",
            "EventChainBroken or EventRecordHashMismatch",
            "discard follower inbox batch and request leader resend",
            vec![
                "sequence".to_owned(),
                "expected_hash".to_owned(),
                "actual_hash".to_owned(),
            ],
            ChaosSeverity::Critical,
        ),
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::StaleConsensusTerm,
            "stale consensus term rehearsal",
            "membership mutation cannot apply to an unexpected term/configuration",
            "submit consensus change with old expected_term",
            "judgment rejected with no membership replacement",
            "DistributedPlanInvalid stale-state reason",
            "refresh membership and regenerate the proposal",
            vec!["expected_term".to_owned(), "actual_term".to_owned()],
            ChaosSeverity::High,
        ),
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::DuplicateSchedulerLease,
            "duplicate scheduler lease rehearsal",
            "one payload has at most one active winning claim",
            "race two workers against the same due job",
            "only one compare-and-swap claim inserts a lease receipt",
            "one accepted lease + one rejected/no-op claim report",
            "expire losing leases and reschedule pending jobs",
            vec![
                "job_id".to_owned(),
                "payload_hash".to_owned(),
                "worker_ids".to_owned(),
            ],
            ChaosSeverity::High,
        ),
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::ProviderReceiptHashMismatch,
            "provider receipt mismatch rehearsal",
            "external side effects are trusted only through matching receipts",
            "corrupt provider receipt payload_hash after SDK/gateway execution",
            "execution report rejected; job remains retryable or blocked",
            "Provider receipt verification failure",
            "do not mark job succeeded; require fresh receipt",
            vec!["request_hash".to_owned(), "receipt_hash".to_owned()],
            ChaosSeverity::High,
        ),
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::ProjectionSecretLeak,
            "projection leak rehearsal",
            "Γ exposes meaning without leaking sensitive cells",
            "inject secret.*, password, token, and credential cells before public projection",
            "public/summary projections omit sensitive keys",
            "projection redaction evidence and no leaked keys",
            "force ProjectionPolicy::public_default until matrix passes",
            vec!["projection_scope".to_owned(), "redacted_keys".to_owned()],
            ChaosSeverity::High,
        ),
        ChaosRehearsalExperiment::new(
            ChaosExperimentKind::UnsafeLawbookMigration,
            "unsafe lawbook migration rehearsal",
            "Λ changes only through safe, explicit transition commits",
            "attempt to remove a foundation rule without allow_foundation_removal",
            "migration rejected and current lawbook hash unchanged",
            "LawbookMigrationUnsafeRemoval or equivalent rejection",
            "split migration into additive rule and reviewed removal proposal",
            vec![
                "before_lawbook_hash".to_owned(),
                "after_lawbook_hash".to_owned(),
            ],
            ChaosSeverity::Critical,
        ),
    ];
    let plan_id = EventId::new();
    let safety_boundary =
        "run against staging, local mirror, or deterministic dry-run stores only".to_owned();
    let generated_at = OffsetDateTime::now_utc();
    let rehearsal_hash = hash_serializable(&(
        plan_id,
        mind_id,
        &experiments,
        &safety_boundary,
        generated_at,
    ))?;
    Ok(ChaosRehearsalPlan {
        plan_id,
        mind_id,
        experiments,
        safety_boundary,
        rehearsal_hash,
        generated_at,
    })
}
