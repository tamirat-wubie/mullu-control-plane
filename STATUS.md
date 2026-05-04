<!--
Purpose: Public repository status witness for GitHub-visible state.
Governance scope: Branch, release, CI, and change-assurance reflection.
Dependencies: README.md, RELEASE_CHECKLIST_v0.1.md, .github/workflows/ci.yml,
  scripts/validate_release_status.py, scripts/validate_protocol_manifest.py.
Invariants: Claims are bounded to named witnesses; gaps are explicit; status
  updates are validated by the release-status gate.
-->

# Repository Status Witness

**Last audited:** 2026-05-01
**Repository:** `tamirat-wubie/mullu-control-plane`
**Default branch:** `main`
**Audited runtime baseline:** `2fdcd37046e0be096ac4c52c357257e4f65c0c0a`
**Audited runtime baseline subject:** `fix(persistence): witness governance store close failures (#305)`
**Status witness publication head:** `1cb9e159a3c1fe0d11d99ef2ba8f19dc5584e30e`
**Status witness publication subject:** `Refresh deployment runtime input witness (#466)`

## Reflection Summary

| Surface | Witness | Status |
|---|---|---|
| Branch witness | GitHub `main` contains this status witness; the audited runtime baseline is named separately from the mutable status-witness commit | Reflected |
| Release witness | GitHub latest release points to `v3.13.0`; release docs declare `0.4.0 (v3.13.0)` | Reflected |
| CI witness | `.github/workflows/ci.yml` contains Python, Rust, schema, protocol-manifest, artifact, release-status, and change-assurance gates | Reflected |
| Governance witness | `scripts/validate_release_status.py --strict` validates release documents, schemas, protocol manifest, artifacts, CI literals, source hygiene, and metadata alignment | Reflected |
| Protocol witness | `docs/52_mullu_governance_protocol.md` and `scripts/validate_protocol_manifest.py` bind the open schema surface, closed runtime boundary, and 32-schema public contract index | Reflected |
| Gateway closure witness | CI runs `python -m pytest tests/test_gateway -q` and `python scripts/validate_gateway_deployment_env.py --strict` | Reflected |
| Deployment runtime input witness | `DEPLOYMENT_STATUS.md` records witness/conformance secret-name presence, absent deployment target variables, and absent `deployment-witness.yml` workflow runs | Reflected |
| General-agent promotion handoff witness | `docs/59_general_agent_promotion_handoff_packet.md`, `examples/general_agent_promotion_handoff_packet.json`, `examples/general_agent_promotion_environment_bindings.json`, `scripts/validate_general_agent_promotion_handoff_packet.py`, `scripts/validate_general_agent_promotion_operator_checklist.py`, `scripts/validate_general_agent_promotion_environment_bindings.py`, `scripts/emit_general_agent_promotion_environment_binding_receipt.py`, `scripts/validate_general_agent_promotion_environment_binding_receipt.py`, `.change_assurance/general_agent_promotion_environment_binding_receipt.json`, and `scripts/preflight_general_agent_promotion_handoff.py` bind the operator checklist, closure plans, validation reports, environment binding preflight, and terminal proof command | Reflected |
| Governed runtime promotion witness | `scripts/validate_governed_runtime_promotion.py` provides a domain-neutral terminal validation command over the existing governed promotion readiness contract | Reflected |
| Operational witness | Runtime deployment, live health, and production readiness are not exposed on the repository landing page | Not reflected |

## Required Public Anchors

The GitHub page is sufficient only when these anchors are present and current:

1. README links to this status witness.
2. `GITHUB_SURFACE.md` mirrors GitHub metadata expectations.
3. `DEPLOYMENT_STATUS.md` names deployment-health evidence state.
4. `docs/52_mullu_governance_protocol.md` names the public protocol contract boundary.
5. CI keeps `python scripts/validate_protocol_manifest.py`.
6. CI keeps `python scripts/validate_public_repository_surface.py`.
7. CI keeps `python scripts/validate_release_status.py --strict`.
8. CI keeps `python scripts/certify_change.py --base HEAD^ --head HEAD --strict --approval-id ci-governance --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md`.
9. CI keeps `python scripts/validate_gateway_deployment_env.py --strict`.
10. Deployment runbooks keep `python scripts/gateway_runtime_smoke.py`.
11. Release metadata in `RELEASE_NOTES_v0.1.md`, `KNOWN_LIMITATIONS_v0.1.md`, and `SECURITY_MODEL_v0.1.md` remains aligned.
12. General-agent promotion handoff remains anchored by `docs/59_general_agent_promotion_handoff_packet.md` and `examples/general_agent_promotion_handoff_packet.json`.
13. Known reflection gaps are named instead of implied.

## Known Reflection Gaps

| Gap | Cause | Required closure |
|---|---|---|
| Deployment status not published | `DEPLOYMENT_STATUS.md` declares no public production endpoint evidence yet; repository variables `MULLU_GATEWAY_URL` and `MULLU_EXPECTED_RUNTIME_ENV` are not set | Set deployment target variables, publish `/health`, `/gateway/witness`, and `/runtime/conformance`, then collect a signed `deployment_claim: published` witness |
| Test-count claim not machine-derived | README states test volume as a human-maintained claim | **Closed (2026-04-28)** - `scripts/generate_test_inventory.py` writes a machine-derived count to `.change_assurance/test_inventory.json`; `python scripts/generate_test_inventory.py --check` fails CI on drift; `mcoi/tests/test_inventory_freshness.py` (10 tests) guards the artifact's shape and self-consistency. Release notes and README should cite the artifact rather than embed numeric literals. |
| GitHub metadata external to git | GitHub description/topics live outside repository commits | Validate metadata with `scripts/validate_public_repository_surface.py` |

## Proof Chain

| Check | Command |
|---|---|
| Branch freshness | `git status --short --branch` |
| Remote head | `git ls-remote origin refs/heads/main` |
| Public repository surface | `python scripts/validate_public_repository_surface.py` |
| Protocol manifest | `python scripts/validate_protocol_manifest.py` |
| Release status | `python scripts/validate_release_status.py --strict` |
| Test inventory freshness | `python scripts/generate_test_inventory.py --check` |
| Gateway deployment validation | `python scripts/validate_gateway_deployment_env.py --strict` |
| Gateway runtime smoke probe | `python scripts/gateway_runtime_smoke.py` |
| General-agent promotion operator checklist | `python scripts/validate_general_agent_promotion_operator_checklist.py --checklist examples/general_agent_promotion_operator_checklist.json --json` |
| General-agent promotion environment bindings | `python scripts/validate_general_agent_promotion_environment_bindings.py --contract examples/general_agent_promotion_environment_bindings.json --json` |
| General-agent promotion environment binding receipt | `python scripts/emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance/general_agent_promotion_environment_binding_receipt.json --json` |
| General-agent promotion environment binding receipt validation | `python scripts/validate_general_agent_promotion_environment_binding_receipt.py --receipt .change_assurance/general_agent_promotion_environment_binding_receipt.json --require-ready --json` |
| Browser sandbox evidence production | `python scripts/produce_browser_sandbox_evidence.py --output "$MULLU_BROWSER_SANDBOX_EVIDENCE" --strict` |
| Sandbox execution receipt validation | `python scripts/validate_sandbox_execution_receipt.py --receipt "$MULLU_BROWSER_SANDBOX_EVIDENCE" --capability-prefix browser. --require-no-workspace-changes --json` |
| Browser sandbox evidence validation | `python scripts/validate_browser_sandbox_evidence.py --evidence "$MULLU_BROWSER_SANDBOX_EVIDENCE" --json` |
| General-agent promotion handoff preflight | `python scripts/preflight_general_agent_promotion_handoff.py --output .change_assurance/general_agent_promotion_handoff_preflight.json --strict --json` |
| General-agent promotion handoff preflight validation | `python scripts/validate_general_agent_promotion_handoff_preflight.py --report .change_assurance/general_agent_promotion_handoff_preflight.json --require-ready --json` |
| Governed runtime promotion validation | `python scripts/validate_governed_runtime_promotion.py --strict` |
| Change assurance | `python scripts/certify_change.py --base HEAD^ --head HEAD --strict --approval-id ci-governance --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md` |

