"""Gateway Capability Fabric Loader.

Purpose: Builds an optional registry-backed command capability admission gate
    for gateway command execution.
Governance scope: environment-gated domain capsule loading, capsule pack
    loading, capability pack loading, capability registry installation, and
    command admission gate construction with maturity read-model projection.
Dependencies: governed capability fabric contracts, compiler, registry, and
    command admission core.
Invariants:
  - Fabric admission is disabled unless explicitly enabled.
  - Enabled fabric admission requires explicit JSON sources or checked-in
    default packs requested through configuration.
  - Installed capabilities are resolved from explicit capsule references.
  - Failed compilation or installation fails gateway startup instead of running
    with a partial capability fabric.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from gateway.capability_maturity import CapabilityRegistryMaturityProjector
from mcoi_runtime.contracts.capability_manifest import CapabilityManifestAdmissionStatus
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    CommandCapabilityAdmissionDecision,
    CommandCapabilityAdmissionStatus,
    DomainCapsule,
)
from mcoi_runtime.core.capability_manifest_registry import CapabilityManifestRegistry
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.domain_capsule_compiler import DomainCapsuleCompiler
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry


_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CAPSULE_PATHS = (
    _REPO_ROOT / "capsules" / "agentic_control.json",
    _REPO_ROOT / "capsules" / "browser.json",
    _REPO_ROOT / "capsules" / "communication.json",
    _REPO_ROOT / "capsules" / "connector.json",
    _REPO_ROOT / "capsules" / "creative.json",
    _REPO_ROOT / "capsules" / "deployment.json",
    _REPO_ROOT / "capsules" / "document.json",
    _REPO_ROOT / "capsules" / "enterprise.json",
    _REPO_ROOT / "capsules" / "financial.json",
    _REPO_ROOT / "capsules" / "computer.json",
    _REPO_ROOT / "capsules" / "messaging.json",
    _REPO_ROOT / "capsules" / "phone.json",
    _REPO_ROOT / "capsules" / "voice.json",
)
_DEFAULT_CAPABILITY_PACK_PATHS = (
    _REPO_ROOT / "capabilities" / "agentic_control" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "browser" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "communication" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "connector" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "creative" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "deployment" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "document" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "enterprise" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "financial" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "computer" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "messaging" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "phone" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "voice" / "capability_pack.json",
)
_SOFTWARE_DEV_CAPSULE_PATH = _REPO_ROOT / "capsules" / "software_dev.json"
_SOFTWARE_DEV_CAPABILITY_PACK_PATH = _REPO_ROOT / "capabilities" / "software_dev" / "capability_pack.json"
_SOFTWARE_DEV_CAPABILITY_MANIFEST_DIR = _REPO_ROOT / "capabilities" / "software_dev" / "manifests"
_AGENTIC_CONTROL_CAPSULE_PATH = _REPO_ROOT / "capsules" / "agentic_control.json"
_AGENTIC_CONTROL_CAPABILITY_PACK_PATH = (
    _REPO_ROOT / "capabilities" / "agentic_control" / "capability_pack.json"
)
_UNIVERSAL_DOMAIN_OPS_CAPSULE_PATH = _REPO_ROOT / "capsules" / "universal_domain_ops.json"
_UNIVERSAL_DOMAIN_OPS_CAPABILITY_PACK_PATH = (
    _REPO_ROOT / "capabilities" / "universal_domain_ops" / "capability_pack.json"
)
_GENERAL_AGENT_PLAN_DEFINITIONS = (
    {
        "plane_index": 0,
        "plane_id": "0.governance_core",
        "name": "Governance Core",
        "capability_prefixes": ("agentic_control.",),
        "capability_ids": (),
        "boundary": "identity, tenant, policy, RBAC, budget, rate-limit, approval, audit, and proof gates",
        "evidence_refs": (
            "gateway.command_spine",
            "gateway.router",
            "gateway.receipt_middleware",
        ),
    },
    {
        "plane_index": 1,
        "plane_id": "1.llm_reasoning_plane",
        "name": "LLM / Reasoning Plane",
        "capability_prefixes": ("creative.",),
        "capability_ids": (
            "document.summarize",
            "email.classify",
            "email.reply_suggest",
            "enterprise.knowledge_search",
            "voice.intent_classification",
            "voice.meeting_summarize",
            "voice.action_items_extract",
        ),
        "boundary": "budgeted model routing and bounded reasoning skills only",
        "evidence_refs": ("mcoi_runtime.app.llm_bootstrap", "mcoi_runtime.adapters.multi_provider"),
    },
    {
        "plane_index": 2,
        "plane_id": "2.memory_plane",
        "name": "Memory Plane",
        "capability_prefixes": (),
        "capability_ids": ("enterprise.knowledge_search",),
        "boundary": "working memory, admitted episodic memory, reviewed semantic memory, and reviewed procedural memory",
        "evidence_refs": ("memory_lattice", "learning_admission", "terminal_closure_certificate"),
    },
    {
        "plane_index": 3,
        "plane_id": "3.tool_skill_plane",
        "name": "Tool / Skill Plane",
        "capability_prefixes": ("browser.", "creative.", "document.", "enterprise.", "financial.", "spreadsheet."),
        "capability_ids": (
            "computer.code.patch",
            "computer.command.run",
            "computer.filesystem.observe",
            "connector.google_drive.read",
            "connector.google_drive.write.with_approval",
            "connector.github.read",
            "connector.github.write.with_approval",
            "github.open_pull_request",
            "connector.postgres.query",
            "connector.postgres.write.with_approval",
            "email.read",
            "email.search",
            "email.draft",
            "email.send.with_approval",
            "email.classify",
            "email.reply_suggest",
            "calendar.read",
            "calendar.conflict_check",
            "calendar.schedule",
            "calendar.reschedule",
            "calendar.invite",
            "voice.speech_to_text",
            "voice.text_to_speech",
            "voice.intent_classification",
            "voice.intent_confirm",
            "voice.meeting_summarize",
            "voice.action_items_extract",
            "messaging.sms.send.with_approval",
            "messaging.sms.draft",
            "messaging.chat.send.with_approval",
            "messaging.chat.draft",
            "messaging.thread.read",
            "phone.call.place.with_approval",
            "phone.call.receive",
            "phone.call.transfer.with_approval",
            "phone.call.terminate",
            "phone.call.transcript_record",
        ),
        "boundary": "capability records are exposed; raw tools stay behind policy-bound workers",
        "evidence_refs": ("governed_capability_records", "capability_registry_manifest"),
    },
    {
        "plane_index": 4,
        "plane_id": "4.computer_control_plane",
        "name": "Computer Control Plane",
        "capability_prefixes": ("computer.",),
        "capability_ids": (),
        "boundary": "workspace-bounded code and command execution through sandbox runners",
        "evidence_refs": ("gateway.sandbox_runner", "mcoi_runtime.adapters.code_adapter"),
    },
    {
        "plane_index": 5,
        "plane_id": "5.browser_web_plane",
        "name": "Browser / Web Plane",
        "capability_prefixes": ("browser.",),
        "capability_ids": (),
        "boundary": "restricted browser worker with domain allowlists and approval for submissions",
        "evidence_refs": ("gateway.browser_worker", "gateway.browser_playwright_adapter"),
    },
    {
        "plane_index": 6,
        "plane_id": "6.document_data_plane",
        "name": "Document / Data Plane",
        "capability_prefixes": ("document.", "spreadsheet."),
        "capability_ids": ("creative.data_analyze", "creative.document_generate"),
        "boundary": "deterministic extraction before explanation; external send requires approval",
        "evidence_refs": ("gateway.document_worker", "gateway.document_production_parsers"),
    },
    {
        "plane_index": 7,
        "plane_id": "7.communication_plane",
        "name": "Communication Plane",
        "capability_prefixes": ("email.", "calendar.", "voice.", "messaging.", "phone."),
        "capability_ids": ("enterprise.notification_send",),
        "boundary": "channel, email, calendar, voice, messaging, and phone adapters produce governed intent and approved sends",
        "evidence_refs": (
            "gateway.channels",
            "gateway.email_calendar_worker",
            "gateway.voice_worker",
            "gateway.messaging_worker",
            "gateway.phone_worker",
        ),
    },
    {
        "plane_index": 8,
        "plane_id": "8.financial_effect_plane",
        "name": "Financial / Effect Plane",
        "capability_prefixes": ("financial.",),
        "capability_ids": (),
        "boundary": "budget, approval, idempotency, settlement, ledger, receipt, and compensation gates",
        "evidence_refs": ("finance_approval_packet_proof", "effect_assurance", "terminal_closure_certificate"),
    },
    {
        "plane_index": 9,
        "plane_id": "9.mcp_external_tool_plane",
        "name": "MCP External Tool Plane",
        "capability_prefixes": ("connector.",),
        "capability_ids": ("github.open_pull_request",),
        "boundary": "external tools enter only through manifest validation, owner binding, and authority gates",
        "evidence_refs": ("examples/mcp_capability_manifest.json", "mcp_operator_read_model"),
    },
    {
        "plane_index": 10,
        "plane_id": "10.scheduling_workflow_plane",
        "name": "Scheduling / Workflow Plane",
        "capability_prefixes": (),
        "capability_ids": (
            "calendar.conflict_check",
            "calendar.schedule",
            "calendar.reschedule",
            "calendar.invite",
            "enterprise.task_schedule",
        ),
        "boundary": "temporal scheduling and workflow activation remain approval and lease governed",
        "evidence_refs": ("temporal_scheduler", "workflow_mining", "enterprise.task_schedule"),
    },
    {
        "plane_index": 11,
        "plane_id": "11.observation_verification_plane",
        "name": "Observation / Verification Plane",
        "capability_prefixes": (),
        "capability_ids": ("deployment.witness.collect", "computer.filesystem.observe"),
        "boundary": "observed effects, verification results, claim checks, and closure certificates precede response",
        "evidence_refs": ("claim_verification", "effect_assurance", "proof_verification_endpoint"),
    },
    {
        "plane_index": 12,
        "plane_id": "12.deployment_witness_plane",
        "name": "Deployment Witness Plane",
        "capability_prefixes": ("deployment.",),
        "capability_ids": (),
        "boundary": "published deployment claims require signed runtime witness and conformance evidence",
        "evidence_refs": ("deployment_witness", "runtime_conformance_certificate"),
    },
)


class MaturityProjectingCapabilityAdmissionGate(CommandCapabilityAdmissionGate):
    """Admission gate that adds derived maturity to registry read models."""

    def __init__(
        self,
        *,
        registry: GovernedCapabilityRegistry,
        clock: Callable[[], str],
        maturity_projector: CapabilityRegistryMaturityProjector | None = None,
        require_production_ready: bool = False,
        capability_manifest_registry_read_model: dict | None = None,
    ) -> None:
        super().__init__(registry=registry, clock=clock)
        self._maturity_projector = maturity_projector or CapabilityRegistryMaturityProjector()
        self._require_production_ready = require_production_ready
        self._capability_manifest_registry_read_model = capability_manifest_registry_read_model

    def admit(self, *, command_id: str, intent_name: str) -> CommandCapabilityAdmissionDecision:
        """Reject non-production-ready capabilities when certification closure is required."""
        decision = super().admit(command_id=command_id, intent_name=intent_name)
        if decision.status is not CommandCapabilityAdmissionStatus.ACCEPTED:
            return decision
        manifest_decision = self._admit_manifest(decision)
        if manifest_decision.status is not CommandCapabilityAdmissionStatus.ACCEPTED:
            return manifest_decision
        if not self._require_production_ready:
            return decision

        capability = self.capability_for_intent(intent_name)
        assessment = self._maturity_projector.assess_entry(capability)
        if assessment.production_ready:
            return decision
        return CommandCapabilityAdmissionDecision(
            command_id=decision.command_id,
            intent_name=decision.intent_name,
            status=CommandCapabilityAdmissionStatus.REJECTED,
            capability_id=decision.capability_id,
            domain=decision.domain,
            owner_team=decision.owner_team,
            evidence_required=decision.evidence_required,
            reason="capability is not production-ready: " + ",".join(assessment.blockers),
            decided_at=decision.decided_at,
        )

    def _admit_manifest(
        self,
        decision: CommandCapabilityAdmissionDecision,
    ) -> CommandCapabilityAdmissionDecision:
        if self._capability_manifest_registry_read_model is None:
            return decision
        manifest_capability_ids = _manifest_registry_capability_ids(
            self._capability_manifest_registry_read_model
        )
        if decision.capability_id in manifest_capability_ids:
            return decision
        return CommandCapabilityAdmissionDecision(
            command_id=decision.command_id,
            intent_name=decision.intent_name,
            status=CommandCapabilityAdmissionStatus.REJECTED,
            capability_id=decision.capability_id,
            domain=decision.domain,
            owner_team=decision.owner_team,
            evidence_required=decision.evidence_required,
            reason="capability manifest is not admitted for typed intent",
            decided_at=decision.decided_at,
        )

    def read_model(self) -> dict:
        """Return registry read model decorated with C0-C7 maturity evidence."""
        decorated = self._maturity_projector.decorate_read_model(super().read_model())
        general_agent_planes = _project_general_agent_planes(decorated)
        manifest_registry = self._capability_manifest_registry_read_model
        manifest_coverage = _project_manifest_coverage(decorated, manifest_registry)
        return {
            **decorated,
            "general_agent_plane_count": len(general_agent_planes),
            "general_agent_execution_order": tuple(
                plane["plane_id"] for plane in general_agent_planes
            ),
            "general_agent_planes": general_agent_planes,
            "require_production_ready": self._require_production_ready,
            "capability_manifest_registry_configured": manifest_registry is not None,
            "capability_manifest_registry": manifest_registry
            if manifest_registry is not None
            else _empty_capability_manifest_registry_read_model(),
            "capability_manifest_gated": manifest_registry is not None,
            "capability_manifest_coverage_status": manifest_coverage["coverage_status"],
            "capability_manifest_covered_count": len(manifest_coverage["covered_capability_ids"]),
            "capability_manifest_missing_count": len(manifest_coverage["missing_capability_ids"]),
            "capability_manifest_covered_capability_ids": manifest_coverage["covered_capability_ids"],
            "capability_manifest_missing_capability_ids": manifest_coverage["missing_capability_ids"],
            "capability_manifest_coverage": manifest_coverage["coverage_records"],
        }


def build_capability_admission_gate_from_env(
    *,
    clock: Callable[[], str],
) -> CommandCapabilityAdmissionGate | None:
    """Build a gateway capability admission gate from environment configuration."""
    if not _truthy(os.environ.get("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "")):
        return None

    capsule_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPSULE_PATH", "").strip()
    capsule_pack_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPSULE_PACK_PATH", "").strip()
    capability_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPABILITY_PATH", "").strip()
    capability_pack_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPABILITY_PACK_PATH", "").strip()
    use_default_packs = _truthy(os.environ.get("MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS", ""))
    if (
        not use_default_packs
        and (not (capsule_path or capsule_pack_path) or not (capability_path or capability_pack_path))
    ):
        raise ValueError("fabric admission requires capsule JSON source and capability JSON source")

    require_certified = not _falsey(os.environ.get("MULLU_CAPABILITY_FABRIC_REQUIRE_CERTIFIED", "true"))
    require_production_ready = _env_require_production_ready()
    capsules = _load_capsule_sources(capsule_path=capsule_path, capsule_pack_path=capsule_pack_path)
    loaded_capabilities = _load_capability_sources(
        capability_path=capability_path,
        capability_pack_path=capability_pack_path,
    )
    if use_default_packs:
        capsules = (*capsules, *load_default_domain_capsules())
        loaded_capabilities = (*loaded_capabilities, *load_default_capability_entries())
    capability_manifest_registry_read_model = _load_capability_manifest_registry_read_model_from_env(
        clock=clock,
    )

    return build_capability_admission_gate(
        capsules=capsules,
        capabilities=loaded_capabilities,
        require_certified=require_certified,
        require_production_ready=require_production_ready,
        capability_manifest_registry_read_model=capability_manifest_registry_read_model,
        clock=clock,
    )


def load_default_domain_capsules() -> tuple[DomainCapsule, ...]:
    """Load checked-in domain capsules for the built-in general domains."""
    return tuple(DomainCapsule.from_mapping(_load_object(path)) for path in _DEFAULT_CAPSULE_PATHS)


def load_default_capability_entries() -> tuple[CapabilityRegistryEntry, ...]:
    """Load checked-in capability entries for the built-in general domains."""
    entries: list[CapabilityRegistryEntry] = []
    for path in _DEFAULT_CAPABILITY_PACK_PATHS:
        entries.extend(_load_capability_pack(path))
    return tuple(entries)


def build_default_capability_admission_gate(
    *,
    clock: Callable[[], str],
    require_certified: bool = True,
    require_production_ready: bool = False,
) -> CommandCapabilityAdmissionGate:
    """Build a capability admission gate from checked-in general-domain packs."""
    return build_capability_admission_gate(
        capsules=load_default_domain_capsules(),
        capabilities=load_default_capability_entries(),
        require_certified=require_certified,
        require_production_ready=require_production_ready,
        clock=clock,
    )


def load_software_dev_domain_capsule() -> DomainCapsule:
    """Load the explicit software-development capsule fixture."""
    return DomainCapsule.from_mapping(_load_object(_SOFTWARE_DEV_CAPSULE_PATH))


def load_software_dev_capability_entries() -> tuple[CapabilityRegistryEntry, ...]:
    """Load explicit software-development capability entries."""
    return tuple(_load_capability_pack(_SOFTWARE_DEV_CAPABILITY_PACK_PATH))


def build_software_dev_capability_admission_gate(
    *,
    clock: Callable[[], str],
    require_certified: bool = True,
    require_production_ready: bool = False,
    manifest_environment: str | None = None,
    manifest_hot_reload: bool = False,
    manifest_dir: Path | str | None = None,
) -> CommandCapabilityAdmissionGate:
    """Build an admission gate for only the software-development capsule."""
    capability_manifest_registry_read_model = None
    if manifest_environment is not None:
        capability_manifest_registry_read_model = build_software_dev_capability_manifest_registry(
            clock=clock,
            environment=manifest_environment,
            hot_reload=manifest_hot_reload,
            manifest_dir=manifest_dir,
        ).read_model()
    return build_capability_admission_gate(
        capsules=(load_software_dev_domain_capsule(),),
        capabilities=load_software_dev_capability_entries(),
        require_certified=require_certified,
        require_production_ready=require_production_ready,
        capability_manifest_registry_read_model=capability_manifest_registry_read_model,
        clock=clock,
    )


def load_universal_domain_ops_domain_capsule() -> DomainCapsule:
    """Load the explicit Universal Domain Operating Pack capsule."""
    return DomainCapsule.from_mapping(_load_object(_UNIVERSAL_DOMAIN_OPS_CAPSULE_PATH))


def load_universal_domain_ops_capability_entries() -> tuple[CapabilityRegistryEntry, ...]:
    """Load explicit Universal Domain Operating Pack capability entries."""
    return tuple(_load_capability_pack(_UNIVERSAL_DOMAIN_OPS_CAPABILITY_PACK_PATH))


def build_universal_domain_ops_capability_admission_gate(
    *,
    clock: Callable[[], str],
    require_certified: bool = True,
    require_production_ready: bool = False,
) -> CommandCapabilityAdmissionGate:
    """Build an admission gate for only the Universal Domain Operating Pack capsule."""
    return build_capability_admission_gate(
        capsules=(load_universal_domain_ops_domain_capsule(),),
        capabilities=load_universal_domain_ops_capability_entries(),
        require_certified=require_certified,
        require_production_ready=require_production_ready,
        clock=clock,
    )


def load_agentic_control_domain_capsule() -> DomainCapsule:
    """Load the explicit agentic-control capsule."""
    return DomainCapsule.from_mapping(_load_object(_AGENTIC_CONTROL_CAPSULE_PATH))


def load_agentic_control_capability_entries() -> tuple[CapabilityRegistryEntry, ...]:
    """Load explicit agentic-control capability entries."""
    return tuple(_load_capability_pack(_AGENTIC_CONTROL_CAPABILITY_PACK_PATH))


def build_agentic_control_capability_admission_gate(
    *,
    clock: Callable[[], str],
    require_certified: bool = True,
    require_production_ready: bool = False,
) -> CommandCapabilityAdmissionGate:
    """Build an admission gate for only the agentic-control capsule."""
    return build_capability_admission_gate(
        capsules=(load_agentic_control_domain_capsule(),),
        capabilities=load_agentic_control_capability_entries(),
        require_certified=require_certified,
        require_production_ready=require_production_ready,
        clock=clock,
    )


def build_software_dev_capability_manifest_registry(
    *,
    clock: Callable[[], str],
    environment: str = "local",
    hot_reload: bool = False,
    manifest_dir: Path | str | None = None,
) -> CapabilityManifestRegistry:
    """Admit software-development capability manifests for a bounded environment."""
    registry = CapabilityManifestRegistry(repo_root=_REPO_ROOT, clock=clock)
    directory = _resolve_capability_manifest_directory(manifest_dir)
    if not directory.is_dir():
        raise ValueError(f"capability manifest directory not found: {directory}")
    admissions = registry.admit_directory(directory, environment=environment, hot_reload=hot_reload)
    if not admissions:
        raise ValueError(f"capability manifest directory contains no manifests: {directory}")
    rejected = tuple(
        admission
        for admission in admissions
        if admission.status is CapabilityManifestAdmissionStatus.REJECTED
    )
    if rejected:
        details = "; ".join(
            f"{admission.source_ref}:{','.join(admission.errors)}"
            for admission in rejected
        )
        raise ValueError(f"capability manifest admission failed: {details}")
    return registry


def build_capability_admission_gate(
    *,
    capsules: tuple[DomainCapsule, ...],
    capabilities: tuple[CapabilityRegistryEntry, ...],
    require_certified: bool,
    require_production_ready: bool = False,
    capability_manifest_registry_read_model: dict | None = None,
    clock: Callable[[], str],
) -> CommandCapabilityAdmissionGate:
    """Install capsules and capabilities into a command admission gate."""
    compiler = DomainCapsuleCompiler(clock=clock)
    registry = GovernedCapabilityRegistry(clock=clock, require_certified=require_certified)
    for capsule in capsules:
        referenced_capabilities = _capabilities_referenced_by_capsule(capsule, capabilities)
        compilation = compiler.compile(capsule, referenced_capabilities)
        if not compilation.succeeded:
            raise ValueError(f"fabric capsule compilation failed for {capsule.capsule_id}: {list(compilation.errors)}")
        installation = registry.install(compilation, referenced_capabilities)
        if installation.errors:
            raise ValueError(f"fabric capsule installation failed for {capsule.capsule_id}: {list(installation.errors)}")
    return MaturityProjectingCapabilityAdmissionGate(
        registry=registry,
        clock=clock,
        require_production_ready=require_production_ready,
        capability_manifest_registry_read_model=capability_manifest_registry_read_model,
    )


def _load_object(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"fabric JSON root must be an object: {path}")
    return payload


def _load_capability_manifest_registry_read_model_from_env(
    *,
    clock: Callable[[], str],
) -> dict | None:
    if not _truthy(os.environ.get("MULLU_CAPABILITY_FABRIC_MANIFEST_REGISTRY_ENABLED", "")):
        return None
    environment = os.environ.get("MULLU_CAPABILITY_FABRIC_MANIFEST_ENVIRONMENT", "").strip()
    if not environment:
        environment = os.environ.get("MULLU_ENV", "").strip().lower() or "local"
    manifest_dir = os.environ.get("MULLU_CAPABILITY_FABRIC_MANIFEST_DIR", "").strip()
    registry = build_software_dev_capability_manifest_registry(
        clock=clock,
        environment=environment,
        hot_reload=_truthy(os.environ.get("MULLU_CAPABILITY_FABRIC_MANIFEST_HOT_RELOAD", "")),
        manifest_dir=manifest_dir or None,
    )
    return registry.read_model()


def _empty_capability_manifest_registry_read_model() -> dict:
    return {
        "manifest_count": 0,
        "admission_count": 0,
        "capability_ids": (),
        "manifests": (),
        "admissions": (),
        "capability_abi_coverage_status": "empty",
        "capability_abi_covered_count": 0,
        "capability_abi_blocked_count": 0,
        "capability_abi_coverage": (),
    }


def _manifest_registry_capability_ids(read_model: dict | None) -> frozenset[str]:
    if read_model is None:
        return frozenset()
    raw_ids = read_model.get("capability_ids", ())
    if not isinstance(raw_ids, (tuple, list)):
        return frozenset()
    return frozenset(str(capability_id) for capability_id in raw_ids if str(capability_id).strip())


def _project_manifest_coverage(
    registry_read_model: dict,
    manifest_read_model: dict | None,
) -> dict[str, object]:
    installed_ids = tuple(
        str(capability.get("capability_id", ""))
        for capability in registry_read_model.get("capabilities", ())
        if isinstance(capability, dict) and str(capability.get("capability_id", "")).strip()
    )
    if manifest_read_model is None:
        return {
            "coverage_status": "not_configured",
            "covered_capability_ids": (),
            "missing_capability_ids": (),
            "coverage_records": (),
        }
    manifest_ids = _manifest_registry_capability_ids(manifest_read_model)
    covered_ids = tuple(sorted(set(installed_ids).intersection(manifest_ids)))
    missing_ids = tuple(sorted(set(installed_ids).difference(manifest_ids)))
    coverage_records = _manifest_coverage_records(
        installed_ids=tuple(sorted(set(installed_ids))),
        manifest_read_model=manifest_read_model,
        manifest_ids=manifest_ids,
    )
    return {
        "coverage_status": _manifest_coverage_status(coverage_records),
        "covered_capability_ids": covered_ids,
        "missing_capability_ids": missing_ids,
        "coverage_records": coverage_records,
    }


def _manifest_coverage_records(
    *,
    installed_ids: tuple[str, ...],
    manifest_read_model: dict,
    manifest_ids: frozenset[str],
) -> tuple[dict, ...]:
    abi_records_by_capability = _capability_abi_records_by_id(manifest_read_model)
    records: list[dict] = []
    for capability_id in installed_ids:
        record = abi_records_by_capability.get(capability_id)
        if capability_id in manifest_ids:
            records.append(_covered_manifest_coverage_record(capability_id, record))
        else:
            records.append(_missing_manifest_coverage_record(capability_id, record))
    return tuple(records)


def _capability_abi_records_by_id(manifest_read_model: dict) -> dict[str, dict]:
    records_by_id: dict[str, dict] = {}
    raw_records = manifest_read_model.get("capability_abi_coverage", ())
    if isinstance(raw_records, (tuple, list)):
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            capability_id = str(item.get("capability_id", "")).strip()
            if capability_id:
                records_by_id[capability_id] = item
    if records_by_id:
        return records_by_id

    for manifest in manifest_read_model.get("manifests", ()):
        if not isinstance(manifest, dict):
            continue
        capability_id = str(manifest.get("capability_id", "")).strip()
        if not capability_id:
            continue
        records_by_id[capability_id] = {
            "capability_id": capability_id,
            "source_ref": "capability-manifest-registry",
            "admission_status": "admitted",
            "coverage_status": "covered",
            "reason": "manifest_admitted",
            "maturity": str(manifest.get("maturity", "unknown")),
            "risk": str(manifest.get("risk", "unknown")),
            "effect_bearing": manifest.get("effect_bearing") is True,
            "sandbox_required": manifest.get("sandbox_required") is True,
            "rollback_required": manifest.get("rollback_required") is True,
            "evidence_refs": _read_model_text_tuple(manifest.get("evidence_refs", ())),
            "errors": (),
            "warnings": (),
        }
    return records_by_id


def _covered_manifest_coverage_record(capability_id: str, record: dict | None) -> dict:
    source = record or {}
    return {
        "capability_id": capability_id,
        "coverage_status": "covered",
        "manifest_admitted": True,
        "reason": str(source.get("reason", "manifest_admitted")),
        "source_ref": str(source.get("source_ref", "capability-manifest-registry")),
        "maturity": str(source.get("maturity", "unknown")),
        "risk": str(source.get("risk", "unknown")),
        "effect_bearing": source.get("effect_bearing") is True,
        "sandbox_required": source.get("sandbox_required") is True,
        "rollback_required": source.get("rollback_required") is True,
        "evidence_refs": _read_model_text_tuple(source.get("evidence_refs", ())),
        "errors": _read_model_text_tuple(source.get("errors", ())),
    }


def _missing_manifest_coverage_record(capability_id: str, record: dict | None) -> dict:
    source = record or {}
    blocked = str(source.get("coverage_status", "")) == "blocked"
    return {
        "capability_id": capability_id,
        "coverage_status": "blocked" if blocked else "missing_manifest",
        "manifest_admitted": False,
        "reason": str(source.get("reason", "capability manifest is not admitted for typed intent")),
        "source_ref": str(source.get("source_ref", "capability-manifest-registry")),
        "maturity": str(source.get("maturity", "unknown")),
        "risk": str(source.get("risk", "unknown")),
        "effect_bearing": source.get("effect_bearing") is True,
        "sandbox_required": source.get("sandbox_required") is True,
        "rollback_required": source.get("rollback_required") is True,
        "evidence_refs": _read_model_text_tuple(source.get("evidence_refs", ())),
        "errors": _read_model_text_tuple(source.get("errors", ())),
    }


def _manifest_coverage_status(records: tuple[dict, ...]) -> str:
    if not records:
        return "empty"
    statuses = {str(record.get("coverage_status", "")) for record in records}
    if statuses == {"covered"}:
        return "complete"
    if "covered" in statuses:
        return "partial"
    if "blocked" in statuses:
        return "blocked"
    if "missing_manifest" in statuses:
        return "missing"
    return "unknown"


def _read_model_text_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _resolve_capability_manifest_directory(manifest_dir: Path | str | None) -> Path:
    if manifest_dir is None:
        return _SOFTWARE_DEV_CAPABILITY_MANIFEST_DIR.resolve()
    candidate = Path(manifest_dir)
    if not candidate.is_absolute():
        candidate = _REPO_ROOT / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(_REPO_ROOT)
    except ValueError as exc:
        raise ValueError("capability manifest directory must stay inside repository") from exc
    return resolved


def _load_capsule_sources(*, capsule_path: str, capsule_pack_path: str) -> tuple[DomainCapsule, ...]:
    capsules: list[DomainCapsule] = []
    if capsule_path:
        capsules.append(DomainCapsule.from_mapping(_load_object(Path(capsule_path))))
    if capsule_pack_path:
        capsules.extend(_load_capsule_pack(Path(capsule_pack_path)))
    return tuple(capsules)


def _load_capsule_pack(path: Path) -> tuple[DomainCapsule, ...]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        raw_capsules = payload.get("capsules")
    elif isinstance(payload, list):
        raw_capsules = payload
    else:
        raise ValueError(f"fabric capsule pack root must be an object or array: {path}")
    if not isinstance(raw_capsules, list):
        raise ValueError(f"fabric capsule pack must contain a capsules array: {path}")
    capsules: list[DomainCapsule] = []
    for index, raw_capsule in enumerate(raw_capsules):
        if not isinstance(raw_capsule, dict):
            raise ValueError(f"fabric capsule pack entry must be an object: {path} capsules[{index}]")
        capsules.append(DomainCapsule.from_mapping(raw_capsule))
    return tuple(capsules)


def _load_capability_sources(
    *,
    capability_path: str,
    capability_pack_path: str,
) -> tuple[CapabilityRegistryEntry, ...]:
    entries: list[CapabilityRegistryEntry] = []
    if capability_path:
        entries.append(CapabilityRegistryEntry.from_mapping(_load_object(Path(capability_path))))
    if capability_pack_path:
        entries.extend(_load_capability_pack(Path(capability_pack_path)))
    return tuple(entries)


def _load_capability_pack(path: Path) -> tuple[CapabilityRegistryEntry, ...]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        raw_capabilities = payload.get("capabilities")
    elif isinstance(payload, list):
        raw_capabilities = payload
    else:
        raise ValueError(f"fabric capability pack root must be an object or array: {path}")
    if not isinstance(raw_capabilities, list):
        raise ValueError(f"fabric capability pack must contain a capabilities array: {path}")
    entries: list[CapabilityRegistryEntry] = []
    for index, raw_capability in enumerate(raw_capabilities):
        if not isinstance(raw_capability, dict):
            raise ValueError(f"fabric capability pack entry must be an object: {path} capabilities[{index}]")
        entries.append(CapabilityRegistryEntry.from_mapping(raw_capability))
    return tuple(entries)


def _capabilities_referenced_by_capsule(
    capsule: DomainCapsule,
    entries: tuple[CapabilityRegistryEntry, ...],
) -> tuple[CapabilityRegistryEntry, ...]:
    by_id: dict[str, CapabilityRegistryEntry] = {}
    duplicates: list[str] = []
    for entry in entries:
        if entry.capability_id in by_id:
            duplicates.append(entry.capability_id)
        by_id[entry.capability_id] = entry
    if duplicates:
        raise ValueError(f"fabric capability source contains duplicate capability ids: {duplicates}")

    missing = [capability_id for capability_id in capsule.capability_refs if capability_id not in by_id]
    if missing:
        raise ValueError(f"fabric capsule references missing capabilities: {missing}")
    return tuple(by_id[capability_id] for capability_id in capsule.capability_refs)


def _project_general_agent_planes(read_model: dict) -> tuple[dict, ...]:
    """Project governed capabilities onto the required general-agent planes."""
    records_by_capability = {
        str(record["capability_id"]): record
        for record in read_model.get("governed_capability_records", ())
        if isinstance(record, dict) and record.get("capability_id")
    }
    all_capability_ids = tuple(sorted(records_by_capability))
    planes: list[dict] = []
    for definition in _GENERAL_AGENT_PLAN_DEFINITIONS:
        capability_ids = _plane_capability_ids(
            definition=definition,
            all_capability_ids=all_capability_ids,
        )
        governed_records = tuple(
            records_by_capability[capability_id]
            for capability_id in capability_ids
            if capability_id in records_by_capability
        )
        planes.append(
            {
                "plane_index": definition["plane_index"],
                "plane_id": definition["plane_id"],
                "name": definition["name"],
                "boundary": definition["boundary"],
                "capability_ids": capability_ids,
                "governed_record_count": len(governed_records),
                "read_only_count": sum(1 for record in governed_records if record.get("read_only") is True),
                "world_mutating_count": sum(1 for record in governed_records if record.get("world_mutating") is True),
                "requires_approval_count": sum(1 for record in governed_records if record.get("requires_approval") is True),
                "requires_sandbox_count": sum(1 for record in governed_records if record.get("requires_sandbox") is True),
                "risk_levels": tuple(sorted({str(record.get("risk_level", "")) for record in governed_records})),
                "max_cost": round(sum(float(record.get("max_cost", 0.0)) for record in governed_records), 6),
                "evidence_refs": tuple(definition["evidence_refs"]),
            }
        )
    return tuple(planes)


def _plane_capability_ids(
    *,
    definition: dict,
    all_capability_ids: tuple[str, ...],
) -> tuple[str, ...]:
    prefixes = tuple(str(prefix) for prefix in definition.get("capability_prefixes", ()))
    explicit_ids = {str(capability_id) for capability_id in definition.get("capability_ids", ())}
    return tuple(
        capability_id
        for capability_id in all_capability_ids
        if capability_id in explicit_ids or any(capability_id.startswith(prefix) for prefix in prefixes)
    )


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _falsey(value: str) -> bool:
    return value.strip().lower() in {"0", "false", "no", "off"}


def _env_require_production_ready() -> bool:
    configured = os.environ.get("MULLU_CAPABILITY_FABRIC_REQUIRE_PRODUCTION_READY", "").strip()
    if configured:
        return _truthy(configured)
    return os.environ.get("MULLU_ENV", "").strip().lower() == "production"
