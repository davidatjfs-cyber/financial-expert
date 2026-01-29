from __future__ import annotations

import time
import uuid
from pathlib import Path

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
