# Glossary

> **In one box:** Every special word used anywhere in this project, explained in
> **one plain sentence**. Then a "deeper" link if you want the full story. This
> page is what makes the docs safe to read at any level — if a page uses a word
> you don't know, it's defined here.

How to use this page: skim it once before reading anything technical, then come
back whenever a term trips you up. Terms are alphabetical. Each entry is:

**Term** — plain one-sentence meaning. *(why it matters)* → deeper link.

---

### 8-guard chain
A fixed sequence of eight automatic checks that every action must pass before it
is allowed to run. *(This is the core safety mechanism — the symbolic intelligence runtime cannot skip
it.)* → [04_policy_and_verification.md](04_policy_and_verification.md)

### Approval gate
The point where Mullu Govern stops and waits for a human "yes" before doing something
consequential. *(Nothing irreversible happens without passing this.)* →
[04_policy_and_verification.md](04_policy_and_verification.md)

### Audit trail (hash-chain)
A permanent, tamper-evident log where every action is recorded in order; each
entry is mathematically linked to the one before it, so any later edit is
detectable. *(This is the "security camera" — it makes the past trustworthy.)*
→ [03_trace_and_replay.md](03_trace_and_replay.md)

### Budget (spend budget)
A hard limit on money (or other resources) for a task; when it's exhausted,
Mullu Govern stops rather than continuing. *(The symbolic intelligence runtime cannot raise its own limit.)* →
[01_shared_invariants.md](01_shared_invariants.md)

### Capability / capability plane
A specific kind of real-world thing Mullu Govern is allowed to do (e.g. "send email",
"make payment"), grouped into "planes" by category. *(Mullu Govern can only do listed
capabilities, nothing else.)* → [06_capability_planes.md](06_capability_planes.md)

### Capability forge / solver forge
The subsystem that proposes, tests, and only then admits new capabilities — a
candidate must beat a baseline on a real metric *and* survive an adversarial
review before it's allowed in. *(New powers are earned, not assumed.)* →
[66_solver_forge_loop.md](66_solver_forge_loop.md)

### Capsule
A self-contained, governed package of a domain's work (its rules plus steps)
that the platform can run as one unit. *(How a domain plugs into the governed
core.)* → [39_governed_capability_fabric.md](39_governed_capability_fabric.md)

### Closure
A formal "this unit of work is fully accounted for — every effect is recorded
and nothing is left dangling" state. *(It's the project's word for "provably
finished and clean.")* → [01_shared_invariants.md](01_shared_invariants.md)

### Control plane
The part of the system that decides, checks, and records — as opposed to the
part that does raw work. *(Mullu Control Plane is the internal/admin technical
surface behind Mullu Govern.)* →
[00_platform_overview.md](00_platform_overview.md)

### Domain adapter / domain pack
A plug-in that teaches Mullu Govern the rules and tasks of one specific field (e.g. a
particular industry workflow). *(Lets the same governed core serve many
domains.)* → [06_capability_planes.md](06_capability_planes.md)

### Effect
An actual change to the real world the system caused (an email sent, money
moved), recorded separately from what it merely intended. *(The system tracks
intended vs actual effects so reality always wins.)* →
[01_shared_invariants.md](01_shared_invariants.md)

### Evidence packet
A governed bundle of source-bound observations that can be checked before it is
allowed to influence planning. *(It keeps planning tied to current evidence
instead of assumptions.)* -> [94_observation_evidence_acquisition_architecture.md](94_observation_evidence_acquisition_architecture.md)

### Gateway
The entry layer that receives messages from chat apps (WhatsApp, Slack, etc.)
and hands them to the control plane. *(It's the "front desk".)* →
[00_platform_overview.md](00_platform_overview.md)

### Foundation Mode
The current private, local-first project posture for careful setup before
deployment, public launch, company formation, paid infrastructure, or patent
filing. *(It keeps the next step small, reversible, and evidence-bound.)* ->
[FOUNDATION_MODE.md](FOUNDATION_MODE.md)

### Governance laws (OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS)
Seven hard rules every piece of work must satisfy — roughly: define everything,
make relationships explicit, trace every cause, keep constraints decidable,
record decisions, keep recursion terminating, and stamp completed work with
proof. *(If one can't be met, the system halts instead of producing an unsafe
result.)* → [`../AGENTS.md`](../AGENTS.md)

### Governed swarm
A mode where multiple worker agents collaborate on a task, still under all the
normal gates, budgets, and audit rules. *(Many workers, same safety.)* →
[governed-swarm-staging-activation-runbook.md](governed-swarm-staging-activation-runbook.md)

### Invariant
A statement that is *always* true in the system, by construction (e.g. "no
action runs without an audit record"). *(Invariants are the promises the system
will never break.)* → [01_shared_invariants.md](01_shared_invariants.md)

### Lineage
The recorded chain of "what led to what" — which input, decision, and prior
step produced a given result. *(Lets you trace any outcome back to its cause.)*
→ [03_trace_and_replay.md](03_trace_and_replay.md)

### Local proof thread
One small workflow run only on the local machine to prove policy, approval,
receipt, audit, and closure before any public deployment. *(It proves the core
shape without creating external risk.)* -> [FOUNDATION_MODE.md](FOUNDATION_MODE.md)

### MAF Core / MCOI Runtime
Two deliberately separated parts: MAF Core is the shared meaning / architecture
layer; MCOI Runtime is the code that actually runs. *(Kept split on purpose so
the two never blur together.)* → [00_platform_overview.md](00_platform_overview.md)

### MCOI
The name of the core runtime package/engine inside this repo (the code you
install and run). *(When docs say `mcoi_runtime`, that's this.)* →
[QUICKSTART.md](QUICKSTART.md)

### Obligation
A required follow-up the system must fulfil after an action (e.g. a recovery or
notification it now owes). *(Promises the system must keep, tracked
explicitly.)* → [39_governed_capability_fabric.md](39_governed_capability_fabric.md)

### Observation Evidence Acquisition Architecture
The system boundary that turns read-only sensing into admitted evidence packets
before planning, execution admission, verification, recovery, or learning can
use them. *(It is how Mullu checks what is true before deciding what to do.)*
-> [94_observation_evidence_acquisition_architecture.md](94_observation_evidence_acquisition_architecture.md)

### Phi traversal (spine)
A fixed thinking order the agent applies to a problem — distinction, then
relation, then cause, and so on — so reasoning is structured and auditable
rather than ad hoc. *(It's the standard "order of operations" for the agent's
analysis.)* → [PHI_CANONICAL_SPEC.md](PHI_CANONICAL_SPEC.md)

### Policy / policy prover
The rules that say what is and isn't allowed, plus the component that
*mathematically checks* an action against them before it runs. *(Verification,
not just hope.)* → [04_policy_and_verification.md](04_policy_and_verification.md)

### Proof receipt / execution receipt
A signed record produced after a task that proves what was done and that the
rules were followed. *(Evidence you can verify later, even offline.)* →
[65_trust_ledger_offline_verification.md](65_trust_ledger_offline_verification.md)

### Receipt
Short for execution / proof receipt — the signed evidence produced after a task
proving what happened. *(See "Proof receipt / execution receipt" above.)* →
[37_terminal_closure_certificate.md](37_terminal_closure_certificate.md)

### Replay
Re-running a recorded history exactly, to see precisely what happened and why.
*(Turns the audit log into something you can step through.)* →
[03_trace_and_replay.md](03_trace_and_replay.md)

### Skill / skill boundary
A defined unit of "something Mullu Govern knows how to do", and the hard edge that
keeps it from doing things outside its authorized skills. *(The symbolic intelligence runtime's "job
description".)* → [19_skill_system.md](19_skill_system.md)

### Symbolic intelligence
This project's term for its approach: meaning is built from explicit, atomic
symbols and explicit relationships, rather than left implicit. *(It's the design
philosophy behind the governance laws.)* → [`../AGENTS.md`](../AGENTS.md)

### Trust ledger
An append-only record of trust-relevant outcomes that can be independently
verified, even without access to the live system. *(Trust you can check
yourself.)* → [65_trust_ledger_offline_verification.md](65_trust_ledger_offline_verification.md)

### ProblemStar compilation receipt
A read-only receipt showing that raw input was separated into canonical
Phi-GPS fields, evidence, assumptions, unknowns, contradictions, actions, and
proof obligations before solver routing. *(It proves framing; it does not grant
execution authority.)* -> [75_problem_star_compilation_receipt.md](75_problem_star_compilation_receipt.md)

### Truth kernel / Truth Kernel Plane
The internal MAF Core subsystem that checks candidate truth states against
declared domains, constraints, and proofs before anything can be treated as
true. *(It keeps truth-state reasoning separate from action execution.)* →
[74_truth_kernel_plane.md](74_truth_kernel_plane.md)

### Witness / witness anchoring
A piece of evidence attached to a claim or proof so that the claim can be
checked rather than taken on faith; "anchoring" means tying that evidence to a
specific, labeled point. *(It's how the system makes its proofs checkable.)* →
[mullu-trust-boundary-map.md](../../docs/mullu-trust-boundary-map.md)

### World-state plane
The system's structured model of "what is currently true in the world" that the
agent reasons over. *(The agent's map of reality.)* →
[16_world_state_plane.md](16_world_state_plane.md)

---

## Missing a term?

If you hit a word in any doc that isn't here, that's a documentation gap worth
fixing. Add it using this pattern:

```
### Term
One plain sentence a non-expert can understand. *(Why it matters.)*
→ [deepest relevant doc](path.md)
```

Keep the sentence jargon-free even if the deep doc is highly technical — the
whole point of this page is to be the safe landing spot for every reader level.

← Back to [Start Here](START_HERE.md) · [Plain-English Overview](explain/PLAIN_ENGLISH.md)
