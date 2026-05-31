# MCOI Runtime

Purpose: package the governed swarm work fabric and lightweight temporal runtime for Mullusi control-plane integration.

Governance scope: this package exposes symbolic intelligence workers as bounded, lease-based runtime components. It does not grant universal authority, direct tool access, side-effect execution, or memory admission outside the governed runtime.

Dependencies: Python 3.12+, setuptools build backend, optional FastAPI gateway adapter.

Invariants:

- Every swarm worker has identity, capability scope, budget scope, and memory scope.
- Every task runs under a finite lease.
- Every inter-agent result is represented as a traceable claim or receipt.
- Side effects are represented as MIL programs and require verifier approval.
- Closure requires terminal proof.
- Package entry points do not bypass runtime validation.

Simple user surface:

```powershell
mullu start
mullu task review-docs --target docs/README.md
mullu task update-docs --target docs/README.md
mullu task notify-support
mullu check --goal "Review docs" --action view --target docs/README.md --allowed-area docs/**
mullu check --goal "Update docs" --action change --target docs/README.md --allowed-area docs/**
mullu check --goal "Notify support" --action send --target support@mullusi.com --allowed-area support@mullusi.com
```

`mullu` is the intended front door for non-technical users. It returns one of
three outcomes: `Ready`, `Needs review`, or `Blocked`. The deeper commands below
remain available for developers, operators, and audit workflows.

Simple app surface:

- `SimplePlatformRuntime` exposes the same plain outcomes in JSON envelopes.
- `create_simple_platform_fastapi_router(runtime)` mounts stable routes:
  - `GET /api/v1/simple/actions`
  - `POST /api/v1/simple/actions/check`
  - `POST /api/v1/simple/tasks/check`
- `build_operational_dashboard_state(..., simple_action_checks=...)` projects
  the same checks into `simple_action_summaries`, `simple_ready_action_refs`,
  `simple_review_action_refs`, and `simple_blocked_action_refs` for dashboard UI
  rendering without granting execution authority.

Command surface:

```powershell
mcoi-swarm --audit-store .\swarm_audit.jsonl run-invoice .\invoice_request.json
mcoi-swarm --audit-store .\swarm_audit.jsonl get-run <run_id>
mcoi-swarm --audit-store .\swarm_audit.jsonl list-runs
mcoi-notes --note-store .\.mullusi\notes capture --kind WorkingNote --scope task --summary "bounded task note" --source-ref task:local --proof-state Unknown --trust-zone workspace --expires-at 2026-05-28T00:00:00+00:00
mcoi-notes --note-store .\.mullusi\notes retrieve "bounded task"
mcoi-notes --note-store .\.mullusi\notes record-rejected-delta --summary "Rejected unsafe note promotion" --source-ref task:local --evidence-ref proof:blocked
mcoi-notes --note-store .\.mullusi\notes queue-promotion <note_id>
mcoi-notes --note-store .\.mullusi\notes promote --note-id <note_id> --receipt .\promotion_receipt.json
mcoi-notes --note-store .\.mullusi\notes expire --now 2026-05-29T00:00:00+00:00
mcoi-notes --note-store .\.mullusi\notes rebuild-index
mcoi-mvk validate intent .\examples\mvk\read_intent.json
mcoi-mvk validate action .\examples\mvk\read_action.json
mcoi-mvk gate --intent .\examples\mvk\read_intent.json --action .\examples\mvk\read_action.json
mcoi-mvk scenario run-canonical
mcoi-mvk seed module governance-adapter --target-dir .\tmp\governance-adapter
mcoi-mvk seed module mfidel-guard --domain mfidel --target-dir .\tmp\mfidel-guard
mcoi-mvk conformance run --target-dir .\tmp\governance-adapter
mcoi-mvk stdlib list --minimum-maturity governed
mcoi-mvk stdlib show std/verifiers/MfidelAtomicityVerifier
mcoi-mvk stdlib policy --module-id module-mfidel --domain mfidel
mcoi-mvk registry query --kind standard --tag primitive --minimum-maturity governed
mcoi-mvk registry query --kind module --module-dir .\tmp\governance-adapter --capability read
mcoi-mvk abi operations
mcoi-mvk abi version
mcoi-mvk abi call action.gate "{""intent"":{...},""action"":{...}}"
mcoi-mvk contract evaluate --target-dir .\tmp\governance-adapter
mcoi-mvk marketplace install --target-dir .\tmp\governance-adapter --target-instance-id instance-a --capability action.gate --scope governance-adapter/input.json
mcoi-mvk federation handshake --source "{""node_id"":""runtime-a"",""owner_id"":""owner-a""}" --target "{""node_id"":""runtime-b"",""owner_id"":""owner-b""}"
mcoi-mvk federation replay-handshake --source "{""node_id"":""runtime-a"",""owner_id"":""owner-a""}" --target "{""node_id"":""runtime-b"",""owner_id"":""owner-b""}"
mcoi-mvk federation memory-court --petition "{""petition_id"":""..."",""request_id"":""..."",""source_node_id"":""runtime-a"",""target_node_id"":""runtime-b"",""memory_scope"":""runtime-b.partner/runtime-a"",""subject_ref"":""memory:candidate"",""evidence_refs"":[""proof-memory-candidate""],""retention_class"":""candidate"",""proof_obligations"":[""boundary_witness"",""local_memory_policy_checked""]}" --policy "{...}" --witness "{...}"
mcoi-mvk federation policy-diff --source-surface "{""surface_id"":""..."",""node_id"":""runtime-a"",""supported_abi_versions"":[""0.1.0""],""sovereign_domains"":[""governance_gate""],""allowed_exchange_kinds"":[""proof_exchange""],""retained_authorities"":[""governance_gate""],""allowed_memory_scopes"":[],""allowed_retention_classes"":[],""required_proof_obligations"":[""boundary_witness""]}" --target-surface "{...}"
mcoi-mvk federation adapter-contract --diff "{""diff_id"":""..."",""source_surface_id"":""..."",""target_surface_id"":""..."",""decision"":""adapter_required"",""shared_abi_versions"":[""0.1.0""],""shared_exchange_kinds"":[""proof_exchange""],""source_only_sovereign_domains"":[],""target_only_sovereign_domains"":[""mfidel_atomicity""],""source_only_retained_authorities"":[],""target_only_retained_authorities"":[],""required_adapters"":[""target_sovereign_domain_bridge_required""],""blocked_reasons"":[],""proof_stamp_id"":""proof-...""}"
mcoi-mvk federation certify-adapter --contract "{""contract_id"":""..."",""diff_id"":""..."",""decision"":""required"",""adapter_obligations"":[...],""blocked_reasons"":[],""prohibited_transfers"":[...],""required_review_refs"":[...],""proof_stamp_id"":""proof-...""}" --test-results "{""test_results"":[{""test_ref"":""test_retained_authority_not_transferred"",""passed"":true,""evidence_refs"":[""evidence:test""],""proof_stamp_id"":""proof:test""}]}"
mcoi-mvk federation badge-check --registry "{""badges"":[{""badge_id"":""..."",""contract_id"":""..."",""certified_obligation_refs"":[],""evidence_refs"":[],""proof_stamp_id"":""proof-...""}]}" --contract-id adapter-contract-...
mcoi-mvk federation preflight --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --source-surface "{...}" --target-surface "{...}" --registry "{...}"
mcoi-mvk federation route-plan --preflight "{""preflight_id"":""..."",""decision"":""ready"",""reason"":""federation_execution_preflight_ready"",""handshake_ref"":""..."",""policy_diff_ref"":""..."",""adapter_contract_ref"":null,""badge_lookup_ref"":null,""federation_witness_ref"":""..."",""blocked_reasons"":[],""proof_stamp_id"":""proof-...""}"
mcoi-mvk federation execution-receipt --route-plan "{""route_id"":""..."",""preflight_id"":""..."",""route_kind"":""direct_execution"",""risk_class"":""low"",""execution_steps"":[""execute_federated_request"",""record_replay_event""],""required_followup_refs"":[""federation_replay_record_required""],""blocked_reasons"":[],""proof_stamp_id"":""proof-...""}" --execution-ref execution-... --replay-event-ref federation-ledger-event-...
mcoi-mvk federation audit-receipt --route-plan "{...}" --receipt "{""receipt_id"":""..."",""route_id"":""..."",""route_kind"":""direct_execution"",""outcome"":""executed"",""execution_ref"":""execution-..."",""replay_event_ref"":""federation-ledger-event-..."",""adapter_contract_ref"":null,""badge_lookup_ref"":null,""memory_court_ref"":null,""blocked_reasons"":[],""evidence_refs"":[],""proof_stamp_id"":""proof-...""}"
mcoi-mvk federation record-receipt --route-plan "{...}" --receipt "{...}"
mcoi-mvk federation verify-receipt-ledger --records "{""records"":[{""ledger_record_id"":""..."",""sequence_index"":0,""route_id"":""..."",""receipt_id"":""..."",""audit_id"":""..."",""audit_decision"":""accepted"",""receipt_outcome"":""executed"",""previous_record_hash"":""genesis"",""record_hash"":""..."",""proof_stamp_id"":""proof-...""}]}"
mcoi-mvk federation execute-plan --preflight "{...}" --execution-ref execution-... --replay-event-ref federation-ledger-event-...
mcoi-mvk federation remediation-plan --orchestration "{""orchestration_id"":""..."",""preflight_id"":""..."",""status"":""blocked"",""route_plan"":{...},""receipt"":{...},""audit"":{...},""ledger_record"":{...},""ledger_integrity"":{...},""blocked_reasons"":[""missing_replay_event_ref""],""proof_stamp_id"":""proof-...""}"
mcoi-mvk federation execute-remediation --plan "{...}" --refs "{""refs"":{""replay_event_ref"":""federation-ledger-event-...""}}"
mcoi-mvk federation retry-package --preflight "{...}" --remediation-execution "{""execution_id"":""..."",""plan_id"":""..."",""status"":""resolved"",""satisfied_action_refs"":[""...""],""unresolved_action_refs"":[],""missing_refs"":[],""supplied_refs"":{""execution_ref"":""execution-..."",""replay_event_ref"":""federation-ledger-event-...""},""retryable"":false,""proof_stamp_id"":""proof-...""}"
mcoi-mvk federation execute-retry --preflight "{...}" --retry-package "{""package_id"":""..."",""preflight_id"":""..."",""remediation_execution_id"":""..."",""status"":""ready"",""retry_refs"":{""execution_ref"":""execution-..."",""replay_event_ref"":""federation-ledger-event-...""},""missing_refs"":[],""command_ref"":""..."",""proof_stamp_id"":""proof-...""}"
mcoi-mvk federation execute-authorized-retry --preflight "{...}" --authorization-capsule "{""capsule_id"":""..."",""retry_package_id"":""..."",""retry_policy_verdict_id"":""..."",""retry_quorum_verdict_id"":""..."",""status"":""ready"",""authorized_retry_refs"":{""execution_ref"":""execution-..."",""replay_event_ref"":""federation-ledger-event-...""},""blocked_reasons"":[],""required_action_refs"":[],""proof_stamp_id"":""proof-...""}"
mcoi-mvk federation record-authorized-retry --preflight "{...}" --authorization-capsule "{...}"
mcoi-mvk federation verify-retry-authorization-ledger --records "{""records"":[]}"
mcoi-mvk federation revoke-authorization --authorization-capsule-id federation-retry-authorization-capsule-... --reason stale_quorum_witness --revoked-by runtime-steward --evidence-ref evidence:revocation
mcoi-mvk federation record-authorization-revocation --authorization-capsule-id federation-retry-authorization-capsule-... --reason stale_quorum_witness --revoked-by runtime-steward --evidence-ref evidence:revocation
mcoi-mvk federation verify-authorization-revocation-ledger --records "{""records"":[]}"
mcoi-mvk federation authorization-lifecycle-audit --authorization-capsule "{...}" --revocation-verdict "{...}" --retry-execution "{...}" --authorization-records "{""records"":[]}" --revocation-records "{""records"":[]}"
mcoi-mvk federation authorization-lifecycle-archive --lifecycle-verdict "{...}" --authorization-records "{""records"":[]}" --revocation-records "{""records"":[]}"
mcoi-mvk federation verify-authorization-lifecycle-archive --archive "{...}" --lifecycle-verdict "{...}" --authorization-records "{""records"":[]}" --revocation-records "{""records"":[]}"
mcoi-mvk federation accept-lifecycle-archive --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --archive "{...}" --verification "{...}"
mcoi-mvk federation record-lifecycle-archive-acceptance --acceptance "{...}"
mcoi-mvk federation verify-lifecycle-archive-acceptance-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-lifecycle-archive-acceptance --record "{...}" --acceptance "{...}"
mcoi-mvk federation bundle-lifecycle-archive-acceptance-replay --record "{...}" --acceptance "{...}"
mcoi-mvk federation intake-lifecycle-archive-acceptance-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-lifecycle-archive-acceptance-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-lifecycle-archive-acceptance-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-lifecycle-archive-acceptance-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-lifecycle-archive-acceptance-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation proof-recursion-guard --chain-depth 6 --max-depth 6 --latest-ref proof:third-party-intake-replay-bundle
mcoi-mvk federation proof-recursion-archive --verdict "{...}"
mcoi-mvk federation verify-proof-recursion-archive --archive "{...}" --verdict "{...}"
mcoi-mvk federation accept-proof-recursion-archive --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --archive "{...}" --verdict "{...}"
mcoi-mvk federation record-proof-recursion-archive-acceptance --acceptance "{...}"
mcoi-mvk federation verify-proof-recursion-archive-acceptance-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-archive-acceptance --record "{...}" --acceptance "{...}"
mcoi-mvk federation bundle-proof-recursion-archive-acceptance-replay --record "{...}" --acceptance "{...}"
mcoi-mvk federation intake-proof-recursion-archive-acceptance-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-archive-acceptance-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-archive-acceptance-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-archive-acceptance-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-archive-acceptance-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation proof-recursion-closure-route-manifest --components "{...}"
mcoi-mvk federation proof-recursion-closure-route-manifest-extension --base-manifest "{...}" --components "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension --extension "{...}" --base-manifest "{...}" --route-manifest-verification "{...}" --route-manifest-verification-record "{...}" --route-manifest-verification-replay-bundle "{...}" --route-manifest-verification-replay-bundle-intake "{...}" --route-manifest-verification-replay-bundle-intake-record "{...}" --route-manifest-verification-replay-bundle-intake-replay-bundle "{...}" --route-manifest-verification-replay-bundle-intake-replay-bundle-intake "{...}" --route-manifest-verification-replay-bundle-intake-replay-bundle-intake-record "{...}" --route-manifest-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification --verification "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification --record "{...}" --verification "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay --record "{...}" --verification "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest --manifest "{...}" --guard-verdict "{...}" --archive "{...}" --archive-verification "{...}" --archive-acceptance "{...}" --acceptance-record "{...}" --acceptance-replay-bundle "{...}" --bundle-intake "{...}" --bundle-intake-record "{...}" --bundle-intake-replay-bundle "{...}" --third-party-intake "{...}" --third-party-intake-record "{...}" --third-party-intake-replay-bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-verification --verification "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-verification-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-verification --record "{...}" --verification "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-verification-replay --record "{...}" --verification "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-verification-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-verification-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-verification-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation intake-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle --source "{...}" --target "{...}" --agreement "{...}" --request "{...}" --bundle "{...}"
mcoi-mvk federation record-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake --intake "{...}"
mcoi-mvk federation verify-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake-ledger --records "{""records"":[]}"
mcoi-mvk federation replay-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake --record "{...}" --intake "{...}"
mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake-replay --record "{...}" --intake "{...}"
mcoi-mvk federation check-authorization-revocation --authorization-capsule "{...}" --revocations "{""revocations"":[{""revocation_id"":""..."",""authorization_capsule_id"":""..."",""reason"":""stale_quorum_witness"",""revoked_by"":""runtime-steward"",""evidence_refs"":[""evidence:revocation""],""proof_stamp_id"":""proof-...""}]}"
mcoi-mvk federation record-retry --preflight "{...}" --retry-package "{...}"
mcoi-mvk federation retry-policy --records "{""records"":[]}" --policy "{""policy_id"":""federation-retry-policy-demo"",""max_attempts"":3,""terminal_statuses"":[""closed""],""manual_review_statuses"":[""rejected""],""proof_stamp_id"":""proof-demo""}"
mcoi-mvk federation retry-quorum --policy-verdict "{""verdict_id"":""..."",""policy_id"":""..."",""decision"":""allow_retry"",""attempt_count"":0,""latest_status"":null,""blocked_reasons"":[],""required_action_refs"":[],""proof_stamp_id"":""proof-...""}" --risk medium --witnesses "{""witnesses"":[{""witness_id"":""..."",""steward_node_id"":""steward-a"",""verdict_id"":""..."",""decision"":""allow_retry"",""risk_class"":""medium"",""evidence_refs"":[""proof-review""],""proof_stamp_id"":""proof-...""}]}"
mcoi-mvk federation retry-authorize --retry-package "{...}" --policy-verdict "{...}" --quorum-verdict "{...}"
```

Note memory service surface:

- `NoteMemoryRuntime` exposes JSON-compatible governed envelopes for capture, rejected-delta recording, retrieval, expiry, promotion queueing, MemoryAnchor promotion, event listing, and index rebuild.
- `NoteMemoryFastAPIAdapter` exposes the same handlers for host HTTP apps without making FastAPI a core dependency.
- `create_note_memory_fastapi_router(runtime)` mounts stable `/api/v1/notes` routes:
  - `POST /api/v1/notes/events`
  - `POST /api/v1/notes/rejected-deltas`
  - `POST /api/v1/notes/retrieve`
  - `POST /api/v1/notes/expire`
  - `POST /api/v1/notes/promotions`
  - `POST /api/v1/notes/anchors`
  - `POST /api/v1/notes/index/rebuild`
  - `GET /api/v1/notes/events`

Minimum viable kernel:

- `IntentFrame` captures formal user goal, scope, and success criteria.
- `ActionSentence` types verb, object, side effects, scope, proof obligations, and domain.
- `GovernanceGate` returns `allow`, `block`, or `escalate` with cause.
- `ProofStamp` and `WitnessRecord` anchor every gate result.
- `MfidelAtomicityVerifier` blocks decomposition, normalization, root extraction, and consonant/vowel splitting.
- `docs/mvk-walkthrough.md` contains the canonical command path.

Seed kit:

- `mcoi-mvk seed module <name>` creates `module.manifest.json`, `proof.config.json`, local constraints, action schema, scenarios, tests, and README.
- Generic seeds cover scoped allow, out-of-scope block, external side-effect escalation, missing proof, and undeclared side-effect block.
- Mfidel seeds add the atomicity constraint and a forbidden transformation scenario.

Conformance:

- `mcoi-mvk conformance run --target-dir <seeded-module>` verifies manifest, proof config, scenarios, and domain constraints against the MVK reference behavior.
- Conformant results emit scenario proof and witness refs.
- Non-conformant results fail closed with explicit remediation findings.

Standard library:

- `mcoi-mvk stdlib list` discovers reusable MVK primitives, gates, verifiers, scenarios, templates, and conformance profiles.
- `mcoi-mvk stdlib show <artifact_id>` returns the usage contract for a standard artifact.
- `mcoi-mvk stdlib policy --module-id <id>` returns recommended standard imports.
- Mfidel import policies include `std/verifiers/MfidelAtomicityVerifier`.

Registry mesh:

- `mcoi-mvk registry query` discovers standard artifacts, reference modules, conformance profiles, and optional seeded module manifests.
- Records carry kind, owner, maturity, scope, trust refs, proof refs, and tags.
- Invalid module manifests fail closed with governed rejection envelopes.

Runtime ABI:

- `mcoi-mvk abi operations` lists stable operation contracts.
- `mcoi-mvk abi version` returns supported operations and compatibility rules.
- `mcoi-mvk abi call <operation_id> <payload>` executes through a governed boundary and returns a boundary witness.
- Initial ABI surfaces include intent validation, action validation/gating, proof inspection, canonical scenarios, standard library discovery, and registry query.

Governance SDK:

- `GovernanceClient` wraps Runtime ABI calls with a typed Python facade.
- `IntentFrameBuilder` requires goal, scope, and success criteria.
- `ActionSentenceBuilder` requires scope and proof obligations before building.
- Mfidel helpers build grid-safe references and governed transformation actions without decomposing fidel.

Developer contract:

- `mcoi-mvk contract evaluate --target-dir <seeded-module>` derives a developer contract from seed artifacts.
- Contract verdicts decide accepted, sandbox-only, revision-required, or rejected status.
- Runtime surfaces are granted only from declared actions, proof obligations, rollback capabilities, and domain invariants.

Runtime marketplace:

- `mcoi-mvk marketplace install` evaluates installability separately from authority.
- Accepted installs produce scoped `AuthorityGrant` records.
- High-risk installs require review.
- Sandbox-only contracts cannot receive full gate authority.
- Revision-required contracts block installation.

Federated runtime:

- `mcoi-mvk federation handshake` compares genome and Runtime ABI compatibility between nodes.
- `mcoi-mvk federation request` admits only bounded evidence exchanges such as proof exchange, scenario exchange, verification request, memory petition, artifact candidate, or registry query.
- `mcoi-mvk federation replay-handshake` and `mcoi-mvk federation replay-request` record a federation ledger event and immediately replay it.
- Cross-node requests preserve retained authority for governance gates, release gates, memory admission, and Mfidel atomicity.
- Incompatible ABI surfaces and sovereign authority transfer attempts fail closed with a federation witness.
- Replay mismatches are reported as governed failures instead of being silently accepted.
- `mcoi-mvk federation memory-court` is the only path that can admit a narrowed cross-node memory petition into local retained memory.
- Memory court verdicts admit, quarantine, or reject based on local scope, evidence, retention class, proof obligations, and the narrowed federation witness.
- `mcoi-mvk federation policy-diff` compares policy surfaces before federation and returns compatible, adapter-required, or incompatible.
- Policy diffs cover ABI versions, exchange kinds, sovereign domains, retained authorities, memory scopes, retention classes, and proof obligations.
- `mcoi-mvk federation adapter-contract` converts adapter-required diffs into governed adapter obligations.
- Incompatible diffs produce rejected adapter contracts with no runnable obligations.
- Adapter obligations name allowed translations, required tests, proof obligations, and prohibited transfers.
- `mcoi-mvk federation certify-adapter` evaluates adapter contracts against required test results.
- Adapter certification emits a badge only when every required test passes; missing tests are incomplete, failed tests fail, and rejected contracts remain rejected.
- `mcoi-mvk federation badge-check` verifies adapter certification badges before federation execution.
- Badge registry lookups return active, revoked, or missing; revoked and missing badges fail closed.
- `mcoi-mvk federation preflight` combines handshake, policy diff, adapter contract, badge lookup, and request gate before execution.
- Preflight returns ready, requires-local-memory-court, or blocked.
- `mcoi-mvk federation route-plan` selects the lowest-risk route from preflight: direct execution, certified adapter execution, local memory court, or blocked.
- `mcoi-mvk federation execution-receipt` stamps the selected route with execution, replay, adapter, badge, memory court, and evidence references, or emits a blocked receipt when required proof refs are missing.
- `mcoi-mvk federation audit-receipt` independently validates a receipt against its route plan before downstream trust or storage.
- `mcoi-mvk federation record-receipt` appends an audited receipt to a hash-chained receipt ledger and verifies the ledger head.
- `mcoi-mvk federation verify-receipt-ledger` rehydrates persisted ledger records and verifies sequence, previous-hash, and record-hash integrity.
- `mcoi-mvk federation execute-plan` runs route selection, receipt emission, audit, ledger append, and ledger verification as one governed closure pipeline.
- `mcoi-mvk federation remediation-plan` converts blocked or rejected orchestration reports into deterministic next actions with owners, required refs, retryability, and proof obligations.
- `mcoi-mvk federation execute-remediation` verifies supplied refs against a remediation plan and resolves only retryable actions; manual-review actions remain bounded.
- `mcoi-mvk federation retry-package` validates remediation execution against the original route obligations and emits a ready or blocked retry package.
- `mcoi-mvk federation execute-retry` consumes a ready retry package, reruns orchestration with packaged refs, and emits the retry closure report.
- `mcoi-mvk federation execute-authorized-retry` consumes a ready retry authorization capsule and executes only capsule-authorized refs.
- `mcoi-mvk federation record-authorized-retry` appends authorized retry executions to a hash-chained authorization ledger.
- `mcoi-mvk federation verify-retry-authorization-ledger` verifies persisted authorization ledger continuity.
- `mcoi-mvk federation revoke-authorization` creates proof-bearing revocation witnesses for previously issued retry capsules.
- `mcoi-mvk federation record-authorization-revocation` appends retry authorization revocations to a hash-chained revocation ledger.
- `mcoi-mvk federation verify-authorization-revocation-ledger` verifies persisted revocation ledger continuity.
- `mcoi-mvk federation authorization-lifecycle-audit` reconciles capsule, revocation verdict, retry execution, authorization ledger, and revocation ledger into one lifecycle verdict.
- `mcoi-mvk federation authorization-lifecycle-archive` emits a compact proof bundle for cross-node lifecycle verification.
- `mcoi-mvk federation verify-authorization-lifecycle-archive` verifies that archive against lifecycle and ledger snapshots.
- `mcoi-mvk federation accept-lifecycle-archive` admits verified lifecycle archives across federation boundaries under an explicit agreement and request.
- `mcoi-mvk federation record-lifecycle-archive-acceptance` appends cross-node lifecycle archive admissions to a hash-chained acceptance ledger.
- `mcoi-mvk federation verify-lifecycle-archive-acceptance-ledger` verifies persisted acceptance ledger continuity.
- `mcoi-mvk federation replay-lifecycle-archive-acceptance` verifies one acceptance ledger record against its source acceptance verdict.
- `mcoi-mvk federation bundle-lifecycle-archive-acceptance-replay` packages a matched acceptance replay into a portable cross-node witness.
- `mcoi-mvk federation intake-lifecycle-archive-acceptance-replay-bundle` admits portable replay bundles only when federation boundary and proof refs align.
- `mcoi-mvk federation record-lifecycle-archive-acceptance-replay-bundle-intake` appends remote bundle intake verdicts to a hash-chained local intake ledger.
- `mcoi-mvk federation verify-lifecycle-archive-acceptance-replay-bundle-intake-ledger` verifies persisted remote bundle intake ledger continuity.
- `mcoi-mvk federation replay-lifecycle-archive-acceptance-replay-bundle-intake` verifies one intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-lifecycle-archive-acceptance-replay-bundle-intake-replay` packages a matched intake replay into a portable cross-node witness.
- `mcoi-mvk federation intake-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle` admits portable intake replay bundles only when third-party boundary and proof refs align.
- `mcoi-mvk federation record-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake` appends third-party intake replay bundle verdicts to a hash-chained local ledger.
- `mcoi-mvk federation verify-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted third-party intake replay bundle ledger continuity.
- `mcoi-mvk federation replay-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake` verifies one third-party intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-lifecycle-archive-acceptance-replay-bundle-intake-replay-bundle-intake-replay` packages a matched third-party intake replay into a portable cross-node witness.
- `mcoi-mvk federation proof-recursion-guard` halts recursive federation proof expansion once a governed depth bound is reached.
- `mcoi-mvk federation proof-recursion-archive` turns a halted recursion guard verdict into a compact terminal archive.
- `mcoi-mvk federation verify-proof-recursion-archive` verifies a recursion closure archive against its source guard verdict.
- `mcoi-mvk federation accept-proof-recursion-archive` admits a verified recursion closure archive at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-archive-acceptance` appends recursion archive acceptance verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-archive-acceptance-ledger` verifies persisted recursion archive acceptance ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-archive-acceptance` verifies one recursion archive acceptance ledger record against its source acceptance verdict.
- `mcoi-mvk federation bundle-proof-recursion-archive-acceptance-replay` packages a matched recursion archive acceptance replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-archive-acceptance-replay-bundle` admits portable recursion archive acceptance replay bundles at a remote boundary.
- `mcoi-mvk federation record-proof-recursion-archive-acceptance-replay-bundle-intake` appends recursion archive replay bundle intake verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-archive-acceptance-replay-bundle-intake-ledger` verifies persisted recursion archive replay bundle intake ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-archive-acceptance-replay-bundle-intake` verifies one recursion archive replay bundle intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-archive-acceptance-replay-bundle-intake-replay` packages a matched recursion archive replay bundle intake replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle` admits portable recursion archive intake replay bundles at a third-party boundary.
- `mcoi-mvk federation record-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake` appends third-party recursion archive intake replay bundle verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted third-party recursion archive intake ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake` verifies one third-party recursion archive intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-archive-acceptance-replay-bundle-intake-replay-bundle-intake-replay` packages a matched third-party recursion archive intake replay into a portable cross-node witness.
- `mcoi-mvk federation proof-recursion-closure-route-manifest` builds a terminal manifest for the full multi-hop recursion archive route.
- `mcoi-mvk federation proof-recursion-closure-route-manifest-extension` extends the terminal route manifest across the route verification replay federation chain.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension` verifies the terminal route manifest extension against concrete route verification replay, intake, ledger, and second-hop bundle artifacts.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification` appends route manifest extension verification results to a hash-chained audit ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-ledger` verifies persisted route manifest extension verification ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification` verifies one route manifest extension verification ledger record against its source verification report.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay` packages a matched route manifest extension verification replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle` admits portable route manifest extension verification replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake` appends route manifest extension verification replay bundle intake verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-ledger` verifies persisted route manifest extension verification replay bundle intake ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake` verifies one route manifest extension verification replay bundle intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay` packages a matched route manifest extension verification replay bundle intake replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle` admits portable route manifest extension verification replay bundle intake replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake` appends second-hop route manifest extension verification replay bundle intake verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted second-hop route manifest extension verification intake ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake` verifies one second-hop route manifest extension verification intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay` packages a matched second-hop route manifest extension verification intake replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle` admits portable second-hop route manifest extension verification intake replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` appends second-hop route manifest extension verification intake replay bundle verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted second-hop route manifest extension verification intake replay bundle ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` verifies one second-hop route manifest extension verification intake replay bundle ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay` packages a matched second-hop route manifest extension verification intake replay bundle replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle` admits portable second-hop route manifest extension verification intake replay bundle replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` appends second-hop route manifest extension verification intake replay bundle replay bundle verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted second-hop route manifest extension verification intake replay bundle replay bundle ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` verifies one second-hop route manifest extension verification intake replay bundle replay bundle ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay` packages a matched second-hop route manifest extension verification intake replay bundle replay bundle replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle` admits portable second-hop route manifest extension verification intake replay bundle replay bundle replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` appends second-hop route manifest extension verification intake replay bundle replay bundle replay bundle verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted second-hop route manifest extension verification intake replay bundle replay bundle replay bundle ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` verifies one second-hop route manifest extension verification intake replay bundle replay bundle replay bundle ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay` packages a matched second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle` admits portable second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` appends second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundle verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundle ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` verifies one second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundle ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay` packages a matched second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundle replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle` admits portable second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundle replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` appends second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundle replay bundle verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted second-hop route manifest extension verification intake replay bundle replay bundle replay bundle replay bundle replay bundle ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` verifies one latest second-hop route manifest extension verification intake replay bundle ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay` packages a matched latest second-hop route manifest extension verification intake replay bundle replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle` admits portable latest second-hop route manifest extension verification intake replay bundle replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` appends latest second-hop route manifest extension verification intake replay bundle replay bundle verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted latest second-hop route manifest extension verification intake replay bundle replay bundle ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake` verifies one latest second-hop route manifest extension verification intake replay bundle replay bundle ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-extension-verification-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay-bundle-intake-replay` packages a matched latest second-hop route manifest extension verification intake replay bundle replay bundle replay into a portable cross-node witness.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest` verifies the terminal route manifest against concrete archive, acceptance, intake, replay, and third-party bundle artifacts.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-verification` appends route manifest verification results to a hash-chained audit ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-verification-ledger` verifies persisted route manifest verification ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-verification` verifies one route manifest verification ledger record against its source verification report.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-verification-replay` packages a matched route manifest verification replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-verification-replay-bundle` admits portable route manifest verification replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-verification-replay-bundle-intake` appends route manifest verification replay bundle intake verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-ledger` verifies persisted route manifest verification replay bundle intake ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-verification-replay-bundle-intake` verifies one route manifest verification replay bundle intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay` packages a matched route manifest verification replay bundle intake replay into a portable cross-node witness.
- `mcoi-mvk federation intake-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle` admits portable route manifest verification replay bundle intake replay bundles at a remote federation boundary.
- `mcoi-mvk federation record-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake` appends second-hop route manifest verification replay bundle intake verdicts to a hash-chained ledger.
- `mcoi-mvk federation verify-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake-ledger` verifies persisted second-hop route manifest verification intake ledger continuity.
- `mcoi-mvk federation replay-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake` verifies one second-hop route manifest verification intake ledger record against its source intake verdict.
- `mcoi-mvk federation bundle-proof-recursion-closure-route-manifest-verification-replay-bundle-intake-replay-bundle-intake-replay` packages a matched second-hop route manifest verification intake replay into a portable cross-node witness.
- `mcoi-mvk federation check-authorization-revocation` blocks revoked capsules before authorized retry execution.
- `mcoi-mvk federation record-retry` appends retry attempts to a hash-chained retry history and verifies attempt continuity.
- `mcoi-mvk federation retry-policy` enforces retry history integrity, terminal statuses, manual-review statuses, and maximum attempt limits before another retry can proceed.
- `mcoi-mvk federation retry-quorum` requires unique steward witnesses against the exact retry-policy verdict, with risk-based thresholds before continuation.
- `mcoi-mvk federation retry-authorize` fuses the retry package, retry-policy verdict, and retry-quorum verdict into one portable execution permit.

Verification:

```powershell
$env:PYTHONPATH='.;mcoi'
pytest mcoi\tests -q
python .\scripts\validate_governed_swarm.py
```
