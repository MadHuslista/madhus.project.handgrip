# @file
# @brief NiceGUI application factory and event-loop runners.
##
# This module replaces runners/live.py and runners/replay.py. The while/
# plt.pause() event loops are replaced by NiceGUI ui.timer() callbacks, which
# run in the asyncio event loop without stealing OS focus.
##
# Root cause fix: plt.pause() called QWidget.raise_() and QWidget.activateWindow()
# on every frame via the Qt5Agg backend, stealing keyboard focus at 20 Hz.
# NiceGUI renders in a browser tab served over localhost; no native OS window
# is created, so focus stealing is architecturally impossible.

from __future__ import annotations

import logging
import time

import numpy as np
from nicegui import app as ng_app
from nicegui import ui
from omegaconf import DictConfig

from lsl_viewer.core.replay import window_from_replay
from lsl_viewer.core.stream import build_streams, fetch_live_window
from lsl_viewer.diagnostics import DiagnosticsRecorder, compute_tick_metrics
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
    # @brief Remove samples that predate the live-reset cutoff timestamps.
    # @param window Current dual window.
    # @param state Viewer state.
    # @return Window trimmed to the active cutoffs, or None.
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
    # @brief Record the latest buffered timestamps as post-clear cutoffs.
    # @param target_stream Connected target stream.
    # @param reference_stream Connected reference stream.
    # @param cfg Hydra configuration.
    # @param target_layout Target layout.
    # @param reference_layout Reference layout.
    # @param state Viewer state.
    latest = fetch_live_window(target_stream, reference_stream, cfg, target_layout, reference_layout)
    if latest is not None and latest.target is not None and latest.target.timestamps_s.size:
        state.target_cutoff_s = float(np.nanmax(latest.target.timestamps_s))
    else:
        state.target_cutoff_s = None

    if latest is not None and latest.reference is not None and latest.reference.timestamps_s.size:
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
    recorder: DiagnosticsRecorder | None = None,
) -> None:
    # @brief Live-mode timer callback.
    # @param cfg Hydra configuration.
    # @param target_stream Connected target stream.
    # @param reference_stream Connected reference stream.
    # @param target_layout Target layout.
    # @param reference_layout Reference layout.
    # @param state Viewer state.
    # @param ch Chart handle bundle.
    # @param validate_reference Whether reference validation is enabled.
    # @param recorder Optional diagnostics recorder (inert when disabled).
    if state.live_paused:
        return

    if state.live_reset_from_latest_window:
        _establish_live_cutoff(target_stream, reference_stream, cfg, target_layout, reference_layout, state)
        return

    live = fetch_live_window(target_stream, reference_stream, cfg, target_layout, reference_layout)
    if live is None:
        return

    lsl_now = _lsl_local_clock()
    target_new_samples = int(target_stream.n_new_samples)  # type: ignore[attr-defined]
    reference_new_samples = int(reference_stream.n_new_samples)  # type: ignore[attr-defined]

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
        target_new_samples=target_new_samples,
        reference_new_samples=reference_new_samples,
    )

    if recorder is not None and recorder.enabled:
        recorder.record_window(live)
        recorder.record_tick(
            compute_tick_metrics(
                live,
                state,
                tick_index=recorder.tick_index,
                wall_time_s=time.time(),
                monotonic_s=time.monotonic(),
                lsl_local_clock_s=lsl_now,
                target_new_samples=target_new_samples,
                reference_new_samples=reference_new_samples,
            )
        )


def _lsl_local_clock() -> float | None:
    # @brief Sample the LSL local clock if a provider is importable.
    # @return local_clock() in seconds, or None when unavailable.
    try:
        from mne_lsl.lsl import local_clock  # type: ignore[import]
    except ImportError:
        try:
            from pylsl import local_clock  # type: ignore[import]
        except ImportError:
            return None
    return float(local_clock())


# ---------------------------------------------------------------------------
# Replay-mode timer callback
# ---------------------------------------------------------------------------


def _replay_tick(
    cfg: DictConfig,
    replay_data: DualReplayData,
    replay_start_wall: list[float],  # mutable container [start_time]
    state: ViewerState,
    ch: ChartHandles,
    mode: str,
) -> None:
    # @brief Replay-mode timer callback.
    # @param cfg Hydra configuration.
    # @param replay_data Pre-loaded replay data.
    # @param replay_start_wall Mutable container holding the wall-clock start.
    # @param state Viewer state.
    # @param ch Chart handle bundle.
    # @param mode Replay mode string.
    if state.replay_finished:
        return

    if state.replay_paused:
        return

    replay_speed = max(1e-9, float(cfg.replay.speed))
    start_offset_s = max(0.0, float(cfg.replay.start_offset_s))
    loop = bool(cfg.replay.loop)
    duration_s = replay_data.duration_s

    elapsed_s = (time.monotonic() - replay_start_wall[0]) * replay_speed + start_offset_s

    if loop and duration_s > 0:
        elapsed_s = elapsed_s % duration_s
    elif elapsed_s > duration_s:
        elapsed_s = duration_s

    window = window_from_replay(replay_data, elapsed_s, cfg.viewer.window_seconds)
    if window is not None:
        progress = f"time   : {elapsed_s:.2f}/{duration_s:.2f} s\nspeed  : {replay_speed:.2f}x"
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
    # @brief Run the viewer in live LSL streaming mode via NiceGUI.
    # @param cfg Fully resolved Hydra configuration.
    # @param validate_reference Whether reference validation is enabled.
    # @return Exit code.
    target_stream, reference_stream, target_layout, reference_layout = build_streams(cfg)
    state = ViewerState()
    ch = build_chart_handles(cfg)
    recorder = DiagnosticsRecorder(cfg)

    mode_label = "live_with_reference_validation" if validate_reference else "live"

    log.info(
        "Live viewer starting: mode=%s target=%s reference=%s window_seconds=%.3f refresh_s=%.3f",
        mode_label,
        cfg.streams.target.name,
        cfg.streams.reference.name,
        cfg.viewer.window_seconds,
        cfg.viewer.refresh_s,
    )

    @ui.page("/")
    # @brief Live-mode page route.
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
                recorder,
            ),
        )

    @ng_app.on_shutdown
    # @brief Shutdown hook that disconnects both LSL streams.
    def _cleanup() -> None:
        log.info("Viewer shutting down — disconnecting LSL streams")
        recorder.close()
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


def run_replay_mode_nicegui(cfg: DictConfig, replay_data: DualReplayData, mode: str) -> int:
    # @brief Animate a pre-loaded replay dataset via NiceGUI.
    # @param cfg Fully resolved Hydra configuration.
    # @param replay_data Pre-loaded replay dataset.
    # @param mode Mode string shown in the info panel.
    # @return Exit code.
    duration_s = replay_data.duration_s
    if duration_s <= 0:
        raise RuntimeError(f"Replay dataset is empty for mode={mode}")

    state = ViewerState()
    ch = build_chart_handles(cfg)

    # Mutable container so the timer callback can read the wall-clock start
    replay_start_wall: list[float] = [time.monotonic()]

    log.info(
        "Replay viewer starting: mode=%s source=%s type=%s duration=%.3fs refresh_s=%.3f speed=%.3f loop=%s",
        mode,
        replay_data.source_name,
        replay_data.source_type,
        duration_s,
        cfg.viewer.refresh_s,
        cfg.replay.speed,
        cfg.replay.loop,
    )

    @ui.page("/")
    # @brief Replay-mode page route.
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
