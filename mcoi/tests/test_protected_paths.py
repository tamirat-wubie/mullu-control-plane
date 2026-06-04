"""Tests for the governed protected-path policy and its enforcement seams.

Covers (1) the pure ProtectedPathPolicy classifier and the default
governance set, and (2) the fail-closed CodeEngine.apply_patch_and_verify
gate that refuses to patch protected control-plane artifacts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.adapters.code_adapter import CommandPolicy, LocalCodeAdapter
from mcoi_runtime.contracts.code import PatchProposal, PatchStatus
from mcoi_runtime.contracts.software_dev_loop import (
    AttemptStatus,
    QualityGateResult,
    WorkPlan,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.code import CodeEngine
from mcoi_runtime.core.software_dev_loop import (
    UCJAOutcomeShape,
    governed_software_change,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkKind,
)
from mcoi_runtime.governance.protected_paths import (
    DEFAULT_GOVERNANCE_PROTECTED_PATHS,
    ProtectedPathMatch,
    ProtectedPathPolicy,
    ProtectedPathVerdict,
    default_governance_protected_paths,
)

T0 = "2025-01-15T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Pure policy classification
# ---------------------------------------------------------------------------


class TestProtectedPathPolicyPure:
    def test_empty_policy_protects_nothing(self):
        policy = ProtectedPathPolicy()
        assert policy.is_empty
        verdict = policy.classify(".github/workflows/ci.yml")
        assert verdict.protected is False
        assert verdict.match is ProtectedPathMatch.NONE

    def test_exact_file_match(self):
        policy = ProtectedPathPolicy(files=("AGENTS.md",))
        verdict = policy.classify("AGENTS.md")
        assert verdict.protected
        assert verdict.match is ProtectedPathMatch.EXACT_FILE
        assert verdict.matched_pattern == "AGENTS.md"
        # A different file is not protected.
        assert not policy.classify("README.md").protected

    def test_within_directory_match(self):
        policy = ProtectedPathPolicy(directories=(".github",))
        assert policy.classify(".github/workflows/ci.yml").protected
        assert policy.classify(".github").protected  # the directory itself
        # Prefix collision must NOT match (".githubfoo" is not under ".github").
        assert not policy.classify(".githubfoo/x.yml").protected

    def test_glob_matches_basename_at_any_depth(self):
        policy = ProtectedPathPolicy(globs=("id_rsa", "*.pem"))
        assert policy.classify("deploy/keys/id_rsa").protected
        assert policy.classify("certs/server.pem").protected
        assert not policy.classify("src/app.py").protected

    def test_absolute_and_traversal_are_failclosed(self):
        policy = ProtectedPathPolicy(files=("AGENTS.md",))
        for bad in ("../escape.py", "../../etc/passwd", "/etc/passwd", "C:/Windows/x"):
            verdict = policy.classify(bad)
            assert verdict.protected, bad
            assert verdict.match is ProtectedPathMatch.UNNORMALIZABLE, bad

    def test_empty_path_is_failclosed(self):
        verdict = ProtectedPathPolicy().classify("")
        assert verdict.protected
        assert verdict.match is ProtectedPathMatch.UNNORMALIZABLE

    def test_backslash_paths_are_normalized(self):
        policy = ProtectedPathPolicy(directories=(".github",))
        assert policy.classify(".github\\workflows\\ci.yml").protected

    def test_leading_dot_slash_normalized(self):
        policy = ProtectedPathPolicy(files=("schemas/x.json",), directories=("schemas",))
        assert policy.classify("./schemas/x.json").protected

    def test_ordinary_source_paths_not_protected(self):
        policy = default_governance_protected_paths()
        for ok in ("mcoi/mcoi_runtime/core/code.py", "src/lib.py", "main.py", "tests/test_x.py"):
            assert not policy.classify(ok).protected, ok

    def test_policy_normalizes_and_dedupes_inputs(self):
        policy = ProtectedPathPolicy(
            directories=(".github/", ".github", "schemas\\"),
            files=("AGENTS.md", "AGENTS.md"),
        )
        assert policy.directories == (".github", "schemas")
        assert policy.files == ("AGENTS.md",)

    def test_protected_in_filters_to_protected_only(self):
        policy = ProtectedPathPolicy(directories=("schemas",))
        verdicts = policy.protected_in(["schemas/a.json", "src/b.py", "schemas/c.json"])
        assert len(verdicts) == 2
        assert all(isinstance(v, ProtectedPathVerdict) and v.protected for v in verdicts)


class TestDefaultGovernancePolicy:
    @pytest.mark.parametrize(
        "protected_path",
        [
            "AGENTS.md",
            "CLAUDE.md",
            ".github/workflows/ci.yml",
            "schemas/proof.schema.json",
            "capabilities/computer/capability_pack.json",
            "mcoi/mcoi_runtime/governance/protected_paths.py",
            "receipts/2026/r1.json",
            "deploy/tls.pem",
            "config/app.env",
            "secrets.json",
        ],
    )
    def test_governance_artifacts_are_protected(self, protected_path: str):
        assert DEFAULT_GOVERNANCE_PROTECTED_PATHS.classify(protected_path).protected

    @pytest.mark.parametrize(
        "ordinary_path",
        ["main.py", "src/app.py", "mcoi/mcoi_runtime/core/code.py", "docs/guide.md"],
    )
    def test_ordinary_paths_are_not_protected(self, ordinary_path: str):
        assert not DEFAULT_GOVERNANCE_PROTECTED_PATHS.classify(ordinary_path).protected

    def test_verdict_is_frozen_and_json_serializable(self):
        verdict = DEFAULT_GOVERNANCE_PROTECTED_PATHS.classify("AGENTS.md")
        # Frozen dataclass: cannot mutate.
        with pytest.raises(Exception):
            verdict.protected = False  # type: ignore[misc]
        # Deterministic JSON (ContractRecord) with enum collapsed to its value.
        payload = verdict.to_json_dict()
        assert payload["protected"] is True
        assert payload["match"] == "exact_file"


# ---------------------------------------------------------------------------
# CodeEngine enforcement seam
# ---------------------------------------------------------------------------


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    return ws


def _adapter(ws: Path) -> LocalCodeAdapter:
    return LocalCodeAdapter(root_path=str(ws), clock=lambda: T0)


_RENAME_MAIN_DIFF = (
    "--- a/main.py\n"
    "+++ b/main.py\n"
    "@@ -1,2 +1,2 @@\n"
    "-def hello():\n"
    "+def greet():\n"
    "     return 'world'\n"
)


class TestCodeEngineProtectedPathGate:
    def test_default_engine_blocks_protected_target(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        engine = CodeEngine(adapter=_adapter(ws), clock=lambda: T0)  # default policy on
        proposal = PatchProposal(
            patch_id="p-blocked",
            target_file="schemas/contract.schema.json",
            description="tamper with a schema",
            unified_diff="--- a\n+++ b\n",
        )
        result = engine.apply_patch_and_verify(proposal)
        assert result.status is PatchStatus.BLOCKED
        assert "protected" in (result.error_message or "").lower()
        # Fail-closed BEFORE any filesystem effect: the dir is never created.
        assert not (ws / "schemas").exists()

    def test_default_engine_allows_ordinary_target(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        engine = CodeEngine(adapter=_adapter(ws), clock=lambda: T0)
        proposal = PatchProposal(
            patch_id="p-ok",
            target_file="main.py",
            description="rename function",
            unified_diff=_RENAME_MAIN_DIFF,
        )
        result = engine.apply_patch_and_verify(proposal)
        assert result.succeeded
        assert "greet" in (ws / "main.py").read_text(encoding="utf-8")

    def test_protected_paths_none_disables_the_gate(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        engine = CodeEngine(adapter=_adapter(ws), clock=lambda: T0, protected_paths=None)
        proposal = PatchProposal(
            patch_id="p-disabled",
            target_file="schemas/contract.schema.json",
            description="no gate",
            unified_diff="--- a\n+++ b\n",
        )
        result = engine.apply_patch_and_verify(proposal)
        # Gate disabled: we fall through to normal apply, which fails because
        # the target does not exist — but the status is NOT a protected BLOCK.
        assert result.status is not PatchStatus.BLOCKED

    def test_empty_policy_disables_the_gate(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        engine = CodeEngine(
            adapter=_adapter(ws), clock=lambda: T0, protected_paths=ProtectedPathPolicy(),
        )
        proposal = PatchProposal(
            patch_id="p-empty",
            target_file="schemas/contract.schema.json",
            description="no gate",
            unified_diff="--- a\n+++ b\n",
        )
        assert engine.apply_patch_and_verify(proposal).status is not PatchStatus.BLOCKED

    def test_custom_policy_scopes_protection(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        (ws / "src").mkdir()
        (ws / "src" / "lib.py").write_text("LIB = '1.0'\n", encoding="utf-8")
        engine = CodeEngine(
            adapter=_adapter(ws), clock=lambda: T0,
            protected_paths=ProtectedPathPolicy(directories=("src",)),
        )
        blocked = engine.apply_patch_and_verify(PatchProposal(
            patch_id="p-src",
            target_file="src/lib.py",
            description="touch protected src",
            unified_diff="--- a\n+++ b\n",
        ))
        assert blocked.status is PatchStatus.BLOCKED
        # main.py is outside the custom protected set → applies normally.
        allowed = engine.apply_patch_and_verify(PatchProposal(
            patch_id="p-main",
            target_file="main.py",
            description="rename",
            unified_diff=_RENAME_MAIN_DIFF,
        ))
        assert allowed.succeeded


# ---------------------------------------------------------------------------
# Autonomy-loop enforcement seam (governed_software_change)
# ---------------------------------------------------------------------------

_PROTECTED_TARGET = ".github/workflows/ci.yml"

_CREATE_CI_DIFF = (
    "--- /dev/null\n"
    "+++ b/.github/workflows/ci.yml\n"
    "@@ -0,0 +1,1 @@\n"
    "+name: ci\n"
)


def _accept_ucja(payload):
    return UCJAOutcomeShape(
        accepted=True, rejected=False, job_id="job-accept",
        halted_at_layer=None, reason="",
    )


def _loop_clock():
    times = iter((T0,) + ("2025-01-15T10:00:05+00:00",) * 16)
    return lambda: next(times)


def _passing_unit_gate(adapter, request, attempt):
    return QualityGateResult(
        gate="unit_tests", passed=True,
        evidence_id=f"gate-unit-{attempt}", summary="ok",
    )


def _protected_request() -> SoftwareRequest:
    return SoftwareRequest(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="touch the ci workflow",
        repository="r-test",
        affected_files=(_PROTECTED_TARGET,),
        acceptance_criteria=("workflow updated",),
        quality_gates=(SoftwareQualityGate.UNIT_TESTS,),
        max_self_debug_iterations=1,
    )


def _protected_plan(req, snap) -> WorkPlan:
    return WorkPlan(
        plan_id="plan-ci", summary="touch ci",
        steps=("create ci workflow",), target_files=(_PROTECTED_TARGET,),
    )


def _protected_patch(req, snap, plan, attempt, prior):
    return PatchProposal(
        patch_id="patch-ci", target_file=_PROTECTED_TARGET,
        description="create ci workflow", unified_diff=_CREATE_CI_DIFF,
    )


def _loop_adapter(tmp_path: Path) -> LocalCodeAdapter:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "main.py").write_text("x = 1\n", encoding="utf-8")
    return LocalCodeAdapter(
        root_path=str(ws), clock=lambda: T0,
        command_policy=CommandPolicy.permissive_for_testing(),
    )


class TestLoopProtectedPathGate:
    def test_loop_blocks_protected_target_by_default(self, tmp_path: Path):
        adapter = _loop_adapter(tmp_path)
        outcome = governed_software_change(
            _protected_request(),
            adapter=adapter,
            plan_generator=_protected_plan,
            patch_generator=_protected_patch,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_unit_gate},
            clock=_loop_clock(),
            ucja_runner=_accept_ucja,
        )
        attempt = outcome.evidence.attempts[0]
        assert attempt.status is AttemptStatus.APPLY_FAILED
        assert attempt.patch_result is not None
        assert attempt.patch_result.status is PatchStatus.BLOCKED
        assert "protected" in (attempt.patch_result.error_message or "").lower()
        # The protected file was never written to disk.
        assert adapter.read_file(_PROTECTED_TARGET) is None
        assert outcome.certificate.disposition is not TerminalClosureDisposition.COMMITTED

    def test_loop_applies_protected_target_when_gate_disabled(self, tmp_path: Path):
        adapter = _loop_adapter(tmp_path)
        outcome = governed_software_change(
            _protected_request(),
            adapter=adapter,
            plan_generator=_protected_plan,
            patch_generator=_protected_patch,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_unit_gate},
            clock=_loop_clock(),
            ucja_runner=_accept_ucja,
            protected_paths=None,
        )
        # Gate disabled → the create patch applies and gates pass → COMMITTED.
        assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED
        assert adapter.read_file(_PROTECTED_TARGET) is not None
