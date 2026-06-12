use crate::{MindResult, SymbolState};
use serde::Serialize;
use sha2::{Digest, Sha256};

pub fn hash_state(state: &SymbolState) -> MindResult<String> {
    hash_serializable(state)
}

pub fn hash_serializable<T>(value: &T) -> MindResult<String>
where
    T: Serialize,
{
    let bytes = serde_json::to_vec(value)?;
    let digest = Sha256::digest(bytes);
    Ok(hex::encode(digest))
}
