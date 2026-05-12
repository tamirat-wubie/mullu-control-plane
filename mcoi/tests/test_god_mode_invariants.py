"""Cross-capability invariants for the god-mode subsystem.

Mirrors the platform's `test_domain_adapter_invariants.py` pattern: rather
than checking each capability in isolation, this enforces structural rules
that must hold across every shipped proposal. Drift in one capability
(e.g. a catastrophic action with a 50-char justification floor) is caught
before it ships.
"""
from __future__ import annotations

import re

from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityBlastRadius,
)
from mcoi_runtime.core.god_mode_integration import default_capability_proposals


PROPOSALS: tuple[GodCapability, ...] = default_capability_proposals()


# --- Coverage ----------------------------------------------------------------


REQUIRED_MODULES = frozenset(
    {
        "data",
        "rbac",
        "governance",
        "temporal_scheduler",
        "constructs",
        "policy",
        "replay",
        "secrets",
        "mfidel",
        "mil_audit",
    }
)


def test_every_required_module_has_at_least_one_capability():
    modules_with_caps = {p.module for p in PROPOSALS}
    missing = REQUIRED_MODULES - modules_with_caps
    assert not missing, f"required modules without a god capability: {sorted(missing)}"


def test_capability_keys_are_unique():
    keys = [p.key for p in PROPOSALS]
    assert len(keys) == len(set(keys)), "duplicate (module, name) capability keys"


# --- Blast-radius proportionality -------------------------------------------


def test_catastrophic_caps_have_strict_justification_floor():
    for cap in PROPOSALS:
        if cap.blast_radius == GodCapabilityBlastRadius.CATASTROPHIC:
            assert cap.min_justification_chars >= 120, (
                f"{cap.fqn}: catastrophic capability must require ≥120 chars of "
                f"justification (got {cap.min_justification_chars})"
            )


def test_catastrophic_caps_have_short_ttl():
    for cap in PROPOSALS:
        if cap.blast_radius == GodCapabilityBlastRadius.CATASTROPHIC:
            assert cap.default_ttl_seconds <= 120, (
                f"{cap.fqn}: catastrophic capability TTL must be ≤120s "
                f"(got {cap.default_ttl_seconds})"
            )


def test_catastrophic_caps_are_one_shot():
    for cap in PROPOSALS:
        if cap.blast_radius == GodCapabilityBlastRadius.CATASTROPHIC:
            assert cap.one_shot, f"{cap.fqn}: catastrophic capability must be one-shot"


def test_catastrophic_caps_are_not_session_scoped():
    for cap in PROPOSALS:
        if cap.blast_radius == GodCapabilityBlastRadius.CATASTROPHIC:
            assert not cap.requires_session, (
                f"{cap.fqn}: catastrophic capability must not be session-scoped"
            )


def test_catastrophic_caps_require_dual_control():
    """Two-person rule: catastrophic ops must require ≥2 distinct registrants."""
    for cap in PROPOSALS:
        if cap.blast_radius == GodCapabilityBlastRadius.CATASTROPHIC:
            assert cap.requires_dual_control, (
                f"{cap.fqn}: catastrophic capability must require dual control"
            )
            assert cap.dual_control_min_actors >= 2


def test_secrets_capabilities_use_strictest_floor():
    """Anything that can reveal secrets carries the 200-char floor."""
    for cap in PROPOSALS:
        if cap.module == "secrets" or "secret" in cap.fqn.lower():
            assert cap.min_justification_chars >= 200, (
                f"{cap.fqn}: secret-revealing capability must require ≥200 chars"
            )


# --- Bypass-label hygiene ---------------------------------------------------


_BYPASS_LABEL_RE = re.compile(r"^[a-z][a-z0-9_]+$")


def test_bypasses_are_lowercase_snake_case():
    for cap in PROPOSALS:
        for label in cap.bypasses:
            assert _BYPASS_LABEL_RE.match(label), (
                f"{cap.fqn}: bypass label {label!r} must be lowercase snake_case"
            )


def test_bypasses_are_unique_within_capability():
    for cap in PROPOSALS:
        assert len(cap.bypasses) == len(set(cap.bypasses)), (
            f"{cap.fqn}: duplicate bypass labels"
        )


def test_every_capability_declares_at_least_one_bypass():
    """A god capability that bypasses nothing is a configuration error."""
    for cap in PROPOSALS:
        assert cap.bypasses, f"{cap.fqn}: must declare at least one bypass"


# --- Naming ----------------------------------------------------------------


_NAME_RE = re.compile(r"^[a-z][a-z0-9_]+$")


def test_capability_names_are_snake_case():
    for cap in PROPOSALS:
        assert _NAME_RE.match(cap.name), (
            f"{cap.fqn}: capability name must be lowercase snake_case"
        )


def test_module_names_are_snake_case():
    for cap in PROPOSALS:
        assert _NAME_RE.match(cap.module), (
            f"{cap.fqn}: module name must be lowercase snake_case"
        )


# --- Description quality ---------------------------------------------------


def test_descriptions_are_substantive():
    """Catalog browsers see the description first; a one-word stub is unsafe."""
    for cap in PROPOSALS:
        assert len(cap.description) >= 30, (
            f"{cap.fqn}: description too short ({len(cap.description)} chars)"
        )


def test_descriptions_dont_mention_god_mode_meta():
    """Descriptions describe the capability, not the registration mechanics."""
    forbidden = ("registration agreement", "activation agreement", "dormant")
    for cap in PROPOSALS:
        lowered = cap.description.lower()
        for term in forbidden:
            assert term not in lowered, (
                f"{cap.fqn}: description must not reference god-mode meta term {term!r}"
            )


# --- TTL bounds -------------------------------------------------------------


def test_ttl_within_subsystem_bounds():
    for cap in PROPOSALS:
        assert 5 <= cap.default_ttl_seconds <= 3600, (
            f"{cap.fqn}: ttl must be within [5, 3600] seconds"
        )


def test_min_justification_within_bounds():
    for cap in PROPOSALS:
        assert 50 <= cap.min_justification_chars <= 2000, (
            f"{cap.fqn}: min_justification_chars must be within [50, 2000]"
        )


# --- Suite-wide health ------------------------------------------------------


def test_proposal_count_matches_documented_minimum():
    """Tripwire: if we drop below 14 capabilities the platform memory is stale."""
    assert len(PROPOSALS) >= 14
