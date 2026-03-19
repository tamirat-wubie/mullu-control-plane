# Skill System

Scope: MCOI Runtime and future verticals. The skill system composes governed capabilities into reusable, verifiable, promotable automation units.

## 1. Purpose

A skill wraps one or more governed actions into a named, typed, constrained automation unit that can be:
- selected based on context, confidence, and policy
- executed under the same governance as individual actions
- verified end-to-end
- persisted and replayed
- promoted into procedural memory (runbooks)

## 2. Skill Classes

### Primitive skill
Wraps a single governed action (one execution step).

### Composite skill
Composes multiple primitive or composite skills with explicit step ordering and data flow.

### Learned skill
Promoted from a verified runbook. Carries full provenance chain.

## 3. Owned Artifacts

- `SkillDescriptor` — identity, classification, preconditions, postconditions, effect/trust/determinism class
- `SkillStep` — one unit of work within a skill, with typed inputs/outputs and dependencies
- `SkillPrecondition` — typed condition that MUST hold before execution may begin
- `SkillPostcondition` — typed condition that MUST hold after execution for the skill to be considered successful
- `SkillOutcome` — terminal result of skill execution including step outcomes and verification
- `SkillExecutionRecord` — full trace of a skill run including all step records
- `SkillSelectionDecision` — why this skill was chosen over alternatives

## 4. Skill Lifecycle

States:
- `candidate` — registered but not yet proven
- `provisional` — executed at least once with success
- `verified` — executed AND verification-closed successfully
- `trusted` — verified AND promoted through runbook admission
- `deprecated` — superseded or no longer recommended
- `blocked` — failed safety/policy gate; MUST NOT be selected

Transitions:
- `candidate -> provisional` — requires one successful execution
- `provisional -> verified` — requires explicit verification closure with pass
- `verified -> trusted` — requires runbook admission through `RunbookLibrary`
- `any -> deprecated` — explicit operator/policy decision
- `any -> blocked` — policy violation or safety gate failure

## 5. Skill Descriptor Fields

Every skill MUST carry:
- `skill_id` — unique stable identifier
- `name` — human-readable name
- `skill_class` — primitive | composite | learned
- `effect_class` — internal_pure | external_read | external_write | human_mediated | privileged
- `determinism_class` — deterministic | input_bounded | recorded_nondeterministic
- `trust_class` — trusted_internal | bounded_external | untrusted_external
- `verification_strength` — none | weak | moderate | strong | mandatory
- `preconditions` — typed conditions checked before execution
- `postconditions` — typed conditions checked after execution
- `steps` — ordered step descriptors (composite skills only)
- `provider_requirements` — which provider classes are needed

## 6. Preconditions and Postconditions

Preconditions:
- Evaluated BEFORE skill execution begins
- Failure prevents execution (fail closed)
- Types: `state_check`, `capability_available`, `provider_healthy`, `policy_allows`

Postconditions:
- Evaluated AFTER skill execution completes
- Failure means the skill outcome is `not_satisfied` even if execution technically succeeded
- Types: `state_changed`, `file_exists`, `process_state`, `verification_passed`

## 7. Relationship to Existing Planes

### Governance
- Skills MUST pass policy gate before execution
- Skill selection MUST respect policy constraints

### Execution
- Skill steps dispatch through the existing execution plane
- No skill may bypass the policy -> execution -> verification path

### Verification
- Every skill execution MUST produce a verification closure
- Composite skills require per-step AND aggregate verification

### Memory / Runbooks
- Verified skill runs are candidates for runbook admission
- Learned skills are promoted runbooks with skill metadata

### Providers
- Skills declare provider requirements
- Skill selection considers provider health and scope

### World State
- Preconditions may reference world-state entities
- Postconditions may check world-state changes

### Meta-Reasoning
- Skill confidence is updated from execution outcomes
- Degraded skills are deprioritized in selection

## 8. Skill Selection Rules

When multiple skills can satisfy a goal:
1. Filter by precondition satisfaction
2. Filter by policy allowance
3. Filter by provider availability
4. Rank by lifecycle state (trusted > verified > provisional > candidate)
5. Rank by confidence score (from meta-reasoning)
6. Rank by effect class (prefer least-privileged)
7. Select deterministically (stable sort by skill_id on ties)

## 9. Failure Modes

- `precondition_not_met` — skill cannot start
- `policy_denied` — governance blocks execution
- `provider_unavailable` — required provider not healthy
- `step_failed` — one step in a composite skill failed
- `postcondition_not_satisfied` — execution completed but outcome invalid
- `verification_failed` — verification closure did not pass
- `timeout` — skill exceeded time boundary

## 10. Prohibitions

- MUST NOT execute without policy approval
- MUST NOT skip verification closure
- MUST NOT fabricate postcondition satisfaction
- MUST NOT promote unverified skills to trusted
- MUST NOT select blocked skills under any circumstances
- MUST NOT compose skills that create circular step dependencies
