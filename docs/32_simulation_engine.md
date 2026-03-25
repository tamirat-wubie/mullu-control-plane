# 32 — Simulation Engine

## Purpose

The simulation engine reasons about consequences before acting.  Given a
proposed action and the current operational graph state, it projects likely
outcomes, compares options, and estimates risks — all without causing any
side effects.

The engine answers: *if we take this action, what will change in the graph,
what new obligations will arise, which nodes will be blocked or unblocked,
how much review burden will be created, and what incident risk do we accept?*

By evaluating multiple action paths and ranking them, the simulation engine
provides a structured basis for human or policy decision-making.  It does not
decide — it informs.

## Owned Artifacts

| Contract                | Role                                                     |
|-------------------------|----------------------------------------------------------|
| SimulationRequest       | Captures the proposed action and its graph context        |
| SimulationOption        | One candidate action path to evaluate                    |
| ConsequenceEstimate     | Projected graph deltas for a single option               |
| RiskEstimate            | Incident probability, review burden, provider exposure   |
| ObligationProjection    | New and fulfilled obligations, deadline pressure          |
| SimulationOutcome       | Composite result joining consequence, risk, and obligation projections for one option |
| SimulationComparison    | Side-by-side ranking of all evaluated options            |
| SimulationVerdict       | Recommended option with verdict type, justification, and confidence |

## Simulation Model

Given a `SimulationRequest` containing a proposed action description and a set
of context node IDs from the current operational graph:

1. **Enumerate options** — produce one or more `SimulationOption` instances,
   each describing a distinct action path that could fulfill the request.
2. **Project consequences** — for each option, compute a `ConsequenceEstimate`:
   - Which existing nodes will be affected.
   - How many new edges and obligations will be created.
   - How many nodes will become blocked or unblocked.
3. **Estimate risk** — for each option, produce a `RiskEstimate`:
   - Classify the overall risk level (minimal through critical).
   - Estimate incident probability as a float in [0, 1].
   - Count the estimated reviews needed (review burden).
   - Count provider actions exposed (provider exposure).
   - Assess verification difficulty and provide a rationale.
4. **Project obligations** — for each option, produce an `ObligationProjection`:
   - List descriptions of new obligations that will arise.
   - List obligations that will be fulfilled.
   - Count obligations with tight deadlines (deadline pressure).
5. **Assemble outcomes** — combine consequence, risk, and obligation projections
   into a `SimulationOutcome` per option.
6. **Compare and rank** — produce a `SimulationComparison` that orders options
   by a composite of risk, obligation cost, estimated duration, and confidence.
7. **Render verdict** — produce a `SimulationVerdict` recommending one option
   with a verdict type, justification string, and confidence score.

## Option Comparison

Options are ranked by the following factors (in priority order):

1. **Risk level** — lower risk is preferred.
2. **Obligation cost** — fewer new obligations and less deadline pressure are
   preferred.
3. **Estimated duration** — shorter paths are preferred when risk is equal.
4. **Confidence** — higher confidence in the projection is preferred.

The ranking is recorded as an ordered tuple of option IDs in the
`SimulationComparison.ranking` field.

## Verdict Model

A `SimulationVerdict` is the final output of the simulation engine.  It
contains:

- **recommended_option_id** — the option ID ranked first.
- **verdict_type** — one of: `proceed`, `proceed_with_caution`,
  `approval_required`, `escalate`, `abort`.
- **justification** — a human-readable explanation of why this option was
  chosen.
- **confidence** — a float in [0, 1] expressing the engine's confidence in
  the recommendation.
- **decided_at** — ISO 8601 timestamp of verdict creation.

## Prohibitions

1. **No side effects** — no simulation may modify the operational graph, invoke
   provider actions, send communications, or alter any persistent state.
2. **No verified-fact treatment** — simulation output is a projection, not a
   verified observation.  No downstream contract may treat simulation results
   as ground truth without independent verification.
3. **No auto-execution** — no simulation verdict may trigger automatic
   execution of the recommended action.  A human decision or explicit policy
   gate must intervene between simulation output and action execution.
4. **No retroactive justification** — simulation results produced after an
   action has already been taken do not constitute pre-action analysis.
5. **No confidence inflation** — confidence values must reflect actual
   projection uncertainty; optimistic bias is a contract violation.
