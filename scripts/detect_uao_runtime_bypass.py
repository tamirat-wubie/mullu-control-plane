#!/usr/bin/env python3
"""Detect runtime dispatch paths that bypass Universal Action Orchestration.

Purpose: scan effect-bearing dispatch and execute call sites for UAO or
governed-dispatch binding before the workspace can claim UAO no-bypass closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library only.
Invariants:
  - The detector is read-only and deterministic.
  - Findings are classified as uao_bound, governed_bound, exempted, or violation.
  - New unbound effect-bearing runtime calls fail closed unless explicitly
    classified with a causal exemption.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_ROOTS = (
    WORKSPACE_ROOT / "gateway",
    WORKSPACE_ROOT / "mcoi" / "mcoi_runtime",
)
SKIPPED_PATH_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        "tests",
        "testdata",
    }
)
HIGH_RISK_FILE_KEYWORDS = frozenset(
    {
        "adapter",
        "capability",
        "dispatcher",
        "dispatch",
        "execution",
        "executor",
        "kernel",
        "operator",
        "worker",
    }
)
DIRECT_EFFECT_METHOD_NAMES = frozenset({"dispatch", "execute", "governed_dispatch"})
DIRECT_EFFECT_FUNCTION_PREFIXES = ("dispatch_", "execute_")
UAO_BINDING_TERMS = frozenset(
    {
        "UniversalActionKernel",
        "UniversalActionRequest",
        "UniversalActionResult",
        "build_universal_action_orchestration_record",
        "universal_action",
        "universal-action",
        "action_envelope",
        "admission_receipt_ref",
        "execution_receipt_ref",
        "closure_state",
    }
)
GOVERNED_BINDING_TERMS = frozenset(
    {
        "GovernedDispatcher",
        "GovernedDispatchContext",
        "GovernedDispatchResult",
        "governed_dispatch",
        "capability_admission",
        "effect_assurance",
        "terminal_closure",
        "receipt_status",
        "execution_receipt",
    }
)
EXEMPTION_TERMS = frozenset({"uao_bypass_exempt", "bypass_detector_exempt"})
ALLOWED_RUNTIME_BOUNDARIES: Mapping[str, str] = {
    "gateway/adapter_worker_clients.py": (
        "signed adapter worker transport; worker receipts and evidence refs are "
        "verified before capability results are returned"
    ),
    "gateway/browser_worker.py": (
        "worker endpoint boundary; request policy and adapter receipts are "
        "validated inside the worker"
    ),
    "gateway/capability_dispatch.py": (
        "legacy capability fabric boundary; direct handlers must return explicit "
        "receipt fields until fully routed through UAO"
    ),
    "gateway/capability_isolation.py": (
        "capability isolation boundary; isolated executor emits capability "
        "execution receipts"
    ),
    "gateway/capability_worker.py": (
        "capability worker endpoint boundary; execution receipt is emitted before "
        "response exposure"
    ),
    "gateway/causal_closure_kernel.py": (
        "causal closure bridge; proof adapter and isolated executor bind dispatch "
        "to closure receipts"
    ),
    "gateway/document_worker.py": (
        "worker endpoint boundary; document adapter evidence is validated before "
        "response exposure"
    ),
    "gateway/email_calendar_worker.py": (
        "worker endpoint boundary; communication actions require policy and "
        "receipt validation"
    ),
    "gateway/mcp_capabilities.py": (
        "MCP executor bridge; execution receipt is returned in the capability "
        "payload"
    ),
    "gateway/messaging_worker.py": (
        "worker endpoint boundary; messaging policy and receipts are checked "
        "before response exposure"
    ),
    "gateway/phone_worker.py": (
        "worker endpoint boundary; phone policy and receipts are checked before "
        "response exposure"
    ),
    "gateway/physical_worker_canary.py": (
        "canary fixture exercises admitted and blocked physical worker receipts"
    ),
    "gateway/proof_carrying_adapter.py": (
        "proof-carrying adapter verifies worker execution receipts before "
        "promotion"
    ),
    "gateway/router.py": (
        "legacy router execution boundary; routed command execution is separately "
        "covered by command spine receipts"
    ),
    "gateway/voice_worker.py": (
        "worker endpoint boundary; voice policy and receipts are checked before "
        "response exposure"
    ),
    "mcoi/mcoi_runtime/app/governed_execution.py": (
        "UAO integration boundary; requests are converted into universal action "
        "kernel inputs"
    ),
    "mcoi/mcoi_runtime/app/operator_executors.py": (
        "operator executor has a governed dispatcher preference and a legacy "
        "dispatcher fallback kept visible for migration"
    ),
    "mcoi/mcoi_runtime/app/operator_runners.py": (
        "operator runner composes registered executors and records run output "
        "inside runtime state"
    ),
    "mcoi/mcoi_runtime/core/governed_session.py": (
        "governed session dispatch prefers governed_dispatcher and records "
        "bounded execution detail"
    ),
    "mcoi/mcoi_runtime/core/dispatcher.py": (
        "raw execution-slice dispatcher; callers must wrap it with governed "
        "dispatcher or UAO before effect-bearing admission"
    ),
    "mcoi/mcoi_runtime/core/live_channel_bindings.py": (
        "live connector binding emits connector execution records for channel "
        "actions"
    ),
    "mcoi/mcoi_runtime/core/live_parser_bindings.py": (
        "live connector binding emits connector execution records for parser "
        "actions"
    ),
    "mcoi/mcoi_runtime/core/mil_dispatcher_bridge.py": (
        "MIL bridge dispatches only after verification and through governed "
        "dispatcher"
    ),
    "mcoi/mcoi_runtime/core/traced_workflow.py": (
        "workflow trace boundary records stage execution and trace snapshots"
    ),
    "mcoi/mcoi_runtime/core/temporal_skill_executor.py": (
        "temporal skill executor emits fail-closed stage and plan receipts for "
        "provider-mediated stage execution"
    ),
    "mcoi/mcoi_runtime/workers/code_worker.py": (
        "code worker delegates sandbox execution to the sandbox runner receipt "
        "boundary"
    ),
}
_DEFAULT_REPORT_CACHE: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RuntimeBypassFinding:
    """One runtime dispatch finding."""

    path: str
    line: int
    symbol: str
    call: str
    classification: str
    reason: str


class _EffectCallVisitor(ast.NodeVisitor):
    """Collect direct runtime dispatch calls from one Python module."""

    def __init__(self, relative_path: str, source_text: str) -> None:
        self._relative_path = relative_path
        self._source_text = source_text
        self._stack: list[ast.AST] = []
        self.findings: list[RuntimeBypassFinding] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._stack.append(node)
        self.generic_visit(node)
        self._stack.pop()
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._stack.append(node)
        self.generic_visit(node)
        self._stack.pop()
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._stack.append(node)
        self.generic_visit(node)
        self._stack.pop()
        return None

    def visit_Call(self, node: ast.Call) -> Any:
        call_name = _call_name(node.func)
        if call_name and self._is_effect_call(call_name):
            finding = self._classify_call(node, call_name)
            if finding is not None:
                self.findings.append(finding)
        self.generic_visit(node)
        return None

    def _is_effect_call(self, call_name: str) -> bool:
        basename = Path(self._relative_path).name.lower()
        path_text = self._relative_path.lower()
        if not _path_looks_runtime_effectful(path_text, basename):
            return False
        leaf_name = call_name.rsplit(".", 1)[-1]
        if leaf_name in DIRECT_EFFECT_METHOD_NAMES:
            return True
        return leaf_name.startswith(DIRECT_EFFECT_FUNCTION_PREFIXES)

    def _classify_call(
        self, node: ast.Call, call_name: str
    ) -> RuntimeBypassFinding | None:
        scope_terms = _scope_search_text(self._current_scope(node))
        symbol = self._symbol_name()
        if any(term in scope_terms for term in EXEMPTION_TERMS):
            return RuntimeBypassFinding(
                path=self._relative_path,
                line=int(getattr(node, "lineno", 0)),
                symbol=symbol,
                call=call_name,
                classification="exempted",
                reason="local source segment declares a bounded bypass detector exemption",
            )
        if any(term in scope_terms for term in UAO_BINDING_TERMS):
            return RuntimeBypassFinding(
                path=self._relative_path,
                line=int(getattr(node, "lineno", 0)),
                symbol=symbol,
                call=call_name,
                classification="uao_bound",
                reason="source segment carries Universal Action Orchestration envelope or receipt binding",
            )
        if call_name.endswith(".governed_dispatch") or any(
            term in scope_terms for term in GOVERNED_BINDING_TERMS
        ):
            return RuntimeBypassFinding(
                path=self._relative_path,
                line=int(getattr(node, "lineno", 0)),
                symbol=symbol,
                call=call_name,
                classification="governed_bound",
                reason="source segment carries governed dispatcher, admission, effect, or receipt binding",
            )
        exemption = ALLOWED_RUNTIME_BOUNDARIES.get(self._relative_path)
        if exemption is not None:
            return RuntimeBypassFinding(
                path=self._relative_path,
                line=int(getattr(node, "lineno", 0)),
                symbol=symbol,
                call=call_name,
                classification="exempted",
                reason=exemption,
            )
        return RuntimeBypassFinding(
            path=self._relative_path,
            line=int(getattr(node, "lineno", 0)),
            symbol=symbol,
            call=call_name,
            classification="violation",
            reason="effect-bearing runtime call has no UAO/governed binding and no bounded exemption",
        )

    def _current_scope(self, node: ast.AST) -> ast.AST:
        for ancestor in reversed(self._stack):
            return ancestor
        return node

    def _symbol_name(self) -> str:
        names: list[str] = []
        for item in self._stack:
            item_name = getattr(item, "name", "")
            if item_name:
                names.append(str(item_name))
        return ".".join(names) if names else "<module>"


def build_detection_report(
    scan_roots: Iterable[Path] = DEFAULT_SCAN_ROOTS,
) -> dict[str, Any]:
    """Build a machine-readable runtime bypass detector report."""

    roots = tuple(scan_roots)
    if _is_default_scan_roots(roots):
        global _DEFAULT_REPORT_CACHE
        if _DEFAULT_REPORT_CACHE is None:
            _DEFAULT_REPORT_CACHE = _build_detection_report_uncached(roots)
        return deepcopy(_DEFAULT_REPORT_CACHE)
    return _build_detection_report_uncached(roots)


def _build_detection_report_uncached(scan_roots: Iterable[Path]) -> dict[str, Any]:
    """Build an uncached runtime bypass detector report."""

    findings: list[RuntimeBypassFinding] = []
    scanned_files = 0
    parse_errors: list[str] = []
    for source_path in _iter_python_files(scan_roots):
        scanned_files += 1
        try:
            findings.extend(scan_source_file(source_path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append(f"{_path_label(source_path)}: {exc.__class__.__name__}")

    finding_dicts = [asdict(finding) for finding in findings]
    violation_count = sum(
        1 for finding in findings if finding.classification == "violation"
    )
    uao_bound_count = sum(
        1 for finding in findings if finding.classification == "uao_bound"
    )
    governed_bound_count = sum(
        1 for finding in findings if finding.classification == "governed_bound"
    )
    exempted_count = sum(
        1 for finding in findings if finding.classification == "exempted"
    )
    status = "passed" if violation_count == 0 and not parse_errors else "failed"
    return {
        "detector_id": "uao_runtime_bypass_detector",
        "status": status,
        "valid": status == "passed",
        "scan_roots": [_path_label(root) for root in scan_roots],
        "scanned_file_count": scanned_files,
        "candidate_count": len(findings),
        "uao_bound_count": uao_bound_count,
        "governed_bound_count": governed_bound_count,
        "exempted_count": exempted_count,
        "violation_count": violation_count,
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors,
        "findings": finding_dicts,
    }


def scan_source_file(source_path: Path) -> list[RuntimeBypassFinding]:
    """Scan one Python source file for direct runtime dispatch calls."""

    source_text = source_path.read_text(encoding="utf-8")
    relative_path = _path_label(source_path)
    return scan_source_text(source_text, relative_path=relative_path)


def scan_source_text(
    source_text: str,
    *,
    relative_path: str = "gateway/runtime_boundary.py",
) -> list[RuntimeBypassFinding]:
    """Scan source text and return classified runtime bypass findings."""

    tree = ast.parse(source_text)
    visitor = _EffectCallVisitor(relative_path, source_text)
    visitor.visit(tree)
    return visitor.findings


def main(argv: list[str] | None = None) -> int:
    """Run the UAO runtime bypass detector."""

    parser = argparse.ArgumentParser(
        description="Detect runtime dispatch paths that bypass UAO."
    )
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        default=[],
        help="Python package or file root to scan; may be repeated",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable detector report",
    )
    args = parser.parse_args(argv)

    scan_roots = tuple(args.root) if args.root else DEFAULT_SCAN_ROOTS
    report = build_detection_report(scan_roots)
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1
    if not report["valid"]:
        for error in report["parse_errors"]:
            sys.stderr.write(f"[FAIL] uao-runtime-bypass-parse: {error}\n")
        for finding in report["findings"]:
            if finding["classification"] == "violation":
                sys.stderr.write(
                    "[FAIL] uao-runtime-bypass: "
                    f"{finding['path']}:{finding['line']} "
                    f"{finding['symbol']} {finding['call']} - {finding['reason']}\n"
                )
        sys.stderr.write("STATUS: failed\n")
        return 1
    sys.stdout.write("[PASS] uao_runtime_bypass_detector\n")
    sys.stdout.write(
        "candidate_count="
        f"{report['candidate_count']} "
        f"uao_bound={report['uao_bound_count']} "
        f"governed_bound={report['governed_bound_count']} "
        f"exempted={report['exempted_count']}\n"
    )
    sys.stdout.write("STATUS: passed\n")
    return 0


def _iter_python_files(scan_roots: Iterable[Path]) -> Iterable[Path]:
    for root in scan_roots:
        resolved = (WORKSPACE_ROOT / root).resolve() if not root.is_absolute() else root
        if resolved.is_file() and resolved.suffix == ".py":
            if not _is_skipped(resolved):
                yield resolved
            continue
        if not resolved.exists():
            continue
        for source_path in sorted(resolved.rglob("*.py")):
            if not _is_skipped(source_path) and _should_scan_file(source_path):
                yield source_path


def _is_skipped(source_path: Path) -> bool:
    return any(part in SKIPPED_PATH_PARTS for part in source_path.parts)


def _should_scan_file(source_path: Path) -> bool:
    path_label = _path_label(source_path).lower()
    basename = source_path.name.lower()
    return _path_looks_runtime_effectful(path_label, basename)


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parent_name = _call_name(func.value)
        return f"{parent_name}.{func.attr}" if parent_name else func.attr
    if isinstance(func, ast.Call):
        return _call_name(func.func)
    return None


def _scope_search_text(node: ast.AST) -> str:
    values: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            values.append(child.id)
        elif isinstance(child, ast.Attribute):
            values.append(child.attr)
        elif isinstance(child, ast.keyword) and child.arg:
            values.append(child.arg)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return "\n".join(values)


def _path_looks_runtime_effectful(path_text: str, basename: str) -> bool:
    if any(keyword in path_text for keyword in HIGH_RISK_FILE_KEYWORDS):
        return True
    return basename == "router.py"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _is_default_scan_roots(scan_roots: tuple[Path, ...]) -> bool:
    observed = tuple(Path(root).resolve(strict=False) for root in scan_roots)
    expected = tuple(root.resolve(strict=False) for root in DEFAULT_SCAN_ROOTS)
    return observed == expected


if __name__ == "__main__":
    raise SystemExit(main())
