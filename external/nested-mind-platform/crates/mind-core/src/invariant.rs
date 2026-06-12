use crate::{MindError, MindId, MindResult, PatchOp, StatePatch, SymbolState, SymbolValue};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Identity {
    pub id: MindId,
    pub parent_id: Option<MindId>,
    pub kind: String,
    pub created_at: OffsetDateTime,
    pub version: u64,
}

impl Identity {
    #[must_use]
    pub fn root(kind: impl Into<String>) -> Self {
        Self::root_with_id(MindId::new(), kind)
    }

    #[must_use]
    pub fn root_with_id(id: MindId, kind: impl Into<String>) -> Self {
        Self {
            id,
            parent_id: None,
            kind: kind.into(),
            created_at: OffsetDateTime::now_utc(),
            version: 1,
        }
    }

    #[must_use]
    pub fn child(parent_id: MindId, kind: impl Into<String>) -> Self {
        Self::child_with_id(MindId::new(), parent_id, kind)
    }

    #[must_use]
    pub fn child_with_id(id: MindId, parent_id: MindId, kind: impl Into<String>) -> Self {
        Self {
            id,
            parent_id: Some(parent_id),
            kind: kind.into(),
            created_at: OffsetDateTime::now_utc(),
            version: 1,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct InvariantSet {
    immutable_keys: BTreeSet<String>,
    required_keys: BTreeSet<String>,
    max_children: usize,
}

impl Default for InvariantSet {
    fn default() -> Self {
        Self {
            immutable_keys: BTreeSet::from([
                "identity.id".to_owned(),
                "identity.kind".to_owned(),
                "identity.parent_id".to_owned(),
            ]),
            required_keys: BTreeSet::from([
                "identity.id".to_owned(),
                "identity.kind".to_owned(),
                "system.version".to_owned(),
            ]),
            max_children: 256,
        }
    }
}

impl InvariantSet {
    #[must_use]
    pub fn max_children(&self) -> usize {
        self.max_children
    }

    #[must_use]
    pub fn immutable_keys(&self) -> &BTreeSet<String> {
        &self.immutable_keys
    }

    #[must_use]
    pub fn required_keys(&self) -> &BTreeSet<String> {
        &self.required_keys
    }

    pub fn validate_patch(&self, current: &SymbolState, patch: &StatePatch) -> MindResult<()> {
        if patch.is_empty() {
            return Err(MindError::EmptyPatch);
        }

        for op in patch.ops() {
            match op {
                PatchOp::Set { key, value } => {
                    self.validate_set(current, key, value)?;
                }
                PatchOp::Remove { key } => {
                    self.validate_remove(key)?;
                }
            }
        }

        Ok(())
    }

    fn validate_set(
        &self,
        current: &SymbolState,
        key: &str,
        value: &SymbolValue,
    ) -> MindResult<()> {
        if self.immutable_keys.contains(key) {
            if let Some(existing) = current.get(key) {
                if existing != value {
                    return Err(MindError::ImmutableKey(key.to_owned()));
                }
            }
        }
        Ok(())
    }

    fn validate_remove(&self, key: &str) -> MindResult<()> {
        if self.required_keys.contains(key) {
            return Err(MindError::RequiredKey(key.to_owned()));
        }
        if self.immutable_keys.contains(key) {
            return Err(MindError::ImmutableKey(key.to_owned()));
        }
        Ok(())
    }
}
