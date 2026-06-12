use crate::{
    hash_serializable, ConsensusMembership, ConsensusMembershipChange, EventId, MindError,
    MindResult,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusChangeProposal {
    pub proposal_id: EventId,
    pub cluster_id: String,
    pub expected_configuration_id: EventId,
    pub expected_term: u64,
    pub actor: String,
    pub reason: String,
    #[serde(default)]
    pub changes: Vec<ConsensusMembershipChange>,
    pub proposed_at: OffsetDateTime,
}

impl ConsensusChangeProposal {
    #[must_use]
    pub fn new(
        current: &ConsensusMembership,
        actor: impl Into<String>,
        reason: impl Into<String>,
        changes: Vec<ConsensusMembershipChange>,
    ) -> Self {
        Self {
            proposal_id: EventId::new(),
            cluster_id: current.cluster_id.clone(),
            expected_configuration_id: current.configuration_id,
            expected_term: current.term,
            actor: actor.into(),
            reason: reason.into(),
            changes,
            proposed_at: OffsetDateTime::now_utc(),
        }
    }

    pub fn validate_against(&self, current: &ConsensusMembership) -> MindResult<()> {
        current.validate()?;
        if self.cluster_id != current.cluster_id {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus change proposal targets a different cluster".to_owned(),
            });
        }
        if self.expected_configuration_id != current.configuration_id {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus change expected configuration id is stale".to_owned(),
            });
        }
        if self.expected_term != current.term {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus change expected term is stale".to_owned(),
            });
        }
        if self.actor.trim().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus change actor is required".to_owned(),
            });
        }
        if self.reason.trim().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus change reason is required".to_owned(),
            });
        }
        if self.changes.is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus change proposal contains no operations".to_owned(),
            });
        }
        Ok(())
    }

    pub fn evaluate(&self, current: &ConsensusMembership) -> MindResult<ConsensusChangeJudgment> {
        self.validate_against(current)?;
        let before_hash = hash_serializable(current)?;
        let mut next = current.clone();
        for change in self.changes.clone() {
            next = next.apply_change(change)?;
        }
        let after_hash = hash_serializable(&next)?;
        Ok(ConsensusChangeJudgment {
            proposal_id: self.proposal_id,
            cluster_id: self.cluster_id.clone(),
            accepted: true,
            actor: self.actor.clone(),
            reason: self.reason.clone(),
            before_configuration_id: current.configuration_id,
            after_configuration_id: next.configuration_id,
            before_term: current.term,
            after_term: next.term,
            before_hash,
            after_hash,
            resulting_membership: next,
            decided_at: OffsetDateTime::now_utc(),
            notes: Vec::new(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusChangeJudgment {
    pub proposal_id: EventId,
    pub cluster_id: String,
    pub accepted: bool,
    pub actor: String,
    pub reason: String,
    pub before_configuration_id: EventId,
    pub after_configuration_id: EventId,
    pub before_term: u64,
    pub after_term: u64,
    pub before_hash: String,
    pub after_hash: String,
    pub resulting_membership: ConsensusMembership,
    pub decided_at: OffsetDateTime,
    #[serde(default)]
    pub notes: Vec<String>,
}

impl ConsensusChangeJudgment {
    pub fn verify_transition(&self, before: &ConsensusMembership) -> MindResult<()> {
        before.validate()?;
        if self.before_configuration_id != before.configuration_id {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus judgment before configuration mismatch".to_owned(),
            });
        }
        let expected_before_hash = hash_serializable(before)?;
        if expected_before_hash != self.before_hash {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus judgment before hash mismatch".to_owned(),
            });
        }
        let expected_after_hash = hash_serializable(&self.resulting_membership)?;
        if expected_after_hash != self.after_hash {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus judgment after hash mismatch".to_owned(),
            });
        }
        Ok(())
    }
}
