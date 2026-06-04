<!--
Purpose: define the Foundation Mode test-evidence boundary for recording local validation evidence without claiming full coverage, CI parity, release readiness, security clearance, customer readiness, legal clearance, publication, or deployment.
Governance scope: focused-validator questions, targeted-pytest questions, full-preflight questions, receipt-validation questions, receipt routing, diff-hygiene questions, failure-case questions, warning-triage questions, coverage-gap questions, reproducibility questions, and non-terminal-closure questions.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_LOCAL_PROOF_THREAD.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, examples/foundation_test_evidence_witness.awaiting_evidence.json, examples/foundation_test_receipt_routing.awaiting_evidence.json, scripts/validate_foundation_test_evidence_boundary.py.
Invariants: no full-test-pass claim, no complete-coverage claim, no CI-parity claim, no release-readiness claim, no deployment-readiness claim, no security-clearance claim, no secret-clearance claim, no customer-readiness claim, no legal-clearance claim, no performance-readiness claim, no flake-free guarantee, no terminal-closure claim, no external publication, and no deployment claim.
-->

# Foundation Test Evidence Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** test-evidence preparation means recording which local checks
> were run, what they cover, what they do not cover, and what remains unknown.
> It does not mean the full test suite passed, coverage is complete, CI is
> equivalent, release is ready, security is cleared, secrets are cleared,
> customers are ready, legal review is complete, or deployment is allowed.

Witness packet: [`../examples/foundation_test_evidence_witness.awaiting_evidence.json`](../examples/foundation_test_evidence_witness.awaiting_evidence.json)
Receipt routing packet: [`../examples/foundation_test_receipt_routing.awaiting_evidence.json`](../examples/foundation_test_receipt_routing.awaiting_evidence.json)

Rule: Test-evidence preparation is a local planning boundary, not a full-test,
complete-coverage, CI-parity, release-readiness, deployment-readiness,
security-clearance, secret-clearance, customer-readiness, legal-clearance,
performance-readiness, flake-free, terminal-closure, external-publication, or
deployment certificate.

No full-test-pass, complete-coverage, CI-parity, release-readiness,
deployment-readiness, security-clearance, secret-clearance, customer-readiness,
legal-clearance, performance-readiness, flake-free guarantee, terminal-closure,
external-publication, or deployment claim is permitted by this boundary.

## Why This Exists

Foundation Mode runs many local validators and tests. Those checks are useful
evidence only when their scope is stated honestly. A targeted pytest run can
prove one boundary. It cannot prove the whole product. A preflight receipt can
prove the registered governance checks ran. It cannot prove customer readiness,
legal clearance, release readiness, or deployment readiness.

This boundary keeps validation useful without overclaiming:

1. focused checks can be named;
2. test scope can be separated from full coverage;
3. warnings can be recorded without hiding them;
4. receipts can be treated as local evidence, not terminal closure;
5. failed or skipped checks can remain visible.

## Current State

```text
test_evidence_boundary_state=AwaitingEvidence
receipt_routing_state=AwaitingEvidence
full_test_pass_claimed=false
complete_coverage_claimed=false
ci_parity_claimed=false
release_readiness_claimed=false
deployment_readiness_claimed=false
security_clearance_claimed=false
secret_clearance_claimed=false
customer_readiness_claimed=false
legal_clearance_claimed=false
performance_readiness_claimed=false
flake_free_guarantee_claimed=false
terminal_closure_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Test-Evidence Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Focused-validator questions | Draft which boundary validators ran. | Do not claim full-test pass. |
| Targeted-pytest questions | Draft which pytest files ran and what they cover. | Do not claim complete coverage. |
| Full-preflight questions | Draft whether the registered preflight ran locally. | Do not claim release readiness. |
| Receipt-validation questions | Draft which saved receipt was validated. | Do not claim terminal closure. |
| Diff-hygiene questions | Draft whether diff hygiene was checked and what warnings appeared. | Do not claim secret clearance. |
| Failure-case questions | Draft which negative tests protect against promotion drift. | Do not claim flake-free behavior. |
| Warning-triage questions | Draft which warnings remain accepted or unresolved. | Do not hide warnings. |
| Coverage-gap questions | Draft what the checks do not prove. | Do not claim complete coverage. |
| Reproducibility questions | Draft which command sequence can be repeated. | Do not claim CI parity. |
| Non-terminal-closure questions | Draft why passing checks are local evidence only. | Do not claim deployment, customer, legal, or commercial readiness. |

## Receipt Routing Packet

The receipt routing packet defines where local validation evidence may be
summarized before a future review. It is not a test report, release certificate,
security review, customer-access approval, legal review, publication approval,
or deployment approval.

| Route | Local receipt reference | Verification reference | Blocked promotion |
| --- | --- | --- | --- |
| Focused validator | `local_cli_summary_pending` | `scripts/validate_foundation_test_evidence_boundary.py` | full-test pass |
| Targeted pytest | `local_cli_summary_pending` | `tests/test_validate_foundation_test_evidence_boundary.py` | complete coverage |
| Full preflight | `.tmp/workspace-governance-preflight-receipt.json` | `scripts/run_workspace_governance_checks.py` | release readiness |
| Receipt validation | `.tmp/workspace-governance-preflight-receipt.json` | `scripts/validate_workspace_governance_preflight_receipt.py` | terminal closure |
| Diff hygiene | `local_cli_summary_pending` | `git diff --check` | secret clearance |
| Failure cases | `local_cli_summary_pending` | `tests/test_validate_foundation_test_evidence_boundary.py` | flake-free guarantee |
| Warning triage | `local_cli_summary_pending` | `local_operator_review_pending` | warning-free claim |
| Coverage gaps | `local_gap_summary_pending` | `local_operator_review_pending` | complete coverage |
| Reproducibility | `local_replay_summary_pending` | `local_operator_replay_pending` | CI parity |
| Non-terminal closure | `local_closure_summary_pending` | `docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md` | terminal closure |

## Operator Procedure

1. Record exact command categories, not broad readiness conclusions.
2. Keep failed, skipped, timed-out, or warning-bearing checks visible.
3. Treat preflight receipts as local governance evidence, not terminal closure.
4. Do not store private paths, secrets, account ids, branch ids, commit ids,
   customer identifiers, endpoint targets, or provider internals in the witness.
5. Keep every unproven validation claim as `AwaitingEvidence`.

## Validation

Run:

```powershell
python scripts/validate_foundation_test_evidence_boundary.py
```

The validator checks that the test-evidence witness and receipt routing packet:

1. keeps full-test pass, complete coverage, CI parity, release readiness,
   deployment readiness, security clearance, secret clearance, customer
   readiness, legal clearance, performance readiness, flake-free guarantees,
   terminal closure, external publication, and deployment blocked;
2. keeps every test-evidence surface in `AwaitingEvidence`;
3. keeps every receipt route in `AwaitingEvidence`;
4. accepts only local receipt references, public repository verification
   references, or named local review placeholders;
5. rejects private values, source-control values, endpoint values, customer
   values, secret values, or readiness-shaped values; and
6. rejects broad test, coverage, CI, release, security, customer, legal,
   publication, or deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Run the local proof thread | [Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md) |
| Prepare source-control evidence safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| See current claim truth | [Current Readiness Snapshot](CURRENT_READINESS_SNAPSHOT.md) |

STATUS:
  Completeness: 100%
  Invariants verified: full-test pass blocked, complete coverage blocked, CI parity blocked, release readiness blocked, deployment readiness blocked, security clearance blocked, secret clearance blocked, customer readiness blocked, legal clearance blocked, performance readiness blocked, flake-free guarantee blocked, terminal closure blocked, external publication blocked, deployment blocked
  Open issues: focused-validator evidence, targeted-pytest evidence, full-preflight evidence, receipt-validation evidence, receipt-routing evidence, diff-hygiene evidence, failure-case evidence, warning-triage evidence, coverage-gap evidence, reproducibility evidence, and non-terminal-closure evidence remain AwaitingEvidence
  Next action: run the test-evidence validator before using validation output as source-control evidence
