# Mullu Govern, Explained in Plain English

> **In one box:** Mullu Govern is being built to make AI action governable,
> auditable, and accountable. It lets a symbolic intelligence assistant help
> with consequential work only through strict controls: approval, policy, budget,
> evidence, audit, and rollback. The current repository is not a public service.
> It is in careful Foundation Mode setup.
>
> You do **not** need technical knowledge to read this page.

---

## Mission

Mullusi exists to make powerful AI systems safe enough to trust.

AI is moving from answering questions into taking actions. That can be useful,
but it also creates risk. When AI touches work, tools, files, budgets, messages,
or operations, people need to know what happened, why it happened, who approved
it, what evidence supported it, and how to recover if something goes wrong.

Mullu Govern is the control layer for that problem.

It does not try to make AI free-running or unchecked. It tries to make AI-driven
action limited, reviewable, approval-bound, evidence-backed, and auditable.

## Current foundation posture

This page explains the product direction in plain words. The current repository
posture is [Foundation Mode](../FOUNDATION_MODE.md): private, local-first,
careful setup before deployment, customer access, company formation, paid
infrastructure, money movement, or patent filing.

Plain-language status is bounded by the
[Foundation Plain-Language Status Boundary](../FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md).
Nothing on this page claims public launch, customer access, legal clearance,
paid use, or deployment.

In this phase, action examples should be understood as future governed
capability. The safe work now is local proof: one reversible workflow at a time,
with receipts, tests, and audit evidence.

## The problem it is meant to solve

An AI system that can talk is useful but limited. An AI system that can help act
on consequential work is more useful and also more risky. The hard questions are
simple:

1. What did the system do?
2. Why did it do it?
3. Who approved the action?
4. Was it allowed by policy?
5. Was it inside budget?
6. What evidence did it use?
7. Can the action be audited later?
8. What happens if something goes wrong?

Mullu Govern answers those questions with structure. A runtime is not supposed
to act freely. It must pass gates, stay inside limits, emit receipts, and leave
an auditable trail.

## The solution in plain words

Mullu Govern turns AI-driven work into governed proposals and proof-backed
outcomes.

Before important action happens, the system checks:

1. authority;
2. policy;
3. budget;
4. evidence;
5. risk;
6. approval;
7. rollback and recovery path.

If a step is blocked, it records why. If a step is allowed, it creates evidence
and a receipt so the result can be reviewed later.

## An analogy

Think of Mullu Govern as a careful workroom for a new assistant. The assistant
may be capable, but the room has fixed rules:

1. **Nothing consequential without a sign-off.** Important actions require an
   approval gate.
2. **A hard budget limit.** Spending-related work must stay inside an approved
   budget.
3. **A record on every step.** Actions produce receipts and audit records.
4. **A fixed job boundary.** The assistant can only use capabilities that have
   been explicitly allowed.
5. **A recovery path.** Serious work must be reviewable, reversible where
   possible, or escalated when recovery is unclear.

The important part is that the rules are enforced by the system, not by trust in
the assistant's good intentions.

## Why this matters for the AI market

Most AI products focus on intelligence output: answers, summaries, code,
messages, images, or plans.

Mullu Govern focuses on controlled action.

The market contribution is simple:

```text
AI can help, but important action should pass through governance first.
```

That makes Mullu Govern closer to a trust layer for AI actions than a chatbot or
foundation model. It can support developers, operators, companies, researchers,
auditors, and future AI-agent platforms that need proof before trust.

## AGI and ASI fear boundary

Mullu Govern should not be described as an AGI or ASI product.

The safer and clearer message is:

```text
Mullu Govern is not built to unleash unchecked machine autonomy.
It is built to limit, verify, and govern AI-driven action.
```

People fear advanced AI because they imagine unbounded autonomy, hidden
decisions, unapproved actions, runaway cost, private-data exposure, or systems
acting faster than humans can stop them. Mullu Govern responds by making action
approval-bound, policy-bound, budget-bound, evidence-bound, and auditable.

## What it is meant to do later

When the required evidence exists, future examples could include:

- drafting an external message and pausing before it is sent;
- checking whether an invoice-related action is allowed before any money moves;
- summarizing local records into a report;
- asking for approval when a step crosses a policy, budget, or evidence
  boundary;
- giving an operator a bounded read model of what is blocked, waiting, approved,
  or proof-ready.

Those are product-direction examples, not current customer access claims.
Foundation Mode keeps them local until the required witnesses exist.

## What it is not

- It is **not** a free-running assistant.
- It is **not** an AGI or ASI claim.
- It is **not** a promise that the current repository is deployed.
- It is **not** customer-ready, legally cleared, commercially ready, or paid-use
  ready.
- It is **not** a reason to spend money, use secrets, invite users, open
  waitlists, or publish access.
- It is **not** proof of live payment execution, live email delivery, bank
  settlement, or production finance automation.

## The 30-second mental model

```text
You ask for a consequential task
        |
        v
Mullu Govern turns it into a bounded proposal
        |
        v
The step must pass policy, authority, budget, evidence, risk, and approval gates
        |
        +-- if blocked: stop and record why
        |
        v
If allowed, execute only the permitted step
        |
        v
Write a receipt, preserve evidence, and keep the action auditable
```

That diagram is the product direction. In Foundation Mode, the current work is
to prove the local control shape before any public or customer-facing use.

---

## Where to go next

| You now want to... | Go to |
| --- | --- |
| Read the mission statement | [Public Mission Statement](../PUBLIC_MISSION_STATEMENT.md) |
| Stay realistic about the current status | [Foundation Mode](../FOUNDATION_MODE.md) |
| See the careful prerequisite checklist | [Foundation Prerequisites](../FOUNDATION_PREREQUISITES.md) |
| Check the plain-language claim boundary | [Foundation Plain-Language Status Boundary](../FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md) |
| Understand the special vocabulary | [Glossary](../GLOSSARY.md) |
| See the whole documentation map | [Start Here](../START_HERE.md) |
| Understand the safety guarantees precisely | [01_shared_invariants.md](../01_shared_invariants.md) |

Nothing above this line requires prior technical knowledge. If something here is
still unclear, that is a documentation gap to record, not a readiness claim.