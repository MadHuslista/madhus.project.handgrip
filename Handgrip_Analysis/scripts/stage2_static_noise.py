#!/usr/bin/env python3
# @package scripts.stage2_static_noise
# @brief Stage 2 stationary noise characterization analysis.

"""Stage 2 — Stationary rest noise characterisation."""
from __future__ import annotations

import logging
from pathlib import Path

import hydra
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from handgrip_analysis._logging import setup_logging
from handgrip_analysis.dsp import (
    allan_deviation,
    bandpower,
    dominant_psd_peaks,
    welch_psd,
)
from handgrip_analysis.io import ensure_dir, load_capture, sampling_summary
from handgrip_analysis.report import save_csv, save_json
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


# @brief Compute channel summary metrics and spectral artifacts for Stage 2.
# @param y Signal vector for one channel.
# @param fs Sampling rate in Hz.
# @param bands Frequency band definitions.
# @return Tuple of summary dict, peak table, PSD arrays, and Allan arrays.
def channel_summary(
    y: np.ndarray, fs: float, bands: list
) -> tuple[dict, pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    f, pxx = welch_psd(y, fs)
    tau, adev = allan_deviation(y, fs)
    peaks = dominant_psd_peaks(f, pxx, fs)
    peak_df = pd.DataFrame(
        [
            {
                "frequency_hz": p.frequency_hz,
                "psd": p.psd,
                "prominence_db": p.prominence_db,
                "alias_hint": p.alias_hint or "",
            }
            for p in peaks
        ]
    )
    bp = {}
    for band in bands[:4]:  # first 4 bands for standard noise reporting
        lo, hi = band[0], band[1]
        key = f"bandpower_{str(lo).replace('.', 'p')}_{str(hi).replace('.', 'p')}_hz"
        bp[key] = bandpower(f, pxx, lo, hi)

    summary = {
        "mean": float(np.mean(y)),
        "std": float(np.std(y, ddof=1)),
        "rms": float(np.sqrt(np.mean(np.square(y)))),
        "peak_to_peak": float(np.max(y) - np.min(y)),
        **bp,
    }
    return summary, peak_df, f, pxx, tau, adev


# @brief Execute Stage 2 static-noise analysis and write outputs.
# @param cfg Hydra configuration object.
# @return None.
@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(level=cfg.logging.level, log_file=cfg.logging.file)
    log.info("Stage 2 — static rest noise characterisation")

    input_path = _require_str(cfg, "input")
    outdir_path = _require_str(cfg, "outdir")

    outdir = ensure_dir(outdir_path)
    cap = load_capture(input_path, time_source=cfg.io.time_source)
    bands = [list(b) for b in cfg.dsp.bandpower_bands]
    dpi = cfg.dsp.plot.dpi

    summary: dict = {
        "input": str(Path(input_path).resolve()),
        "time_source": cap.time_source,
        "sampling": sampling_summary(cap.time_s),
        "channels": {},
    }

    fig_time, ax_time = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_wide))
    fig_hist, ax_hist = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_square))
    fig_psd, ax_psd = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_square))
    fig_allan, ax_allan = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_square))

    for channel in list(cfg.analysis.channels):
        if channel == "filtered" and "target_filtered_units" not in cap.df.columns:
            log.warning("Stage 2: no target_filtered_units column — skipping channel")
            continue
        y = cap.series(channel)
        ch_summary, peak_df, f, pxx, tau, adev = channel_summary(y, cap.fs_estimate_hz, bands)
        summary["channels"][channel] = ch_summary
        save_csv(outdir / f"{channel}_psd_peaks.csv", peak_df)

        ax_time.plot(cap.time_s, y, label=channel)
        ax_hist.hist(y, bins=80, alpha=0.5, density=True, label=channel)
        if f.size:
            ax_psd.semilogy(f, pxx, label=channel)
        if tau.size:
            ax_allan.loglog(tau, adev, label=channel)

    save_json(outdir / "summary.json", summary)

    for fig, ax, title, xlabel, ylabel, fname in [
        (fig_time, ax_time, "Static rest capture", "Time [s]", "Signal", "time_series.png"),
        (fig_hist, ax_hist, "Histogram", "Signal", "Density", "histogram.png"),
        (fig_psd, ax_psd, "Welch PSD", "Frequency [Hz]", "PSD [signal² / Hz]", "psd.png"),
        (fig_allan, ax_allan, "Allan deviation", "Tau [s]", "Allan deviation", "allan_deviation.png"),
    ]:
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, which="both" if "Allan" in title else "major")
        ax.legend()
        fig.tight_layout()
        fig.savefig(outdir / fname, dpi=dpi)
        plt.close(fig)

    log.info("Stage 2 complete — outputs in %s", outdir)


if __name__ == "__main__":
    main()
