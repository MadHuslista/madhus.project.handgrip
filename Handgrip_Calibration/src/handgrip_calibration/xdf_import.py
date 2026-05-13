"""Optional XDF import support.

Live sessions are recorded to CSV by this package because CSV is easy to inspect
and robust on lab machines. If you also record with LabRecorder/XDF, this module
can convert the relevant target/reference/marker streams into the same canonical
session files used by the offline fitting pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .config_schema import AppConfig
from .export import append_ndjson, ensure_dir
from .lsl_io import resolve_channel_indices

log = logging.getLogger(__name__)


class XDFImportError(RuntimeError):
    """Raised when an XDF file cannot be imported into the canonical schema."""


def _import_pyxdf() -> Any:
    try:
        import pyxdf
    except Exception as exc:  # pragma: no cover - optional dependency
        raise XDFImportError("pyxdf is required for XDF import. Install with: python -m pip install -e '.[xdf]'") from exc
    return pyxdf


def _stream_name(stream: dict[str, Any]) -> str:
    return stream.get("info", {}).get("name", [""])[0]


def _stream_type(stream: dict[str, Any]) -> str:
    return stream.get("info", {}).get("type", [""])[0]


def _channel_labels(stream: dict[str, Any]) -> list[str]:
    info = stream.get("info", {})
    count = int(info.get("channel_count", [0])[0] or 0)
    labels: list[str] = []
    try:
        channels = info["desc"][0]["channels"][0]["channel"]
        for idx, ch in enumerate(channels):
            labels.append(ch.get("label", [f"ch{idx}"])[0])
    except Exception:
        labels = []
    if len(labels) != count:
        labels = [f"ch{i}" for i in range(count)]
    return labels


def _find_stream(streams: list[dict[str, Any]], *, name: str, stream_type: str | None = None) -> dict[str, Any] | None:
    for stream in streams:
        if _stream_name(stream) == name:
            return stream
    if stream_type:
        for stream in streams:
            if _stream_type(stream) == stream_type:
                return stream
    return None


def _write_numeric_stream(stream: dict[str, Any], output_csv: Path, channel_map: dict[str, list[str | int]]) -> None:
    labels = _channel_labels(stream)
    indices = resolve_channel_indices(labels, channel_map)
    time_stamps = stream.get("time_stamps", [])
    series = stream.get("time_series", [])
    rows: list[dict[str, Any]] = []
    for timestamp, sample in zip(time_stamps, series):
        row: dict[str, Any] = {"timestamp_lsl": float(timestamp)}
        for canonical, idx in indices.items():
            row[canonical] = sample[idx]
        for i, value in enumerate(sample):
            row[f"channel_{i}"] = value
        rows.append(row)
    pd.DataFrame(rows).to_csv(output_csv, index=False)


def _write_marker_stream(stream: dict[str, Any], output_events: Path, *, session_id: str) -> None:
    rows: list[dict[str, Any]] = []
    for timestamp, sample in zip(stream.get("time_stamps", []), stream.get("time_series", [])):
        raw = sample[0] if isinstance(sample, (list, tuple)) else sample
        try:
            row = json.loads(raw)
        except Exception:
            row = {"schema": "handgrip_marker.v1", "event": str(raw), "session_id": session_id}
        row.setdefault("session_id", session_id)
        row.setdefault("lsl_time", float(timestamp))
        rows.append(row)
    append_ndjson(output_events, rows)


def import_xdf(xdf_path: str | Path, session_dir: str | Path, config: AppConfig, *, session_id: str | None = None) -> Path:
    """Import an XDF file into canonical target/reference CSV + marker NDJSON files."""

    pyxdf = _import_pyxdf()
    xdf_path = Path(xdf_path)
    session_dir = ensure_dir(session_dir)
    streams, _header = pyxdf.load_xdf(str(xdf_path))
    target_stream = _find_stream(streams, name=config.streams["target"].name, stream_type=config.streams["target"].stream_type)
    reference_stream = _find_stream(streams, name=config.streams["reference"].name, stream_type=config.streams["reference"].stream_type)
    marker_stream = _find_stream(streams, name=config.markers.stream_name, stream_type=config.markers.stream_type)
    if target_stream is None:
        raise XDFImportError(f"Could not find target stream {config.streams['target'].name!r} in {xdf_path}")
    if reference_stream is None:
        raise XDFImportError(f"Could not find reference stream {config.streams['reference'].name!r} in {xdf_path}")
    _write_numeric_stream(target_stream, session_dir / "target.csv", config.streams["target"].channel_map)
    _write_numeric_stream(reference_stream, session_dir / "reference.csv", config.streams["reference"].channel_map)
    if marker_stream is not None:
        _write_marker_stream(marker_stream, session_dir / "events.ndjson", session_id=session_id or session_dir.name)
    log.info("XDF import complete: %s", session_dir)
    return session_dir
