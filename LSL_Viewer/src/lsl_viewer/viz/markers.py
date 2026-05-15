# @file
# @brief Calibration-event marker overlay for time-domain panels.
##
# The viewer reads marker events from an NDJSON file written by
# Handgrip_Calibration. It is a read-only overlay aid; the viewer never owns
# or modifies calibration decisions.
##
# Design notes (v0.4.0 - ECharts):
# - _load_marker_events() is unchanged (pure NDJSON loader).
# - refresh_marker_cache() is unchanged (mtime-gated cache).
# - get_marker_x_positions() replaces the old Plotly shape helper.
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from hydra.utils import to_absolute_path
from omegaconf import DictConfig

from lsl_viewer.types import ViewerState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure NDJSON loader  (unchanged from original)
# ---------------------------------------------------------------------------

def _load_marker_events(cfg: DictConfig) -> list[dict[str, Any]]:
    # @brief Parse the optional calibration NDJSON marker file.
    # @param cfg Hydra configuration.
    # @return List of parsed marker-event dicts.
    if not cfg.calibration_markers.enabled:
        return []
    raw_path = cfg.calibration_markers.events_ndjson_path
    if not raw_path:
        return []
    path = Path(to_absolute_path(str(raw_path)))
    if not path.exists():
        log.debug("Calibration marker file not found: %s", path)
        return []

    allowed = set(cfg.calibration_markers.draw_events)
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = record.get("payload", record)
        event = payload.get("event", record.get("event"))
        if allowed and event not in allowed:
            continue
        ts = record.get(
            "lsl_timestamp", record.get("lsl_ts", payload.get("lsl_ts"))
        )
        if ts is None:
            continue
        try:
            events.append({"event": str(event), "lsl_ts": float(ts), "payload": payload})
        except (TypeError, ValueError):
            continue
    return events


# ---------------------------------------------------------------------------
# Cache management  (unchanged from v0.3.0 — fixes per-frame re-read bug)
# ---------------------------------------------------------------------------

def refresh_marker_cache(state: ViewerState, cfg: DictConfig) -> None:
    # @brief Reload marker events only when the NDJSON file mtime has changed.
    # @param state Viewer state with cache fields.
    # @param cfg Hydra configuration.
    if not cfg.calibration_markers.enabled:
        if state.marker_events:
            state.marker_events = []
        return

    raw_path = cfg.calibration_markers.events_ndjson_path
    if not raw_path:
        state.marker_events = []
        return

    path = Path(to_absolute_path(str(raw_path)))
    if not path.exists():
        state.marker_events = []
        return

    mtime = path.stat().st_mtime
    if mtime != state.marker_file_mtime:
        state.marker_events = _load_marker_events(cfg)
        state.marker_file_mtime = mtime
        log.debug(
            "Calibration markers reloaded: %d events from %s",
            len(state.marker_events),
            path,
        )


# ---------------------------------------------------------------------------
# ECharts marker position helper  (replaces Plotly get_marker_shapes)
# ---------------------------------------------------------------------------

def get_marker_x_positions(
    state: ViewerState,
    cfg: DictConfig,
    t_end: float,
) -> list[float]:
    # @brief Return relative x-axis positions for calibration marker lines.
    # @param state ViewerState with cached marker events.
    # @param cfg Hydra configuration.
    # @param t_end Current end-of-window LSL timestamp.
    # @return Relative x positions for visible marker lines.
    window_s = float(cfg.viewer.window_seconds)
    positions: list[float] = []
    for item in state.marker_events:
        x = float(item["lsl_ts"]) - t_end
        if -window_s <= x <= 0.5:
            positions.append(x)
    return positions
