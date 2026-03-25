"""Phase 141 — Flagship Dominance Tests."""
import pytest
from mcoi_runtime.pilot.flagship_strategy import (
    FLAGSHIP, FLAGSHIP_PACK, FLAGSHIP_NAME, FLAGSHIP_ROADMAP,
    ReferenceAccount, ReferenceProgram,
    EXPANSION_PLAYBOOKS, INCUBATION_PACKS,
    FlagshipActionDashboard,
)

class TestFlagshipFocus:
    def test_flagship_is_regulated_ops(self):
        assert FLAGSHIP_PACK == "regulated_ops"
        assert FLAGSHIP.pack_domain == "regulated_ops"

    def test_investment_priority(self):
        assert FLAGSHIP.investment_priority == "maximum"

    def test_engineering_focus_areas(self):
        assert len(FLAGSHIP.engineering_focus) == 7
        assert "evidence_workflow_improvements" in FLAGSHIP.engineering_focus

class TestReferenceProgram:
    def test_add_accounts(self):
        prog = ReferenceProgram()
        prog.add_account(ReferenceAccount("a1", "BigBank", "finance", "2026-01-15", 15, "VP Compliance"))
        prog.add_account(ReferenceAccount("a2", "MegaCorp", "insurance", "2026-02-01", 20, "Chief Audit"))
        assert prog.total == 2

    def test_reference_ready(self):
        prog = ReferenceProgram()
        prog.add_account(ReferenceAccount("a1", "BigBank", "finance", "2026-01-15", 15, "VP", roi_captured=True, reference_willing=True, maturity="champion"))
        prog.add_account(ReferenceAccount("a2", "SmallCo", "retail", "2026-03-01", 5, "Mgr", roi_captured=False, maturity="early"))
        assert len(prog.reference_ready_accounts()) == 1

    def test_summary(self):
        prog = ReferenceProgram()
        prog.add_account(ReferenceAccount("a1", "A", "fin", "2026-01", 10, "VP", roi_captured=True, case_study_published=True, reference_willing=True, maturity="champion"))
        prog.add_account(ReferenceAccount("a2", "B", "ins", "2026-02", 8, "Dir", roi_captured=True, maturity="mature"))
        prog.add_account(ReferenceAccount("a3", "C", "hc", "2026-03", 12, "VP", maturity="growing"))
        s = prog.summary()
        assert s["total_accounts"] == 3
        assert s["champions"] == 1
        assert s["roi_captured"] == 2
        assert s["case_studies"] == 1

class TestExpansionPlaybooks:
    def test_3_playbooks(self):
        assert len(EXPANSION_PLAYBOOKS) == 3

    def test_regulated_to_financial(self):
        pb = EXPANSION_PLAYBOOKS["regulated_to_financial"]
        assert pb["land"] == "regulated_ops"
        assert pb["expand_to"] == "financial_control"
        assert pb["expected_acv_increase"] >= 1.5

    def test_factory_to_supply_chain(self):
        pb = EXPANSION_PLAYBOOKS["factory_to_supply_chain"]
        assert pb["expected_acv_increase"] == 2.0

class TestIncubation:
    def test_research_incubated(self):
        assert "research_lab" in INCUBATION_PACKS
        assert INCUBATION_PACKS["research_lab"]["status"] == "incubated"

    def test_blocked_activities(self):
        blocked = INCUBATION_PACKS["research_lab"]["blocked_activities"]
        assert "major_gtm_push" in blocked

class TestActionDashboard:
    def test_dashboard_generation(self):
        prog = ReferenceProgram()
        prog.add_account(ReferenceAccount("a1", "A", "fin", "2026-01", 10, "VP", roi_captured=True, case_study_published=True, reference_willing=True, maturity="champion"))
        prog.add_account(ReferenceAccount("a2", "B", "ins", "2026-02", 8, "Dir", maturity="growing"))
        prog.add_account(ReferenceAccount("a3", "C", "hc", "2026-03", 12, "VP", maturity="early"))

        dash = FlagshipActionDashboard(prog)
        d = dash.generate()
        assert d["flagship"]["pack"] == "regulated_ops"
        assert d["references"]["total_accounts"] == 3
        assert d["expansion_playbooks"] == 3
        assert "research_lab" in d["incubation"]
        assert len(d["action_items"]) >= 3

class TestGoldenProof:
    def test_flagship_dominance_lifecycle(self):
        # 1. Flagship is regulated ops
        assert FLAGSHIP_PACK == "regulated_ops"

        # 2. Reference program with 5 accounts
        prog = ReferenceProgram()
        accounts = [
            ReferenceAccount("ref1", "Alpha Financial", "finance", "2025-10", 20, "CCO", True, True, True, "champion"),
            ReferenceAccount("ref2", "Beta Insurance", "insurance", "2025-12", 15, "VP Audit", True, True, True, "mature"),
            ReferenceAccount("ref3", "Gamma Health", "healthcare", "2026-01", 12, "CISO", True, False, True, "mature"),
            ReferenceAccount("ref4", "Delta Energy", "energy", "2026-02", 18, "VP Compliance", False, False, False, "growing"),
            ReferenceAccount("ref5", "Epsilon Gov", "government", "2026-03", 8, "Director", False, False, False, "early"),
        ]
        for a in accounts:
            prog.add_account(a)

        assert prog.total == 5
        assert len(prog.reference_ready_accounts()) == 3  # champion + 2 mature with roi+willing

        # 3. Roadmap focused on flagship value
        assert len(FLAGSHIP_ROADMAP) == 7
        assert FLAGSHIP_ROADMAP[0]["area"] == "evidence"

        # 4. Expansion playbooks defined
        assert "regulated_to_financial" in EXPANSION_PLAYBOOKS
        assert "factory_to_supply_chain" in EXPANSION_PLAYBOOKS

        # 5. Research incubated, not killed
        assert INCUBATION_PACKS["research_lab"]["status"] == "incubated"

        # 6. Executive dashboard actionable
        dash = FlagshipActionDashboard(prog)
        d = dash.generate()
        assert d["flagship"]["name"] == FLAGSHIP_NAME
        assert d["references"]["champions"] == 1
        assert d["references"]["reference_ready"] == 3
