#![forbid(unsafe_code)]
//! MAF Core capability types — cross-domain capability abstractions.
//!
//! Purpose: define generic capability descriptors, effect classes, determinism classes,
//! and trust classes that verticals specialize but do not redefine.
//!
//! Governance: maps to schemas/capability_descriptor.schema.json and docs/06_capability_planes.md.
//! Invariants: capability classifications are explicit and frozen per the audit.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

// ---------------------------------------------------------------------------
// Effect class — what kind of side effects a capability may produce
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectClass {
    InternalPure,
    ExternalRead,
    ExternalWrite,
    HumanMediated,
    Privileged,
}

// ---------------------------------------------------------------------------
// Determinism class — how predictable a capability's output is
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DeterminismClass {
    Deterministic,
    InputBounded,
    RecordedNondeterministic,
}

// ---------------------------------------------------------------------------
// Trust class — how much the platform trusts the capability's source
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TrustClass {
    TrustedInternal,
    BoundedExternal,
    UntrustedExternal,
}

// ---------------------------------------------------------------------------
// Verification strength — how strongly the capability's output is verified
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VerificationStrength {
    None,
    Weak,
    Moderate,
    Strong,
    Mandatory,
}

// ---------------------------------------------------------------------------
// Lifecycle state — where the capability is in its lifecycle
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LifecycleState {
    Candidate,
    Provisional,
    Verified,
    Trusted,
    Deprecated,
    Blocked,
}

// ---------------------------------------------------------------------------
// Capability constraint
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilityConstraint {
    pub key: String,
    pub value: String,
}

// ---------------------------------------------------------------------------
// Capability descriptor — maps to schemas/capability_descriptor.schema.json
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilityDescriptor {
    pub capability_id: String,
    pub subject_id: String,
    pub name: String,
    pub version: String,
    pub scope: String,
    #[serde(default)]
    pub constraints: Vec<String>,
    #[serde(default)]
    pub risk_tier: String,
    #[serde(default)]
    pub declared_effects: Vec<String>,
    #[serde(default)]
    pub forbidden_effects: Vec<String>,
    #[serde(default)]
    pub evidence_required: Vec<String>,
    #[serde(default)]
    pub rollback: BTreeMap<String, serde_json::Value>,
    #[serde(default)]
    pub graph_projection: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extensions: BTreeMap<String, serde_json::Value>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::de::DeserializeOwned;

    fn assert_fixture_round_trip<T>(fixture_json: &str)
    where
        T: DeserializeOwned + Serialize,
    {
        let fixture_value: serde_json::Value = serde_json::from_str(fixture_json).unwrap();
        let parsed: T = serde_json::from_str(fixture_json).unwrap();
        let round_trip_value = serde_json::to_value(parsed).unwrap();
        assert_eq!(fixture_value, round_trip_value);
    }

    #[test]
    fn effect_class_serializes_to_snake_case() {
        let json = serde_json::to_string(&EffectClass::ExternalRead).unwrap();
        assert_eq!(json, r#""external_read""#);
    }

    #[test]
    fn determinism_class_serializes_to_snake_case() {
        let json = serde_json::to_string(&DeterminismClass::InputBounded).unwrap();
        assert_eq!(json, r#""input_bounded""#);
    }

    #[test]
    fn trust_class_serializes_to_snake_case() {
        let json = serde_json::to_string(&TrustClass::BoundedExternal).unwrap();
        assert_eq!(json, r#""bounded_external""#);
    }

    #[test]
    fn lifecycle_serializes_to_snake_case() {
        let json = serde_json::to_string(&LifecycleState::Deprecated).unwrap();
        assert_eq!(json, r#""deprecated""#);
    }

    #[test]
    fn capability_descriptor_round_trips() {
        let descriptor = CapabilityDescriptor {
            capability_id: "cap-1".into(),
            subject_id: "agent-1".into(),
            name: "shell_execute".into(),
            version: "1.0.0".into(),
            scope: "local".into(),
            constraints: vec!["os=linux".into()],
            risk_tier: "low".into(),
            declared_effects: vec!["command_output_created".into()],
            forbidden_effects: vec!["unauthorized_state_mutation".into()],
            evidence_required: vec!["output_hash".into()],
            rollback: BTreeMap::new(),
            graph_projection: BTreeMap::new(),
            metadata: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        let json = serde_json::to_string(&descriptor).unwrap();
        let restored: CapabilityDescriptor = serde_json::from_str(&json).unwrap();
        assert_eq!(descriptor, restored);
        assert!(json.contains("\"constraints\":[\"os=linux\"]"));
    }

    #[test]
    fn capability_descriptor_minimal() {
        let descriptor = CapabilityDescriptor {
            capability_id: "cap-2".into(),
            subject_id: "agent-1".into(),
            name: "read_file".into(),
            version: "1.0.0".into(),
            scope: "local".into(),
            constraints: vec!["read_only".into()],
            risk_tier: String::new(),
            declared_effects: Vec::new(),
            forbidden_effects: Vec::new(),
            evidence_required: Vec::new(),
            rollback: BTreeMap::new(),
            graph_projection: BTreeMap::new(),
            metadata: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        let json = serde_json::to_string(&descriptor).unwrap();
        assert!(!json.contains("metadata"));
        assert!(!json.contains("extensions"));
        let restored: CapabilityDescriptor = serde_json::from_str(&json).unwrap();
        assert_eq!(descriptor, restored);
        assert!(json.contains("\"constraints\":[\"read_only\"]"));
    }

    #[test]
    fn canonical_capability_fixture_round_trips() {
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../integration/contracts_compat/fixtures/capability_descriptor.json"
        ));
        assert_fixture_round_trip::<CapabilityDescriptor>(fixture_json);
    }
}
