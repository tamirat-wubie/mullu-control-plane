"""Gateway capability forge.

Purpose: Build and validate candidate capability packages before they can
    enter governed capability certification.
Governance scope: candidate-only capability generation, policy/evidence/eval
    completeness, side-effect classification, rollback coverage, certification
    maturity handoff, registry evidence installation, and promotion blocking for
    uncertified or high-risk packages.
Dependencies: standard-library dataclasses, command-spine hashing, capability
    maturity evidence bundles, and governed capability fabric contracts.
Invariants:
  - The forge emits candidate packages, never production-certified powers.
  - Effect-bearing capabilities require receipt, sandbox, and recovery evidence.
  - High-risk capabilities require approval policy and tenant-boundary evals.
  - Candidate packages must name mock providers before sandbox promotion.
  - Certification handoff emits evidence bundles, not registry mutations.
  - Registry handoff installation writes certification evidence only.
  - Direct maturity overrides are refused on handoff installation.
  - Batch handoff installation requires exact entry-to-handoff coverage.
  - No candidate may self-deploy into the capability registry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Mapping

from gateway.capability_maturity import CapabilityCertificationEvidenceBundle, CapabilityMaturityEvidenceSynthesizer
from gateway.command_spine import canonical_hash
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
)


_REQUIRED_BASE_EVALS = (
    "tenant_boundary",
    "approval_required",
    "no_secret_leak",
)
_REQUIRED_INJECTION_EVAL = "prompt_injection"
_EFFECT_BEARING_EFFECTS = {
    "external_message_send",
    "external_write",
    "payment_dispatch",
    "credentialed_provider_write",
    "filesystem_write",
    "database_write",
}
_CERTIFICATION_EVIDENCE_EXTENSION_KEY = "capability_certification_evidence"
_MATURITY_EVIDENCE_EXTENSION_KEY = "capability_maturity_evidence"


@dataclass(frozen=True, slots=True)
class CapabilitySchemaBundle:
    """Input, output, error, and receipt schema references."""

    input_schema_ref: str
    output_schema_ref: str
    error_schema_ref: str
    receipt_schema_ref: str


@dataclass(frozen=True, slots=True)
class CapabilityAdapterSpec:
    """Candidate adapter boundary."""

    adapter_id: str
    adapter_type: str
    entrypoint: str
    sandbox_required: bool
    network_allowlist: list[str] = field(default_factory=list)
    secret_scope: str = "none"

    def __post_init__(self) -> None:
        object.__setattr__(self, "network_allowlist", list(self.network_allowlist))


@dataclass(frozen=True, slots=True)
class CapabilityPolicyRule:
    """Policy rule required before candidate execution."""

    rule_id: str
    rule_type: str
    required: bool
    description: str


@dataclass(frozen=True, slots=True)
class CapabilityEvalCase:
    """Eval case required for certification."""

    eval_id: str
    eval_type: str
    fixture_ref: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class CapabilityMockProvider:
    """Deterministic mock provider for non-production testing."""

    provider_id: str
    fixture_ref: str
    deterministic: bool


@dataclass(frozen=True, slots=True)
class CapabilitySandboxTest:
    """Sandbox replay test required for candidate promotion."""

    test_id: str
    scenario_ref: str
    expected_receipt_ref: str


@dataclass(frozen=True, slots=True)
class CapabilityReceiptContract:
    """Command-bound receipt contract."""

    receipt_type: str
    required_fields: list[str]
    terminal_certificate_required: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_fields", list(self.required_fields))


@dataclass(frozen=True, slots=True)
class CapabilityRollbackPath:
    """Rollback, compensation, or review path for failed effects."""

    rollback_type: str
    capability_ref: str = ""
    review_required: bool = False
    compensation_required: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityDocumentation:
    """Operator and promotion documentation references."""

    operator_runbook_ref: str
    promotion_evidence_ref: str
    limitations_ref: str


@dataclass(frozen=True, slots=True)
class CandidateCapabilityPackage:
    """Candidate package emitted by the capability forge."""

    package_id: str
    capability_id: str
    version: str
    domain: str
    risk: str
    side_effects: list[str]
    schemas: CapabilitySchemaBundle
    adapter: CapabilityAdapterSpec
    policy_rules: list[CapabilityPolicyRule]
    evals: list[CapabilityEvalCase]
    mock_provider: CapabilityMockProvider
    sandbox_tests: list[CapabilitySandboxTest]
    receipt_contract: CapabilityReceiptContract
    rollback_path: CapabilityRollbackPath
    documentation: CapabilityDocumentation
    certification_status: str = "candidate"
    promotion_blocked: bool = True
    package_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "side_effects", list(self.side_effects))
        object.__setattr__(self, "policy_rules", list(self.policy_rules))
        object.__setattr__(self, "evals", list(self.evals))
        object.__setattr__(self, "sandbox_tests", list(self.sandbox_tests))


@dataclass(frozen=True, slots=True)
class CapabilityForgeInput:
    """Structured source material used to create a candidate package."""

    capability_id: str
    version: str
    domain: str
    risk: str
    side_effects: tuple[str, ...]
    api_docs_ref: str
    input_schema_ref: str
    output_schema_ref: str
    owner_team: str
    network_allowlist: tuple[str, ...] = ()
    secret_scope: str = "none"
    requires_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "side_effects", tuple(self.side_effects))
        object.__setattr__(self, "network_allowlist", tuple(self.network_allowlist))


@dataclass(frozen=True, slots=True)
class CapabilityForgeValidation:
    """Validation result for a candidate package."""

    accepted: bool
    reason: str
    errors: tuple[str, ...] = ()
    package_id: str = ""
    package_hash: str = ""


@dataclass(frozen=True, slots=True)
class CapabilityCertificationHandoff:
    """Candidate-to-certification handoff carrying maturity evidence refs."""

    package_id: str
    capability_id: str
    package_hash: str
    maturity_evidence_bundle: CapabilityCertificationEvidenceBundle
    required_evidence_refs: tuple[str, ...]
    handoff_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_evidence_refs", tuple(str(ref) for ref in self.required_evidence_refs))


@dataclass(frozen=True, slots=True)
class CapabilityHandoffEvidenceInstallBatch:
    """Evidence-only installation batch for capsule compiler inputs."""

    registry_entries: tuple[CapabilityRegistryEntry, ...]
    installed_capability_ids: tuple[str, ...]
    handoff_hashes: tuple[str, ...]
    batch_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "registry_entries", tuple(self.registry_entries))
        for entry in self.registry_entries:
            if not isinstance(entry, CapabilityRegistryEntry):
                raise ValueError("registry_entries must contain CapabilityRegistryEntry values")
        object.__setattr__(self, "installed_capability_ids", tuple(str(value) for value in self.installed_capability_ids))
        object.__setattr__(self, "handoff_hashes", tuple(str(value) for value in self.handoff_hashes))
        if self.installed_capability_ids != tuple(entry.capability_id for entry in self.registry_entries):
            raise ValueError("installed_capability_ids must match registry_entries")
        if len(self.handoff_hashes) != len(self.registry_entries):
            raise ValueError("handoff_hashes must match registry_entries")
        if any(not handoff_hash.strip() for handoff_hash in self.handoff_hashes):
            raise ValueError("handoff_hashes must contain non-empty strings")
        if self.batch_hash:
            normalized_hash = str(self.batch_hash).strip()
            if not normalized_hash:
                raise ValueError("batch_hash must be non-empty when supplied")
            object.__setattr__(self, "batch_hash", normalized_hash)


class CapabilityForge:
    """Create and validate candidate capability packages."""

    def create_candidate(self, source: CapabilityForgeInput) -> CandidateCapabilityPackage:
        """Create a deterministic candidate package from structured source material."""
        package_seed = {
            "capability_id": source.capability_id,
            "version": source.version,
            "domain": source.domain,
            "api_docs_ref": source.api_docs_ref,
        }
        package_id = f"capability-candidate-{canonical_hash(package_seed)[:16]}"
        effect_bearing = _effect_bearing(source.side_effects)
        policy_rules = (
            CapabilityPolicyRule(
                rule_id="policy-tenant-boundary",
                rule_type="tenant_binding",
                required=True,
                description="Tenant identity must bind every request.",
            ),
            CapabilityPolicyRule(
                rule_id="policy-approval",
                rule_type="approval",
                required=source.requires_approval or source.risk == "high",
                description="Approval is required when risk or side effects require it.",
            ),
            CapabilityPolicyRule(
                rule_id="policy-secret-scope",
                rule_type="secret_scope",
                required=source.secret_scope != "none",
                description="Secrets remain inside declared adapter scope.",
            ),
        )
        evals = [
            CapabilityEvalCase(
                eval_id=f"eval-{eval_type.replace('_', '-')}",
                eval_type=eval_type,
                fixture_ref=f"fixtures/{source.capability_id}/{eval_type}.json",
            )
            for eval_type in _required_eval_types(source.risk)
        ]
        sandbox_tests = (
            CapabilitySandboxTest(
                test_id="sandbox-replay",
                scenario_ref=f"sandbox/{source.capability_id}/scenario.json",
                expected_receipt_ref=f"sandbox/{source.capability_id}/receipt.json",
            ),
        )
        candidate = CandidateCapabilityPackage(
            package_id=package_id,
            capability_id=source.capability_id,
            version=source.version,
            domain=source.domain,
            risk=source.risk,
            side_effects=source.side_effects,
            schemas=CapabilitySchemaBundle(
                input_schema_ref=source.input_schema_ref,
                output_schema_ref=source.output_schema_ref,
                error_schema_ref=f"schemas/{source.capability_id}.error.schema.json",
                receipt_schema_ref=f"schemas/{source.capability_id}.receipt.schema.json",
            ),
            adapter=CapabilityAdapterSpec(
                adapter_id=f"adapter-{source.capability_id}",
                adapter_type="provider_adapter",
                entrypoint=f"gateway.adapters.{source.capability_id}",
                sandbox_required=effect_bearing or source.risk in {"medium", "high"},
                network_allowlist=source.network_allowlist,
                secret_scope=source.secret_scope,
            ),
            policy_rules=list(policy_rules),
            evals=list(evals),
            mock_provider=CapabilityMockProvider(
                provider_id=f"mock-{source.capability_id}",
                fixture_ref=f"fixtures/{source.capability_id}/mock_provider.json",
                deterministic=True,
            ),
            sandbox_tests=list(sandbox_tests),
            receipt_contract=CapabilityReceiptContract(
                receipt_type=f"{source.capability_id}.receipt",
                required_fields=["command_id", "tenant_id", "capability_id", "receipt_hash"],
                terminal_certificate_required=effect_bearing or source.risk == "high",
            ),
            rollback_path=CapabilityRollbackPath(
                rollback_type="review" if effect_bearing else "none",
                review_required=effect_bearing,
                compensation_required="payment_dispatch" in source.side_effects,
            ),
            documentation=CapabilityDocumentation(
                operator_runbook_ref=f"docs/capabilities/{source.capability_id}.md",
                promotion_evidence_ref=f"evidence/{source.capability_id}/promotion.json",
                limitations_ref=f"docs/capabilities/{source.capability_id}.limitations.md",
            ),
            certification_status="candidate",
            promotion_blocked=True,
            metadata={
                "api_docs_ref": source.api_docs_ref,
                "owner_team": source.owner_team,
                **source.metadata,
            },
        )
        return _stamp_package(candidate)

    def validate(self, package: CandidateCapabilityPackage) -> CapabilityForgeValidation:
        """Validate a candidate package without installing it."""
        errors = _validation_errors(package)
        if errors:
            return CapabilityForgeValidation(
                accepted=False,
                reason="candidate_invalid",
                errors=tuple(errors),
                package_id=package.package_id,
                package_hash=package.package_hash,
            )
        return CapabilityForgeValidation(
            accepted=True,
            reason="candidate_ready_for_certification",
            errors=(),
            package_id=package.package_id,
            package_hash=package.package_hash,
        )

    def build_certification_handoff(
        self,
        package: CandidateCapabilityPackage,
        *,
        live_read_receipt_ref: str,
        worker_deployment_ref: str,
        recovery_evidence_ref: str,
        live_write_receipt_ref: str = "",
        autonomy_controls_ref: str = "",
        certification_ref: str = "",
        sandbox_receipt_ref: str = "",
    ) -> CapabilityCertificationHandoff:
        """Build the maturity evidence handoff for an externally certified package."""
        validation = self.validate(package)
        if not validation.accepted:
            raise ValueError("capability_candidate_invalid_for_certification_handoff")
        normalized_live_read = _require_text(live_read_receipt_ref, "live_read_receipt_ref")
        normalized_worker = _require_text(worker_deployment_ref, "worker_deployment_ref")
        normalized_recovery = _require_text(recovery_evidence_ref, "recovery_evidence_ref")
        normalized_live_write = str(live_write_receipt_ref).strip()
        if _effect_bearing(package.side_effects) and not normalized_live_write:
            raise ValueError("effect_bearing_certification_requires_live_write_ref")
        bundle = CapabilityCertificationEvidenceBundle(
            capability_id=package.capability_id,
            certification_ref=str(certification_ref).strip() or package.documentation.promotion_evidence_ref,
            sandbox_receipt_ref=str(sandbox_receipt_ref).strip() or _sandbox_receipt_ref(package),
            live_read_receipt_ref=normalized_live_read,
            live_write_receipt_ref=normalized_live_write,
            worker_deployment_ref=normalized_worker,
            recovery_evidence_ref=normalized_recovery,
            autonomy_controls_ref=str(autonomy_controls_ref).strip(),
        )
        return _stamp_handoff(
            CapabilityCertificationHandoff(
                package_id=package.package_id,
                capability_id=package.capability_id,
                package_hash=package.package_hash,
                maturity_evidence_bundle=bundle,
                required_evidence_refs=_handoff_required_evidence_refs(package, bundle),
            )
        )


def install_certification_handoff_evidence(
    entry: CapabilityRegistryEntry,
    handoff: CapabilityCertificationHandoff,
    *,
    require_production_ready: bool = False,
) -> CapabilityRegistryEntry:
    """Return a certified registry entry carrying handoff certification evidence.

    Error contract:
      - capability_handoff_entry_mismatch: registry and handoff capability ids differ.
      - capability_handoff_requires_certified_entry: entry has not passed certification.
      - capability_handoff_hash_required: handoff has not been stamped.
      - capability_handoff_hash_mismatch: handoff content differs from its stamp.
      - capability_handoff_refuses_maturity_override: entry carries direct maturity evidence.
      - capability_handoff_evidence_conflict: existing certification evidence differs.
      - capability_certification_evidence_incomplete: strict production readiness failed.
    """
    if entry.capability_id != handoff.capability_id:
        raise ValueError("capability_handoff_entry_mismatch")
    if entry.certification_status is not CapabilityCertificationStatus.CERTIFIED:
        raise ValueError("capability_handoff_requires_certified_entry")
    _validate_handoff_stamp(handoff)
    if _MATURITY_EVIDENCE_EXTENSION_KEY in entry.extensions:
        raise ValueError("capability_handoff_refuses_maturity_override")

    extension = _certification_evidence_extension_from_handoff(handoff)
    existing_extension = entry.extensions.get(_CERTIFICATION_EVIDENCE_EXTENSION_KEY)
    if existing_extension is not None:
        if not isinstance(existing_extension, Mapping):
            raise ValueError("capability_handoff_evidence_conflict")
        if dict(existing_extension) != extension:
            raise ValueError("capability_handoff_evidence_conflict")

    CapabilityMaturityEvidenceSynthesizer().materialize_extension(
        entry,
        handoff.maturity_evidence_bundle,
        require_production_ready=require_production_ready,
    )
    return replace(
        entry,
        extensions={
            **dict(entry.extensions),
            _CERTIFICATION_EVIDENCE_EXTENSION_KEY: extension,
        },
    )


def install_certification_handoff_evidence_batch(
    entries: Iterable[CapabilityRegistryEntry],
    handoffs: Iterable[CapabilityCertificationHandoff],
    *,
    require_production_ready: bool = False,
) -> CapabilityHandoffEvidenceInstallBatch:
    """Return registry entries with exact handoff certification evidence installed.

    Error contract:
      - capability_handoff_batch_entry_required: no registry entries were supplied.
      - capability_handoff_batch_duplicate_entry: one capability id appears twice.
      - capability_handoff_batch_duplicate_handoff: one handoff capability id appears twice.
      - capability_handoff_batch_missing_handoff:<ids>: entry ids lack handoffs.
      - capability_handoff_batch_extra_handoff:<ids>: handoffs lack matching entries.
      - single-entry install errors from install_certification_handoff_evidence.
    """
    entries_tuple = tuple(entries)
    handoffs_tuple = tuple(handoffs)
    if not entries_tuple:
        raise ValueError("capability_handoff_batch_entry_required")
    entry_ids = tuple(entry.capability_id for entry in entries_tuple)
    if len(set(entry_ids)) != len(entry_ids):
        raise ValueError("capability_handoff_batch_duplicate_entry")
    handoff_ids = tuple(handoff.capability_id for handoff in handoffs_tuple)
    if len(set(handoff_ids)) != len(handoff_ids):
        raise ValueError("capability_handoff_batch_duplicate_handoff")
    handoffs_by_capability = {handoff.capability_id: handoff for handoff in handoffs_tuple}
    missing_handoffs = tuple(capability_id for capability_id in entry_ids if capability_id not in handoffs_by_capability)
    if missing_handoffs:
        raise ValueError(f"capability_handoff_batch_missing_handoff:{','.join(missing_handoffs)}")
    extra_handoffs = tuple(capability_id for capability_id in handoff_ids if capability_id not in entry_ids)
    if extra_handoffs:
        raise ValueError(f"capability_handoff_batch_extra_handoff:{','.join(extra_handoffs)}")

    installed_entries = tuple(
        install_certification_handoff_evidence(
            entry,
            handoffs_by_capability[entry.capability_id],
            require_production_ready=require_production_ready,
        )
        for entry in entries_tuple
    )
    return _stamp_handoff_evidence_install_batch(
        CapabilityHandoffEvidenceInstallBatch(
            registry_entries=installed_entries,
            installed_capability_ids=entry_ids,
            handoff_hashes=tuple(handoffs_by_capability[capability_id].handoff_hash for capability_id in entry_ids),
        )
    )


def _validation_errors(package: CandidateCapabilityPackage) -> list[str]:
    errors: list[str] = []
    if not package.package_id:
        errors.append("package_id_required")
    if not package.capability_id:
        errors.append("capability_id_required")
    if not package.version:
        errors.append("version_required")
    if package.certification_status != "candidate":
        errors.append("candidate_must_not_claim_certified_status")
    if not package.promotion_blocked:
        errors.append("candidate_promotion_must_be_blocked")
    if not package.package_hash:
        errors.append("package_hash_required")
    if not package.schemas.input_schema_ref or not package.schemas.output_schema_ref:
        errors.append("input_output_schema_refs_required")
    if not package.schemas.receipt_schema_ref:
        errors.append("receipt_schema_ref_required")
    if not package.adapter.adapter_id or not package.adapter.entrypoint:
        errors.append("adapter_boundary_required")
    if package.adapter.secret_scope != "none" and not package.adapter.sandbox_required:
        errors.append("secret_scope_requires_sandbox")
    eval_types = {eval_case.eval_type for eval_case in package.evals if eval_case.required}
    for eval_type in _REQUIRED_BASE_EVALS:
        if eval_type not in eval_types:
            errors.append(f"missing_eval:{eval_type}")
    if package.risk in {"medium", "high"} and _REQUIRED_INJECTION_EVAL not in eval_types:
        errors.append(f"missing_eval:{_REQUIRED_INJECTION_EVAL}")
    policy_types = {rule.rule_type for rule in package.policy_rules if rule.required}
    if "tenant_binding" not in policy_types:
        errors.append("tenant_binding_policy_required")
    effect_bearing = _effect_bearing(package.side_effects)
    if package.risk == "high" and "approval" not in policy_types:
        errors.append("high_risk_approval_policy_required")
    if effect_bearing and not package.adapter.sandbox_required:
        errors.append("effect_bearing_candidate_requires_sandbox")
    if effect_bearing and not package.sandbox_tests:
        errors.append("effect_bearing_candidate_requires_sandbox_tests")
    if effect_bearing and not package.receipt_contract.terminal_certificate_required:
        errors.append("effect_bearing_candidate_requires_terminal_certificate")
    if effect_bearing and package.rollback_path.rollback_type == "none":
        errors.append("effect_bearing_candidate_requires_recovery_path")
    if not package.mock_provider.provider_id or not package.mock_provider.deterministic:
        errors.append("deterministic_mock_provider_required")
    if not package.documentation.operator_runbook_ref:
        errors.append("operator_runbook_required")
    return errors


def _required_eval_types(risk: str) -> tuple[str, ...]:
    eval_types = list(_REQUIRED_BASE_EVALS)
    if risk in {"medium", "high"}:
        eval_types.insert(0, _REQUIRED_INJECTION_EVAL)
    return tuple(eval_types)


def _effect_bearing(side_effects: Iterable[str]) -> bool:
    return bool(set(side_effects).intersection(_EFFECT_BEARING_EFFECTS))


def _sandbox_receipt_ref(package: CandidateCapabilityPackage) -> str:
    if not package.sandbox_tests:
        raise ValueError("sandbox_receipt_ref_required")
    return _require_text(package.sandbox_tests[0].expected_receipt_ref, "sandbox_receipt_ref")


def _handoff_required_evidence_refs(
    package: CandidateCapabilityPackage,
    bundle: CapabilityCertificationEvidenceBundle,
) -> tuple[str, ...]:
    refs = (
        package.documentation.promotion_evidence_ref,
        bundle.sandbox_receipt_ref,
        bundle.live_read_receipt_ref,
        bundle.live_write_receipt_ref,
        bundle.worker_deployment_ref,
        bundle.recovery_evidence_ref,
        bundle.autonomy_controls_ref,
    )
    return tuple(ref for ref in refs if ref)


def _validate_handoff_stamp(handoff: CapabilityCertificationHandoff) -> None:
    _require_text(handoff.package_id, "capability_handoff_package_id")
    _require_text(handoff.package_hash, "capability_handoff_package_hash")
    handoff_hash = _require_text(handoff.handoff_hash, "capability_handoff_hash")
    payload = asdict(replace(handoff, handoff_hash=""))
    if handoff_hash != canonical_hash(payload):
        raise ValueError("capability_handoff_hash_mismatch")


def _certification_evidence_extension_from_handoff(
    handoff: CapabilityCertificationHandoff,
) -> dict[str, Any]:
    bundle = handoff.maturity_evidence_bundle
    payload: dict[str, Any] = {
        "capability_id": bundle.capability_id,
        "certification_ref": bundle.certification_ref,
        "sandbox_receipt_ref": bundle.sandbox_receipt_ref,
        "live_read_receipt_ref": bundle.live_read_receipt_ref,
        "live_write_receipt_ref": bundle.live_write_receipt_ref,
        "worker_deployment_ref": bundle.worker_deployment_ref,
        "recovery_evidence_ref": bundle.recovery_evidence_ref,
        "autonomy_controls_ref": bundle.autonomy_controls_ref,
        "source_package_id": handoff.package_id,
        "source_package_hash": handoff.package_hash,
        "source_handoff_hash": handoff.handoff_hash,
        "installed_by": "install_certification_handoff_evidence",
    }
    return {
        **payload,
        "certification_evidence_hash": canonical_hash(payload),
    }


def _stamp_handoff_evidence_install_batch(
    batch: CapabilityHandoffEvidenceInstallBatch,
) -> CapabilityHandoffEvidenceInstallBatch:
    payload = {
        "registry_entries": [entry.to_json_dict() for entry in batch.registry_entries],
        "installed_capability_ids": list(batch.installed_capability_ids),
        "handoff_hashes": list(batch.handoff_hashes),
    }
    return replace(batch, batch_hash=canonical_hash(payload))


def _require_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name}_required")
    return normalized


def _stamp_package(package: CandidateCapabilityPackage) -> CandidateCapabilityPackage:
    payload = asdict(replace(package, package_hash=""))
    return replace(package, package_hash=canonical_hash(payload))


def _stamp_handoff(handoff: CapabilityCertificationHandoff) -> CapabilityCertificationHandoff:
    payload = asdict(replace(handoff, handoff_hash=""))
    return replace(handoff, handoff_hash=canonical_hash(payload))
