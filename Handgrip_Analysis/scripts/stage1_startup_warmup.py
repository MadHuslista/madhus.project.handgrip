#!/usr/bin/env python3
"""Stage 1 — Startup warm-up / zero stabilisation analysis."""
from __future__ import annotations

import logging
from pathlib import Path

import hydra
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from omegaconf import DictConfig

from handgrip_analysis._logging import setup_logging
from handgrip_analysis.dsp import rolling_mean_std_slope, suggest_ready_time
from handgrip_analysis.io import ensure_dir, load_capture, sampling_summary
from handgrip_analysis.report import save_json

matplotlib.use("Agg")
log = logging.getLogger(__name__)


@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(
        level=cfg.logging.level,
        log_file=cfg.logging.file,
    )
    log.info("Stage 1 — startup warm-up analysis")

    outdir = ensure_dir(cfg.outdir)
    cap = load_capture(cfg.input, time_source=cfg.io.time_source)
    y = cap.series(cfg.analysis.channel)

    means, stds, slopes = rolling_mean_std_slope(
        y, cap.fs_estimate_hz, cfg.analysis.warmup_window_s
    )
    ready = suggest_ready_time(cap.time_s, stds, slopes)

    n_tail = max(10, len(means) // 10)
    summary = {
        "input": str(Path(cfg.input).resolve()),
        "channel": cfg.analysis.channel,
        "time_source": cap.time_source,
        "sampling": sampling_summary(cap.time_s),
        **ready,
        "warmup_window_s": cfg.analysis.warmup_window_s,
        "final_mean": float(np.nanmean(means[-n_tail:])),
        "final_std": float(np.nanmean(stds[-n_tail:])),
        "final_abs_slope": float(np.nanmean(np.abs(slopes[-n_tail:]))),
    }
    save_json(outdir / "summary.json", summary)

    dpi = cfg.dsp.plot.dpi
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(cap.time_s, y, label=cfg.analysis.channel)
    axes[0].set_ylabel("Signal")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].plot(cap.time_s, means, label="rolling mean")
    axes[1].set_ylabel("Mean")
    axes[1].grid(True)
    axes[1].legend()

    axes[2].plot(cap.time_s, stds, label="rolling std")
    axes[2].set_ylabel("Std")
    axes[2].grid(True)
    axes[2].legend()

    axes[3].plot(cap.time_s, np.abs(slopes), label="|slope|")
    axes[3].set_xlabel("Time [s]")
    axes[3].set_ylabel("|Slope|")
    axes[3].grid(True)
    axes[3].legend()

    if ready["suggested_ready_time_s"] is not None:
        for ax in axes:
            ax.axvline(ready["suggested_ready_time_s"], color="green", linestyle="--", alpha=0.7)

    fig.suptitle("Stage 1 — Startup warm-up")
    fig.tight_layout()
    fig.savefig(outdir / "warmup.png", dpi=dpi)
    plt.close(fig)
    log.info("Stage 1 complete — outputs in %s", outdir)


if __name__ == "__main__":
    main()
