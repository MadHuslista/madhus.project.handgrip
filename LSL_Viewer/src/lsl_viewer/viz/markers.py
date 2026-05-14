"""
Calibration-event marker overlay for time-domain panels.

The viewer reads marker events from an NDJSON file written by
Handgrip_Calibration.  It is a **read-only** overlay aid; the viewer
never owns or modifies calibration decisions.

Design notes (v0.4.0 — ECharts)
---------------------------------
* ``_load_marker_events()`` is unchanged (pure NDJSON loader).
* ``refresh_marker_cache()`` is unchanged (mtime-gated cache, fixes the
  per-frame re-read bug present in the original Matplotlib implementation).
* ``get_marker_shapes()`` (Plotly layout shape dicts) is replaced by
  ``get_marker_x_positions()`` which returns a plain ``list[float]``.
  Each time-domain panel passes this list to ``_apply_markline()`` in
  ``charts.py``, which attaches it as an ECharts ``markLine`` entry on
  the first series — no separate shape layer required.
"""
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
    """
    Parse the optional calibration NDJSON marker file.

    Returns an empty list when markers are disabled, the path is unset,
    or the file does not exist.  Malformed lines are silently skipped.
    """
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
    """
    Reload marker events only when the NDJSON file mtime has changed.

    Safe and cheap to call once per render cycle.
    """
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
    """
    Return relative x-axis positions for calibration marker lines.

    Pure function — reads only ``state.marker_events`` and ``cfg``.

    Each position is ``event.lsl_ts - t_end`` (seconds relative to the
    current window end), clipped to the visible window.  The list is
    consumed by ``charts._apply_markline()`` which attaches it as an
    ECharts ``markLine`` on the first series of each time-domain panel.

    Parameters
    ----------
    state:
        ``ViewerState`` with a populated ``marker_events`` cache.
    cfg:
        Hydra config; ``viewer.window_seconds`` defines the visible range.
    t_end:
        Current end-of-window LSL timestamp (seconds).

    Returns
    -------
    List of relative x positions (float).  Empty when no events fall
    within the current window.

    """
    window_s = float(cfg.viewer.window_seconds)
    positions: list[float] = []
    for item in state.marker_events:
        x = float(item["lsl_ts"]) - t_end
        if -window_s <= x <= 0.5:
            positions.append(x)
    return positions
