# Mullu Platform MCOI Runtime -- Known Limitations v0.1.0

**Version:** 0.1.0 (internal alpha)
**Date:** 2026-03-19

This document lists known limitations, incomplete features, and areas where the
runtime does not yet behave as intended by the architecture specification.

## Serialization

- **Nested deserialization:** Improved from earlier iterations, but the registry
  backend still uses dynamic `make_dataclass` for opaque restoration of persisted
  objects. Round-trip fidelity is tested but edge cases with deeply nested custom
  types may surface.

## Integration Adapters

- **HTTP connector:** Uses `urllib` (standard library). No per-read timeout
  enforcement on slow responses -- a server that sends headers promptly but trickles
  body bytes can hold a connection open past the intended timeout.
- **No real SMTP testing in CI:** SMTP connector logic is unit-tested with mocks.
  Sending actual email requires a live SMTP server, which is not part of the CI
  environment.
- **No real HTTP integration testing in CI:** HTTP connector is tested against
  synthetic responses. No live endpoint tests run in CI.
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

- **Working and episodic memory are in-memory only.** Promotion to procedural memory
  is implemented, but working/episodic tiers are not persistence-backed. Restarting
  the runtime loses working and episodic memory contents.

## Policy

- **Policy packs are declarative only.** Packs can be listed and loaded, but the
  policy engine does not yet consume pack rules during evaluation. Policy decisions
  currently come from the core policy engine's built-in logic, not from pack
  declarations.

## Replay

- **Verdict reports show first failing class only.** When a replay produces multiple
  field mismatches across different contract classes, the verdict report surfaces the
  first failing class. Subsequent mismatches are still detected internally but are
  not included in the operator-facing verdict summary.

## Not Yet Implemented

The following features are described in architecture documents but have no runtime
implementation in this release:

- **Autonomous background scheduling daemon:** Temporal plane defines task and
  deadline contracts, but no background process monitors or fires scheduled tasks.
- **Multi-agent live runtime:** Coordination plane defines delegation and handoff
  contracts, but no multi-process or networked agent execution exists.
- **Web UI:** All operator interaction is through the CLI and console renderer.
  No browser-based dashboard or monitoring interface.
