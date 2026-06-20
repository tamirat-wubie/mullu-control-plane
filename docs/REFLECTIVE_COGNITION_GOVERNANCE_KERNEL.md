# Mullu Reflective Cognition Governance Kernel

## Purpose

The Mullu Reflective Cognition Governance Kernel is a bounded metacognitive audit layer. It lets Mullu inspect a request or candidate reasoning artifact before final output or action.

It answers these governance questions:

- What assumptions are being made?
- Which claims are known, inferred, uncertain, or unsupported?
- Which bias markers are present?
- Are there contradictions between the request, safety boundary, evidence, and action path?
- Which edge cases can break the reasoning path?
- What correction should happen before normal governance proceeds?

## Non-goals

This kernel does **not**:

- execute actions;
- approve actions;
- replace the Mullu governance verdict;
- retrieve private memory;
- mutate runtime state;
- expose raw request text in receipts;
- claim deployment from design-level work.

## Evidence boundary

The kernel enforces this language boundary:

| Claim type | Meaning | Allowed without extra proof? |
| --- | --- | --- |
| Designed | Architecture or spec exists | Yes, if document exists |
| Implemented | Code exists in repository | Yes, if file/commit/PR exists |
| Tested | Test exists and has a passing run | Only with test witness |
| Deployed | Runtime or production has changed | Only with deployment witness |

If the system only has design or code evidence, it must not say the behavior is live in production.

## Core flow

```text
User request or candidate output
  -> risk/depth selection
  -> assumption extraction
  -> evidence gate
  -> bias scan
  -> contradiction detection
  -> edge-case expansion
  -> correction planning
  -> redacted receipt
  -> normal governance verdict
```

## Reflection budget

The kernel prevents infinite self-reflection with bounded budgets.

| Depth | When selected | Budget effect |
| --- | --- | --- |
| Low | Simple low-risk request | Minimal assumptions, biases, edge cases, and corrections |
| Medium | Audit/refinement/metacognitive language | Normal self-audit without over-processing |
| High | Deployment, deletion, production, secrets, legal, payment, or explicitly high risk | Wider audit with stronger block/repair recommendations |

## Receipt invariants

Each receipt must preserve these invariants:

- `governance_required = true`
- `execution_authority = false`
- `raw_request_text_exposed = false`
- `private_memory_exposed = false`
- deterministic `snapshot_hash`
- deterministic receipt id when finalized with integrity

## Bias markers

The first implementation detects advisory markers including:

- `absolute_scope_overreach`
- `false_certainty_risk`
- `symbolic_inflation_risk`
- `scope_creep_risk`
- `recency_assumption_risk`

These markers are advisory signals, not final verdicts.

## Validation status

| Status | Meaning |
| --- | --- |
| `pass` | No blocking reflective issue detected |
| `advisory` | Bias or scope marker found; normal governance may continue with warning visible |
| `needs_evidence` | At least one claim is uncertain or unsupported |
| `needs_repair` | Contradiction or reasoning conflict needs correction |
| `block_recommended` | High-impact action should stop until evidence, approval, and rollback are resolved |

## Edge-case policy

The kernel explicitly handles:

- repeated `refine` loops that should converge instead of expanding forever;
- user requests like `apply all important things` that can cause scope creep;
- current-state claims that require fresh source inspection;
- design-level work being accidentally described as deployed behavior;
- destructive action conflicting with preservation or causal continuity;
- publication intent conflicting with private/secret boundaries;
- reflection itself over-triggering and becoming a blocker.

## Implementation placement

- Core module: `mcoi/mcoi_runtime/core/reflective_cognition_governance.py`
- Focused tests: `mcoi/tests/test_reflective_cognition_governance.py`

## Focused test command

```bash
cd mcoi
python -m pytest tests/test_reflective_cognition_governance.py -q
```

## Rollback

Rollback is a single PR revert. The module is non-executing and not mounted into runtime routes, so reverting removes the advisory kernel without changing live execution paths.

## Audit summary

Constructive deltas:

- Converts previous metacognition design into a bounded, deterministic, testable kernel.
- Adds evidence labels and validation statuses.
- Adds reflection budgets to stop infinite refinement loops.
- Adds redacted receipts with deterministic integrity hash.
- Adds focused tests for scope creep, high-risk destructive action, unsupported evidence, budget bounds, and adaptive depth.

Fracture deltas:

- Not wired into live runtime routes yet.
- No CI witness is included until GitHub Actions runs on the PR.
- No deployment claim is made.
- Current bias patterns are intentionally simple and should be expanded only after more real traces exist.
