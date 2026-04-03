#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from handgrip_analysis.dsp import linear_trend
from handgrip_analysis.io import ensure_dir, load_capture, sampling_summary
from handgrip_analysis.report import save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze loaded drift / creep")
    parser.add_argument("--input", required=True)
    parser.add_argument("--channel", default="raw", choices=["raw", "filtered"])
    parser.add_argument("--time-source", default="auto", choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--pre-window-s", type=float, default=10.0, help="Baseline window at start for return-to-zero estimate")
    parser.add_argument("--post-window-s", type=float, default=10.0, help="Post window at end for return-to-zero estimate")
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outdir = ensure_dir(args.outdir)
    cap = load_capture(args.input, time_source=args.time_source)
    y = cap.series(args.channel)
    slope, intercept = linear_trend(y, cap.time_s)
    trend = slope * cap.time_s + intercept
    detrended = y - trend

    n_pre = max(1, int(round(args.pre_window_s * cap.fs_estimate_hz)))
    n_post = max(1, int(round(args.post_window_s * cap.fs_estimate_hz)))
    pre_mean = float(np.mean(y[:n_pre]))
    post_mean = float(np.mean(y[-n_post:]))

    summary = {
        "input": str(Path(args.input).resolve()),
        "channel": args.channel,
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

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
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
    fig.savefig(outdir / "loaded_drift.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
