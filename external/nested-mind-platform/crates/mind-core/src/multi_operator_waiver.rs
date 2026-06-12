use crate::{
    hash_serializable, EventId, MindError, MindResult, ProductionReadinessGateReport,
    ReadinessWaiverProposal, ReadinessWaiverStatus, ReadinessWaiverVoteDecision,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverOperatorRole {
    Maintainer,
    Security,
    Sre,
    ProductOwner,
    Auditor,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MultiOperatorWaiverPolicy {
    pub minimum_approvals: usize,
    pub minimum_distinct_teams: usize,
    #[serde(default)]
    pub required_roles: BTreeSet<WaiverOperatorRole>,
    pub require_security_for_critical_blockers: bool,
    pub forbid_risk_owner_vote: bool,
}

impl Default for MultiOperatorWaiverPolicy {
    fn default() -> Self {
        let mut required_roles = BTreeSet::new();
        required_roles.insert(WaiverOperatorRole::Maintainer);
        required_roles.insert(WaiverOperatorRole::Security);
        Self {
            minimum_approvals: 2,
            minimum_distinct_teams: 2,
            required_roles,
            require_security_for_critical_blockers: true,
            forbid_risk_owner_vote: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MultiOperatorWaiverVote {
    pub vote_id: EventId,
    pub proposal_id: EventId,
    pub operator_id: String,
    pub role: WaiverOperatorRole,
    pub team: String,
    pub decision: ReadinessWaiverVoteDecision,
    pub rationale: String,
    pub vote_hash: String,
    pub voted_at: OffsetDateTime,
}

impl MultiOperatorWaiverVote {
    pub fn new(
        proposal_id: EventId,
        operator_id: impl Into<String>,
        role: WaiverOperatorRole,
        team: impl Into<String>,
        decision: ReadinessWaiverVoteDecision,
        rationale: impl Into<String>,
    ) -> MindResult<Self> {
        let operator_id = operator_id.into();
        let team = team.into();
        if operator_id.trim().is_empty() || team.trim().is_empty() {
            return Err(MindError::Store(
                "multi-operator waiver vote requires operator and team".to_owned(),
            ));
        }
        let vote_id = EventId::new();
        let rationale = rationale.into();
        let voted_at = OffsetDateTime::now_utc();
        let vote_hash = hash_serializable(&(
            vote_id,
            proposal_id,
            &operator_id,
            role,
            &team,
            decision,
            &rationale,
            voted_at,
        ))?;
        Ok(Self {
            vote_id,
            proposal_id,
            operator_id,
            role,
            team,
            decision,
            rationale,
            vote_hash,
            voted_at,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.vote_id,
            self.proposal_id,
            &self.operator_id,
            self.role,
            &self.team,
            self.decision,
            &self.rationale,
            self.voted_at,
        ))?;
        if expected != self.vote_hash {
            return Err(MindError::Store(
                "multi-operator waiver vote hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MultiOperatorWaiverCertificate {
    pub certificate_id: EventId,
    pub proposal: ReadinessWaiverProposal,
    pub gate_id: EventId,
    pub policy: MultiOperatorWaiverPolicy,
    #[serde(default)]
    pub votes: Vec<MultiOperatorWaiverVote>,
    pub approval_count: usize,
    pub rejection_count: usize,
    #[serde(default)]
    pub approving_roles: BTreeSet<WaiverOperatorRole>,
    #[serde(default)]
    pub approving_teams: BTreeSet<String>,
    pub status: ReadinessWaiverStatus,
    #[serde(default)]
    pub findings: Vec<String>,
    pub certificate_hash: String,
    pub certified_at: OffsetDateTime,
}

impl MultiOperatorWaiverCertificate {
    pub fn verify(&self) -> MindResult<()> {
        self.proposal.verify()?;
        for vote in &self.votes {
            vote.verify()?;
        }
        let expected = hash_serializable(&(
            self.certificate_id,
            &self.proposal,
            self.gate_id,
            &self.policy,
            &self.votes,
            self.approval_count,
            self.rejection_count,
            &self.approving_roles,
            &self.approving_teams,
            self.status,
            &self.findings,
            self.certified_at,
        ))?;
        if expected != self.certificate_hash {
            return Err(MindError::Store(
                "multi-operator waiver certificate hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn certify_multi_operator_readiness_waiver(
    proposal: ReadinessWaiverProposal,
    gate: &ProductionReadinessGateReport,
    votes: Vec<MultiOperatorWaiverVote>,
    policy: MultiOperatorWaiverPolicy,
) -> MindResult<MultiOperatorWaiverCertificate> {
    proposal.verify()?;
    if proposal.gate_id != gate.gate_id {
        return Err(MindError::Store(
            "multi-operator waiver proposal references a different gate".to_owned(),
        ));
    }
    if policy.minimum_approvals == 0 {
        return Err(MindError::Store(
            "multi-operator waiver requires at least one approval".to_owned(),
        ));
    }
    let mut latest_by_operator: BTreeMap<String, MultiOperatorWaiverVote> = BTreeMap::new();
    for vote in votes {
        vote.verify()?;
        if vote.proposal_id != proposal.proposal_id {
            return Err(MindError::Store(
                "multi-operator waiver vote references a different proposal".to_owned(),
            ));
        }
        latest_by_operator.insert(vote.operator_id.clone(), vote);
    }
    let votes = latest_by_operator.into_values().collect::<Vec<_>>();
    let mut findings = Vec::new();
    let mut approving_roles = BTreeSet::new();
    let mut approving_teams = BTreeSet::new();
    let mut approval_count = 0_usize;
    let mut rejection_count = 0_usize;
    for vote in &votes {
        match vote.decision {
            ReadinessWaiverVoteDecision::Approve => {
                if policy.forbid_risk_owner_vote && vote.operator_id == proposal.risk_owner {
                    findings.push(format!(
                        "risk owner `{}` cannot approve own waiver",
                        vote.operator_id
                    ));
                    continue;
                }
                approval_count += 1;
                approving_roles.insert(vote.role);
                approving_teams.insert(vote.team.clone());
            }
            ReadinessWaiverVoteDecision::Reject => rejection_count += 1,
        }
    }
    for required in &policy.required_roles {
        if !approving_roles.contains(required) {
            findings.push(format!("missing required approval role {required:?}"));
        }
    }
    if approval_count < policy.minimum_approvals {
        findings.push(format!(
            "approval count {approval_count} below required {}",
            policy.minimum_approvals
        ));
    }
    if approving_teams.len() < policy.minimum_distinct_teams {
        findings.push(format!(
            "approving team count {} below required {}",
            approving_teams.len(),
            policy.minimum_distinct_teams
        ));
    }
    let critical_blocker = gate.blockers.iter().any(|blocker| {
        let text = format!(
            "{} {} {}",
            blocker.title, blocker.reason, blocker.required_action
        )
        .to_ascii_lowercase();
        text.contains("critical") || text.contains("secret") || text.contains("signature")
    });
    if policy.require_security_for_critical_blockers
        && critical_blocker
        && !approving_roles.contains(&WaiverOperatorRole::Security)
    {
        findings.push("critical blocker waiver requires security approval".to_owned());
    }
    let now = OffsetDateTime::now_utc();
    let status = if proposal
        .expires_at
        .is_some_and(|expires_at| expires_at <= now)
    {
        ReadinessWaiverStatus::Expired
    } else if rejection_count > 0 {
        ReadinessWaiverStatus::Rejected
    } else if findings.is_empty() {
        ReadinessWaiverStatus::Approved
    } else {
        ReadinessWaiverStatus::InsufficientApprovals
    };
    let certificate_id = EventId::new();
    let certificate_hash = hash_serializable(&(
        certificate_id,
        &proposal,
        gate.gate_id,
        &policy,
        &votes,
        approval_count,
        rejection_count,
        &approving_roles,
        &approving_teams,
        status,
        &findings,
        now,
    ))?;
    Ok(MultiOperatorWaiverCertificate {
        certificate_id,
        proposal,
        gate_id: gate.gate_id,
        policy,
        votes,
        approval_count,
        rejection_count,
        approving_roles,
        approving_teams,
        status,
        findings,
        certificate_hash,
        certified_at: now,
    })
}
