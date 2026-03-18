# Policy and Verification

Policy gate precedes execution. Verification closes execution.

## Policy rules

- No execution MAY begin without a `PolicyDecision` of `allow`.
- A policy decision MUST be made from admitted knowledge only.
- Policy logic MUST be separate from adapters and execution handlers.
- A policy denial or escalation MUST stop the action path.

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
- Accepted risk MUST be recorded and bounded by the consuming implementation.
