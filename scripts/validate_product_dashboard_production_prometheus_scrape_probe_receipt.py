#!/usr/bin/env python3
"""Validate product dashboard production Prometheus scrape probe receipts.

Purpose: gate public dashboard production closure on schema-backed scrape
evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scrape probe receipt schema, scrape probe collector constants,
and repository schema validation helpers.
Invariants:
  - AwaitingEvidence receipts may be structurally valid.
  - SolvedVerified requires DNS, health, metrics, and all required families.
  - The optional require-closed gate fails closed until production evidence
    is complete.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_product_dashboard_production_prometheus_scrape_probe import (  # noqa: E402
    DEFAULT_OUTPUT,
    REQUIRED_METRIC_FAMILIES,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "product_dashboard_production_prometheus_scrape_probe_validation.json"
)
PRODUCTION_SCRAPE_PROBE_SCHEMA_PATH = (
    REPO_ROOT
    / "schemas"
    / "product_dashboard_production_prometheus_scrape_probe_receipt.schema.json"
)
RECEIPT_ID_PATTERN = re.compile(
    r"^product-dashboard-production-prometheus-scrape-probe-[0-9a-f]{16}$"
)
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "password", "secret")


@dataclass(frozen=True, slots=True)
class ProductDashboardProductionProbeValidationStep:
    """One production scrape probe validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ProductDashboardProductionProbeValidation:
    """Structured validation report for one production scrape probe receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    closure_state: str
    production_claim_closed: bool
    observed_family_count: int
    missing_family_count: int
    steps: tuple[ProductDashboardProductionProbeValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_product_dashboard_production_prometheus_scrape_probe_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = PRODUCTION_SCRAPE_PROBE_SCHEMA_PATH,
    require_closed: bool = False,
) -> ProductDashboardProductionProbeValidation:
    """Validate one production scrape probe receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_required_families(payload),
        _check_production_gate(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("summary"))
    return ProductDashboardProductionProbeValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        closure_state=_bounded_text(summary.get("closure_state")),
        production_claim_closed=summary.get("production_claim_closed") is True,
        observed_family_count=_bounded_int(summary.get("observed_family_count")),
        missing_family_count=_bounded_int(summary.get("missing_family_count")),
        steps=steps,
    )


def write_product_dashboard_production_probe_validation_report(
    validation: ProductDashboardProductionProbeValidation,
    output_path: Path,
) -> Path:
    """Write one local production scrape probe validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read production scrape probe receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("production scrape probe receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("production scrape probe receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> ProductDashboardProductionProbeValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return ProductDashboardProductionProbeValidationStep(
            "schema contract",
            False,
            "schema-read-failed",
        )
    errors = _validate_schema_instance(schema, payload)
    return ProductDashboardProductionProbeValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> ProductDashboardProductionProbeValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return ProductDashboardProductionProbeValidationStep(
        "receipt id",
        passed,
        "valid" if passed else "invalid",
    )


def _check_required_families(
    payload: dict[str, Any],
) -> ProductDashboardProductionProbeValidationStep:
    metrics_probe = _object(_object(payload.get("probe")).get("metrics_http_probe"))
    observed = set(_text_items(metrics_probe.get("observed_metric_families")))
    missing = set(_text_items(metrics_probe.get("missing_metric_families")))
    required = set(REQUIRED_METRIC_FAMILIES)
    passed = required <= observed and missing == required - observed
    detail = f"observed={len(observed)} missing={len(missing)} required={len(required)}"
    return ProductDashboardProductionProbeValidationStep("required families", passed, detail)


def _check_production_gate(
    payload: dict[str, Any],
) -> ProductDashboardProductionProbeValidationStep:
    proof_state = payload.get("proof_state")
    solver_outcome = payload.get("solver_outcome")
    probe = _object(payload.get("probe"))
    dns_resolution = _object(probe.get("dns_resolution"))
    metrics_probe = _object(probe.get("metrics_http_probe"))
    health_probe = _object(probe.get("health_http_probe"))
    summary = _object(payload.get("summary"))
    closed = summary.get("production_claim_closed") is True
    complete_evidence = (
        dns_resolution.get("status") == "resolved"
        and _bounded_int(dns_resolution.get("resolver_result_count")) > 0
        and metrics_probe.get("request_reached_endpoint") is True
        and metrics_probe.get("status_code") == 200
        and not _text_items(metrics_probe.get("missing_metric_families"))
        and health_probe.get("request_reached_endpoint") is True
        and health_probe.get("status_code") == 200
    )
    if closed:
        passed = proof_state == "Pass" and solver_outcome == "SolvedVerified" and complete_evidence
        detail = "closed" if passed else "closed-with-incomplete-evidence"
    else:
        passed = proof_state == "Fail" and solver_outcome == "AwaitingEvidence"
        detail = "awaiting-evidence" if passed else "open-state-mismatch"
    return ProductDashboardProductionProbeValidationStep("production gate", passed, detail)


def _check_secret_boundary(
    payload: dict[str, Any],
) -> ProductDashboardProductionProbeValidationStep:
    serialized = json.dumps(payload, sort_keys=True).casefold()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return ProductDashboardProductionProbeValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked-terms={len(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> ProductDashboardProductionProbeValidationStep:
    if not require_closed:
        return ProductDashboardProductionProbeValidationStep(
            "require closed",
            True,
            "not-required",
        )
    summary = _object(payload.get("summary"))
    passed = summary.get("production_claim_closed") is True and payload.get("solver_outcome") == "SolvedVerified"
    return ProductDashboardProductionProbeValidationStep(
        "require closed",
        passed,
        "closed" if passed else "awaiting-evidence",
    )


def _bounded_receipt_path(receipt_path: Path) -> str:
    if receipt_path == DEFAULT_OUTPUT:
        return "examples/product_dashboard_production_prometheus_scrape_probe_receipt.json"
    return "provided_receipt"


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    if RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None:
        return str(receipt_id)
    return "invalid"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_items(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str))


def _bounded_int(value: Any) -> int:
    if isinstance(value, int):
        return max(value, 0)
    return 0


def _bounded_text(value: Any) -> str:
    return str(value) if isinstance(value, str) and value else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse production scrape probe receipt validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate a product dashboard production Prometheus scrape probe receipt."
    )
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(PRODUCTION_SCRAPE_PROBE_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for production scrape probe receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_product_dashboard_production_prometheus_scrape_probe_receipt(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
            require_closed=args.require_closed,
        )
    except RuntimeError:
        print("production scrape probe receipt validation failed")
        return 1

    output_path = write_product_dashboard_production_probe_validation_report(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {output_path}")
        print(f"receipt: {validation.receipt_path}")
        print(f"receipt_id: {validation.receipt_id}")
        print(f"valid: {str(validation.valid).lower()}")
        for step in validation.steps:
            print(
                f"step: {step.name} "
                f"passed={str(step.passed).lower()} "
                f"detail={step.detail}"
            )
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
