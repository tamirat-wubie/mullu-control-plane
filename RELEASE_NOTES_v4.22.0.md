# Mullu Platform v4.22.0 — CI Node.js 24 Opt-In

**Release date:** TBD
**Codename:** Forward
**Migration required:** No (CI-only)

---

## What this release is

GitHub deprecated the Node.js 20 runtime that backs `actions/checkout`,
`actions/setup-python`, `actions/cache`, and `actions/upload-artifact`
on 2025-09-19, with Node.js 24 becoming default in June 2026. Until
then, every CI run emits a deprecation warning on every job. v4.22
opts into Node.js 24 now, silencing the warnings and exercising the
new runtime ahead of the cutover.

This is a CI-only change. Zero impact on the runtime, the test suite,
or any deployment artifact.

---

## What is new in v4.22.0

### Workflow-level `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`

Five workflow files updated:
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- [`.github/workflows/deployment-witness.yml`](.github/workflows/deployment-witness.yml)
- [`.github/workflows/gateway-publication.yml`](.github/workflows/gateway-publication.yml)
- [`.github/workflows/nightly.yml`](.github/workflows/nightly.yml)
- [`.github/workflows/nightly_tamper_drill.yml`](.github/workflows/nightly_tamper_drill.yml)

Each gets a workflow-level `env:` block opting into Node.js 24:

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
```

This is the official opt-in mechanism documented in [GitHub's
deprecation notice](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/).

When Node.js 24 becomes default in June 2026, the env vars become
no-ops; we'll remove them in a follow-up. If a regression surfaces in
the meantime (some action behaves differently under Node 24), the
runner still accepts `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true` as
a temporary opt-out.

### Why workflow-level instead of job-level

The env var only matters when the runtime parses an action's
`runs.using: "node20"` field. Workflow-level `env:` cascades to every
step in every job by default — one place to maintain instead of
duplicating across each `uses:` step. No conflicting env on any
existing job.

---

## Compatibility

- **CI-only change.** Every test suite, schema check, contract guard,
  build verification, and deployment gate runs identically — just
  under Node 24 inside the JavaScript actions
- **Reverts to default in June 2026.** When Node 24 becomes default,
  the env var is a no-op and can be removed
- **Fallback documented.** `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true`
  is the documented escape hatch if a Node-24 regression surfaces

---

## Test counts

Unchanged from v4.21.0: 47,871 mcoi + 806 top-level. This release
ships no source or test changes — the workflow update is the entire
delta.

---

## Production-readiness gap status

```
✅ #3 JWKS/RSA                      — v4.19.0
✅ "in-process counters only"        — v4.20.0
✅ "no latency histograms"           — v4.21.0
✅ CI Node.js 20 deprecation        — v4.22.0
⏳ #1 Live deployment evidence       — needs real production environment
⏳ #2 Single-process state           — needs Redis + Postgres
⏳ #4 DB schema migrations           — could be done locally; bigger surface
```

---

## Honest assessment

A two-line change × five files. CI hygiene only. Mentioned as a
distinct release because the deprecation timeline matters for any
fork or downstream consumer that runs the same workflows — they need
to know when this opt-in landed and what to remove after June 2026.

**We recommend:**
- Merge whenever convenient. Zero blast radius.
- Set a reminder for June 2026 to remove the env vars (or absorb into
  a "post-Node-20-EOL cleanup" PR alongside other GitHub Actions
  updates).
