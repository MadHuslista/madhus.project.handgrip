"""Replay-mode runner for the handgrip realtime viewer.

Handles both ``csv_replay`` and ``xdf_replay`` modes; they share the same
animation loop.  The only difference is the :class:`DualReplayData` source,
which is loaded in :mod:`lsl_viewer.cli` before this runner is called.
"""
from __future__ import annotations

import logging
import time

from lsl_viewer.core.replay import window_from_replay
from lsl_viewer.types import DualReplayData
from lsl_viewer.viz.figure import init_figure
from lsl_viewer.viz.plots import update_plots
from matplotlib import pyplot as plt
from omegaconf import DictConfig

log = logging.getLogger(__name__)


def run_replay_mode(cfg: DictConfig, replay_data: DualReplayData, mode: str) -> int:
    """Animate a pre-loaded replay dataset.

    Parameters
    ----------
    cfg:
        Hydra configuration (fully resolved).
    replay_data:
        Pre-loaded dataset returned by :func:`~lsl_viewer.core.replay.load_csv_replay`
        or :func:`~lsl_viewer.core.replay.load_xdf_replay`.
    mode:
        Mode string shown in the info panel (``"csv_replay"`` or ``"xdf_replay"``).

    Returns
    -------
    Exit code (0 on clean exit).
    """
    handles = init_figure(cfg)
    duration_s = replay_data.duration_s
    if duration_s <= 0:
        raise RuntimeError(f"Replay dataset is empty for mode={mode}")

    start_offset_s = max(0.0, cfg.replay.start_offset_s)
    replay_speed = max(1e-9, cfg.replay.speed)
    loop = cfg.replay.loop

    log.info(
        "Replay viewer started: mode=%s source=%s type=%s "
        "duration=%.3fs refresh_s=%.3f speed=%.3f loop=%s",
        mode,
        replay_data.source_name,
        replay_data.source_type,
        duration_s,
        cfg.viewer.refresh_s,
        replay_speed,
        loop,
    )

    replay_start_wall = time.monotonic()
    try:
        while plt.fignum_exists(handles.fig.number):
            elapsed_s = (
                time.monotonic() - replay_start_wall
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
                update_plots(
                    handles,
                    window,
                    cfg,
                    source_name=replay_data.source_name,
                    source_type=replay_data.source_type,
                    mode=mode,
                    replay_progress_text=progress,
                )
            plt.pause(cfg.viewer.refresh_s)

            if elapsed_s >= duration_s and not loop:
                log.info("Replay reached end of dataset; holding final frame.")
                while plt.fignum_exists(handles.fig.number):
                    plt.pause(cfg.viewer.refresh_s)
                break

    except KeyboardInterrupt:
        log.info("Stopping on user request (Ctrl-C)")
    finally:
        plt.close(handles.fig)

    return 0
