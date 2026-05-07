# Mullu Platform MCOI Runtime -- Release Notes v0.1.0

**Version:** 0.4.3 (v3.13.3)
**Date:** 2026-05-06
**Status:** Internal use only. Not for external distribution.

## Summary

First internal alpha of the Mullu Platform MCOI Runtime. This release provides a
governed execution runtime for agentic operations with policy control, verification
closure, persistence, replay, procedural memory, and a multi-plane capability
architecture.

## What's Included

### Runtime Core
- **Policy engine:** gate all execution through policy approval; deny/escalate block dispatch
- **Verification closure:** every action requires verification before completion
- **Dispatcher:** route execution to registered executor adapters
- **Replay engine:** deterministic replay of persisted execution traces
- **Procedural memory:** working/episodic/procedural tiers with promotion between tiers
- **Structured error taxonomy:** 11 error families with recoverability classification

### Capability Planes
- Communication plane (message routing, delivery tracking)
- External integration plane (HTTP connector, SMTP connector, provider registry)
- Model orchestration plane (model invocation, response handling)
- Temporal plane (scheduling, deadlines, state transitions)
- Coordination plane (delegation, handoff, conflict detection, merge decisions)
- World-state plane (entity tracking, contradiction detection, state hashing)
- Meta-reasoning plane (capability degradation, escalation recommendations)

### Operator Tooling
- **CLI:** `mcoi run`, `mcoi status`, `mcoi profiles`, `mcoi packs`
- **Operator console:** structured run reports with view models
- **Configuration profiles:** local-dev, safe-readonly, operator-approved, sandboxed, pilot-prod
- **Policy packs:** declarative rule sets for runtime governance

### Persistence
- Trace store (JSON-backed execution trace persistence)
- Snapshot store (world-state snapshots)
- Replay store (replay record persistence)
- Registry backend (provider and capability registration)

### Platform Components
- **MAF Core:** Rust type definitions for the Mullu Agentic Framework
- **MCOI Runtime:** Python runtime implementation
- **Architecture docs:** governed platform, runtime, and pilot documentation under `docs/`
- **JSON schemas:** canonical contract schemas validated by `scripts/validate_schemas.py --strict`
- **Release gate:** deterministic summary derived by `scripts/validate_release_status.py --strict`
- **Red-team release gate:** deterministic adversarial harness validated by `scripts/run_red_team_harness.py --output .change_assurance/red_team_harness.json --min-pass-rate 1.0`

## Test Coverage

- **Python:** validated by the full `pytest -q` suite
- **Rust:** validated by `cargo test`
- **Red-team harness:** 8/8 cases passed (`pass_rate: 1.0`) across prompt injection, budget evasion, audit tampering, and policy bypass
- **Red-team witness:** `.change_assurance/red_team_harness.json`, report hash `sha256:86a63fb36fe94ff44d44a8124625367aa1ead6b99a698a4ebd1b61c6024e5710`

## Breaking Changes

N/A -- first release.

## Known Issues

See [KNOWN_LIMITATIONS_v0.1.md](KNOWN_LIMITATIONS_v0.1.md) for a complete list of
current limitations and areas not yet implemented.

## Security

See [SECURITY_MODEL_v0.1.md](SECURITY_MODEL_v0.1.md) for the current security posture
and what is not yet covered.

## Getting Started

See [OPERATOR_GUIDE_v0.1.md](OPERATOR_GUIDE_v0.1.md) for installation, CLI usage,
and configuration. See [PILOT_WORKFLOWS_v0.1.md](PILOT_WORKFLOWS_v0.1.md),
[PILOT_CHECKLIST_v0.1.md](PILOT_CHECKLIST_v0.1.md), and
[PILOT_OPERATIONS_GUIDE_v0.1.md](PILOT_OPERATIONS_GUIDE_v0.1.md) for controlled
pilot execution guidance.
