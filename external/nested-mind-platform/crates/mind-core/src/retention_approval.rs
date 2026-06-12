use crate::{
    hash_serializable, ConsensusMembership, ConsensusRetentionEnforcementPlan, EventId, MindError,
    MindResult,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum RetentionApprovalVoteDecision {
    Approve,
    Reject,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum RetentionApprovalStatus {
    Pending,
    Approved,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusRetentionApprovalPolicy {
    pub require_quorum: bool,
    pub require_backup_guard_hash: bool,
    pub minimum_approvals: usize,
}

impl Default for ConsensusRetentionApprovalPolicy {
    fn default() -> Self {
        Self {
            require_quorum: true,
            require_backup_guard_hash: true,
            minimum_approvals: 1,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusRetentionApprovalProposal {
    pub proposal_id: EventId,
    pub plan_id: EventId,
    pub decision_id: EventId,
    pub cluster_id: String,
    pub expected_configuration_id: EventId,
    pub expected_term: u64,
    pub backup_guard_hash: String,
    pub plan_hash: String,
    pub proposed_by: String,
    pub proposed_at: OffsetDateTime,
}

impl ConsensusRetentionApprovalProposal {
    pub fn from_plan(
        plan: &ConsensusRetentionEnforcementPlan,
        membership: &ConsensusMembership,
        proposed_by: impl Into<String>,
    ) -> MindResult<Self> {
        membership.validate()?;
        if plan.cluster_id != membership.cluster_id {
            return Err(MindError::DistributedPlanInvalid {
                reason: "retention approval cluster mismatch".to_owned(),
            });
        }
        let proposed_by = proposed_by.into();
        let plan_hash = hash_serializable(plan)?;
        Ok(Self {
            proposal_id: EventId::new(),
            plan_id: plan.plan_id,
            decision_id: plan.decision_id,
            cluster_id: plan.cluster_id.clone(),
            expected_configuration_id: membership.configuration_id,
            expected_term: membership.term,
            backup_guard_hash: plan.backup_guard_hash.clone(),
            plan_hash,
            proposed_by,
            proposed_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusRetentionApprovalVote {
    pub vote_id: EventId,
    pub proposal_id: EventId,
    pub voter_id: String,
    pub decision: RetentionApprovalVoteDecision,
    pub proposal_hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    pub voted_at: OffsetDateTime,
}

impl ConsensusRetentionApprovalVote {
    pub fn new(
        proposal: &ConsensusRetentionApprovalProposal,
        voter_id: impl Into<String>,
        decision: RetentionApprovalVoteDecision,
    ) -> MindResult<Self> {
        Ok(Self {
            vote_id: EventId::new(),
            proposal_id: proposal.proposal_id,
            voter_id: voter_id.into(),
            decision,
            proposal_hash: hash_serializable(proposal)?,
            reason: None,
            voted_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusRetentionApprovalCertificate {
    pub certificate_id: EventId,
    pub proposal_id: EventId,
    pub plan_id: EventId,
    pub cluster_id: String,
    pub status: RetentionApprovalStatus,
    pub approvals: usize,
    pub rejections: usize,
    pub quorum_size: usize,
    #[serde(default)]
    pub voters: Vec<String>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub certified_at: OffsetDateTime,
}

pub fn certify_consensus_retention_approval(
    proposal: &ConsensusRetentionApprovalProposal,
    membership: &ConsensusMembership,
    policy: &ConsensusRetentionApprovalPolicy,
    votes: &[ConsensusRetentionApprovalVote],
) -> MindResult<ConsensusRetentionApprovalCertificate> {
    membership.validate()?;
    if proposal.cluster_id != membership.cluster_id
        || proposal.expected_configuration_id != membership.configuration_id
        || proposal.expected_term != membership.term
    {
        return Err(MindError::DistributedPlanInvalid {
            reason: "retention approval proposal is stale for current membership".to_owned(),
        });
    }
    if policy.require_backup_guard_hash && proposal.backup_guard_hash.trim().is_empty() {
        return Err(MindError::DistributedPlanInvalid {
            reason: "retention approval requires a backup guard hash".to_owned(),
        });
    }
    let voting_members: BTreeSet<String> = membership
        .voting_members()
        .into_iter()
        .map(|member| member.member_id.clone())
        .collect();
    let proposal_hash = hash_serializable(proposal)?;
    let mut seen = BTreeSet::new();
    let mut approvals = 0;
    let mut rejections = 0;
    let mut voters = Vec::new();
    let mut reasons = Vec::new();
    for vote in votes {
        if vote.proposal_id != proposal.proposal_id || vote.proposal_hash != proposal_hash {
            reasons.push(format!("vote `{}` does not bind to proposal", vote.vote_id));
            continue;
        }
        if !voting_members.contains(&vote.voter_id) || !seen.insert(vote.voter_id.clone()) {
            reasons.push(format!("vote from `{}` ignored", vote.voter_id));
            continue;
        }
        voters.push(vote.voter_id.clone());
        match vote.decision {
            RetentionApprovalVoteDecision::Approve => approvals += 1,
            RetentionApprovalVoteDecision::Reject => rejections += 1,
        }
    }
    let quorum_size = if policy.require_quorum {
        membership.quorum_size()
    } else {
        policy.minimum_approvals.max(1)
    };
    let needed = quorum_size.max(policy.minimum_approvals.max(1));
    let status = if rejections >= quorum_size {
        RetentionApprovalStatus::Rejected
    } else if approvals >= needed {
        RetentionApprovalStatus::Approved
    } else {
        RetentionApprovalStatus::Pending
    };
    if status == RetentionApprovalStatus::Approved {
        reasons.push("retention approval reached required quorum".to_owned());
    }
    Ok(ConsensusRetentionApprovalCertificate {
        certificate_id: EventId::new(),
        proposal_id: proposal.proposal_id,
        plan_id: proposal.plan_id,
        cluster_id: proposal.cluster_id.clone(),
        status,
        approvals,
        rejections,
        quorum_size,
        voters,
        reasons,
        certified_at: OffsetDateTime::now_utc(),
    })
}
