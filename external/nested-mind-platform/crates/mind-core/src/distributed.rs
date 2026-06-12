use crate::{MindError, MindResult};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum EventStoreConsistencyModel {
    SingleWriter,
    LeaderReplicated,
    Quorum,
    Consensus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EventStoreReplica {
    pub replica_id: String,
    pub region: String,
    pub writable: bool,
    pub priority: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedEventStoreStrategy {
    pub strategy_id: String,
    pub consistency_model: EventStoreConsistencyModel,
    #[serde(default)]
    pub replicas: Vec<EventStoreReplica>,
    pub write_quorum: usize,
    pub read_quorum: usize,
    pub require_monotonic_sequence: bool,
    pub require_hash_chain: bool,
}

impl DistributedEventStoreStrategy {
    #[must_use]
    pub fn single_node() -> Self {
        Self {
            strategy_id: "single-node".to_owned(),
            consistency_model: EventStoreConsistencyModel::SingleWriter,
            replicas: vec![EventStoreReplica {
                replica_id: "primary".to_owned(),
                region: "local".to_owned(),
                writable: true,
                priority: 0,
            }],
            write_quorum: 1,
            read_quorum: 1,
            require_monotonic_sequence: true,
            require_hash_chain: true,
        }
    }

    #[must_use]
    pub fn quorum(
        strategy_id: impl Into<String>,
        replicas: Vec<EventStoreReplica>,
        write_quorum: usize,
        read_quorum: usize,
    ) -> Self {
        Self {
            strategy_id: strategy_id.into(),
            consistency_model: EventStoreConsistencyModel::Quorum,
            replicas,
            write_quorum,
            read_quorum,
            require_monotonic_sequence: true,
            require_hash_chain: true,
        }
    }

    pub fn validate(&self) -> MindResult<()> {
        let writable = self
            .replicas
            .iter()
            .filter(|replica| replica.writable)
            .count();
        if self.replicas.is_empty() {
            return Err(MindError::DistributedAppendRejected {
                reason: "no event-store replicas configured".to_owned(),
            });
        }
        if self.write_quorum == 0 || self.write_quorum > writable {
            return Err(MindError::QuorumNotMet {
                required: self.write_quorum,
                accepted: writable,
            });
        }
        if self.read_quorum == 0 || self.read_quorum > self.replicas.len() {
            return Err(MindError::DistributedAppendRejected {
                reason: "read quorum is outside configured replica count".to_owned(),
            });
        }
        Ok(())
    }

    pub fn evaluate_append(
        &self,
        receipts: Vec<ReplicaAppendReceipt>,
    ) -> MindResult<DistributedAppendDecision> {
        self.validate()?;
        let accepted: Vec<&ReplicaAppendReceipt> =
            receipts.iter().filter(|receipt| receipt.accepted).collect();
        if accepted.len() < self.write_quorum {
            return Err(MindError::QuorumNotMet {
                required: self.write_quorum,
                accepted: accepted.len(),
            });
        }
        let canonical_sequence = accepted.first().and_then(|receipt| receipt.sequence);
        let canonical_record_hash = accepted
            .first()
            .and_then(|receipt| receipt.record_hash.clone());
        if self.require_monotonic_sequence {
            if let Some(sequence) = canonical_sequence {
                if accepted
                    .iter()
                    .any(|receipt| receipt.sequence != Some(sequence))
                {
                    return Err(MindError::DistributedAppendRejected {
                        reason: "replica sequence mismatch".to_owned(),
                    });
                }
            }
        }
        if self.require_hash_chain {
            if let Some(record_hash) = canonical_record_hash.as_ref() {
                if accepted
                    .iter()
                    .any(|receipt| receipt.record_hash.as_ref() != Some(record_hash))
                {
                    return Err(MindError::DistributedAppendRejected {
                        reason: "replica record-hash mismatch".to_owned(),
                    });
                }
            }
        }
        Ok(DistributedAppendDecision {
            strategy_id: self.strategy_id.clone(),
            quorum_met: true,
            required_quorum: self.write_quorum,
            accepted_count: accepted.len(),
            rejected_count: receipts.len().saturating_sub(accepted.len()),
            canonical_sequence,
            canonical_record_hash,
            receipts,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicaAppendReceipt {
    pub replica_id: String,
    pub accepted: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sequence: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub record_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl ReplicaAppendReceipt {
    #[must_use]
    pub fn accepted(
        replica_id: impl Into<String>,
        sequence: u64,
        record_hash: impl Into<String>,
    ) -> Self {
        Self {
            replica_id: replica_id.into(),
            accepted: true,
            sequence: Some(sequence),
            record_hash: Some(record_hash.into()),
            error: None,
        }
    }

    #[must_use]
    pub fn rejected(replica_id: impl Into<String>, error: impl Into<String>) -> Self {
        Self {
            replica_id: replica_id.into(),
            accepted: false,
            sequence: None,
            record_hash: None,
            error: Some(error.into()),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedAppendDecision {
    pub strategy_id: String,
    pub quorum_met: bool,
    pub required_quorum: usize,
    pub accepted_count: usize,
    pub rejected_count: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub canonical_sequence: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub canonical_record_hash: Option<String>,
    #[serde(default)]
    pub receipts: Vec<ReplicaAppendReceipt>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum EventStoreStrategy {
    SingleWriter,
    LeaderReplicated,
    ConsensusReplicated,
    ObjectArchivedFollower,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum DistributedNodeRole {
    Single,
    Leader,
    Follower,
    Witness,
    Learner,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedEventStorePlan {
    pub strategy: EventStoreStrategy,
    pub node_id: String,
    pub role: DistributedNodeRole,
    pub voting_members: u16,
    pub quorum_size: u16,
    pub allow_local_appends: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub replication_lag_limit_events: Option<u64>,
}

impl DistributedEventStorePlan {
    #[must_use]
    pub fn single_writer(node_id: impl Into<String>) -> Self {
        Self {
            strategy: EventStoreStrategy::SingleWriter,
            node_id: node_id.into(),
            role: DistributedNodeRole::Single,
            voting_members: 1,
            quorum_size: 1,
            allow_local_appends: true,
            replication_lag_limit_events: Some(0),
        }
    }

    #[must_use]
    pub fn leader(node_id: impl Into<String>, voting_members: u16) -> Self {
        let voting_members = voting_members.max(1);
        Self {
            strategy: EventStoreStrategy::LeaderReplicated,
            node_id: node_id.into(),
            role: DistributedNodeRole::Leader,
            voting_members,
            quorum_size: 1,
            allow_local_appends: true,
            replication_lag_limit_events: Some(128),
        }
    }

    #[must_use]
    pub fn follower(node_id: impl Into<String>, voting_members: u16) -> Self {
        let voting_members = voting_members.max(1);
        Self {
            strategy: EventStoreStrategy::LeaderReplicated,
            node_id: node_id.into(),
            role: DistributedNodeRole::Follower,
            voting_members,
            quorum_size: 1,
            allow_local_appends: false,
            replication_lag_limit_events: Some(128),
        }
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.node_id.trim().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "node_id is required".to_owned(),
            });
        }
        if self.voting_members == 0 {
            return Err(MindError::DistributedPlanInvalid {
                reason: "voting_members must be greater than zero".to_owned(),
            });
        }
        if self.quorum_size == 0 || self.quorum_size > self.voting_members {
            return Err(MindError::DistributedPlanInvalid {
                reason: "quorum_size must be within voting_members".to_owned(),
            });
        }
        if matches!(self.strategy, EventStoreStrategy::ConsensusReplicated)
            && self.quorum_size < (self.voting_members / 2 + 1)
        {
            return Err(MindError::QuorumNotMet {
                required: (self.voting_members / 2 + 1) as usize,
                accepted: self.quorum_size as usize,
            });
        }
        Ok(())
    }

    pub fn validate_append_authority(&self) -> MindResult<()> {
        self.validate()?;
        if !self.allow_local_appends {
            return Err(MindError::DistributedWriteRejected {
                node_id: self.node_id.clone(),
                role: format!("{:?}", self.role),
                strategy: format!("{:?}", self.strategy),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClusterHealthReport {
    pub strategy: EventStoreStrategy,
    pub node_id: String,
    pub role: DistributedNodeRole,
    pub voting_members: u16,
    pub quorum_size: u16,
    pub append_authorized: bool,
    pub event_store_writable: bool,
    pub valid: bool,
    #[serde(default)]
    pub notes: Vec<String>,
}

impl ClusterHealthReport {
    pub fn from_plan(plan: DistributedEventStorePlan) -> MindResult<Self> {
        let mut notes = Vec::new();
        plan.validate()?;
        if !plan.allow_local_appends {
            notes.push("local node is read-only/follower for append operations".to_owned());
        }
        Ok(Self {
            strategy: plan.strategy,
            node_id: plan.node_id,
            role: plan.role,
            voting_members: plan.voting_members,
            quorum_size: plan.quorum_size,
            append_authorized: plan.allow_local_appends,
            event_store_writable: plan.allow_local_appends,
            valid: true,
            notes,
        })
    }
}
