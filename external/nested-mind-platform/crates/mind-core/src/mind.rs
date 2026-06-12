use crate::{
    Commit, Identity, InvariantSet, Lawbook, MindError, MindId, MindResult, SymbolState,
    SymbolValue,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Mind {
    identity: Identity,
    invariants: InvariantSet,
    lawbook: Lawbook,
    state: SymbolState,
    children: BTreeMap<MindId, Mind>,
    history: Vec<Commit>,
}

impl Mind {
    #[must_use]
    pub fn new_root(kind: impl Into<String>) -> Self {
        Self::from_identity(Identity::root(kind))
    }

    #[must_use]
    pub fn new_child(parent_id: MindId, kind: impl Into<String>) -> Self {
        Self::from_identity(Identity::child(parent_id, kind))
    }

    #[must_use]
    pub fn from_identity(identity: Identity) -> Self {
        let lawbook = Lawbook::default();
        let mut state = SymbolState::new();
        state.insert("identity.id", SymbolValue::Text(identity.id.to_string()));
        state.insert("identity.kind", SymbolValue::Text(identity.kind.clone()));
        state.insert(
            "identity.parent_id",
            identity
                .parent_id
                .map(|id| SymbolValue::Text(id.to_string()))
                .unwrap_or(SymbolValue::Null),
        );
        state.insert(
            "system.version",
            SymbolValue::Number(identity.version as f64),
        );
        state.insert("lawbook.id", SymbolValue::Text(lawbook.id().to_string()));
        state.insert(
            "lawbook.version",
            SymbolValue::Number(lawbook.version() as f64),
        );
        state.insert(
            "lawbook.hash",
            SymbolValue::Text(lawbook.hash().expect("base lawbook serializes")),
        );
        Self {
            identity,
            invariants: InvariantSet::default(),
            lawbook,
            state,
            children: BTreeMap::new(),
            history: Vec::new(),
        }
    }

    #[must_use]
    pub fn id(&self) -> MindId {
        self.identity.id
    }

    #[must_use]
    pub fn identity(&self) -> &Identity {
        &self.identity
    }

    #[must_use]
    pub fn invariants(&self) -> &InvariantSet {
        &self.invariants
    }

    #[must_use]
    pub fn lawbook(&self) -> &Lawbook {
        &self.lawbook
    }

    #[must_use]
    pub fn state(&self) -> &SymbolState {
        &self.state
    }

    #[must_use]
    pub fn children(&self) -> &BTreeMap<MindId, Mind> {
        &self.children
    }

    #[must_use]
    pub fn history(&self) -> &[Commit] {
        &self.history
    }

    #[must_use]
    pub fn latest_commit_id(&self) -> Option<crate::EventId> {
        self.history.last().map(|commit| commit.id)
    }

    pub(crate) fn add_child(&mut self, child: Mind) -> MindResult<()> {
        if self.children.len() >= self.invariants.max_children() {
            return Err(MindError::MaxChildren {
                max_children: self.invariants.max_children(),
            });
        }
        if child.identity.parent_id != Some(self.id()) {
            return Err(MindError::WrongParent {
                child_parent: child.identity.parent_id,
                target_parent: self.id(),
            });
        }
        if self.children.contains_key(&child.id()) {
            return Err(MindError::DuplicateChild(child.id()));
        }
        self.children.insert(child.id(), child);
        Ok(())
    }

    pub(crate) fn replace_state(&mut self, state: SymbolState) {
        self.state = state;
    }

    pub(crate) fn replace_lawbook(&mut self, lawbook: Lawbook) {
        self.lawbook = lawbook;
    }

    pub(crate) fn push_commit(&mut self, commit: Commit) {
        self.history.push(commit);
    }

    pub(crate) fn from_restored_parts(
        identity: Identity,
        lawbook: Lawbook,
        state: SymbolState,
        children: Vec<Mind>,
        history: Vec<Commit>,
    ) -> MindResult<Self> {
        let mut mind = Self {
            identity,
            invariants: InvariantSet::default(),
            lawbook,
            state,
            children: BTreeMap::new(),
            history,
        };
        for child in children {
            mind.add_child(child)?;
        }
        Ok(mind)
    }
}
