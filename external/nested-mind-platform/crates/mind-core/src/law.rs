use crate::{hash_serializable, EventId, LawId, MindError, MindResult, SymbolState};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Lawbook {
    id: LawId,
    version: u64,
    rules: Vec<LawRule>,
}

impl Lawbook {
    #[must_use]
    pub fn base_symbolic() -> Self {
        Self {
            id: base_law_id(),
            version: 1,
            rules: vec![
                LawRule::RequireKey {
                    key: "identity.id".to_owned(),
                },
                LawRule::RequireKey {
                    key: "identity.kind".to_owned(),
                },
                LawRule::RequireKey {
                    key: "system.version".to_owned(),
                },
                LawRule::ImmutableKey {
                    key: "identity.id".to_owned(),
                },
                LawRule::ImmutableKey {
                    key: "identity.kind".to_owned(),
                },
            ],
        }
    }

    #[must_use]
    pub fn from_rules(id: LawId, version: u64, rules: Vec<LawRule>) -> Self {
        Self { id, version, rules }
    }

    #[must_use]
    pub fn id(&self) -> LawId {
        self.id
    }

    #[must_use]
    pub fn version(&self) -> u64 {
        self.version
    }

    #[must_use]
    pub fn rules(&self) -> &[LawRule] {
        &self.rules
    }

    pub fn hash(&self) -> MindResult<String> {
        hash_serializable(self)
    }

    pub fn validate_state(&self, state: &SymbolState) -> MindResult<()> {
        for rule in &self.rules {
            match rule {
                LawRule::RequireKey { key } if !state.contains_key(key) => {
                    return Err(MindError::MissingRequiredKey(key.clone()))
                }
                LawRule::ForbidKey { key } if state.contains_key(key) => {
                    return Err(MindError::ForbiddenKey(key.clone()))
                }
                LawRule::RequireKey { .. }
                | LawRule::ForbidKey { .. }
                | LawRule::ImmutableKey { .. } => {}
            }
        }
        Ok(())
    }

    pub fn apply_migration(&self, migration: LawbookMigration) -> MindResult<LawbookTransition> {
        if migration.from_version != self.version {
            return Err(MindError::LawbookMigrationVersionMismatch {
                current: self.version,
                from: migration.from_version,
            });
        }
        let expected_to = self.version + 1;
        if migration.to_version != expected_to {
            return Err(MindError::LawbookMigrationTargetVersion {
                expected: expected_to,
                to: migration.to_version,
            });
        }
        if migration.operations.is_empty() {
            return Err(MindError::LawbookMigrationEmpty);
        }

        let before_hash = self.hash()?;
        let mut next = self.clone();
        next.version = migration.to_version;

        for operation in &migration.operations {
            match operation {
                LawbookMigrationOp::AddRule { rule } => {
                    if !next.rules.contains(rule) {
                        next.rules.push(rule.clone());
                    }
                }
                LawbookMigrationOp::RemoveRule { rule } => {
                    if rule.is_foundation_rule() && !migration.allow_foundation_removal {
                        return Err(MindError::LawbookMigrationUnsafeRemoval {
                            rule: rule.clone(),
                        });
                    }
                    next.rules.retain(|existing| existing != rule);
                }
            }
        }

        let after_hash = next.hash()?;
        Ok(LawbookTransition {
            migration,
            before_hash,
            after_hash,
            after: next,
        })
    }

    #[must_use]
    pub fn trace(&self) -> Vec<String> {
        let mut trace = vec![format!("lawbook(id={}, version={})", self.id, self.version)];
        trace.extend(self.rules.iter().map(ToString::to_string));
        trace
    }
}

impl Default for Lawbook {
    fn default() -> Self {
        Self::base_symbolic()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum LawRule {
    RequireKey { key: String },
    ForbidKey { key: String },
    ImmutableKey { key: String },
}

impl LawRule {
    #[must_use]
    pub fn is_foundation_rule(&self) -> bool {
        matches!(self, Self::RequireKey { key } if matches!(key.as_str(), "identity.id" | "identity.kind" | "system.version"))
            || matches!(self, Self::ImmutableKey { key } if matches!(key.as_str(), "identity.id" | "identity.kind" | "identity.parent_id"))
    }
}

impl std::fmt::Display for LawRule {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::RequireKey { key } => write!(f, "require_key({key})"),
            Self::ForbidKey { key } => write!(f, "forbid_key({key})"),
            Self::ImmutableKey { key } => write!(f, "immutable_key({key})"),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LawbookMigration {
    pub id: EventId,
    pub from_version: u64,
    pub to_version: u64,
    pub actor: String,
    pub reason: String,
    pub operations: Vec<LawbookMigrationOp>,
    #[serde(default)]
    pub allow_foundation_removal: bool,
    pub created_at: OffsetDateTime,
}

impl LawbookMigration {
    #[must_use]
    pub fn new(
        from_version: u64,
        to_version: u64,
        actor: impl Into<String>,
        reason: impl Into<String>,
        operations: Vec<LawbookMigrationOp>,
    ) -> Self {
        Self {
            id: EventId::new(),
            from_version,
            to_version,
            actor: actor.into(),
            reason: reason.into(),
            operations,
            allow_foundation_removal: false,
            created_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn with_foundation_removal(mut self) -> Self {
        self.allow_foundation_removal = true;
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum LawbookMigrationOp {
    AddRule { rule: LawRule },
    RemoveRule { rule: LawRule },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LawbookTransition {
    pub migration: LawbookMigration,
    pub before_hash: String,
    pub after_hash: String,
    pub after: Lawbook,
}

impl LawbookTransition {
    pub fn verify_against(&self, current: &Lawbook) -> MindResult<()> {
        let transition = current.apply_migration(self.migration.clone())?;
        if transition.before_hash != self.before_hash {
            return Err(MindError::LawbookTransitionHashMismatch {
                expected: transition.before_hash,
                actual: self.before_hash.clone(),
            });
        }
        if transition.after_hash != self.after_hash {
            return Err(MindError::LawbookTransitionHashMismatch {
                expected: transition.after_hash,
                actual: self.after_hash.clone(),
            });
        }
        let embedded_after_hash = self.after.hash()?;
        if embedded_after_hash != self.after_hash {
            return Err(MindError::LawbookTransitionHashMismatch {
                expected: self.after_hash.clone(),
                actual: embedded_after_hash,
            });
        }
        Ok(())
    }
}

fn base_law_id() -> LawId {
    LawId::parse_str("00000000-0000-0000-0000-000000000101")
        .expect("static base law id must be valid")
}
