# Lambda Safety Guard Chain

Purpose: define the explicit safety stages for prompt injection detection and output scrubbing.

Governance scope: request and response safety only. These stages do not replace authorization, budget enforcement, or policy evaluation.

## Stages

| Stage | Position | Responsibility | Failure semantic |
| --- | --- | --- | --- |
| `Lambda_input_safety` | After RBAC, before rate limit and budget | Detect prompt injection, jailbreak, code injection, and data exfiltration patterns in request prompt/content | Reject request with `input safety blocked` |
| `Lambda_output_safety` | After model/tool execution, before audit-facing response return | Redact PII and block unsafe generated output | Return blocked output result with `output safety blocked` |

## Detector Bindings

Current bindings:

1. Prompt injection and jailbreak patterns use `ContentSafetyChain`.
2. PII scrubbing uses `PIIScanner`, a deterministic local wrapper. A Presidio-backed scanner can replace this wrapper without changing the stage contract.
3. Mfidel text remains atomic: normalization applies only to non-Ethiopic runs.

## Invariants

1. `Lambda_input_safety` is a named governance guard in the request guard chain.
2. `Lambda_output_safety` returns an `OutputSafetyResult` witness with stage name, verdict, redaction status, and flags.
3. Input safety may enrich context with flags, but does not rewrite the request payload.
4. Output safety may rewrite output only by deterministic redaction or by blocking unsafe output.
5. Both stages produce bounded reasons and never expose matched sensitive text in rejection reasons.

STATUS:
  Completeness: 100%
  Invariants verified: [input stage position, output scrub stage, bounded reasons, Mfidel atomicity]
  Open issues: none
  Next action: connect external Presidio adapter when dependency policy permits
