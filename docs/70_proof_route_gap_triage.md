# Proof Route Gap Triage

> **In one box:** A shortcut for finding API routes that lack proof coverage
> and ranking them into batches to fix — a maintenance/triage tool that pairs
> with the [Proof Coverage Matrix](40_proof_coverage_matrix.md). New here? →
> [Plain-English Overview](explain/PLAIN_ENGLISH.md). *(Doc type: Reference.)*

Purpose: define the deterministic shortcut for converting unclassified declared
routes into ranked proof-closure batches.

Governance scope: `scripts/proof_route_gap_triage.py` reads the canonical proof
coverage matrix, preserves every `unclassified_declared_route`, attaches source
file and HTTP method evidence, and emits `.change_assurance/proof_route_gap_triage.json`.
It does not mark any route as witnessed or proven.

## Operator Procedure

1. Regenerate the canonical proof matrix:
   `python scripts/proof_coverage_matrix.py`
2. Generate the route gap triage witness:
   `python scripts/proof_route_gap_triage.py`
3. Verify the witness is fresh:
   `python scripts/proof_route_gap_triage.py --check`
4. If `ranked_families[]` is non-empty, select the first item as the next
   closure candidate unless a release blocker names a stricter family.
5. If `ranked_families[]` is empty and `open_issue` is `none`, preserve the
   closed witness and continue monitoring new route declarations.
6. Close any future selected family by adding a named proof surface, evidence
   files, route tests, and a closure action in `scripts/proof_coverage_matrix.py`.

## Report Contract

| Field | Meaning |
|---|---|
| `declared_route_count` | Proof-relevant declared routes from the canonical matrix. |
| `total_unclassified_route_count` | Routes still mapped to `unclassified_declared_route`. |
| `route_family_count` | Number of route families containing unclassified routes. |
| `ranked_families` | Deterministic queue sorted by route count, risk class, then route family. |
| `risk_class` | `effect_bearing`, `mixed`, or `read_model` derived from method and path tokens. |
| `suggested_proof_level` | Minimum closure level to investigate for the family. |
| `source_files` | Route declaration files that must provide implementation evidence. |

## Invariants

1. No route is reclassified by the triage script.
2. Every ranked family is derived from at least one unclassified declared route.
3. Mutating methods and effect-bearing route tokens force `action_proof` as the
   suggested proof level.
4. `--check` fails when the stored assurance witness is stale.

## Current Closure Witness

The current canonical proof matrix reports `declared_route_count: 418` and
`total_unclassified_route_count: 0`. The generated proof-route triage report is
therefore closed with `ranked_families: []`, `open_issue: none`, and
`next_action: none`.

The closure is guarded by `tests/test_proof_route_gap_triage.py`, which compares
the documentation status with `build_gap_triage_report(...)` output from the
canonical proof coverage fixture.

STATUS:
  Completeness: 100%
  Invariants verified: [route gap preservation, deterministic ranking, source-file binding, stale witness detection, closed report/documentation parity]
  Open issues: none
  Next action: run `python scripts/proof_route_gap_triage.py --check` after route or proof-surface changes
