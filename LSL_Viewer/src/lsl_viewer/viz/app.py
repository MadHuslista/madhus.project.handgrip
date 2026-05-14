"""NiceGUI application factory and event-loop runners.

This module replaces ``runners/live.py`` and ``runners/replay.py``.
The ``while/plt.pause()`` event loops are replaced by NiceGUI ``ui.timer()``
callbacks, which run in the asyncio event loop without stealing OS focus.

Root cause fix
--------------
``plt.pause()`` called ``QWidget.raise_()`` + ``QWidget.activateWindow()``
on every frame via the Qt5Agg backend, stealing keyboard focus at 20 Hz.
NiceGUI renders in a browser tab served over localhost; no native OS window
is created, so focus stealing is architecturally impossible.
"""
from __future__ import annotations

import logging
import time

import numpy as np
from nicegui import app as ng_app
from nicegui import ui
from omegaconf import DictConfig

from lsl_viewer.core.replay import window_from_replay
from lsl_viewer.core.stream import build_streams, fetch_live_window
from lsl_viewer.types import (
    DualReplayData,
    DualWindow,
    ReferenceWindow,
    TargetWindow,
    ViewerState,
)
from lsl_viewer.viz.charts import ChartHandles, build_chart_handles, update_charts
from lsl_viewer.viz.panels import build_page_layout

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Live-mode helpers  (migrated from runners/live.py)
# ---------------------------------------------------------------------------

def _slice_dual_after_cutoffs(
    window: DualWindow,
    state: ViewerState,
) -> DualWindow | None:
    """Remove samples that predate the live-reset cutoff timestamps.

    After the user presses the clear key, only samples newer than the cutoff
    are rendered so previously buffered data does not reappear.
    """
    target = window.target
    reference = window.reference

    if target is not None and state.target_cutoff_s is not None:
        mask = target.timestamps_s > float(state.target_cutoff_s)
        target = (
            TargetWindow(
                target.timestamps_s[mask],
                target.device_clock_us[mask],
                target.raw[mask],
                target.filtered[mask],
            )
            if np.any(mask)
            else None
        )
    if reference is not None and state.reference_cutoff_s is not None:
        mask = reference.timestamps_s > float(state.reference_cutoff_s)
        reference = (
            ReferenceWindow(
                reference.timestamps_s[mask],
                reference.rs485_clock[mask],
                reference.raw[mask],
            )
            if np.any(mask)
            else None
        )

    if target is None and reference is None:
        return None
    return DualWindow(target=target, reference=reference)


def _establish_live_cutoff(
    target_stream: object,
    reference_stream: object,
    cfg: DictConfig,
    target_layout: object,
    reference_layout: object,
    state: ViewerState,
) -> None:
    """Record the latest buffered timestamps as post-clear cutoffs.

    After a manual clear or pause-resume, only samples arriving after these
    cutoffs are rendered so the display starts fresh.
    """
    latest = fetch_live_window(
        target_stream, reference_stream, cfg, target_layout, reference_layout
    )
    if latest is not None and latest.target is not None and latest.target.timestamps_s.size:
        state.target_cutoff_s = float(np.nanmax(latest.target.timestamps_s))
    else:
        state.target_cutoff_s = None

    if (
        latest is not None
        and latest.reference is not None
        and latest.reference.timestamps_s.size
    ):
        state.reference_cutoff_s = float(np.nanmax(latest.reference.timestamps_s))
    else:
        state.reference_cutoff_s = None

    log.info(
        "Live render cutoffs reset: target=%s reference=%s",
        state.target_cutoff_s,
        state.reference_cutoff_s,
    )
    state.live_reset_from_latest_window = False


# ---------------------------------------------------------------------------
# Live-mode timer callback
# ---------------------------------------------------------------------------

def _live_tick(
    cfg: DictConfig,
    target_stream: object,
    reference_stream: object,
    target_layout: object,
    reference_layout: object,
    state: ViewerState,
    ch: ChartHandles,
    validate_reference: bool,
) -> None:
    """Called by ``ui.timer`` every ``refresh_s`` seconds in live mode."""
    if state.live_paused:
        return

    if state.live_reset_from_latest_window:
        _establish_live_cutoff(
            target_stream, reference_stream, cfg, target_layout, reference_layout, state
        )
        return

    live = fetch_live_window(
        target_stream, reference_stream, cfg, target_layout, reference_layout
    )
    if live is None:
        return

    live = _slice_dual_after_cutoffs(live, state)
    if live is None:
        return

    update_charts(
        ch,
        live,
        state,
        cfg,
        source_name=f"{target_stream.name} + {reference_stream.name}",  # type: ignore[attr-defined]
        source_type="dual_native_lsl",
        mode="live_ref" if validate_reference else "live",
        target_new_samples=int(target_stream.n_new_samples),  # type: ignore[attr-defined]
        reference_new_samples=int(reference_stream.n_new_samples),  # type: ignore[attr-defined]
    )


# ---------------------------------------------------------------------------
# Replay-mode timer callback
# ---------------------------------------------------------------------------

def _replay_tick(
    cfg: DictConfig,
    replay_data: DualReplayData,
    replay_start_wall: list[float],   # mutable container [start_time]
    state: ViewerState,
    ch: ChartHandles,
    mode: str,
) -> None:
    """Called by ``ui.timer`` every ``refresh_s`` seconds in replay mode."""
    if state.replay_finished:
        return

    if state.replay_paused:
        return

    replay_speed = max(1e-9, float(cfg.replay.speed))
    start_offset_s = max(0.0, float(cfg.replay.start_offset_s))
    loop = bool(cfg.replay.loop)
    duration_s = replay_data.duration_s

    elapsed_s = (
        time.monotonic() - replay_start_wall[0]
    ) * replay_speed + start_offset_s

    if loop and duration_s > 0:
        elapsed_s = elapsed_s % duration_s
    elif elapsed_s > duration_s:
        elapsed_s = duration_s

    window = window_from_replay(replay_data, elapsed_s, cfg.viewer.window_seconds)
    if window is not None:
        progress = (
            f"time   : {elapsed_s:.2f}/{duration_s:.2f} s\n"
            f"speed  : {replay_speed:.2f}x"
        )
        update_charts(
            ch,
            window,
            state,
            cfg,
            source_name=replay_data.source_name,
            source_type=replay_data.source_type,
            mode=mode,
            replay_progress_text=progress,
        )

    if elapsed_s >= duration_s and not loop:
        log.info("Replay reached end of dataset; holding final frame.")
        state.replay_finished = True


# ---------------------------------------------------------------------------
# Public runners (called from cli.py)
# ---------------------------------------------------------------------------

def run_live_mode_nicegui(cfg: DictConfig, validate_reference: bool) -> int:
    """Run the viewer in live LSL streaming mode via NiceGUI.

    Replaces ``runners/live.py:run_live_mode()``.  The ``while/plt.pause()``
    event loop is replaced by a ``ui.timer()`` callback so the process never
    steals OS focus.

    Parameters
    ----------
    cfg:
        Hydra configuration (fully resolved).
    validate_reference:
        When ``True`` the mode label is ``"live_with_reference_validation"``.

    Returns
    -------
    Exit code (0 on clean exit).
    """
    target_stream, reference_stream, target_layout, reference_layout = build_streams(cfg)
    state = ViewerState()
    ch = build_chart_handles(cfg)

    mode_label = "live_with_reference_validation" if validate_reference else "live"

    log.info(
        "Live viewer starting: mode=%s target=%s reference=%s "
        "window_seconds=%.3f refresh_s=%.3f",
        mode_label,
        cfg.streams.target.name,
        cfg.streams.reference.name,
        cfg.viewer.window_seconds,
        cfg.viewer.refresh_s,
    )

    @ui.page("/")
    def index() -> None:
        build_page_layout(cfg, ch, state, mode=mode_label, is_replay=False)
        ui.timer(
            cfg.viewer.refresh_s,
            lambda: _live_tick(
                cfg,
                target_stream,
                reference_stream,
                target_layout,
                reference_layout,
                state,
                ch,
                validate_reference,
            ),
        )

    @ng_app.on_shutdown
    def _cleanup() -> None:
        log.info("Viewer shutting down — disconnecting LSL streams")
        try:
            target_stream.disconnect()  # type: ignore[union-attr]
        except Exception:
            pass
        try:
            reference_stream.disconnect()  # type: ignore[union-attr]
        except Exception:
            pass

    ui.run(
        host=cfg.viewer.server.host,
        port=cfg.viewer.server.port,
        show=cfg.viewer.server.show,
        reload=False,
        dark=cfg.viewer.server.dark,
        title=cfg.viewer.server.title,
    )
    return 0


def run_replay_mode_nicegui(
    cfg: DictConfig, replay_data: DualReplayData, mode: str
) -> int:
    """Animate a pre-loaded replay dataset via NiceGUI.

    Replaces ``runners/replay.py:run_replay_mode()``.

    Parameters
    ----------
    cfg:
        Hydra configuration (fully resolved).
    replay_data:
        Pre-loaded dataset returned by the core replay loaders.
    mode:
        Mode string shown in the info panel (``"csv_replay"`` or ``"xdf_replay"``).

    Returns
    -------
    Exit code (0 on clean exit).
    """
    duration_s = replay_data.duration_s
    if duration_s <= 0:
        raise RuntimeError(f"Replay dataset is empty for mode={mode}")

    state = ViewerState()
    ch = build_chart_handles(cfg)

    # Mutable container so the timer callback can read the wall-clock start
    replay_start_wall: list[float] = [time.monotonic()]

    log.info(
        "Replay viewer starting: mode=%s source=%s type=%s "
        "duration=%.3fs refresh_s=%.3f speed=%.3f loop=%s",
        mode,
        replay_data.source_name,
        replay_data.source_type,
        duration_s,
        cfg.viewer.refresh_s,
        cfg.replay.speed,
        cfg.replay.loop,
    )

    @ui.page("/")
    def index() -> None:
        build_page_layout(cfg, ch, state, mode=mode, is_replay=True)
        ui.timer(
            cfg.viewer.refresh_s,
            lambda: _replay_tick(cfg, replay_data, replay_start_wall, state, ch, mode),
        )

    ui.run(
        host=cfg.viewer.server.host,
        port=cfg.viewer.server.port,
        show=cfg.viewer.server.show,
        reload=False,
        dark=cfg.viewer.server.dark,
        title=f"{cfg.viewer.server.title} — {mode}",
    )
    return 0
