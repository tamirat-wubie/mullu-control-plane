# Code Change Physics

Purpose: define how code-change planning uses physics-style structure for
governance, creative solution discovery, and repair without granting execution
authority.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS; Universal Action
Orchestration; Foundation Mode; software-development capability planning.

Dependencies:
- `docs/20_code_automation_plane.md`
- `docs/60_logic_governance_application.md`
- `docs/66_solver_forge_loop.md`
- `schemas/code_change_physics_packet.schema.json`
- `examples/code_change_physics_packet.foundation.json`
- `scripts/validate_code_change_physics_packet.py`

Invariants:
- Physics terms are planning symbols, not execution permission.
- The packet discovers safer paths; it does not bypass governance gates.
- A selected path cannot require a live effect unless it is reported as blocked
  or awaiting evidence.
- Every pressure, barrier, or repair claim has an evidence reference.
- Mfidel atomicity is unchanged and cannot be weakened by analogy.

---

## 1. Decision

Code-change planning uses three physics lanes:

| Lane | Role | Core question | Output |
| --- | --- | --- | --- |
| Code Governance Physics | Blocks unsafe movement | Is this movement allowed? | barriers, proof need, approval burden |
| Code Creative Physics | Finds better movement | What lower-risk path still gives value? | indirect paths, bottleneck release, pressure valves |
| Code Repair Physics | Restores stable movement | What drift or instability must be repaired first? | entropy checks, rollback paths, repair-first deltas |

The model is invalid if it only says "stop" when a lower-risk, non-effecting
path can preserve value. The model is also invalid if it uses creativity to
smuggle an unapproved effect past governance.

---

## 2. Architecture

```text
CodeChangeIntent
  -> Code Governance Physics
       risk, barrier, proof, approval, forbidden action
  -> Code Creative Physics
       pressure, bottleneck, indirect path, energy minimization
  -> Code Repair Physics
       entropy, drift, contradiction, instability, rollback
  -> CodeChangePhysicsPacket
       non-executing recommendation with evidence refs
  -> Existing SDLC / UAO / sandbox gates
       execute only after ordinary proof and approval pass
```

The packet sits between intent analysis and effect-bearing work. It can improve
route choice, work slicing, and proof selection. It cannot write files, mutate
Git state, send messages, deploy systems, or declare tests passed.

---

## 3. Physics Vocabulary

| Physics term | Code-change meaning | Required witness |
| --- | --- | --- |
| mass | blast radius or risk weight | affected surface list |
| gravity | danger pulling toward harm | blocked action or hazard ref |
| energy | proof and effort needed | required validator or receipt |
| barrier | forbidden movement | policy, schema, or capability gate |
| friction | approval or coordination burden | approval/refusal condition |
| pressure | accumulated tension in a module or workflow | stress signal with evidence |
| bottleneck | constrained component limiting flow | dependency or ownership trace |
| pressure valve | value-preserving safer path | draft, queue, simulation, probe, or plan |
| circuit breaker | stop condition before damage | fail-closed gate |
| resonance matching | route to best component or method family | solver/capability match evidence |
| stability basin | known-safe operating mode | Foundation Mode or sandbox boundary |
| entropy | drift, duplication, stale evidence, unclear state | repair finding |
| phase transition | authority or lifecycle state change | transition receipt |

---

## 4. Algorithm

1. Distinction: name the exact code-change boundary and affected surfaces.
2. Constraint: list barriers, proof needs, approvals, and forbidden effects.
3. Ontology: classify each physics signal as governance, creative, or repair.
4. Topology: map overloaded components, hidden coupling, and route choices.
5. Form: assign bounded pressure, risk, energy, and evidence states.
6. Organization: preserve invariants and owners.
7. Module: keep the packet advisory; do not move execution authority into it.
8. Execution: choose a non-effecting or lowest-risk path first when available.
9. Body: define halt, rollback, repair-first, or approval-queue behavior.
10. Architecture: hand off selected paths to SDLC, UAO, Solver Forge, or
    sandbox gates as appropriate.
11. Performance: prefer the smallest verified change that releases the most
    pressure.
12. Feedback: record rejected paths and why they were rejected.
13. Evolution: retain the packet as planning evidence for future routing.

---

## 5. Creative Path Rules

Creative physics is allowed to propose:

1. Draft-only workflows when live send or live write is blocked.
2. Approval queues when authority is missing but value can be staged.
3. Simulated receipts when live evidence is unavailable.
4. Sandbox probes when strict execution evidence is required.
5. Smallest-safe pull-request slices when full scope is overloaded.
6. Repair-first changes when drift or instability would corrupt the main work.
7. Solver Forge candidate comparison when multiple method families compete.

Creative physics is not allowed to:

1. Reclassify a forbidden action as safe.
2. Treat a planning packet as execution approval.
3. Hide direct effects behind "indirect path" language.
4. Skip proof because a path is useful.
5. Convert unknown hard constraints into permission.
6. Decompose Mfidel atoms or weaken substrate invariants.

---

## 6. Packet Contract

`CodeChangePhysicsPacket` is the durable witness:

```text
packet := <
  affected_surfaces,
  lanes: governance_physics | creative_physics | repair_physics,
  force_terms,
  candidate_paths,
  selected_path,
  conservation_checks,
  blocked_actions,
  evidence_refs,
  next_action
>
```

Required conservation checks:

| Check | Meaning |
| --- | --- |
| `no_unapproved_authority` | selected path does not grant execution authority |
| `smallest_safe_change` | selected path minimizes blast radius while preserving value |
| `proof_need_declared` | validators, receipts, or missing evidence are named |
| `repair_path_named` | drift or instability has a repair route |

Validation command:

```powershell
python scripts/validate_code_change_physics_packet.py
```

---

## 7. Example Application

```text
Goal force:
  user needs outgoing communication value

Governance barrier:
  live send is blocked without approval and live connector evidence

Creative path:
  draft message -> approval queue -> send receipt schema -> live probe later

Repair path:
  if connector evidence is stale, refresh read-only probe before any send path

Selected path:
  draft-only plus approval queue, because it gives value now without live effect
```

The selected path is useful because it reduces system pressure without
pretending the barrier disappeared.

---

## 8. Halt Conditions

Halt the packet if:

1. Any lane is missing.
2. A selected path requires a live effect while the packet claims validation.
3. A selected path lacks required evidence refs.
4. A direct forbidden path is chosen over a lower-risk available path.
5. A repair finding has no repair action.
6. A hard unknown is degraded into permission.

---

## 9. Status

STATUS:
  Completeness: 100%
  Invariants verified: three-lane physics split, advisory-only execution boundary, creative path no-bypass rule, repair path witness, schema-backed packet
  Open issues: none
  Next action: validate new or changed packets with `python scripts/validate_code_change_physics_packet.py`
