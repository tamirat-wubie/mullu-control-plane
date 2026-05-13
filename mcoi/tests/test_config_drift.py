"""Tests for Phase 231C — Config Drift Detector."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.config_drift import ConfigDriftDetector, DriftItem, DriftReport, DriftSeverity


class TestConfigDriftDetector:
    def test_no_drift_when_matching(self):
        d = ConfigDriftDetector()
        d.set_expected({"key": "val", "num": 42})
        report = d.detect({"key": "val", "num": 42})
        assert not report.has_drift

    def test_detects_value_change(self):
        d = ConfigDriftDetector()
        d.set_expected({"key": "original"})
        report = d.detect({"key": "changed"})
        assert report.has_drift
        assert len(report.drifts) == 1
        assert report.drifts[0].key == "key"
        assert report.drifts[0].message == "Configuration value changed"
        assert "key" not in report.drifts[0].message

    def test_detects_missing_key(self):
        d = ConfigDriftDetector()
        d.set_expected({"required": "yes"})
        report = d.detect({})
        assert report.has_drift
        assert report.drifts[0].message == "Missing configuration key"
        assert "required" not in report.drifts[0].message

    def test_detects_unexpected_key(self):
        d = ConfigDriftDetector()
        d.set_expected({})
        report = d.detect({"extra": "surprise"})
        assert report.has_drift
        assert report.drifts[0].severity == DriftSeverity.INFO
        assert report.drifts[0].message == "Unexpected configuration key"
        assert "extra" not in report.drifts[0].message

    def test_secret_key_is_critical(self):
        d = ConfigDriftDetector()
        d.set_expected({"api_secret": "abc"})
        report = d.detect({"api_secret": "changed"})
        assert report.drifts[0].severity == DriftSeverity.CRITICAL

    def test_password_key_is_critical(self):
        d = ConfigDriftDetector()
        d.set_expected({"db_password": "x"})
        report = d.detect({})
        assert report.drifts[0].severity == DriftSeverity.CRITICAL

    def test_severity_override(self):
        d = ConfigDriftDetector()
        d.set_expected({"log_level": "info"})
        d.set_severity("log_level", DriftSeverity.INFO)
        report = d.detect({"log_level": "debug"})
        assert report.drifts[0].severity == DriftSeverity.INFO

    def test_to_dict(self):
        d = ConfigDriftDetector()
        d.set_expected({"a": 1})
        report = d.detect({"a": 2})
        data = report.to_dict()
        assert data["has_drift"] is True
        assert data["total_drifts"] == 1

    def test_input_shapes_are_bounded(self):
        d = ConfigDriftDetector()
        with pytest.raises(ValueError, match="config"):
            d.set_expected("bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="config key"):
            d.set_expected({"": "value"})
        with pytest.raises(ValueError, match="actual"):
            d.detect("bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="severity"):
            d.set_severity("a", "critical")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="key"):
            d.set_severity("", DriftSeverity.INFO)

    def test_report_and_item_validation(self):
        item = DriftItem(
            key="a",
            expected=1,
            actual=2,
            severity=DriftSeverity.WARNING,
            message="changed",
        )
        report = DriftReport(drifts=[item], scanned_at=1.0)
        assert report.drifts == (item,)
        with pytest.raises(ValueError, match="drifts"):
            DriftReport(drifts="bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="severity"):
            DriftItem(key="a", expected=1, actual=2, severity="warning")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="scanned_at"):
            DriftReport(drifts=[item], scanned_at=True)  # type: ignore[arg-type]

    def test_summary(self):
        d = ConfigDriftDetector()
        d.set_expected({"a": 1})
        d.detect({"a": 1})
        s = d.summary()
        assert s["total_scans"] == 1
        assert s["total_drifts_found"] == 0

    def test_critical_count(self):
        d = ConfigDriftDetector()
        d.set_expected({"api_key": "x", "name": "y"})
        report = d.detect({"api_key": "changed", "name": "changed"})
        assert report.critical_count == 1  # only api_key is critical
