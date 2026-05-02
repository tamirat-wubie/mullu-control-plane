#!/usr/bin/env python3
"""Collect capability adapter closure evidence.

Purpose: emit a deterministic evidence report for browser, document, voice, and
communication worker production-closure gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: optional adapter runtime modules and live receipt artifacts.
Invariants:
  - Adapter code presence is separate from dependency availability.
  - Dependency availability is separate from live closure receipts.
  - Missing runtime libraries or receipts block promotion without side effects.
  - Provider credentials are checked by presence only and never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_adapter_evidence.json"
DEFAULT_BROWSER_RECEIPT = REPO_ROOT / ".change_assurance" / "browser_live_receipt.json"
DEFAULT_DOCUMENT_RECEIPT = REPO_ROOT / ".change_assurance" / "document_live_receipt.json"
DEFAULT_VOICE_RECEIPT = REPO_ROOT / ".change_assurance" / "voice_live_receipt.json"
DEFAULT_EMAIL_CALENDAR_RECEIPT = REPO_ROOT / ".change_assurance" / "email_calendar_live_receipt.json"

REQUIRED_DOCUMENT_PARSERS = frozenset(
    {
        "production-pdf",
        "production-docx",
        "production-xlsx",
        "production-pptx",
    }
)


@dataclass(frozen=True, slots=True)
class DependencyCheck:
    """One adapter dependency check."""

    name: str
    available: bool
    required: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready dependency check."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReceiptCheck:
    """One live evidence receipt check."""

    name: str
    passed: bool
    detail: str
    receipt_path: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready receipt check."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdapterEvidence:
    """Production closure evidence for one governed adapter family."""

    adapter_id: str
    status: str
    adapter_module: str
    worker_module: str
    dependency_checks: tuple[DependencyCheck, ...]
    receipt_check: ReceiptCheck
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    @property
    def closed(self) -> bool:
        """Return whether this adapter family is production-closed."""
        return self.status == "closed" and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready adapter evidence payload."""
        return {
            "adapter_id": self.adapter_id,
            "status": self.status,
            "adapter_module": self.adapter_module,
            "worker_module": self.worker_module,
            "dependency_checks": [check.as_dict() for check in self.dependency_checks],
            "receipt_check": self.receipt_check.as_dict(),
            "blockers": list(self.blockers),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class CapabilityAdapterEvidenceReport:
    """Full adapter closure evidence report."""

    report_id: str
    checked_at: str
    ready: bool
    adapters: tuple[AdapterEvidence, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready report."""
        return {
            "report_id": self.report_id,
            "checked_at": self.checked_at,
            "ready": self.ready,
            "adapters": [adapter.as_dict() for adapter in self.adapters],
            "blockers": list(self.blockers),
        }


ModuleAvailable = Callable[[str], bool]
EnvReader = Callable[[str], str | None]


def collect_capability_adapter_evidence(
    *,
    repo_root: Path = REPO_ROOT,
    browser_receipt_path: Path = DEFAULT_BROWSER_RECEIPT,
    document_receipt_path: Path = DEFAULT_DOCUMENT_RECEIPT,
    voice_receipt_path: Path = DEFAULT_VOICE_RECEIPT,
    email_calendar_receipt_path: Path = DEFAULT_EMAIL_CALENDAR_RECEIPT,
    module_available: ModuleAvailable | None = None,
    env_reader: EnvReader | None = None,
    clock: Callable[[], str] | None = None,
) -> CapabilityAdapterEvidenceReport:
    """Collect adapter dependency and live receipt evidence."""
    resolved_module_available = module_available or _module_available
    resolved_env_reader = env_reader or os.environ.get
    resolved_clock = clock or _validation_clock
    resolved_repo_root = repo_root.resolve(strict=False)

    adapters = (
        _browser_evidence(
            repo_root=resolved_repo_root,
            receipt_path=browser_receipt_path,
            module_available=resolved_module_available,
        ),
        _document_evidence(
            repo_root=resolved_repo_root,
            receipt_path=document_receipt_path,
            module_available=resolved_module_available,
        ),
        _voice_evidence(
            repo_root=resolved_repo_root,
            receipt_path=voice_receipt_path,
            module_available=resolved_module_available,
            env_reader=resolved_env_reader,
        ),
        _email_calendar_evidence(
            repo_root=resolved_repo_root,
            receipt_path=email_calendar_receipt_path,
            env_reader=resolved_env_reader,
        ),
    )
    blockers = tuple(blocker for adapter in adapters for blocker in adapter.blockers)
    checked_at = resolved_clock()
    report_hash = hashlib.sha256(
        json.dumps(
            {
                "checked_at": checked_at,
                "adapters": [adapter.as_dict() for adapter in adapters],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return CapabilityAdapterEvidenceReport(
        report_id=f"capability-adapter-evidence-{report_hash[:16]}",
        checked_at=checked_at,
        ready=not blockers,
        adapters=adapters,
        blockers=blockers,
    )


def write_capability_adapter_evidence(
    report: CapabilityAdapterEvidenceReport,
    output_path: Path,
) -> Path:
    """Write one adapter evidence report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _browser_evidence(
    *,
    repo_root: Path,
    receipt_path: Path,
    module_available: ModuleAvailable,
) -> AdapterEvidence:
    dependencies = (_dependency("playwright", module_available),)
    receipt = _browser_receipt_check(receipt_path)
    blockers = [
        f"browser_dependency_missing:{check.name}"
        for check in dependencies
        if check.required and not check.available
    ]
    if not receipt.passed:
        blockers.append("browser_live_evidence_missing")
    return _adapter_evidence(
        adapter_id="browser.playwright",
        adapter_module="gateway.browser_playwright_adapter",
        worker_module="gateway.browser_worker",
        repo_root=repo_root,
        dependencies=dependencies,
        receipt=receipt,
        blockers=tuple(blockers),
    )


def _document_evidence(
    *,
    repo_root: Path,
    receipt_path: Path,
    module_available: ModuleAvailable,
) -> AdapterEvidence:
    dependencies = tuple(
        _dependency(module_name, module_available)
        for module_name in ("pypdf", "docx", "openpyxl", "pptx")
    )
    receipt = _document_receipt_check(receipt_path)
    blockers = [
        f"document_dependency_missing:{check.name}"
        for check in dependencies
        if check.required and not check.available
    ]
    if not receipt.passed:
        blockers.append("document_live_evidence_missing")
    return _adapter_evidence(
        adapter_id="document.production_parsers",
        adapter_module="gateway.document_production_parsers",
        worker_module="gateway.document_worker",
        repo_root=repo_root,
        dependencies=dependencies,
        receipt=receipt,
        blockers=tuple(blockers),
    )


def _voice_evidence(
    *,
    repo_root: Path,
    receipt_path: Path,
    module_available: ModuleAvailable,
    env_reader: EnvReader,
) -> AdapterEvidence:
    openai_dependency = _dependency("openai", module_available)
    credential_present = bool((env_reader("OPENAI_API_KEY") or "").strip())
    credential_check = DependencyCheck(
        name="OPENAI_API_KEY",
        available=credential_present,
        required=True,
        detail="configured" if credential_present else "missing",
    )
    dependencies = (openai_dependency, credential_check)
    receipt = _voice_receipt_check(receipt_path)
    blockers = [
        f"voice_dependency_missing:{check.name}"
        for check in dependencies
        if check.required and not check.available
    ]
    if not receipt.passed:
        blockers.append("voice_live_evidence_missing")
    return _adapter_evidence(
        adapter_id="voice.openai",
        adapter_module="gateway.voice_openai_adapter",
        worker_module="gateway.voice_worker",
        repo_root=repo_root,
        dependencies=dependencies,
        receipt=receipt,
        blockers=tuple(blockers),
    )


def _email_calendar_evidence(
    *,
    repo_root: Path,
    receipt_path: Path,
    env_reader: EnvReader,
) -> AdapterEvidence:
    credential_present = any(
        bool((env_reader(name) or "").strip())
        for name in (
            "GMAIL_ACCESS_TOKEN",
            "GOOGLE_CALENDAR_ACCESS_TOKEN",
            "MICROSOFT_GRAPH_ACCESS_TOKEN",
        )
    )
    credential_check = DependencyCheck(
        name="EMAIL_CALENDAR_CONNECTOR_TOKEN",
        available=credential_present,
        required=True,
        detail="configured" if credential_present else "missing",
    )
    dependencies = (credential_check,)
    receipt = _email_calendar_receipt_check(receipt_path)
    blockers = [
        f"email_calendar_dependency_missing:{check.name}"
        for check in dependencies
        if check.required and not check.available
    ]
    if not receipt.passed:
        blockers.append("email_calendar_live_evidence_missing")
    return _adapter_evidence(
        adapter_id="communication.email_calendar_worker",
        adapter_module="gateway.email_calendar_connector_adapters",
        worker_module="gateway.email_calendar_worker",
        repo_root=repo_root,
        dependencies=dependencies,
        receipt=receipt,
        blockers=tuple(blockers),
    )


def _adapter_evidence(
    *,
    adapter_id: str,
    adapter_module: str,
    worker_module: str,
    repo_root: Path,
    dependencies: tuple[DependencyCheck, ...],
    receipt: ReceiptCheck,
    blockers: tuple[str, ...],
) -> AdapterEvidence:
    module_refs = tuple(dict.fromkeys(_module_ref(repo_root, module_name) for module_name in (worker_module, adapter_module)))
    missing_modules = tuple(ref for ref in module_refs if not Path(ref).exists())
    all_blockers = (
        *blockers,
        *(f"adapter_module_missing:{Path(ref).name}" for ref in missing_modules),
    )
    return AdapterEvidence(
        adapter_id=adapter_id,
        status="closed" if not all_blockers else "not_closed",
        adapter_module=adapter_module,
        worker_module=worker_module,
        dependency_checks=dependencies,
        receipt_check=receipt,
        blockers=tuple(all_blockers),
        evidence_refs=(*module_refs, receipt.receipt_path),
    )


def _dependency(name: str, module_available: ModuleAvailable) -> DependencyCheck:
    available = module_available(name)
    return DependencyCheck(
        name=name,
        available=available,
        required=True,
        detail="available" if available else "missing",
    )


def _browser_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("browser live receipt", False, error, str(path))
    passed = (
        _passed_status(payload)
        and payload.get("adapter_id") == "browser.playwright"
        and payload.get("sandboxed_worker") is True
    )
    detail = "passed" if passed else "requires status=passed, adapter_id=browser.playwright, sandboxed_worker=true"
    return ReceiptCheck("browser live receipt", passed, detail, str(path))


def _document_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("document live receipt", False, error, str(path))
    parser_ids = {
        str(parser_id)
        for parser_id in payload.get("parser_ids", payload.get("production_parser_ids", ()))
    }
    passed = _passed_status(payload) and REQUIRED_DOCUMENT_PARSERS.issubset(parser_ids)
    detail = (
        "passed"
        if passed
        else f"requires status=passed and parser_ids={sorted(REQUIRED_DOCUMENT_PARSERS)}"
    )
    return ReceiptCheck("document live receipt", passed, detail, str(path))


def _voice_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("voice live receipt", False, error, str(path))
    passed = (
        _passed_status(payload)
        and payload.get("speech_to_text_status") == "passed"
        and payload.get("text_to_speech_status") == "passed"
    )
    detail = "passed" if passed else "requires passed speech_to_text and text_to_speech checks"
    return ReceiptCheck("voice live receipt", passed, detail, str(path))


def _email_calendar_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("email/calendar live receipt", False, error, str(path))
    passed = (
        _passed_status(payload)
        and payload.get("adapter_id") == "communication.email_calendar_worker"
        and payload.get("external_write") is False
    )
    detail = (
        "passed"
        if passed
        else "requires status=passed, adapter_id=communication.email_calendar_worker, external_write=false"
    )
    return ReceiptCheck("email/calendar live receipt", passed, detail, str(path))


def _load_receipt(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "receipt missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"receipt JSON parse failed: {exc.msg}"
    if not isinstance(payload, dict):
        return {}, "receipt JSON root must be an object"
    return payload, ""


def _passed_status(payload: dict[str, Any]) -> bool:
    return payload.get("status") == "passed" or payload.get("verification_status") == "passed"


def _module_ref(repo_root: Path, module_name: str) -> str:
    return str(repo_root / Path(*module_name.split(".")).with_suffix(".py"))


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse adapter evidence collection arguments."""
    parser = argparse.ArgumentParser(description="Collect governed adapter closure evidence.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--browser-receipt", default=str(DEFAULT_BROWSER_RECEIPT))
    parser.add_argument("--document-receipt", default=str(DEFAULT_DOCUMENT_RECEIPT))
    parser.add_argument("--voice-receipt", default=str(DEFAULT_VOICE_RECEIPT))
    parser.add_argument("--email-calendar-receipt", default=str(DEFAULT_EMAIL_CALENDAR_RECEIPT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON evidence.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when adapter closure is incomplete.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for adapter evidence collection."""
    args = parse_args(argv)
    report = collect_capability_adapter_evidence(
        repo_root=Path(args.repo_root),
        browser_receipt_path=Path(args.browser_receipt),
        document_receipt_path=Path(args.document_receipt),
        voice_receipt_path=Path(args.voice_receipt),
        email_calendar_receipt_path=Path(args.email_calendar_receipt),
    )
    write_capability_adapter_evidence(report, Path(args.output))
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    elif report.ready:
        print(f"CAPABILITY ADAPTER EVIDENCE READY report_id={report.report_id}")
    else:
        print(f"CAPABILITY ADAPTER EVIDENCE BLOCKED blockers={list(report.blockers)}")
    return 0 if report.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
