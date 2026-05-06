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
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    CommandCapabilityAdmissionDecision,
    CommandCapabilityAdmissionStatus,
    DomainCapsule,
)
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.domain_capsule_compiler import DomainCapsuleCompiler
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry


_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CAPSULE_PATHS = (
    _REPO_ROOT / "capsules" / "browser.json",
    _REPO_ROOT / "capsules" / "communication.json",
    _REPO_ROOT / "capsules" / "connector.json",
    _REPO_ROOT / "capsules" / "creative.json",
    _REPO_ROOT / "capsules" / "deployment.json",
    _REPO_ROOT / "capsules" / "document.json",
    _REPO_ROOT / "capsules" / "enterprise.json",
    _REPO_ROOT / "capsules" / "financial.json",
    _REPO_ROOT / "capsules" / "computer.json",
    _REPO_ROOT / "capsules" / "voice.json",
)
_DEFAULT_CAPABILITY_PACK_PATHS = (
    _REPO_ROOT / "capabilities" / "browser" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "communication" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "connector" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "creative" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "deployment" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "document" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "enterprise" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "financial" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "computer" / "capability_pack.json",
    _REPO_ROOT / "capabilities" / "voice" / "capability_pack.json",
)
_GENERAL_AGENT_PLAN_DEFINITIONS = (
    {
        "plane_index": 0,
        "plane_id": "0.governance_core",
        "name": "Governance Core",
        "capability_prefixes": (),
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
        "capability_prefixes": ("email.", "calendar.", "voice."),
        "capability_ids": ("enterprise.notification_send",),
        "boundary": "channel, email, calendar, and voice adapters produce governed intent and approved sends",
        "evidence_refs": ("gateway.channels", "gateway.email_calendar_worker", "gateway.voice_worker"),
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
        "capability_ids": (),
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
    ) -> None:
        super().__init__(registry=registry, clock=clock)
        self._maturity_projector = maturity_projector or CapabilityRegistryMaturityProjector()
        self._require_production_ready = require_production_ready

    def admit(self, *, command_id: str, intent_name: str) -> CommandCapabilityAdmissionDecision:
        """Reject non-production-ready capabilities when certification closure is required."""
        decision = super().admit(command_id=command_id, intent_name=intent_name)
        if decision.status is not CommandCapabilityAdmissionStatus.ACCEPTED:
            return decision
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

    def read_model(self) -> dict:
        """Return registry read model decorated with C0-C7 maturity evidence."""
        decorated = self._maturity_projector.decorate_read_model(super().read_model())
        general_agent_planes = _project_general_agent_planes(decorated)
        return {
            **decorated,
            "general_agent_plane_count": len(general_agent_planes),
            "general_agent_execution_order": tuple(
                plane["plane_id"] for plane in general_agent_planes
            ),
            "general_agent_planes": general_agent_planes,
            "require_production_ready": self._require_production_ready,
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

    return build_capability_admission_gate(
        capsules=capsules,
        capabilities=loaded_capabilities,
        require_certified=require_certified,
        require_production_ready=require_production_ready,
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


def build_capability_admission_gate(
    *,
    capsules: tuple[DomainCapsule, ...],
    capabilities: tuple[CapabilityRegistryEntry, ...],
    require_certified: bool,
    require_production_ready: bool = False,
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
    )


def _load_object(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"fabric JSON root must be an object: {path}")
    return payload


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
