use crate::{Mind, MindId, SymbolState, SymbolValue};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum ProjectionScope {
    Summary,
    #[default]
    Public,
    Internal,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProjectionPolicy {
    pub scope: ProjectionScope,
    pub expose_state: bool,
    pub allow_keys: BTreeSet<String>,
    pub deny_keys: BTreeSet<String>,
    pub deny_prefixes: Vec<String>,
    pub deny_contains: Vec<String>,
    pub redact_denied: bool,
}

impl ProjectionPolicy {
    #[must_use]
    pub fn for_scope(scope: ProjectionScope) -> Self {
        match scope {
            ProjectionScope::Summary => Self::summary(),
            ProjectionScope::Public => Self::public_default(),
            ProjectionScope::Internal => Self::internal(),
        }
    }

    #[must_use]
    pub fn summary() -> Self {
        Self {
            scope: ProjectionScope::Summary,
            expose_state: false,
            allow_keys: BTreeSet::new(),
            deny_keys: BTreeSet::new(),
            deny_prefixes: Vec::new(),
            deny_contains: Vec::new(),
            redact_denied: false,
        }
    }

    #[must_use]
    pub fn public_default() -> Self {
        Self {
            scope: ProjectionScope::Public,
            expose_state: true,
            allow_keys: BTreeSet::new(),
            deny_keys: BTreeSet::from([
                "password".to_owned(),
                "api_key".to_owned(),
                "access_token".to_owned(),
                "refresh_token".to_owned(),
            ]),
            deny_prefixes: vec![
                "auth.".to_owned(),
                "internal.".to_owned(),
                "private.".to_owned(),
                "secret.".to_owned(),
            ],
            deny_contains: vec![
                "password".to_owned(),
                "secret".to_owned(),
                "token".to_owned(),
                "credential".to_owned(),
            ],
            redact_denied: false,
        }
    }

    #[must_use]
    pub fn internal() -> Self {
        Self {
            scope: ProjectionScope::Internal,
            expose_state: true,
            allow_keys: BTreeSet::new(),
            deny_keys: BTreeSet::new(),
            deny_prefixes: Vec::new(),
            deny_contains: Vec::new(),
            redact_denied: false,
        }
    }

    #[must_use]
    pub fn allows_key(&self, key: &str) -> bool {
        if !self.expose_state {
            return false;
        }

        if !self.allow_keys.is_empty() && !self.allow_keys.contains(key) {
            return false;
        }

        let key_lower = key.to_ascii_lowercase();

        if self
            .deny_keys
            .iter()
            .any(|denied| denied.eq_ignore_ascii_case(key))
        {
            return false;
        }

        if self
            .deny_prefixes
            .iter()
            .any(|prefix| key_lower.starts_with(&prefix.to_ascii_lowercase()))
        {
            return false;
        }

        if self
            .deny_contains
            .iter()
            .any(|needle| key_lower.contains(&needle.to_ascii_lowercase()))
        {
            return false;
        }

        true
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MindProjection {
    pub id: MindId,
    pub parent_id: Option<MindId>,
    pub kind: String,
    pub scope: ProjectionScope,
    pub state: SymbolState,
    pub history_len: usize,
    pub children: Vec<MindProjectionSummary>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MindProjectionSummary {
    pub id: MindId,
    pub kind: String,
    pub history_len: usize,
    pub child_count: usize,
}

impl MindProjection {
    #[must_use]
    pub fn with_policy(mind: &Mind, policy: &ProjectionPolicy) -> Self {
        let children = mind
            .children()
            .values()
            .map(MindProjectionSummary::from)
            .collect();

        Self {
            id: mind.id(),
            parent_id: mind.identity().parent_id,
            kind: mind.identity().kind.clone(),
            scope: policy.scope.clone(),
            state: projected_state(mind.state(), policy),
            history_len: mind.history().len(),
            children,
        }
    }
}

impl From<&Mind> for MindProjection {
    fn from(mind: &Mind) -> Self {
        Self::with_policy(mind, &ProjectionPolicy::public_default())
    }
}

impl From<&Mind> for MindProjectionSummary {
    fn from(mind: &Mind) -> Self {
        Self {
            id: mind.id(),
            kind: mind.identity().kind.clone(),
            history_len: mind.history().len(),
            child_count: mind.children().len(),
        }
    }
}

fn projected_state(state: &SymbolState, policy: &ProjectionPolicy) -> SymbolState {
    let mut projected = SymbolState::new();

    if !policy.expose_state {
        return projected;
    }

    for (key, value) in state.cells() {
        if policy.allows_key(key) {
            projected.insert(key.clone(), value.clone());
        } else if policy.redact_denied {
            projected.insert(key.clone(), SymbolValue::Text("[redacted]".to_owned()));
        }
    }

    projected
}
