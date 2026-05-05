"""Markdown/HTML report generation for a calibration session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from .export import ensure_dir, read_ndjson
from .fitting import AffineFitResult, fit_affine_from_dataset


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_plot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def generate_plots(session_dir: str | Path) -> list[Path]:
    """Generate diagnostic plots from session files.

    Plots are intentionally simple and independent. This makes the report useful
    even on a lab PC without an interactive plotting stack.
    """

    session_dir = Path(session_dir)
    plots_dir = ensure_dir(session_dir / "plots")
    generated: list[Path] = []
    target_csv = session_dir / "target.csv"
    reference_csv = session_dir / "reference.csv"
    dataset_csv = session_dir / "calibration_dataset.csv"
    fit_json = session_dir / "fit_result.json"

    if target_csv.exists() and reference_csv.exists():
        target = pd.read_csv(target_csv)
        reference = pd.read_csv(reference_csv)
        if "timestamp_lsl" in target and "raw" in target:
            plt.figure(figsize=(10, 4))
            plt.plot(target["timestamp_lsl"] - target["timestamp_lsl"].iloc[0], target["raw"], label="target raw")
            plt.xlabel("Time since target start [s]")
            plt.ylabel("Target raw / units")
            plt.title("Target time series")
            plt.legend()
            out = plots_dir / "target_timeseries.png"
            _save_plot(out)
            generated.append(out)
        if "timestamp_lsl" in reference and "raw" in reference:
            plt.figure(figsize=(10, 4))
            plt.plot(reference["timestamp_lsl"] - reference["timestamp_lsl"].iloc[0], reference["raw"], label="reference raw/force")
            plt.xlabel("Time since reference start [s]")
            plt.ylabel("Reference force / raw")
            plt.title("Reference time series")
            plt.legend()
            out = plots_dir / "reference_timeseries.png"
            _save_plot(out)
            generated.append(out)

    if dataset_csv.exists() and fit_json.exists():
        dataset = pd.read_csv(dataset_csv)
        fit = _load_json(fit_json)
        coeff = fit.get("force_N", {})
        a = coeff.get("a")
        b = coeff.get("b")
        if a is not None and b is not None and not dataset.empty:
            x = dataset["target_raw_median"].to_numpy(dtype=float)
            y = dataset["reference_force_median_N"].to_numpy(dtype=float)
            order = np.argsort(x)
            pred = float(a) * x + float(b)
            plt.figure(figsize=(7, 5))
            plt.scatter(x, y, label="accepted holds")
            plt.plot(x[order], pred[order], label="affine fit")
            plt.xlabel("Target raw median")
            plt.ylabel("Reference force median [N]")
            plt.title("Calibration curve")
            plt.legend()
            out = plots_dir / "force_vs_raw_fit.png"
            _save_plot(out)
            generated.append(out)

            plt.figure(figsize=(7, 4))
            plt.axhline(0, linestyle="--", linewidth=1)
            plt.scatter(y, y - pred)
            plt.xlabel("Reference force [N]")
            plt.ylabel("Residual [N]")
            plt.title("Residuals by force")
            out = plots_dir / "residuals_by_force.png"
            _save_plot(out)
            generated.append(out)

            if "direction" in dataset.columns:
                plt.figure(figsize=(7, 4))
                for direction, group in dataset.groupby("direction"):
                    plt.scatter(group["reference_force_median_N"], group["target_raw_median"], label=str(direction))
                plt.xlabel("Reference force [N]")
                plt.ylabel("Target raw median")
                plt.title("Ascending/descending hold comparison")
                plt.legend()
                out = plots_dir / "hysteresis_up_down.png"
                _save_plot(out)
                generated.append(out)
    return generated


def _table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_No rows._\n"
    present = [c for c in columns if c in df.columns]
    return df[present].to_markdown(index=False) + "\n"


def generate_report(session_dir: str | Path) -> Path:
    """Generate Markdown and HTML calibration reports."""

    session_dir = Path(session_dir)
    manifest = _load_yaml(session_dir / "session_manifest.yaml")
    fit = _load_json(session_dir / "fit_result.json")
    events = read_ndjson(session_dir / "events.ndjson")
    dataset = pd.read_csv(session_dir / "calibration_dataset.csv") if (session_dir / "calibration_dataset.csv").exists() else pd.DataFrame()
    plots = generate_plots(session_dir)

    session = manifest.get("session", {})
    metrics = fit.get("metrics", {})
    coeff = fit.get("force_N", {})
    lines = [
        "# Handgrip Calibration Report",
        "",
        "## Summary",
        "",
        f"- **Session ID:** `{session.get('session_id', session_dir.name)}`",
        f"- **Operator:** {session.get('operator', 'unknown')}",
        f"- **Purpose:** {session.get('purpose', 'unknown')}",
        f"- **Affine model:** `force_N = {coeff.get('a', float('nan')):.12g} * raw + {coeff.get('b', float('nan')):.12g}`" if coeff else "- **Affine model:** not available",
        f"- **RMSE:** {metrics.get('rmse_N', float('nan')):.6g} N" if metrics else "- **RMSE:** not available",
        f"- **Max abs error:** {metrics.get('max_abs_error_N', float('nan')):.6g} N" if metrics else "- **Max abs error:** not available",
        f"- **Residual threshold pass:** {fit.get('passes_residual_threshold', 'unknown')}",
        "",
        "## Fit result JSON excerpt",
        "",
        "```json",
        json.dumps(fit, indent=2, ensure_ascii=False)[:4000],
        "```",
        "",
        "## Accepted hold dataset",
        "",
        _table(dataset, [
            "trial_id", "target_force_nominal_N", "direction", "target_raw_median",
            "reference_force_median_N", "reference_force_std_N", "reference_slope_N_s",
            "accepted_by_quality", "quality_rejection_reason",
        ]),
        "",
        "## Event summary",
        "",
        _table(pd.DataFrame(events), ["event", "trial_id", "target_force_N", "phase", "reason", "host_time_unix", "lsl_time"]),
        "",
        "## Plots",
        "",
    ]
    for plot in plots:
        rel = plot.relative_to(session_dir)
        lines.append(f"![{plot.stem}]({rel.as_posix()})")
        lines.append("")
    lines.extend([
        "## Firmware constant caution",
        "",
        "The report includes an HX711-style scale/offset approximation, but firmware constants must be verified against the exact HX711 library semantics before flashing. In particular, confirm whether the runtime uses `force = a * raw + b` or `units = (raw - offset) / scale`.",
        "",
        "## Limitations",
        "",
        "- The fit is only as good as the accepted static holds.",
        "- Dynamic trials are validation data, not primary affine-fit data.",
        "- If the reference board applies hidden zeroing, display masking, dynamic tracking, or stability gating, the reference trace may not represent the true physical input.",
    ])
    md_path = session_dir / "calibration_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # Lightweight HTML fallback: no external markdown dependency required.
    html = "<html><head><meta charset='utf-8'><title>Handgrip Calibration Report</title></head><body><pre>" + md_path.read_text(encoding="utf-8").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre></body></html>"
    (session_dir / "calibration_report.html").write_text(html, encoding="utf-8")
    return md_path
