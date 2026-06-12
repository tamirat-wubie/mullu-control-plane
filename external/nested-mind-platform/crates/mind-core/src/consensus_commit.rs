use crate::{hash_serializable, ConsensusMembership, EventId, MindError, MindResult};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusLogEntry {
    pub entry_id: EventId,
    pub cluster_id: String,
    pub configuration_id: EventId,
    pub term: u64,
    pub leader_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub previous_entry_hash: Option<String>,
    pub operation_kind: String,
    pub operation_hash: String,
    pub operation_json: String,
    pub entry_hash: String,
    pub proposed_at: OffsetDateTime,
}

impl ConsensusLogEntry {
    pub fn new<T: Serialize>(
        membership: &ConsensusMembership,
        leader_id: impl Into<String>,
        operation_kind: impl Into<String>,
        operation: &T,
        previous_entry_hash: Option<String>,
    ) -> MindResult<Self> {
        membership.validate()?;
        let leader_id = leader_id.into();
        if !membership
            .members
            .iter()
            .any(|member| member.member_id == leader_id && member.voting)
        {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus log leader must be a voting member".to_owned(),
            });
        }
        let operation_kind = operation_kind.into();
        if operation_kind.trim().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus log operation kind is required".to_owned(),
            });
        }
        let operation_json = serde_json::to_string(operation)?;
        let operation_hash = hash_serializable(operation)?;
        let mut entry = Self {
            entry_id: EventId::new(),
            cluster_id: membership.cluster_id.clone(),
            configuration_id: membership.configuration_id,
            term: membership.term,
            leader_id,
            previous_entry_hash,
            operation_kind,
            operation_hash,
            operation_json,
            entry_hash: String::new(),
            proposed_at: OffsetDateTime::now_utc(),
        };
        entry.entry_hash = entry.calculate_entry_hash()?;
        Ok(entry)
    }

    pub fn calculate_entry_hash(&self) -> MindResult<String> {
        #[derive(Serialize)]
        struct Body<'a> {
            entry_id: EventId,
            cluster_id: &'a str,
            configuration_id: EventId,
            term: u64,
            leader_id: &'a str,
            previous_entry_hash: &'a Option<String>,
            operation_kind: &'a str,
            operation_hash: &'a str,
            operation_json: &'a str,
            proposed_at: OffsetDateTime,
        }
        hash_serializable(&Body {
            entry_id: self.entry_id,
            cluster_id: &self.cluster_id,
            configuration_id: self.configuration_id,
            term: self.term,
            leader_id: &self.leader_id,
            previous_entry_hash: &self.previous_entry_hash,
            operation_kind: &self.operation_kind,
            operation_hash: &self.operation_hash,
            operation_json: &self.operation_json,
            proposed_at: self.proposed_at,
        })
    }

    pub fn verify(&self, membership: &ConsensusMembership) -> MindResult<()> {
        membership.validate()?;
        if self.cluster_id != membership.cluster_id
            || self.configuration_id != membership.configuration_id
            || self.term != membership.term
        {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus log entry does not match current membership".to_owned(),
            });
        }
        if !membership
            .members
            .iter()
            .any(|member| member.member_id == self.leader_id && member.voting)
        {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus log entry leader is not a voting member".to_owned(),
            });
        }
        let expected = self.calculate_entry_hash()?;
        if expected != self.entry_hash {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus log entry hash mismatch".to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusCommitVote {
    pub vote_id: EventId,
    pub entry_id: EventId,
    pub voter_id: String,
    pub term: u64,
    pub entry_hash: String,
    pub accepted: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    pub voted_at: OffsetDateTime,
}

impl ConsensusCommitVote {
    #[must_use]
    pub fn accept(entry: &ConsensusLogEntry, voter_id: impl Into<String>) -> Self {
        Self {
            vote_id: EventId::new(),
            entry_id: entry.entry_id,
            voter_id: voter_id.into(),
            term: entry.term,
            entry_hash: entry.entry_hash.clone(),
            accepted: true,
            reason: None,
            voted_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn reject(
        entry: &ConsensusLogEntry,
        voter_id: impl Into<String>,
        reason: impl Into<String>,
    ) -> Self {
        Self {
            vote_id: EventId::new(),
            entry_id: entry.entry_id,
            voter_id: voter_id.into(),
            term: entry.term,
            entry_hash: entry.entry_hash.clone(),
            accepted: false,
            reason: Some(reason.into()),
            voted_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusCommitCertificate {
    pub certificate_id: EventId,
    pub entry: ConsensusLogEntry,
    #[serde(default)]
    pub votes: Vec<ConsensusCommitVote>,
    pub required_quorum: usize,
    pub accepted_votes: usize,
    pub committed: bool,
    pub certified_at: OffsetDateTime,
}

impl ConsensusCommitCertificate {
    pub fn certify(
        membership: &ConsensusMembership,
        entry: ConsensusLogEntry,
        votes: Vec<ConsensusCommitVote>,
    ) -> MindResult<Self> {
        entry.verify(membership)?;
        let voting_members: BTreeSet<String> = membership
            .voting_members()
            .into_iter()
            .map(|member| member.member_id.clone())
            .collect();
        let mut seen = BTreeSet::new();
        let mut accepted_votes = 0;
        for vote in &votes {
            if vote.entry_id != entry.entry_id
                || vote.term != entry.term
                || vote.entry_hash != entry.entry_hash
            {
                return Err(MindError::DistributedPlanInvalid {
                    reason: "consensus commit vote does not match entry".to_owned(),
                });
            }
            if !voting_members.contains(&vote.voter_id) {
                return Err(MindError::DistributedPlanInvalid {
                    reason: format!(
                        "consensus commit voter `{}` is not a voting member",
                        vote.voter_id
                    ),
                });
            }
            if !seen.insert(vote.voter_id.clone()) {
                return Err(MindError::DistributedPlanInvalid {
                    reason: format!("duplicate consensus commit vote from `{}`", vote.voter_id),
                });
            }
            if vote.accepted {
                accepted_votes += 1;
            }
        }
        let required_quorum = membership.quorum_size();
        Ok(Self {
            certificate_id: EventId::new(),
            entry,
            votes,
            required_quorum,
            accepted_votes,
            committed: accepted_votes >= required_quorum,
            certified_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn verify(&self, membership: &ConsensusMembership) -> MindResult<()> {
        let expected = Self::certify(membership, self.entry.clone(), self.votes.clone())?;
        if expected.required_quorum != self.required_quorum
            || expected.accepted_votes != self.accepted_votes
            || expected.committed != self.committed
        {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus commit certificate quorum mismatch".to_owned(),
            });
        }
        Ok(())
    }
}
