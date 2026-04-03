#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from handgrip_analysis.dsp import allan_deviation, bandpower, dominant_psd_peaks, welch_psd
from handgrip_analysis.io import ensure_dir, load_capture, sampling_summary
from handgrip_analysis.report import save_csv, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze stationary rest noise and PSD")
    parser.add_argument("--input", required=True)
    parser.add_argument("--time-source", default="auto", choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--channels", nargs="+", default=["raw", "filtered"], choices=["raw", "filtered"])
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def channel_summary(y: np.ndarray, fs: float) -> tuple[dict, pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    f, pxx = welch_psd(y, fs)
    tau, adev = allan_deviation(y, fs)
    peaks = dominant_psd_peaks(f, pxx, fs)
    peak_df = pd.DataFrame([
        {
            "frequency_hz": p.frequency_hz,
            "psd": p.psd,
            "prominence_db": p.prominence_db,
            "alias_hint": p.alias_hint or "",
        }
        for p in peaks
    ])
    summary = {
        "mean": float(np.mean(y)),
        "std": float(np.std(y, ddof=1)),
        "rms": float(np.sqrt(np.mean(np.square(y)))),
        "peak_to_peak": float(np.max(y) - np.min(y)),
        "bandpower_0_1_hz": bandpower(f, pxx, 0.0, 1.0),
        "bandpower_1_4_hz": bandpower(f, pxx, 1.0, 4.0),
        "bandpower_4_12_hz": bandpower(f, pxx, 4.0, 12.0),
        "bandpower_12_30_hz": bandpower(f, pxx, 12.0, 30.0),
    }
    return summary, peak_df, f, pxx, tau, adev


def main() -> None:
    args = parse_args()
    outdir = ensure_dir(args.outdir)
    cap = load_capture(args.input, time_source=args.time_source)
    summary = {
        "input": str(Path(args.input).resolve()),
        "time_source": cap.time_source,
        "sampling": sampling_summary(cap.time_s),
        "channels": {},
    }

    fig_time, ax_time = plt.subplots(figsize=(12, 4))
    fig_hist, ax_hist = plt.subplots(figsize=(10, 4))
    fig_psd, ax_psd = plt.subplots(figsize=(10, 5))
    fig_allan, ax_allan = plt.subplots(figsize=(10, 5))

    for channel in args.channels:
        if channel == "filtered" and "value_filtered" not in cap.df.columns:
            continue
        y = cap.series(channel)
        ch_summary, peak_df, f, pxx, tau, adev = channel_summary(y, cap.fs_estimate_hz)
        summary["channels"][channel] = ch_summary
        save_csv(outdir / f"{channel}_psd_peaks.csv", peak_df)

        ax_time.plot(cap.time_s, y, label=channel)
        ax_hist.hist(y, bins=80, alpha=0.5, density=True, label=channel)
        if f.size:
            ax_psd.semilogy(f, pxx, label=channel)
        if tau.size:
            ax_allan.loglog(tau, adev, label=channel)

    save_json(outdir / "summary.json", summary)

    ax_time.set_title("Static rest capture")
    ax_time.set_xlabel("Time [s]")
    ax_time.set_ylabel("Signal")
    ax_time.grid(True)
    ax_time.legend()
    fig_time.tight_layout()
    fig_time.savefig(outdir / "time_series.png", dpi=150)
    plt.close(fig_time)

    ax_hist.set_title("Histogram")
    ax_hist.set_xlabel("Signal")
    ax_hist.set_ylabel("Density")
    ax_hist.grid(True)
    ax_hist.legend()
    fig_hist.tight_layout()
    fig_hist.savefig(outdir / "histogram.png", dpi=150)
    plt.close(fig_hist)

    ax_psd.set_title("Welch PSD")
    ax_psd.set_xlabel("Frequency [Hz]")
    ax_psd.set_ylabel("PSD [signal^2 / Hz]")
    ax_psd.grid(True)
    ax_psd.legend()
    fig_psd.tight_layout()
    fig_psd.savefig(outdir / "psd.png", dpi=150)
    plt.close(fig_psd)

    ax_allan.set_title("Allan deviation")
    ax_allan.set_xlabel("Tau [s]")
    ax_allan.set_ylabel("Allan deviation")
    ax_allan.grid(True, which="both")
    ax_allan.legend()
    fig_allan.tight_layout()
    fig_allan.savefig(outdir / "allan_deviation.png", dpi=150)
    plt.close(fig_allan)


if __name__ == "__main__":
    main()
