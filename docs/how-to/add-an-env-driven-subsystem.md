# Add an env-driven subsystem to the control plane

<!-- TYPE: How-to -->
<!-- AUDIENCE: developer adding a new persistence-backed subsystem -->

> **In one box:** When you add a subsystem that picks where it stores data
> based on an environment variable (a file on disk when the variable is set, an
> in-memory store when it isn't), put that decision in its own small module
> instead of inline in the server's startup file. This page gives you the exact
> shape to copy so every subsystem behaves the same way and is easy to test.
>
> Assumes you know Python and have the [control plane](../GLOSSARY.md#control-plane)
> running locally once.

---

## The goal and the finished state

You have a new store (e.g. `WidgetReceiptStore` with a file-backed
`FileWidgetReceiptStore`) and an environment variable
(`MULLU_WIDGET_RECEIPT_STORE_PATH`) that decides whether to persist to disk.

When you're done:

- A new `mcoi/mcoi_runtime/app/widget_integration.py` owns the env-to-store
  decision and validates the hosted path **before** constructing anything.
- `mcoi/mcoi_runtime/app/server.py` wires the subsystem in **3–5 lines** by
  calling your helper — no inline `os.environ.get → Path → FileStore` branch.
- A `tests/test_widget_control_plane_integration.py` proves the selection and
  validation without importing `server.py`'s module-level wiring.

This keeps the [fail-closed](../GLOSSARY.md#invariant) precondition contract in
one place and makes a regression (e.g. "file store not selected when the env is
set") catchable by a unit test.

## Step 1 — Create the integration module

Copy the shape of
[`finance_approval_integration.py`](../../mcoi/mcoi_runtime/app/finance_approval_integration.py)
(the shortest exemplar). Three pieces:

1. A module-level constant for the env var name.
2. A frozen `@dataclass` capturing the **startup posture** (the resulting
   `store` plus `path` and `persistent` flags — never just the bare store, so
   callers and tests can assert what was chosen).
3. A `select_*` (or `bootstrap_*` / `mount_*`) entrypoint that returns that
   dataclass, plus a thin `validate_*_store_path` that delegates to the shared
   validator.

```python
from mcoi_runtime.app._integration_paths import validate_hosted_store_path

WIDGET_RECEIPT_STORE_PATH_ENV = "MULLU_WIDGET_RECEIPT_STORE_PATH"


@dataclass(frozen=True)
class WidgetReceiptStoreBootstrap:
    store: WidgetReceiptStore
    path: str
    persistent: bool


def select_widget_receipt_store(runtime_env: Mapping[str, str]) -> WidgetReceiptStoreBootstrap:
    raw_value = runtime_env.get(WIDGET_RECEIPT_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return WidgetReceiptStoreBootstrap(store=WidgetReceiptStore(), path="", persistent=False)
    path = validate_widget_receipt_store_path(str(raw_value).strip())
    return WidgetReceiptStoreBootstrap(store=FileWidgetReceiptStore(path), path=str(path), persistent=True)


def validate_widget_receipt_store_path(store_path: str | Path) -> Path:
    return validate_hosted_store_path(
        store_path,
        env_name=WIDGET_RECEIPT_STORE_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
```

## Step 2 — Use the shared path validator, don't hand-roll one

`mcoi/mcoi_runtime/app/_integration_paths.py` is the **single source of truth**
for hosted-store preconditions. Always delegate to
`validate_hosted_store_path(...)`; never re-implement the absolute /
suffix / parent-exists / writable checks. Its parameters:

| Parameter | Meaning |
| --- | --- |
| `env_name` | The env var name; used verbatim in every error message. |
| `kind` | `"file"` for a single-file store, `"directory"` for a store that owns a directory tree (e.g. note-memory). |
| `required_suffix` | `".json"`, `".jsonl"`, or omit for no suffix check. Must include the leading dot. Ignored when `kind="directory"`. |

It guarantees, for both kinds: absolute path, parent directory already exists
and is a directory, the writable target (the path if it exists, else its
parent) is writable, and the target is the right type (a file store rejects a
directory target; a directory store rejects a regular file).

`env_flag(value)` in the same module is the single source of truth for boolean
flags (the truthy set is `{1, true, yes, on, enabled}`, case-insensitive and
trimmed) — use it for any `MULLU_*_ENABLED`-style switch.

## Step 3 — Wire it into `server.py`

Replace what would have been an inline branch with the helper call:

```python
from mcoi_runtime.app.widget_integration import select_widget_receipt_store

_widget_bootstrap = select_widget_receipt_store(os.environ)
widget_receipt_store = _widget_bootstrap.store
deps.set("widget_receipt_store", widget_receipt_store)
```

If your subsystem also needs a restore-on-startup step or a save-on-shutdown
hook, model it the way
[`artifact_lineage_integration.py`](../../mcoi/mcoi_runtime/app/artifact_lineage_integration.py)
does: return the restore result and an optional `save_on_shutdown` callable on
the bootstrap dataclass, and let `server.py` register the callback. If it has a
conditional background worker, split into separate `bootstrap_*` and
`maybe_start_*` helpers the way
[`temporal_scheduler_integration.py`](../../mcoi/mcoi_runtime/app/temporal_scheduler_integration.py)
does, and accept injected factories so the worker path is testable without
starting a thread.

## Step 4 — Test the helper, not the server

Add `tests/test_widget_control_plane_integration.py` asserting:

- unset env → in-memory store, `persistent is False`, `path == ""`
- blank/whitespace env → same as unset
- env set to a valid path → file store, `persistent is True`
- the four validator failure modes: relative path, wrong/missing suffix,
  directory target, missing parent

Because the helper is a pure function of its `env` mapping, none of these tests
import `server.py`. See
[`test_finance_approval_control_plane_integration.py`](../../tests/test_finance_approval_control_plane_integration.py)
for the canonical set.

## Checklist before you open the PR

- [ ] Module is named `app/<subsystem>_integration.py`.
- [ ] `validate_*` delegates to `validate_hosted_store_path` — no hand-rolled checks.
- [ ] Any boolean flag uses the shared `env_flag`.
- [ ] Bootstrap is a frozen dataclass exposing the posture, not a bare store.
- [ ] `server.py` calls the helper; no inline `os.environ.get → FileStore` branch remains.
- [ ] Test file covers selection + all validator failure modes and does not import `server.py`.

---

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| Understand the big picture in plain words | [Plain-English Overview](../explain/PLAIN_ENGLISH.md) |
| Look up a confusing word | [Glossary](../GLOSSARY.md) |
| See the whole documentation map | [Start Here](../START_HERE.md) |
| See the shared validator's exact contract | [`_integration_paths.py`](../../mcoi/mcoi_runtime/app/_integration_paths.py) |
| Turn on the first such subsystem (the governed swarm) | [README → Governed Swarm Runtime](../../README.md) |

← Back to [Start Here](../START_HERE.md)
