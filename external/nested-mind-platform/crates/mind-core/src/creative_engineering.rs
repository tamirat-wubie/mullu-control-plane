use crate::{hash_serializable, EventId, MindResult, PLATFORM_SCHEMA_VERSION};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum EngineeringArea {
    Kernel,
    Storage,
    Identity,
    Scheduler,
    ProviderBoundary,
    Consensus,
    Projection,
    Observability,
    Operations,
    DeveloperExperience,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum EngineeringPriority {
    Critical,
    High,
    Medium,
    Low,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum EngineeringEffort {
    Small,
    Medium,
    Large,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum EngineeringRisk {
    Low,
    Medium,
    High,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct EngineeringAssumption {
    pub key: String,
    pub value: String,
    pub confidence: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CreativeEngineeringSuggestion {
    pub suggestion_id: EventId,
    pub area: EngineeringArea,
    pub title: String,
    pub mechanism: String,
    pub invariant_guard: String,
    pub implementation_delta: String,
    pub validation_probe: String,
    pub rollback_plan: String,
    pub priority: EngineeringPriority,
    pub effort: EngineeringEffort,
    pub risk: EngineeringRisk,
    pub priority_score: i64,
    #[serde(default)]
    pub depends_on: Vec<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    pub created_at: OffsetDateTime,
}

impl CreativeEngineeringSuggestion {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        area: EngineeringArea,
        title: impl Into<String>,
        mechanism: impl Into<String>,
        invariant_guard: impl Into<String>,
        implementation_delta: impl Into<String>,
        validation_probe: impl Into<String>,
        rollback_plan: impl Into<String>,
        priority: EngineeringPriority,
        effort: EngineeringEffort,
        risk: EngineeringRisk,
        tags: Vec<String>,
    ) -> Self {
        let priority_score = score(priority, effort, risk);
        Self {
            suggestion_id: EventId::new(),
            area,
            title: title.into(),
            mechanism: mechanism.into(),
            invariant_guard: invariant_guard.into(),
            implementation_delta: implementation_delta.into(),
            validation_probe: validation_probe.into(),
            rollback_plan: rollback_plan.into(),
            priority,
            effort,
            risk,
            priority_score,
            depends_on: Vec::new(),
            tags,
            created_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CreativeEngineeringReportInput {
    pub deployment_stage: String,
    pub current_schema_version: u64,
    #[serde(default)]
    pub observed_fractures: Vec<String>,
    #[serde(default)]
    pub enabled_features: Vec<String>,
    pub desired_next_layer: String,
    #[serde(default)]
    pub constraints: BTreeMap<String, String>,
}

impl Default for CreativeEngineeringReportInput {
    fn default() -> Self {
        Self {
            deployment_stage: "pre_production".to_owned(),
            current_schema_version: PLATFORM_SCHEMA_VERSION,
            observed_fractures: Vec::new(),
            enabled_features: Vec::new(),
            desired_next_layer: "creative engineering hardening".to_owned(),
            constraints: BTreeMap::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CreativeEngineeringReport {
    pub report_id: EventId,
    pub report_hash: String,
    pub platform_schema_version: u64,
    pub input: CreativeEngineeringReportInput,
    #[serde(default)]
    pub assumptions: Vec<EngineeringAssumption>,
    #[serde(default)]
    pub suggestions: Vec<CreativeEngineeringSuggestion>,
    #[serde(default)]
    pub high_leverage_first: Vec<EventId>,
    #[serde(default)]
    pub rejected_patterns: Vec<String>,
    #[serde(default)]
    pub constructive_delta: Vec<String>,
    #[serde(default)]
    pub fracture_delta: Vec<String>,
    pub generated_at: OffsetDateTime,
}

pub fn generate_creative_engineering_report(
    input: CreativeEngineeringReportInput,
) -> MindResult<CreativeEngineeringReport> {
    let mut suggestions = baseline_suggestions();
    let normalized_fractures: BTreeSet<String> = input
        .observed_fractures
        .iter()
        .map(|value| value.to_ascii_lowercase())
        .collect();
    let enabled_features: BTreeSet<String> = input
        .enabled_features
        .iter()
        .map(|value| value.to_ascii_lowercase())
        .collect();

    if normalized_fractures
        .iter()
        .any(|fracture| fracture.contains("lease") || fracture.contains("scheduler"))
    {
        suggestions.push(CreativeEngineeringSuggestion::new(
            EngineeringArea::Scheduler,
            "Add fenced distributed lease receipts",
            "Attach monotonic fencing tokens to every claimed job and reject receipts that do not bind token + payload hash.",
            "A worker may execute only the payload it leased, and only while its lease token is current.",
            "Add a lease-fence table and pass fence tokens into domain executor evidence.",
            "Run two-worker contention rehearsal and assert one accepted claim.",
            "Disable non-SQLite lease adapters and fall back to local compare-and-swap claims.",
            EngineeringPriority::Critical,
            EngineeringEffort::Medium,
            EngineeringRisk::Medium,
            vec!["lease".to_owned(), "race".to_owned()],
        ));
    }

    if normalized_fractures.iter().any(|fracture| {
        fracture.contains("provider") || fracture.contains("sdk") || fracture.contains("kms")
    }) || enabled_features
        .iter()
        .any(|feature| feature.contains("provider"))
    {
        suggestions.push(CreativeEngineeringSuggestion::new(
            EngineeringArea::ProviderBoundary,
            "Provider SDK harness with golden receipts",
            "Every native SDK call is wrapped by a fixture-backed harness that produces replayable request/receipt pairs before live enablement.",
            "Provider side effects are not trusted unless receipt payload hash, provider operation id, and key/object identity match the request.",
            "Add provider/<vendor>/golden directory plus emulator/dry-run fixtures for each feature flag.",
            "Replay golden receipts against the verifier and corrupt each field once.",
            "Route provider execution through external gateway or dry-run mode until fixtures pass.",
            EngineeringPriority::High,
            EngineeringEffort::Large,
            EngineeringRisk::Medium,
            vec!["provider".to_owned(), "receipt".to_owned()],
        ));
    }

    if normalized_fractures
        .iter()
        .any(|fracture| fracture.contains("consensus") || fracture.contains("replication"))
    {
        suggestions.push(CreativeEngineeringSuggestion::new(
            EngineeringArea::Consensus,
            "Consensus log shadow mode",
            "Run the replicated-log protocol in shadow mode beside the existing leader path and compare commit certificates before allowing writes.",
            "No consensus output mutates H until certificate, quorum, term, and replay tail all agree.",
            "Add a shadow_consensus_jobs scheduled task that emits comparison reports but does not append.",
            "Inject stale terms and duplicate entries into the shadow path.",
            "Keep single-writer strategy as the authority until shadow reports are green over a fixed window.",
            EngineeringPriority::Critical,
            EngineeringEffort::Large,
            EngineeringRisk::High,
            vec!["consensus".to_owned(), "shadow".to_owned()],
        ));
    }

    let mut assumptions = vec![
        EngineeringAssumption {
            key: "kernel_language".to_owned(),
            value: "Rust remains the invariant-owning implementation language".to_owned(),
            confidence: 0.92,
        },
        EngineeringAssumption {
            key: "mutation_order".to_owned(),
            value: "append-before-apply remains non-negotiable".to_owned(),
            confidence: 0.99,
        },
        EngineeringAssumption {
            key: "production_stage".to_owned(),
            value: input.deployment_stage.clone(),
            confidence: if input.deployment_stage.contains("prod") {
                0.76
            } else {
                0.86
            },
        },
    ];
    if input.current_schema_version != PLATFORM_SCHEMA_VERSION {
        assumptions.push(EngineeringAssumption {
            key: "schema_drift".to_owned(),
            value: format!(
                "input schema {} differs from runtime schema {}",
                input.current_schema_version, PLATFORM_SCHEMA_VERSION
            ),
            confidence: 0.80,
        });
    }

    suggestions.sort_by(|left, right| {
        right
            .priority_score
            .cmp(&left.priority_score)
            .then_with(|| left.title.cmp(&right.title))
    });
    let high_leverage_first = suggestions
        .iter()
        .take(5)
        .map(|suggestion| suggestion.suggestion_id)
        .collect::<Vec<_>>();
    let rejected_patterns = vec![
        "state mutation before event append".to_owned(),
        "provider SDK side effect without hash-bound receipt".to_owned(),
        "projection policy embedded inside handler code".to_owned(),
        "consensus evidence deletion without backup guard and quorum approval".to_owned(),
        "worker success without domain-specific evidence".to_owned(),
    ];
    let constructive_delta = vec![
        "creative suggestions are ranked by invariant impact, operational effort, and failure risk".to_owned(),
        "chaos rehearsal and invariant fuzzing are promoted to first-class production readiness inputs".to_owned(),
        "future engineering work can be admitted through auditable reports rather than ad hoc notes".to_owned(),
    ];
    let fracture_delta = vec![
        "suggestions do not implement provider or consensus side effects by themselves".to_owned(),
        "ranking depends on supplied fracture evidence and should be regenerated after each production incident".to_owned(),
    ];

    let report_id = EventId::new();
    let generated_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        report_id,
        PLATFORM_SCHEMA_VERSION,
        &input,
        &assumptions,
        &suggestions,
        &high_leverage_first,
        &rejected_patterns,
        generated_at,
    ))?;
    Ok(CreativeEngineeringReport {
        report_id,
        report_hash,
        platform_schema_version: PLATFORM_SCHEMA_VERSION,
        input,
        assumptions,
        suggestions,
        high_leverage_first,
        rejected_patterns,
        constructive_delta,
        fracture_delta,
        generated_at,
    })
}

fn baseline_suggestions() -> Vec<CreativeEngineeringSuggestion> {
    vec![
        CreativeEngineeringSuggestion::new(
            EngineeringArea::Kernel,
            "Invariant fuzzer seed bank",
            "Generate deterministic proposal cases for immutable-key edits, empty patches, wrong targets, forbidden keys, and valid state growth.",
            "A generated destructive case must be rejected without mutating Σ or H.",
            "Run fuzz cases in CI against EvolutionEngine and replay the accepted cases.",
            "For every seed, assert expected acceptance class and replay hash stability.",
            "Pin the last passing seed bank and skip new seeds while investigating.",
            EngineeringPriority::Critical,
            EngineeringEffort::Medium,
            EngineeringRisk::Low,
            vec!["invariant".to_owned(), "ci".to_owned()],
        ),
        CreativeEngineeringSuggestion::new(
            EngineeringArea::Operations,
            "Chaos rehearsal before feature enablement",
            "Declare failure injections as data and require containment evidence before enabling a production feature flag.",
            "Each feature flag must have at least one rehearsal proving fail-closed behavior.",
            "Add chaos rehearsal artifacts to release gates and deployment manifests.",
            "Break signature, chain hash, lease ownership, and provider receipt fields one at a time.",
            "Disable the feature flag and keep the prior schema state active.",
            EngineeringPriority::Critical,
            EngineeringEffort::Medium,
            EngineeringRisk::Medium,
            vec!["chaos".to_owned(), "release-gate".to_owned()],
        ),
        CreativeEngineeringSuggestion::new(
            EngineeringArea::Projection,
            "Projection firewall test matrix",
            "Compile projection policies into independent leak tests for public, summary, internal, audit, and maintenance scopes.",
            "Γ may expose meaning but never mutation authority or secret-bearing cells.",
            "Add generated projection fixtures containing secret.*, token, password, key, and credential cells.",
            "Assert all public/summary projections omit sensitive keys and include redaction reasons.",
            "Fall back to public_default projection until policy tests pass.",
            EngineeringPriority::High,
            EngineeringEffort::Small,
            EngineeringRisk::Low,
            vec!["projection".to_owned(), "privacy".to_owned()],
        ),
        CreativeEngineeringSuggestion::new(
            EngineeringArea::DeveloperExperience,
            "Architecture review gate as code",
            "Convert every production readiness question into a machine-readable blocker or advisory, then ledger the resulting gate report.",
            "No release promotion without explicit blocker disposition.",
            "Add a readiness-gate CLI that consumes creative report + chaos plan + fuzz run.",
            "Run the gate against a deliberately incomplete report and assert blocked status.",
            "Allow staging-only deployment with blocked production flag.",
            EngineeringPriority::High,
            EngineeringEffort::Small,
            EngineeringRisk::Low,
            vec!["review".to_owned(), "governance".to_owned()],
        ),
        CreativeEngineeringSuggestion::new(
            EngineeringArea::Observability,
            "Causal trace passport",
            "Attach a trace passport to every cross-boundary operation containing actor, proposal, commit, receipt, replay, and projection identifiers.",
            "Audit consumers can reconstruct why an external side effect was permitted.",
            "Add trace_passport_id to provider, lease, job, and consensus receipts.",
            "Pick any production event and resolve all passport references without reading private state.",
            "Keep current receipt IDs and synthesize passports during audit export.",
            EngineeringPriority::Medium,
            EngineeringEffort::Medium,
            EngineeringRisk::Low,
            vec!["audit".to_owned(), "trace".to_owned()],
        ),
        CreativeEngineeringSuggestion::new(
            EngineeringArea::Operations,
            "Mandatory readiness CI gate",
            "Promote readiness from a report to a branch-protection input that fails CI when fuzz, chaos, or gate evidence is missing.",
            "No code path merges into protected branches unless executable readiness evidence is present and passing.",
            "Add a mandatory-readiness workflow and a hash-bound CI gate report model.",
            "Run the workflow with a deliberately missing fuzz execution and assert failure.",
            "Revert to advisory readiness workflow while keeping v18 executable evidence checks.",
            EngineeringPriority::Critical,
            EngineeringEffort::Small,
            EngineeringRisk::Low,
            vec!["ci".to_owned(), "readiness".to_owned(), "branch-protection".to_owned()],
        ),
        CreativeEngineeringSuggestion::new(
            EngineeringArea::DeveloperExperience,
            "Implementation evidence bundle",
            "Convert high-ranked suggestions into jobs that cannot close without PR, test, readiness, and rollback artifacts.",
            "A completed implementation job must be causally linked to evidence proving it changed code safely.",
            "Generate branch/PR/test-command plans and validate evidence bundles before marking jobs satisfied.",
            "Attach synthetic PR evidence and omit rollback evidence once; assert incomplete status.",
            "Keep the scheduled job open and require manual artifact attachment.",
            EngineeringPriority::High,
            EngineeringEffort::Small,
            EngineeringRisk::Low,
            vec!["evidence".to_owned(), "pull-request".to_owned(), "tests".to_owned()],
        ),
    ]
}

fn score(priority: EngineeringPriority, effort: EngineeringEffort, risk: EngineeringRisk) -> i64 {
    let priority_weight = match priority {
        EngineeringPriority::Critical => 100,
        EngineeringPriority::High => 75,
        EngineeringPriority::Medium => 50,
        EngineeringPriority::Low => 25,
    };
    let effort_penalty = match effort {
        EngineeringEffort::Small => 5,
        EngineeringEffort::Medium => 15,
        EngineeringEffort::Large => 30,
    };
    let risk_penalty = match risk {
        EngineeringRisk::Low => 0,
        EngineeringRisk::Medium => 10,
        EngineeringRisk::High => 20,
    };
    priority_weight - effort_penalty - risk_penalty
}
