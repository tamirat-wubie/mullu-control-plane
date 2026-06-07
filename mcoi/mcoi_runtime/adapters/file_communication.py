"""Purpose: file-backed communication provider — writes messages to local JSON files.
Governance scope: communication adapter only.
Dependencies: communication contracts.
Invariants:
  - Messages are persisted as JSON files.
  - Delivery result is always produced.
  - No real email/SMS — local file output only.
"""

from __future__ import annotations

from typing import Callable

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from mcoi_runtime.contracts.communication import (
    CommunicationMessage,
    DeliveryResult,
    DeliveryStatus,
)
from mcoi_runtime.contracts.file_effects import FileEffectOperation, FileWriteReceipt
from mcoi_runtime.core.invariants import stable_identifier


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


_SAFE_MESSAGE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _safe_message_filename(message_id: str) -> str | None:
    """Return a flat JSON filename for message_id, or None if it is unsafe."""
    if "\0" in message_id or not _SAFE_MESSAGE_ID_PATTERN.fullmatch(message_id):
        return None
    posix_path = PurePosixPath(message_id)
    windows_path = PureWindowsPath(message_id)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or len(posix_path.parts) != 1
        or len(windows_path.parts) != 1
        or posix_path.name != message_id
        or windows_path.name != message_id
    ):
        return None
    return f"{message_id}.json"


def _build_file_write_receipt(
    *,
    delivery_id: str,
    message_id: str,
    file_path: Path,
    content: str,
    written_at: str,
) -> FileWriteReceipt:
    content_hash = _sha256_text(content)
    path_hash = _sha256_text(str(file_path.resolve()))
    receipt_id = stable_identifier(
        "file-write-receipt",
        {
            "delivery_id": delivery_id,
            "message_id": message_id,
            "path_hash": path_hash,
            "content_hash": content_hash,
        },
    )
    return FileWriteReceipt(
        receipt_id=receipt_id,
        operation=FileEffectOperation.WRITE,
        target_path_hash=path_hash,
        content_hash=content_hash,
        bytes_written=len(content.encode("utf-8")),
        atomic_replace=True,
        evidence_ref=f"file-write:{message_id}:{receipt_id}",
        written_at=written_at,
        metadata={"delivery_id": delivery_id, "message_id": message_id},
    )


class FileCommunicationAdapter:
    """Writes communication messages to local JSON files for operator review.

    Each message becomes a file: {outbox_path}/{message_id}.json
    This is the simplest real communication provider — no network, no email.
    """

    def __init__(self, *, outbox_path: Path, clock: Callable[[], str]) -> None:
        self._outbox = outbox_path
        self._clock = clock

    def deliver(self, message: CommunicationMessage) -> DeliveryResult:
        delivery_id = stable_identifier("file-delivery", {
            "message_id": message.message_id,
        })

        self._outbox.mkdir(parents=True, exist_ok=True)
        safe_filename = _safe_message_filename(message.message_id)

        # message_id is only validated as non-empty text. File-backed delivery
        # treats it as a filename, so require a single safe path component before
        # building the destination path.
        if safe_filename is None:
            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.FAILED,
                channel=message.channel,
                error_code="unsafe_message_id_path",
            )
        file_path = self._outbox / safe_filename

        if not file_path.resolve().is_relative_to(self._outbox.resolve()):
            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.FAILED,
                channel=message.channel,
                error_code="unsafe_message_id_path",
            )

        try:
            content = json.dumps(
                message.to_dict(),
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            )
            # Atomic write
            fd, tmp_path = tempfile.mkstemp(dir=str(self._outbox), suffix=".tmp")
            try:
                os.write(fd, content.encode("utf-8"))
                os.close(fd)
                fd = -1
                os.replace(tmp_path, str(file_path))
            except BaseException:
                if fd >= 0:
                    os.close(fd)
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

            delivered_at = self._clock()
            receipt = _build_file_write_receipt(
                delivery_id=delivery_id,
                message_id=message.message_id,
                file_path=file_path,
                content=content,
                written_at=delivered_at,
            )
            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.DELIVERED,
                channel=message.channel,
                delivered_at=delivered_at,
                metadata={
                    "file_path": str(file_path),
                    "file_write_receipt": receipt.to_json_dict(),
                },
            )
        except OSError as exc:
            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.FAILED,
                channel=message.channel,
                error_code=f"file_write_error:{type(exc).__name__}",
            )
