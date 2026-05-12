"""Live-mode runner for the handgrip realtime viewer.

This module is part of the **imperative shell**: it drives the matplotlib
event loop, calls the LSL stream API, and manages stream lifetimes.
"""
from __future__ import annotations

import logging

import numpy as np
from lsl_viewer.core.stream import (
    _slice_reference_window,
    _slice_target_window,
    build_streams,
    fetch_live_window,
)
from lsl_viewer.types import DualWindow, FigureHandles, ReferenceWindow, TargetWindow
from lsl_viewer.viz.figure import clear_plot_artists, init_figure
from lsl_viewer.viz.plots import update_plots
from matplotlib import pyplot as plt
from omegaconf import DictConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cutoff helpers
# ---------------------------------------------------------------------------

def _slice_dual_after_cutoffs(
    window: DualWindow,
    target_cutoff: float | None,
    reference_cutoff: float | None,
) -> DualWindow | None:
    """Remove samples that predate the live-reset cutoff timestamps.

    After the user presses the clear key, only samples newer than the cutoff
    are rendered so previously buffered data does not reappear.
    """
    target = window.target
    reference = window.reference

    if target is not None and target_cutoff is not None:
        mask = target.timestamps_s > float(target_cutoff)
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
    if reference is not None and reference_cutoff is not None:
        mask = reference.timestamps_s > float(reference_cutoff)
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
    target_stream,
    reference_stream,
    cfg: DictConfig,
    target_layout,
    reference_layout,
    handles: FigureHandles,
) -> None:
    """Record the latest timestamps in the current buffers as post-clear cutoffs.

    After a manual clear, the viewer only renders samples that arrive after
    these cutoffs so the display starts fresh.
    """
    latest = fetch_live_window(
        target_stream, reference_stream, cfg, target_layout, reference_layout
    )
    if latest is not None and latest.target is not None and latest.target.timestamps_s.size:
        handles.state["target_live_cutoff_timestamp_s"] = float(
            np.nanmax(latest.target.timestamps_s)
        )
    else:
        handles.state["target_live_cutoff_timestamp_s"] = None

    if (
        latest is not None
        and latest.reference is not None
        and latest.reference.timestamps_s.size
    ):
        handles.state["reference_live_cutoff_timestamp_s"] = float(
            np.nanmax(latest.reference.timestamps_s)
        )
    else:
        handles.state["reference_live_cutoff_timestamp_s"] = None

    log.info(
        "Live render cutoffs reset: target=%s reference=%s",
        handles.state["target_live_cutoff_timestamp_s"],
        handles.state["reference_live_cutoff_timestamp_s"],
    )
    handles.state["live_reset_from_latest_window"] = False


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_live_mode(cfg: DictConfig, validate_reference: bool) -> int:
    """Run the viewer in live LSL streaming mode.

    Parameters
    ----------
    cfg:
        Hydra configuration (fully resolved).
    validate_reference:
        When ``True`` the mode label is ``"live_with_reference_validation"``;
        the data flow is identical but the info panel reflects the intent.

    Returns
    -------
    Exit code (0 on clean exit).
    """
    target_stream, reference_stream, target_layout, reference_layout = build_streams(cfg)
    handles = init_figure(cfg)

    mode_label = "live_with_reference_validation" if validate_reference else "live"
    log.info(
        "Live viewer started: mode=%s target=%s reference=%s "
        "window_seconds=%.3f refresh_s=%.3f",
        mode_label,
        cfg.streams.target.name,
        cfg.streams.reference.name,
        cfg.viewer.window_seconds,
        cfg.viewer.refresh_s,
    )

    try:
        while plt.fignum_exists(handles.fig.number):
            if bool(handles.state.get("live_paused", False)):
                plt.pause(cfg.viewer.refresh_s)
                continue

            if bool(handles.state.get("live_reset_from_latest_window", False)):
                _establish_live_cutoff(
                    target_stream,
                    reference_stream,
                    cfg,
                    target_layout,
                    reference_layout,
                    handles,
                )
                plt.pause(cfg.viewer.refresh_s)
                continue

            live = fetch_live_window(
                target_stream, reference_stream, cfg, target_layout, reference_layout
            )
            if live is None:
                plt.pause(cfg.viewer.refresh_s)
                continue

            live = _slice_dual_after_cutoffs(
                live,
                handles.state.get("target_live_cutoff_timestamp_s"),
                handles.state.get("reference_live_cutoff_timestamp_s"),
            )
            if live is None:
                plt.pause(cfg.viewer.refresh_s)
                continue

            update_plots(
                handles,
                live,
                cfg,
                source_name=f"{target_stream.name} + {reference_stream.name}",
                source_type="dual_native_lsl",
                mode="live_ref" if validate_reference else "live",
                target_new_samples=int(target_stream.n_new_samples),
                reference_new_samples=int(reference_stream.n_new_samples),
            )
            plt.pause(cfg.viewer.refresh_s)

    except KeyboardInterrupt:
        log.info("Stopping on user request (Ctrl-C)")
    finally:
        target_stream.disconnect()
        reference_stream.disconnect()
        plt.close(handles.fig)

    return 0
