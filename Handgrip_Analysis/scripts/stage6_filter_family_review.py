#!/usr/bin/env python3
"""Stage 6b — Filter family review: multi-signal ranking with composite score."""
from __future__ import annotations

import logging
from pathlib import Path

import hydra
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from handgrip_analysis._logging import setup_logging
from handgrip_analysis.dsp import (
    apply_filter_spec,
    best_event_metrics,
    dominant_psd_peaks,
    load_filter_specs,
    welch_psd,
)
from handgrip_analysis.io import ensure_dir, load_capture
from handgrip_analysis.report import save_json
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
    log.info("Stage 6b — filter family review")

    rest_input = _require_str(cfg, "rest_input")
    dynamic_inputs = _require_list(cfg, "dynamic_inputs")
    outdir_path = _require_str(cfg, "outdir")

    outdir = ensure_dir(outdir_path)
    ev_cfg = cfg.dsp.event_detection
    hf_lo, hf_hi = list(cfg.analysis.hf_noise_band_hz)
    w = cfg.analysis.filter_weights
    dpi = cfg.dsp.plot.dpi

    # Load rest capture
    cap_rest = load_capture(rest_input, time_source=cfg.io.time_source)
    y_rest, fs_rest = cap_rest.series("raw"), cap_rest.fs_estimate_hz
    f_rest_raw, p_rest_raw = welch_psd(y_rest, fs_rest)

    # Report raw rest PSD peaks
    peaks = dominant_psd_peaks(f_rest_raw, p_rest_raw, fs_rest)
    peak_df = pd.DataFrame([
        {"frequency_hz": p.frequency_hz, "psd": p.psd,
         "prominence_db": p.prominence_db, "alias_hint": p.alias_hint or ""}
        for p in peaks
    ])
    peak_df.to_csv(outdir / "rest_psd_peaks.csv", index=False)

    # Load all dynamic captures and compute raw metrics
    raw_dynamic: dict[str, tuple] = {}
    for path in dynamic_inputs:
        cap = load_capture(path, time_source=cfg.io.time_source)
        t, y, fs = cap.time_s, cap.series("raw"), cap.fs_estimate_hz
        raw_m = best_event_metrics(
            y, t, fs,
            baseline_s=ev_cfg.baseline_s,
            threshold_sigma=ev_cfg.threshold_sigma,
            min_duration_s=ev_cfg.min_duration_s,
            merge_gap_s=ev_cfg.merge_gap_s,
            pad_s=ev_cfg.pad_s,
        )
        raw_dynamic[path] = (t, y, fs, raw_m)

    specs = load_filter_specs(cfg.analysis.filter_config)
    rows = []

    for spec in specs:
        name = spec["name"]
        log.info("Evaluating filter: %s", name)

        # Rest: noise characterisation
        y_rest_f = apply_filter_spec(y_rest, fs_rest, spec)
        f_f, p_f = welch_psd(y_rest_f, fs_rest)
        hf_mask = (f_f >= hf_lo) & (f_f <= hf_hi)
        row: dict = {
            "filter": name,
            "rest_std": float(pd.Series(y_rest_f).std()),
            "rest_peak_to_peak": float(y_rest_f.max() - y_rest_f.min()),
            "rest_hf_sum": float(p_f[hf_mask].sum()) if hf_mask.any() else float("nan"),
        }

        # Dynamic: waveform fidelity
        peak_errs, rise_errs, time_errs, slope_devs = [], [], [], []
        for path, (t, y, fs, raw_m) in raw_dynamic.items():
            filt_m = best_event_metrics(
                apply_filter_spec(y, fs, spec), t, fs,
                baseline_s=ev_cfg.baseline_s,
                threshold_sigma=ev_cfg.threshold_sigma,
                min_duration_s=ev_cfg.min_duration_s,
                merge_gap_s=ev_cfg.merge_gap_s,
                pad_s=ev_cfg.pad_s,
            )
            label = Path(path).stem
            row[f"{label}_peak_error"] = filt_m["peak_value"] - raw_m["peak_value"]
            row[f"{label}_peak_time_shift_s"] = filt_m["peak_time_s"] - raw_m["peak_time_s"]
            row[f"{label}_rise_shift_s"] = filt_m["rise_10_90_s"] - raw_m["rise_10_90_s"]
            dfdt_ratio = (
                filt_m["max_dfdt"] / raw_m["max_dfdt"]
                if raw_m["max_dfdt"]
                else float("nan")
            )
            row[f"{label}_max_dfdt_ratio"] = dfdt_ratio
            peak_errs.append(abs(row[f"{label}_peak_error"]) / max(abs(raw_m["peak_value"]), 1.0))
            rise_errs.append(
                abs(row[f"{label}_rise_shift_s"]) / max(abs(raw_m["rise_10_90_s"]), 1e-6)
            )
            time_errs.append(abs(row[f"{label}_peak_time_shift_s"]) / 0.1)
            slope_devs.append(abs(1.0 - dfdt_ratio) if pd.notna(dfdt_ratio) else float("nan"))

        row["mean_peak_relative_error"] = float(pd.Series(peak_errs).mean())
        row["mean_rise_relative_error"] = float(pd.Series(rise_errs).mean())
        row["mean_peak_time_shift_norm"] = float(pd.Series(time_errs).mean())
        row["mean_dfdt_deviation"] = float(pd.Series(slope_devs).mean())
        rows.append(row)

    df = pd.DataFrame(rows)
    raw_rest_std = float(pd.Series(y_rest).std())
    df["rest_std_norm"] = df["rest_std"] / raw_rest_std
    df["composite_score"] = (
        w.rest_std_norm * df["rest_std_norm"]
        + w.mean_peak_relative_error * df["mean_peak_relative_error"]
        + w.mean_rise_relative_error * df["mean_rise_relative_error"]
        + w.mean_peak_time_shift_norm * df["mean_peak_time_shift_norm"]
        + w.mean_dfdt_deviation * df["mean_dfdt_deviation"]
    )
    df = df.sort_values("composite_score", ascending=True)
    df.to_csv(outdir / "filter_family_assessment.csv", index=False)

    save_json(
        outdir / "summary.json",
        {
            "rest_input": str(Path(rest_input).resolve()),
            "dynamic_inputs": [str(Path(p).resolve()) for p in dynamic_inputs],
            "n_candidates": len(specs),
            "rest_psd_top_peaks_hz": peak_df["frequency_hz"].tolist() if not peak_df.empty else [],
            "top_ranked_filter": str(df.iloc[0]["filter"]) if not df.empty else None,
        },
    )

    # Bar chart of composite scores
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(df["filter"], df["composite_score"])
    ax.set_title("Composite filter score (lower is better)")
    ax.set_ylabel("Score")
    ax.set_xlabel("Candidate")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, axis="y")
    fig.tight_layout()
    fig.savefig(outdir / "composite_score.png", dpi=dpi)
    plt.close(fig)

    # Rest PSD — raw vs top-ranked candidates
    spec_map = {s["name"]: s for s in specs}
    fig2, ax2 = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_square))
    ax2.semilogy(f_rest_raw, p_rest_raw, label="raw rest", linewidth=1.1)
    for name in df["filter"].head(min(4, len(df))).tolist():
        y_f = apply_filter_spec(y_rest, fs_rest, spec_map[name])
        f_f2, p_f2 = welch_psd(y_f, fs_rest)
        ax2.semilogy(f_f2, p_f2, label=name)
    ax2.set_title("Rest PSD — raw vs top-ranked candidates")
    ax2.set_xlabel("Frequency [Hz]")
    ax2.set_ylabel("PSD [counts²/Hz]")
    ax2.grid(True)
    ax2.legend(fontsize=8)
    fig2.tight_layout()
    fig2.savefig(outdir / "rest_psd_top_candidates.png", dpi=dpi)
    plt.close(fig2)
    log.info("Stage 6b complete — outputs in %s", outdir)


if __name__ == "__main__":
    main()
