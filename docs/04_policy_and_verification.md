# Policy and Verification

Policy gate precedes execution. Verification closes execution.

## Policy rules

- No execution MAY begin without a `PolicyDecision` of `allow`.
- A policy decision MUST be made from admitted knowledge only.
- Policy logic MUST be separate from adapters and execution handlers.
- A policy denial or escalation MUST stop the action path.

## Policy versioning rules

- A policy version MUST be an immutable artifact with a deterministic artifact hash.
- Promotion MUST update an explicit active-version pointer only after the target version is registered.
- Rollback MUST target a previously active registered version.
- Policy diffs MUST report added, removed, changed, and unchanged rules explicitly.
- Shadow governance MUST evaluate a candidate version beside the active version without promoting it.
- Shadow governance MUST record both verdicts, reason codes, and whether the verdict changed.

## Execution rules

- An execution MAY emit an `ExecutionResult` only after the policy gate passes.
- `ExecutionResult.actual_effects` MUST be recorded from observation, not assumption.
- If observed effects differ from assumed effects, the actual effects prevail.

## Verification rules

- Every completed action MUST have exactly one terminal `VerificationResult`.
- Verification MUST reference the execution it closes.
- Verification MUST state pass, fail, or inconclusive explicitly.
- An action is not complete until verification closure exists.

## Acceptance rule

- If verification cannot be completed, the action MAY remain open only in an explicit accepted-risk state.
- Accepted risk MUST be recorded with case, owner, approver, expiry, review obligation, and evidence references.
- Accepted risk MUST NOT be created for a passing verification or matched effect reconciliation.
- Accepted risk MUST expire or close through explicit follow-up evidence.

STATUS:
  Completeness: 100%
  Invariants verified: policy gate precedence, immutable policy artifacts, deterministic artifact hashes, explicit promotion, explicit rollback, diff visibility, shadow-mode non-promotion, operator-facing policy version routes
  Open issues: none
  Next action: persist policy version registry beyond process memory
