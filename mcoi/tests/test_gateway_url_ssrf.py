"""SSRF guard for the launch-gateway deployment-witness gateway URL.

collect_launch_gateway_pilot_deployment_witness fetches the caller-supplied
gateway_url (the witness collector issues GET requests to {gateway}/gateway/witness
etc. via urllib and reflects the HTTP status + a response digest back into the
witness). _validate_gateway_base_url previously checked only scheme / credentials /
path, so a caller could point the gateway at http://169.254.169.254 or an internal
address and make the server probe internal services (semi-blind SSRF).

It now rejects private / loopback / link-local / cloud-metadata destinations via
the unified SSRF policy. Unresolvable hosts are permitted (the collector's own
connect fails closed on them), so a legitimate-but-currently-unresolvable gateway
is not hard-rejected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.organization_kernel import _validate_gateway_base_url
from mcoi_runtime.governance.network.ssrf import is_private_host


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254",          # AWS/Azure/DO IMDS
        "http://169.254.169.254/",
        "http://127.0.0.1",                # loopback
        "http://10.0.0.5",                 # RFC 1918
        "http://192.168.1.10",
        "http://172.16.5.5",
        "http://localhost",
        "http://metadata.google.internal",  # GCP IMDS
        "https://[::1]",                   # IPv6 loopback
    ],
)
def test_gateway_url_rejects_private_and_metadata(url):
    with pytest.raises(HTTPException) as exc:
        _validate_gateway_base_url(url)
    assert exc.value.status_code == 400


def test_gateway_url_allows_public_ip_literal():
    # Public IP literal resolves without a DNS query and is accepted.
    assert _validate_gateway_base_url("https://93.184.216.34") == "https://93.184.216.34"


def test_gateway_url_allows_unresolvable_host():
    # Reserved .example TLD does not resolve; permitted (not an SSRF target,
    # the collector's own connect fails on it).
    assert _validate_gateway_base_url("https://gateway.example") == "https://gateway.example"


def test_block_unresolvable_param_semantics():
    # Default (webhook posture) fail-closes on unresolvable; the gateway path
    # opts out, but real SSRF targets stay blocked either way.
    assert is_private_host("gateway.example") is True
    assert is_private_host("gateway.example", block_unresolvable=False) is False
    assert is_private_host("169.254.169.254", block_unresolvable=False) is True
    assert is_private_host("127.0.0.1", block_unresolvable=False) is True
