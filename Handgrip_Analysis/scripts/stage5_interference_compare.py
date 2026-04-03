#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from handgrip_analysis.dsp import bandpower, dominant_psd_peaks, welch_psd
from handgrip_analysis.io import ensure_dir, load_capture
from handgrip_analysis.report import save_csv, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare interference conditions through PSD overlays")
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--labels", nargs="+", required=True)
    parser.add_argument("--channel", default="raw", choices=["raw", "filtered"])
    parser.add_argument("--time-source", default="auto", choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if len(args.inputs) != len(args.labels):
        raise SystemExit("--inputs and --labels must have the same length")
    outdir = ensure_dir(args.outdir)
    rows = []
    summary = {"comparisons": []}
    fig, ax = plt.subplots(figsize=(10, 5))

    for csv_path, label in zip(args.inputs, args.labels):
        cap = load_capture(csv_path, time_source=args.time_source)
        y = cap.series(args.channel)
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
        summary["comparisons"].append({
            "label": label,
            "bandpower_0_1_hz": bandpower(f, pxx, 0.0, 1.0),
            "bandpower_1_4_hz": bandpower(f, pxx, 1.0, 4.0),
            "bandpower_4_12_hz": bandpower(f, pxx, 4.0, 12.0),
            "bandpower_12_30_hz": bandpower(f, pxx, 12.0, 30.0),
        })

    save_csv(outdir / "peak_comparison.csv", pd.DataFrame(rows))
    save_json(outdir / "summary.json", summary)

    ax.set_title("Stage 5 — Interference PSD comparison")
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("PSD [signal^2 / Hz]")
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "psd_compare.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
