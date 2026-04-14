# Mullu Platform MCOI Runtime -- Known Limitations v0.2.0

**Version:** 0.4.0 (v3.13.0)
**Date:** 2026-03-30

This document lists known limitations, incomplete features, and areas where the
runtime does not yet behave as intended by the architecture specification.

## Resolved in v3.9.x

- ~~**HTTP connector read timeout (urllib):**~~ Read timeout enforcement added (v3.9.1).
  Slow trickle responses are now terminated by `read_timeout_seconds` deadline.
- ~~**No HTTP integration testing:**~~ 29 live-path integration tests added (v3.9.0).
- ~~**server.py god object:**~~ Split into 6 router modules (v3.9.0).
- ~~**CORS wildcard default:**~~ Locked to localhost in dev, explicit origins required
  in production (v3.9.0).
- ~~**Memory DB in compose:**~~ Default changed to PostgreSQL (v3.9.0).

## Serialization

- **Nested deserialization:** Improved from earlier iterations, but the registry
  backend still uses dynamic `make_dataclass` for opaque restoration of persisted
  objects. Round-trip fidelity is tested but edge cases with deeply nested custom
  types may surface.

## Integration Adapters

- **No real SMTP testing in CI:** SMTP connector logic is unit-tested with mocks.
  Sending actual email requires a live SMTP server (e.g. containerized MailHog),
  which is not part of the CI environment.
- **No browser adapter:** No Selenium, Playwright, or CDP integration.
- **No document adapter:** No PDF, Office, or structured-document manipulation.
- **No voice adapter:** No speech-to-text or text-to-speech integration.

## Provider Identity

- Aggregate provider counts appear in operator reports.
- Per-run route tracking is present (the report shows which executor route was used).
- Per-plane `provider_id` attribution is not yet implemented -- you can see how many
  providers are registered and which are unhealthy, but individual plane operations
  do not tag which provider serviced them.

## Memory

- **Working and episodic memory persistence is explicit and opt-in.** The runtime
  now supports deterministic local save/load for working and episodic tiers, but it
  does not auto-save or auto-restore them. A caller must wire a memory store and
  request restore explicitly at bootstrap time.

## Coordination

- **Coordination state persistence is explicit and opt-in.** The runtime supports
  deterministic checkpoint/restore for coordination state (delegations, handoffs,
  merges, conflicts), but it does not auto-save or auto-restore. A caller must
  configure a coordination store and request checkpoint/restore explicitly. Restore
  is governed: expired leases are rejected, policy pack drift triggers review, and
  retry counts are tracked to prevent zombie workflows.

## Replay

- **Verdict reports show first failing class only.** When a replay produces multiple
  field mismatches across different contract classes, the verdict report surfaces the
  first failing class. Subsequent mismatches are still detected internally but are
  not included in the operator-facing verdict summary.

## Not Yet Implemented

The following features are described in architecture documents but have no runtime
implementation in this release:

- **Multi-agent live runtime:** Coordination plane defines delegation and handoff
  contracts, but no multi-process or networked agent execution exists. External
  agents can connect via the agent adapter protocol.
- **Web UI:** Operator console provides structured JSON dashboard views (home,
  runs, audit, checkpoints, providers, scheduler) but no browser-based frontend.
- **RBAC / human governance:** API key auth with scopes, JWT auth, and
  per-session RBAC checks exist. Team ownership, approval chains, and
  escalation rights are not yet implemented.
