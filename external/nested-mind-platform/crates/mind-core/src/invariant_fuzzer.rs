use crate::{
    hash_serializable, EditProposal, EventId, MindId, MindResult, StatePatch, SymbolValue,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum FuzzMutationClass {
    EmptyPatch,
    ImmutableIdentityChange,
    RequiredKeyRemoval,
    ForbiddenKeyInsertion,
    WrongTarget,
    ValidStateExpansion,
    ProjectionSecretLeakProbe,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InvariantFuzzCase {
    pub case_id: EventId,
    pub seed: u64,
    pub target_mind_id: MindId,
    pub class: FuzzMutationClass,
    pub proposal: EditProposal,
    pub expected_acceptance: bool,
    pub expected_rejection_contains: Option<String>,
    pub oracle: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct InvariantFuzzRunConfig {
    pub seed: u64,
    pub cases: usize,
    pub include_valid: bool,
    pub include_projection_probes: bool,
}

impl Default for InvariantFuzzRunConfig {
    fn default() -> Self {
        Self {
            seed: 17,
            cases: 24,
            include_valid: true,
            include_projection_probes: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InvariantFuzzRunReport {
    pub run_id: EventId,
    pub target_mind_id: MindId,
    pub config: InvariantFuzzRunConfig,
    #[serde(default)]
    pub cases: Vec<InvariantFuzzCase>,
    pub expected_accept_count: usize,
    pub expected_reject_count: usize,
    pub mutation_free_rejection_count: usize,
    pub case_bank_hash: String,
    pub generated_at: OffsetDateTime,
}

pub fn generate_invariant_fuzz_run(
    target_mind_id: MindId,
    config: InvariantFuzzRunConfig,
) -> MindResult<InvariantFuzzRunReport> {
    let mut seed = config.seed;
    let mut cases = Vec::new();
    for index in 0..config.cases.max(1) {
        seed = next_seed(seed);
        let class = select_class(seed, config.include_valid, config.include_projection_probes);
        cases.push(case_for(target_mind_id, seed, index, class));
    }
    let expected_accept_count = cases.iter().filter(|case| case.expected_acceptance).count();
    let expected_reject_count = cases.len().saturating_sub(expected_accept_count);
    let mutation_free_rejection_count = cases
        .iter()
        .filter(|case| !case.expected_acceptance)
        .filter(|case| {
            matches!(
                case.class,
                FuzzMutationClass::EmptyPatch | FuzzMutationClass::WrongTarget
            )
        })
        .count();
    let run_id = EventId::new();
    let generated_at = OffsetDateTime::now_utc();
    let case_bank_hash =
        hash_serializable(&(run_id, target_mind_id, &config, &cases, generated_at))?;
    Ok(InvariantFuzzRunReport {
        run_id,
        target_mind_id,
        config,
        cases,
        expected_accept_count,
        expected_reject_count,
        mutation_free_rejection_count,
        case_bank_hash,
        generated_at,
    })
}

fn case_for(
    target_mind_id: MindId,
    seed: u64,
    index: usize,
    class: FuzzMutationClass,
) -> InvariantFuzzCase {
    let actor = format!("fuzzer-{seed:016x}");
    let reason = format!("deterministic invariant fuzz case {index}");
    let proposal_mind_id = if class == FuzzMutationClass::WrongTarget {
        MindId::new()
    } else {
        target_mind_id
    };
    let patch = match class {
        FuzzMutationClass::EmptyPatch => StatePatch::new(),
        FuzzMutationClass::ImmutableIdentityChange => {
            StatePatch::new().set("identity.id", SymbolValue::from(format!("corrupt-{seed}")))
        }
        FuzzMutationClass::RequiredKeyRemoval => StatePatch::new().remove("identity.kind"),
        FuzzMutationClass::ForbiddenKeyInsertion => {
            StatePatch::new().set("password", SymbolValue::from(format!("forbidden-{seed}")))
        }
        FuzzMutationClass::WrongTarget => StatePatch::new().set(
            format!("fuzz.valid.{index}"),
            SymbolValue::from(format!("wrong-target-{seed}")),
        ),
        FuzzMutationClass::ValidStateExpansion => StatePatch::new().set(
            format!("fuzz.valid.{index}"),
            SymbolValue::from(format!("value-{seed}")),
        ),
        FuzzMutationClass::ProjectionSecretLeakProbe => StatePatch::new().set(
            format!("secret.fuzz.{index}"),
            SymbolValue::from(format!("secret-{seed}")),
        ),
    };
    let expected_acceptance = matches!(class, FuzzMutationClass::ValidStateExpansion);
    let expected_rejection_contains = match class {
        FuzzMutationClass::EmptyPatch => Some("empty".to_owned()),
        FuzzMutationClass::ImmutableIdentityChange => Some("immutable".to_owned()),
        FuzzMutationClass::RequiredKeyRemoval => Some("required".to_owned()),
        FuzzMutationClass::ForbiddenKeyInsertion => Some("forbidden".to_owned()),
        FuzzMutationClass::WrongTarget => Some("target".to_owned()),
        FuzzMutationClass::ProjectionSecretLeakProbe => Some("projection".to_owned()),
        FuzzMutationClass::ValidStateExpansion => None,
    };
    let oracle = if expected_acceptance {
        "accepted case must append, apply, replay, and preserve after_hash".to_owned()
    } else if class == FuzzMutationClass::ProjectionSecretLeakProbe {
        "proposal may be rejected by lawbook or must be hidden from public projection if accepted by a custom lawbook".to_owned()
    } else {
        "rejected case must not mutate state or event history".to_owned()
    };
    InvariantFuzzCase {
        case_id: EventId::new(),
        seed,
        target_mind_id,
        class,
        proposal: EditProposal::new(proposal_mind_id, actor, reason, patch),
        expected_acceptance,
        expected_rejection_contains,
        oracle,
    }
}

fn next_seed(seed: u64) -> u64 {
    seed.wrapping_mul(6364136223846793005)
        .wrapping_add(1442695040888963407)
}

fn select_class(
    seed: u64,
    include_valid: bool,
    include_projection_probes: bool,
) -> FuzzMutationClass {
    let modulo = if include_projection_probes { 7 } else { 6 };
    match seed % modulo {
        0 => FuzzMutationClass::EmptyPatch,
        1 => FuzzMutationClass::ImmutableIdentityChange,
        2 => FuzzMutationClass::RequiredKeyRemoval,
        3 => FuzzMutationClass::ForbiddenKeyInsertion,
        4 => FuzzMutationClass::WrongTarget,
        5 if include_valid => FuzzMutationClass::ValidStateExpansion,
        5 => FuzzMutationClass::ForbiddenKeyInsertion,
        _ => FuzzMutationClass::ProjectionSecretLeakProbe,
    }
}
