"""Purpose: typed Personal Assistant capability-pack runtime index.
Governance scope: no-effect capability-pack loading, pack-entry admission,
skill-to-capability binding, and read-model projection without execution.
Dependencies: JSON capability pack fixture and Personal Assistant skill
registry contracts.
Invariants:
  - Capability pack loading never executes connector, mailbox, calendar,
    deployment, memory, or external actions.
  - Admitted Personal Assistant capability entries are candidate-only,
    fixture-only, networkless, secretless, non-mutating, receipt-required,
    and verification-required.
  - Local personal_assistant.* skill capability references must bind to a
    capability-pack entry before a registry is considered aligned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import PersonalAssistantInvariantError


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CAPABILITY_PACK_PATH = REPO_ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
LOCAL_CAPABILITY_PREFIX = "personal_assistant."


@dataclass(frozen=True, slots=True)
class PersonalAssistantCapabilityPackEntry:
    """Admitted no-effect capability-pack entry for the foundation layer."""

    capability_id: str
    version: str
    input_schema_ref: str
    output_schema_ref: str
    expected_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    required_evidence: tuple[str, ...]
    certification_status: str
    secret_scope: str
    network_allowlist: tuple[str, ...]
    governed_allowed_tools: tuple[str, ...]
    governed_forbidden_effects: tuple[str, ...]
    fixture_only: bool
    production_ready: bool
    read_only: bool
    world_mutating: bool
    requires_approval: bool
    receipt_required: bool
    verification_required: bool

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "PersonalAssistantCapabilityPackEntry":
        """Build and validate a typed Personal Assistant capability entry."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("capability entry must be an object")
        if _require_text(payload, "domain") != "personal_assistant":
            raise PersonalAssistantInvariantError("capability entry domain must be personal_assistant")

        effect_model = _require_mapping(payload, "effect_model")
        evidence_model = _require_mapping(payload, "evidence_model")
        isolation_profile = _require_mapping(payload, "isolation_profile")
        metadata = _require_mapping(payload, "metadata")
        extensions = _require_mapping(payload, "extensions")
        governed_record = _require_mapping(extensions, "governed_record")

        entry = PersonalAssistantCapabilityPackEntry(
            capability_id=_require_text(payload, "capability_id"),
            version=_require_text(payload, "version"),
            input_schema_ref=_require_text(payload, "input_schema_ref"),
            output_schema_ref=_require_text(payload, "output_schema_ref"),
            expected_effects=_text_tuple(effect_model, "expected_effects"),
            forbidden_effects=_text_tuple(effect_model, "forbidden_effects"),
            required_evidence=_text_tuple(evidence_model, "required_evidence"),
            certification_status=_require_text(payload, "certification_status"),
            secret_scope=_require_text(isolation_profile, "secret_scope"),
            network_allowlist=_text_tuple(isolation_profile, "network_allowlist", allow_empty=True),
            governed_allowed_tools=_text_tuple(governed_record, "allowed_tools", allow_empty=True),
            governed_forbidden_effects=_text_tuple(governed_record, "forbidden_effects"),
            fixture_only=_require_bool(metadata, "fixture_only"),
            production_ready=_require_bool(metadata, "production_ready"),
            read_only=_require_bool(governed_record, "read_only"),
            world_mutating=_require_bool(governed_record, "world_mutating"),
            requires_approval=_require_bool(governed_record, "requires_approval"),
            receipt_required=_require_bool(governed_record, "receipt_required"),
            verification_required=_require_bool(governed_record, "verification_required"),
        )
        entry.assert_foundation_bound()
        return entry

    def assert_foundation_bound(self) -> None:
        """Validate no-effect foundation capability invariants."""
        if not self.capability_id.startswith(LOCAL_CAPABILITY_PREFIX):
            raise PersonalAssistantInvariantError(
                f"{self.capability_id}: capability_id must start with {LOCAL_CAPABILITY_PREFIX}"
            )
        if self.certification_status != "candidate":
            raise PersonalAssistantInvariantError(f"{self.capability_id}: certification_status must be candidate")
        if self.fixture_only is not True:
            raise PersonalAssistantInvariantError(f"{self.capability_id}: fixture_only must be true")
        if self.production_ready is not False:
            raise PersonalAssistantInvariantError(f"{self.capability_id}: production_ready must be false")
        if self.secret_scope != "none":
            raise PersonalAssistantInvariantError(f"{self.capability_id}: secret_scope must be none")
        if self.network_allowlist:
            raise PersonalAssistantInvariantError(f"{self.capability_id}: network_allowlist must be empty")
        if self.world_mutating:
            raise PersonalAssistantInvariantError(f"{self.capability_id}: world_mutating must be false")
        if self.receipt_required is not True:
            raise PersonalAssistantInvariantError(f"{self.capability_id}: receipt_required must be true")
        if self.verification_required is not True:
            raise PersonalAssistantInvariantError(f"{self.capability_id}: verification_required must be true")
        if not self.forbidden_effects:
            raise PersonalAssistantInvariantError(f"{self.capability_id}: forbidden_effects must not be empty")
        if not self.governed_forbidden_effects:
            raise PersonalAssistantInvariantError(
                f"{self.capability_id}: governed forbidden_effects must not be empty"
            )

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready capability read model."""
        return {
            "capability_id": self.capability_id,
            "version": self.version,
            "input_schema_ref": self.input_schema_ref,
            "output_schema_ref": self.output_schema_ref,
            "expected_effects": list(self.expected_effects),
            "forbidden_effects": list(self.forbidden_effects),
            "required_evidence": list(self.required_evidence),
            "certification_status": self.certification_status,
            "secret_scope": self.secret_scope,
            "network_allowlist": list(self.network_allowlist),
            "governed_allowed_tools": list(self.governed_allowed_tools),
            "governed_forbidden_effects": list(self.governed_forbidden_effects),
            "fixture_only": self.fixture_only,
            "production_ready": self.production_ready,
            "read_only": self.read_only,
            "world_mutating": self.world_mutating,
            "requires_approval": self.requires_approval,
            "receipt_required": self.receipt_required,
            "verification_required": self.verification_required,
        }


@dataclass(frozen=True, slots=True)
class PersonalAssistantSkillCapabilityBindingReport:
    """Deterministic report for skill registry to capability-pack alignment."""

    local_capability_refs: tuple[str, ...]
    external_capability_refs: tuple[str, ...]
    missing_local_capability_refs: tuple[str, ...]
    bound_skill_ids: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Return whether every local Personal Assistant capability ref is bound."""
        return not self.missing_local_capability_refs

    def assert_valid(self) -> None:
        """Fail closed when local capability refs are missing from the pack."""
        if self.missing_local_capability_refs:
            raise PersonalAssistantInvariantError(
                "personal assistant skill registry has unbound local capability refs: "
                f"{list(self.missing_local_capability_refs)}"
            )

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready alignment report."""
        return {
            "valid": self.valid,
            "local_capability_refs": list(self.local_capability_refs),
            "external_capability_refs": list(self.external_capability_refs),
            "missing_local_capability_refs": list(self.missing_local_capability_refs),
            "bound_skill_ids": list(self.bound_skill_ids),
        }


@dataclass(slots=True)
class PersonalAssistantCapabilityPackIndex:
    """In-memory no-effect index for Personal Assistant capability-pack entries."""

    _entries: dict[str, PersonalAssistantCapabilityPackEntry] = field(default_factory=dict)

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "PersonalAssistantCapabilityPackIndex":
        """Build a capability-pack index from a parsed JSON mapping."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("capability pack root must be an object")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, list):
            raise PersonalAssistantInvariantError("capability pack capabilities must be a list")

        index = PersonalAssistantCapabilityPackIndex()
        for offset, capability in enumerate(capabilities):
            try:
                entry = PersonalAssistantCapabilityPackEntry.from_mapping(capability)
            except PersonalAssistantInvariantError as exc:
                raise PersonalAssistantInvariantError(f"capabilities[{offset}]: {exc}") from exc
            index.register(entry)
        return index

    def register(self, entry: PersonalAssistantCapabilityPackEntry) -> None:
        """Register one admitted capability-pack entry."""
        if not isinstance(entry, PersonalAssistantCapabilityPackEntry):
            raise PersonalAssistantInvariantError("entry must be a PersonalAssistantCapabilityPackEntry")
        if entry.capability_id in self._entries:
            raise PersonalAssistantInvariantError(f"duplicate capability_id: {entry.capability_id}")
        self._entries[entry.capability_id] = entry

    def get(self, capability_id: str) -> PersonalAssistantCapabilityPackEntry:
        """Return one capability entry by id or fail with a causal error."""
        capability_id = _require_query_text(capability_id, "capability_id")
        try:
            return self._entries[capability_id]
        except KeyError as exc:
            raise PersonalAssistantInvariantError(f"unknown capability_id: {capability_id}") from exc

    def capability_ids(self) -> tuple[str, ...]:
        """Return admitted capability ids sorted lexicographically."""
        return tuple(sorted(self._entries))

    def all_entries(self) -> tuple[PersonalAssistantCapabilityPackEntry, ...]:
        """Return admitted capability entries sorted by capability id."""
        return tuple(self._entries[capability_id] for capability_id in self.capability_ids())

    def bind_skill_registry(self, registry: Any) -> PersonalAssistantSkillCapabilityBindingReport:
        """Return a no-effect alignment report for registry capability refs."""
        if not hasattr(registry, "all_skills"):
            raise PersonalAssistantInvariantError("registry must expose all_skills()")

        local_refs: set[str] = set()
        external_refs: set[str] = set()
        bound_skill_ids: set[str] = set()
        for skill in registry.all_skills():
            for capability_ref in skill.capability_refs:
                if capability_ref.startswith(LOCAL_CAPABILITY_PREFIX):
                    local_refs.add(capability_ref)
                    if capability_ref in self._entries:
                        bound_skill_ids.add(skill.skill_id)
                else:
                    external_refs.add(capability_ref)

        missing_local_refs = tuple(ref for ref in sorted(local_refs) if ref not in self._entries)
        return PersonalAssistantSkillCapabilityBindingReport(
            local_capability_refs=tuple(sorted(local_refs)),
            external_capability_refs=tuple(sorted(external_refs)),
            missing_local_capability_refs=missing_local_refs,
            bound_skill_ids=tuple(sorted(bound_skill_ids)),
        )

    def read_model(self) -> dict[str, Any]:
        """Return a deterministic operator-facing capability-pack read model."""
        entries = self.all_entries()
        return {
            "capability_count": len(entries),
            "capability_ids": [entry.capability_id for entry in entries],
            "candidate_only": all(entry.certification_status == "candidate" for entry in entries),
            "fixture_only": all(entry.fixture_only is True for entry in entries),
            "production_ready": any(entry.production_ready is True for entry in entries),
            "networkless": all(not entry.network_allowlist for entry in entries),
            "secretless": all(entry.secret_scope == "none" for entry in entries),
            "non_mutating": all(entry.world_mutating is False for entry in entries),
            "receipt_required": all(entry.receipt_required is True for entry in entries),
            "verification_required": all(entry.verification_required is True for entry in entries),
            "capabilities": [entry.as_dict() for entry in entries],
        }

    @property
    def count(self) -> int:
        """Return admitted capability count."""
        return len(self._entries)


def load_default_personal_assistant_capability_pack() -> PersonalAssistantCapabilityPackIndex:
    """Load the foundation Personal Assistant capability pack."""
    return load_personal_assistant_capability_pack(DEFAULT_CAPABILITY_PACK_PATH)


def load_personal_assistant_capability_pack(path: Path) -> PersonalAssistantCapabilityPackIndex:
    """Load and admit a Personal Assistant capability pack from JSON."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PersonalAssistantInvariantError(f"capability pack could not be read: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PersonalAssistantInvariantError(f"capability pack must be JSON: {path}") from exc
    return PersonalAssistantCapabilityPackIndex.from_mapping(payload)


def _require_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be an object")
    return value


def _require_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value


def _require_bool(payload: Mapping[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise PersonalAssistantInvariantError(f"{field_name} must be a boolean")
    return value


def _text_tuple(payload: Mapping[str, Any], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    values = payload.get(field_name)
    if not isinstance(values, list):
        raise PersonalAssistantInvariantError(f"{field_name} must be a list")
    normalized: list[str] = []
    for offset, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise PersonalAssistantInvariantError(f"{field_name}[{offset}] must be a non-empty string")
        normalized.append(value)
    if not normalized and not allow_empty:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    if len(normalized) != len(set(normalized)):
        raise PersonalAssistantInvariantError(f"{field_name} contains duplicate entries")
    return tuple(normalized)


def _require_query_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value
