# Schema Compatibility Policy

These schemas define the canonical shared JSON interchange surface for Mullu Platform.
The public Mullu Governance Protocol manifest lives at
`schemas/mullu_governance_protocol.manifest.json` and declares which schema
files are open wire contracts. Runtime modules under `mcoi/`, `gateway/`, and
`scripts/` remain reference implementation surfaces, not protocol contracts.

## Compatibility Rules

1. Root objects are strict. Unknown top-level fields are rejected unless they are carried inside `metadata` or `extensions`.
2. `metadata` and `extensions` are the only forward-compatible escape hatches.
3. Shared docs in `docs/` define meaning. Schemas define field names, required fields, and enums for interchange.
4. Existing field meanings are stable. Do not repurpose an existing field for a different semantic role.
5. Additive changes are preferred. New required fields or reinterpreted enums require a coordinated docs, schema, and runtime update.
6. Python and Rust implementations must map to these fields without reinterpretation.
7. `workflow` and `plan` are shared coordination surfaces. They do not redefine policy, verification, or execution semantics.

## File Map

| File | Purpose |
| --- | --- |
| `agent_identity.schema.json` | Canonical user-owned agent identity, scope, budget, delegation, and reputation record |
| `audit_verification_endpoint.schema.json` | Canonical live gateway audit-chain verification response |
| `autonomous_test_generation_plan.schema.json` | Canonical activation-blocked test generation plan from failure traces |
| `capability_adapter_closure_plan.schema.json` | Canonical adapter source closure action plan |
| `capability_candidate.schema.json` | Canonical forge-generated candidate capability package |
| `capability_descriptor.schema.json` | Canonical capability declaration |
| `capability_evidence_endpoint.schema.json` | Canonical live gateway capability evidence projection |
| `capability_improvement_portfolio.schema.json` | Canonical activation-blocked portfolio of prioritized capability upgrade proposals |
| `capability_improvement_proof_receipt.schema.json` | Canonical repository-local proof receipt for capability improvement plan evidence |
| `capability_maturity.schema.json` | Canonical evidence-derived capability maturity assessment |
| `collaboration_case.schema.json` | Canonical governed collaboration case with approval separation and non-terminal closure |
| `capability_registry_entry.schema.json` | Universal governed capability registry entry |
| `capability_improvement_portfolio.schema.json` | Canonical activation-blocked portfolio of ranked capability improvement proposals |
| `capability_upgrade_plan.schema.json` | Canonical governed capability upgrade proposal plan |
| `claim_verification_report.schema.json` | Canonical claim graph verification report for support, contradiction, freshness, and execution admission |
| `code_change_physics_packet.schema.json` | Canonical non-executing code-change physics packet for governance, creative path discovery, and repair planning |
| `commercial_metering_snapshot.schema.json` | Canonical commercial metering snapshot with plans, usage, provider costs, decisions, and tenant billing summaries |
| `economic_intelligence_snapshot.schema.json` | Canonical governed economic routing snapshot with utility decisions, blocked candidates, and policy override closure |
| `data_governance_snapshot.schema.json` | Canonical data governance lifecycle snapshot with decisions and retention controls |
| `deployment_orchestration_receipt.schema.json` | Canonical gateway deployment handoff receipt |
| `deployment_publication_closure_plan.schema.json` | Canonical deployment publication closure action plan |
| `deployment_publication_evidence_packet.schema.json` | Canonical non-effecting deployment publication evidence packet summary |
| `deployment_publication_operator_input_request.schema.json` | Canonical public-safe request for missing deployment publication operator inputs |
| `deployment_upstream_blocker_receipt.schema.json` | Canonical upstream API/DNS readiness blocker receipt for deployment publication |
| `durable_gmail_oauth_operator_handoff.schema.json` | Canonical redacted Gmail OAuth provider-setup handoff, recommended defaults, runtime bindings, and live-probe blockers |
| `durable_gmail_live_write_operator_input_request.schema.json` | Canonical public-safe request for missing durable Gmail live write operator inputs |
| `team_ops_shared_inbox_operator_handoff.schema.json` | Canonical redacted TeamOps shared inbox operator handoff with assistant profile, owner queue, approval policy, and live-probe blockers |
| `team_ops_shared_inbox_live_probe_approval_binding.schema.json` | Canonical redacted TeamOps shared inbox live-probe approval binding for downstream authority receipts |
| `team_ops_shared_inbox_live_probe_authority.schema.json` | Canonical redacted TeamOps shared inbox live-probe authority receipt that admits only approved read-only probes |
| `team_ops_shared_inbox_live_probe_operator_input_request.schema.json` | Canonical public-safe request for missing TeamOps shared inbox live-probe operator inputs |
| `team_ops_shared_inbox_live_probe_receipt.schema.json` | Canonical TeamOps shared inbox read-only live-probe receipt binding operator-input readiness to redacted observation evidence |
| `team_ops_shared_inbox_observation_routing_receipt.schema.json` | Canonical TeamOps shared inbox no-send routing receipt binding redacted observations to classification, owner assignment, and approval obligations |
| `team_ops_shared_inbox_approval_queue_receipt.schema.json` | Canonical TeamOps shared inbox no-send approval queue receipt binding ready routing evidence to a pending approval obligation |
| `team_ops_shared_inbox_approval_decision_receipt.schema.json` | Canonical TeamOps shared inbox no-send approval decision receipt binding a pending approval obligation to redacted operator decision evidence |
| `team_ops_shared_inbox_send_preparation_receipt.schema.json` | Canonical TeamOps shared inbox no-send preparation receipt binding approved decision evidence to redacted send-preparation evidence |
| `team_ops_shared_inbox_send_execution_receipt.schema.json` | Canonical TeamOps shared inbox send-execution receipt binding ready preparation evidence to redacted provider dispatch evidence without local provider mutation |
| `team_ops_shared_inbox_sent_message_observation_receipt.schema.json` | Canonical TeamOps shared inbox sent-message observation receipt binding send execution to two redacted provider observations, duplicate-absence evidence, and deterministic replay |
| `team_ops_shared_inbox_terminal_closure_review_packet.schema.json` | Canonical TeamOps shared inbox terminal closure review packet binding sent-message observation and provider-observation receipt evidence into a non-terminal closure candidate review |
| `personal_assistant_approval_review_packet.schema.json` | Canonical no-effect Personal Assistant approval proposal review packet with operator checks, authority denials, and evidence refs |
| `public_production_health_declaration.schema.json` | Canonical evidence-gated public production health declaration receipt |
| `deployment_witness.schema.json` | Canonical live gateway deployment witness artifact |
| `domain_capsule.schema.json` | Domain capsule operating-model package |
| `durable_gmail_oauth_operator_handoff.schema.json` | Canonical redacted operator handoff for durable Gmail OAuth setup and live-probe admission |
| `effect_assurance.schema.json` | Canonical planned, observed, and reconciled effect record |
| `finance_approval_email_calendar_binding_receipt.schema.json` | Canonical redacted worker, connector-token, and read-only scope witness binding receipt for finance live handoff |
| `finance_approval_email_calendar_operator_input_request.schema.json` | Canonical public-safe request for missing finance email/calendar operator inputs |
| `finance_approval_email_calendar_live_receipt.schema.json` | Canonical redacted live email/calendar receipt for finance approval handoff evidence |
| `finance_approval_handoff_packet.schema.json` | Canonical operator handoff packet for finance approval proof-pilot, live receipt binding, and live blockers |
| `finance_approval_live_handoff_chain_validation.schema.json` | Canonical aggregate chain validation report for finance approval live handoff artifacts |
| `finance_approval_live_handoff_closure_run.schema.json` | Canonical dry-run command sequence for finance approval live handoff closure |
| `finance_approval_live_handoff_plan.schema.json` | Canonical finance approval live email handoff promotion plan |
| `finance_approval_live_handoff_preflight.schema.json` | Canonical four-step preflight report for finance approval live handoff readiness |
| `finance_approval_operator_summary.schema.json` | Canonical redacted finance operator summary for packet and chain readiness |
| `finance_approval_packet_proof.schema.json` | Canonical proof export for governed finance approval packet closure or review |
| `finance_approval_payment_closure_receipt.schema.json` | Canonical provider-payment and ledger-reconciliation receipt for finance payment closure |
| `finance_approval_payment_provider_binding_receipt.schema.json` | Canonical redacted payment-provider binding receipt for non-sandbox finance payment closure |
| `operator_control_tower_snapshot.schema.json` | Canonical read-only operator control tower snapshot across governed platform panels |
| `physical_action_receipt.schema.json` | Canonical no-effect physical action safety receipt |
| `physical_capability_promotion_receipt.schema.json` | Canonical operator receipt binding physical Forge requirements, handoff refs, registry safety evidence, and preflight readiness |
| `general_agent_promotion_closure_plan.schema.json` | Canonical promotion closure action plan |
| `general_agent_promotion_environment_bindings.schema.json` | Canonical presence-only operator environment binding contract |
| `general_agent_promotion_environment_binding_receipt.schema.json` | Canonical presence-only operator environment binding receipt |
| `general_agent_promotion_live_evidence_queue.schema.json` | Canonical non-executing promotion live-evidence queue |
| `general_agent_promotion_terminal_approvals.schema.json` | Canonical terminal approval-ref receipt |
| `general_agent_promotion_terminal_certificate_gate.schema.json` | Canonical non-executing terminal certificate admission gate |
| `general_agent_promotion_terminal_certificate_candidates.schema.json` | Canonical non-executing terminal certificate candidate set |
| `general_agent_promotion_terminal_evidence_reconciliation.schema.json` | Canonical terminal evidence reconciliation gate |
| `general_agent_promotion_terminal_minting_gate.schema.json` | Canonical terminal certificate minting admission gate |
| `general_agent_promotion_terminal_certificate_minting_run.schema.json` | Canonical terminal certificate minting run receipt |
| `general_agent_promotion_handoff_packet.schema.json` | Canonical promotion handoff packet |
| `gateway_dns_resolution_receipt.schema.json` | Canonical gateway DNS resolution receipt for deployment publication gates |
| `gateway_dns_target_binding_receipt.schema.json` | Canonical gateway DNS target binding receipt for publication handoff |
| `gateway_health.schema.json` | Canonical public gateway health read model |
| `gateway_observability_snapshot.schema.json` | Canonical gateway observability summary with bounded run metrics |
| `goal.schema.json` | Canonical governed goal compilation contract |
| `channel_approval_strength_policy.schema.json` | Canonical Foundation Mode channel trust and approval-strength policy |
| `policy_decision.schema.json` | Canonical policy gate outcome |
| `production_evidence_witness.schema.json` | Canonical live gateway production evidence witness response |
| `proof_verification_endpoint.schema.json` | Canonical live gateway proof verification response |
| `execution_result.schema.json` | Canonical execution outcome |
| `trace_entry.schema.json` | Canonical causal audit entry |
| `replay_record.schema.json` | Canonical replay and audit capture |
| `runtime_conformance_collection.schema.json` | Canonical live runtime conformance collection envelope |
| `runtime_witness.schema.json` | Canonical signed runtime witness for gateway closure and anchor state |
| `simulation_receipt.schema.json` | Canonical causal simulation dry-run receipt |
| `sdlc_change_request.schema.json` | Canonical governed software-delivery intake artifact |
| `sdlc_requirement.schema.json` | Canonical governed software-delivery requirement artifact |
| `sdlc_design_decision.schema.json` | Canonical governed software-delivery design decision artifact |
| `sdlc_work_plan.schema.json` | Canonical governed software-delivery ordered work plan artifact |
| `sdlc_implementation_receipt.schema.json` | Canonical governed software-delivery implementation delta receipt |
| `sdlc_transition_receipt.schema.json` | Canonical governed software-delivery state transition receipt |
| `sdlc_verification_receipt.schema.json` | Canonical governed software-delivery verification receipt |
| `sdlc_security_review.schema.json` | Canonical governed software-delivery security review artifact |
| `sdlc_release_candidate.schema.json` | Canonical governed software-delivery release readiness artifact |
| `sdlc_deployment_candidate.schema.json` | Canonical governed software-delivery deployment readiness artifact |
| `sdlc_recovery_handoff_receipt.schema.json` | Canonical governed software-delivery rollback and incident handoff receipt |
| `sdlc_closure_receipt.schema.json` | Canonical governed software-delivery terminal closure receipt |
| `search_decision_receipt.schema.json` | Canonical search classification, freshness, budget, and retrieval-authority receipt |
| `software_dev/capability_manifest.schema.json` | Governed manifest contract for admitting dynamic software-development capabilities |
| `software_dev/*.input.schema.json` | Governed input contracts for repository mapping, context building, gate planning, sandboxed software changes, app task graph planning, and PR candidate preparation |
| `software_dev/*.output.schema.json` | Governed output and receipt contracts for repository maps, context bundles, gate plans, software-change receipts, app task graphs, and PR candidates |
| `streaming_budget_enforcement.schema.json` | Canonical predictive streaming budget event |
| `temporal_evidence_freshness_receipt.schema.json` | Canonical governed evidence freshness recheck receipt |
| `temporal_operation_receipt.schema.json` | Canonical runtime-owned temporal operation receipt |
| `temporal_resolution_receipt.schema.json` | Canonical governed temporal phrase resolution receipt |
| `temporal_reapproval_receipt.schema.json` | Canonical governed execution-time approval recheck receipt |
| `temporal_dispatch_window_receipt.schema.json` | Canonical governed dispatch-window admission receipt |
| `temporal_budget_window_receipt.schema.json` | Canonical governed tenant-local budget-window admission receipt |
| `temporal_causal_order_receipt.schema.json` | Canonical governed temporal causal-order receipt |
| `temporal_monotonic_duration_receipt.schema.json` | Canonical governed monotonic duration receipt |
| `temporal_accepted_risk_expiry_receipt.schema.json` | Canonical governed accepted-risk expiry receipt |
| `temporal_credential_expiry_receipt.schema.json` | Canonical governed credential expiry receipt |
| `temporal_retention_window_receipt.schema.json` | Canonical governed retention-window receipt |
| `temporal_rate_limit_window_receipt.schema.json` | Canonical governed rate-limit window receipt |
| `temporal_retry_window_receipt.schema.json` | Canonical governed retry-window receipt |
| `temporal_lease_window_receipt.schema.json` | Canonical governed lease-window receipt |
| `temporal_idempotency_window_receipt.schema.json` | Canonical governed idempotency-window receipt |
| `temporal_missed_run_receipt.schema.json` | Canonical governed missed-run receipt |
| `temporal_recurrence_window_receipt.schema.json` | Canonical governed recurrence-window receipt |
| `temporal_memory_receipt.schema.json` | Canonical governed temporal memory use receipt |
| `temporal_memory_refresh_receipt.schema.json` | Canonical governed temporal memory refresh workflow receipt |
| `temporal_scheduler_receipt.schema.json` | Canonical governed scheduled wakeup and lease receipt |
| `temporal_sla_receipt.schema.json` | Canonical governed SLA, business-window, and escalation receipt |
| `terminal_closure_certificate.schema.json` | Canonical final command closure certificate; TeamOps use binds provider-observation receipt identity through certificate metadata and graph refs |
| `trust_ledger_anchor_receipt.schema.json` | Canonical signed external proof anchor receipt for trust ledger bundles; TeamOps anchors require provider-observation artifact binding |
| `trust_ledger_anchor_submission_receipt.schema.json` | Canonical signed operator submission receipt for externally anchored trust-ledger exports; preserves anchor artifact root, artifact count, and required artifact classes including provider-observation when required |
| `trust_ledger_anchor_verification_report.schema.json` | Canonical offline verifier report for trust ledger anchor and package replay; preserves anchor artifact root, artifact count, and required artifact classes when the receipt is readable |
| `trust_ledger_bundle.schema.json` | Canonical signed evidence bundle for terminal closure anchoring; TeamOps use binds provider-observation receipt identity through bundle metadata and proof refs |
| `trust_ledger_bundle_verification_report.schema.json` | Canonical offline verifier report for trust ledger bundle replay |
| `trust_ledger_evidence_artifacts.schema.json` | Canonical typed evidence artifact export for trust ledger anchor verification, including provider-observation artifacts when a domain chain requires them |
| `trust_ledger_export_package.schema.json` | Canonical manifest binding trust ledger bundle, anchor receipt, and artifact export files |
| `trust_ledger_remote_submission_preflight.schema.json` | Canonical read-only remote anchor submission preflight receipt; projects required artifact classes before remote submit |
| `verification_result.schema.json` | Canonical verification closure |
| `learning_admission.schema.json` | Canonical learning admission decision |
| `latest_anchor_read_model.schema.json` | Canonical latest command-event anchor read model |
| `low_code_builder_catalog.schema.json` | Canonical declarative low-code builder catalog snapshot |
| `marketplace_sdk_catalog.schema.json` | Canonical governed marketplace and SDK catalog snapshot |
| `memory_lattice.schema.json` | Canonical memory planning and execution admission claim |
| `p3_memory_topology_read_model.schema.json` | Canonical P3 memory topology operator read model |
| `universal_action_orchestration.schema.json` | Canonical non-executing Universal Action Orchestration v1 envelope contract |
| `universal_action_orchestration_validation_receipt.schema.json` | Canonical non-terminal UAO validation receipt contract |
| `multimodal_operation_receipt.schema.json` | Canonical governed multimodal operation admission receipt |
| `environment_fingerprint.schema.json` | Canonical environment fingerprint |
| `lineage_query.schema.json` | Canonical lineage query response document |
| `multimodal_operation_receipt.schema.json` | Canonical governed multimodal operation receipt |
| `read_only_document_worker_path.schema.json` | Canonical Foundation Mode read-only document worker path selection |
| `read_only_first_worker_path.schema.json` | Canonical Foundation Mode first worker path selection |
| `read_only_search_worker_path.schema.json` | Canonical Foundation Mode read-only search worker path selection |
| `world_state.schema.json` | Canonical world-state graph projection |
| `worker_failure_receipt.schema.json` | Canonical non-terminal worker failure and recovery receipt |
| `worker_mesh.schema.json` | Canonical networked worker lease and dispatch receipt |
| `read_only_worker_runtime_receipt_handoff.schema.json` | Canonical Foundation Mode handoff from read-only worker rehearsal evidence to future runtime receipt-emitter obligations |
| `read_only_worker_runtime_receipt_emitter_dry_run.schema.json` | Canonical Foundation Mode dry-run receipt for future read-only worker runtime receipt-emitter evidence |
| `read_only_worker_runtime_runner_binding_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker runtime runner registration and runtime receipt schema-binding evidence |
| `read_only_worker_runtime_receipt_candidate.schema.json` | Canonical Foundation Mode candidate for the future read-only worker runtime receipt envelope |
| `read_only_worker_runtime_receipt_schema_binding_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker runtime receipt schema-binding evidence |
| `read_only_worker_runtime_receipt_store_write_path_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker runtime receipt-store write-path evidence |
| `read_only_worker_runtime_runner_registration_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime runner registration evidence |
| `read_only_worker_runtime_dispatch_endpoint_registration_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime dispatch endpoint registration evidence |
| `read_only_worker_runtime_receipt_emitter_registration_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime receipt emitter registration evidence |
| `read_only_worker_runtime_receipt_schema_binding_activation_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime receipt schema-binding activation evidence |
| `read_only_worker_runtime_receipt_store_activation_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime receipt-store activation evidence |
| `read_only_worker_runtime_receipt_store_operator_approval_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime receipt-store operator approval evidence |
| `read_only_worker_runtime_receipt_emission_admission_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime receipt emission admission evidence |
| `read_only_worker_runtime_active_lease_admission_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker active runtime lease admission evidence |
| `read_only_worker_runtime_dispatch_admission_witness.schema.json` | Canonical Foundation Mode witness for future live read-only worker runtime dispatch admission evidence |
| `read_only_worker_active_runtime_lease_admission_witness.schema.json` | Canonical Foundation Mode witness for future active read-only worker runtime lease admission evidence |
| `read_only_worker_uao_dispatch_authorization_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker UAO dispatch authorization evidence |
| `read_only_worker_phi_gov_dispatch_authorization_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker Phi_gov dispatch authorization evidence |
| `read_only_worker_effect_reconciliation_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker effect reconciliation evidence |
| `read_only_worker_receipt_append_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker receipt append evidence |
| `read_only_worker_terminal_closure_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker terminal closure evidence |
| `read_only_worker_runtime_enablement_witness.schema.json` | Canonical Foundation Mode witness for future read-only worker runtime enablement evidence |
| `read_only_worker_runtime_enablement_operator_input_request.schema.json` | Public-safe request contract for missing read-only worker runtime enablement evidence names |
| `read_only_worker_runtime_enablement_evidence_request_status_ledger.schema.json` | Read-only status ledger for unresolved read-only worker runtime enablement evidence requests |
| `read_only_worker_runtime_enablement_submitted_evidence_refs.schema.json` | Submitted-for-review repo-local evidence refs for read-only worker runtime enablement, without acceptance or authority |
| `workflow.schema.json` | Shared workflow descriptor interchange surface |
| `plan.schema.json` | Shared plan definition |
| `policy_proof_report.schema.json` | Canonical policy prover result and counterexample report |
| `policy_studio_session.schema.json` | Canonical read-only policy studio session with simulations and bounded probe report |
| `public_naming_readiness.schema.json` | Public naming launch-gate witness |
| `mullu_name_clearance_draft.schema.json` | Draft name-clearance evidence packet |

## Notes

The schemas stay conservative by keeping canonical meaning in shared docs and future growth in `metadata` or `extensions`. If shared behavior changes, update docs and schemas in the same change.
