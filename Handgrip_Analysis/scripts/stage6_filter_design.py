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

from handgrip_analysis.dsp import apply_filter_spec, detect_events, event_metrics, load_filter_specs, welch_psd
from handgrip_analysis.io import ensure_dir, load_capture
from handgrip_analysis.report import save_csv, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark candidate digital filters")
    parser.add_argument("--input", required=True)
    parser.add_argument("--channel", default="raw", choices=["raw", "filtered"])
    parser.add_argument("--time-source", default="auto", choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--config", required=True, help="YAML file with candidate filter specs")
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outdir = ensure_dir(args.outdir)
    cap = load_capture(args.input, time_source=args.time_source)
    y = cap.series(args.channel)
    specs = load_filter_specs(args.config)

    events_raw = detect_events(y, cap.fs_estimate_hz)
    raw_metrics = event_metrics(y, cap.time_s, events_raw)
    raw_peak = float(raw_metrics["peak_value"].max()) if not raw_metrics.empty else np.nan
    raw_peak_time = float(raw_metrics.loc[raw_metrics["peak_value"].idxmax(), "peak_time_s"]) if not raw_metrics.empty else np.nan

    rows = []
    fig_time, ax_time = plt.subplots(figsize=(12, 5))
    fig_psd, ax_psd = plt.subplots(figsize=(10, 5))
    ax_time.plot(cap.time_s, y, label="raw", linewidth=1.2)
    f_raw, pxx_raw = welch_psd(y, cap.fs_estimate_hz)
    if f_raw.size:
        ax_psd.semilogy(f_raw, pxx_raw, label="raw", linewidth=1.2)

    for spec in specs:
        name = spec["name"]
        y_filt = apply_filter_spec(y, cap.fs_estimate_hz, spec)
        noise_rms = float(np.std(y_filt, ddof=1))
        f, pxx = welch_psd(y_filt, cap.fs_estimate_hz)
        events = detect_events(y_filt, cap.fs_estimate_hz)
        metrics = event_metrics(y_filt, cap.time_s, events)
        peak_value = float(metrics["peak_value"].max()) if not metrics.empty else np.nan
        peak_time = float(metrics.loc[metrics["peak_value"].idxmax(), "peak_time_s"]) if not metrics.empty else np.nan
        rows.append({
            "filter": name,
            "std": noise_rms,
            "rms": float(np.sqrt(np.mean(np.square(y_filt)))),
            "peak_value": peak_value,
            "peak_shift_vs_raw": peak_value - raw_peak if np.isfinite(raw_peak) and np.isfinite(peak_value) else np.nan,
            "peak_time_shift_s": peak_time - raw_peak_time if np.isfinite(raw_peak_time) and np.isfinite(peak_time) else np.nan,
        })
        ax_time.plot(cap.time_s, y_filt, label=name, alpha=0.85)
        if f.size:
            ax_psd.semilogy(f, pxx, label=name, alpha=0.85)

    comparison_df = pd.DataFrame(rows).sort_values(by="std", ascending=True)
    save_csv(outdir / "filter_comparison.csv", comparison_df)
    save_json(outdir / "summary.json", {
        "input": str(Path(args.input).resolve()),
        "channel": args.channel,
        "config": str(Path(args.config).resolve()),
        "n_candidates": int(len(specs)),
    })

    ax_time.set_title("Stage 6 — Time-domain comparison")
    ax_time.set_xlabel("Time [s]")
    ax_time.set_ylabel("Signal")
    ax_time.grid(True)
    ax_time.legend(loc="best", fontsize=8)
    fig_time.tight_layout()
    fig_time.savefig(outdir / "filter_time_overlay.png", dpi=150)
    plt.close(fig_time)

    ax_psd.set_title("Stage 6 — PSD comparison")
    ax_psd.set_xlabel("Frequency [Hz]")
    ax_psd.set_ylabel("PSD [signal^2 / Hz]")
    ax_psd.grid(True)
    ax_psd.legend(loc="best", fontsize=8)
    fig_psd.tight_layout()
    fig_psd.savefig(outdir / "filter_psd_overlay.png", dpi=150)
    plt.close(fig_psd)


if __name__ == "__main__":
    main()
