# @file
# @brief Offline analyzer for the XY staircase investigation.
##
# Estimates the inter-stream lag of fast force steps from data captured by:
# - the LSL_Viewer diagnostics recorder session dir (metrics.jsonl + sample CSVs),
# - optionally the LSL_Bridge per-stream CSVs (publisher-side ground truth),
# - optionally the RS485_GUI interpreted_signal.ndjson (monotonic adjust trace).
##
# Usage:
#   uv run python scripts/analyze_xy_lag.py --viewer-session diagnostics/<ts> \
#       [--bridge-target-csv ...] [--bridge-reference-csv ...] [--gui-ndjson ...]
##
# Verdict logic (see plan):
# - persistent LSL-time lag, target anchor drift small, adjust trace large -> RS485 stamping (a2)
# - persistent lag with large target anchor drift -> target anchoring (a1)
# - lag ~0 but viewer dropped-count spikes during steps -> viewer raw_lsl exclusion (b)

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STEP_MIN_REL_AMPLITUDE = 0.30  # fraction of robust signal span
STEP_EDGE_WINDOW_S = 0.25  # window over which a step must complete
STEP_MIN_SEPARATION_S = 1.0  # merge onsets closer than this
LEVEL_WINDOW_S = 0.5  # pre/post level estimation window
ONSET_PAIRING_TOLERANCE_S = 0.5  # max distance when pairing onsets across streams
XCORR_RATE_HZ = 500.0


# ---------------------------------------------------------------------------
# Step detection
# ---------------------------------------------------------------------------


def detect_step_onsets(t: np.ndarray, y: np.ndarray) -> list[dict]:
    # @brief Detect fast step onsets via mid-level crossing of large transitions.
    # @param t Sample timestamps (seconds, any shared epoch).
    # @param y Signal values.
    # @return List of dicts: onset_s, direction, pre_level, post_level, amplitude.
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(t) & np.isfinite(y)
    t, y = t[finite], y[finite]
    order = np.argsort(t)
    t, y = t[order], y[order]
    if t.size < 10:
        return []

    p5, p95 = np.percentile(y, [5, 95])
    span = p95 - p5
    if span <= 0:
        return []
    ynorm = (y - p5) / span

    # Change of the signal across a short forward-looking window.
    idx_fwd = np.searchsorted(t, t + STEP_EDGE_WINDOW_S, side="right") - 1
    idx_fwd = np.clip(idx_fwd, 0, t.size - 1)
    delta = ynorm[idx_fwd] - ynorm
    candidates = np.where(np.abs(delta) >= STEP_MIN_REL_AMPLITUDE)[0]
    if candidates.size == 0:
        return []

    # Group candidate indices into events separated by min separation.
    events: list[tuple[int, int]] = []
    start = candidates[0]
    prev = candidates[0]
    for i in candidates[1:]:
        if t[i] - t[prev] > STEP_MIN_SEPARATION_S:
            events.append((start, prev))
            start = i
        prev = i
    events.append((start, prev))

    onsets: list[dict] = []
    for lo, hi in events:
        t_lo, t_hi = t[lo], t[min(hi + 1, t.size - 1)] + STEP_EDGE_WINDOW_S
        pre_mask = (t >= t_lo - LEVEL_WINDOW_S) & (t < t_lo)
        post_mask = (t > t_hi) & (t <= t_hi + LEVEL_WINDOW_S)
        if not np.any(pre_mask) or not np.any(post_mask):
            continue
        pre_level = float(np.median(y[pre_mask]))
        post_level = float(np.median(y[post_mask]))
        amplitude = post_level - pre_level
        if abs(amplitude) < STEP_MIN_REL_AMPLITUDE * span:
            continue
        mid = pre_level + 0.5 * amplitude
        region = (t >= t_lo) & (t <= t_hi)
        rt, ry = t[region], y[region]
        crossed = ry >= mid if amplitude > 0 else ry <= mid
        if not np.any(crossed):
            continue
        onsets.append(
            {
                "onset_s": float(rt[np.argmax(crossed)]),
                "direction": "rise" if amplitude > 0 else "fall",
                "pre_level": pre_level,
                "post_level": post_level,
                "amplitude": amplitude,
            }
        )
    return onsets


def pair_onsets(target_onsets: list[dict], reference_onsets: list[dict]) -> list[dict]:
    # @brief Pair target/reference onsets by nearest time within tolerance.
    # @param target_onsets Onsets detected on the target stream.
    # @param reference_onsets Onsets detected on the reference stream.
    # @return List of dicts with both onsets and lag_s = target - reference.
    pairs: list[dict] = []
    used: set[int] = set()
    for ton in target_onsets:
        best_j, best_dt = None, math.inf
        for j, ron in enumerate(reference_onsets):
            if j in used or ron["direction"] != ton["direction"]:
                continue
            dt = abs(ton["onset_s"] - ron["onset_s"])
            if dt < best_dt:
                best_j, best_dt = j, dt
        if best_j is not None and best_dt <= ONSET_PAIRING_TOLERANCE_S:
            used.add(best_j)
            ron = reference_onsets[best_j]
            pairs.append(
                {
                    "direction": ton["direction"],
                    "target_onset_s": ton["onset_s"],
                    "reference_onset_s": ron["onset_s"],
                    "lag_s": ton["onset_s"] - ron["onset_s"],
                }
            )
    return pairs


def cross_correlation_lag_s(
    t_a: np.ndarray, y_a: np.ndarray, t_b: np.ndarray, y_b: np.ndarray
) -> float | None:
    # @brief Whole-recording lag estimate (a relative to b) via cross-correlation.
    # @return Lag in seconds (positive = a later than b), or None when not computable.
    t0 = max(np.nanmin(t_a), np.nanmin(t_b))
    t1 = min(np.nanmax(t_a), np.nanmax(t_b))
    if not (math.isfinite(t0) and math.isfinite(t1)) or t1 - t0 < 2.0:
        return None
    grid = np.arange(t0, t1, 1.0 / XCORR_RATE_HZ)
    a = np.interp(grid, t_a, y_a)
    b = np.interp(grid, t_b, y_b)
    a = (a - a.mean()) / (a.std() or 1.0)
    b = (b - b.mean()) / (b.std() or 1.0)
    corr = np.correlate(a, b, mode="full")
    lag_samples = int(np.argmax(corr)) - (grid.size - 1)
    return lag_samples / XCORR_RATE_HZ


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_viewer_session(session: Path) -> dict:
    # @brief Load metrics.jsonl and sample CSVs from a viewer session dir.
    out: dict = {}
    metrics_path = session / "metrics.jsonl"
    if metrics_path.exists():
        out["metrics"] = pd.DataFrame(
            json.loads(line) for line in metrics_path.read_text().splitlines() if line.strip()
        )
    for name, key in (("target_samples.csv", "target"), ("reference_samples.csv", "reference")):
        path = session / name
        if path.exists():
            out[key] = pd.read_csv(path)
    return out


def load_gui_ndjson(path: Path) -> pd.DataFrame:
    # @brief Load RS485_GUI interpreted_signal.ndjson rows (flat interpreted dicts).
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.json_normalize(rows)


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------


def report_onset_lags(
    label: str, t_t: np.ndarray, y_t: np.ndarray, t_r: np.ndarray, y_r: np.ndarray
) -> None:
    # @brief Print per-step and whole-recording lag for one source pair.
    target_onsets = detect_step_onsets(t_t, y_t)
    reference_onsets = detect_step_onsets(t_r, y_r)
    print(f"\n=== {label} ===")
    print(f"target steps detected   : {len(target_onsets)}")
    print(f"reference steps detected: {len(reference_onsets)}")
    pairs = pair_onsets(target_onsets, reference_onsets)
    if pairs:
        lags = np.array([p["lag_s"] for p in pairs])
        for p in pairs:
            print(
                f"  {p['direction']:<4} target@{p['target_onset_s']:.3f}  "
                f"reference@{p['reference_onset_s']:.3f}  "
                f"lag(target-reference)={p['lag_s']*1e3:+.1f} ms"
            )
        print(
            f"  onset lag: mean={lags.mean()*1e3:+.1f} ms  median={np.median(lags)*1e3:+.1f} ms  "
            f"n={lags.size}"
        )
    else:
        print("  no pairable step onsets found")
    xlag = cross_correlation_lag_s(t_t, y_t, t_r, y_r)
    if xlag is not None:
        print(f"  cross-correlation lag (target vs reference): {xlag*1e3:+.1f} ms")


def report_viewer_metrics(metrics: pd.DataFrame) -> None:
    # @brief Summarize per-tick viewer metrics relevant to the staircase.
    print("\n=== Viewer per-tick metrics ===")
    print(f"ticks: {len(metrics)}")
    for col, scale, unit in (
        ("tail_delta_s", 1e3, "ms"),
        ("shift_s", 1e3, "ms"),
        ("target_dropped_newer_than_ref_tail", 1, "samples"),
        ("xy_pair_count", 1, "pairs"),
    ):
        if col in metrics and metrics[col].notna().any():
            s = metrics[col].dropna().astype(float) * scale
            print(
                f"  {col:<38} min={s.min():+.2f} median={s.median():+.2f} "
                f"max={s.max():+.2f} {unit}"
            )
    if "target_dropped_newer_than_ref_tail" in metrics:
        dropped = metrics["target_dropped_newer_than_ref_tail"].fillna(0).astype(float)
        spike_ticks = int((dropped > 0).sum())
        print(f"  ticks with freshest-target exclusion > 0: {spike_ticks}/{len(metrics)}")


def report_target_anchor_drift(df: pd.DataFrame) -> None:
    # @brief Summarize bridge-side target anchor drift (published - arrival).
    if "arrival_lsl_time_s" not in df or df["arrival_lsl_time_s"].isna().all():
        print("\n=== Target anchor drift: arrival_lsl_time_s column absent (older bridge CSV) ===")
        return
    drift = (df["lsl_timestamp_s"].astype(float) - df["arrival_lsl_time_s"].astype(float)) * 1e3
    print("\n=== Target anchor drift (published - arrival, bridge CSV) ===")
    print(
        f"  min={drift.min():+.2f} ms  median={drift.median():+.2f} ms  "
        f"max={drift.max():+.2f} ms  (a1 if comparable to observed lag)"
    )


def report_gui_adjust(df: pd.DataFrame) -> None:
    # @brief Summarize RS485_GUI monotonic adjust magnitudes from ndjson diagnostics.
    cols = [c for c in df.columns if c.endswith("monotonic_adjust_s")]
    if not cols:
        print("\n=== GUI monotonic adjust: not present in ndjson (older RS485_GUI) ===")
        return
    adj = df[cols[0]].dropna().astype(float)
    nonzero = adj[adj > 0]
    print("\n=== RS485_GUI monotonic timestamp adjust ===")
    print(f"  frames={len(adj)}  adjusted={len(nonzero)}")
    if len(nonzero):
        print(
            f"  adjust_s: median={nonzero.median()*1e3:.2f} ms  max={nonzero.max()*1e3:.2f} ms  "
            f"total={nonzero.sum()*1e3:.1f} ms  (a2 if comparable to observed lag)"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    # @brief CLI entry point.
    parser = argparse.ArgumentParser(description="Analyze XY staircase capture data.")
    parser.add_argument("--viewer-session", type=Path, help="LSL_Viewer diagnostics session dir")
    parser.add_argument("--bridge-target-csv", type=Path, help="LSL_Bridge target CSV")
    parser.add_argument("--bridge-reference-csv", type=Path, help="LSL_Bridge reference CSV")
    parser.add_argument("--gui-ndjson", type=Path, help="RS485_GUI interpreted_signal.ndjson")
    args = parser.parse_args(argv)

    if not any((args.viewer_session, args.bridge_target_csv and args.bridge_reference_csv)):
        parser.error("provide --viewer-session and/or both --bridge-*-csv paths")

    if args.viewer_session:
        data = load_viewer_session(args.viewer_session)
        if "target" in data and "reference" in data:
            report_onset_lags(
                "Viewer-received samples (LSL time)",
                data["target"]["lsl_timestamp_s"].to_numpy(),
                data["target"]["raw"].to_numpy(),
                data["reference"]["lsl_timestamp_s"].to_numpy(),
                data["reference"]["raw"].to_numpy(),
            )
        if "metrics" in data:
            report_viewer_metrics(data["metrics"])

    if args.bridge_target_csv and args.bridge_reference_csv:
        tdf = pd.read_csv(args.bridge_target_csv)
        rdf = pd.read_csv(args.bridge_reference_csv)
        report_onset_lags(
            "Bridge-published samples (LSL time)",
            tdf["lsl_timestamp_s"].to_numpy(dtype=float),
            tdf["target_raw_count"].to_numpy(dtype=float),
            rdf["lsl_timestamp_s"].to_numpy(dtype=float),
            rdf["reference_force_N"].to_numpy(dtype=float),
        )
        report_target_anchor_drift(tdf)

    if args.gui_ndjson:
        report_gui_adjust(load_gui_ndjson(args.gui_ndjson))

    print(
        "\nNote: reference_clock_s is host-derived (active_send reconstructed LSL clock), "
        "not an independent device clock; cross-stream device-clock onset comparison is "
        "only meaningful for the target's device_clock_us drift trace."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
