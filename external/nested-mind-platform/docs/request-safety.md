# Request Safety

The API runtime now applies a request safety gate before authorization and mutation.

```text
HTTP request
  → declared body-size check
  → per-principal/path rate window
  → authorization
  → handler
```

## Configuration

```bash
MIND_MAX_BODY_BYTES=65536
MIND_RATE_LIMIT_REQUESTS=60
MIND_RATE_LIMIT_WINDOW_SECONDS=60
```

The limiter is intentionally simple and in-memory. It protects a single runtime process from accidental or low-grade abuse. It is not a distributed quota system.

## Rate key

```text
authenticated request → principal:<principal-id>
anonymous request     → anonymous:<path>
```

This avoids storing bearer tokens in the rate-limit map.

## Headers

Successful responses include:

```text
x-ratelimit-limit
x-ratelimit-remaining
x-ratelimit-reset
```

## Fracture

```text
- The limiter resets on process restart.
- Multi-replica deployments need an external shared limiter.
- Body limits depend on declared or extracted body size; upstream proxies should enforce the same limit.
```
