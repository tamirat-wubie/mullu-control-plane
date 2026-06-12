use crate::{EventId, MindError, MindResult};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConsensusMemberRole {
    Voter,
    Leader,
    Learner,
    Witness,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusMember {
    pub member_id: String,
    pub role: ConsensusMemberRole,
    pub voting: bool,
    pub priority: u32,
}

impl ConsensusMember {
    #[must_use]
    pub fn voter(member_id: impl Into<String>) -> Self {
        Self {
            member_id: member_id.into(),
            role: ConsensusMemberRole::Voter,
            voting: true,
            priority: 0,
        }
    }
    #[must_use]
    pub fn learner(member_id: impl Into<String>) -> Self {
        Self {
            member_id: member_id.into(),
            role: ConsensusMemberRole::Learner,
            voting: false,
            priority: 100,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusMembership {
    pub cluster_id: String,
    pub configuration_id: EventId,
    pub term: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub leader_id: Option<String>,
    #[serde(default)]
    pub members: Vec<ConsensusMember>,
    pub created_at: OffsetDateTime,
}

impl ConsensusMembership {
    #[must_use]
    pub fn new(cluster_id: impl Into<String>, members: Vec<ConsensusMember>) -> Self {
        Self {
            cluster_id: cluster_id.into(),
            configuration_id: EventId::new(),
            term: 1,
            leader_id: None,
            members,
            created_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn quorum_size(&self) -> usize {
        self.voting_members().len() / 2 + 1
    }

    #[must_use]
    pub fn voting_members(&self) -> Vec<&ConsensusMember> {
        self.members.iter().filter(|member| member.voting).collect()
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.cluster_id.trim().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus cluster id is required".to_owned(),
            });
        }
        let mut seen = BTreeSet::new();
        for member in &self.members {
            if member.member_id.trim().is_empty() {
                return Err(MindError::DistributedPlanInvalid {
                    reason: "consensus member id is required".to_owned(),
                });
            }
            if !seen.insert(member.member_id.clone()) {
                return Err(MindError::DistributedPlanInvalid {
                    reason: format!("duplicate consensus member `{}`", member.member_id),
                });
            }
        }
        if self.voting_members().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus membership requires at least one voting member".to_owned(),
            });
        }
        if let Some(leader_id) = &self.leader_id {
            if !self
                .members
                .iter()
                .any(|member| &member.member_id == leader_id)
            {
                return Err(MindError::DistributedPlanInvalid {
                    reason: "consensus leader is not a configured member".to_owned(),
                });
            }
        }
        Ok(())
    }

    pub fn apply_change(&self, change: ConsensusMembershipChange) -> MindResult<Self> {
        self.validate()?;
        let mut next = self.clone();
        next.configuration_id = EventId::new();
        next.term += 1;
        next.created_at = OffsetDateTime::now_utc();
        match change {
            ConsensusMembershipChange::AddMember { member } => {
                if next
                    .members
                    .iter()
                    .any(|existing| existing.member_id == member.member_id)
                {
                    return Err(MindError::DistributedPlanInvalid {
                        reason: format!("consensus member `{}` already exists", member.member_id),
                    });
                }
                next.members.push(member);
            }
            ConsensusMembershipChange::RemoveMember { member_id } => {
                next.members.retain(|member| member.member_id != member_id);
                if next.leader_id.as_deref() == Some(member_id.as_str()) {
                    next.leader_id = None;
                }
            }
            ConsensusMembershipChange::PromoteToVoter { member_id } => {
                let Some(member) = next
                    .members
                    .iter_mut()
                    .find(|member| member.member_id == member_id)
                else {
                    return Err(MindError::DistributedPlanInvalid {
                        reason: format!("consensus member `{member_id}` not found"),
                    });
                };
                member.voting = true;
                member.role = ConsensusMemberRole::Voter;
            }
            ConsensusMembershipChange::DemoteToLearner { member_id } => {
                let Some(member) = next
                    .members
                    .iter_mut()
                    .find(|member| member.member_id == member_id)
                else {
                    return Err(MindError::DistributedPlanInvalid {
                        reason: format!("consensus member `{member_id}` not found"),
                    });
                };
                member.voting = false;
                member.role = ConsensusMemberRole::Learner;
                if next.leader_id.as_deref() == Some(member_id.as_str()) {
                    next.leader_id = None;
                }
            }
            ConsensusMembershipChange::SetLeader { member_id } => {
                if !next
                    .members
                    .iter()
                    .any(|member| member.member_id == member_id && member.voting)
                {
                    return Err(MindError::DistributedPlanInvalid {
                        reason: "consensus leader must be a voting member".to_owned(),
                    });
                }
                next.leader_id = Some(member_id);
            }
        }
        next.validate()?;
        Ok(next)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum ConsensusMembershipChange {
    AddMember { member: ConsensusMember },
    RemoveMember { member_id: String },
    PromoteToVoter { member_id: String },
    DemoteToLearner { member_id: String },
    SetLeader { member_id: String },
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ElectionVote {
    pub term: u64,
    pub voter_id: String,
    pub candidate_id: String,
    pub granted: bool,
    pub voted_at: OffsetDateTime,
}

impl ElectionVote {
    #[must_use]
    pub fn grant(term: u64, voter_id: impl Into<String>, candidate_id: impl Into<String>) -> Self {
        Self {
            term,
            voter_id: voter_id.into(),
            candidate_id: candidate_id.into(),
            granted: true,
            voted_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ElectionTally {
    pub term: u64,
    pub candidate_id: String,
    pub granted_votes: usize,
    pub rejected_votes: usize,
    pub quorum_size: usize,
    pub elected: bool,
}

impl ElectionTally {
    pub fn tally(
        membership: &ConsensusMembership,
        term: u64,
        candidate_id: impl Into<String>,
        votes: &[ElectionVote],
    ) -> MindResult<Self> {
        membership.validate()?;
        let candidate_id = candidate_id.into();
        if !membership
            .members
            .iter()
            .any(|member| member.member_id == candidate_id && member.voting)
        {
            return Err(MindError::DistributedPlanInvalid {
                reason: "election candidate must be a voting member".to_owned(),
            });
        }
        let voting: BTreeSet<String> = membership
            .voting_members()
            .into_iter()
            .map(|member| member.member_id.clone())
            .collect();
        let granted_votes = votes
            .iter()
            .filter(|vote| {
                vote.term == term
                    && vote.candidate_id == candidate_id
                    && vote.granted
                    && voting.contains(&vote.voter_id)
            })
            .count();
        let rejected_votes = votes
            .iter()
            .filter(|vote| {
                vote.term == term
                    && vote.candidate_id == candidate_id
                    && !vote.granted
                    && voting.contains(&vote.voter_id)
            })
            .count();
        let quorum_size = membership.quorum_size();
        Ok(Self {
            term,
            candidate_id,
            granted_votes,
            rejected_votes,
            quorum_size,
            elected: granted_votes >= quorum_size,
        })
    }
}
