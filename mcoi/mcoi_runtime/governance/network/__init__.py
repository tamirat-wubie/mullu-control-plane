"""Outbound network policy — SSRF defense + webhook delivery.

Modules:
  - ``ssrf`` — unified SSRF policy: cloud metadata blocklists
    (AWS / Azure / GCP / Alibaba / DO IMDS), IPv6 link-local,
    DNS resolution with fail-closed posture, IP pinning
  - ``webhook`` — outbound webhook delivery; SSRF re-check at
    delivery time defends against DNS rebinding by an
    attacker who controls the operator's subscribed domain

Both modules share one policy module (audit F9 + F10, v4.32).
Future SSRF-relevant code MUST import from ``ssrf`` rather
than rolling its own list.
"""
