#!/usr/bin/env python3
# @package scripts.stage6_filter_design
# @brief Stage 6a filter design benchmark for a single signal.

"""Stage 6a — Filter design: single-signal candidate benchmark."""

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
    load_filter_specs,
    welch_psd,
)
from handgrip_analysis.io import ensure_dir, load_capture
from handgrip_analysis.report import save_json
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


# @brief Execute Stage 6a filter design benchmark and save outputs.
# @param cfg Hydra configuration object.
# @return None.
@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(level=cfg.logging.level, log_file=cfg.logging.file)
    log.info("Stage 6a — filter design benchmark")

    input_path = _require_str(cfg, "input")
    outdir_path = _require_str(cfg, "outdir")

    outdir = ensure_dir(outdir_path)
    cap = load_capture(input_path, time_source=cfg.io.time_source)
    t, y, fs = cap.time_s, cap.series("raw"), cap.fs_estimate_hz

    ev_cfg = cfg.dsp.event_detection
    raw_metrics = best_event_metrics(
        y,
        t,
        fs,
        baseline_s=ev_cfg.baseline_s,
        threshold_sigma=cfg.analysis.get("threshold_sigma", ev_cfg.threshold_sigma),
        min_duration_s=ev_cfg.min_duration_s,
        merge_gap_s=ev_cfg.merge_gap_s,
        pad_s=ev_cfg.pad_s,
    )

    rest = None
    if cfg.get("rest_input"):
        cap_rest = load_capture(cfg.rest_input, time_source=cfg.io.time_source)
        rest = (cap_rest.time_s, cap_rest.series("raw"), cap_rest.fs_estimate_hz)

    specs = load_filter_specs(cfg.analysis.filter_config)
    hf_lo, hf_hi = list(cfg.analysis.hf_noise_band_hz)
    dpi = cfg.dsp.plot.dpi

    fig_time, ax_time = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_wide))
    ax_time.plot(t, y, label="raw", linewidth=1.1)
    fig_psd, ax_psd = plt.subplots(figsize=tuple(cfg.dsp.plot.figsize_square))
    f_raw, p_raw = welch_psd(y, fs)
    if f_raw.size:
        ax_psd.semilogy(f_raw, p_raw, label="raw", linewidth=1.1)

    rows = []
    for spec in specs:
        name = spec["name"]
        log.info("Benchmarking filter: %s", name)
        y_f = apply_filter_spec(y, fs, spec)
        m = best_event_metrics(
            y_f,
            t,
            fs,
            baseline_s=ev_cfg.baseline_s,
            threshold_sigma=cfg.analysis.get("threshold_sigma", ev_cfg.threshold_sigma),
            min_duration_s=ev_cfg.min_duration_s,
            merge_gap_s=ev_cfg.merge_gap_s,
            pad_s=ev_cfg.pad_s,
        )
        row: dict = {
            "filter": name,
            "n_events": m["n_events"],
            "peak_value": m["peak_value"],
            "peak_error_vs_raw": m["peak_value"] - raw_metrics["peak_value"],
            "peak_time_shift_s": m["peak_time_s"] - raw_metrics["peak_time_s"],
            "rise_10_90_shift_s": m["rise_10_90_s"] - raw_metrics["rise_10_90_s"],
            "max_dfdt_ratio_vs_raw": (
                m["max_dfdt"] / raw_metrics["max_dfdt"] if raw_metrics["max_dfdt"] else float("nan")
            ),
            "plateau_std_last20pct": m["plateau_std_last20pct"],
        }
        if rest is not None:
            _, y_rest, fs_rest = rest
            y_rest_f = apply_filter_spec(y_rest, fs_rest, spec)
            row["rest_std"] = float(pd.Series(y_rest_f).std())
            f_rest, p_rest = welch_psd(y_rest_f, fs_rest)
            mask = (f_rest >= hf_lo) & (f_rest <= hf_hi)
            row["rest_bandpower_hf_hz"] = float(p_rest[mask].sum()) if mask.any() else float("nan")
        rows.append(row)

        ax_time.plot(t, y_f, label=name, alpha=0.8)
        f_f, p_f = welch_psd(y_f, fs)
        if f_f.size:
            ax_psd.semilogy(f_f, p_f, label=name, alpha=0.8)

    df = pd.DataFrame(rows).reindex(pd.Series(rows).apply(lambda r: abs(r["peak_error_vs_raw"])).sort_values().index)
    df.to_csv(outdir / "filter_comparison.csv", index=False)

    save_json(
        outdir / "summary.json",
        {
            "input": str(Path(input_path).resolve()),
            "rest_input": str(Path(cfg.rest_input).resolve()) if cfg.get("rest_input") else None,
            "fs_hz": fs,
            "selected_event_raw_metrics": raw_metrics,
            "n_candidates": len(specs),
        },
    )

    ax_time.set_title("Stage 6a — dynamic overlay (calibration signal)")
    ax_time.set_xlabel("Time [s]")
    ax_time.set_ylabel("Raw counts")
    ax_time.grid(True)
    ax_time.legend(fontsize=8, loc="best")
    fig_time.tight_layout()
    fig_time.savefig(outdir / "time_overlay.png", dpi=dpi)
    plt.close(fig_time)

    ax_psd.set_title("Stage 6a — dynamic PSD comparison")
    ax_psd.set_xlabel("Frequency [Hz]")
    ax_psd.set_ylabel("PSD [counts²/Hz]")
    ax_psd.grid(True)
    ax_psd.legend(fontsize=8, loc="best")
    fig_psd.tight_layout()
    fig_psd.savefig(outdir / "psd_overlay.png", dpi=dpi)
    plt.close(fig_psd)
    log.info("Stage 6a complete — outputs in %s", outdir)


if __name__ == "__main__":
    main()
