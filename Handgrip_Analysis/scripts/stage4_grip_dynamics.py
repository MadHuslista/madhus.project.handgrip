#!/usr/bin/env python3
# @package scripts.stage4_grip_dynamics
# @brief Stage 4 grip dynamics event-detection analysis.

"""Stage 4 — Grip dynamics: event detection and metrics."""

from __future__ import annotations

import logging
from pathlib import Path

import hydra
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from handgrip_analysis._logging import setup_logging
from handgrip_analysis.dsp import detect_events, event_metrics, welch_psd
from handgrip_analysis.io import ensure_dir, load_capture
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


# @brief Read a required non-empty list of strings from Hydra config.
# @param cfg Hydra configuration object.
# @param key Config key to validate.
# @return Sanitized non-empty list of string values.
# @throws ValueError Raised when key is missing or contains no values.
def _require_list(cfg: DictConfig, key: str) -> list[str]:
    raw = cfg.get(key)
    if raw is None:
        raise ValueError(f"Missing required argument: {key}=[...]")
    values = [str(v) for v in list(raw) if str(v).strip()]
    if not values:
        raise ValueError(f"Missing required argument: {key}=[...]")
    return values


# @brief Execute Stage 4 grip dynamics analysis and persist outputs.
# @param cfg Hydra configuration object.
# @return None.
@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(level=cfg.logging.level, log_file=cfg.logging.file)
    log.info("Stage 4 — grip dynamics analysis")

    inputs = _require_list(cfg, "inputs")
    outdir_path = _require_str(cfg, "outdir")

    outdir = ensure_dir(outdir_path)
    all_metrics = []
    summary: dict = {"files": []}

    overlay_fig, overlay_ax = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_wide))
    hold_fig, hold_ax = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_square))
    dpi = cfg.dsp.plot.dpi

    for csv_path in inputs:
        cap = load_capture(csv_path, time_source=cfg.io.time_source)
        y = cap.series(cfg.analysis.channel)
        events = detect_events(
            y,
            cap.fs_estimate_hz,
            baseline_s=cfg.dsp.event_detection.baseline_s,
            threshold_sigma=cfg.analysis.threshold_sigma,
            min_duration_s=cfg.dsp.event_detection.min_duration_s,
            merge_gap_s=cfg.dsp.event_detection.merge_gap_s,
            pad_s=cfg.dsp.event_detection.pad_s,
        )
        metrics = event_metrics(y, cap.time_s, events)
        if not metrics.empty:
            metrics.insert(0, "file", Path(csv_path).name)
            all_metrics.append(metrics)
        summary["files"].append(
            {
                "input": str(Path(csv_path).resolve()),
                "n_events": int(len(events)),
                "fs_estimate_hz": float(cap.fs_estimate_hz),
            }
        )

        fig, ax = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_wide))
        ax.plot(cap.time_s, y, label=cfg.analysis.channel)
        for ev in events:
            ax.axvspan(cap.time_s[ev.start_idx], cap.time_s[ev.end_idx], alpha=0.15)
            seg_t = cap.time_s[ev.start_idx : ev.end_idx + 1] - cap.time_s[ev.start_idx]
            seg_y = y[ev.start_idx : ev.end_idx + 1]
            overlay_ax.plot(
                seg_t,
                seg_y,
                alpha=0.8,
                label=Path(csv_path).stem if len(events) == 1 else None,
            )
            if len(seg_y) > int(2 * cap.fs_estimate_hz):
                hold_slice = seg_y[int(0.5 * len(seg_y)) :]
                f, pxx = welch_psd(hold_slice, cap.fs_estimate_hz)
                if f.size:
                    hold_ax.semilogy(
                        f,
                        pxx,
                        alpha=0.8,
                        label=Path(csv_path).stem if len(events) == 1 else None,
                    )
        ax.set_title(f"Detected grip events — {Path(csv_path).name}")
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Signal")
        ax.grid(True)
        fig.tight_layout()
        fig.savefig(outdir / f"events_{Path(csv_path).stem}.png", dpi=dpi)
        plt.close(fig)

    if all_metrics:
        metrics_df = pd.concat(all_metrics, ignore_index=True)
    else:
        metrics_df = pd.DataFrame(
            columns=[
                "file",
                "event_index",
                "start_time_s",
                "peak_time_s",
                "end_time_s",
                "duration_s",
                "peak_value",
                "baseline_value",
                "rise_10_90_s",
                "max_dfdt",
                "hold_std_last_20pct",
            ]
        )
    save_csv(outdir / "event_metrics.csv", metrics_df)
    save_json(outdir / "summary.json", summary)

    overlay_ax.set_title("Grip-event overlay")
    overlay_ax.set_xlabel("Time since event start [s]")
    overlay_ax.set_ylabel("Signal")
    overlay_ax.grid(True)
    overlay_fig.tight_layout()
    overlay_fig.savefig(outdir / "event_overlay.png", dpi=dpi)
    plt.close(overlay_fig)

    hold_ax.set_title("Hold-segment PSD")
    hold_ax.set_xlabel("Frequency [Hz]")
    hold_ax.set_ylabel("PSD [signal² / Hz]")
    hold_ax.grid(True)
    hold_fig.tight_layout()
    hold_fig.savefig(outdir / "hold_psd.png", dpi=dpi)
    plt.close(hold_fig)
    log.info("Stage 4 complete — outputs in %s", outdir)


if __name__ == "__main__":
    main()
