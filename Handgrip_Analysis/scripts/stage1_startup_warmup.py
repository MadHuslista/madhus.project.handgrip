#!/usr/bin/env python3
# @package scripts.stage1_startup_warmup
# @brief Stage 1 startup warm-up and zero stabilization analysis.

"""Stage 1 — Startup warm-up / zero stabilisation analysis."""
from __future__ import annotations

import logging
from pathlib import Path

import hydra
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from handgrip_analysis._logging import setup_logging
from handgrip_analysis.dsp import rolling_mean_std_slope, suggest_ready_time
from handgrip_analysis.io import ensure_dir, load_capture, sampling_summary
from handgrip_analysis.report import save_json
from omegaconf import DictConfig

matplotlib.use("Agg")
log = logging.getLogger(__name__)


# @brief Read a required non-empty string value from Hydra config.
# @param cfg Hydra configuration object.
# @param key Config key to validate.
# @return The required value converted to string.
# @throws ValueError Raised when key is missing or empty.
def _require_str(cfg: DictConfig, key: str) -> str:
    value = cfg.get(key)
    if value is None or not str(value).strip():
        raise ValueError(f"Missing required argument: {key}=<value>")
    return str(value)


# @brief Execute Stage 1 warm-up analysis and write summary/plots.
# @param cfg Hydra configuration object.
# @return None.
@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(
        level=cfg.logging.level,
        log_file=cfg.logging.file,
    )
    log.info("Stage 1 — startup warm-up analysis")

    input_path = _require_str(cfg, "input")
    outdir_path = _require_str(cfg, "outdir")

    outdir = ensure_dir(outdir_path)
    cap = load_capture(input_path, time_source=cfg.io.time_source)
    y = cap.series(cfg.analysis.channel)

    means, stds, slopes = rolling_mean_std_slope(
        y, cap.fs_estimate_hz, cfg.analysis.warmup_window_s
    )
    ready = suggest_ready_time(cap.time_s, stds, slopes)

    n_tail = max(10, len(means) // 10)
    summary = {
        "input": str(Path(input_path).resolve()),
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
