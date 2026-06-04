#!/usr/bin/env python3
"""
Analyze step-hold relaxation / rebound in Handgrip_Calibration sessions.

Default channel assumptions for the current D2 + RS485 LSL CSVs:
  target.csv:    channel_0=seq, channel_1=device_clock_us, channel_2=target_raw_count,
                 channel_3=target_current_units, channel_4=target_filtered_units, channel_5=status
  reference.csv: channel_0=seq, channel_1=reference_clock_s, channel_2=reference_force_N,
                 channel_3=status

Usage from the Handgrip_Calibration repo root:
  python scripts/analyze_step_relaxation.py \
    data/calibration/2026-05-13_055327_handgrip_cal \
    --out-dir data/calibration/2026-05-13_055327_handgrip_cal/relaxation_diagnostics

The script writes:
  - step_relaxation_metrics.csv
  - step_shape_correlations.csv
  - actual_hold_dataset.csv
  - relaxation_summary.md
  - several PNG diagnostic plots
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from scipy.optimize import curve_fit
except Exception:  # scipy is optional; exponential diagnostics are skipped without it.
    curve_fit = None

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


def load_events(session_dir: Path) -> list[dict[str, Any]]:
    path = session_dir / "events.ndjson"
    if not path.exists():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def index_events(events: list[dict[str, Any]]) -> tuple[dict[str, dict[str, dict[str, Any]]], set[str]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    accepted: set[str] = set()
    rejected: set[str] = set()
    for event in events:
        trial_id = event.get("trial_id")
        name = event.get("event")
        if not trial_id or not name:
            continue
        indexed.setdefault(str(trial_id), {})[str(name)] = event
        if name == "trial_accept":
            accepted.add(str(trial_id))
        elif name == "trial_reject":
            rejected.add(str(trial_id))
    return indexed, accepted - rejected


def event_time(event: dict[str, Any]) -> float:
    if event.get("lsl_time") is not None:
        return float(event["lsl_time"])
    return float(event["host_time_unix"])


def rolling_median(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return values
    return pd.Series(values).rolling(window, center=True, min_periods=1).median().to_numpy()


def linear_fit(t: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    mask = np.isfinite(t) & np.isfinite(y)
    t = t[mask]
    y = y[mask]
    if len(t) < 3:
        return np.nan, np.nan, np.nan
    x = t - t[0]
    design = np.vstack([x, np.ones_like(x)]).T
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return float(slope), float(intercept), float(r2)


def exp_model(t: np.ndarray, c: float, a: float, tau: float) -> np.ndarray:
    return c + a * np.exp(-t / tau)


def exponential_fit(t: np.ndarray, y: np.ndarray) -> dict[str, float]:
    empty = {"exp_C": np.nan, "exp_A": np.nan, "exp_tau_s": np.nan, "exp_r2": np.nan}
    if curve_fit is None:
        return empty
    mask = np.isfinite(t) & np.isfinite(y)
    t = t[mask]
    y = y[mask]
    if len(t) < 20 or t[-1] <= t[0]:
        return empty

    # Downsample robustly to around 20 Hz for speed and to reduce quantization noise.
    duration = t[-1] - t[0]
    n_bins = max(20, int(duration * 20))
    bins = np.linspace(t[0], t[-1], n_bins + 1)
    bin_idx = np.digitize(t, bins) - 1
    bx: list[float] = []
    by: list[float] = []
    for i in range(n_bins):
        vals = y[bin_idx == i]
        if len(vals):
            bx.append((bins[i] + bins[i + 1]) / 2 - t[0])
            by.append(float(np.nanmedian(vals)))
    tt = np.asarray(bx, dtype=float)
    yy = rolling_median(np.asarray(by, dtype=float), 3)
    if len(tt) < 10:
        return empty

    c0 = float(np.median(yy[-max(3, len(yy) // 5) :]))
    a0 = float(np.median(yy[: max(3, len(yy) // 10)]) - c0)
    tau0 = max(0.5, min(20.0, duration / 3.0))
    y_range = max(1e-6, float(np.nanmax(yy) - np.nanmin(yy)))
    lower = [float(np.nanmin(yy) - 10 * y_range), -20 * y_range, 0.05]
    upper = [float(np.nanmax(yy) + 10 * y_range), 20 * y_range, 100.0]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            popt, _ = curve_fit(
                exp_model,
                tt,
                yy,
                p0=[c0, a0, tau0],
                bounds=(lower, upper),
                maxfev=20000,
            )
        pred = exp_model(tt, *popt)
        ss_res = float(np.sum((yy - pred) ** 2))
        ss_tot = float(np.sum((yy - np.mean(yy)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        return {
            "exp_C": float(popt[0]),
            "exp_A": float(popt[1]),
            "exp_tau_s": float(popt[2]),
            "exp_r2": float(r2),
        }
    except Exception:
        return empty


def window_metrics(df: pd.DataFrame, t0: float, t1: float, value_col: str, smooth_window: int = 1) -> dict[str, float]:
    if value_col not in df.columns:
        raise KeyError(f"Missing column {value_col!r}. Available: {list(df.columns)}")
    w = df[(df["timestamp_lsl"] >= t0) & (df["timestamp_lsl"] <= t1)][["timestamp_lsl", value_col]].dropna()
    if len(w) < 3:
        return {}
    t = w["timestamp_lsl"].to_numpy(dtype=float)
    y = w[value_col].to_numpy(dtype=float)
    duration = t1 - t0
    edge_s = min(1.0, max(0.4, duration * 0.1))
    start_mask = t <= t0 + edge_s
    end_mask = t >= t1 - edge_s
    y_start = float(np.nanmedian(y[start_mask])) if np.any(start_mask) else float(y[0])
    y_end = float(np.nanmedian(y[end_mask])) if np.any(end_mask) else float(y[-1])
    slope, _, lin_r2 = linear_fit(t, y)
    smoothed = rolling_median(y, smooth_window)
    dy = np.diff(smoothed)
    expected_sign = np.sign(y_end - y_start)
    if expected_sign == 0 or not len(dy):
        monotonic_fraction = np.nan
    else:
        threshold = np.nanpercentile(np.abs(dy), 50) * 0.2
        dym = dy[np.abs(dy) > threshold]
        monotonic_fraction = float(np.mean(np.sign(dym) == expected_sign)) if len(dym) else np.nan
    out = {
        "n": float(len(w)),
        "median": float(np.nanmedian(y)),
        "mean": float(np.nanmean(y)),
        "std": float(np.nanstd(y, ddof=1)),
        "start_median": y_start,
        "end_median": y_end,
        "delta_end_minus_start": float(y_end - y_start),
        "slope_per_s": slope,
        "lin_r2": lin_r2,
        "monotonic_fraction": monotonic_fraction,
    }
    out.update(exponential_fit(t, y))
    return out


def robust_affine(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    design = np.vstack([x, np.ones_like(x)]).T
    a, b = np.linalg.lstsq(design, y, rcond=None)[0]
    return float(a), float(b)


def analyze_session(
    session_dir: Path,
    out_dir: Path,
    target_raw_col: str,
    target_filtered_col: str | None,
    reference_force_col: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = pd.read_csv(session_dir / "target.csv")
    reference = pd.read_csv(session_dir / "reference.csv")
    events = load_events(session_dir)
    indexed, accepted = index_events(events)

    # Fit a temporary force scale for target diagnostics only. This is NOT a deployment model.
    fit_rows: list[dict[str, Any]] = []
    for trial_id in sorted(accepted):
        evs = indexed.get(trial_id, {})
        if "hold_start" not in evs or "hold_end" not in evs:
            continue
        start_event = evs.get("stable_window_start", evs["hold_start"])
        end_event = evs["hold_end"]
        t0 = event_time(start_event)
        t1 = event_time(end_event)
        tw = target[(target["timestamp_lsl"] >= t0) & (target["timestamp_lsl"] <= t1)]
        rw = reference[(reference["timestamp_lsl"] >= t0) & (reference["timestamp_lsl"] <= t1)]
        if len(tw) > 10 and len(rw) > 10:
            fit_rows.append(
                {
                    "trial_id": trial_id,
                    "target_force_nominal_N": evs["hold_start"].get("target_force_N"),
                    "direction": (evs["hold_start"].get("payload") or {}).get("direction"),
                    "target_raw_median": float(tw[target_raw_col].median()),
                    "reference_force_median_N": float(rw[reference_force_col].median()),
                    "t_start_lsl": t0,
                    "t_end_lsl": t1,
                }
            )
    actual_dataset = pd.DataFrame(fit_rows)
    if len(actual_dataset) < 2:
        raise RuntimeError("Not enough accepted hold windows for analysis")
    a, b = robust_affine(
        actual_dataset["target_raw_median"].to_numpy(dtype=float),
        actual_dataset["reference_force_median_N"].to_numpy(dtype=float),
    )
    actual_dataset["target_force_est_median_N"] = a * actual_dataset["target_raw_median"] + b
    actual_dataset.to_csv(out_dir / "actual_hold_dataset.csv", index=False)

    target = target.copy()
    target["target_force_est_N"] = a * target[target_raw_col].astype(float) + b
    if target_filtered_col and target_filtered_col in target.columns:
        target["target_filtered_force_est_N"] = a * target[target_filtered_col].astype(float) + b

    metrics_rows: list[dict[str, Any]] = []
    for trial_id in sorted(accepted):
        evs = indexed.get(trial_id, {})
        if "hold_start" not in evs or "hold_end" not in evs:
            continue
        hold_start = evs["hold_start"]
        hold_end = evs["hold_end"]
        stable_start = evs.get("stable_window_start")
        payload = hold_start.get("payload") or {}
        windows = [
            ("full_hold", event_time(hold_start), event_time(hold_end)),
            ("stable_window", event_time(stable_start or hold_start), event_time(hold_end)),
        ]
        for window_name, t0, t1 in windows:
            row: dict[str, Any] = {
                "session": session_dir.name,
                "trial_id": trial_id,
                "window": window_name,
                "nominal_N": float(hold_start.get("target_force_N") or 0.0),
                "direction": payload.get("direction"),
                "repeat_index": payload.get("repeat_index"),
                "level_index": payload.get("level_index"),
                "duration_s": t1 - t0,
            }
            signals = [
                ("target_raw_N", target, "target_force_est_N", 7),
                ("reference_N", reference, reference_force_col, 11),
            ]
            if "target_filtered_force_est_N" in target.columns:
                signals.append(("target_filtered_N", target, "target_filtered_force_est_N", 7))
            for prefix, df, col, smooth_window in signals:
                for key, value in window_metrics(df, t0, t1, col, smooth_window=smooth_window).items():
                    row[f"{prefix}__{key}"] = value
            metrics_rows.append(row)
    metrics = pd.DataFrame(metrics_rows)
    metrics.to_csv(out_dir / "step_relaxation_metrics.csv", index=False)

    # Shape correlations between target and reference on the full holds.
    corr_rows: list[dict[str, Any]] = []
    for trial_id in sorted(accepted):
        evs = indexed.get(trial_id, {})
        if "hold_start" not in evs or "hold_end" not in evs:
            continue
        t0 = event_time(evs["hold_start"])
        t1 = event_time(evs["hold_end"])
        tw = target[(target["timestamp_lsl"] >= t0) & (target["timestamp_lsl"] <= t1)]
        rw = reference[(reference["timestamp_lsl"] >= t0) & (reference["timestamp_lsl"] <= t1)]
        corr = np.nan
        if len(tw) > 10 and len(rw) > 10:
            grid = np.linspace(t0, t1, 101)
            y_target = np.interp(grid, tw["timestamp_lsl"], tw["target_force_est_N"])
            y_ref = np.interp(grid, rw["timestamp_lsl"], rw[reference_force_col])
            y_target = y_target - y_target[0]
            y_ref = y_ref - y_ref[0]
            if np.std(y_target) > 0 and np.std(y_ref) > 0:
                corr = float(np.corrcoef(y_target, y_ref)[0, 1])
        hs = evs["hold_start"]
        corr_rows.append(
            {
                "trial_id": trial_id,
                "nominal_N": float(hs.get("target_force_N") or 0.0),
                "direction": (hs.get("payload") or {}).get("direction"),
                "shape_corr_target_ref": corr,
            }
        )
    correlations = pd.DataFrame(corr_rows)
    correlations.to_csv(out_dir / "step_shape_correlations.csv", index=False)

    write_summary(out_dir, session_dir, target, reference, actual_dataset, metrics, correlations, a, b, target_raw_col, reference_force_col)
    if plt is not None:
        make_plots(out_dir, target, reference, indexed, accepted, metrics, correlations, reference_force_col)


def write_summary(
    out_dir: Path,
    session_dir: Path,
    target: pd.DataFrame,
    reference: pd.DataFrame,
    actual_dataset: pd.DataFrame,
    metrics: pd.DataFrame,
    correlations: pd.DataFrame,
    a: float,
    b: float,
    target_raw_col: str,
    reference_force_col: str,
) -> None:
    primary = metrics[(metrics["window"] == "full_hold") & (metrics["nominal_N"] > 0)].copy()
    lines = []
    lines.append(f"# Step relaxation diagnostics — {session_dir.name}\n")
    lines.append("## Channel assumptions\n")
    lines.append(f"- Target raw column: `{target_raw_col}`")
    lines.append(f"- Reference force column: `{reference_force_col}`")
    lines.append(f"- Temporary target diagnostic scale: `reference_N ~= {a:.12g} * target_raw + {b:.12g}`")
    lines.append("\n## CSV sanity check\n")
    lines.append(f"- target rows: {len(target):,}; reference rows: {len(reference):,}")
    lines.append(f"- target `{target_raw_col}` range: {target[target_raw_col].min():.3g} .. {target[target_raw_col].max():.3g}")
    lines.append(f"- reference `{reference_force_col}` range: {reference[reference_force_col].min():.3g} .. {reference[reference_force_col].max():.3g} N")
    if "channel_0" in reference.columns:
        slope, _, _ = linear_fit(reference["timestamp_lsl"].to_numpy(float), reference["channel_0"].to_numpy(float))
        lines.append(f"- reference `channel_0` linear slope: {slope:.3f} units/s. If this is ~500, it is almost certainly a sequence counter, not force.")
    lines.append("\n## Full-hold relaxation summary\n")
    for sig in ["reference_N", "target_raw_N"]:
        delta = primary[f"{sig}__delta_end_minus_start"]
        slope = primary[f"{sig}__slope_per_s"]
        r2 = primary[f"{sig}__exp_r2"]
        tau = primary[f"{sig}__exp_tau_s"]
        lines.append(f"- `{sig}` median |delta| over 10 s: {np.nanmedian(np.abs(delta)):.3f} N-equivalent")
        lines.append(f"- `{sig}` median |linear slope|: {np.nanmedian(np.abs(slope)):.4f} N/s")
        lines.append(f"- `{sig}` median exponential R²: {np.nanmedian(r2):.3f}; median tau: {np.nanmedian(tau):.2f} s")
        by_dir = primary.groupby("direction")[f"{sig}__delta_end_minus_start"].median().to_dict()
        lines.append(f"- `{sig}` median delta by direction: {by_dir}")
    lines.append("\n## Shape symmetry\n")
    for direction, group in correlations.groupby("direction"):
        vals = group["shape_corr_target_ref"].dropna()
        if len(vals):
            lines.append(f"- {direction}: median target/reference shape correlation = {vals.median():.3f} over {len(vals)} holds")
    lines.append("\n## Files generated\n")
    for name in ["actual_hold_dataset.csv", "step_relaxation_metrics.csv", "step_shape_correlations.csv"]:
        lines.append(f"- `{name}`")
    (out_dir / "relaxation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_plots(
    out_dir: Path,
    target: pd.DataFrame,
    reference: pd.DataFrame,
    indexed: dict[str, dict[str, dict[str, Any]]],
    accepted: set[str],
    metrics: pd.DataFrame,
    correlations: pd.DataFrame,
    reference_force_col: str,
) -> None:
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(exist_ok=True)

    # Delta by nominal level and direction.
    full = metrics[(metrics["window"] == "full_hold") & (metrics["nominal_N"] > 0)].copy()
    for sig in ["reference_N", "target_raw_N"]:
        fig = plt.figure(figsize=(9, 5))
        for direction, marker in [("ascending", "o"), ("descending", "x")]:
            g = full[full["direction"] == direction]
            plt.scatter(g["nominal_N"], g[f"{sig}__delta_end_minus_start"], label=direction, marker=marker)
        plt.axhline(0, linewidth=1)
        plt.xlabel("Nominal step (N)")
        plt.ylabel("End - start over 10 s (N-equivalent)")
        plt.title(f"Relaxation / rebound delta: {sig}")
        plt.legend()
        plt.tight_layout()
        fig.savefig(plot_dir / f"delta_by_level_{sig}.png", dpi=160)
        plt.close(fig)

    # Shape correlations.
    fig = plt.figure(figsize=(8, 5))
    for direction, marker in [("ascending", "o"), ("descending", "x"), ("flat", "s")]:
        g = correlations[correlations["direction"] == direction]
        if len(g):
            plt.scatter(g["nominal_N"], g["shape_corr_target_ref"], label=direction, marker=marker)
    plt.axhline(0, linewidth=1)
    plt.xlabel("Nominal step (N)")
    plt.ylabel("Target/reference normalized shape correlation")
    plt.title("Common-mode shape correlation")
    plt.legend()
    plt.tight_layout()
    fig.savefig(plot_dir / "shape_correlation_by_level.png", dpi=160)
    plt.close(fig)

    # Example high-force ascending and mid-force descending traces if present.
    examples = ["R02_H10_100N", "R02_H16_20N", "R01_H13_55N"]
    for trial_id in examples:
        evs = indexed.get(trial_id)
        if not evs or "hold_start" not in evs or "hold_end" not in evs:
            continue
        t0 = event_time(evs["hold_start"])
        t1 = event_time(evs["hold_end"])
        tw = target[(target["timestamp_lsl"] >= t0) & (target["timestamp_lsl"] <= t1)]
        rw = reference[(reference["timestamp_lsl"] >= t0) & (reference["timestamp_lsl"] <= t1)]
        fig = plt.figure(figsize=(9, 5))
        plt.plot(tw["timestamp_lsl"] - t0, tw["target_force_est_N"] - tw["target_force_est_N"].iloc[0], label="target raw, force-scaled")
        plt.plot(rw["timestamp_lsl"] - t0, rw[reference_force_col] - rw[reference_force_col].iloc[0], label="reference N")
        plt.axhline(0, linewidth=1)
        plt.xlabel("Seconds since hold_start")
        plt.ylabel("Delta from hold start (N-equivalent)")
        plt.title(f"Example relaxation trace: {trial_id}")
        plt.legend()
        plt.tight_layout()
        fig.savefig(plot_dir / f"example_trace_{trial_id}.png", dpi=160)
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Handgrip_Calibration step-hold relaxation.")
    parser.add_argument("session_dir", type=Path, help="Path to a Handgrip_Calibration session directory")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output directory for diagnostics")
    parser.add_argument("--target-raw-col", default="channel_2")
    parser.add_argument("--target-filtered-col", default="channel_4")
    parser.add_argument("--reference-force-col", default="channel_2")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_dir = args.session_dir.resolve()
    out_dir = args.out_dir or (session_dir / "relaxation_diagnostics")
    analyze_session(
        session_dir=session_dir,
        out_dir=out_dir.resolve(),
        target_raw_col=args.target_raw_col,
        target_filtered_col=args.target_filtered_col,
        reference_force_col=args.reference_force_col,
    )
    print(f"Wrote diagnostics to: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
