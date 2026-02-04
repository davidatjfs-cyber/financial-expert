from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import BinaryIO

from core.db import get_app_data_dir


def get_upload_dir() -> Path:
    d = get_app_data_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_uploaded_file(*, filename: str, data: bytes) -> Path:
    ext = Path(filename).suffix.lower() if filename else ""
    safe_name = f"{int(time.time())}_{uuid.uuid4().hex}{ext}"
    path = get_upload_dir() / safe_name
    path.write_bytes(data)
    return path


def save_uploaded_file_stream(*, filename: str, fileobj: BinaryIO, max_bytes: int | None = None) -> Path:
    ext = Path(filename).suffix.lower() if filename else ""
    safe_name = f"{int(time.time())}_{uuid.uuid4().hex}{ext}"
    path = get_upload_dir() / safe_name

    written = 0
    with path.open("wb") as f:
        while True:
            chunk = fileobj.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if max_bytes is not None and written > max_bytes:
                try:
                    f.close()
                except Exception:
                    pass
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise ValueError("upload_too_large")
            f.write(chunk)
    return path
