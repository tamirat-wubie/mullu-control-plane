use crate::MindResult;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(untagged)]
pub enum SymbolValue {
    Null,
    Bool(bool),
    Number(f64),
    Text(String),
    List(Vec<SymbolValue>),
    Map(BTreeMap<String, SymbolValue>),
}

impl From<&str> for SymbolValue {
    fn from(value: &str) -> Self {
        Self::Text(value.to_owned())
    }
}

impl From<String> for SymbolValue {
    fn from(value: String) -> Self {
        Self::Text(value)
    }
}

impl From<bool> for SymbolValue {
    fn from(value: bool) -> Self {
        Self::Bool(value)
    }
}

impl From<f64> for SymbolValue {
    fn from(value: f64) -> Self {
        Self::Number(value)
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct SymbolState {
    cells: BTreeMap<String, SymbolValue>,
}

impl SymbolState {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&mut self, key: impl Into<String>, value: SymbolValue) -> Option<SymbolValue> {
        self.cells.insert(key.into(), value)
    }

    #[must_use]
    pub fn get(&self, key: &str) -> Option<&SymbolValue> {
        self.cells.get(key)
    }

    #[must_use]
    pub fn contains_key(&self, key: &str) -> bool {
        self.cells.contains_key(key)
    }

    #[must_use]
    pub fn cells(&self) -> &BTreeMap<String, SymbolValue> {
        &self.cells
    }

    pub fn apply(&mut self, patch: &StatePatch) -> MindResult<()> {
        for op in patch.ops() {
            match op {
                PatchOp::Set { key, value } => {
                    self.cells.insert(key.clone(), value.clone());
                }
                PatchOp::Remove { key } => {
                    self.cells.remove(key);
                }
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct StatePatch {
    ops: Vec<PatchOp>,
}

impl StatePatch {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    #[must_use]
    pub fn from_ops(ops: Vec<PatchOp>) -> Self {
        Self { ops }
    }

    #[must_use]
    pub fn set(mut self, key: impl Into<String>, value: SymbolValue) -> Self {
        self.ops.push(PatchOp::Set {
            key: key.into(),
            value,
        });
        self
    }

    #[must_use]
    pub fn remove(mut self, key: impl Into<String>) -> Self {
        self.ops.push(PatchOp::Remove { key: key.into() });
        self
    }

    #[must_use]
    pub fn ops(&self) -> &[PatchOp] {
        &self.ops
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.ops.is_empty()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum PatchOp {
    Set { key: String, value: SymbolValue },
    Remove { key: String },
}
