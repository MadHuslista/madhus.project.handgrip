"""Small file-format helpers used across the calibration pipeline."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable


def ensure_dir(path: str | Path) -> Path:
    # @brief Create a directory path if needed.
    #  @param path Directory path to create.
    #  @return Path object for the created/existing directory.
    """Create a directory and return it as a :class:`Path`."""

    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def json_default(value: Any) -> Any:
    # @brief Convert non-JSON-native objects into JSON-compatible values.
    #  @param value Value to serialize.
    #  @return JSON-compatible representation.
    """JSON serializer for dataclasses and pathlib paths."""

    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def append_ndjson(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    # @brief Append records to an NDJSON log file.
    #  @param path NDJSON output file path.
    #  @param rows Iterable of row dictionaries to append.
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
    # @brief Read an NDJSON file into Python dictionaries.
    #  @param path NDJSON input file path.
    #  @return Parsed row dictionaries, or an empty list when the file is missing.
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
    # @brief Write a stable, human-readable JSON file.
    #  @param path Output JSON path.
    #  @param data Serializable data object.
    """Write stable, human-readable JSON."""

    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=json_default)
        fh.write("\n")
