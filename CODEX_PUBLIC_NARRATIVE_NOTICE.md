# Codex Public Narrative Notice

Purpose: give future Codex runs an explicit handoff for the mission-first public narrative change.
Governance scope: README, website copy, public docs, launch copy, product identity, plain-English explanation, and Foundation Mode claim boundaries.
Dependencies: `AGENTS.md`, `docs/PUBLIC_MISSION_STATEMENT.md`, `docs/PUBLIC_LAUNCH_COPY.md`, `docs/PRODUCT_IDENTITY.md`, `docs/explain/PLAIN_ENGLISH.md`, `docs/FOUNDATION_MODE.md`.
Invariants: public narrative must explain mission before mechanics; technical proof must remain available but should not be the first thing a non-technical visitor sees; Foundation Mode claim boundaries remain binding.

## Notice To Codex

Future Codex work on public-facing Mullusi or Mullu Govern surfaces must preserve this narrative order:

```text
mission
problem
solution
trust model
market role
Foundation Mode status
proof and documentation routes
```

Do not lead public pages with schemas, runtime conformance, witness endpoints, internal substrate names, long boundary indexes, or architecture internals unless the page is explicitly for developers or auditors.

The public mission is:

```text
Mullusi exists to make powerful AI systems safe enough to trust.
Mullu Govern makes AI action governable, auditable, and accountable.
```

The plain market role is:

```text
Mullu Govern is a trust layer for AI actions.
```

## Required Behavior

When editing homepage, product, launch, README, or plain-English docs:

1. Start with mission and user meaning.
2. Explain the problem in ordinary language.
3. Explain the solution without decorative abstraction.
4. State the trust model: approval, policy, budget, evidence, receipts, audit, rollback.
5. State current Foundation Mode status before any access, launch, or production language.
6. Move deep proof, schemas, runtime witnesses, and boundary indexes below the public orientation.
7. Keep `docs/PUBLIC_MISSION_STATEMENT.md` and `docs/PUBLIC_LAUNCH_COPY.md` aligned.

## Blocked Public Claims

Do not claim:

```text
public deployment readiness
customer access readiness
paid-use readiness
production runtime health
legal clearance
complete AI safety guarantee
AGI or ASI product status
live external-effect execution
```

## Required Handoff Shape

For future public-copy changes, end the change note with:

```text
Constructive delta: what became clearer for visitors.
Fracture delta: what remains unproven or blocked.
Claim boundary: what the public copy may and may not claim.
```

## STATUS

Completeness: Codex public narrative notice created.
Invariants verified: mission-first hierarchy, Foundation Mode boundary, public claim restraint, technical proof preserved below public orientation.
Open issues: this notice should be mirrored into `AGENTS.md` if future source-control policy allows broad instruction-file edits.
Next action: future Codex runs should check this notice before changing website, README, launch, or public product copy.
