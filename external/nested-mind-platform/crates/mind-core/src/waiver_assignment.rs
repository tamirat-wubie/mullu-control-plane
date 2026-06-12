use crate::{
    hash_serializable, EventId, MindError, MindResult, WaiverOperatorRole, WaiverReviewQueueItem,
    WaiverReviewStatus,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use time::{Duration, OffsetDateTime};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverAssignmentStatus {
    Assigned,
    NeedsEscalation,
    Escalated,
    Rejected,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverEscalationStatus {
    Planned,
    Sent,
    Acknowledged,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverReviewerCandidate {
    pub operator: String,
    pub team: String,
    pub role: WaiverOperatorRole,
    pub available: bool,
    pub current_queue_depth: u32,
}

impl WaiverReviewerCandidate {
    pub fn new(
        operator: impl Into<String>,
        team: impl Into<String>,
        role: WaiverOperatorRole,
        available: bool,
        current_queue_depth: u32,
    ) -> MindResult<Self> {
        let operator = operator.into();
        let team = team.into();
        if operator.trim().is_empty() || team.trim().is_empty() {
            return Err(MindError::Store(
                "waiver reviewer candidate requires operator and team".to_owned(),
            ));
        }
        Ok(Self {
            operator,
            team,
            role,
            available,
            current_queue_depth,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverReviewerAssignmentPlan {
    pub assignment_plan_id: EventId,
    pub review_id: EventId,
    pub proposal_id: EventId,
    #[serde(default)]
    pub required_roles: BTreeSet<WaiverOperatorRole>,
    #[serde(default)]
    pub selected_reviewers: Vec<WaiverReviewerCandidate>,
    #[serde(default)]
    pub missing_roles: BTreeSet<WaiverOperatorRole>,
    #[serde(default)]
    pub escalation_targets: BTreeMap<WaiverOperatorRole, String>,
    pub status: WaiverAssignmentStatus,
    pub due_at: OffsetDateTime,
    pub escalation_after: OffsetDateTime,
    pub assignment_hash: String,
    pub created_at: OffsetDateTime,
}

impl WaiverReviewerAssignmentPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.assignment_plan_id,
            self.review_id,
            self.proposal_id,
            &self.required_roles,
            &self.selected_reviewers,
            &self.missing_roles,
            &self.escalation_targets,
            self.status,
            self.due_at,
            self.escalation_after,
            self.created_at,
        ))?;
        if expected != self.assignment_hash {
            return Err(MindError::Store(
                "waiver reviewer assignment plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverEscalationCertificate {
    pub certificate_id: EventId,
    pub assignment_plan_id: EventId,
    pub review_id: EventId,
    pub proposal_id: EventId,
    pub status: WaiverEscalationStatus,
    pub reason: String,
    #[serde(default)]
    pub escalated_to: Vec<String>,
    #[serde(default)]
    pub missing_roles: BTreeSet<WaiverOperatorRole>,
    pub certificate_hash: String,
    pub escalated_at: OffsetDateTime,
}

impl WaiverEscalationCertificate {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.certificate_id,
            self.assignment_plan_id,
            self.review_id,
            self.proposal_id,
            self.status,
            &self.reason,
            &self.escalated_to,
            &self.missing_roles,
            self.escalated_at,
        ))?;
        if expected != self.certificate_hash {
            return Err(MindError::Store(
                "waiver escalation certificate hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_waiver_reviewer_assignment(
    queue_item: &WaiverReviewQueueItem,
    mut candidates: Vec<WaiverReviewerCandidate>,
    escalation_targets: BTreeMap<WaiverOperatorRole, String>,
    escalation_after_hours: i64,
) -> MindResult<WaiverReviewerAssignmentPlan> {
    queue_item.verify()?;
    if queue_item.status != WaiverReviewStatus::Open {
        return Err(MindError::Store(
            "waiver reviewer assignment requires an open review".to_owned(),
        ));
    }
    candidates.sort_by(|left, right| {
        left.current_queue_depth
            .cmp(&right.current_queue_depth)
            .then_with(|| left.team.cmp(&right.team))
            .then_with(|| left.operator.cmp(&right.operator))
    });
    let mut selected_reviewers = Vec::new();
    let mut covered_roles = BTreeSet::new();
    let mut selected_teams = BTreeSet::new();
    for role in &queue_item.required_roles {
        if let Some(candidate) = candidates.iter().find(|candidate| {
            candidate.available
                && &candidate.role == role
                && !selected_teams.contains(&candidate.team)
        }) {
            selected_teams.insert(candidate.team.clone());
            covered_roles.insert(candidate.role);
            selected_reviewers.push(candidate.clone());
        }
    }
    let missing_roles = queue_item
        .required_roles
        .difference(&covered_roles)
        .copied()
        .collect::<BTreeSet<_>>();
    let status = if missing_roles.is_empty() {
        WaiverAssignmentStatus::Assigned
    } else if missing_roles
        .iter()
        .all(|role| escalation_targets.contains_key(role))
    {
        WaiverAssignmentStatus::NeedsEscalation
    } else {
        WaiverAssignmentStatus::Rejected
    };
    let assignment_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let escalation_after = created_at + Duration::hours(escalation_after_hours.max(1));
    let assignment_hash = hash_serializable(&(
        assignment_plan_id,
        queue_item.review_id,
        queue_item.proposal_id,
        &queue_item.required_roles,
        &selected_reviewers,
        &missing_roles,
        &escalation_targets,
        status,
        queue_item.due_at,
        escalation_after,
        created_at,
    ))?;
    Ok(WaiverReviewerAssignmentPlan {
        assignment_plan_id,
        review_id: queue_item.review_id,
        proposal_id: queue_item.proposal_id,
        required_roles: queue_item.required_roles.clone(),
        selected_reviewers,
        missing_roles,
        escalation_targets,
        status,
        due_at: queue_item.due_at,
        escalation_after,
        assignment_hash,
        created_at,
    })
}

pub fn certify_waiver_escalation(
    plan: &WaiverReviewerAssignmentPlan,
    reason: impl Into<String>,
) -> MindResult<WaiverEscalationCertificate> {
    plan.verify()?;
    let reason = reason.into();
    if reason.trim().is_empty() {
        return Err(MindError::Store(
            "waiver escalation requires a reason".to_owned(),
        ));
    }
    let escalated_to = plan
        .missing_roles
        .iter()
        .filter_map(|role| plan.escalation_targets.get(role).cloned())
        .collect::<Vec<_>>();
    let status = if plan.missing_roles.is_empty() || escalated_to.is_empty() {
        WaiverEscalationStatus::Rejected
    } else {
        WaiverEscalationStatus::Planned
    };
    let certificate_id = EventId::new();
    let escalated_at = OffsetDateTime::now_utc();
    let certificate_hash = hash_serializable(&(
        certificate_id,
        plan.assignment_plan_id,
        plan.review_id,
        plan.proposal_id,
        status,
        &reason,
        &escalated_to,
        &plan.missing_roles,
        escalated_at,
    ))?;
    Ok(WaiverEscalationCertificate {
        certificate_id,
        assignment_plan_id: plan.assignment_plan_id,
        review_id: plan.review_id,
        proposal_id: plan.proposal_id,
        status,
        reason,
        escalated_to,
        missing_roles: plan.missing_roles.clone(),
        certificate_hash,
        escalated_at,
    })
}
