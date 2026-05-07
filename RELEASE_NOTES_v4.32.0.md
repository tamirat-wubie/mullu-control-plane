# Mullu Platform v4.32.0 — Unified SSRF Policy + DNS-Rebinding Defense (Audit F9, F10)

**Release date:** TBD
**Codename:** Pin
**Migration required:** No for runtime callers; tests using unresolvable webhook URL placeholders need real-resolvable hostnames

---

## What this release is

Closes audit fractures **F9** (webhook SSRF gaps) and **F10** (DNS-rebinding window in `http_connector`).

Pre-v4.32 the platform shipped two SSRF policies side-by-side:
- `adapters/http_connector._is_private_host` — strong: hostname blocklist + RFC 1918 prefixes + DNS resolution + redirect block
- `core/webhook_system._is_private_url` — weak: `{"localhost", "metadata.google.internal"}` + prefix check. **No DNS resolution. No IPv6 link-local. No Azure / Alibaba / DigitalOcean metadata.**

A subscription with hostname `attacker.example.com` resolving to `169.254.169.254` was silently accepted by `subscribe()` and would deliver to AWS IMDS at runtime. v4.32 unifies both surfaces.

For F10: even the strong `http_connector` had a TOCTOU window between its DNS lookup and urllib's. v4.32 closes it by pinning the resolved IP for the actual connect while preserving the original hostname for TLS SNI.

---

## What is new in v4.32.0

### `core/ssrf_policy.py` — single source of truth

Combined the strong policy with broader cloud metadata coverage:

| What | Pre-v4.32 webhook | Pre-v4.32 http_connector | v4.32 unified |
|---|---|---|---|
| AWS / DO / Linode IMDS (169.254.169.254) | prefix only | exact + prefix | exact + prefix + DNS |
| GCP IMDS (`metadata.google.internal`) | exact | not blocked | exact |
| Azure IMDS (`metadata.azure.com`) | not blocked | not blocked | exact |
| Alibaba ECS (`metadata.aliyun.com`, `metadata`) | not blocked | not blocked | exact |
| IPv6 link-local (`fe80::*`) | not blocked | partial | prefix + DNS |
| IPv6 ULA (`fc00::/7`) | not blocked | partial | prefix + DNS |
| DNS resolution | **no** | yes | **yes** |
| Multi-A mixed (split-horizon block) | n/a | catches | catches |

Public API:
```python
def is_private_ip(ip_str: str) -> bool: ...
def is_private_host(host: str) -> bool: ...
def is_private_url(url: str) -> bool: ...
def resolve_and_check(url: str) -> tuple[bool, str | None]: ...
```

`resolve_and_check` returns the resolved public IP for callers that can pin it.

### Webhook unified

```python
# core/webhook_system.py
from mcoi_runtime.core.ssrf_policy import is_private_url as _is_private_url
```

Plus a re-check at delivery time, not just registration:
```python
if _is_private_url(sub.url):
    continue  # skip this delivery; subscription stays registered
```

The subscription stays registered when delivery is blocked — operators can audit failures via `delivery_history`. Defense against DNS-rebinding by an attacker controlling the operator's subscribed domain.

### http_connector: DNS-pinned connect

`adapters/http_connector.py` uses `resolve_and_check` to get both the verdict and the IP:
```python
is_private, pinned_ip = _resolve_and_check(normalized_url)
if is_private or pinned_ip is None:
    return self._failure(..., "blocked_private_address")
opener = _build_pinned_opener(pinned_ip)
with opener.open(req, timeout=...) as response:
    ...
```

`_PinnedHTTPSConnection` connects to `(pinned_ip, port)` directly — bypassing urllib's own DNS lookup and closing the rebinding window. TLS SNI uses the original hostname via `wrap_socket(server_hostname=self.host)` so cert validation works.

Defense-in-depth at socket level:
```python
peer_ip = sock.getpeername()[0]
if _is_private_ip(peer_ip):
    sock.close()
    raise OSError(f"blocked_private_address_at_connect:{peer_ip}")
```

`_NoRedirectHandler` is registered alongside the pinned handlers, so 3xx redirects to private space remain blocked.

---

## Compatibility

- All v4.31.x runtime callers work unchanged. Both surfaces keep the same import names; they now resolve to the shared module
- **Stricter webhook URL acceptance.** Pre-v4.32 unresolvable placeholders (`http://x`, `http://hook`) were silently accepted at subscribe. v4.32 rejects them. **Tests using such placeholders need real-resolvable hostnames.** This PR updates `test_webhook_system.py`, `test_agent_workflow.py`, `test_server_phase205.py`, `test_http_connector.py`, `test_http_connector_ssrf.py`, `test_http_connector_read_timeout.py`
- Cloud metadata hostnames (Azure DNS alias, Alibaba) that pre-v4.32 webhook accepted are now rejected — operators with intentionally-internal webhooks see new 400s at subscribe time, which is the correct posture for SSRF defense

---

## Test counts

57 new tests in [`test_v4_29_ssrf_unified.py`](mullu-control-plane/mcoi/tests/test_v4_29_ssrf_unified.py) (filename retained from initial scope; substance is v4.32):

- `is_private_ip` blocks/allows + fail-closed (3 tests)
- `is_private_host` static blocklists, prefix blocks, empty, fail-closed-on-resolve, DNS-private rebinding leg, multi-A mixed (8)
- `resolve_and_check` for DNS pinning across all metadata clouds + parse failure (7)
- `is_private_url` webhook wrapper for all 5 IMDS endpoints + IPv6 link-local + ULA (3)
- Webhook integration: subscribe rejects metadata, IPv6 link-local; delivery re-check catches rebinding (3)
- http_connector integration: `_resolve_and_check` exercised, pinned opener constructs correctly (2)
- Plus parametrized variants (~31)

All 45 existing http_connector + webhook tests pass after URL placeholder updates.

---

## Production deployment guidance

### Watch for new error codes

- `blocked_private_address_at_connect:<ip>` — defense-in-depth catch at socket level. Non-zero count = active DNS rebinding attempt (or misconfigured DNS)
- `blocked_private_address` (existing) — first-leg block at SSRF check time

### Webhook subscriptions

Customers with internal-network webhooks (`http://internal-svc:8080/...`) will see new rejection at subscribe time — that's correct. Move those to a public-facing reverse proxy or use a different mechanism (in-process callbacks, internal queue).

### Operators of forked stores

If you have a custom `BudgetStore`-style fork with hand-rolled SSRF policy, migrate to import from `core/ssrf_policy`. Future SSRF-relevant code should import from there rather than rolling its own list.

---

## Production-readiness gap status

```
✅ F2 atomic budget                   — v4.27.0
✅ F3 audit checkpoint anchor         — v4.28.0
✅ F11 atomic rate limit              — v4.29.0
✅ F15 atomic hash chain append       — v4.30.0
✅ F4 atomic audit append             — v4.31.0
✅ F9 + F10 unified SSRF + pin        — v4.32.0
⏳ F5 / F6 env + tenant binding       — small, similar to F16 pattern
⏳ F7 governance module sprawl        — architectural
⏳ F8 MAF substrate disconnect        — README mitigated; PyO3 weeks
⏳ F12 DB write throughput ceiling    — needs connection pool
⏳ JWT hardening                      — small, defense-in-depth
```

14 of 17 audit fractures fully closed. Remaining 3 either need external infra (F12) or are small contained pieces.

---

## Honest assessment

v4.32 is moderate (~150 LoC source + ~370 LoC tests). Most of the source diff is the `_PinnedHTTPSConnection` / `_PinnedHTTPHandler` machinery — plumbing through urllib's awkward connection-class injection point. The actual security fix is one DNS lookup that runs both as the SSRF check AND as the pinned-IP source for the connect.

The structural lesson: when two modules implement "the same" policy independently, they will drift. F9 was that drift surfacing. The v4.32 fix is mechanical (extract module, import everywhere); the discipline is that future SSRF-relevant code must import from `core/ssrf_policy` rather than rolling its own list.

**We recommend:**
- Upgrade in place. v4.32 is additive for runtime callers
- Test code using placeholder webhook URLs (`http://x`, `http://hook`) needs real-resolvable hostnames (this PR updates the obvious ones)
- Watch for `blocked_private_address_at_connect:*` errors in production
- After deploy, scan any private forks for hand-rolled SSRF policies; migrate them to import from `core/ssrf_policy`
