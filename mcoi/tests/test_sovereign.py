"""Phase 151 — Sovereign Deployment Track Tests."""
import pytest
from mcoi_runtime.pilot.sovereign import (
    SOVEREIGN_PROFILES, TRUST_BUNDLES, COMPLIANCE_ARTIFACTS,
    CONNECTOR_CLASSIFICATION, SOVEREIGN_PILOT_STEPS,
    SovereignPilotProgress,
)

class TestProfiles:
    def test_4_profiles(self):
        assert len(SOVEREIGN_PROFILES) == 4

    def test_sovereign_cloud_restricted(self):
        p = SOVEREIGN_PROFILES["sovereign_cloud"]
        assert p.export_restricted
        assert p.break_glass_policy == "dual_approval"

    def test_on_prem_customer_controlled(self):
        p = SOVEREIGN_PROFILES["on_prem"]
        assert p.update_path == "customer_controlled"
        assert p.support_path == "on_site"

    def test_all_have_residency(self):
        for p in SOVEREIGN_PROFILES.values():
            assert p.data_residency
            assert len(p.allowed_connectors) >= 3

class TestTrustBundles:
    def test_4_bundles(self):
        assert len(TRUST_BUNDLES) == 4

    def test_high_security(self):
        b = TRUST_BUNDLES["high_security"]
        assert b.identity_mode == "piv_cac"
        assert b.copilot_mode == "explain_only"
        assert b.approval_minimum == "unanimous"

    def test_classified_copilot_disabled(self):
        b = TRUST_BUNDLES["classified_adjacent"]
        assert b.copilot_mode == "disabled"

    def test_all_immutable_evidence(self):
        for b in TRUST_BUNDLES.values():
            assert b.evidence_immutability

class TestArtifacts:
    def test_6_artifacts(self):
        assert len(COMPLIANCE_ARTIFACTS) == 6

    def test_each_has_sections(self):
        for a in COMPLIANCE_ARTIFACTS.values():
            assert a["title"]
            assert len(a["sections"]) >= 4

class TestConnectors:
    def test_classification(self):
        assert len(CONNECTOR_CLASSIFICATION["allowed_default"]) == 3
        assert len(CONNECTOR_CLASSIFICATION["blocked_sovereign"]) >= 3

    def test_offline_alternatives(self):
        assert "ticketing" in CONNECTOR_CLASSIFICATION["offline_alternatives"]

class TestPilotPath:
    def test_10_steps(self):
        assert len(SOVEREIGN_PILOT_STEPS) == 10

    def test_progress(self):
        p = SovereignPilotProgress("t1", "sov-cloud", "trust-std-gov")
        for i in range(1, 6):
            p.complete_step(i)
        assert p.completion_rate == 0.5
        assert not p.is_ready

    def test_full_completion(self):
        p = SovereignPilotProgress("t1", "sov-cloud", "trust-std-gov")
        for i in range(1, 11):
            p.complete_step(i)
        assert p.is_ready
        assert p.next_step == "all_complete"

class TestGoldenProof:
    def test_sovereign_deployment_lifecycle(self):
        # 1. Select profile
        profile = SOVEREIGN_PROFILES["sovereign_cloud"]
        assert profile.deployment_model == "sovereign_cloud"

        # 2. Data residency enforced
        assert profile.data_residency == "local_sovereign"
        assert profile.export_restricted

        # 3. Restricted connectors
        assert "third_party_saas" in profile.blocked_connectors

        # 4. Trust bundle
        trust = TRUST_BUNDLES["standard_gov"]
        assert trust.evidence_immutability
        assert trust.copilot_mode == "restricted_no_generation"

        # 5. Compliance artifacts exist
        assert len(COMPLIANCE_ARTIFACTS) == 6

        # 6. Sovereign pilot path
        progress = SovereignPilotProgress("gov-tenant-1", "sov-cloud", "trust-std-gov")
        for i in range(1, 11):
            progress.complete_step(i)
        assert progress.is_ready

        # 7. No forked architecture
        assert profile.update_path == "managed"  # same platform, managed updates
