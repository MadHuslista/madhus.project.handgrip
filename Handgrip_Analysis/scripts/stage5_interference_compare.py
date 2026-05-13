#!/usr/bin/env python3
"""Stage 5 — Interference PSD comparison across conditions."""
from __future__ import annotations

import logging

import hydra
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from handgrip_analysis._logging import setup_logging
from handgrip_analysis.dsp import bandpower, dominant_psd_peaks, welch_psd
from handgrip_analysis.io import ensure_dir, load_capture
from handgrip_analysis.report import save_csv, save_json
from omegaconf import DictConfig

matplotlib.use("Agg")
log = logging.getLogger(__name__)


def _require_str(cfg: DictConfig, key: str) -> str:
    value = cfg.get(key)
    if value is None or not str(value).strip():
        raise ValueError(f"Missing required argument: {key}=<value>")
    return str(value)


def _require_list(cfg: DictConfig, key: str) -> list[str]:
    raw = cfg.get(key)
    if raw is None:
        raise ValueError(f"Missing required argument: {key}=[...]")
    values = [str(v) for v in list(raw) if str(v).strip()]
    if not values:
        raise ValueError(f"Missing required argument: {key}=[...]")
    return values


@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(level=cfg.logging.level, log_file=cfg.logging.file)
    log.info("Stage 5 — interference PSD comparison")

    inputs = _require_list(cfg, "inputs")
    labels = _require_list(cfg, "labels")
    outdir_path = _require_str(cfg, "outdir")
    if len(inputs) != len(labels):
        raise ValueError("inputs and labels must have the same length")

    outdir = ensure_dir(outdir_path)
    bands = [list(b) for b in cfg.dsp.bandpower_bands]
    dpi = cfg.dsp.plot.dpi

    rows = []
    summary: dict = {"comparisons": []}
    fig, ax = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_square))

    for csv_path, label in zip(inputs, labels, strict=False):
        cap = load_capture(csv_path, time_source=cfg.io.time_source)
        y = cap.series(cfg.analysis.channel)
        f, pxx = welch_psd(y, cap.fs_estimate_hz)
        ax.semilogy(f, pxx, label=label)
        peaks = dominant_psd_peaks(f, pxx, cap.fs_estimate_hz)
        for peak in peaks:
            rows.append({
                "label": label,
                "frequency_hz": peak.frequency_hz,
                "psd": peak.psd,
                "prominence_db": peak.prominence_db,
                "alias_hint": peak.alias_hint or "",
            })
        bp = {}
        for band in bands[:4]:
            lo, hi = band[0], band[1]
            key = f"bandpower_{str(lo).replace('.', 'p')}_{str(hi).replace('.', 'p')}_hz"
            bp[key] = bandpower(f, pxx, lo, hi)
        summary["comparisons"].append({"label": label, **bp})

    save_csv(outdir / "peak_comparison.csv", pd.DataFrame(rows))
    save_json(outdir / "summary.json", summary)

    ax.set_title("Stage 5 — Interference PSD comparison")
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("PSD [signal² / Hz]")
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "psd_compare.png", dpi=dpi)
    plt.close(fig)
    log.info("Stage 5 complete — outputs in %s", outdir)


if __name__ == "__main__":
    main()
