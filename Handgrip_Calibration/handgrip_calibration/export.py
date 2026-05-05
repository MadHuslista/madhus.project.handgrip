"""Small file-format helpers used across the calibration pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable


def ensure_dir(path: str | Path) -> Path:
    """Create a directory and return it as a :class:`Path`."""

    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def json_default(value: Any) -> Any:
    """JSON serializer for dataclasses and pathlib paths."""

    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def append_ndjson(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    """Append rows to an NDJSON file.

    NDJSON is used for event/quality logs because it is append-friendly and can
    be tailed while a session is running.
    """

    path = Path(path)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")


def read_ndjson(path: str | Path) -> list[dict[str, Any]]:
    """Read an NDJSON file into a list of dictionaries."""

    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid NDJSON at {path}:{line_no}: {exc}") from exc
    return rows


def write_json(path: str | Path, data: Any) -> None:
    """Write stable, human-readable JSON."""

    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=json_default)
        fh.write("\n")
