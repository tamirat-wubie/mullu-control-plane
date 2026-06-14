#![forbid(unsafe_code)]
//! Mullu Truth Kernel finite-domain substrate.
//!
//! Purpose: provide the first Rust-side, side-effect-free finite-domain proof
//! thread for exact projection and closure before any truth-state mutation.
//! Governance scope: deterministic domain membership, total finite constraint
//! evaluation, budget-bounded non-promotion, sandbox witness retention, and
//! adapter-gated truth admission.
//! Dependencies: serde for stable payloads, serde_json for canonical hashing,
//! and sha2 for deterministic identifiers.
//! Invariants: this crate does not mutate truth state; exact truth authority
//! requires `Pass` + `ExactResult` + sandbox witness + deterministic replay.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub const SANDBOX_ISOLATION_WITNESS_REF: &str = "witness:sandbox-isolated";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TruthKernelError {
    EmptyText(&'static str),
    DuplicateDomain(String),
    EmptyDomain(String),
    DuplicateDomainValue(String),
    MfidelAtomicityViolation(String),
    EmptyConstraint(String),
    UnknownConstraintDomain(String),
    ConstraintAssignmentScopeMismatch(String),
    ConstraintAssignmentValueUnknown(String),
    ProjectionVariableUnknown(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProofState {
    Pass,
    Fail,
    Unknown,
    BudgetUnknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ResultKind {
    ExactResult,
    ContradictionResult,
    BudgetExceededResult,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FiniteTruthDomain {
    pub variable_id: String,
    pub values: Vec<String>,
    pub source_ref: String,
    pub includes_mfidel: bool,
    pub mfidel_atomicity_preserved: bool,
}

impl FiniteTruthDomain {
    pub fn new(variable_id: &str, values: Vec<&str>, source_ref: &str) -> Self {
        Self {
            variable_id: variable_id.to_string(),
            values: values.into_iter().map(str::to_string).collect(),
            source_ref: source_ref.to_string(),
            includes_mfidel: false,
            mfidel_atomicity_preserved: true,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FiniteTruthConstraint {
    pub constraint_id: String,
    pub scope: Vec<String>,
    pub source_ref: String,
    pub statement: String,
    pub allowed_assignments: Vec<BTreeMap<String, String>>,
    pub forbidden_assignments: Vec<BTreeMap<String, String>>,
}

impl FiniteTruthConstraint {
    pub fn allowed(
        constraint_id: &str,
        scope: Vec<&str>,
        source_ref: &str,
        statement: &str,
        assignments: Vec<BTreeMap<String, String>>,
    ) -> Self {
        Self {
            constraint_id: constraint_id.to_string(),
            scope: scope.into_iter().map(str::to_string).collect(),
            source_ref: source_ref.to_string(),
            statement: statement.to_string(),
            allowed_assignments: assignments,
            forbidden_assignments: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FinitePropagationReport {
    pub proof_state: ProofState,
    pub result_kind: ResultKind,
    pub projected_values: BTreeMap<String, Vec<String>>,
    pub pruned_values: BTreeMap<String, Vec<String>>,
    pub forced_values: BTreeMap<String, String>,
    pub checked_state_count: usize,
    pub valid_state_count: usize,
    pub kernel_signature: String,
    pub closure_hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FiniteProjectionProof {
    pub proof_id: String,
    pub tenant_id: String,
    pub proof_state: ProofState,
    pub result_kind: ResultKind,
    pub kernel_signature: String,
    pub subject_ref: String,
    pub projection_variable_id: String,
    pub projection_values: Vec<String>,
    pub checked_state_count: usize,
    pub valid_state_count: usize,
    pub witness_refs: Vec<String>,
    pub deterministic_replay: bool,
    pub expected_replay_hash: String,
    pub limitations: Vec<String>,
    pub proof_hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FiniteTruthKernel {
    domains: BTreeMap<String, FiniteTruthDomain>,
    constraints: Vec<FiniteTruthConstraint>,
    kernel_signature: String,
}

impl FiniteTruthKernel {
    pub fn new(
        domains: Vec<FiniteTruthDomain>,
        constraints: Vec<FiniteTruthConstraint>,
    ) -> Result<Self, TruthKernelError> {
        if domains.is_empty() {
            return Err(TruthKernelError::EmptyDomain("kernel".to_string()));
        }

        let mut domain_map = BTreeMap::new();
        for domain in domains {
            validate_non_empty("variable_id", &domain.variable_id)?;
            validate_non_empty("source_ref", &domain.source_ref)?;
            if domain.values.is_empty() {
                return Err(TruthKernelError::EmptyDomain(domain.variable_id));
            }
            let mut seen = BTreeSet::new();
            for value in &domain.values {
                validate_non_empty("domain_value", value)?;
                if !seen.insert(value.clone()) {
                    return Err(TruthKernelError::DuplicateDomainValue(domain.variable_id));
                }
            }
            if domain.includes_mfidel && !domain.mfidel_atomicity_preserved {
                return Err(TruthKernelError::MfidelAtomicityViolation(
                    domain.variable_id,
                ));
            }
            if domain_map
                .insert(domain.variable_id.clone(), domain)
                .is_some()
            {
                return Err(TruthKernelError::DuplicateDomain("domain".to_string()));
            }
        }

        validate_constraints(&domain_map, &constraints)?;
        let kernel_signature = stable_identifier(
            "truth-kernel-signature",
            &serde_json::json!({
                "domains": domain_map,
                "constraints": constraints,
            }),
        );
        Ok(Self {
            domains: domain_map,
            constraints,
            kernel_signature,
        })
    }

    pub fn kernel_signature(&self) -> &str {
        &self.kernel_signature
    }

    pub fn propagate(&self, budget_limit: usize) -> FinitePropagationReport {
        let total_state_count = self.total_state_count();
        if total_state_count > budget_limit {
            return self.build_propagation_report(
                budget_limit,
                &[],
                ProofState::BudgetUnknown,
                ResultKind::BudgetExceededResult,
            );
        }

        let mut valid_states = Vec::new();
        let states = self.candidate_states();
        for state in &states {
            if self.satisfies_constraints(state) {
                valid_states.push(state.clone());
            }
        }

        let result_kind = if valid_states.is_empty() {
            ResultKind::ContradictionResult
        } else {
            ResultKind::ExactResult
        };
        self.build_propagation_report(states.len(), &valid_states, ProofState::Pass, result_kind)
    }

    pub fn exact_projection(
        &self,
        variable_id: &str,
        tenant_id: &str,
        proof_id: &str,
        subject_ref: &str,
        budget_limit: usize,
    ) -> Result<FiniteProjectionProof, TruthKernelError> {
        validate_non_empty("variable_id", variable_id)?;
        validate_non_empty("tenant_id", tenant_id)?;
        validate_non_empty("proof_id", proof_id)?;
        validate_non_empty("subject_ref", subject_ref)?;
        if !self.domains.contains_key(variable_id) {
            return Err(TruthKernelError::ProjectionVariableUnknown(
                variable_id.to_string(),
            ));
        }

        let report = self.propagate(budget_limit);
        let projection_values = report
            .projected_values
            .get(variable_id)
            .cloned()
            .unwrap_or_default();
        let limitations = match report.result_kind {
            ResultKind::BudgetExceededResult => {
                vec!["budget_exceeded_before_exact_projection".to_string()]
            }
            _ => Vec::new(),
        };
        let witness_refs = witness_refs_from_report(&report, &limitations);
        let replay_basis = serde_json::json!({
            "kernel_signature": self.kernel_signature,
            "variable_id": variable_id,
            "projection_values": projection_values,
            "checked_state_count": report.checked_state_count,
            "valid_state_count": report.valid_state_count,
            "result_kind": report.result_kind,
            "limitations": limitations,
        });
        let expected_replay_hash = stable_identifier("truth-kernel-replay", &replay_basis);
        let proof_without_hash = serde_json::json!({
            "proof_id": proof_id,
            "tenant_id": tenant_id,
            "proof_state": report.proof_state,
            "result_kind": report.result_kind,
            "kernel_signature": self.kernel_signature,
            "subject_ref": subject_ref,
            "projection_variable_id": variable_id,
            "projection_values": projection_values,
            "checked_state_count": report.checked_state_count,
            "valid_state_count": report.valid_state_count,
            "witness_refs": witness_refs,
            "deterministic_replay": true,
            "expected_replay_hash": expected_replay_hash,
            "limitations": limitations,
        });
        let proof_hash = stable_identifier("kernel-proof", &proof_without_hash);

        Ok(FiniteProjectionProof {
            proof_id: proof_id.to_string(),
            tenant_id: tenant_id.to_string(),
            proof_state: report.proof_state,
            result_kind: report.result_kind,
            kernel_signature: self.kernel_signature.clone(),
            subject_ref: subject_ref.to_string(),
            projection_variable_id: variable_id.to_string(),
            projection_values,
            checked_state_count: report.checked_state_count,
            valid_state_count: report.valid_state_count,
            witness_refs,
            deterministic_replay: true,
            expected_replay_hash,
            limitations,
            proof_hash,
        })
    }

    pub fn projection_kernel_proof_payload(
        &self,
        variable_id: &str,
        tenant_id: &str,
        proof_id: &str,
        subject_ref: &str,
        generated_at: &str,
        budget_limit: usize,
    ) -> Result<serde_json::Value, TruthKernelError> {
        validate_non_empty("generated_at", generated_at)?;
        let proof =
            self.exact_projection(variable_id, tenant_id, proof_id, subject_ref, budget_limit)?;
        let supports_truth_mutation = proof.result_kind == ResultKind::ExactResult;
        let payload_without_hash = serde_json::json!({
            "proof_id": proof.proof_id,
            "tenant_id": proof.tenant_id,
            "proof_kind": "ProjectionProof",
            "proof_state": proof.proof_state,
            "result_kind": proof.result_kind,
            "kernel_signature": proof.kernel_signature,
            "subject_ref": proof.subject_ref,
            "generated_at": generated_at,
            "premises": self.premises(),
            "derivation_steps": self.projection_derivation_steps(
                variable_id,
                proof.checked_state_count,
                &proof.projection_values,
                proof.result_kind,
            ),
            "conclusion": {
                "statement": projection_statement(
                    variable_id,
                    &proof.projection_values,
                    proof.result_kind,
                ),
                "supports_truth_mutation": supports_truth_mutation,
                "required_next_action": if supports_truth_mutation {
                    "commit_candidate"
                } else {
                    "plan_sensing"
                },
            },
            "witness_refs": proof.witness_refs,
            "replay": {
                "replay_mode": "observation_only",
                "deterministic": proof.deterministic_replay,
                "source_hash": self.kernel_signature,
                "expected_hash": proof.expected_replay_hash,
                "reason_codes": proof.limitations,
            },
            "budget": {
                "budget_id": format!("budget:{}", proof_id),
                "limit": budget_limit,
                "used": proof.checked_state_count,
                "unit": "checks",
            },
            "limitations": proof.limitations,
        });
        let proof_hash = stable_identifier("kernel-proof", &payload_without_hash);
        let mut payload = payload_without_hash;
        payload["proof_hash"] = serde_json::Value::String(proof_hash);
        Ok(payload)
    }

    fn total_state_count(&self) -> usize {
        self.domains
            .values()
            .map(|domain| domain.values.len())
            .product()
    }

    fn candidate_states(&self) -> Vec<BTreeMap<String, String>> {
        let variables: Vec<String> = self.domains.keys().cloned().collect();
        let mut states = Vec::new();
        self.expand_state(&variables, 0, &mut BTreeMap::new(), &mut states);
        states
    }

    fn expand_state(
        &self,
        variables: &[String],
        index: usize,
        current: &mut BTreeMap<String, String>,
        states: &mut Vec<BTreeMap<String, String>>,
    ) {
        if index == variables.len() {
            states.push(current.clone());
            return;
        }
        let variable_id = &variables[index];
        let domain = &self.domains[variable_id];
        for value in &domain.values {
            current.insert(variable_id.clone(), value.clone());
            self.expand_state(variables, index + 1, current, states);
        }
        current.remove(variable_id);
    }

    fn satisfies_constraints(&self, state: &BTreeMap<String, String>) -> bool {
        self.constraints
            .iter()
            .all(|constraint| constraint_satisfied(constraint, state))
    }

    fn build_propagation_report(
        &self,
        checked_state_count: usize,
        valid_states: &[BTreeMap<String, String>],
        proof_state: ProofState,
        result_kind: ResultKind,
    ) -> FinitePropagationReport {
        let mut projected_values = BTreeMap::new();
        let mut pruned_values = BTreeMap::new();
        let mut forced_values = BTreeMap::new();

        for (variable_id, domain) in &self.domains {
            let mut projected: Vec<String> = valid_states
                .iter()
                .filter_map(|state| state.get(variable_id).cloned())
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect();
            projected.sort();
            let pruned: Vec<String> = domain
                .values
                .iter()
                .filter(|value| !projected.contains(value))
                .cloned()
                .collect();
            if result_kind == ResultKind::ExactResult && projected.len() == 1 {
                forced_values.insert(variable_id.clone(), projected[0].clone());
            }
            projected_values.insert(variable_id.clone(), projected);
            pruned_values.insert(variable_id.clone(), pruned);
        }

        let closure_payload = serde_json::json!({
            "kernel_signature": self.kernel_signature,
            "proof_state": proof_state,
            "result_kind": result_kind,
            "projected_values": projected_values,
            "pruned_values": pruned_values,
            "forced_values": forced_values,
            "checked_state_count": checked_state_count,
            "valid_state_count": valid_states.len(),
        });
        let closure_hash = stable_identifier("truth-kernel-closure", &closure_payload);
        FinitePropagationReport {
            proof_state,
            result_kind,
            projected_values,
            pruned_values,
            forced_values,
            checked_state_count,
            valid_state_count: valid_states.len(),
            kernel_signature: self.kernel_signature.clone(),
            closure_hash,
        }
    }

    fn premises(&self) -> Vec<serde_json::Value> {
        let mut premises: Vec<serde_json::Value> = self
            .domains
            .values()
            .map(|domain| {
                serde_json::json!({
                    "premise_id": format!("premise-domain:{}", domain.variable_id),
                    "premise_kind": "domain",
                    "source_ref": domain.source_ref,
                    "statement": format!(
                        "{} has {} declared finite values.",
                        domain.variable_id,
                        domain.values.len(),
                    ),
                })
            })
            .collect();
        premises.extend(self.constraints.iter().map(|constraint| {
            serde_json::json!({
                "premise_id": format!("premise-constraint:{}", constraint.constraint_id),
                "premise_kind": "constraint",
                "source_ref": constraint.source_ref,
                "statement": constraint.statement,
            })
        }));
        premises
    }

    fn projection_derivation_steps(
        &self,
        variable_id: &str,
        checked_state_count: usize,
        projection_values: &[String],
        result_kind: ResultKind,
    ) -> Vec<serde_json::Value> {
        let domain_refs: Vec<String> = self
            .domains
            .keys()
            .map(|variable_id| format!("premise-domain:{}", variable_id))
            .collect();
        let mut constraint_input_refs: Vec<String> = self
            .constraints
            .iter()
            .map(|constraint| format!("premise-constraint:{}", constraint.constraint_id))
            .collect();
        constraint_input_refs.push("step-enumerate-finite-domain".to_string());
        vec![
            serde_json::json!({
                "step_id": "step-enumerate-finite-domain",
                "rule_ref": "rule:finite-domain-enumeration",
                "input_refs": domain_refs,
                "output_statement": format!(
                    "Enumerated {} candidate states within declared budget.",
                    checked_state_count,
                ),
            }),
            serde_json::json!({
                "step_id": "step-apply-finite-constraints",
                "rule_ref": "rule:total-finite-constraint-check",
                "input_refs": constraint_input_refs,
                "output_statement": format!("Constraint evaluation produced {:?}.", result_kind),
            }),
            serde_json::json!({
                "step_id": "step-project-variable",
                "rule_ref": "rule:exact-finite-projection",
                "input_refs": ["step-apply-finite-constraints"],
                "output_statement": format!(
                    "{} projects to {:?}.",
                    variable_id,
                    projection_values,
                ),
            }),
        ]
    }
}

fn validate_constraints(
    domains: &BTreeMap<String, FiniteTruthDomain>,
    constraints: &[FiniteTruthConstraint],
) -> Result<(), TruthKernelError> {
    for constraint in constraints {
        validate_non_empty("constraint_id", &constraint.constraint_id)?;
        validate_non_empty("source_ref", &constraint.source_ref)?;
        validate_non_empty("statement", &constraint.statement)?;
        if constraint.allowed_assignments.is_empty() && constraint.forbidden_assignments.is_empty()
        {
            return Err(TruthKernelError::EmptyConstraint(
                constraint.constraint_id.clone(),
            ));
        }
        for variable_id in &constraint.scope {
            if !domains.contains_key(variable_id) {
                return Err(TruthKernelError::UnknownConstraintDomain(
                    variable_id.clone(),
                ));
            }
        }
        for assignment in constraint
            .allowed_assignments
            .iter()
            .chain(constraint.forbidden_assignments.iter())
        {
            validate_assignment(domains, constraint, assignment)?;
        }
    }
    Ok(())
}

fn validate_assignment(
    domains: &BTreeMap<String, FiniteTruthDomain>,
    constraint: &FiniteTruthConstraint,
    assignment: &BTreeMap<String, String>,
) -> Result<(), TruthKernelError> {
    let scope_set: BTreeSet<String> = constraint.scope.iter().cloned().collect();
    let assignment_set: BTreeSet<String> = assignment.keys().cloned().collect();
    if scope_set != assignment_set {
        return Err(TruthKernelError::ConstraintAssignmentScopeMismatch(
            constraint.constraint_id.clone(),
        ));
    }
    for (variable_id, value) in assignment {
        if !domains[variable_id].values.contains(value) {
            return Err(TruthKernelError::ConstraintAssignmentValueUnknown(
                variable_id.clone(),
            ));
        }
    }
    Ok(())
}

fn constraint_satisfied(
    constraint: &FiniteTruthConstraint,
    state: &BTreeMap<String, String>,
) -> bool {
    let scoped: BTreeMap<String, String> = constraint
        .scope
        .iter()
        .filter_map(|variable_id| {
            state
                .get(variable_id)
                .map(|value| (variable_id.clone(), value.clone()))
        })
        .collect();

    if !constraint.allowed_assignments.is_empty()
        && !constraint
            .allowed_assignments
            .iter()
            .any(|item| item == &scoped)
    {
        return false;
    }
    !constraint
        .forbidden_assignments
        .iter()
        .any(|item| item == &scoped)
}

fn witness_refs_from_report(
    report: &FinitePropagationReport,
    limitations: &[String],
) -> Vec<String> {
    if let Some(first) = limitations.first() {
        return vec![
            SANDBOX_ISOLATION_WITNESS_REF.to_string(),
            format!("limitation:{}", first),
        ];
    }
    if report.result_kind == ResultKind::ContradictionResult {
        return vec![
            SANDBOX_ISOLATION_WITNESS_REF.to_string(),
            "witness:no-valid-state".to_string(),
        ];
    }
    let mut refs = vec![SANDBOX_ISOLATION_WITNESS_REF.to_string()];
    for (variable_id, projected) in &report.projected_values {
        refs.push(stable_identifier(
            "witness-projection",
            &serde_json::json!({
                "kernel_signature": report.kernel_signature,
                "variable_id": variable_id,
                "projected_values": projected,
            }),
        ));
    }
    refs
}

fn projection_statement(
    variable_id: &str,
    projection_values: &[String],
    result_kind: ResultKind,
) -> String {
    match result_kind {
        ResultKind::BudgetExceededResult => {
            format!(
                "Budget ended before exact projection for {} could be proven.",
                variable_id
            )
        }
        ResultKind::ContradictionResult => {
            format!("No valid finite-domain state remains for {}.", variable_id)
        }
        ResultKind::ExactResult => {
            format!(
                "Exact projection for {} is {:?}.",
                variable_id, projection_values
            )
        }
    }
}

fn validate_non_empty(field: &'static str, value: &str) -> Result<(), TruthKernelError> {
    if value.trim().is_empty() {
        return Err(TruthKernelError::EmptyText(field));
    }
    Ok(())
}

fn stable_identifier(prefix: &str, value: &serde_json::Value) -> String {
    let canonical = serde_json::to_string(value).expect("serde_json::Value serialization is total");
    format!("{}-{}", prefix, sha256_hex(&canonical))
}

fn sha256_hex(input: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assignment(pairs: &[(&str, &str)]) -> BTreeMap<String, String> {
        pairs
            .iter()
            .map(|(key, value)| (key.to_string(), value.to_string()))
            .collect()
    }

    fn color_kernel() -> FiniteTruthKernel {
        FiniteTruthKernel::new(
            vec![FiniteTruthDomain::new(
                "var:color",
                vec!["red", "blue", "green"],
                "domain:color",
            )],
            vec![FiniteTruthConstraint::allowed(
                "constraint:color-red-blue",
                vec!["var:color"],
                "constraint:color-red-blue",
                "Color must be red or blue.",
                vec![
                    assignment(&[("var:color", "red")]),
                    assignment(&[("var:color", "blue")]),
                ],
            )],
        )
        .unwrap()
    }

    fn finite_projection_summary(
        proof: &FiniteProjectionProof,
        variable_id: &str,
        budget_limit: usize,
    ) -> serde_json::Value {
        serde_json::json!({
            "summary_id": "truth-kernel-finite-projection-summary-v1",
            "runtime_boundary": "finite-domain-proof-summary",
            "tenant_id": proof.tenant_id,
            "proof_id": proof.proof_id,
            "subject_ref": proof.subject_ref,
            "variable_id": variable_id,
            "proof_state": proof.proof_state,
            "result_kind": proof.result_kind,
            "projection_values": proof.projection_values,
            "checked_state_count": proof.checked_state_count,
            "valid_state_count": proof.valid_state_count,
            "budget_limit": budget_limit,
            "limitations": proof.limitations,
            "sandbox_witness_present": proof
                .witness_refs
                .contains(&SANDBOX_ISOLATION_WITNESS_REF.to_string()),
            "deterministic_replay": proof.deterministic_replay,
            "truth_mutation_authority": "adapter_required",
        })
    }

    #[test]
    fn exact_projection_is_deterministic_and_sandbox_witnessed() {
        let first = color_kernel()
            .exact_projection(
                "var:color",
                "foundation-local",
                "kernel-proof:color",
                "truth-candidate:color",
                8,
            )
            .unwrap();
        let second = color_kernel()
            .exact_projection(
                "var:color",
                "foundation-local",
                "kernel-proof:color",
                "truth-candidate:color",
                8,
            )
            .unwrap();

        assert_eq!(first.proof_state, ProofState::Pass);
        assert_eq!(first.result_kind, ResultKind::ExactResult);
        assert_eq!(first.projection_values, vec!["blue", "red"]);
        assert_eq!(first.checked_state_count, 3);
        assert_eq!(first.valid_state_count, 2);
        assert!(first
            .witness_refs
            .contains(&SANDBOX_ISOLATION_WITNESS_REF.to_string()));
        assert!(first.deterministic_replay);
        assert_eq!(first.proof_hash, second.proof_hash);
        assert_eq!(first.expected_replay_hash, second.expected_replay_hash);
    }

    #[test]
    fn rust_finite_projection_summary_matches_cross_language_fixture() {
        let budget_limit = 8;
        let proof = color_kernel()
            .exact_projection(
                "var:color",
                "foundation-local",
                "kernel-proof:finite-domain-color-parity",
                "truth-candidate:finite-domain-color-parity",
                budget_limit,
            )
            .unwrap();
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../examples/truth_kernel/truth_kernel_finite_projection_summary.json"
        ));
        let expected: serde_json::Value = serde_json::from_str(fixture_json).unwrap();
        let summary = finite_projection_summary(&proof, "var:color", budget_limit);

        assert_eq!(summary, expected);
        assert_eq!(summary["sandbox_witness_present"], true);
        assert_eq!(summary["truth_mutation_authority"], "adapter_required");
        assert_eq!(
            summary["projection_values"],
            serde_json::json!(["blue", "red"])
        );
    }

    #[test]
    fn rust_projection_kernel_proof_payload_matches_schema_fixture() {
        let payload = color_kernel()
            .projection_kernel_proof_payload(
                "var:color",
                "foundation-local",
                "kernel-proof:rust-finite-domain-color",
                "truth-candidate:rust-finite-domain-color",
                "2026-06-14T00:13:00Z",
                8,
            )
            .unwrap();
        let fixture_json = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../../examples/truth_kernel/kernel_proof.rust_finite_projection.json"
        ));
        let expected: serde_json::Value = serde_json::from_str(fixture_json).unwrap();

        assert_eq!(payload, expected);
        assert_eq!(payload["proof_kind"], "ProjectionProof");
        assert_eq!(payload["proof_state"], "Pass");
        assert_eq!(payload["result_kind"], "ExactResult");
        assert_eq!(payload["conclusion"]["supports_truth_mutation"], true);
        assert_eq!(payload["replay"]["deterministic"], true);
        assert!(payload["witness_refs"]
            .as_array()
            .unwrap()
            .contains(&serde_json::json!(SANDBOX_ISOLATION_WITNESS_REF)));
    }

    #[test]
    fn propagation_prunes_values_and_is_monotonic() {
        let unconstrained = FiniteTruthKernel::new(
            vec![FiniteTruthDomain::new(
                "var:color",
                vec!["red", "blue", "green"],
                "domain:color",
            )],
            vec![],
        )
        .unwrap();
        let broad = unconstrained.propagate(4);
        let narrow = color_kernel().propagate(4);

        assert_eq!(
            broad.projected_values["var:color"],
            vec!["blue", "green", "red"]
        );
        assert_eq!(narrow.projected_values["var:color"], vec!["blue", "red"]);
        assert!(narrow.projected_values["var:color"]
            .iter()
            .all(|value| broad.projected_values["var:color"].contains(value)));
        assert_eq!(narrow.pruned_values["var:color"], vec!["green"]);
        assert!(narrow.forced_values.is_empty());
        assert_eq!(narrow.result_kind, ResultKind::ExactResult);
    }

    #[test]
    fn budget_exhaustion_cannot_emit_exact_projection() {
        let kernel = FiniteTruthKernel::new(
            vec![
                FiniteTruthDomain::new("var:left", vec!["a", "b", "c"], "domain:left"),
                FiniteTruthDomain::new("var:right", vec!["x", "y", "z"], "domain:right"),
            ],
            vec![],
        )
        .unwrap();

        let proof = kernel
            .exact_projection(
                "var:left",
                "foundation-local",
                "kernel-proof:budget",
                "truth-candidate:budget",
                4,
            )
            .unwrap();

        assert_eq!(proof.proof_state, ProofState::BudgetUnknown);
        assert_eq!(proof.result_kind, ResultKind::BudgetExceededResult);
        assert!(proof.projection_values.is_empty());
        assert_eq!(proof.checked_state_count, 4);
        assert_eq!(
            proof.limitations,
            vec!["budget_exceeded_before_exact_projection".to_string()]
        );
        assert!(proof
            .witness_refs
            .contains(&SANDBOX_ISOLATION_WITNESS_REF.to_string()));
    }

    #[test]
    fn contradiction_reports_no_valid_state_without_mutation_authority() {
        let kernel = FiniteTruthKernel::new(
            vec![FiniteTruthDomain::new(
                "var:color",
                vec!["red", "blue"],
                "domain:color",
            )],
            vec![FiniteTruthConstraint {
                constraint_id: "constraint:forbid-all".to_string(),
                scope: vec!["var:color".to_string()],
                source_ref: "constraint:forbid-all".to_string(),
                statement: "No color remains valid.".to_string(),
                allowed_assignments: Vec::new(),
                forbidden_assignments: vec![
                    assignment(&[("var:color", "red")]),
                    assignment(&[("var:color", "blue")]),
                ],
            }],
        )
        .unwrap();

        let proof = kernel
            .exact_projection(
                "var:color",
                "foundation-local",
                "kernel-proof:contradiction",
                "truth-candidate:contradiction",
                4,
            )
            .unwrap();

        assert_eq!(proof.proof_state, ProofState::Pass);
        assert_eq!(proof.result_kind, ResultKind::ContradictionResult);
        assert!(proof.projection_values.is_empty());
        assert_eq!(proof.valid_state_count, 0);
        assert_eq!(
            proof.witness_refs,
            vec![
                SANDBOX_ISOLATION_WITNESS_REF.to_string(),
                "witness:no-valid-state".to_string()
            ]
        );
    }

    #[test]
    fn mfidel_domain_requires_atomicity_preservation() {
        let mut domain = FiniteTruthDomain::new("var:mfidel", vec!["f[1][1]"], "domain:mfidel");
        domain.includes_mfidel = true;
        domain.mfidel_atomicity_preserved = false;
        let error = FiniteTruthKernel::new(vec![domain], vec![]).unwrap_err();

        assert_eq!(
            error,
            TruthKernelError::MfidelAtomicityViolation("var:mfidel".to_string())
        );
    }

    #[test]
    fn invalid_constraint_assignment_fails_closed() {
        let error = FiniteTruthKernel::new(
            vec![FiniteTruthDomain::new(
                "var:color",
                vec!["red", "blue"],
                "domain:color",
            )],
            vec![FiniteTruthConstraint::allowed(
                "constraint:unknown-color",
                vec!["var:color"],
                "constraint:unknown-color",
                "Color must be green.",
                vec![assignment(&[("var:color", "green")])],
            )],
        )
        .unwrap_err();

        assert_eq!(
            error,
            TruthKernelError::ConstraintAssignmentValueUnknown("var:color".to_string())
        );
    }
}
