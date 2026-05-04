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
import re
import tomllib
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
MODULE_PACKAGE_NAMES = {
    "docx": "python-docx",
    "pptx": "python-pptx",
}
WORKER_EXTRA_BY_MODULE = {
    "playwright": "browser-worker",
    "pypdf": "document-worker",
    "docx": "document-worker",
    "openpyxl": "document-worker",
    "pptx": "document-worker",
    "openai": "voice-worker",
}


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
    evidence_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready receipt check."""
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


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
    worker_dependency_contract = _worker_dependency_contract(resolved_repo_root)

    adapters = (
        _browser_evidence(
            repo_root=resolved_repo_root,
            receipt_path=browser_receipt_path,
            module_available=resolved_module_available,
            worker_dependency_contract=worker_dependency_contract,
        ),
        _document_evidence(
            repo_root=resolved_repo_root,
            receipt_path=document_receipt_path,
            module_available=resolved_module_available,
            worker_dependency_contract=worker_dependency_contract,
        ),
        _voice_evidence(
            repo_root=resolved_repo_root,
            receipt_path=voice_receipt_path,
            module_available=resolved_module_available,
            env_reader=resolved_env_reader,
            worker_dependency_contract=worker_dependency_contract,
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
    worker_dependency_contract: dict[str, bool],
) -> AdapterEvidence:
    dependencies = (_dependency("playwright", module_available, worker_dependency_contract),)
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
    worker_dependency_contract: dict[str, bool],
) -> AdapterEvidence:
    dependencies = tuple(
        _dependency(module_name, module_available, worker_dependency_contract)
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
    worker_dependency_contract: dict[str, bool],
) -> AdapterEvidence:
    openai_dependency = _dependency("openai", module_available, worker_dependency_contract)
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
        evidence_refs=(*module_refs, receipt.receipt_path, *receipt.evidence_refs),
    )


def _dependency(
    name: str,
    module_available: ModuleAvailable,
    worker_dependency_contract: dict[str, bool],
) -> DependencyCheck:
    runtime_available = module_available(name)
    worker_declared = worker_dependency_contract.get(name) is True
    available = runtime_available or worker_declared
    detail = "available" if runtime_available else "worker_dependency_declared" if worker_declared else "missing"
    return DependencyCheck(
        name=name,
        available=available,
        required=True,
        detail=detail,
    )


def _worker_dependency_contract(repo_root: Path) -> dict[str, bool]:
    pyproject_extras = _mcoi_optional_dependency_packages(repo_root / "mcoi" / "pyproject.toml")
    dockerfile_text = _read_text(repo_root / "Dockerfile")
    installs_worker_extras = _dockerfile_installs_worker_extras(dockerfile_text)
    return {
        module_name: (
            installs_worker_extras
            and _package_declared_for_worker_extra(
                pyproject_extras,
                package_name=MODULE_PACKAGE_NAMES.get(module_name, module_name),
                extra_name=extra_name,
            )
        )
        for module_name, extra_name in WORKER_EXTRA_BY_MODULE.items()
    }


def _mcoi_optional_dependency_packages(pyproject_path: Path) -> dict[str, set[str]]:
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    extras = payload.get("project", {}).get("optional-dependencies", {})
    if not isinstance(extras, dict):
        return {}
    parsed: dict[str, set[str]] = {}
    for extra_name, raw_requirements in extras.items():
        if not isinstance(extra_name, str) or not isinstance(raw_requirements, list):
            continue
        parsed[extra_name] = {
            _requirement_package_name(str(requirement))
            for requirement in raw_requirements
            if str(requirement).strip()
        }
    return parsed


def _requirement_package_name(requirement: str) -> str:
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)", requirement)
    return match.group(1).lower().replace("_", "-") if match else ""


def _dockerfile_installs_worker_extras(dockerfile_text: str) -> bool:
    normalized = dockerfile_text.replace('"', "'").replace(" ", "")
    return "mcoi[all]" in normalized or "mcoi[worker]" in normalized


def _package_declared_for_worker_extra(
    extras: dict[str, set[str]],
    *,
    package_name: str,
    extra_name: str,
) -> bool:
    normalized_package = package_name.lower().replace("_", "-")
    return (
        normalized_package in extras.get(extra_name, set())
        or normalized_package in extras.get("worker", set())
        or normalized_package in extras.get("all", set())
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _browser_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("browser live receipt", False, error, str(path), ())
    sandbox_evidence_id = str(payload.get("sandbox_evidence_id", "")).strip()
    sandbox_receipt_id = str(payload.get("sandbox_receipt_id", "")).strip()
    worker_receipt = payload.get("worker_receipt") if isinstance(payload.get("worker_receipt"), dict) else {}
    network_requests = payload.get("network_requests", ())
    blockers = payload.get("blockers", ())
    passed = (
        _passed_status(payload)
        and payload.get("adapter_id") == "browser.playwright"
        and payload.get("sandboxed_worker") is True
        and sandbox_evidence_id.startswith("browser-sandbox-evidence-")
        and sandbox_receipt_id.startswith("sandbox-receipt-")
        and worker_receipt.get("verification_status") == "passed"
        and bool(str(payload.get("url_before", "")).strip())
        and bool(str(payload.get("url_after", "")).strip())
        and bool(str(payload.get("screenshot_before_ref", "")).strip())
        and bool(str(payload.get("screenshot_after_ref", "")).strip())
        and isinstance(network_requests, list)
        and bool(network_requests)
        and blockers == []
    )
    detail = (
        f"passed sandbox_evidence_id={sandbox_evidence_id} sandbox_receipt_id={sandbox_receipt_id}"
        if passed
        else (
            "requires status=passed, adapter_id=browser.playwright, sandboxed_worker=true, "
            "sandbox_evidence_id, sandbox_receipt_id, worker receipt, URL/screenshot refs, "
            "network requests, and empty blockers"
        )
    )
    evidence_refs = tuple(ref for ref in (sandbox_evidence_id, sandbox_receipt_id) if ref)
    return ReceiptCheck("browser live receipt", passed, detail, str(path), evidence_refs)


def _document_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("document live receipt", False, error, str(path), ())
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
    return ReceiptCheck("document live receipt", passed, detail, str(path), ())


def _voice_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("voice live receipt", False, error, str(path), ())
    speech_receipt = payload.get("speech_receipt") if isinstance(payload.get("speech_receipt"), dict) else {}
    synthesis_receipt = payload.get("synthesis_receipt") if isinstance(payload.get("synthesis_receipt"), dict) else {}
    blockers = payload.get("blockers", ())
    passed = (
        _passed_status(payload)
        and payload.get("speech_to_text_status") == "passed"
        and payload.get("text_to_speech_status") == "passed"
        and speech_receipt.get("verification_status") == "passed"
        and synthesis_receipt.get("verification_status") == "passed"
        and speech_receipt.get("capability_id") == "voice.speech_to_text"
        and synthesis_receipt.get("capability_id") == "voice.text_to_speech"
        and bool(str(payload.get("audio_input_hash", "")).strip())
        and bool(str(synthesis_receipt.get("audio_hash", "")).strip())
        and bool(str(synthesis_receipt.get("audio_ref", "")).strip())
        and speech_receipt.get("forbidden_effects_observed") is False
        and synthesis_receipt.get("forbidden_effects_observed") is False
        and speech_receipt.get("requires_confirmation") is False
        and synthesis_receipt.get("requires_confirmation") is False
        and blockers == []
    )
    evidence_refs = tuple(
        ref
        for ref in (
            str(speech_receipt.get("receipt_id", "")).strip(),
            str(synthesis_receipt.get("receipt_id", "")).strip(),
            str(synthesis_receipt.get("audio_ref", "")).strip(),
        )
        if ref
    )
    detail = (
        f"passed speech_receipt={speech_receipt.get('receipt_id', '')} "
        f"synthesis_receipt={synthesis_receipt.get('receipt_id', '')}"
        if passed
        else (
            "requires passed speech_to_text/text_to_speech worker receipts, audio input hash, "
            "synthesis audio ref/hash, no forbidden effects, no confirmation requirement, and empty blockers"
        )
    )
    return ReceiptCheck("voice live receipt", passed, detail, str(path), evidence_refs)


def _email_calendar_receipt_check(path: Path) -> ReceiptCheck:
    payload, error = _load_receipt(path)
    if error:
        return ReceiptCheck("email/calendar live receipt", False, error, str(path), ())
    worker_receipt = payload.get("worker_receipt") if isinstance(payload.get("worker_receipt"), dict) else {}
    blockers = payload.get("blockers", ())
    passed = (
        _passed_status(payload)
        and payload.get("adapter_id") == "communication.email_calendar_worker"
        and payload.get("external_write") is False
        and payload.get("connector_id") == worker_receipt.get("connector_id")
        and payload.get("provider_operation") == worker_receipt.get("provider_operation")
        and payload.get("resource_id") == worker_receipt.get("resource_id")
        and payload.get("response_digest") == worker_receipt.get("response_digest")
        and worker_receipt.get("verification_status") == "passed"
        and worker_receipt.get("capability_id") == "email.search"
        and worker_receipt.get("action") == "email.search"
        and worker_receipt.get("external_write") is False
        and worker_receipt.get("forbidden_effects_observed") is False
        and bool(str(worker_receipt.get("connector_id", "")).strip())
        and bool(str(worker_receipt.get("provider_operation", "")).strip())
        and bool(str(worker_receipt.get("resource_id", "")).strip())
        and bool(str(worker_receipt.get("response_digest", "")).strip())
        and blockers == []
    )
    evidence_refs = tuple(
        ref
        for ref in (
            str(worker_receipt.get("receipt_id", "")).strip(),
            str(worker_receipt.get("connector_id", "")).strip(),
            str(worker_receipt.get("resource_id", "")).strip(),
        )
        if ref
    )
    detail = (
        f"passed worker_receipt={worker_receipt.get('receipt_id', '')} connector_id={payload.get('connector_id', '')}"
        if passed
        else (
            "requires status=passed, adapter_id=communication.email_calendar_worker, "
            "read-only worker receipt, connector/resource/digest match, no forbidden effects, and empty blockers"
        )
    )
    return ReceiptCheck("email/calendar live receipt", passed, detail, str(path), evidence_refs)


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
