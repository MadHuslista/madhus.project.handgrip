"""
Plot generation for the manifest-driven analysis pipeline.

The plotting layer is intentionally a thin imperative shell around the pure
stage analyzers.  It reloads captures from the already-validated
:class:`TrialSpec` objects and writes PNG artifacts into the standard Phase 3
figure directories without changing scalar metrics or tables.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import DSPConfig, PlotConfig
from .domain import AnalysisPlan, ConditionSummary, StageConfig, TrialResult, TrialSpec
from .dsp import apply_filter_spec, load_filter_specs, rolling_mean_std_slope, welch_psd
from .io import FILTERED_COLUMN, CaptureData, load_capture
from .stages.stage6_filters import choose_representative_dynamic_trial

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named figure size constants
#
# These map to the archetypes defined in conf/dsp/defaults.yaml (plot.*) and
# PlotConfig.  They are centralised here rather than scattered as inline
# literals to ensure consistent sizing across all stage plot functions.
#
# Override via PlotConfig when calling generate_stage_figures().
# ---------------------------------------------------------------------------

#: Wide time-series plots.  Matches ``PlotConfig.figsize_wide`` default.
FIGSIZE_WIDE: tuple[float, float] = (12.0, 5.0)

#: PSD / histogram comparison plots.  Matches ``PlotConfig.figsize_square`` default.
FIGSIZE_SQUARE: tuple[float, float] = (10.0, 5.0)

#: Multi-panel stacked plots (e.g. Stage 1 four-panel warmup overview).
FIGSIZE_TALL: tuple[float, float] = (12.0, 10.0)

#: Compact event-overlay plots.
FIGSIZE_COMPACT: tuple[float, float] = (8.0, 5.0)

#: Default DPI for saved figures.  Matches ``PlotConfig.dpi`` default.
PLOT_DPI: int = 150

MAX_POINTS = 8_000


def _resolve_plot_cfg(cfg: StageConfig) -> PlotConfig:
    """Extract PlotConfig from StageConfig if available, else return defaults."""
    if hasattr(cfg, "dsp") and isinstance(cfg.dsp, DSPConfig):
        return cfg.dsp.plot
    return PlotConfig()


def _slug(text: str) -> str:
    """Return a filesystem-safe, compact slug."""
    out = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(text).strip())
    return out.strip("-") or "item"


def _trial_slug(spec: TrialSpec) -> str:
    return _slug(f"{spec.session_id}_{spec.stage}_{spec.condition}_{spec.trial_id}")


def _downsample_xy(x: np.ndarray, y: np.ndarray, max_points: int = MAX_POINTS) -> tuple[np.ndarray, np.ndarray]:
    """Return a deterministic plotting subset without modifying analysis data."""
    if x.size <= max_points:
        return x, y
    idx = np.linspace(0, x.size - 1, max_points).astype(int)
    return x[idx], y[idx]


def _series(cap: CaptureData, channel: str) -> np.ndarray:
    if channel == "filtered" and FILTERED_COLUMN not in cap.df.columns:
        channel = "raw"
    return cap.series(channel)  # type: ignore[arg-type]


def _save(fig: plt.Figure, path: Path, paths: dict[str, Path], key_prefix: str, dpi: int = PLOT_DPI) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    paths[key_prefix] = path
    log.info("plotting: wrote %s", path)


def _plot_stage1_trial(result: TrialResult, cfg: StageConfig, outdir: Path, paths: dict[str, Path]) -> None:
    spec = result.spec
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = _series(cap, channel)
    means, stds, slopes = rolling_mean_std_slope(y, cap.fs_estimate_hz, cfg.warmup_window_s)

    fig, axes = plt.subplots(4, 1, figsize=FIGSIZE_TALL, sharex=True)
    x_plot, y_plot = _downsample_xy(cap.time_s, y)
    axes[0].plot(x_plot, y_plot, label=channel)
    axes[0].set_ylabel("Signal")
    axes[0].legend()

    for ax, values, ylabel, label in [
        (axes[1], means, "Mean", "rolling mean"),
        (axes[2], stds, "Std", "rolling std"),
        (axes[3], np.abs(slopes), "|Slope|", "|slope|"),
    ]:
        xp, yp = _downsample_xy(cap.time_s, np.asarray(values, dtype=float))
        ax.plot(xp, yp, label=label)
        ax.set_ylabel(ylabel)
        ax.legend()

    ready = result.metrics.get("suggested_ready_time_s")
    if ready is not None and pd.notna(ready):
        for ax in axes:
            ax.axvline(float(ready), linestyle="--", alpha=0.7)

    for ax in axes:
        ax.grid(True)
    axes[-1].set_xlabel("Time [s]")
    fig.suptitle(f"Stage 1 warm-up — {spec.session_id} {spec.trial_id}")
    _save(fig, outdir / f"{_trial_slug(spec)}_warmup.png", paths, f"figure_{_trial_slug(spec)}_warmup")


def _plot_stage1_aggregate(results: Sequence[TrialResult], outdir: Path, paths: dict[str, Path]) -> None:
    rows = []
    for r in results:
        rows.append(
            {
                "trial": f"{r.spec.session_id}/{r.spec.trial_id}",
                "condition": r.spec.condition,
                "ready_s": r.metrics.get("suggested_ready_time_s", np.nan),
                "final_std": r.metrics.get("final_std", np.nan),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=FIGSIZE_SQUARE)
    ax.scatter(np.arange(len(df)), df["ready_s"].astype(float))
    ax.set_xticks(np.arange(len(df)))
    ax.set_xticklabels(df["trial"], rotation=45, ha="right")
    ax.set_ylabel("Suggested ready time [s]")
    ax.set_title("Stage 1 — ready time by trial")
    ax.grid(True, axis="y")
    _save(fig, outdir / "stage1_ready_time_by_trial.png", paths, "figure_stage1_ready_time_by_trial")

    fig2, ax2 = plt.subplots(figsize=FIGSIZE_SQUARE)
    ax2.scatter(np.arange(len(df)), df["final_std"].astype(float))
    ax2.set_xticks(np.arange(len(df)))
    ax2.set_xticklabels(df["trial"], rotation=45, ha="right")
    ax2.set_ylabel("Final rolling std")
    ax2.set_title("Stage 1 — final noise by trial")
    ax2.grid(True, axis="y")
    _save(fig2, outdir / "stage1_final_std_by_trial.png", paths, "figure_stage1_final_std_by_trial")


def _psd_tables(result: TrialResult) -> list[tuple[str, pd.DataFrame]]:
    return [
        (name, table)
        for name, table in result.tables.items()
        if "psd" in name and "peak" not in name and {"frequency_hz", "psd"}.issubset(table.columns)
    ]


def _allan_tables(result: TrialResult) -> list[tuple[str, pd.DataFrame]]:
    return [
        (name, table)
        for name, table in result.tables.items()
        if "allan" in name and {"tau_s", "allan_deviation"}.issubset(table.columns)
    ]


def _plot_time_hist_trial(result: TrialResult, cfg: StageConfig, outdir: Path, paths: dict[str, Path], stage_title: str) -> None:
    spec = result.spec
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channels = cfg.channels or (spec.channel or cfg.channel,)

    fig_time, ax_time = plt.subplots(figsize=FIGSIZE_WIDE)
    fig_hist, ax_hist = plt.subplots(figsize=FIGSIZE_COMPACT)
    plotted = False
    for channel in channels:
        if channel == "filtered" and FILTERED_COLUMN not in cap.df.columns:
            continue
        y = _series(cap, channel)
        xp, yp = _downsample_xy(cap.time_s, y)
        ax_time.plot(xp, yp, label=channel)
        ax_hist.hist(y[np.isfinite(y)], bins=80, density=True, histtype="step", label=channel)
        plotted = True
    if not plotted:
        y = _series(cap, spec.channel or cfg.channel)
        xp, yp = _downsample_xy(cap.time_s, y)
        ax_time.plot(xp, yp, label=spec.channel or cfg.channel)
        ax_hist.hist(y[np.isfinite(y)], bins=80, density=True, histtype="step", label=spec.channel or cfg.channel)
    ax_time.set_title(f"{stage_title} — time series — {spec.session_id} {spec.trial_id}")
    ax_time.set_xlabel("Time [s]")
    ax_time.set_ylabel("Signal")
    ax_time.grid(True)
    ax_time.legend()
    _save(fig_time, outdir / f"{_trial_slug(spec)}_time_series.png", paths, f"figure_{_trial_slug(spec)}_time_series")

    ax_hist.set_title(f"{stage_title} — histogram — {spec.session_id} {spec.trial_id}")
    ax_hist.set_xlabel("Signal")
    ax_hist.set_ylabel("Density")
    ax_hist.grid(True)
    ax_hist.legend()
    _save(fig_hist, outdir / f"{_trial_slug(spec)}_histogram.png", paths, f"figure_{_trial_slug(spec)}_histogram")


def _plot_psd_allan_trial(result: TrialResult, outdir: Path, paths: dict[str, Path], stage_title: str) -> None:
    spec = result.spec
    psd_items = _psd_tables(result)
    if psd_items:
        fig, ax = plt.subplots(figsize=FIGSIZE_COMPACT)
        for name, df in psd_items:
            ax.semilogy(df["frequency_hz"].to_numpy(float), df["psd"].to_numpy(float), label=name.replace("_psd", ""))
        ax.set_title(f"{stage_title} — Welch PSD — {spec.session_id} {spec.trial_id}")
        ax.set_xlabel("Frequency [Hz]")
        ax.set_ylabel("PSD [signal²/Hz]")
        ax.grid(True, which="both")
        ax.legend()
        _save(fig, outdir / f"{_trial_slug(spec)}_psd.png", paths, f"figure_{_trial_slug(spec)}_psd")

    allan_items = _allan_tables(result)
    if allan_items:
        fig, ax = plt.subplots(figsize=FIGSIZE_COMPACT)
        for name, df in allan_items:
            ax.loglog(df["tau_s"].to_numpy(float), df["allan_deviation"].to_numpy(float), label=name.replace("_allan", ""))
        ax.set_title(f"{stage_title} — Allan deviation — {spec.session_id} {spec.trial_id}")
        ax.set_xlabel("Tau [s]")
        ax.set_ylabel("Allan deviation")
        ax.grid(True, which="both")
        ax.legend()
        _save(fig, outdir / f"{_trial_slug(spec)}_allan_deviation.png", paths, f"figure_{_trial_slug(spec)}_allan")


def _plot_psd_aggregate(results: Sequence[TrialResult], outdir: Path, paths: dict[str, Path], stage_title: str) -> None:
    by_key: dict[tuple[str, str], list[pd.DataFrame]] = {}
    for result in results:
        for name, table in _psd_tables(result):
            by_key.setdefault((result.spec.condition, name), []).append(table)
    for (condition, table_name), tables in by_key.items():
        if not tables:
            continue
        f_max = min(float(t["frequency_hz"].max()) for t in tables if not t.empty)
        if not np.isfinite(f_max) or f_max <= 0:
            continue
        grid = np.linspace(0.0, f_max, 512)
        values = []
        fig, ax = plt.subplots(figsize=FIGSIZE_COMPACT)
        for table in tables:
            f = table["frequency_hz"].to_numpy(float)
            p = table["psd"].to_numpy(float)
            interp = np.interp(grid, f, p)
            values.append(interp)
            ax.semilogy(grid, interp, alpha=0.25)
        median = np.nanmedian(np.vstack(values), axis=0)
        ax.semilogy(grid, median, linewidth=2.0, label="median")
        ax.set_title(f"{stage_title} — {condition} — {table_name} median PSD")
        ax.set_xlabel("Frequency [Hz]")
        ax.set_ylabel("PSD [signal²/Hz]")
        ax.grid(True, which="both")
        ax.legend()
        _save(fig, outdir / f"{_slug(condition)}_{_slug(table_name)}_median_psd.png", paths, f"figure_{_slug(condition)}_{_slug(table_name)}_median_psd")


def _plot_stage3_trial(result: TrialResult, cfg: StageConfig, outdir: Path, paths: dict[str, Path]) -> None:
    spec = result.spec
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = _series(cap, channel)
    slope = float(result.metrics.get("drift_slope_per_s", np.nan))
    intercept = float(result.metrics.get("trend_intercept", np.nan))
    trend = slope * cap.time_s + intercept if np.isfinite(slope) and np.isfinite(intercept) else np.full_like(y, np.nan)
    detrended = y - trend

    fig, axes = plt.subplots(2, 1, figsize=FIGSIZE_TALL, sharex=True)
    x, yp = _downsample_xy(cap.time_s, y)
    axes[0].plot(x, yp, label=channel)
    if np.all(np.isfinite(trend)):
        xt, tr = _downsample_xy(cap.time_s, trend)
        axes[0].plot(xt, tr, linestyle="--", label="linear trend")
    axes[0].set_ylabel("Signal")
    axes[0].legend()
    xd, yd = _downsample_xy(cap.time_s, detrended)
    axes[1].plot(xd, yd, label="detrended")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Residual")
    axes[1].legend()
    for ax in axes:
        ax.grid(True)
    fig.suptitle(f"Stage 3 loaded drift — {spec.session_id} {spec.trial_id}")
    _save(fig, outdir / f"{_trial_slug(spec)}_loaded_drift.png", paths, f"figure_{_trial_slug(spec)}_loaded_drift")


def _plot_metric_scatter(results: Sequence[TrialResult], outdir: Path, paths: dict[str, Path], metric: str, title: str, ylabel: str) -> None:
    rows = [
        {"trial": f"{r.spec.session_id}/{r.spec.trial_id}", "condition": r.spec.condition, "value": r.metrics.get(metric, np.nan)}
        for r in results
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=FIGSIZE_SQUARE)
    ax.scatter(np.arange(len(df)), pd.to_numeric(df["value"], errors="coerce"))
    ax.set_xticks(np.arange(len(df)))
    ax.set_xticklabels(df["trial"], rotation=45, ha="right")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y")
    _save(fig, outdir / f"{_slug(metric)}_by_trial.png", paths, f"figure_{_slug(metric)}_by_trial")


def _plot_stage4_trial(result: TrialResult, cfg: StageConfig, outdir: Path, paths: dict[str, Path]) -> None:
    spec = result.spec
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = _series(cap, channel)
    events = result.tables.get("event_metrics", pd.DataFrame())

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    x, yp = _downsample_xy(cap.time_s, y)
    ax.plot(x, yp, label=channel)
    if not events.empty:
        for _, row in events.iterrows():
            start = float(row.get("start_time_s", np.nan))
            end = float(row.get("end_time_s", np.nan))
            peak = float(row.get("peak_time_s", np.nan))
            if np.isfinite(start) and np.isfinite(end):
                ax.axvspan(start, end, alpha=0.12)
            if np.isfinite(peak):
                ax.axvline(peak, linestyle="--", alpha=0.6)
    ax.set_title(f"Stage 4 dynamics — {spec.condition} — {spec.session_id} {spec.trial_id}")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Signal")
    ax.grid(True)
    ax.legend()
    _save(fig, outdir / f"{_trial_slug(spec)}_events.png", paths, f"figure_{_trial_slug(spec)}_events")


def _plot_stage4_aggregate(results: Sequence[TrialResult], cfg: StageConfig, outdir: Path, paths: dict[str, Path]) -> None:
    # Event-aligned overlay for the first event of each dynamic trial.
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    plotted = False
    for result in results:
        events = result.tables.get("event_metrics", pd.DataFrame())
        if events.empty:
            continue
        first = events.iloc[0]
        start, end = float(first["start_time_s"]), float(first["end_time_s"])
        cap = load_capture(result.spec.path, time_source=cfg.time_source)
        y = _series(cap, result.spec.channel or cfg.channel)
        mask = (cap.time_s >= start) & (cap.time_s <= end)
        if not mask.any():
            continue
        t_seg = cap.time_s[mask] - start
        y_seg = y[mask]
        t_plot, y_plot = _downsample_xy(t_seg, y_seg, max_points=2_000)
        ax.plot(t_plot, y_plot, alpha=0.65, label=f"{result.spec.condition}/{result.spec.trial_id}")
        plotted = True
    if plotted:
        ax.set_title("Stage 4 — event-aligned overlay")
        ax.set_xlabel("Time since event start [s]")
        ax.set_ylabel("Signal")
        ax.grid(True)
        ax.legend(fontsize=8)
        _save(fig, outdir / "stage4_event_aligned_overlay.png", paths, "figure_stage4_event_aligned_overlay")
    else:
        plt.close(fig)

    _plot_metric_scatter(results, outdir, paths, "peak_value_max", "Stage 4 — peak value by trial", "Peak value")
    _plot_metric_scatter(results, outdir, paths, "rise_10_90_s_median", "Stage 4 — rise time by trial", "Rise 10–90 [s]")


def _stage6_filter_tables(results: Sequence[TrialResult]) -> pd.DataFrame:
    frames = []
    for result in results:
        table = result.tables.get("filter_metrics")
        if table is not None and not table.empty:
            frames.append(table.copy())
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _score_from_filter_table(filter_df: pd.DataFrame, cfg: StageConfig) -> pd.DataFrame:
    if filter_df.empty:
        return pd.DataFrame()
    rows = []
    for filter_name, group in filter_df.groupby("filter", dropna=False):
        row: dict[str, object] = {"filter": filter_name}
        for col in ["rest_std_norm", "peak_relative_error", "rise_relative_error", "peak_time_shift_s", "dfdt_deviation"]:
            if col in group.columns:
                values = pd.to_numeric(group[col], errors="coerce").dropna()
                row[f"{col}__median"] = float(values.median()) if not values.empty else np.nan
        terms = {
            "rest_std_norm": row.get("rest_std_norm__median", np.nan),
            "mean_peak_relative_error": row.get("peak_relative_error__median", np.nan),
            "mean_rise_relative_error": row.get("rise_relative_error__median", np.nan),
            "mean_peak_time_shift_norm": abs(float(row.get("peak_time_shift_s__median", np.nan))) / 0.1,
            "mean_dfdt_deviation": row.get("dfdt_deviation__median", np.nan),
        }
        score = 0.0
        weight_sum = 0.0
        for key, value in terms.items():
            if pd.notna(value) and np.isfinite(float(value)):
                weight = float(cfg.filter_weights.get(key, 0.0))
                score += weight * float(value)
                weight_sum += weight
        row["composite_score"] = score / weight_sum if weight_sum else np.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("composite_score", ascending=True)
    return out


def _plot_stage6_trial(result: TrialResult, cfg: StageConfig, outdir: Path, paths: dict[str, Path]) -> None:
    spec = result.spec
    cap = load_capture(spec.path, time_source=cfg.time_source)
    y = _series(cap, spec.channel or cfg.channel)
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    x, yp = _downsample_xy(cap.time_s, y)
    ax.plot(x, yp, label="raw")
    ax.set_title(f"Stage 6 input trial — {spec.condition} — {spec.session_id} {spec.trial_id}")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Signal")
    ax.grid(True)
    ax.legend()
    _save(fig, outdir / f"{_trial_slug(spec)}_input_signal.png", paths, f"figure_{_trial_slug(spec)}_input_signal")


def _plot_stage6_design_overlay(
    results: Sequence[TrialResult], cfg: StageConfig, outdir: Path, paths: dict[str, Path], ranking: pd.DataFrame
) -> None:
    representative = choose_representative_dynamic_trial(list(results))
    if representative is None or ranking.empty or cfg.filter_config is None:
        return
    try:
        spec_map = {str(s["name"]): s for s in load_filter_specs(cfg.filter_config)}
    except Exception as exc:  # noqa: BLE001
        log.warning("plotting: could not load Stage 6 filter specs for design overlay: %s", exc)
        return
    cap = load_capture(representative.spec.path, time_source=cfg.time_source)
    y = _series(cap, representative.spec.channel or cfg.channel)
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    x, yp = _downsample_xy(cap.time_s, y)
    ax.plot(x, yp, label="raw", linewidth=1.5)
    for name in ranking["filter"].astype(str).head(min(3, len(ranking))):
        spec = spec_map.get(name)
        if spec is None:
            continue
        y_f = apply_filter_spec(y, cap.fs_estimate_hz, spec)
        xf, yf = _downsample_xy(cap.time_s, y_f)
        ax.plot(xf, yf, label=name, alpha=0.9)
    ax.set_title(
        f"Stage 6 — representative dynamic overlay — {representative.spec.condition} — {representative.spec.session_id} {representative.spec.trial_id}"
    )
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Signal")
    ax.grid(True)
    ax.legend(fontsize=8)
    _save(
        fig, outdir / "stage6_design_representative_overlay.png", paths, "figure_stage6_design_representative_overlay"
    )


def _plot_stage6_aggregate(results: Sequence[TrialResult], cfg: StageConfig, outdir: Path, paths: dict[str, Path]) -> None:
    filter_df = _stage6_filter_tables(results)
    ranking = _score_from_filter_table(filter_df, cfg)
    if not ranking.empty:
        fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
        ax.bar(ranking["filter"].astype(str), ranking["composite_score"].astype(float))
        ax.set_title("Stage 6 — composite filter score (lower is better)")
        ax.set_xlabel("Candidate")
        ax.set_ylabel("Score")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, axis="y")
        _save(fig, outdir / "stage6_composite_score.png", paths, "figure_stage6_composite_score")

        _plot_stage6_design_overlay(results, cfg, outdir, paths, ranking)

    # Raw rest PSD vs top-ranked candidates using the first available rest trial.
    if cfg.filter_config is None or ranking.empty:
        return
    rest_result = next((r for r in results if str(r.metrics.get("trial_kind", "")).lower() == "rest"), None)
    if rest_result is None:
        return
    try:
        specs = load_filter_specs(cfg.filter_config)
    except Exception as exc:  # noqa: BLE001 - plotting must not invalidate analysis outputs
        log.warning("plotting: could not load filter specs for Stage 6 aggregate PSD: %s", exc)
        return
    spec_map: Mapping[str, dict] = {str(s["name"]): s for s in specs}
    cap = load_capture(rest_result.spec.path, time_source=cfg.time_source)
    y = _series(cap, rest_result.spec.channel or cfg.channel)
    f_raw, p_raw = welch_psd(y, cap.fs_estimate_hz)
    fig, ax = plt.subplots(figsize=FIGSIZE_COMPACT)
    ax.semilogy(f_raw, p_raw, label="raw rest")
    for name in ranking["filter"].astype(str).head(min(4, len(ranking))):
        if name not in spec_map:
            continue
        y_f = apply_filter_spec(y, cap.fs_estimate_hz, spec_map[name])
        f_f, p_f = welch_psd(y_f, cap.fs_estimate_hz)
        ax.semilogy(f_f, p_f, label=name)
    ax.set_title("Stage 6 — rest PSD raw vs top candidates")
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("PSD [signal²/Hz]")
    ax.grid(True, which="both")
    ax.legend(fontsize=8)
    _save(fig, outdir / "stage6_rest_psd_top_candidates.png", paths, "figure_stage6_rest_psd_top_candidates")


def _plot_stage5_aggregate(results: Sequence[TrialResult], outdir: Path, paths: dict[str, Path]) -> None:
    _plot_psd_aggregate(results, outdir, paths, "Stage 5")
    _plot_metric_scatter(results, outdir, paths, "top_peak_hz", "Stage 5 — top spectral peak by trial", "Frequency [Hz]")
    _plot_metric_scatter(results, outdir, paths, "robust_std", "Stage 5 — robust std by trial", "Robust std")


def generate_stage_figures(
    plan: AnalysisPlan,
    cfg: StageConfig,
    results: Sequence[TrialResult],
    summaries: Sequence[ConditionSummary],
    directories: Mapping[str, Path],
    plot_cfg: PlotConfig | None = None,
) -> dict[str, Path]:
    """
    Generate standard per-trial and aggregate PNG figures for a stage.

    Figure generation is best-effort but intentionally logs and continues on a
    per-figure basis.  Analysis CSV/JSON artifacts remain authoritative even if
    a plot cannot be generated for a malformed trial.

    Parameters
    ----------
    plot_cfg:
        Optional :class:`~handgrip_analysis.config.PlotConfig` controlling
        figure DPI and default sizes.  Falls back to ``cfg.dsp.plot`` if
        ``cfg`` carries a ``DSPConfig``, or to module-level defaults otherwise.
    """
    del summaries  # summaries are kept in the signature for future aggregate plots.
    _plot = plot_cfg or _resolve_plot_cfg(cfg)
    paths: dict[str, Path] = {}
    per_trial = directories["figures_per_trial"]
    aggregate = directories["figures_aggregate"]

    for result in results:
        try:
            if plan.stage == "stage1":
                _plot_stage1_trial(result, cfg, per_trial, paths)
            elif plan.stage == "stage2":
                _plot_time_hist_trial(result, cfg, per_trial, paths, "Stage 2 static noise")
                _plot_psd_allan_trial(result, per_trial, paths, "Stage 2 static noise")
            elif plan.stage == "stage3":
                _plot_stage3_trial(result, cfg, per_trial, paths)
            elif plan.stage == "stage4":
                _plot_stage4_trial(result, cfg, per_trial, paths)
            elif plan.stage == "stage5":
                _plot_time_hist_trial(result, cfg, per_trial, paths, "Stage 5 interference")
                _plot_psd_allan_trial(result, per_trial, paths, "Stage 5 interference")
            elif plan.stage.startswith("stage6"):
                _plot_stage6_trial(result, cfg, per_trial, paths)
        except Exception as exc:  # noqa: BLE001 - keep report generation robust
            log.warning("plotting: skipped per-trial figure for %s: %s", result.spec.identity, exc)

    try:
        if plan.stage == "stage1":
            _plot_stage1_aggregate(results, aggregate, paths)
        elif plan.stage == "stage2":
            _plot_psd_aggregate(results, aggregate, paths, "Stage 2")
            _plot_metric_scatter(results, aggregate, paths, "raw_std", "Stage 2 — raw std by trial", "Std")
            _plot_metric_scatter(results, aggregate, paths, "raw_top_peak_hz", "Stage 2 — top spectral peak by trial", "Frequency [Hz]")
        elif plan.stage == "stage3":
            _plot_metric_scatter(results, aggregate, paths, "drift_slope_per_min", "Stage 3 — drift slope by trial", "Slope [signal/min]")
            _plot_metric_scatter(results, aggregate, paths, "return_to_zero_error", "Stage 3 — return-to-zero error by trial", "Post-pre mean")
        elif plan.stage == "stage4":
            _plot_stage4_aggregate(results, cfg, aggregate, paths)
        elif plan.stage == "stage5":
            _plot_stage5_aggregate(results, aggregate, paths)
        elif plan.stage.startswith("stage6"):
            _plot_stage6_aggregate(results, cfg, aggregate, paths)
    except Exception as exc:  # noqa: BLE001
        log.warning("plotting: skipped aggregate figures for %s: %s", plan.stage, exc)

    return paths
