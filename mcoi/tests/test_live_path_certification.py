"""Phase 199C — Live-path certification tests.

Tests: CertificationStep, CertificationChain, RestartProof, LivePathCertifier
    with full integration through API → DB → LLM → Ledger → Restart.
"""

import hashlib
import json
import pytest

from mcoi_runtime.core.live_path_certification import (
    CertificationChain,
    CertificationStatus,
    CertificationStep,
    LivePathCertifier,
    RestartProof,
)
from mcoi_runtime.contracts.llm import LLMBudget, LLMProvider, LLMResult
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.persistence.postgres_store import InMemoryStore


FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


# ═══ Contract Tests ═══

class TestCertificationStep:
    def test_valid_step(self):
        step = CertificationStep(
            step_id="s1", name="test", status=CertificationStatus.PASSED, proof_hash="abc"
        )
        assert step.step_id == "s1"
        assert step.status == CertificationStatus.PASSED

    def test_empty_step_id_rejected(self):
        with pytest.raises(ValueError):
            CertificationStep(step_id="", name="test", status=CertificationStatus.PASSED, proof_hash="abc")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            CertificationStep(step_id="s1", name="", status=CertificationStatus.PASSED, proof_hash="abc")

    def test_frozen(self):
        step = CertificationStep(step_id="s1", name="t", status=CertificationStatus.PASSED, proof_hash="h")
        with pytest.raises(AttributeError):
            step.status = CertificationStatus.FAILED

    def test_all_statuses(self):
        for status in CertificationStatus:
            step = CertificationStep(step_id="s", name="t", status=status, proof_hash="h")
            assert step.status == status


class TestCertificationChain:
    def test_valid_chain(self):
        steps = (CertificationStep("s1", "t", CertificationStatus.PASSED, "h"),)
        chain = CertificationChain(
            chain_id="c1", steps=steps, chain_hash="ch", certified_at="2026-01-01", all_passed=True
        )
        assert chain.chain_id == "c1"
        assert chain.all_passed is True
        assert len(chain.steps) == 1

    def test_empty_chain_id_rejected(self):
        with pytest.raises(ValueError):
            CertificationChain(chain_id="", steps=(), chain_hash="h", certified_at="t", all_passed=True)


class TestRestartProof:
    def test_valid_proof(self):
        proof = RestartProof(
            proof_id="r1", pre_restart_hash="a", post_restart_hash="b",
            entries_before=5, entries_after=5, state_preserved=True
        )
        assert proof.state_preserved is True

    def test_empty_proof_id_rejected(self):
        with pytest.raises(ValueError):
            RestartProof(proof_id="", pre_restart_hash="a", post_restart_hash="b",
                         entries_before=0, entries_after=0, state_preserved=True)


# ═══ Individual Step Certifications ═══

class TestCertifyAPIBoundary:
    def test_passed_with_handler(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_api_boundary(
            handle_fn=lambda req: {"status": "ok", "governed": True}
        )
        assert step.status == CertificationStatus.PASSED
        assert step.proof_hash
        assert "api_boundary" in step.name

    def test_passed_without_handler(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_api_boundary()
        assert step.status == CertificationStatus.PASSED

    def test_failed_on_exception(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_api_boundary(
            handle_fn=lambda req: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        assert step.status == CertificationStatus.FAILED
        assert "boom" in step.detail


class TestCertifyDBPersistence:
    def test_passed_with_store(self):
        store = InMemoryStore()
        certifier = LivePathCertifier(clock=FIXED_CLOCK)

        def write_fn(tenant_id, content):
            return store.append_ledger("cert", "certifier", tenant_id, content,
                                       hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest())

        def read_fn(tenant_id):
            return store.query_ledger(tenant_id)

        step = certifier.certify_db_persistence(write_fn=write_fn, read_fn=read_fn)
        assert step.status == CertificationStatus.PASSED
        assert step.proof_hash
        assert store.ledger_count() >= 1

    def test_skipped_without_functions(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_db_persistence()
        assert step.status == CertificationStatus.SKIPPED

    def test_failed_on_read_mismatch(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_db_persistence(
            write_fn=lambda t, c: 1,
            read_fn=lambda t: [],  # Empty — won't find the entry
        )
        assert step.status == CertificationStatus.FAILED


class TestCertifyLLMInvocation:
    def test_passed_with_stub(self):
        bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_llm_invocation(
            invoke_fn=lambda prompt: bridge.complete(prompt)
        )
        assert step.status == CertificationStatus.PASSED
        assert step.proof_hash

    def test_skipped_without_fn(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_llm_invocation()
        assert step.status == CertificationStatus.SKIPPED

    def test_failed_on_error(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_llm_invocation(
            invoke_fn=lambda prompt: (_ for _ in ()).throw(RuntimeError("llm down"))
        )
        assert step.status == CertificationStatus.FAILED
        assert "llm down" in step.detail


class TestCertifyLedgerIntegrity:
    def test_passed_with_valid_entries(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        entries = [
            {"hash": "abc123", "type": "test"},
            {"hash": "def456", "type": "test"},
        ]
        step = certifier.certify_ledger_integrity(ledger_entries=entries)
        assert step.status == CertificationStatus.PASSED
        assert step.proof_hash

    def test_failed_with_missing_hash(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        entries = [
            {"hash": "abc123"},
            {"hash": ""},  # Empty hash
        ]
        step = certifier.certify_ledger_integrity(ledger_entries=entries)
        assert step.status == CertificationStatus.FAILED

    def test_skipped_without_entries(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_ledger_integrity()
        assert step.status == CertificationStatus.SKIPPED

    def test_skipped_with_empty_list(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step = certifier.certify_ledger_integrity(ledger_entries=[])
        assert step.status == CertificationStatus.SKIPPED


class TestCertifyRestartProof:
    def test_passed_with_preserved_state(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step, proof = certifier.certify_restart_proof(
            pre_state_fn=lambda: ("hash-pre", 5),
            restart_fn=lambda: None,
            post_state_fn=lambda: ("hash-post", 5),
        )
        assert step.status == CertificationStatus.PASSED
        assert proof is not None
        assert proof.state_preserved is True
        assert proof.entries_before == 5
        assert proof.entries_after == 5

    def test_failed_on_state_loss(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step, proof = certifier.certify_restart_proof(
            pre_state_fn=lambda: ("hash-pre", 5),
            restart_fn=lambda: None,
            post_state_fn=lambda: ("hash-post", 3),  # Lost entries
        )
        assert step.status == CertificationStatus.FAILED
        assert proof is not None
        assert proof.state_preserved is False

    def test_skipped_without_functions(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step, proof = certifier.certify_restart_proof()
        assert step.status == CertificationStatus.SKIPPED
        assert proof is None

    def test_no_restart_fn_still_works(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        step, proof = certifier.certify_restart_proof(
            pre_state_fn=lambda: ("h", 3),
            post_state_fn=lambda: ("h", 3),
        )
        assert step.status == CertificationStatus.PASSED


# ═══ Full Certification ═══

class TestFullCertification:
    def _setup_full(self):
        """Set up all components for a full certification run."""
        store = InMemoryStore()
        bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
        bridge.register_budget(LLMBudget(budget_id="cert-budget", tenant_id="cert-tenant", max_cost=10.0))
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        return store, bridge, certifier

    def test_all_passed(self):
        store, bridge, certifier = self._setup_full()

        # Pre-populate some ledger entries
        store.append_ledger("init", "system", "cert-tenant", {"init": True},
                            hashlib.sha256(b"init").hexdigest())

        chain = certifier.run_full_certification(
            api_handle_fn=lambda req: {"status": "ok"},
            db_write_fn=lambda t, c: store.append_ledger("cert", "certifier", t, c,
                                                          hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()),
            db_read_fn=lambda t: store.query_ledger(t),
            llm_invoke_fn=lambda prompt: bridge.complete(prompt, budget_id="cert-budget"),
            ledger_entries=store.query_ledger("cert-tenant"),
            pre_state_fn=lambda: (hashlib.sha256(b"state").hexdigest(), store.ledger_count()),
            restart_fn=lambda: None,
            post_state_fn=lambda: (hashlib.sha256(b"state").hexdigest(), store.ledger_count()),
        )

        assert chain.all_passed is True
        assert len(chain.steps) == 5
        assert chain.chain_hash
        assert chain.chain_id
        assert certifier.chain_count == 1

    def test_partial_failure(self):
        store, bridge, certifier = self._setup_full()

        chain = certifier.run_full_certification(
            api_handle_fn=lambda req: (_ for _ in ()).throw(RuntimeError("api down")),
            db_write_fn=lambda t, c: store.append_ledger("cert", "certifier", t, c,
                                                          hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()),
            db_read_fn=lambda t: store.query_ledger(t),
        )

        assert chain.all_passed is False
        api_step = chain.steps[0]
        assert api_step.status == CertificationStatus.FAILED

    def test_all_skipped(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        chain = certifier.run_full_certification()
        # API passes without handler, rest are skipped
        assert len(chain.steps) == 5
        assert chain.all_passed is True  # Passed and skipped both count

    def test_chain_hash_deterministic(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        c1 = certifier.run_full_certification()
        c2 = certifier.run_full_certification()
        assert c1.chain_hash == c2.chain_hash

    def test_certification_history(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        certifier.run_full_certification()
        certifier.run_full_certification()
        history = certifier.certification_history()
        assert len(history) == 2
        assert all(h["steps"] == 5 for h in history)


# ═══ End-to-End Integration ═══

class TestEndToEndCertification:
    """Full integration: InMemoryStore + LLMIntegrationBridge + LivePathCertifier."""

    def test_complete_live_path(self):
        store = InMemoryStore()
        bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
        bridge.register_budget(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0))
        certifier = LivePathCertifier(clock=FIXED_CLOCK)

        # Step 1: Write initial state through store
        store.append_ledger("boot", "system", "t1", {"boot": True},
                            hashlib.sha256(b"boot").hexdigest())

        # Step 2: Make an LLM call through the bridge
        llm_result = bridge.complete("test prompt", budget_id="b1", tenant_id="t1")
        assert llm_result.succeeded is True

        # Step 3: Record LLM invocation to store
        store.save_llm_invocation(
            invocation_id="e2e-inv-1",
            model_name=llm_result.model_name,
            provider=llm_result.provider.value,
            input_tokens=llm_result.input_tokens,
            output_tokens=llm_result.output_tokens,
            cost=llm_result.cost,
            succeeded=llm_result.succeeded,
            budget_id="b1",
            tenant_id="t1",
        )

        # Step 4: Run full certification
        chain = certifier.run_full_certification(
            api_handle_fn=lambda req: {"governed": True},
            db_write_fn=lambda t, c: store.append_ledger("cert", "certifier", t, c,
                                                          hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()),
            db_read_fn=lambda t: store.query_ledger(t),
            llm_invoke_fn=lambda prompt: bridge.complete(prompt, budget_id="b1", tenant_id="t1"),
            ledger_entries=store.query_ledger("t1"),
            pre_state_fn=lambda: (hashlib.sha256(str(store.ledger_count()).encode()).hexdigest(), store.ledger_count()),
            post_state_fn=lambda: (hashlib.sha256(str(store.ledger_count()).encode()).hexdigest(), store.ledger_count()),
        )

        assert chain.all_passed is True
        assert certifier.chain_count == 1

        # Verify all stores have data
        assert store.ledger_count() >= 2
        assert store.llm_invocation_count() >= 1
        assert bridge.invocation_count >= 2  # 1 direct + 1 certification
        assert bridge.total_cost > 0

    def test_budget_exhaustion_during_certification(self):
        """Certification still reports results even if LLM budget is exhausted."""
        store = InMemoryStore()
        bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
        bridge.register_budget(LLMBudget(budget_id="tiny", tenant_id="t1", max_cost=0.0001, max_calls=1))
        certifier = LivePathCertifier(clock=FIXED_CLOCK)

        # Exhaust the budget
        bridge.complete("exhaust", budget_id="tiny", tenant_id="t1")

        # Certification should report LLM step as failed
        chain = certifier.run_full_certification(
            llm_invoke_fn=lambda prompt: bridge.complete(prompt, budget_id="tiny", tenant_id="t1"),
        )

        llm_step = next(s for s in chain.steps if s.name == "llm_invocation")
        assert llm_step.status == CertificationStatus.FAILED
        assert chain.all_passed is False
