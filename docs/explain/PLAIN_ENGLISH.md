# Mullu Govern, Explained in Plain English

> **In one box:** Mullu Govern is software that lets a symbolic intelligence assistant do *real* tasks for
> you (send an email, pay an invoice, make a document, crunch some data) — but
> only inside strict, automatic safety rules. Every single thing it does is
> checked before it happens, written down permanently, and kept inside limits
> you set (like a spending cap). You talk to it like a person, through chat apps
> you already use.
>
> You do **not** need any technical knowledge to read this page.

---

## Current foundation posture

This page explains the product direction. The current repository posture is
[Foundation Mode](../FOUNDATION_MODE.md): private, local-first, careful setup
before deployment, customer access, company formation, paid infrastructure, or
patent filing.

In this phase, "real tasks" should be understood as future governed capability.
The safe work now is local proof: one reversible workflow at a time, with
receipts, tests, and audit evidence.

## The problem it solves

A symbolic intelligence system that can *talk* is useful but limited. A symbolic intelligence system that can *act* — actually
send the email, actually move the money — is far more useful, but also scary:
What if it sends the wrong email? What if it spends too much? What if nobody can
tell later what it did or why?

Most "symbolic intelligence agents" answer this with "trust us, it'll probably be fine." Mullu Govern
answers it with **structure**: the symbolic intelligence runtime is never allowed to act freely. It works
the way a careful organization works — with approvals, budgets, records, and
hard limits that the symbolic intelligence runtime itself cannot remove.

## An analogy

Think of Mullu Govern as **a brand-new, very capable employee on their first day**, who
operates under four unbreakable office rules:

1. **Nothing irreversible without a sign-off.** Before doing anything that
   matters (spending money, sending something external), they must get approval.
   They physically cannot skip this.
2. **A spending limit on the company card.** They have a budget. When it's used
   up, they stop. They cannot raise their own limit.
3. **A security camera on everything.** Every action is recorded in a tamper-proof
   log, in order, forever. Months later you can replay exactly what happened and
   why.
4. **A fixed job description.** They can only do the specific kinds of tasks
   they've been authorized for. They can't wander off and do something random.

The clever part: these four rules are enforced by the *building itself*, not by
the employee's good intentions. The symbolic intelligence runtime can be as smart or as confused as it
likes — it still cannot get past the rules.

(In the project's own words those four rules show up as the **approval gate**,
**budget**, **hash-chain audit trail**, and **skill boundaries**. Each of those
terms is defined in one sentence in the [Glossary](../GLOSSARY.md). You don't
need them yet.)

## What it actually does for you

You send a message in a chat app you already use — WhatsApp, Telegram, Slack,
Discord, or a web page. You ask for something real, for example:

- "Draft and send the renewal email to this client."
- "Pay this invoice if it matches the contract."
- "Pull last month's numbers into a one-page summary."

Mullu Govern figures out the steps, but **pauses at every consequential step to get
approval and stay inside your limits**. You get the result *plus* a complete,
trustworthy record of how it got there.

## What it is **not**

- It is **not** a chatbot that only talks. It does real work.
- It is **not** a symbolic intelligence system you have to blindly trust. The safety is mechanical, not a
  promise.
- It is **not** "set it loose and hope." Nothing consequential happens without
  passing the gates.

## The 30-second mental model

```
You (chat app)
      │  "do this real task"
      ▼
   Mullu Govern  ──►  plans the steps
      │
      ▼
  For each step:  Is it allowed?  Within budget?  Approved?  ── no ──► stop & ask
      │ yes
      ▼
   Do the step  ──►  record it permanently (tamper-proof log)
      │
      ▼
You get the result  +  a full, replayable history
```

That diagram *is* the product. Everything else in the documentation is detail
about one of those boxes.

---

## Where to go next

| You now want to... | Go to |
| --- | --- |
| Actually run it and watch it work, step by step | [Tutorial 1: Your First Run](../tutorials/01_first_governed_task.md) |
| Watch it govern real money (refuse an overspend, prove a payment) | [Tutorial 2: Watch Mullu Govern Real Money](../tutorials/02_a_real_governed_task.md) |
| Understand the special vocabulary | [Glossary](../GLOSSARY.md) |
| See the whole documentation map | [Start Here](../START_HERE.md) |
| Get technical fast (you're a developer) | [Quickstart](../QUICKSTART.md) |
| Understand the safety guarantees precisely | [01_shared_invariants.md](../01_shared_invariants.md) |

Nothing above this line required any prior knowledge. If something here was
still unclear, that's a documentation bug — the goal is that *anyone* can read
this page and understand what Mullu Govern is.
