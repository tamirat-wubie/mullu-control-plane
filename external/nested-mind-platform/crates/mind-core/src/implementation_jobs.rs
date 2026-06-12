use crate::{
    hash_serializable, CreativeEngineeringReport, CreativeEngineeringSuggestion,
    EngineeringPriority, EventId, MindError, MindResult, ScheduledJob, ScheduledJobKind,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::cmp::Reverse;
use time::{Duration, OffsetDateTime};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EngineeringImplementationJob {
    pub implementation_job_id: EventId,
    pub suggestion_id: EventId,
    pub suggestion_title: String,
    pub priority: EngineeringPriority,
    pub scheduled_job: ScheduledJob,
    #[serde(default)]
    pub acceptance_criteria: Vec<String>,
    pub rollback_plan: String,
    pub job_hash: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EngineeringImplementationJobPlan {
    pub plan_id: EventId,
    pub source_report_id: EventId,
    #[serde(default)]
    pub jobs: Vec<EngineeringImplementationJob>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl EngineeringImplementationJobPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.plan_id,
            self.source_report_id,
            &self.jobs,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "engineering implementation job plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn schedule_engineering_implementation_jobs(
    report: &CreativeEngineeringReport,
    limit: usize,
    due_in_seconds: i64,
) -> MindResult<EngineeringImplementationJobPlan> {
    let mut suggestions = report.suggestions.clone();
    suggestions.sort_by_key(|suggestion| Reverse(suggestion.priority_score));
    let selected = suggestions
        .into_iter()
        .take(limit.max(1))
        .collect::<Vec<_>>();
    let due_at = OffsetDateTime::now_utc() + Duration::seconds(due_in_seconds.max(0));
    let mut jobs = Vec::new();
    for suggestion in selected {
        jobs.push(job_from_suggestion(&suggestion, due_at)?);
    }
    let plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(plan_id, report.report_id, &jobs, created_at))?;
    Ok(EngineeringImplementationJobPlan {
        plan_id,
        source_report_id: report.report_id,
        jobs,
        plan_hash,
        created_at,
    })
}

fn job_from_suggestion(
    suggestion: &CreativeEngineeringSuggestion,
    due_at: OffsetDateTime,
) -> MindResult<EngineeringImplementationJob> {
    let payload = json!({
        "suggestion_id": suggestion.suggestion_id,
        "area": format!("{:?}", suggestion.area),
        "title": suggestion.title,
        "mechanism": suggestion.mechanism,
        "invariant_guard": suggestion.invariant_guard,
        "implementation_delta": suggestion.implementation_delta,
        "validation_probe": suggestion.validation_probe,
        "tags": suggestion.tags,
    });
    let target = format!("engineering/{:?}", suggestion.area).to_ascii_lowercase();
    let scheduled_job = ScheduledJob::new(
        ScheduledJobKind::ProviderExecution,
        target,
        &payload,
        due_at,
        1,
    )?;
    let acceptance_criteria = vec![
        suggestion.invariant_guard.clone(),
        suggestion.validation_probe.clone(),
        "receipt or test evidence is attached before closing the implementation job".to_owned(),
    ];
    let implementation_job_id = EventId::new();
    let rollback_plan = suggestion.rollback_plan.clone();
    let job_hash = hash_serializable(&(
        implementation_job_id,
        suggestion.suggestion_id,
        &suggestion.title,
        suggestion.priority,
        &scheduled_job,
        &acceptance_criteria,
        &rollback_plan,
    ))?;
    Ok(EngineeringImplementationJob {
        implementation_job_id,
        suggestion_id: suggestion.suggestion_id,
        suggestion_title: suggestion.title.clone(),
        priority: suggestion.priority,
        scheduled_job,
        acceptance_criteria,
        rollback_plan,
        job_hash,
    })
}
