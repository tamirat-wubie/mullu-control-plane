"""Tests for the Personal Assistant capability-pack runtime index.

Purpose: prove capability-pack loading is deterministic, no-effect, and bound
to local skill registry references.
Governance scope: candidate-only admission, non-production posture, secret and
network denial, mutation denial, and local skill capability binding.
Dependencies: mcoi_runtime.personal_assistant capability-pack runtime and the
foundation Personal Assistant fixtures.
Invariants:
  - Capability pack runtime loading never executes live connectors.
  - Pack entries remain fixture-only, secretless, networkless, and non-mutating.
  - Local personal_assistant.* skill refs must bind to capability-pack entries.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantCapabilityPackIndex,
    PersonalAssistantInvariantError,
    PersonalAssistantSkillRegistry,
    load_default_personal_assistant_capability_pack,
    load_default_skill_registry,
)


ROOT = Path(__file__).resolve().parent.parent
CAPABILITY_PACK_PATH = ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
REGISTRY_PATH = ROOT / "examples" / "personal_assistant_skill_registry.json"


def test_default_capability_pack_loads_no_effect_entries() -> None:
    index = load_default_personal_assistant_capability_pack()
    capability_ids = index.capability_ids()
    receipt_entry = index.get("personal_assistant.receipt.project")

    assert index.count == 12
    assert capability_ids == tuple(sorted(capability_ids))
    assert "personal_assistant.intent.interpret" in capability_ids
    assert "personal_assistant.planning.schedule_preview" in capability_ids
    assert receipt_entry.secret_scope == "none"
    assert receipt_entry.world_mutating is False
    assert receipt_entry.receipt_required is True


def test_capability_pack_read_model_preserves_foundation_boundary() -> None:
    read_model = load_default_personal_assistant_capability_pack().read_model()

    assert read_model["capability_count"] == 12
    assert read_model["candidate_only"] is True
    assert read_model["fixture_only"] is True
    assert read_model["production_ready"] is False
    assert read_model["networkless"] is True
    assert read_model["secretless"] is True
    assert read_model["non_mutating"] is True
    assert read_model["receipt_required"] is True
    assert read_model["verification_required"] is True


def test_skill_registry_local_refs_bind_to_capability_pack() -> None:
    registry = load_default_skill_registry()
    pack = load_default_personal_assistant_capability_pack()
    report = pack.bind_skill_registry(registry)

    assert report.valid is True
    assert report.missing_local_capability_refs == ()
    assert "personal_assistant.receipt.project" in report.local_capability_refs
    assert "personal_assistant.clarification.request" in report.local_capability_refs
    assert "email.read" in report.external_capability_refs
    assert "software_dev.repo_map.read" in report.external_capability_refs
    assert "email.inbox.summarize" in report.bound_skill_ids
    assert "deployment.publish.review" in report.bound_skill_ids


def test_unbound_local_skill_capability_ref_fails_closed() -> None:
    registry_payload = _load_json(REGISTRY_PATH)
    _skill_by_id(registry_payload, "email.inbox.summarize")["capability_refs"].append(
        "personal_assistant.unregistered.local_ref"
    )
    registry = PersonalAssistantSkillRegistry.from_mapping(registry_payload)
    report = load_default_personal_assistant_capability_pack().bind_skill_registry(registry)

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        report.assert_valid()

    assert report.valid is False
    assert report.missing_local_capability_refs == ("personal_assistant.unregistered.local_ref",)
    assert "unbound local capability refs" in str(exc_info.value)


def test_capability_pack_rejects_production_secret_network_and_mutation_authority() -> None:
    pack_payload = _load_json(CAPABILITY_PACK_PATH)
    mutated_entry = deepcopy(pack_payload["capabilities"][0])
    mutated_entry["metadata"]["production_ready"] = True
    mutated_entry["isolation_profile"]["secret_scope"] = "gmail"
    mutated_entry["isolation_profile"]["network_allowlist"] = ["gmail.googleapis.com"]
    mutated_entry["extensions"]["governed_record"]["world_mutating"] = True
    pack_payload["capabilities"][0] = mutated_entry

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        PersonalAssistantCapabilityPackIndex.from_mapping(pack_payload)

    message = str(exc_info.value)
    assert "capabilities[0]" in message
    assert "production_ready must be false" in message
    assert "secret_scope" not in message


def test_duplicate_capability_id_is_rejected() -> None:
    pack_payload = _load_json(CAPABILITY_PACK_PATH)
    pack_payload["capabilities"].append(deepcopy(pack_payload["capabilities"][0]))

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        PersonalAssistantCapabilityPackIndex.from_mapping(pack_payload)

    assert "duplicate capability_id" in str(exc_info.value)
    assert "personal_assistant.intent.interpret" in str(exc_info.value)
    assert len(pack_payload["capabilities"]) == 13


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_by_id(registry_payload: dict, skill_id: str) -> dict:
    for skill in registry_payload["skills"]:
        if skill["skill_id"] == skill_id:
            return skill
    raise AssertionError(f"missing skill {skill_id}")
