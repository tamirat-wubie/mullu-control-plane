# Projection Policy

Projection is the `Γ` boundary. It exposes useful meaning without leaking mutation authority or private state.

```text
Γ := project(𝕊, policy) → view
```

## Scopes

The initial platform exposes three scopes:

```text
summary   identity, kind, history length, child summaries, no state cells
public    public state cells with sensitive keys omitted
internal  full state cells for trusted operators
```

API examples:

```bash
curl 'http://localhost:8080/minds/root?scope=summary'
curl 'http://localhost:8080/minds/root?scope=public'
curl 'http://localhost:8080/minds/root?scope=internal'
```

## Default public policy

The default public policy omits keys matching these classes:

```text
exact keys:      password, api_key, access_token, refresh_token
prefixes:        auth., internal., private., secret.
contains:        password, secret, token, credential
```

The default is omission, not redaction. Omission prevents exposing sensitive key names as side-channel evidence.

## Required hardening

Before exposing public projections outside local development, add:

```text
per-actor authorization
per-field projection rules
purpose-bound projection requests
projection audit events
schema-level public/private annotations
negative tests for known secret patterns
```
