# ClarificationRequest Contract

Purpose: define the public missing-slot clarification contract used before a
vague action-like request can become a plan, search, approval request, command,
or execution.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: `schemas/clarification_request.schema.json`,
`examples/clarification_request.foundation.json`,
`scripts/validate_clarification_request.py`, and gateway interpretation tests.
Invariants: raw user text is represented by hash only; one focused question is
allowed; `safe_default` remains `no_execution`; no execution, approval,
connector, deployment, launch, production, customer, or support readiness is
claimed.

## 1. Boundary

`ClarificationRequest` is an interpretation-layer blocker. It records that a
request is too underspecified for planning or execution and asks exactly one
safe question.

It is not:

- a plan;
- an approval;
- a command;
- a connector grant;
- a runtime registration;
- a terminal closure certificate.

## 2. Foundation Profile

The Foundation Mode profile is:

```text
missing_fields: target, allowed_action
reason: missing_required_interpretation_slots
max_questions: 1
safe_default: no_execution
raw_message_hash: hash-only message reference
```

The one-question limit closes the drift between the runtime gateway behavior
and the public contract. A clarification request may block progress, but it
must not expand into multi-question intake, planning, or approval by itself.

## 3. Validation

Run:

```powershell
python scripts/validate_clarification_request.py
python -m pytest tests/test_validate_clarification_request.py tests/test_gateway/test_interpretation.py -q
```

Before claiming release closure, also run schema, protocol, SDLC, root coverage,
and workspace governance preflight checks.

## 4. Status

STATUS:
  Completeness: 100%
  Invariants verified: one focused question, no_execution default, hash-only raw message boundary, no execution authority, no approval authority, Foundation Mode
  Open issues: none for the Foundation Mode public contract
  Next action: keep broader clarification-engine slot expansion as a separate proof thread
