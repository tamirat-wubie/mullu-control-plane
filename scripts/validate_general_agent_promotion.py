#!/usr/bin/env python3
"""Validate governed general-agent promotion readiness.

Purpose: prevent broad general-agent promotion claims unless capability,
adapter, sandbox, MCP, and deployment witness evidence are all closed.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: default capability fabric, MCP manifest validation,
KNOWN_LIMITATIONS_v0.1.md, DEPLOYMENT_STATUS.md, and deployment witness JSON.
Invariants:
  - Governed capability records are the exposed surface, not raw tools.
  - Pilot governed core may pass while production promotion remains blocked.
  - Browser, document, voice, email/calendar, sandbox, and witness closures are explicit.
  - Full promotion requires published deployment evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from gateway.capability_fabric import build_default_capability_admission_gate  # noqa: E402
from scripts.validate_deployment_publication_closure import (  # noqa: E402
    load_witness_payload,
    validate_publication_closure,
)
from scripts.validate_mcp_capability_manifest import (  # noqa: E402
    validate_mcp_capability_manifest,
)

DEFAULT_DEPLOYMENT_STATUS_PATH = REPO_ROOT / "DEPLOYMENT_STATUS.md"
DEFAULT_KNOWN_LIMITATIONS_PATH = REPO_ROOT / "KNOWN_LIMITATIONS_v0.1.md"
DEFAULT_MCP_MANIFEST_PATH = REPO_ROOT / "examples" / "mcp_capability_manifest.json"
DEFAULT_WITNESS_PATH = REPO_ROOT / ".change_assurance" / "deployment_witness.json"
DEFAULT_ADAPTER_EVIDENCE_PATH = REPO_ROOT / ".change_assurance" / "capability_adapter_evidence.json"

REQUIRED_DOMAINS = frozenset(
    {
        "browser",
        "communication",
        "computer",
        "connector",
        "creative",
        "deployment",
        "document",
        "enterprise",
        "financial",
        "voice",
    }
)
REQUIRED_GOVERNED_RECORD_FIELDS = frozenset(
    {
        "capability_id",
        "tenant_id",
        "risk_level",
        "read_only",
        "world_mutating",
        "requires_approval",
        "requires_sandbox",
        "max_cost",
        "allowed_roles",
        "allowed_tools",
        "allowed_networks",
        "allowed_paths",
        "forbidden_effects",
        "verification_required",
        "receipt_required",
        "rollback_or_compensation_required",
    }
)
RAW_TOOL_SURFACE_FIELDS = frozenset(
    {
        "input_schema_ref",
        "output_schema_ref",
        "effect_model",
        "evidence_model",
        "authority_policy",
        "isolation_profile",
        "recovery_plan",
        "extensions",
        "metadata",
    }
)
DEPLOYMENT_STATE_PATTERN = re.compile(
    r"^\*\*Deployment witness state:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)
PUBLIC_HEALTH_PATTERN = re.compile(
    r"^\*\*Public production health endpoint:\*\*\s+`([^`]+)`$",
    re.MULTILINE,
)
FOUNDATION_BLOCKERS = frozenset(
    {
        "capability_fabric_not_closed",
        "governed_record_surface_not_closed",
        "mcp_manifest_not_closed",
    }
)


@dataclass(frozen=True, slots=True)
class PromotionCheck:
    """One deterministic general-agent promotion check."""

    name: str
    passed: bool
    detail: str
    evidence_refs: tuple[str, ...] = ()
    blocker_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready check payload."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GeneralAgentPromotionReadiness:
    """Structured readiness report for governed general-agent promotion."""

    ready: bool
    readiness_level: str
    checked_at: str
    capability_count: int
    capsule_count: int
    missing_closure_count: int
    blockers: tuple[str, ...]
    checks: tuple[PromotionCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready readiness report."""
        return {
            "ready": self.ready,
            "readiness_level": self.readiness_level,
            "checked_at": self.checked_at,
            "capability_count": self.capability_count,
            "capsule_count": self.capsule_count,
            "missing_closure_count": self.missing_closure_count,
            "blockers": list(self.blockers),
            "checks": [check.as_dict() for check in self.checks],
        }


def write_general_agent_promotion_readiness(
    readiness: GeneralAgentPromotionReadiness,
    output_path: Path,
) -> Path:
    """Write one deterministic promotion readiness artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(readiness.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def validate_general_agent_promotion(
    *,
    repo_root: Path = REPO_ROOT,
    deployment_status_path: Path | None = None,
    deployment_witness_path: Path | None = None,
    mcp_manifest_path: Path | None = None,
    adapter_evidence_path: Path | None = None,
    clock: Callable[[], str] | None = None,
) -> GeneralAgentPromotionReadiness:
    """Validate whether this checkout may claim production general-agent status."""
    resolved_clock = clock or _validation_clock
    resolved_repo_root = repo_root.resolve(strict=False)
    resolved_status_path = deployment_status_path or resolved_repo_root / "DEPLOYMENT_STATUS.md"
    resolved_witness_path = deployment_witness_path or (
        resolved_repo_root / ".change_assurance" / "deployment_witness.json"
    )
    resolved_manifest_path = mcp_manifest_path or (
        resolved_repo_root / "examples" / "mcp_capability_manifest.json"
    )
    resolved_adapter_evidence_path = adapter_evidence_path or (
        resolved_repo_root / ".change_assurance" / "capability_adapter_evidence.json"
    )
    known_limitations_text = _read_text_optional(
        resolved_repo_root / "KNOWN_LIMITATIONS_v0.1.md"
    )

    fabric_check, capability_count, capsule_count, read_model = _check_default_capability_fabric(
        clock=resolved_clock
    )
    checks = [
        fabric_check,
        _check_governed_record_surface(read_model, capability_count=capability_count),
        _check_mcp_manifest(resolved_manifest_path),
        _check_sandbox_contract(resolved_repo_root),
        _check_capability_adapter_evidence(resolved_adapter_evidence_path),
        _check_browser_adapter_closure(resolved_repo_root, known_limitations_text),
        _check_document_adapter_closure(resolved_repo_root, known_limitations_text),
        _check_voice_adapter_closure(resolved_repo_root, known_limitations_text),
        _check_email_calendar_adapter_closure(resolved_repo_root, known_limitations_text),
        *evaluate_deployment_publication(
            deployment_status_path=resolved_status_path,
            deployment_witness_path=resolved_witness_path,
        ),
    ]
    blockers = tuple(
        check.blocker_id for check in checks if not check.passed and check.blocker_id
    )
    ready = not blockers and all(check.passed for check in checks)
    readiness_level = _readiness_level(blockers)
    return GeneralAgentPromotionReadiness(
        ready=ready,
        readiness_level=readiness_level,
        checked_at=resolved_clock(),
        capability_count=capability_count,
        capsule_count=capsule_count,
        missing_closure_count=len(blockers),
        blockers=blockers,
        checks=tuple(checks),
    )


def evaluate_deployment_publication(
    *,
    deployment_status_path: Path,
    deployment_witness_path: Path,
) -> tuple[PromotionCheck, ...]:
    """Evaluate deployment witness and public health evidence for promotion."""
    status_text = _read_text_optional(deployment_status_path)
    deployment_state = _extract_field(status_text, DEPLOYMENT_STATE_PATTERN)
    public_health_endpoint = _extract_field(status_text, PUBLIC_HEALTH_PATTERN)
    witness_payload, witness_errors = load_witness_payload(deployment_witness_path)
    closure_errors = validate_publication_closure(
        deployment_status_text=status_text,
        witness_payload=witness_payload,
        witness_path=deployment_witness_path,
    )
    witness_published = bool(
        witness_payload
        and witness_payload.get("deployment_claim") == "published"
        and deployment_state == "published"
        and not witness_errors
        and not closure_errors
    )
    debt_applicable = bool(
        witness_payload
        and witness_payload.get("deployment_claim") == "published"
        and deployment_state == "published"
        and not witness_errors
    )
    runtime_debt_clear = (
        not debt_applicable or witness_payload.get("runtime_responsibility_debt_clear") is True
    )
    authority_debt_clear = (
        not debt_applicable or witness_payload.get("authority_responsibility_debt_clear") is True
    )
    witness_detail = (
        "deployment witness is published and publication closure validates"
        if witness_published
        else _join_detail(
            "deployment witness is not published",
            (
                f"state={deployment_state or 'missing'}",
                f"witness_errors={len(witness_errors)}",
                f"closure_errors={len(closure_errors)}",
            ),
        )
    )
    public_health_published = bool(
        witness_published
        and public_health_endpoint
        and public_health_endpoint != "not-declared"
        and public_health_endpoint.startswith("https://")
    )
    public_health_detail = (
        f"public health endpoint declared with validated witness: {public_health_endpoint}"
        if public_health_published
        else _join_detail(
            "public production health endpoint is not validated",
            (
                f"endpoint={public_health_endpoint or 'missing'}",
                f"witness_published={witness_published}",
                f"closure_errors={len(closure_errors)}",
            ),
        )
    )
    return (
        PromotionCheck(
            name="deployment witness publication",
            passed=witness_published,
            detail=witness_detail,
            evidence_refs=(
                str(deployment_status_path),
                str(deployment_witness_path),
            ),
            blocker_id="" if witness_published else "deployment_witness_not_published",
        ),
        PromotionCheck(
            name="deployment runtime responsibility debt",
            passed=runtime_debt_clear,
            detail=(
                "runtime responsibility debt is clear"
                if runtime_debt_clear
                else "deployment witness has runtime_responsibility_debt_clear=false"
            ),
            evidence_refs=(str(deployment_witness_path),),
            blocker_id=(
                "" if runtime_debt_clear else "deployment_runtime_responsibility_debt_present"
            ),
        ),
        PromotionCheck(
            name="deployment authority responsibility debt",
            passed=authority_debt_clear,
            detail=(
                "authority responsibility debt is clear"
                if authority_debt_clear
                else "deployment witness has authority_responsibility_debt_clear=false"
            ),
            evidence_refs=(str(deployment_witness_path),),
            blocker_id=(
                "" if authority_debt_clear else "deployment_authority_responsibility_debt_present"
            ),
        ),
        PromotionCheck(
            name="public production health endpoint",
            passed=public_health_published,
            detail=public_health_detail,
            evidence_refs=(str(deployment_status_path),),
            blocker_id="" if public_health_published else "production_health_not_declared",
        ),
    )


def _check_default_capability_fabric(
    *,
    clock: Callable[[], str],
) -> tuple[PromotionCheck, int, int, dict[str, Any]]:
    try:
        gate = build_default_capability_admission_gate(clock=clock)
        read_model = gate.read_model()
    except Exception:  # noqa: BLE001
        return (
            PromotionCheck(
                name="default governed capability fabric",
                passed=False,
                detail="default capability fabric failed to build",
                evidence_refs=("gateway.capability_fabric",),
                blocker_id="capability_fabric_not_closed",
            ),
            0,
            0,
            {},
        )
    domains = {
        str(domain_entry.get("domain", ""))
        for domain_entry in read_model.get("domains", ())
        if isinstance(domain_entry, dict)
    }
    missing_domains = tuple(sorted(REQUIRED_DOMAINS - domains))
    capability_count = int(read_model.get("capability_count", 0))
    capsule_count = int(read_model.get("capsule_count", 0))
    passed = not missing_domains and capability_count > 0 and capsule_count > 0
    detail = (
        f"default fabric exposes {capsule_count} capsules and {capability_count} capabilities"
        if passed
        else f"default fabric missing domains: {list(missing_domains)}"
    )
    return (
        PromotionCheck(
            name="default governed capability fabric",
            passed=passed,
            detail=detail,
            evidence_refs=("gateway.capability_fabric.build_default_capability_admission_gate",),
            blocker_id="" if passed else "capability_fabric_not_closed",
        ),
        capability_count,
        capsule_count,
        read_model,
    )


def _check_governed_record_surface(
    read_model: dict[str, Any],
    *,
    capability_count: int,
) -> PromotionCheck:
    records = read_model.get("governed_capability_records", ())
    if not isinstance(records, tuple):
        return PromotionCheck(
            name="tenant governed capability record surface",
            passed=False,
            detail="governed_capability_records must be an immutable tuple",
            evidence_refs=("mcoi_runtime.core.governed_capability_registry",),
            blocker_id="governed_record_surface_not_closed",
        )
    missing_field_records: list[str] = []
    raw_surface_records: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            missing_field_records.append("<non-object-record>")
            continue
        capability_id = str(record.get("capability_id", "<missing-capability-id>"))
        missing_fields = REQUIRED_GOVERNED_RECORD_FIELDS - set(record)
        raw_fields = RAW_TOOL_SURFACE_FIELDS & set(record)
        if missing_fields:
            missing_field_records.append(f"{capability_id}:{sorted(missing_fields)}")
        if raw_fields:
            raw_surface_records.append(f"{capability_id}:{sorted(raw_fields)}")
    passed = (
        capability_count > 0
        and len(records) == capability_count
        and not missing_field_records
        and not raw_surface_records
    )
    detail = (
        f"{len(records)} governed capability records expose bounded capability contracts"
        if passed
        else _join_detail(
            "governed capability record surface is incomplete",
            (
                f"records={len(records)} capabilities={capability_count}",
                f"missing_fields={missing_field_records[:3]}",
                f"raw_fields={raw_surface_records[:3]}",
            ),
        )
    )
    return PromotionCheck(
        name="tenant governed capability record surface",
        passed=passed,
        detail=detail,
        evidence_refs=("governed_capability_records",),
        blocker_id="" if passed else "governed_record_surface_not_closed",
    )


def _check_mcp_manifest(manifest_path: Path) -> PromotionCheck:
    result = validate_mcp_capability_manifest(manifest_path)
    passed = result.ok
    detail = (
        f"MCP manifest validates {len(result.capability_ids)} governed capability imports"
        if passed
        else f"MCP manifest validation errors: {list(result.errors)}"
    )
    return PromotionCheck(
        name="MCP governed import manifest",
        passed=passed,
        detail=detail,
        evidence_refs=(str(manifest_path),),
        blocker_id="" if passed else "mcp_manifest_not_closed",
    )


def _check_sandbox_contract(repo_root: Path) -> PromotionCheck:
    sandbox_path = repo_root / "gateway" / "sandbox_runner.py"
    sandbox_source = _read_text_optional(sandbox_path)
    required_markers = (
        "docker-rootless",
        "network: str = \"none\"",
        "read_only_rootfs: bool = True",
        "allowed_executables",
        "denied_executables",
        "forbidden_mounts",
        "SandboxExecutionReceipt",
    )
    missing_markers = tuple(marker for marker in required_markers if marker not in sandbox_source)
    passed = sandbox_path.exists() and not missing_markers
    detail = (
        "sandbox runner contract is present with no-network, read-only-rootfs, allowlist, and receipts"
        if passed
        else f"sandbox runner contract missing markers: {list(missing_markers)}"
    )
    return PromotionCheck(
        name="sandboxed computer/code runner contract",
        passed=passed,
        detail=detail,
        evidence_refs=(str(sandbox_path),),
        blocker_id="" if passed else "sandbox_runner_not_closed",
    )


def _check_capability_adapter_evidence(adapter_evidence_path: Path) -> PromotionCheck:
    if not adapter_evidence_path.exists():
        return PromotionCheck(
            name="capability adapter closure evidence",
            passed=False,
            detail="capability adapter evidence report is missing",
            evidence_refs=(str(adapter_evidence_path),),
            blocker_id="adapter_evidence_not_closed",
        )
    try:
        payload = json.loads(adapter_evidence_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return PromotionCheck(
            name="capability adapter closure evidence",
            passed=False,
            detail="capability adapter evidence JSON parse failed",
            evidence_refs=(str(adapter_evidence_path),),
            blocker_id="adapter_evidence_not_closed",
        )
    if not isinstance(payload, dict):
        return PromotionCheck(
            name="capability adapter closure evidence",
            passed=False,
            detail="capability adapter evidence root must be an object",
            evidence_refs=(str(adapter_evidence_path),),
            blocker_id="adapter_evidence_not_closed",
        )
    adapters = payload.get("adapters", ())
    adapter_ids = {
        str(adapter.get("adapter_id", ""))
        for adapter in adapters
        if isinstance(adapter, dict)
    }
    required_adapter_ids = {
        "browser.playwright",
        "document.production_parsers",
        "voice.openai",
        "communication.email_calendar_worker",
    }
    missing_adapters = tuple(sorted(required_adapter_ids - adapter_ids))
    blockers = tuple(str(blocker) for blocker in payload.get("blockers", ()))
    passed = payload.get("ready") is True and not blockers and not missing_adapters
    detail = (
        "capability adapter evidence closes browser, document, voice, and communication worker adapters"
        if passed
        else _join_detail(
            "capability adapter evidence is not closed",
            (
                f"ready={payload.get('ready')!r}",
                f"missing_adapters={list(missing_adapters)}",
                f"blockers={list(blockers)[:5]}",
            ),
        )
    )
    return PromotionCheck(
        name="capability adapter closure evidence",
        passed=passed,
        detail=detail,
        evidence_refs=(str(adapter_evidence_path),),
        blocker_id="" if passed else "adapter_evidence_not_closed",
    )


def _check_browser_adapter_closure(
    repo_root: Path,
    known_limitations_text: str,
) -> PromotionCheck:
    worker_path = repo_root / "gateway" / "browser_worker.py"
    adapter_path = repo_root / "gateway" / "browser_playwright_adapter.py"
    adapter_source = _read_text_optional(adapter_path)
    limitation_open = _limitation_open(
        known_limitations_text,
        "no browser adapter",
        "browser adapter not production-closed",
    )
    concrete_adapter = (
        adapter_path.exists()
        and "PlaywrightBrowserAdapter" in adapter_source
        and "sync_playwright" in adapter_source
        and "UnavailableBrowserAdapter" not in adapter_source
    )
    passed = worker_path.exists() and not limitation_open and concrete_adapter
    detail = (
        "real browser adapter closure evidence is present"
        if passed
        else _join_detail(
            "browser adapter is not closed",
            (
                f"worker_exists={worker_path.exists()}",
                f"known_limitation_open={limitation_open}",
                f"concrete_adapter={concrete_adapter}",
            ),
        )
    )
    return PromotionCheck(
        name="real browser adapter closure",
        passed=passed,
        detail=detail,
        evidence_refs=(str(worker_path), str(adapter_path), str(DEFAULT_KNOWN_LIMITATIONS_PATH)),
        blocker_id="" if passed else "browser_adapter_not_closed",
    )


def _check_document_adapter_closure(
    repo_root: Path,
    known_limitations_text: str,
) -> PromotionCheck:
    worker_path = repo_root / "gateway" / "document_worker.py"
    adapter_path = repo_root / "gateway" / "document_production_parsers.py"
    adapter_source = _read_text_optional(adapter_path)
    limitation_open = _limitation_open(
        known_limitations_text,
        "no document adapter",
        "document adapter not production-closed",
    )
    production_parser_markers = (
        "pypdf",
        "pdfplumber",
        "python_docx",
        "from docx",
        "openpyxl",
        "pptx",
    )
    concrete_adapter = (
        adapter_path.exists()
        and all(
            parser_class in adapter_source
            for parser_class in (
                "ProductionPDFParser",
                "ProductionDOCXParser",
                "ProductionXLSXParser",
                "ProductionPPTXParser",
            )
        )
        and any(marker in adapter_source.lower() for marker in production_parser_markers)
    )
    passed = worker_path.exists() and not limitation_open and concrete_adapter
    detail = (
        "real PDF/Office document adapter closure evidence is present"
        if passed
        else _join_detail(
            "document adapter is not closed",
            (
                f"worker_exists={worker_path.exists()}",
                f"known_limitation_open={limitation_open}",
                f"concrete_adapter={concrete_adapter}",
            ),
        )
    )
    return PromotionCheck(
        name="real document adapter closure",
        passed=passed,
        detail=detail,
        evidence_refs=(str(worker_path), str(adapter_path), str(DEFAULT_KNOWN_LIMITATIONS_PATH)),
        blocker_id="" if passed else "document_adapter_not_closed",
    )


def _check_voice_adapter_closure(
    repo_root: Path,
    known_limitations_text: str,
) -> PromotionCheck:
    worker_path = repo_root / "gateway" / "voice_worker.py"
    adapter_path = repo_root / "gateway" / "voice_openai_adapter.py"
    adapter_source = _read_text_optional(adapter_path)
    limitation_open = _limitation_open(
        known_limitations_text,
        "no voice adapter",
        "voice adapter not production-closed",
    )
    provider_markers = (
        "whisper",
        "speech_recognition",
        "texttospeech",
        "text_to_speech_client",
        "transcription",
    )
    concrete_adapter = (
        adapter_path.exists()
        and "OpenAIVoiceAdapter" in adapter_source
        and any(marker in adapter_source.lower() for marker in provider_markers)
        and "UnavailableVoiceAdapter" not in adapter_source
    )
    passed = worker_path.exists() and not limitation_open and concrete_adapter
    detail = (
        "real STT/TTS adapter closure evidence is present"
        if passed
        else _join_detail(
            "voice adapter is not closed",
            (
                f"worker_exists={worker_path.exists()}",
                f"known_limitation_open={limitation_open}",
                f"concrete_adapter={concrete_adapter}",
            ),
        )
    )
    return PromotionCheck(
        name="real voice adapter closure",
        passed=passed,
        detail=detail,
        evidence_refs=(str(worker_path), str(adapter_path), str(DEFAULT_KNOWN_LIMITATIONS_PATH)),
        blocker_id="" if passed else "voice_adapter_not_closed",
    )


def _check_email_calendar_adapter_closure(
    repo_root: Path,
    known_limitations_text: str,
) -> PromotionCheck:
    worker_path = repo_root / "gateway" / "email_calendar_worker.py"
    adapter_path = repo_root / "gateway" / "email_calendar_connector_adapters.py"
    adapter_source = _read_text_optional(adapter_path)
    limitation_open = _limitation_open(
        known_limitations_text,
        "email/calendar adapter not production-closed",
    )
    concrete_adapter = (
        adapter_path.exists()
        and "HttpEmailCalendarAdapter" in adapter_source
        and "build_email_calendar_adapter_from_env" in adapter_source
        and "UnavailableEmailCalendarAdapter" not in adapter_source
    )
    passed = worker_path.exists() and not limitation_open and concrete_adapter
    detail = (
        "real email/calendar connector adapter closure evidence is present"
        if passed
        else _join_detail(
            "email/calendar adapter is not closed",
            (
                f"worker_exists={worker_path.exists()}",
                f"known_limitation_open={limitation_open}",
                f"concrete_adapter={concrete_adapter}",
            ),
        )
    )
    return PromotionCheck(
        name="real email/calendar adapter closure",
        passed=passed,
        detail=detail,
        evidence_refs=(str(worker_path), str(adapter_path), str(DEFAULT_KNOWN_LIMITATIONS_PATH)),
        blocker_id="" if passed else "email_calendar_adapter_not_closed",
    )


def _readiness_level(blockers: tuple[str, ...]) -> str:
    if not blockers:
        return "production-general-agent"
    if FOUNDATION_BLOCKERS.isdisjoint(blockers):
        return "pilot-governed-core"
    return "not-ready"


def _limitation_open(text: str, *phrases: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _read_text_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _extract_field(text: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(text)
    if match is None:
        return ""
    return match.group(1).strip()


def _join_detail(prefix: str, fragments: tuple[str, ...]) -> str:
    return f"{prefix}: " + "; ".join(fragments)


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for general-agent promotion validation."""
    parser = argparse.ArgumentParser(
        description="Validate governed general-agent promotion readiness.",
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--deployment-status", default="")
    parser.add_argument("--deployment-witness", default="")
    parser.add_argument("--mcp-manifest", default="")
    parser.add_argument("--adapter-evidence", default="")
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print deterministic JSON readiness output.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when production promotion is blocked.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for general-agent promotion validation."""
    args = parse_args(argv)
    repo_root = Path(args.repo_root)
    readiness = validate_general_agent_promotion(
        repo_root=repo_root,
        deployment_status_path=Path(args.deployment_status) if args.deployment_status else None,
        deployment_witness_path=Path(args.deployment_witness) if args.deployment_witness else None,
        mcp_manifest_path=Path(args.mcp_manifest) if args.mcp_manifest else None,
        adapter_evidence_path=Path(args.adapter_evidence) if args.adapter_evidence else None,
    )
    if args.json:
        print(json.dumps(readiness.as_dict(), indent=2, sort_keys=True))
    elif readiness.ready:
        print(
            "GENERAL AGENT PROMOTION READY "
            f"capabilities={readiness.capability_count} capsules={readiness.capsule_count}"
        )
    else:
        print(
            "GENERAL AGENT PROMOTION BLOCKED "
            f"level={readiness.readiness_level} blockers={list(readiness.blockers)}"
        )
        for check in readiness.checks:
            state = "pass" if check.passed else "block"
            print(f"{state}: {check.name}: {check.detail}")
    if args.output:
        output_path = write_general_agent_promotion_readiness(readiness, Path(args.output))
        if not args.json:
            print(f"promotion_readiness_written: {output_path}")
    return 0 if readiness.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
