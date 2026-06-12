use crate::{
    hash_serializable, EventId, MindError, MindResult, ReadinessBlocker, ReadinessWaiverProposal,
    ReadinessWaiverVoteDecision, WaiverOperatorRole,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::{Duration, OffsetDateTime};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverReviewStatus {
    Open,
    ChangesRequested,
    Approved,
    Rejected,
    Expired,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverReviewQueueItem {
    pub review_id: EventId,
    pub proposal_id: EventId,
    #[serde(default)]
    pub blocker_ids: Vec<EventId>,
    pub risk_owner: String,
    #[serde(default)]
    pub required_roles: BTreeSet<WaiverOperatorRole>,
    pub status: WaiverReviewStatus,
    pub due_at: OffsetDateTime,
    pub queue_hash: String,
    pub opened_at: OffsetDateTime,
}

impl WaiverReviewQueueItem {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.review_id,
            self.proposal_id,
            &self.blocker_ids,
            &self.risk_owner,
            &self.required_roles,
            self.status,
            self.due_at,
            self.opened_at,
        ))?;
        if expected != self.queue_hash {
            return Err(MindError::Store(
                "waiver review queue item hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverReviewComment {
    pub comment_id: EventId,
    pub review_id: EventId,
    pub author: String,
    pub role: WaiverOperatorRole,
    pub body: String,
    pub decision: ReadinessWaiverVoteDecision,
    pub comment_hash: String,
    pub created_at: OffsetDateTime,
}

impl WaiverReviewComment {
    pub fn new(
        review_id: EventId,
        author: impl Into<String>,
        role: WaiverOperatorRole,
        decision: ReadinessWaiverVoteDecision,
        body: impl Into<String>,
    ) -> MindResult<Self> {
        let author = author.into();
        let body = body.into();
        if author.trim().is_empty() || body.trim().is_empty() {
            return Err(MindError::Store(
                "waiver review comments require author and body".to_owned(),
            ));
        }
        let comment_id = EventId::new();
        let created_at = OffsetDateTime::now_utc();
        let comment_hash = hash_serializable(&(
            comment_id, review_id, &author, role, &body, decision, created_at,
        ))?;
        Ok(Self {
            comment_id,
            review_id,
            author,
            role,
            body,
            decision,
            comment_hash,
            created_at,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.comment_id,
            self.review_id,
            &self.author,
            self.role,
            &self.body,
            self.decision,
            self.created_at,
        ))?;
        if expected != self.comment_hash {
            return Err(MindError::Store(
                "waiver review comment hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverReviewCertificate {
    pub certificate_id: EventId,
    pub review_id: EventId,
    pub proposal_id: EventId,
    #[serde(default)]
    pub comments: Vec<WaiverReviewComment>,
    pub status: WaiverReviewStatus,
    #[serde(default)]
    pub findings: Vec<String>,
    pub certificate_hash: String,
    pub certified_at: OffsetDateTime,
}

impl WaiverReviewCertificate {
    pub fn verify(&self) -> MindResult<()> {
        for comment in &self.comments {
            comment.verify()?;
        }
        let expected = hash_serializable(&(
            self.certificate_id,
            self.review_id,
            self.proposal_id,
            &self.comments,
            self.status,
            &self.findings,
            self.certified_at,
        ))?;
        if expected != self.certificate_hash {
            return Err(MindError::Store(
                "waiver review certificate hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn open_waiver_review_queue_item(
    proposal: &ReadinessWaiverProposal,
    blockers: &[ReadinessBlocker],
    required_roles: BTreeSet<WaiverOperatorRole>,
    due_in_hours: i64,
) -> MindResult<WaiverReviewQueueItem> {
    proposal.verify()?;
    if required_roles.is_empty() {
        return Err(MindError::Store(
            "waiver review requires at least one required role".to_owned(),
        ));
    }
    let blocker_ids = if proposal.blocker_ids.is_empty() {
        blockers
            .iter()
            .map(|blocker| blocker.blocker_id)
            .collect::<Vec<_>>()
    } else {
        proposal.blocker_ids.clone()
    };
    let review_id = EventId::new();
    let opened_at = OffsetDateTime::now_utc();
    let due_at = opened_at + Duration::hours(due_in_hours.max(1));
    let queue_hash = hash_serializable(&(
        review_id,
        proposal.proposal_id,
        &blocker_ids,
        &proposal.risk_owner,
        &required_roles,
        WaiverReviewStatus::Open,
        due_at,
        opened_at,
    ))?;
    Ok(WaiverReviewQueueItem {
        review_id,
        proposal_id: proposal.proposal_id,
        blocker_ids,
        risk_owner: proposal.risk_owner.clone(),
        required_roles,
        status: WaiverReviewStatus::Open,
        due_at,
        queue_hash,
        opened_at,
    })
}

pub fn certify_waiver_review(
    item: &WaiverReviewQueueItem,
    comments: Vec<WaiverReviewComment>,
) -> MindResult<WaiverReviewCertificate> {
    item.verify()?;
    for comment in &comments {
        comment.verify()?;
        if comment.review_id != item.review_id {
            return Err(MindError::Store(
                "waiver review comment belongs to a different review".to_owned(),
            ));
        }
    }
    let approved_roles = comments
        .iter()
        .filter(|comment| comment.decision == ReadinessWaiverVoteDecision::Approve)
        .map(|comment| comment.role)
        .collect::<BTreeSet<_>>();
    let missing_roles = item
        .required_roles
        .difference(&approved_roles)
        .copied()
        .collect::<BTreeSet<_>>();
    let mut findings = Vec::new();
    if !missing_roles.is_empty() {
        findings.push(format!("missing approvals from roles: {:?}", missing_roles));
    }
    if comments
        .iter()
        .any(|comment| comment.decision == ReadinessWaiverVoteDecision::Reject)
    {
        findings.push("at least one reviewer rejected the waiver".to_owned());
    }
    let status = if comments
        .iter()
        .any(|comment| comment.decision == ReadinessWaiverVoteDecision::Reject)
    {
        WaiverReviewStatus::Rejected
    } else if !missing_roles.is_empty() {
        WaiverReviewStatus::ChangesRequested
    } else {
        WaiverReviewStatus::Approved
    };
    let certificate_id = EventId::new();
    let certified_at = OffsetDateTime::now_utc();
    let certificate_hash = hash_serializable(&(
        certificate_id,
        item.review_id,
        item.proposal_id,
        &comments,
        status,
        &findings,
        certified_at,
    ))?;
    Ok(WaiverReviewCertificate {
        certificate_id,
        review_id: item.review_id,
        proposal_id: item.proposal_id,
        comments,
        status,
        findings,
        certificate_hash,
        certified_at,
    })
}
