# Design: wiring the live operator path through the CognitiveLoop

Status: **DRAFT for review — no code yet.** Author: Claude (Opus 4.8). Date: 2026-06-03.
Scope: the single highest-leverage refinement from the agentic-capability audit — turning the
dormant cognitive organs on for live HTTP traffic. This document exists to surface the two
decisions that are the user's to make (determinism/replay posture, governance posture) BEFORE any
code is written.

## 1. Problem (grounded in current code)

Two execution paths exist and never meet:

- `core/whqr_mil_orchestrator.run_whqr_mil_orchestration()` — the "acting spine" with OPTIONAL
  meta-reasoning + complexity hooks. Audited test-only / zero production callers
  (see `project_whqr_spine_cognition_wiring`). Its gates are default-OFF (`meta_reasoning=None`).
- `app/operator_loop.py::OperatorLoop.run_step()` → `app/governed_execution.py::
  governed_operator_mil_dispatch_with_trace()` — the ACTUAL HTTP-serving path. **Single-shot.**
  It consults almost none of the bootstrapped cognitive engines.

So the engines instantiated in `app/bootstrap.py` — `MetaReasoningEngine`, `DecisionLearningEngine`
(added this campaign), `WorldStateEngine`, `EpisodicMemory`/`SemanticMemoryStore`,
`MILLearningAdmissionGate` — are a "brain in a jar": built, mounted, never consulted live. Grep
confirms **no router references** meta_reasoning / decision_learning / world_state /
episodic_memory / cognitive_loop. `record_outcome` runs live only for provider-health; the
dashboard merely DISPLAYS learned factors.

The `CognitiveLoop` (shipped, default-OFF behind `MULLU_COGNITIVE_LOOP_ENABLED`) already wraps the
EXISTING governed dispatch with observe→decide→act→verify→learn→(replan|terminate) and consults
those engines. **The remaining work is wiring, not building.**

## 2. Goal

Route live operator requests through `CognitiveLoop` so that, per step:
- DECIDE consults meta-reasoning + ProofState before dispatch (degraded/low-confidence ⇒ replan or
  SafeHalt; UNKNOWN hard constraint ⇒ GovernanceBlocked).
- ACT delegates to the unchanged `governed_operator_mil_dispatch_with_trace` (no governed semantics
  touched).
- VERIFY combines the mechanical proof with the inner critic (PR #1248).
- LEARN feeds decision_learning + meta_reasoning + episodic, gated by admission (rollback-safe).
…all WITHOUT weakening the platform's defining property: deterministic, replayable, append-only
governed execution.

## 3. The core tension (why this needs a human decision)

The platform's identity is determinism: byte-identical proof hashes, append-only replay
(`universal_command_orchestration_record_view` already replays hash-bound UAO records), the F8
closure work. An iterative loop that *replans* and a critic that may *sample a second model*
introduce non-determinism and latency. **The decision is not "add the loop" — it is where to spend
the determinism budget.**

Good news: the dispatch path is ALREADY single-shot-deterministic and ALREADY records replayable
orchestration records per command. The loop adds a control layer ABOVE dispatch. So the determinism
question reduces to: **how is the loop's own trajectory (which steps ran, each DECIDE verdict, each
replan, the critic verdict) made replayable?**

## 4. Proposed approach (staged, each stage independently shippable + default-OFF)

### Stage A — shadow mode (zero risk, pure observability)
Run the `CognitiveLoop` ALONGSIDE the existing `run_step` for the SAME request, but discard the
loop's control decisions — `run_step` still drives the real dispatch. The loop's DECIDE/VERIFY/LEARN
run in record-only mode; emit its `CognitiveLoopReport` as a trace artifact next to the existing
report. This proves: (1) the loop reaches the same ACT outcome as today on real traffic, (2) what
the meta-reasoning gate WOULD have blocked/replanned, (3) measured latency overhead. No behavior
change. Gated by a new `MULLU_COGNITIVE_LOOP_SHADOW` flag.

### Stage B — enforce DECIDE only (pre-dispatch gating)
Promote the loop's DECIDE gate from shadow to live: a degraded-capability or UNKNOWN-hard-constraint
verdict can now BLOCK dispatch (SafeHalt / GovernanceBlocked) before any effect. This is the
safety-positive half — it can only ever REFUSE to act, never act more. Still single dispatch per
request (no replan yet), so determinism is unchanged. The replan ceiling stays 0.

### Stage C — bounded replan + live LEARN
Allow >1 bounded iteration (max_steps/budget already in CognitiveLoop) and let LEARN write back to
decision_learning + episodic under the admission gate. This is the first point that introduces
multi-step non-determinism and a persistent learning side-effect, so it ships LAST and only after
the determinism/governance decisions below are made.

## 5. DECISIONS NEEDED FROM THE USER

**D1 — Determinism / replay posture for the loop trajectory.** Options:
  (a) *Record-and-replay the trajectory* (recommended): treat each loop step like dispatch does —
      append the DECIDE verdict, replan, and critic verdict to the command ledger as hash-bound
      events, so a run replays exactly. Critic stays deterministic (PR #1248's critics are pure;
      a future model-backed critic would be recorded, replayed from the record, never re-sampled).
  (b) *Forbid non-determinism in the loop* — keep critics/replan purely rule-based forever. Simpler,
      but caps the capability at heuristics.
  (c) *Loop is advisory only* — never gates live (shadow forever). Lowest value.

**D2 — Governance posture.** Does promoting DECIDE to a live BLOCK (Stage B) require a `Phi_gov`
authority sign-off / a governance review, given it changes when the system refuses to act? My
assumption: yes for Stage B+, no for Stage A (shadow is observability only). Confirm.

**D3 — Scope of first cut.** Recommended: ship **Stage A (shadow) only** next, behind its own flag,
gather real-traffic evidence, then revisit B/C with data. Confirm or widen.

## 6. What I will NOT do without explicit go
- Touch `governed_operator_mil_dispatch_with_trace` semantics or any governed dispatch internals.
- Enable any flag by default.
- Write back to learning/episodic on the live path (Stage C) before D1/D2 are decided.

## 7. Test/verification plan (when greenlit)
- Stage A: a test asserting shadow loop report is emitted AND the real dispatch outcome is
  byte-identical to no-shadow (the loop cannot perturb the result). Reflective-contract guard +
  full MCOI shards green. Determinism test: same request ⇒ identical shadow report hash.
- Stage B: tests for block-on-degraded / block-on-unknown-constraint on the live path; proof that a
  non-degraded request is unaffected.
- Stage C: replan-bounded + admission rollback tests; replay test proving a recorded trajectory
  replays identically.

---
This doc is the deliverable for "draft the live-wiring design." It is intentionally code-free.
Resume = user answers D1–D3, then implement Stage A behind `MULLU_COGNITIVE_LOOP_SHADOW`.
