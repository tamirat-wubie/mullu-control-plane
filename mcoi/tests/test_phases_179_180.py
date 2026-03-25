"""Phases 179-180 — Scientific Domain Extension Tests."""
import pytest
from mcoi_runtime.pilot.scientific_domains import (
    CHEMISTRY_CAPABILITIES, CHEMISTRY_PROFILE, BIOLOGY_CAPABILITIES, BIOLOGY_PROFILE,
    SCIENTIFIC_DOMAIN_ROADMAP, scientific_expansion_summary,
)

class TestChemistry:
    def test_10_capabilities(self):
        assert len(CHEMISTRY_CAPABILITIES) == 10
    def test_profile_uses_existing_runtimes(self):
        assert "research_runtime" in CHEMISTRY_PROFILE.uses_runtimes
        assert "factory_runtime" in CHEMISTRY_PROFILE.uses_runtimes
    def test_profile_uses_intelligence(self):
        assert "ontology_runtime" in CHEMISTRY_PROFILE.uses_intelligence
    def test_target_industries(self):
        assert len(CHEMISTRY_PROFILE.target_industries) >= 4

class TestBiology:
    def test_10_capabilities(self):
        assert len(BIOLOGY_CAPABILITIES) == 10
    def test_profile_uses_existing_runtimes(self):
        assert "research_runtime" in BIOLOGY_PROFILE.uses_runtimes
        assert "healthcare_runtime" in BIOLOGY_PROFILE.uses_runtimes
    def test_profile_uses_intelligence(self):
        assert "epistemic_runtime" in BIOLOGY_PROFILE.uses_intelligence
    def test_target_industries(self):
        assert len(BIOLOGY_PROFILE.target_industries) >= 4

class TestRoadmap:
    def test_2_domains(self):
        assert len(SCIENTIFIC_DOMAIN_ROADMAP) == 2
    def test_prerequisites_ready(self):
        for v in SCIENTIFIC_DOMAIN_ROADMAP.values():
            assert v["prerequisite_packs_ready"]

class TestSummary:
    def test_expansion_summary(self):
        s = scientific_expansion_summary()
        assert s["domains_planned"] == 2
        assert s["total_new_capabilities"] == 20
        assert s["all_prerequisites_ready"]
        assert s["total_estimated_phases"] == 7
