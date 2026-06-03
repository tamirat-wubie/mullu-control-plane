# Solver Forge Loop

> **In one box:** How Mullu *discovers* which solution to a problem is worth
> packaging — candidates are built, compared on real evidence, and adversarially
> reviewed before being handed to the
> [capability forge](GLOSSARY.md#capability-forge--solver-forge). Crucially it
> **never** auto-installs anything: new power is earned, not assumed. New here?
> See the [Plain-English Overview](explain/PLAIN_ENGLISH.md).
> *(Doc type: Explanation.)*

Purpose: define how candidate method pipelines are typed, composed, compared under evidence, adversarially reviewed, and handed to the existing Capability Forge so that the Mullu platform can discover *which* solution to a problem class is worth packaging without ever auto-promoting it.
Governance scope: candidate-only experimentation upstream of the capability registry and the C0–C7 maturity ladder. The loop never installs capabilities, never mutates the registry, never unblocks promotion.
Dependencies: `docs/39_governed_capability_fabric.md`, `docs/53_red_team_harness.md`, `docs/56_general_agent_capability_roadmap.md`, `docs/62_governed_operational_intelligence.md`.
Invariants:
- A candidate is a winner only when its `baseline_delta` on the signature's primary success metric beats the recorded baseline run AND adversarial review records no findings.
- The candidate ledger is append-only; failed, regressed, timed-out, budget-exceeded, and review-failing candidates have the same first-class record shape as winners.
- Every candidate runs under the same budget, timeout, and seed-per-pipeline as every other candidate for a given problem signature.
- A baseline that fails adversarial review disqualifies every candidate for that run — no winner may claim to beat an untrusted baseline.
- The composer and the bridge have no `install` / `promote` / `certify` / `deploy` / `register_capability` surface.
- Domain and risk of a `CapabilityForgeInput` produced by the bridge are taken from the problem signature, never from caller overrides.
- High-risk signatures force `requires_approval=True` on any forge input the bridge produces.

## Why this layer exists

The pre-existing `gateway/capability_forge.py` (~40 KB) builds candidate capability packages and hands them to the C0–C7 maturity ladder. It is the *post-comparison* surface — given a candidate worth packaging, it produces a typed, schema-backed, promotion-blocked package. Without a pre-comparison surface, the only way to decide *which* candidate is worth packaging was author judgment: someone picks a method, hand-writes a `CapabilityForgeInput`, and the maturity ladder gates it from there.

That works for a small number of admitted capabilities. It does not scale to the user's framing of broad experimentation:

> Explore broadly. Promote narrowly. Act only through governance.

The Solver Forge loop is the broad-exploration layer. It tries many method combinations under a single typed problem statement, compares them under identical conditions, runs both gates (evaluator + adversarial reviewer) on every candidate, and emits a comparison report whose winners can be packaged by the existing forge. The maturity ladder is unchanged; the registry is unchanged; the worker runtime is unchanged.

## Pipeline

```text
ProblemSignature
       |
       v
 CandidateComposer.run(evaluator, adversarial_reviewer)
       |
       |  Gate 1 (evaluator):           passed AND beats baseline on primary metric
       |  Gate 2 (adversarial reviewer): no findings
       |          - applied symmetrically to baseline and candidates
       |          - a compromised baseline disqualifies every candidate
       v
 CandidateLedger (append-only; negatives + findings preserved)
       |
       v
 forge_input_for_winner()      <-- inherits both gates by construction
       |
       v
 CapabilityForge.create_candidate()
       |
       v
 CandidateCapabilityPackage  (candidate-only, promotion_blocked=True,
                              carries solver_forge.* provenance in metadata)
       |
       v
 C0 -> C1 -> C2 -> C3 -> C4 -> C5 -> C6 -> C7   (existing maturity ladder)
```

## Components

| Module | Type | Role |
| --- | --- | --- |
| `gateway/problem_signature.py` | `ProblemSignature`, `ProblemMetric`, `ProblemEvidenceRequirement` | Types a problem before any candidate exists. Canonical-hash identity; physical risk requires physical-safety evidence; non-low risk requires explicit budget + timeout. |
| `gateway/candidate_ledger.py` | `CandidateLedger`, `CandidateRun`, `CandidateScore`, stores | Append-only record of every candidate run. Negative results and adversarial findings are first-class. In-memory + JSON-file stores follow the `plan_ledger.py` pattern. |
| `gateway/candidate_composer.py` | `CandidateComposer`, `MethodCapsule`, `CandidatePipeline`, `CandidateEvaluation`, `AdversarialReviewResult`, `CandidateComparisonReport` | Composes pipelines from registered capsules, runs each under a deterministic per-pipeline seed, applies both gates, and records every result. |
| `gateway/solver_forge_bridge.py` | `forge_input_for_winner`, `build_provenance`, `extract_provenance`, `SolverForgeProvenance`, `is_winner` | Carries a winning ledger record into a `CapabilityForgeInput` with full provenance stamped under the reserved `solver_forge.*` metadata key. Refuses non-winners and findings-bearing runs. |
| `gateway/solver_forge_red_team_adapter.py` | `RedTeamPlatformReviewer` | Production `AdversarialReviewCallback` backed by `RedTeamHarness`. Caches the report per instance by default. Findings derive from the harness category summary; evidence ref is the harness `report_hash`. |
| `gateway/method_registry.py` | `MethodRegistry`, `STARTER_CAPSULES`, `default_registry` | Typed catalog of method capsules. Selects the capsules a signature admits and builds a composer; declaration-only, with no promotion surface. Ships a conservative starter catalog. |
| `gateway/solver_forge_benchmarks.py` | `reference_evaluator`, `run_benchmark`, `BENCHMARKS`, `DUPLICATE_INVOICE_SIGNATURE` | Worked duplicate-invoice benchmark over a labeled fixture with three real detectors. Deterministic; primary metric is F1 so a recall-only trap cannot win. |
| `gateway/solver_forge_cli.py` | `main`, `build_parser` | Read-and-experiment CLI: list capsules/benchmarks, run a benchmark, preview a forge input. No promote / install / deploy subcommand. |
| `gateway/solver_forge_capsule_probes.py` | `CapsuleProbeReviewer`, `CompositeAdversarialReviewer`, `DEFAULT_PROBES` | Candidate-specific Gate-2 reviewer: deterministic probes derived from each capsule's declared contract, so different candidates get different findings. Composes with `RedTeamPlatformReviewer`. |
| `gateway/candidate_ledger_postgres.py` | `PostgresCandidateLedgerStore`, `connect` | Durable Postgres-backed `CandidateLedgerStore`. Append-only, rejects duplicate `record_hash`, mirrors the platform `DatabaseConnection` protocol (injectable, so it is fully testable without a live DB). |
| `gateway/signature_cluster.py` | `SignatureClusterIndex`, `signature_similarity` | Cross-signature clustering: deterministic feature-overlap similarity groups related problem classes and surfaces prior winning method families from the ledger. Read-only, advisory, no promotion surface. |

## Problem signatures

A signature is the lab's only input grammar. Two signatures with identical content produce identical `signature_hash` values; this is what makes the ledger addressable by problem class.

```python
ProblemSignature(
    problem_id="invoice_duplicate_detection.v1",
    domain="finance_ops",
    goal="detect duplicate invoice before payment",
    inputs=("invoice", "vendor_record", "payment_history"),
    constraints=("no payment decision without vendor match",),
    risk="high",
    metrics=(
        ProblemMetric(metric_id="precision", metric_kind="success", direction="maximize", threshold=0.95),
        ProblemMetric(metric_id="false_positive_rate", metric_kind="failure", direction="minimize"),
    ),
    required_evidence=(
        ProblemEvidenceRequirement(requirement_id="ledger-match", evidence_type="ledger_lookup_receipt", required=True),
    ),
    budget_units=100.0,
    timeout_seconds=5.0,
    allowed_method_families=("rule_based", "graph_match", "constraint_solver"),
    forbidden_method_families=("llm_only",),
    baseline_method_family="rule_based",
)
```

Validation rules enforced in `__post_init__`:

- Non-low risk requires explicit budget AND timeout.
- Physical risk requires at least one `physical_safety` evidence requirement.
- Allowed and forbidden method-family sets must not overlap.
- The baseline method family must not appear in the forbidden list.
- At least one success metric must be present.

## Composer fairness

Every candidate pipeline for a given signature receives the same seed (derived from `signature_hash` + `pipeline_id`), the same budget, and the same timeout. The evaluator callback owns subsystem logic; the composer owns orchestration. This mirrors `mcoi/mcoi_runtime/core/benchmark_engine.py`'s injection pattern.

Capsule admissibility checks before composition:

1. `signature.admits_method_family(capsule.method_family)` — allowed list (if any) and forbidden list.
2. Capsule's `risk_ceiling` covers `signature.risk` (low < medium < high < physical).

Skipped capsules are reported in `CandidateComparisonReport.skipped_capsule_ids` with a reason in `skipped_reasons`. A composer subclass with a different composition strategy overrides `_composer_skips()` so these fields describe what *that* strategy skipped — see the multi-capsule composer below, where the keys become composition pipeline ids rather than capsule ids.

## Both gates

The composer requires two independent verdicts before declaring a winner.

### Gate 1: evaluator

```python
EvaluatorCallback = Callable[[ProblemSignature, CandidatePipeline, str], CandidateEvaluation]
```

The evaluator returns one of `passed`, `failed`, `regression`, `timeout`, `budget_exceeded`, `error`, `skipped` plus measured scores. A candidate that does not return `passed` is recorded and excluded from winner consideration. A `passed` candidate must additionally show a positive `baseline_delta` on the signature's primary success metric (negative when the metric direction is `minimize`).

### Gate 2: adversarial reviewer

```python
AdversarialReviewCallback = Callable[
    [ProblemSignature, CandidatePipeline, CandidateEvaluation, str],
    AdversarialReviewResult,
]
```

The reviewer is optional but recommended. It is invoked on passing evaluations only (failed-evaluator runs are already losing; adversarial review would add cost without changing the outcome). The reviewer is applied **symmetrically** to the baseline. Why: if the baseline itself fails review (audit tamper, policy bypass, prompt-injection susceptibility), then a candidate's `baseline_delta` cannot be trusted as a comparison signal. `CandidateComparisonReport.baseline_compromised=True` zeroes the winner set for that run.

A production wiring is provided by `gateway/solver_forge_red_team_adapter.py`. `RedTeamPlatformReviewer` is a callable that satisfies `AdversarialReviewCallback` and is backed by the platform's deterministic `RedTeamHarness` (prompt injection, budget evasion, audit tampering, policy bypass).

```python
from gateway.solver_forge_red_team_adapter import RedTeamPlatformReviewer

reviewer = RedTeamPlatformReviewer()  # default harness; cached per instance
composer = CandidateComposer(ledger, capsules=..., adversarial_reviewer=reviewer)
```

The adapter tests *platform invariants*, not candidate-specific behavior. Every candidate in a session inherits the same verdict: either the platform is safe (no findings) or it is not (all candidates fail with `red_team_<category>_failed` findings, one per failing category, and the harness `report_hash` as the evidence ref).

`severity_threshold` tolerates up to N failed cases (default `0` = strict). `cache=True` (default) runs the harness once per adapter instance; `reset_cache()` forces a fresh run. Construct a new adapter for each composer.run() session if you want fresh platform evidence per session.

Candidate-specific adversarial probes (per-pipeline findings derived from each capsule's declared contract) are implemented by `gateway/solver_forge_capsule_probes.py`; see the Candidate-specific adversarial probes section below.

## Comparison ledger

`CandidateRun` is the unit of comparison evidence:

```text
record_id, signature_hash, problem_id, candidate_pipeline_id, method_families,
outcome, scores, baseline_delta, failure_modes, evidence_refs,
cost_units, duration_seconds, run_seed, is_baseline, recorded_at,
record_hash, notes,
adversarial_review_findings, adversarial_review_evidence_refs
```

The ledger is append-only. `record_hash` is a canonical hash over identity-defining fields and rejects duplicate writes at the store layer. Negative results and review failures are recorded with the same shape as winners — this is the load-bearing asset that lets a future composer run avoid relitigating known-failing combinations and lets reviewers audit *why* a candidate was selected for forge handoff.

## Bridge to CapabilityForge

```python
forge_input = forge_input_for_winner(
    winner=winning_run,
    signature=signature,
    capability_id="finance.duplicate_invoice_guard.v1",
    version="0.1.0",
    api_docs_ref="docs/api/duplicate_invoice_guard.md",
    input_schema_ref="schemas/duplicate_invoice_guard.input.schema.json",
    output_schema_ref="schemas/duplicate_invoice_guard.output.schema.json",
    owner_team="finance-platform",
    side_effects=("ledger_read", "external_message_send"),
    requires_approval=True,  # forced when signature.risk == "high"
)
package = CapabilityForge().create_candidate(forge_input)
# package.metadata["solver_forge"] carries full provenance
```

Author-supplied fields (capability_id, version, schema refs, owner_team, side effects, network/secret declarations) are required because the comparison ledger neither has nor invents them. Domain and risk are taken from the signature only; this prevents a capability from being relabeled into a domain it was not proven against.

The bridge stamps a `solver_forge.*` metadata block onto the forge input:

```text
signature_hash, problem_id, winner_record_hash, primary_metric_id,
primary_metric_value, primary_metric_baseline_delta, primary_metric_direction,
method_families, run_seed, cost_units, duration_seconds, recorded_at,
provenance_hash
```

`CapabilityForge.create_candidate` preserves the block. `extract_provenance(forge_input)` (or, by extension, `extract_provenance(package_with_metadata)`) reads it back so reviewers and the certification handoff can audit comparison evidence from the package side without re-querying the ledger.

## How to add a method capsule

A method capsule is a typed wrapper around a method family the composer can include in candidate pipelines. The composer does not own implementation; the evaluator does.

```python
MethodCapsule(
    capsule_id="capsule:graph_match.invoice_vendor.v1",
    method_family="graph_match",
    declared_inputs=("invoice", "vendor_graph"),
    declared_outputs=("duplicate_flag", "matched_edges"),
    declared_assumptions=("vendor identity graph exists", "invoice fields are parsed"),
    declared_failure_modes=("missing vendor relation", "stale ledger"),
    cost_class="low",
    explainability="high",
    risk_ceiling="medium",
)
```

`risk_ceiling` is the maximum signature risk under which this capsule may be composed. A capsule with `risk_ceiling="low"` is silently skipped for a signature with `risk="high"` and the skip reason is reported.

## How to add a method family to an existing capability

Method families are open-ended strings; the registry is just whichever capsules have been registered with a given composer. To make a new family eligible:

1. Pick a stable family name (e.g. `causal_reasoning`, `formal_verification`, `multi_agent_debate`).
2. Wrap the implementation in an evaluator callback that takes `(ProblemSignature, CandidatePipeline, seed)` and returns a `CandidateEvaluation`.
3. Register one or more `MethodCapsule` instances declaring the family.
4. If the family represents elevated risk, set `risk_ceiling` appropriately.
5. Optionally add the family to `allowed_method_families` on problem signatures where it should compete.

## Multi-capsule pipelines

The base `CandidateComposer` emits one single-capsule pipeline per admissible capsule. `DeclaredCompositionComposer` (a subclass overriding **only** `compose_pipelines`) emits caller-declared ordered multi-capsule chains — e.g. `OCR → field extractor → vendor matcher → duplicate detector`. The composer never invents compositions: the caller declares each one as a `CompositionSpec(pipeline_id, capsule_ids, description)`. Data flow between capsules remains the evaluator's responsibility, exactly as for single-capsule pipelines (composer owns orchestration, evaluator owns subsystem logic).

`run()`, both gates, per-pipeline seed fairness, the ledger, and the comparison report are inherited unchanged — a multi-capsule pipeline is recorded, gated, and scored exactly like a single-capsule one.

Rules specific to the declared composer:

- **Chain poisoning.** Every capsule in a declared chain must be admissible (method family allowed/not-forbidden AND `risk_ceiling` covers the signature risk). A single inadmissible or unknown capsule poisons the *whole* chain — you cannot run half a pipeline. The spec is not composed; the reason is recorded.
- **Duplicate ids rejected.** Two `CompositionSpec`s sharing a `pipeline_id` would derive the same run seed and the same ledger record hash. The later duplicate is skipped with reason `duplicate_pipeline_id` rather than crashing mid-run.
- **Skip auditing.** Poisoned and duplicate specs are exposed two ways: `skipped_compositions()` returns full `SkippedComposition` records, and the comparison report's `skipped_capsule_ids` / `skipped_reasons` are keyed by the skipped composition's `pipeline_id` with the offending capsule encoded in the reason (the declared composer overrides `_composer_skips()` to make the report describe composition-level skips instead of single-capsule admissibility).
- **Baseline.** `run()` still detects the baseline as the pipeline whose `method_families` is the single-element tuple `(signature.baseline_method_family,)`. A multi-capsule pipeline can never be mistaken for the baseline; a caller that wants one includes a single-capsule `CompositionSpec` for the baseline family.

## Method registry and starter catalog

`gateway/method_registry.py` is the "Method Registry" box of the loop: a typed
catalog of `MethodCapsule` declarations the composer can draw on. It owns no
implementation and no promotion path — `composer_for(signature, ledger)` returns
a `CandidateComposer` seeded with the capsules whose method family the signature
admits, and the composer reports any risk-ceiling skips transparently.

`default_registry()` ships a conservative `STARTER_CAPSULES` catalog spanning the
first three problem domains (`document_verification`, `workflow_automation`,
`engineering_puzzle`) plus general-purpose families (`llm_planner`,
`llm_reviewer`, `multi_agent_debate`, `human_review_gate`). These are starter
DEFAULTS: every capsule is tagged `metadata["provenance"] = "starter_default"`,
and capsule/adapter owners should review and replace the `risk_ceiling`,
`cost_class`, and `explainability` claims with measured values before those
claims inform a promotion decision.

## Reference benchmark

`gateway/solver_forge_benchmarks.py` is a worked, runnable benchmark that
exercises the whole loop on real computation. `invoice_duplicate_detection.v1`
embeds a labeled invoice fixture and three genuine detectors:

- `rule_based` exact field match (the baseline): high precision, low recall.
- `graph_match` normalized vendor + amount proximity: catches variations.
- `statistical_anomaly` same-vendor overflag: a recall-only trap.

The evaluator is deterministic and measures precision/recall/F1 on the fixture
rather than declaring scores. The signature's primary metric is **F1, not
recall**, so the overflag trap — which has perfect recall but low precision —
runs, is recorded as a passed candidate, and is correctly **refused as a
winner**. Only the graph-match detector beats the baseline on F1 and is selected.
This is the loop demonstrating "Promote narrowly": a high-recall result is not a
winner unless it also clears the primary metric.

A second benchmark, `task_scheduling_with_deadlines.v1` (`engineering_puzzle`),
makes the same point in a different domain. A naive in-order baseline, an
earliest-deadline-first scheduler, and a "longest-first" anti-pattern are
compared on real single-worker scheduling with dependencies. The primary metric
is on-time rate, so earliest-deadline-first wins (it meets every deadline) while
the longest-first heuristic runs, is recorded, and is refused for missing more
deadlines than the baseline. This benchmark also exercises the `search_planner`,
`constraint_solver`, and `optimization_solver` capsules that the duplicate-invoice
benchmark does not.

A third benchmark, `deployment_gate_decision.v1` (`workflow_automation`),
completes the first three problem domains and exercises the `simulation_check`
capsule. It decides GO/NO-GO on deploy requests, scored against recorded incident
outcomes: a naive tests-only baseline, a full safety policy, and a
throughput-maximizing "ship-fast" gate. The primary metric is decision accuracy,
so the full safety policy wins (and approves nothing unsafe) while the
throughput gate — which approves too much and would wave through real incidents —
runs, is recorded, and is refused.

## Running the lab (CLI)

`gateway/solver_forge_cli.py` is the read-and-experiment entrypoint. It has no
promote / install / certify / deploy subcommand by construction; acting on a
winner stays a deliberate, downstream step through the C0-C7 maturity ladder.

```text
python -m gateway.solver_forge_cli list-capsules [--domain D] [--family F]
python -m gateway.solver_forge_cli list-benchmarks
python -m gateway.solver_forge_cli run <benchmark_id> [--json] [--ledger-out FILE]
python -m gateway.solver_forge_cli forge-input <benchmark_id> \
    --capability-id <id> --owner-team <team>   # PREVIEW only; creates nothing
```

`run` prints the winners, passed-non-winners (with their negative
`baseline_delta`), negatives, and skipped capsules, and can persist the full
candidate ledger to a JSON file. `forge-input` previews the
`CapabilityForgeInput` a winner would produce — including the stamped
`solver_forge.*` provenance — but never calls `CapabilityForge.create_candidate`.

## Candidate-specific adversarial probes

`RedTeamPlatformReviewer` tests platform invariants, so every candidate in a
session inherits the same verdict. `gateway/solver_forge_capsule_probes.py` adds
the complementary layer: `CapsuleProbeReviewer` is an `AdversarialReviewCallback`
that derives deterministic probes from each capsule's **declared contract**, so
two different candidates can receive **different** findings.

The default probes:

- **Unmitigated injection surface** — a capsule that consumes untrusted free
  text (an LLM-backed family, or an input named `text` / `prompt` / `document` /
  …) must declare an injection-class failure mode; otherwise the surface is
  unguarded.
- **Unguarded external-state assumption** — an assumption that depends on
  external mutable state (a graph `exists`, data is `fresh`, a service is
  `reachable`) must have a matching `missing` / `stale` / `unavailable` failure
  mode.
- **High-risk / low-oversight** — a high- or physical-risk capsule with low
  explainability must be paired with a `human_review_gate` in the pipeline.

Findings are honest by construction: they are derived from declared metadata, so
a finding means "the declared contract leaves a surface unguarded", never "the
method was attacked and failed". The reviewer obeys every existing gate
invariant — it is applied symmetrically to the baseline (a flagged baseline sets
`baseline_compromised` and zeroes winners), and findings are recorded on the
ledger record. `CompositeAdversarialReviewer` unions several reviewers so the
platform harness and the capsule probes can run together.

The shipped starter catalog **passes** its own default probes: every capsule
declares the failure modes the probes require — injection mitigations on the
LLM-backed capsules (`llm_planner`, `llm_reviewer`, `multi_agent_debate`) and an
availability guard on `human_review_gate`. (Those declarations were added in
response to the probes flagging the gaps — the lab closing a contract gap it
found in itself.) A test asserts the catalog stays clean, so probes can be
attached to any benchmark without compromising its baseline.

## Cross-signature clustering

Two signatures with different `signature_hash` values are siblings, not the same
problem class — so ledger evidence does not transfer between them by default.
`gateway/signature_cluster.py` adds the advisory layer. `SignatureClusterIndex`
computes a deterministic, symmetric **feature-overlap** similarity between
signatures — domain match, goal-token Jaccard, success-metric-id Jaccard,
allowed-family Jaccard, and risk match, under explicit tunable weights — *not* a
learned model. Identical content scores 1.0.

It exposes `related(signature)` (registered signatures above the threshold,
sorted by score), `clusters()` (connected components = problem classes), and
`prior_winning_families(signature, ledger)` — which reads the ledger's winners
for related signatures and tallies the method families that have won on problems
*like this one*. That tally is **evidence, not a recommendation**: the index
never composes, scores, or promotes anything, and reads each related signature's
winners with that signature's own primary metric.

## Relationship to existing infrastructure

| Pre-existing module | Relationship |
| --- | --- |
| `gateway/capability_forge.py` | Consumer of bridge output. Unchanged. Builds the candidate package and the certification handoff. |
| `gateway/capability_maturity.py` | Unchanged. Synthesizes maturity evidence and projects readiness onto registry entries. Solver Forge candidate packages enter this ladder at C0. |
| `gateway/autonomous_capability_upgrade.py` | Unchanged. C0–C7 transitions and autonomy controls. |
| `mcoi/mcoi_runtime/core/governed_capability_registry.py` | Unchanged. Registry remains authoritative for admitted capabilities. The composer never touches it. |
| `mcoi/mcoi_runtime/core/benchmark_engine.py` | Pattern source. The composer mirrors its evaluator-callback injection pattern. |
| `mcoi/mcoi_runtime/core/red_team_harness.py` | Production-mode adversarial-review provider. The `AdversarialReviewCallback` is the integration seam. |
| `mcoi/mcoi_runtime/core/adversarial_operations.py` | Source of red-team operations (prompt injection, budget evasion, audit tampering, policy bypass). |
| `gateway/plan_ledger.py` | Pattern source. The candidate ledger mirrors its append-only store contract and JSON-file durability. |

## Failure modes the loop refuses

- **Method soup.** A passing candidate without a recorded baseline cannot be a winner. Without `baseline_delta` on the primary metric, the winner-selection logic excludes the run.
- **Score-only optimization.** A candidate with the highest raw score but adversarial findings is not a winner. The reviewer's verdict is independent of the evaluator's.
- **Untrusted-baseline laundering.** If the baseline fails review, no candidate wins for that run. A future composer call must establish a clean baseline before any winner claim is valid.
- **Domain relabeling.** The bridge takes domain and risk from the signature only. A caller cannot ask for a low-risk forge input from a high-risk signature.
- **Negative-result amnesia.** The ledger preserves losers with the same record shape as winners. Composer runs that revisit a known-failing combination produce a new record (different `run_seed`, same `record_hash` if the inputs collide) instead of silently re-running.
- **Composer-side promotion.** The composer and bridge expose no `install` / `promote` / `certify` / `deploy` / `register_capability` surface (asserted by tests). Promotion remains the C0–C7 ladder.

## Test coverage

| Suite | Tests | Subject |
| --- | --- | --- |
| `tests/test_gateway/test_solver_forge.py` | 19 | Signature validation, ledger append-only and duplicate rejection, composer fairness, baseline-required winner claim, capsule skip, promotion isolation. |
| `tests/test_gateway/test_solver_forge_bridge.py` | 20 | Winner classification, provenance round-trip, non-winner refusal, signature-hash mismatch, domain/risk laundering refusal, high-risk approval enforcement, reserved-key protection, end-to-end round-trip through `CapabilityForge.create_candidate`. |
| `tests/test_gateway/test_solver_forge_adversarial.py` | 12 | Review-result shape invariants, reviewer-on-passing-only semantics, finding preservation, candidate exclusion despite beating baseline, baseline-compromise zeroing winners, ledger filtering, bridge refusal, double-gate end-to-end. |
| `tests/test_gateway/test_solver_forge_red_team_adapter.py` | 14 | Default-platform clean path, injected failing case → findings + report_hash evidence ref, multi-category finding derivation (sorted + deduped), malformed/inconsistent report defenses, severity_threshold tolerance, cache hit + opt-out + `reset_cache()` + `latest_report()` immutability, end-to-end composer integration with both clean and failing platform. |
| `tests/test_gateway/test_solver_forge_multicapsule.py` | 14 | `CompositionSpec` shape, ordered multi-capsule emission, chain poisoning (forbidden / unknown / below-risk-ceiling capsule), `skipped_compositions()` reset-per-call, single-capsule-baseline detection with multi-capsule candidates, double-gate end-to-end, base-composer regression guard, truthful composition-level skip reporting, and duplicate-`pipeline_id` safety. |
| `tests/test_gateway/test_method_registry.py` | 12 | Register / duplicate-rejection, family + domain queries, signature admissibility (allow / forbid / risk-ceiling), composer construction, no-promotion-surface, starter-catalog integrity. |
| `tests/test_gateway/test_solver_forge_benchmarks.py` | 11 | Detector ground truth (precision / recall), deterministic evaluator, unknown-capsule skip, end-to-end winner selection, recall-only-trap refusal, winner crosses the bridge, ledger winners match the report. |
| `tests/test_gateway/test_solver_forge_cli.py` | 9 | No-promotion subcommand surface, list capsules / benchmarks (incl. domain + family filters), text + JSON run output, unknown-benchmark error, ledger-file write, read-only forge-input preview. |
| `tests/test_gateway/test_solver_forge_scheduling_benchmark.py` | 6 | Scheduler ground truth (on-time rate), deterministic evaluator, unknown-capsule skip, EDF wins / longest-first anti-pattern refused, winner crosses the bridge, catalog membership. |
| `tests/test_gateway/test_solver_forge_deployment_benchmark.py` | 6 | Gate ground truth (accuracy + unsafe-approval rate), deterministic evaluator, unknown-capsule skip, safety-policy wins / throughput gate refused, winner crosses the bridge, three-domain catalog. |
| `tests/test_gateway/test_solver_forge_capsule_probes.py` | 14 | Each probe (injection / external-state / high-risk-low-oversight) + its mitigation, deterministic candidate-specific findings, starter-catalog calibration, composite union, composer double-gate exclusion, baseline-compromise. |
| `tests/test_gateway/test_candidate_ledger_postgres.py` | 8 | Schema init, append + byte-faithful roundtrip, duplicate rejection, findings roundtrip, per-signature isolation, status, drop-in `CandidateLedger` backend, clear error without psycopg2 (+ skip-gated real-DB smoke). |
| `tests/test_gateway/test_signature_cluster.py` | 8 | Similarity (identical=1, symmetric, variant-related, unrelated below threshold), related excludes self + sorts by score, clusters group problem classes, prior-winning-families reads related evidence (ignores unrelated), threshold validation, no-promotion-surface. |

## Open questions deferred to follow-on work

- **Composer-invented compositions.** `DeclaredCompositionComposer` runs *caller-declared* chains (see "Multi-capsule pipelines" above). A composer that automatically *generates* candidate compositions — searching the space of capsule orderings under the signature constraints rather than running an explicit list — is not in scope. The declared composer is the deterministic substrate such a search would sit on top of.
- **Live-attack candidate probes.** Candidate-specific *contract-level* probes are now implemented (`gateway/solver_forge_capsule_probes.py`, `CapsuleProbeReviewer`). The remaining gap is probes that *execute* live attacks per pipeline (rather than auditing the declared contract); the `AdversarialReviewCallback` seam already supports it.
- **Production ledger-pool wiring.** A Postgres-backed store is now implemented (`gateway/candidate_ledger_postgres.py`, `PostgresCandidateLedgerStore`), testable via an injected connection. The remaining follow-on is wiring it to the platform's production connection pool / migration CLI; the store itself is pool-agnostic (it accepts any `DatabaseConnection`).
- **Learned cross-signature similarity.** A deterministic feature-overlap clustering layer is now implemented (`gateway/signature_cluster.py`, `SignatureClusterIndex`). A natural follow-on is a *learned* similarity (e.g. embeddings over signature structure) for cross-domain problem classes the feature heuristic misses; the index's `weights` / `threshold` seam and the ledger evidence are already in place.
