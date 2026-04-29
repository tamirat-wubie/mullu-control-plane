"""Purpose: validate gateway capability fabric loader configuration paths.
Governance scope: environment-gated capability fabric admission and checked-in
    default capsule/capability pack installation.
Dependencies: gateway capability fabric loader and governed capability registry.
Invariants:
  - Fabric admission remains disabled unless explicitly enabled.
  - Enabled admission requires explicit sources unless default packs are requested.
  - Checked-in default packs install all certified creative and enterprise entries.
"""

from __future__ import annotations

import os

import pytest

from gateway.capability_fabric import (
    build_capability_admission_gate_from_env,
    build_default_capability_admission_gate,
    load_default_capability_entries,
    load_default_domain_capsules,
)


def _clock() -> str:
    return "2026-04-29T12:00:00+00:00"


@pytest.fixture(autouse=True)
def _clear_fabric_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(os.environ):
        if key.startswith("MULLU_CAPABILITY_FABRIC_"):
            monkeypatch.delenv(key, raising=False)


def test_capability_fabric_env_loader_stays_disabled_without_enable_flag() -> None:
    gate = build_capability_admission_gate_from_env(clock=_clock)

    assert gate is None
    assert load_default_domain_capsules()[0].capsule_id == "creative.productivity.v0"
    assert load_default_capability_entries()[0].capability_id == "creative.document_generate"


def test_capability_fabric_env_loader_requires_source_without_default_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")

    with pytest.raises(ValueError, match="requires capsule JSON source and capability JSON source"):
        build_capability_admission_gate_from_env(clock=_clock)

    assert "MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS" not in os.environ
    assert "MULLU_CAPABILITY_FABRIC_CAPSULE_PATH" not in os.environ
    assert "MULLU_CAPABILITY_FABRIC_CAPABILITY_PATH" not in os.environ


def test_capability_fabric_env_loader_installs_checked_in_default_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS", "true")

    gate = build_capability_admission_gate_from_env(clock=_clock)

    assert gate is not None
    read_model = gate.read_model()
    assert read_model["capsule_count"] == 2
    assert read_model["capability_count"] == 6
    assert {domain["domain"] for domain in read_model["domains"]} == {"creative", "enterprise"}


def test_default_capability_admission_gate_accepts_pack_capabilities() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)

    creative_decision = gate.admit(command_id="command-1", intent_name="creative.translate")
    enterprise_decision = gate.admit(command_id="command-2", intent_name="enterprise.task_schedule")
    rejected_decision = gate.admit(command_id="command-3", intent_name="gateway.unknown")

    assert creative_decision.status.value == "accepted"
    assert creative_decision.capability_id == "creative.translate"
    assert enterprise_decision.status.value == "accepted"
    assert enterprise_decision.owner_team == "enterprise-ops"
    assert rejected_decision.status.value == "rejected"
    assert rejected_decision.capability_id == ""
