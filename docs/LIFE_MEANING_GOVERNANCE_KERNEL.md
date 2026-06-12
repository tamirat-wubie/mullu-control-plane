Purpose: translate Universal Symbol Continuity and Meaning-Through-Feeling Theory into an executable Mullu Control Plane governance layer.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS for Universal Action Orchestration preflight.
Dependencies: docs/UNIVERSAL_SYMBOL_CONTINUITY_DOCTRINE.md, docs/MEANING_THROUGH_FEELING_THEORY.md, schemas/life_meaning_judgment.schema.json, and mcoi/mcoi_runtime/core/life_meaning_governance.py.
Invariants: every effect-bearing action receives a LifeMeaningJudgment; unknown life or feeling impact with irreversible action escalates; dignity failure or domination risk blocks.

# Mullu Life-Meaning Governance Kernel

Mullu Control Plane should not only ask:

1. Can this action run?
2. Is it allowed by policy?
3. Is there budget?
4. Is there approval?
5. Is there proof?

It must also ask:

1. What symbols are affected?
2. Does this touch life?
3. Does this touch feeling?
4. Does this touch meaning?
5. Does this touch dignity, consent, identity, memory, habitat, or future continuity?
6. Does it increase love or domination?
7. Does it create resonance or forced harmony?
8. Does it preserve truth?
9. Can harm be repaired?
10. Should this pass, pause, block, or escalate?

## Core Application Formula

```text
Universal Symbol Continuity Doctrine
+ Meaning-Through-Feeling Theory
+ Love-Resonance Governance
+ Truth / Dignity / Justice / Consent / Repair
  -> Mullu Life-Meaning Governance Kernel
  -> LifeMeaningJudgment contract
  -> Universal Action Orchestration preflight
  -> Policy / Budget / Approval / Evidence gates
  -> Execution, pause, block, or escalation
  -> Receipt, proof, audit, rollback, repair record
```

This makes the doctrine executable:

```text
Mullu refuses, pauses, or escalates actions when life, feeling, meaning,
dignity, consent, love, resonance, truth, or continuity are at risk.
```

## Runtime Object

The central object is:

```text
LifeMeaningJudgment
```

It answers:

1. What symbols are affected?
2. Which are alive?
3. Which may feel?
4. Which carry meaning?
5. Which are fragile?
6. Which have agency?
7. Which have dignity or consent boundaries?
8. Is life impact none, indirect, direct, or unknown?
9. Is feeling impact none, indirect, direct, or unknown?
10. Is meaning impact none, indirect, direct, or unknown?
11. Is there domination risk?
12. Is truth preserved?
13. Is love positive, neutral, negative, or unknown?
14. Is resonance positive, neutral, negative, or unknown?
15. Is justice or repair required?
16. Is the action reversible?
17. Is approval required?
18. Is evidence required?
19. Is rollback required?
20. Should Mullu pass, pause, block, or escalate?

## Pre-Execution Gate

Existing no-bypass rule:

```text
effect_bearing(action) and not passed_through_UAO(action)
  -> deny(action, reason="unorchestrated_effect")
```

Life-meaning addition:

```text
effect_bearing(action) and missing_life_meaning_judgment(action)
  -> deny(action, reason="missing_life_meaning_judgment")
```

Decision mapping:

```text
life_meaning.decision == pass
  -> continue to policy, budget, approval, and execution gates

life_meaning.decision == pause
  -> require evidence, approval, or bounded sensing before execution

life_meaning.decision == block
  -> deny action and retain evidence

life_meaning.decision == escalate
  -> route to operator, Phi_gov, or authority review
```

## Workflow Spine

Recommended governed workflow order:

```text
stage_intake
-> stage_classify_symbols
-> stage_life_meaning_judgment
-> stage_policy_authority_check
-> stage_budget_check
-> stage_approval_gate
-> stage_execute_or_prepare
-> stage_verify_effect
-> stage_repair_or_rollback_note
-> stage_close_receipt
```

Foundation Mode implementation may use an ordinary task first:

```json
{
  "task_id": "life-meaning-check",
  "task_type": "task",
  "action": "life_meaning.judge",
  "verification_required": true,
  "evidence_required": ["life-meaning://judgment"]
}
```

## Domain Defaults

Local proof document:

```text
meaning impact: none
decision: pass
```

Finance payment handoff:

```text
meaning impact: indirect
decision: approval/evidence required unless consent and proof are present
```

External deployment:

```text
meaning impact: indirect or unknown
decision: pause or escalate until witness evidence closes
```

Unknown environment:

```text
meaning impact: unknown
decision: escalate or precautionary block
```

## Public-Safe Mission

Mullusi builds governed symbolic intelligence because power should protect the
life that makes meaning possible.

Allowed Foundation Mode claim:

```text
Mullu has a local, testable governance model for life, feeling, meaning, love,
resonance, dignity, consent, truth, justice, repair, and continuity impact.
```

Do not claim life-safety certification, production ethical readiness, customer
readiness, deployment readiness, legal clearance, or expansion readiness
without explicit witness evidence.
