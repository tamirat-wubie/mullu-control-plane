"""Purpose: verify local file effect receipt contract invariants.
Governance scope: filesystem mutation evidence typing only.
Dependencies: pytest and file effect receipt contracts.
Invariants: receipts bind path/content hashes, byte counts, and atomic write evidence without raw file content.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.file_effects import FileEffectOperation, FileWriteReceipt


def _receipt(**overrides: object) -> FileWriteReceipt:
    defaults = {
        "receipt_id": "file-write-receipt-1",
        "operation": FileEffectOperation.WRITE,
        "target_path_hash": "path-hash",
        "content_hash": "content-hash",
        "bytes_written": 12,
        "atomic_replace": True,
        "evidence_ref": "file-write:msg-1:receipt-1",
        "written_at": "2026-03-19T00:00:00+00:00",
        "metadata": {"message_id": "msg-1", "delivery_id": "delivery-1"},
    }
    defaults.update(overrides)
    return FileWriteReceipt(**defaults)


def test_file_write_receipt_accepts_hashed_evidence() -> None:
    receipt = _receipt()

    assert receipt.operation is FileEffectOperation.WRITE
    assert receipt.target_path_hash == "path-hash"
    assert receipt.content_hash == "content-hash"
    assert receipt.bytes_written == 12
    assert receipt.atomic_replace is True


def test_file_write_receipt_rejects_missing_evidence_ref() -> None:
    with pytest.raises(ValueError, match="^evidence_ref must be a non-empty string$") as exc_info:
        _receipt(evidence_ref="")

    message = str(exc_info.value)
    assert "evidence_ref" in message
    assert "file-write:msg-1:receipt-1" not in message
    assert "non-empty" in message


def test_file_write_receipt_rejects_invalid_byte_count_and_atomic_flag() -> None:
    with pytest.raises(ValueError, match="^bytes_written must be a non-negative integer$"):
        _receipt(bytes_written=-1)

    with pytest.raises(ValueError, match="^atomic_replace must be a boolean$"):
        _receipt(atomic_replace="yes")

    valid_empty = _receipt(bytes_written=0)
    assert valid_empty.bytes_written == 0
