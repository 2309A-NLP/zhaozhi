"""Shared JSON storage helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from rag_qa_system.backend.utils.logger import get_logger


LOGGER = get_logger("rag.storage")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        LOGGER.exception("storage_load_failed | path=%s", path)
        return default


def save_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)
