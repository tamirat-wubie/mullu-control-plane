# Mullu Platform MCOI Runtime -- Known Limitations v0.2.0

**Version:** 0.4.3 (v3.13.3)
**Date:** 2026-05-06

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
- **Governed capability fabric is present, but live production evidence remains
  the promotion boundary:** Browser, document, voice, email/calendar, connector,
  sandboxed computer, operator capability UI, multi-agent delegation, and
  deployment-witness publication entries are now represented as governed
  capability families. Production claims still require live receipts,
  dependency probes, signed worker responses, and deployment witness evidence.
- **Browser adapter not production-closed:** A restricted Playwright adapter
  exists, but browser runtime dependencies, browser binaries, sandboxed worker
  packaging, and live evidence are not yet published.
- **Document parser adapter evidence closed for parser-first scope:** Optional
  PDF/Office parser implementations, dependency probes, and live parser receipt
  evidence are represented through the adapter evidence collector. External
  document send, sign, and submit effects remain approval-gated and require
  separate effect receipts before any production claim.
- **Voice adapter not production-closed:** An OpenAI-compatible voice adapter
  exists, but provider credentials, live STT/TTS checks, and deployment evidence
  are not yet published.
- **Email/calendar adapter not production-closed:** A signed email/calendar worker
  contract and bounded Gmail, Google Calendar, and Microsoft Graph HTTP adapter
  exist for draft/send/read/schedule policy enforcement, but provider credentials,
  live read-only connector receipts, and deployment receipts are not yet
  published.

## Provider Identity

- Aggregate provider counts appear in operator reports.
- Per-run route tracking is present (the report shows which executor route was used).
- Per-plane `provider_id` attribution is implemented for runtime run reports through
  a provider attribution ledger. Records bind request/execution identity, provider
  class, provider id, attribution source, evidence id, and timestamp.
- Current attribution distinguishes healthy-plane resolution from routing or execution
  receipts. Communication and integration effect-result adapters now promote
  receipt-level provider ids into execution-receipt attribution metadata.

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
- **Specialist delegation is bounded, not a networked runtime.** The gateway now
  supports controlled specialist-worker delegation with role allowlists,
  capability checks, budget ceilings, timeouts, leases, and receipts. This is not
  a distributed multi-process agent runtime; external agents still require the
  agent adapter protocol or a separate worker deployment.

## Authority And Obligations

- Gateway authority includes ownership, approval-chain, obligation, escalation,
  ownership read-model, and policy read-model surfaces.
- External directory sync is specified in `docs/54_authority_directory_sync.md`
  and implemented for SCIM export, LDAP export, SAML group export, GitHub Teams,
  Google Workspace groups, and static workspace group sources through normalized
  batch adapters and sync receipt tooling. Remaining production work is
  credentialed scheduling/webhook ingestion and organization-management UI.

## Replay

- **Verdict reports show first failing class only.** When a replay produces multiple
  field mismatches across different contract classes, the verdict report surfaces the
  first failing class. Subsequent mismatches are still detected internally but are
  not included in the operator-facing verdict summary.

## Not Yet Implemented

The following features are described in architecture documents but have no runtime
implementation in this release:

- **Networked multi-agent runtime:** Coordination plane defines delegation and
  handoff contracts, and the gateway has bounded specialist leases, but no
  multi-process or networked agent execution fabric exists. External agents can
  connect via the agent adapter protocol.
- **Full operator web UI:** Operator console provides structured JSON dashboard
  views and a minimal browser-based capability read model. Full approval queues,
  audit/proof exploration, organization management, and credentialed directory
  scheduling UI are not yet implemented.
- **RBAC / human governance:** API key auth with scopes, JWT auth, per-session
  RBAC checks, gateway authority resolution, and authority-obligation read
  models exist. Full organization-management UI and credentialed directory
  scheduling UI are not yet implemented.
