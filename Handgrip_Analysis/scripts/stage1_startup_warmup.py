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

from handgrip_analysis.dsp import rolling_mean_std_slope, suggest_ready_time
from handgrip_analysis.io import ensure_dir, load_capture, sampling_summary
from handgrip_analysis.report import save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze startup warm-up / zero stabilization")
    parser.add_argument("--input", required=True, help="Path to CSV capture")
    parser.add_argument("--channel", default="raw", choices=["raw", "filtered"])
    parser.add_argument("--time-source", default="auto", choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--window-s", type=float, default=10.0, help="Rolling window for mean/std/slope")
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outdir = ensure_dir(args.outdir)
    cap = load_capture(args.input, time_source=args.time_source)
    y = cap.series(args.channel)
    means, stds, slopes = rolling_mean_std_slope(y, cap.fs_estimate_hz, args.window_s)
    ready = suggest_ready_time(cap.time_s, stds, slopes)

    summary = {
        "input": str(Path(args.input).resolve()),
        "channel": args.channel,
        "time_source": cap.time_source,
        "sampling": sampling_summary(cap.time_s),
        **ready,
        "warmup_window_s": args.window_s,
        "final_mean": float(np.nanmean(means[-max(10, len(means)//10):])),
        "final_std": float(np.nanmean(stds[-max(10, len(stds)//10):])),
        "final_abs_slope": float(np.nanmean(np.abs(slopes[-max(10, len(slopes)//10):]))),
    }
    save_json(outdir / "summary.json", summary)

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(cap.time_s, y, label=args.channel)
    axes[0].set_ylabel("Signal")
    axes[0].grid(True)

    axes[1].plot(cap.time_s, means, label="rolling mean")
    axes[1].set_ylabel("Mean")
    axes[1].grid(True)

    axes[2].plot(cap.time_s, stds, label="rolling std")
    if ready["std_threshold"] is not None:
        axes[2].axhline(ready["std_threshold"], linestyle="--")
    axes[2].set_ylabel("Std")
    axes[2].grid(True)

    axes[3].plot(cap.time_s, np.abs(slopes), label="|rolling slope|")
    if ready["slope_threshold"] is not None:
        axes[3].axhline(ready["slope_threshold"], linestyle="--")
    if ready["suggested_ready_time_s"] is not None:
        for ax in axes:
            ax.axvline(ready["suggested_ready_time_s"], linestyle=":")
    axes[3].set_ylabel("Abs slope / s")
    axes[3].set_xlabel("Time [s]")
    axes[3].grid(True)

    fig.suptitle("Stage 1 — Startup warm-up")
    fig.tight_layout()
    fig.savefig(outdir / "startup_warmup.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
