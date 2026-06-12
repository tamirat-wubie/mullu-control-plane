use crate::{
    hash_serializable, EventId, MindError, MindResult, ProductionReadinessGateReport,
    ProductionReadinessStatus, ReadinessBlocker,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadinessWaiverProposal {
    pub proposal_id: EventId,
    pub gate_id: EventId,
    #[serde(default)]
    pub blocker_ids: Vec<EventId>,
    pub proposed_by: String,
    pub reason: String,
    pub risk_owner: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<OffsetDateTime>,
    pub proposal_hash: String,
    pub proposed_at: OffsetDateTime,
}

impl ReadinessWaiverProposal {
    pub fn new(
        gate: &ProductionReadinessGateReport,
        blocker_ids: Vec<EventId>,
        proposed_by: impl Into<String>,
        reason: impl Into<String>,
        risk_owner: impl Into<String>,
        expires_at: Option<OffsetDateTime>,
    ) -> MindResult<Self> {
        let proposed_by = proposed_by.into();
        let risk_owner = risk_owner.into();
        if proposed_by.trim().is_empty() || risk_owner.trim().is_empty() {
            return Err(MindError::Store(
                "waiver proposer and risk owner are required".to_owned(),
            ));
        }
        let known: BTreeSet<EventId> = gate
            .blockers
            .iter()
            .map(|blocker| blocker.blocker_id)
            .collect();
        for blocker_id in &blocker_ids {
            if !known.contains(blocker_id) {
                return Err(MindError::Store(format!(
                    "waiver references unknown blocker {blocker_id}"
                )));
            }
        }
        let proposal_id = EventId::new();
        let proposed_at = OffsetDateTime::now_utc();
        let reason = reason.into();
        let proposal_hash = hash_serializable(&(
            proposal_id,
            gate.gate_id,
            &blocker_ids,
            &proposed_by,
            &reason,
            &risk_owner,
            expires_at,
            proposed_at,
        ))?;
        Ok(Self {
            proposal_id,
            gate_id: gate.gate_id,
            blocker_ids,
            proposed_by,
            reason,
            risk_owner,
            expires_at,
            proposal_hash,
            proposed_at,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.proposal_id,
            self.gate_id,
            &self.blocker_ids,
            &self.proposed_by,
            &self.reason,
            &self.risk_owner,
            self.expires_at,
            self.proposed_at,
        ))?;
        if expected != self.proposal_hash {
            return Err(MindError::Store(
                "readiness waiver proposal hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ReadinessWaiverVoteDecision {
    Approve,
    Reject,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadinessWaiverVote {
    pub vote_id: EventId,
    pub proposal_id: EventId,
    pub voter: String,
    pub decision: ReadinessWaiverVoteDecision,
    pub rationale: String,
    pub vote_hash: String,
    pub voted_at: OffsetDateTime,
}

impl ReadinessWaiverVote {
    pub fn new(
        proposal_id: EventId,
        voter: impl Into<String>,
        decision: ReadinessWaiverVoteDecision,
        rationale: impl Into<String>,
    ) -> MindResult<Self> {
        let voter = voter.into();
        if voter.trim().is_empty() {
            return Err(MindError::Store(
                "readiness waiver voter is required".to_owned(),
            ));
        }
        let vote_id = EventId::new();
        let rationale = rationale.into();
        let voted_at = OffsetDateTime::now_utc();
        let vote_hash =
            hash_serializable(&(vote_id, proposal_id, &voter, decision, &rationale, voted_at))?;
        Ok(Self {
            vote_id,
            proposal_id,
            voter,
            decision,
            rationale,
            vote_hash,
            voted_at,
        })
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ReadinessWaiverStatus {
    Approved,
    Rejected,
    InsufficientApprovals,
    Expired,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadinessWaiverCertificate {
    pub certificate_id: EventId,
    pub proposal: ReadinessWaiverProposal,
    #[serde(default)]
    pub votes: Vec<ReadinessWaiverVote>,
    pub required_approvals: usize,
    pub approval_count: usize,
    pub rejection_count: usize,
    pub status: ReadinessWaiverStatus,
    pub certificate_hash: String,
    pub certified_at: OffsetDateTime,
}

impl ReadinessWaiverCertificate {
    pub fn verify(&self) -> MindResult<()> {
        self.proposal.verify()?;
        let expected = hash_serializable(&(
            self.certificate_id,
            &self.proposal,
            &self.votes,
            self.required_approvals,
            self.approval_count,
            self.rejection_count,
            self.status,
            self.certified_at,
        ))?;
        if expected != self.certificate_hash {
            return Err(MindError::Store(
                "readiness waiver certificate hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadinessWaiverApplicationReport {
    pub report_id: EventId,
    pub gate_id: EventId,
    pub original_status: ProductionReadinessStatus,
    pub effective_status: ProductionReadinessStatus,
    #[serde(default)]
    pub waived_blockers: Vec<ReadinessBlocker>,
    #[serde(default)]
    pub remaining_blockers: Vec<ReadinessBlocker>,
    #[serde(default)]
    pub certificate_ids: Vec<EventId>,
    pub report_hash: String,
    pub evaluated_at: OffsetDateTime,
}

pub fn certify_readiness_waiver(
    proposal: ReadinessWaiverProposal,
    votes: Vec<ReadinessWaiverVote>,
    required_approvals: usize,
) -> MindResult<ReadinessWaiverCertificate> {
    proposal.verify()?;
    if required_approvals == 0 {
        return Err(MindError::Store(
            "readiness waiver requires at least one approval".to_owned(),
        ));
    }
    let mut latest_by_voter: BTreeMap<String, ReadinessWaiverVote> = BTreeMap::new();
    for vote in votes {
        if vote.proposal_id != proposal.proposal_id {
            return Err(MindError::Store(
                "readiness waiver vote references a different proposal".to_owned(),
            ));
        }
        latest_by_voter.insert(vote.voter.clone(), vote);
    }
    let votes = latest_by_voter.into_values().collect::<Vec<_>>();
    let approval_count = votes
        .iter()
        .filter(|vote| vote.decision == ReadinessWaiverVoteDecision::Approve)
        .count();
    let rejection_count = votes
        .iter()
        .filter(|vote| vote.decision == ReadinessWaiverVoteDecision::Reject)
        .count();
    let now = OffsetDateTime::now_utc();
    let status = if proposal
        .expires_at
        .is_some_and(|expires_at| expires_at <= now)
    {
        ReadinessWaiverStatus::Expired
    } else if rejection_count > 0 {
        ReadinessWaiverStatus::Rejected
    } else if approval_count >= required_approvals {
        ReadinessWaiverStatus::Approved
    } else {
        ReadinessWaiverStatus::InsufficientApprovals
    };
    let certificate_id = EventId::new();
    let certificate_hash = hash_serializable(&(
        certificate_id,
        &proposal,
        &votes,
        required_approvals,
        approval_count,
        rejection_count,
        status,
        now,
    ))?;
    Ok(ReadinessWaiverCertificate {
        certificate_id,
        proposal,
        votes,
        required_approvals,
        approval_count,
        rejection_count,
        status,
        certificate_hash,
        certified_at: now,
    })
}

pub fn apply_readiness_waivers_to_gate(
    gate: &ProductionReadinessGateReport,
    certificates: &[ReadinessWaiverCertificate],
) -> MindResult<ReadinessWaiverApplicationReport> {
    let mut waived_ids = BTreeSet::new();
    let mut certificate_ids = Vec::new();
    for certificate in certificates {
        certificate.verify()?;
        if certificate.proposal.gate_id != gate.gate_id {
            continue;
        }
        if certificate.status == ReadinessWaiverStatus::Approved {
            certificate_ids.push(certificate.certificate_id);
            for blocker_id in &certificate.proposal.blocker_ids {
                waived_ids.insert(*blocker_id);
            }
        }
    }
    let mut waived_blockers = Vec::new();
    let mut remaining_blockers = Vec::new();
    for blocker in &gate.blockers {
        if waived_ids.contains(&blocker.blocker_id) {
            waived_blockers.push(blocker.clone());
        } else {
            remaining_blockers.push(blocker.clone());
        }
    }
    let effective_status = if remaining_blockers.is_empty() {
        match gate.status {
            ProductionReadinessStatus::Blocked => ProductionReadinessStatus::ReadyForStaging,
            other => other,
        }
    } else {
        ProductionReadinessStatus::Blocked
    };
    let report_id = EventId::new();
    let evaluated_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        report_id,
        gate.gate_id,
        gate.status,
        effective_status,
        &waived_blockers,
        &remaining_blockers,
        &certificate_ids,
        evaluated_at,
    ))?;
    Ok(ReadinessWaiverApplicationReport {
        report_id,
        gate_id: gate.gate_id,
        original_status: gate.status,
        effective_status,
        waived_blockers,
        remaining_blockers,
        certificate_ids,
        report_hash,
        evaluated_at,
    })
}
