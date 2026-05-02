# 37 - Terminal Closure Certificate

## Purpose

The terminal closure certificate is the final proof envelope for an
effect-bearing command. It binds the command to exactly one terminal disposition:
committed, compensated, accepted risk, or requires review.

This prevents scattered proof surfaces from being mistaken for final closure.
Effect reconciliation, compensation, accepted risk, response evidence, graph
anchors, and episodic memory can all exist, but the command is not terminally
certified until one closure certificate names the final path.

## Owned Artifacts

| Artifact | Role |
|---|---|
| `TerminalClosureCertificate` | Final certificate for one command closure |
| `TerminalClosureDisposition` | Closed-state classification |
| `TerminalClosureCertifier` | Runtime that validates and issues certificates |
| `schemas/terminal_closure_certificate.schema.json` | Public wire contract for terminal closure certificates |
| `examples/terminal_closure_certificate.json` | Canonical committed certificate example |
| `scripts/validate_terminal_closure_certificate.py` | Schema and disposition validator for certificate artifacts |

## Dispositions

| Disposition | Required proof |
|---|---|
| `committed` | Passing verification and effect reconciliation `MATCH` |
| `compensated` | Unresolved original reconciliation and successful compensation outcome |
| `accepted_risk` | Unresolved reconciliation and active accepted-risk record |
| `requires_review` | Unresolved reconciliation and case reference |

Every certificate carries command ID, execution ID, verification result ID,
effect reconciliation ID, evidence references, and closure time. Optional
surfaces include response closure reference, episodic memory entry, graph refs,
compensation outcome, accepted risk, and case.

## Hard Invariants

1. No committed certificate without passing verification.
2. No committed certificate without reconciliation `MATCH`.
3. No compensated certificate without successful compensation outcome.
4. No accepted-risk certificate without active accepted risk and case.
5. No review-required certificate without case.
6. No terminal certificate without evidence references.
7. A terminal certificate records final disposition; it does not invent missing
   lower-layer proof.

## Closure Shape

```text
EffectReconciliation MATCH
  -> TerminalClosureCertificate(committed)

EffectReconciliation unresolved
  -> CompensationOutcome succeeded
  -> TerminalClosureCertificate(compensated)

EffectReconciliation unresolved
  -> AcceptedRiskRecord active
  -> TerminalClosureCertificate(accepted_risk)

EffectReconciliation unresolved
  -> Case open
  -> TerminalClosureCertificate(requires_review)
```

The certificate is a capstone, not a bypass. It only certifies paths that lower
layers have already proven.

## Validation

```bash
python scripts/validate_terminal_closure_certificate.py --certificate examples/terminal_closure_certificate.json --json
```

Expected result: `valid=true`.
