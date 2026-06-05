"""Tests for production Prometheus scrape probe receipt validation.

Purpose: prove production dashboard scrape receipts are schema-backed and
fail closed until live evidence is complete.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_product_dashboard_production_prometheus_scrape_probe_receipt.
Invariants:
  - AwaitingEvidence receipts can be structurally valid.
  - require-closed fails while production evidence remains open.
  - SolvedVerified receipts require all dashboard metric families.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.collect_product_dashboard_production_prometheus_scrape_probe import (
    HttpProbeResult,
    REQUIRED_METRIC_FAMILIES,
    collect_production_prometheus_scrape_probe,
)
from scripts.validate_product_dashboard_production_prometheus_scrape_probe_receipt import (
    PRODUCTION_SCRAPE_PROBE_SCHEMA_PATH,
    main,
    validate_product_dashboard_production_prometheus_scrape_probe_receipt,
    write_product_dashboard_production_probe_validation_report,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


FIXED_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _prometheus_text(families: tuple[str, ...] = REQUIRED_METRIC_FAMILIES) -> bytes:
    lines: list[str] = []
    for family in families:
        lines.append(f"# HELP {family} test metric")
        lines.append(f"# TYPE {family} gauge")
        lines.append(f"{family} 1.0")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _closed_receipt() -> dict[str, object]:
    def resolver(host: str) -> tuple[str, ...]:
        assert host == "api.mullusi.com"
        return ("203.0.113.10",)

    def http_getter(url: str) -> HttpProbeResult:
        if url.endswith("/metrics"):
            return HttpProbeResult(200, {"content-type": "text/plain"}, _prometheus_text(), True, "")
        if url.endswith("/health"):
            return HttpProbeResult(200, {"content-type": "application/json"}, b'{"status":"healthy"}', True, "")
        raise AssertionError(url)

    return collect_production_prometheus_scrape_probe(
        resolver=resolver,
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )


def _open_receipt() -> dict[str, object]:
    return collect_production_prometheus_scrape_probe(
        resolver=lambda host: (),
        now_utc=FIXED_NOW,
    )


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_production_scrape_probe_receipt_matches_public_schema(tmp_path: Path) -> None:
    receipt_path = tmp_path / "production_probe.json"
    receipt = _closed_receipt()
    _write_receipt(receipt_path, receipt)
    schema = _load_schema(PRODUCTION_SCRAPE_PROBE_SCHEMA_PATH)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["summary"]["production_claim_closed"] is True
    assert payload["summary"]["missing_family_count"] == 0
    assert payload["blockers"] == []


def test_validation_accepts_awaiting_evidence_without_closed_gate(tmp_path: Path) -> None:
    receipt_path = tmp_path / "production_probe.json"
    _write_receipt(receipt_path, _open_receipt())

    validation = validate_product_dashboard_production_prometheus_scrape_probe_receipt(
        receipt_path=receipt_path,
    )

    assert validation.valid is True
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.production_claim_closed is False
    assert validation.observed_family_count == 0
    assert _step(validation, "production gate").detail == "awaiting-evidence"
    assert _step(validation, "require closed").detail == "not-required"


def test_validation_require_closed_fails_for_open_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "production_probe.json"
    _write_receipt(receipt_path, _open_receipt())

    validation = validate_product_dashboard_production_prometheus_scrape_probe_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.closure_state == "production_scrape_awaiting_dns"
    assert _step(validation, "schema contract").passed is True
    assert _step(validation, "require closed").passed is False
    assert _step(validation, "require closed").detail == "awaiting-evidence"


def test_validation_accepts_closed_receipt_with_required_families(tmp_path: Path) -> None:
    receipt_path = tmp_path / "production_probe.json"
    validation_path = tmp_path / "production_probe_validation.json"
    _write_receipt(receipt_path, _closed_receipt())

    validation = validate_product_dashboard_production_prometheus_scrape_probe_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )
    write_product_dashboard_production_probe_validation_report(validation, validation_path)
    report = json.loads(validation_path.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.production_claim_closed is True
    assert validation.observed_family_count == len(REQUIRED_METRIC_FAMILIES)
    assert report["receipt_path"] == "provided_receipt"
    assert _step(validation, "required families").detail == "observed=16 missing=0 required=16"


def test_validation_accepts_closed_receipt_with_extra_prometheus_families(tmp_path: Path) -> None:
    receipt_path = tmp_path / "production_probe.json"

    def resolver(host: str) -> tuple[str, ...]:
        assert host == "api.mullusi.com"
        return ("203.0.113.10",)

    def http_getter(url: str) -> HttpProbeResult:
        if url.endswith("/metrics"):
            families = (*REQUIRED_METRIC_FAMILIES, "python_gc_objects_collected_total")
            return HttpProbeResult(200, {"content-type": "text/plain"}, _prometheus_text(families), True, "")
        if url.endswith("/health"):
            return HttpProbeResult(200, {"content-type": "application/json"}, b'{"status":"healthy"}', True, "")
        raise AssertionError(url)

    receipt = collect_production_prometheus_scrape_probe(
        resolver=resolver,
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    _write_receipt(receipt_path, receipt)

    validation = validate_product_dashboard_production_prometheus_scrape_probe_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.production_claim_closed is True
    assert validation.observed_family_count == len(REQUIRED_METRIC_FAMILIES) + 1
    assert _step(validation, "schema contract").passed is True
    assert _step(validation, "required families").passed is True
    assert _step(validation, "required families").detail == "observed=17 missing=0 required=16"


def test_validation_rejects_false_closed_receipt_missing_family(tmp_path: Path) -> None:
    receipt_path = tmp_path / "production_probe.json"
    receipt = _closed_receipt()
    metrics_probe = receipt["probe"]["metrics_http_probe"]  # type: ignore[index]
    metrics_probe["observed_metric_families"] = list(REQUIRED_METRIC_FAMILIES[:-1])  # type: ignore[index]
    metrics_probe["missing_metric_families"] = []  # type: ignore[index]
    _write_receipt(receipt_path, receipt)

    validation = validate_product_dashboard_production_prometheus_scrape_probe_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert _step(validation, "required families").passed is False
    assert _step(validation, "production gate").passed is True
    assert _step(validation, "require closed").passed is True


def test_validation_cli_writes_json_report(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "production_probe.json"
    validation_path = tmp_path / "production_probe_validation.json"
    _write_receipt(receipt_path, _open_receipt())

    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--output",
            str(validation_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    stdout_report = json.loads(captured.out)

    assert exit_code == 0
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert stdout_report["receipt_id"] == report["receipt_id"]
    assert stdout_report["steps"] == report["steps"]
    assert captured.err == ""


def _step(validation, name: str):
    return next(step for step in validation.steps if step.name == name)
