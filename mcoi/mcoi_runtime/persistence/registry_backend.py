"""Purpose: registry state persistence to a single JSON file.
Governance scope: persistence layer registry storage only.
Dependencies: persistence errors, registry store types, contracts _base.
Invariants: preserves lifecycle state explicitly, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import is_dataclass, fields as dc_fields
from hashlib import sha256
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts._base import thaw_value
from mcoi_runtime.core.registry_store import RegistryEntry, RegistryLifecycle, RegistryStore

from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _atomic_write(path: Path, content: str) -> None:
    """Write content to a file atomically via temp-file-then-rename."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("registry write failed", exc)) from exc


def _entry_value_to_dict(value: Any) -> dict[str, Any]:
    """Convert a dataclass value to a serializable dict, thawing frozen values."""
    if is_dataclass(value) and not isinstance(value, type):
        result: dict[str, Any] = {}
        for f in dc_fields(value):
            result[f.name] = thaw_value(getattr(value, f.name))
        return result
    raise CorruptedDataError("registry entry value must be a dataclass instance")


def _serialize_entry(entry: RegistryEntry[Any]) -> dict[str, Any]:
    """Serialize a single RegistryEntry to a plain dict."""
    return {
        "entry_id": entry.entry_id,
        "entry_type": entry.entry_type,
        "lifecycle": str(entry.lifecycle),
        "value": _entry_value_to_dict(entry.value),
    }


class RegistryBackend:
    """Persists a RegistryStore to a single registry.json file.

    The file contains a JSON object with an "entries" key mapping entry_id
    to entry data. Lifecycle state is preserved explicitly as a string.
    """

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _registry_path(self) -> Path:
        return self._base_path / "registry.json"

    def save_registry(self, store: RegistryStore[Any]) -> str:
        if not isinstance(store, RegistryStore):
            raise PersistenceError("store must be a RegistryStore instance")

        entries = store.list()
        serialized: dict[str, Any] = {}
        for entry in entries:
            serialized[entry.entry_id] = _serialize_entry(entry)

        payload = {"entries": serialized}
        content = _deterministic_json(payload)
        content_hash = sha256(content.encode("ascii", "ignore")).hexdigest()

        _atomic_write(self._registry_path(), content)

        return content_hash

    def load_registry(self) -> RegistryStore[Any]:
        path = self._registry_path()
        if not path.exists():
            raise CorruptedDataError("registry file not found")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed registry file", exc)) from exc

        if not isinstance(raw, dict) or "entries" not in raw:
            raise CorruptedDataError("registry file must contain an 'entries' key")

        entries_raw = raw["entries"]
        if not isinstance(entries_raw, dict):
            raise CorruptedDataError("'entries' must be a JSON object")

        store: RegistryStore[Any] = RegistryStore()

        for entry_id, entry_data in sorted(entries_raw.items()):
            if not isinstance(entry_data, dict):
                raise CorruptedDataError("registry entry must be a JSON object")

            try:
                lifecycle_str = entry_data["lifecycle"]
                lifecycle = RegistryLifecycle(lifecycle_str)
            except (KeyError, ValueError) as exc:
                raise CorruptedDataError(_bounded_store_error("invalid registry lifecycle", exc)) from exc

            try:
                entry_type = entry_data["entry_type"]
                value_data = entry_data["value"]
            except KeyError as exc:
                raise CorruptedDataError(
                    _bounded_store_error("registry entry missing required field", exc)
                ) from exc

            if not isinstance(value_data, dict):
                raise CorruptedDataError("registry entry value must be a JSON object")

            # Store raw value dict wrapped in a SimpleNamespace-like frozen dataclass
            # so it passes the dataclass check in RegistryEntry.__post_init__.
            # We use a _RawRegistryValue to hold the deserialized dict fields.
            from dataclasses import make_dataclass, field as dc_field

            field_defs = [(k, type(v), dc_field(default=v)) for k, v in value_data.items()]
            RawValue = make_dataclass("RawValue", field_defs, frozen=True)
            value_instance = RawValue()

            entry = RegistryEntry(
                entry_id=entry_id,
                entry_type=entry_type,
                value=value_instance,
                lifecycle=lifecycle,
            )
            store.add(entry)

        return store

    def registry_exists(self) -> bool:
        return self._registry_path().exists()
