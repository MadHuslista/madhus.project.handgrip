"""Calibration-event marker overlay for time-domain axes.

The viewer reads marker events from an NDJSON file written by
Handgrip_Calibration.  It is a **read-only** overlay aid; the viewer
never owns or modifies calibration decisions.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from hydra.utils import to_absolute_path
from lsl_viewer.types import FigureHandles
from omegaconf import DictConfig

log = logging.getLogger(__name__)


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


def draw_marker_overlays(
    handles: FigureHandles, cfg: DictConfig, t_end: float
) -> int:
    """Draw vertical calibration-event markers on the time-domain axes.

    Existing marker artists from previous frames are removed before drawing.

    Parameters
    ----------
    handles:
        Figure handles (state mutated: ``marker_artists`` key).
    cfg:
        Hydra config; ``calibration_markers`` section controls behaviour.
    t_end:
        Current end-of-window LSL timestamp (seconds); used to compute the
        x-position of each event relative to the window edge.

    Returns
    -------
    Number of markers drawn in the current frame.
    """
    for artist in handles.state.get("marker_artists", []):
        try:
            artist.remove()
        except Exception:
            pass
    handles.state["marker_artists"] = []

    marker_events = _load_marker_events(cfg)
    if not marker_events:
        return 0

    window_s = cfg.viewer.window_seconds
    axes = [handles.axes[k] for k in ["target_raw", "reference_raw", "target_filtered", "overlay"]]
    count = 0
    for item in marker_events:
        x = float(item["lsl_ts"]) - t_end
        if x < -window_s or x > 0.5:
            continue
        for ax in axes:
            handles.state["marker_artists"].append(
                ax.axvline(x, linestyle=":", linewidth=0.8, alpha=0.45)
            )
        count += 1
    return count
