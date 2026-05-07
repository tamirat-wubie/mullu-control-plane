"""Tier 3 coordination constructs."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.substrate.constructs import (
    Coupling,
    Emergence,
    Equilibrium,
    Resonance,
    Synchronization,
    TIER3_RESPONSIBILITIES,
    Tier,
    verify_tier3_disambiguation,
)


def test_tier3_disambiguation():
    verify_tier3_disambiguation()
    assert len(set(TIER3_RESPONSIBILITIES.values())) == 5


# ---- Coupling ----


def test_coupling_basic():
    a, b = uuid4(), uuid4()
    c = Coupling(source_id=a, target_id=b, strength=0.5, coupling_type="bidirectional")
    assert c.tier == Tier.COORDINATION
    assert c.coupling_type == "bidirectional"


def test_coupling_rejects_self_coupling():
    a = uuid4()
    with pytest.raises(ValueError, match="self-coupling"):
        Coupling(source_id=a, target_id=a)


def test_coupling_requires_both_endpoints():
    with pytest.raises(ValueError):
        Coupling(source_id=uuid4())
    with pytest.raises(ValueError):
        Coupling(target_id=uuid4())


def test_coupling_strength_bounds():
    with pytest.raises(ValueError):
        Coupling(source_id=uuid4(), target_id=uuid4(), strength=1.1)


def test_coupling_invalid_type():
    with pytest.raises(ValueError):
        Coupling(source_id=uuid4(), target_id=uuid4(), coupling_type="weird")


# ---- Synchronization ----


def test_synchronization_basic():
    p1, p2 = uuid4(), uuid4()
    s = Synchronization(
        pattern_ids=(p1, p2),
        frequency=60.0,
        drift_tolerance=0.5,
    )
    assert s.frequency == 60.0


def test_synchronization_requires_two_patterns():
    with pytest.raises(ValueError):
        Synchronization(pattern_ids=(uuid4(),))


def test_synchronization_rejects_duplicates():
    p = uuid4()
    with pytest.raises(ValueError, match="distinct"):
        Synchronization(pattern_ids=(p, p))


def test_synchronization_rejects_negative_drift():
    with pytest.raises(ValueError):
        Synchronization(
            pattern_ids=(uuid4(), uuid4()),
            drift_tolerance=-1.0,
        )


# ---- Resonance ----


def test_resonance_basic():
    r = Resonance(
        pattern_id=uuid4(),
        natural_frequency=440.0,
        amplitude=2.0,
        damping_factor=0.1,
        activation_threshold=0.5,
    )
    assert r.natural_frequency == 440.0


def test_resonance_requires_pattern():
    with pytest.raises(ValueError):
        Resonance()


def test_resonance_damping_bounds():
    with pytest.raises(ValueError):
        Resonance(pattern_id=uuid4(), damping_factor=1.5)


# ---- Equilibrium ----


def test_equilibrium_basic():
    a, b = uuid4(), uuid4()
    e = Equilibrium(
        attractor_state_ids=(a, b),
        perturbation_tolerance=0.3,
        stability_kind="metastable",
    )
    assert e.stability_kind == "metastable"


def test_equilibrium_requires_attractor():
    with pytest.raises(ValueError):
        Equilibrium()


def test_equilibrium_rejects_duplicate_attractors():
    a = uuid4()
    with pytest.raises(ValueError, match="distinct"):
        Equilibrium(attractor_state_ids=(a, a))


def test_equilibrium_invalid_stability_kind():
    with pytest.raises(ValueError):
        Equilibrium(
            attractor_state_ids=(uuid4(),),
            stability_kind="bouncy",
        )


# ---- Emergence ----


def test_emergence_basic():
    components = (uuid4(), uuid4(), uuid4())
    interactions = (uuid4(),)
    novel = uuid4()
    e = Emergence(
        component_ids=components,
        interaction_ids=interactions,
        novel_pattern_id=novel,
        irreducibility_evidence="components in isolation produce no flocking; together they do",
    )
    assert e.novel_pattern_id == novel


def test_emergence_requires_evidence():
    with pytest.raises(ValueError, match="irreducibility_evidence"):
        Emergence(
            component_ids=(uuid4(), uuid4()),
            interaction_ids=(uuid4(),),
            novel_pattern_id=uuid4(),
            irreducibility_evidence="",
        )


def test_emergence_requires_two_components():
    with pytest.raises(ValueError):
        Emergence(
            component_ids=(uuid4(),),
            interaction_ids=(uuid4(),),
            novel_pattern_id=uuid4(),
            irreducibility_evidence="evidence",
        )


def test_emergence_requires_interactions():
    with pytest.raises(ValueError):
        Emergence(
            component_ids=(uuid4(), uuid4()),
            interaction_ids=(),
            novel_pattern_id=uuid4(),
            irreducibility_evidence="evidence",
        )
