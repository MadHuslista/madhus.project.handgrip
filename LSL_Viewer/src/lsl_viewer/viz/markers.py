"""Calibration-event marker overlay for time-domain panels.

The viewer reads marker events from an NDJSON file written by
Handgrip_Calibration.  It is a **read-only** overlay aid; the viewer
never owns or modifies calibration decisions.

Design changes from original
-----------------------------
* ``_load_marker_events()`` is unchanged (pure loader).
* ``draw_marker_overlays()`` (Matplotlib axvline) is replaced by
  ``get_marker_shapes()`` which returns Plotly shape dicts.
* Result is cached in :class:`~lsl_viewer.types.ViewerState` to prevent
  re-reading the NDJSON file on every frame (was a bug in the original).
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
# Pure NDJSON loader  (unchanged from original viz/markers.py)
# ---------------------------------------------------------------------------

def _load_marker_events(cfg: DictConfig) -> list[dict[str, Any]]:
    """Parse the optional calibration NDJSON marker file.

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
# Cache management (fixes per-frame re-read bug from original)
# ---------------------------------------------------------------------------

def refresh_marker_cache(state: ViewerState, cfg: DictConfig) -> None:
    """Reload marker events if the NDJSON file has changed since last read.

    Only reads from disk when the file modification time differs from the
    cached value.  Calling this once per render cycle is safe and cheap.
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
# Plotly shape builder (replaces axvline drawing in original)
# ---------------------------------------------------------------------------

def get_marker_shapes(
    state: ViewerState,
    cfg: DictConfig,
    t_end: float,
    xaxis_refs: list[str],
) -> list[dict[str, Any]]:
    """Return Plotly layout shape dicts for calibration markers.

    Each event produces one vertical dashed line per time-domain axis
    (``target_raw``, ``reference_raw``, ``target_filtered``, ``overlay``).

    Parameters
    ----------
    state:
        ViewerState with cached ``marker_events``.
    cfg:
        Hydra config; ``calibration_markers.draw_events`` controls which
        event types are drawn.
    t_end:
        Current end-of-window LSL timestamp (seconds).
    xaxis_refs:
        List of Plotly xaxis reference strings (e.g. ``['x', 'x2', 'x3', 'x4']``)
        identifying the panels that should receive marker lines.

    Returns
    -------
    List of Plotly shape dicts suitable for ``fig.layout.shapes``.
    """
    shapes: list[dict[str, Any]] = []
    window_s = float(cfg.viewer.window_seconds)

    for item in state.marker_events:
        x_pos = float(item["lsl_ts"]) - t_end
        if x_pos < -window_s or x_pos > 0.5:
            continue
        for xref in xaxis_refs:
            shapes.append(
                dict(
                    type="line",
                    x0=x_pos,
                    x1=x_pos,
                    y0=0,
                    y1=1,
                    xref=xref,
                    yref="paper",
                    line=dict(color="gray", dash="dot", width=0.8),
                    opacity=0.45,
                )
            )
    return shapes
