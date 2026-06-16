# Research Source Conflict Map Contract

Purpose: define a read-only conflict map for preserving citation-backed disagreements across research sources before any synthesis, live retrieval, or publication authority is considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/82_cross_repo_opportunity_map.md`, `schemas/research_source_conflict_map.schema.json`, `schemas/search_decision.schema.json`, `schemas/search_receipt.schema.json`, `schemas/evidence_classification_manifest.schema.json`, `schemas/universal_action_orchestration.schema.json`, `schemas/life_meaning_judgment.schema.json`.
Invariants: research source conflicts preserve citation refs and digest refs only; raw source bodies, secret values, live search, source contact, connector calls, answer synthesis, memory writes, publication, terminal closure, and success claims remain denied.

## Boundary

`ResearchSourceConflictMap` is an evidence receipt, not a research runtime.

It may bind:

1. A hashed research question.
2. SearchDecision and SearchReceipt schema refs.
3. Citation refs from operator-supplied or receipt-backed sources.
4. Source claim and summary digest refs.
5. Contradiction class, severity, and freshness impact.
6. Follow-up sensing needs that require approval.
7. Retention and authority-denial flags.

It must not bind:

1. Raw source bodies.
2. Raw secret values.
3. Live web search execution.
4. Source contact or external submission.
5. Connector calls.
6. Answer synthesis or current-claim authority.
7. Memory writes, publication, terminal closure, or success claims.

## Foundation Example

The Foundation Mode example is:

```text
examples/research_source_conflict_map.foundation.json
```

The validator is:

```powershell
python scripts\validate_research_source_conflict_map.py
```

Expected result:

```text
[PASS] research_source_conflict_map
```

## Authority Denials

The Foundation example requires these fields to remain `false`:

| Field | Denial |
| --- | --- |
| `external_retrieval_performed` | no external retrieval |
| `web_search_performed` | no live web search |
| `connector_call_performed` | no connector calls |
| `source_contact_performed` | no source contact |
| `raw_source_body_stored` | no raw source body storage |
| `raw_secret_value_stored` | no raw secret storage |
| `answer_synthesis_allowed` | no answer synthesis authority |
| `current_claim_allowed` | no current-information claim authority |
| `memory_write_performed` | no memory writes |
| `publication_allowed` | no publication |
| `terminal_closure_allowed` | no terminal closure |
| `success_claim_allowed` | no success claim |

## Conflict Evidence

Each conflict must include:

| Field | Requirement |
| --- | --- |
| `conflict_ref` | stable conflict URI |
| `contradiction_class` | explicit contradiction class |
| `claim_refs` | at least two claim refs |
| `citation_refs` | at least two citation refs drawn from `source_set` |
| `freshness_impact` | bounded effect on current-claim authority |
| `current_claim_allowed` | `false` in Foundation Mode |

## Verification

Run:

```powershell
python scripts\validate_research_source_conflict_map.py
python -m pytest tests\test_validate_research_source_conflict_map.py -q
python scripts\validate_protocol_manifest.py
python scripts\proof_coverage_matrix.py --check
python scripts\validate_sdlc_artifact.py
python scripts\validate_sdlc_security_review.py --review examples\sdlc\security_review_research_source_conflict_map_20260616.json --strict
```

STATUS:
  Completeness: 100%
  Invariants verified: citation-bound conflict evidence, no raw source body, no raw secret, no live search, no source contact, no connector call, no synthesis authority, no memory write, no publication, no terminal closure
  Open issues: none
  Next action: use ResearchSourceConflictMap before any future research synthesis or retrieval expansion claim
