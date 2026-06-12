use crate::{CommitSignature, EventId, Identity, LawbookTransition, MindId, StatePatch};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct EditProposal {
    pub id: EventId,
    pub mind_id: MindId,
    pub actor: String,
    pub reason: String,
    pub patch: StatePatch,
    pub evidence: Vec<String>,
}

impl EditProposal {
    #[must_use]
    pub fn new(
        mind_id: MindId,
        actor: impl Into<String>,
        reason: impl Into<String>,
        patch: StatePatch,
    ) -> Self {
        Self {
            id: EventId::new(),
            mind_id,
            actor: actor.into(),
            reason: reason.into(),
            patch,
            evidence: Vec::new(),
        }
    }
    #[must_use]
    pub fn with_evidence(mut self, evidence: impl Into<String>) -> Self {
        self.evidence.push(evidence.into());
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Judgment {
    pub accepted: bool,
    pub rationale: String,
    pub constructive_delta: Vec<String>,
    pub fracture_delta: Vec<String>,
    pub law_trace: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum TopologyEffect {
    AttachChild { identity: Identity },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Commit {
    pub id: EventId,
    pub proposal_id: EventId,
    pub mind_id: MindId,
    pub parent_commit: Option<EventId>,
    pub actor: String,
    pub reason: String,
    pub at: OffsetDateTime,
    pub patch: StatePatch,
    #[serde(default)]
    pub topology: Vec<TopologyEffect>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lawbook_transition: Option<LawbookTransition>,
    pub before_hash: String,
    pub after_hash: String,
    pub judgment: Judgment,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signature: Option<CommitSignature>,
}
