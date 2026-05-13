#!/usr/bin/env python3
"""Stage 3 — Loaded drift / creep analysis."""
from __future__ import annotations

import logging
from pathlib import Path

import hydra
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from handgrip_analysis._logging import setup_logging
from handgrip_analysis.dsp import linear_trend
from handgrip_analysis.io import ensure_dir, load_capture, sampling_summary
from handgrip_analysis.report import save_json
from omegaconf import DictConfig

matplotlib.use("Agg")
log = logging.getLogger(__name__)


def _require_str(cfg: DictConfig, key: str) -> str:
    value = cfg.get(key)
    if value is None or not str(value).strip():
        raise ValueError(f"Missing required argument: {key}=<value>")
    return str(value)


@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(level=cfg.logging.level, log_file=cfg.logging.file)
    log.info("Stage 3 — loaded drift / creep analysis")

    input_path = _require_str(cfg, "input")
    outdir_path = _require_str(cfg, "outdir")

    outdir = ensure_dir(outdir_path)
    cap = load_capture(input_path, time_source=cfg.io.time_source)
    y = cap.series(cfg.analysis.channel)
    slope, intercept = linear_trend(y, cap.time_s)
    trend = slope * cap.time_s + intercept
    detrended = y - trend

    n_pre = max(1, int(round(cfg.analysis.pre_window_s * cap.fs_estimate_hz)))
    n_post = max(1, int(round(cfg.analysis.post_window_s * cap.fs_estimate_hz)))
    pre_mean = float(np.mean(y[:n_pre]))
    post_mean = float(np.mean(y[-n_post:]))

    summary = {
        "input": str(Path(input_path).resolve()),
        "channel": cfg.analysis.channel,
        "time_source": cap.time_source,
        "sampling": sampling_summary(cap.time_s),
        "drift_slope_per_s": slope,
        "drift_slope_per_min": slope * 60.0,
        "pre_window_mean": pre_mean,
        "post_window_mean": post_mean,
        "return_to_zero_error": post_mean - pre_mean,
        "detrended_std": float(np.std(detrended, ddof=1)),
    }
    save_json(outdir / "summary.json", summary)

    fig, axes = plt.subplots(2, 1, figsize=tuple(cfg.dsp.plot.figsize_wide), sharex=True)
    axes[0].plot(cap.time_s, y, label="signal")
    axes[0].plot(cap.time_s, trend, label="linear trend")
    axes[0].set_ylabel("Signal")
    axes[0].set_title("Stage 3 — Loaded drift / creep")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].plot(cap.time_s, detrended, label="detrended")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Signal")
    axes[1].grid(True)
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(outdir / "loaded_drift.png", dpi=cfg.dsp.plot.dpi)
    plt.close(fig)
    log.info("Stage 3 complete — outputs in %s", outdir)


if __name__ == "__main__":
    main()
