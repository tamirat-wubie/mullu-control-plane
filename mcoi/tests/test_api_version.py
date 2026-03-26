"""Phase 210C — API versioning tests."""

import pytest
from mcoi_runtime.core.api_version import APIVersionManager, EndpointDescriptor

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestAPIVersionManager:
    def test_register_endpoint(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        mgr.register_endpoint(EndpointDescriptor(method="GET", path="/health", name="Health", version="1.0"))
        assert mgr.endpoint_count == 1

    def test_release_version(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        mgr.register_endpoint(EndpointDescriptor(method="GET", path="/health", name="Health", version="1.0"))
        v = mgr.release_version("1.0.0")
        assert v.status == "active"
        assert len(v.endpoints) == 1
        assert mgr.current_version == "1.0.0"

    def test_freeze_version(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        mgr.register_endpoint(EndpointDescriptor(method="GET", path="/health", name="Health", version="1.0"))
        v = mgr.freeze_version("1.0.0")
        assert v.status == "frozen"
        assert v.frozen_at

    def test_deprecate_endpoint(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        mgr.register_endpoint(EndpointDescriptor(method="GET", path="/old", name="Old", version="1.0"))
        assert mgr.deprecate_endpoint("/old", "GET", "2027-01-01") is True
        deps = mgr.deprecated_endpoints()
        assert len(deps) == 1
        assert deps[0].sunset_date == "2027-01-01"

    def test_deprecate_nonexistent(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        assert mgr.deprecate_endpoint("/fake", "GET", "2027-01-01") is False

    def test_endpoints_by_phase(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        mgr.register_endpoint(EndpointDescriptor(method="GET", path="/a", name="A", version="1.0", added_in_phase=200))
        mgr.register_endpoint(EndpointDescriptor(method="GET", path="/b", name="B", version="1.0", added_in_phase=205))
        assert len(mgr.endpoints_by_phase(200)) == 1

    def test_summary(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        mgr.register_endpoint(EndpointDescriptor(method="GET", path="/x", name="X", version="1.0"))
        mgr.release_version("1.0.0")
        s = mgr.summary()
        assert s["current_version"] == "1.0.0"
        assert s["total_endpoints"] == 1
        assert s["versions_released"] == 1

    def test_bulk_register(self):
        mgr = APIVersionManager(clock=FIXED_CLOCK)
        mgr.register_endpoints_bulk([
            EndpointDescriptor(method="GET", path="/a", name="A", version="1.0"),
            EndpointDescriptor(method="POST", path="/b", name="B", version="1.0"),
        ])
        assert mgr.endpoint_count == 2
