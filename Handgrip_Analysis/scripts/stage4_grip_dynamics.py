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

from handgrip_analysis.dsp import detect_events, event_metrics, welch_psd
from handgrip_analysis.io import ensure_dir, load_capture
from handgrip_analysis.report import save_csv, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze handgrip dynamics from one or more grip-trial captures")
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--channel", default="raw", choices=["raw", "filtered"])
    parser.add_argument("--time-source", default="auto", choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--threshold-sigma", type=float, default=5.0)
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outdir = ensure_dir(args.outdir)
    all_metrics = []
    summary = {"files": []}

    overlay_fig, overlay_ax = plt.subplots(figsize=(12, 5))
    hold_fig, hold_ax = plt.subplots(figsize=(10, 5))

    for csv_path in args.input:
        cap = load_capture(csv_path, time_source=args.time_source)
        y = cap.series(args.channel)
        events = detect_events(y, cap.fs_estimate_hz, threshold_sigma=args.threshold_sigma)
        metrics = event_metrics(y, cap.time_s, events)
        if not metrics.empty:
            metrics.insert(0, "file", Path(csv_path).name)
            all_metrics.append(metrics)
        summary["files"].append({
            "input": str(Path(csv_path).resolve()),
            "n_events": int(len(events)),
            "fs_estimate_hz": float(cap.fs_estimate_hz),
        })

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(cap.time_s, y, label=args.channel)
        for ev in events:
            ax.axvspan(cap.time_s[ev.start_idx], cap.time_s[ev.end_idx], alpha=0.15)
            seg_t = cap.time_s[ev.start_idx : ev.end_idx + 1] - cap.time_s[ev.start_idx]
            seg_y = y[ev.start_idx : ev.end_idx + 1]
            overlay_ax.plot(seg_t, seg_y, alpha=0.8, label=Path(csv_path).stem if len(events) == 1 else None)
            if len(seg_y) > int(2 * cap.fs_estimate_hz):
                hold_slice = seg_y[int(0.5 * len(seg_y)) :]
                f, pxx = welch_psd(hold_slice, cap.fs_estimate_hz)
                if f.size:
                    hold_ax.semilogy(f, pxx, alpha=0.8, label=Path(csv_path).stem if len(events) == 1 else None)
        ax.set_title(f"Detected grip events — {Path(csv_path).name}")
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Signal")
        ax.grid(True)
        fig.tight_layout()
        fig.savefig(outdir / f"events_{Path(csv_path).stem}.png", dpi=150)
        plt.close(fig)

    if all_metrics:
        metrics_df = pd.concat(all_metrics, ignore_index=True)
    else:
        metrics_df = pd.DataFrame(columns=[
            "file", "event_index", "start_time_s", "peak_time_s", "end_time_s",
            "duration_s", "peak_value", "baseline_value", "rise_10_90_s", "max_dfdt",
            "hold_std_last_20pct",
        ])
    save_csv(outdir / "event_metrics.csv", metrics_df)
    save_json(outdir / "summary.json", summary)

    overlay_ax.set_title("Grip-event overlay")
    overlay_ax.set_xlabel("Time since event start [s]")
    overlay_ax.set_ylabel("Signal")
    overlay_ax.grid(True)
    overlay_fig.tight_layout()
    overlay_fig.savefig(outdir / "event_overlay.png", dpi=150)
    plt.close(overlay_fig)

    hold_ax.set_title("Hold-segment PSD")
    hold_ax.set_xlabel("Frequency [Hz]")
    hold_ax.set_ylabel("PSD [signal^2 / Hz]")
    hold_ax.grid(True)
    hold_fig.tight_layout()
    hold_fig.savefig(outdir / "hold_psd.png", dpi=150)
    plt.close(hold_fig)


if __name__ == "__main__":
    main()
