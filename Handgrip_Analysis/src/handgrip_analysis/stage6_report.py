# @package handgrip_analysis.stage6_report
# @brief Markdown reporting helpers for Stage 6 review and design decisions.

"""Markdown reporting for the Stage 6 review + design decision."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml

from .domain import StageConfig, TrialSpec
from .manifest import filter_trials, load_manifest
from .report import to_jsonable
from .stages import get_stage_module
from .stages.stage6_filters import lsl_bridge_processing_snippet, select_final_filter

log = logging.getLogger(__name__)

_STAGE_CONTEXT_STAGES = ("stage1", "stage2", "stage3", "stage4", "stage5")
_STAGE_RE = re.compile(r"stage(?P<num>[1-5])")
_TRIAL_RE = re.compile(r"trial(?P<num>\d+)")
_SESSION_RE = re.compile(r"(?P<session>20\d{6})")


# @brief Compute median over finite values.
# @param values Input scalar sequence.
# @return Median value or None when no finite values exist.
def _median(values: Iterable[float]) -> float | None:
    arr = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    if arr.empty:
        return None
    return float(arr.median())


# @brief Compute most common rounded value.
# @param values Input scalar sequence.
# @param ndigits Decimal precision for rounding before mode.
# @return Modal rounded value or None when no finite values exist.
def _most_common_rounded(values: Iterable[float], ndigits: int = 3) -> float | None:
    arr = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    if arr.empty:
        return None
    rounded = arr.round(ndigits)
    return float(rounded.mode().iloc[0])


# @brief Format path relative to base when possible.
# @param path Input path or None.
# @param base Base directory for relative conversion.
# @return Relative or absolute path string, or None.
def _safe_rel(path: Path | None, base: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


# @brief Build stable dedupe key for trial identity.
# @param trial Trial specification.
# @return Tuple identity key.
def _trial_identity_key(trial: TrialSpec) -> tuple[str, str, str, str, str, str]:
    """Return a stable dedupe key for merged manifest/context trials."""
    return (
        trial.stage,
        trial.condition,
        trial.trial_type,
        trial.session_id,
        trial.trial_id,
        str(trial.path.resolve()),
    )


# @brief Check whether any Stage 1-5 context rows are present.
# @param trials Trial sequence.
# @return True when Stage 1-5 rows exist.
def _has_context_rows(trials: Sequence[TrialSpec]) -> bool:
    return any(trial.stage in _STAGE_CONTEXT_STAGES for trial in trials)


# @brief Build candidate Stage 1-5 context manifest paths.
# @param all_trials Current Stage 6 trial sequence.
# @param cfg Stage configuration.
# @return Ordered list of candidate manifest paths.
def _candidate_context_manifest_paths(all_trials: Sequence[TrialSpec], cfg: StageConfig) -> list[Path]:
    """
    Return likely manifests containing Stage 1–5 context rows.

    Stage 6 is commonly run from ``stage6_filter_review_manifest.csv``. That
    manifest is intentionally Stage 6-only because its rows re-use Stage 2 rest
    and Stage 4 dynamic captures as filter-review inputs. The report, however,
    needs the original Stage 1–5 manifest context. This resolver first honors an
    explicit ``stage_context_manifest`` override and then searches sibling
    project manifest locations inferred from the capture file paths.
    """
    candidates: list[Path] = []
    explicit = getattr(cfg, "stage_context_manifest", None)
    if explicit is not None:
        candidates.append(Path(explicit))

    names = [
        "all_runnable_manifest.csv",
        "analysis_stages_1_4_manifest.csv",
        "calibration_manifest.csv",
    ]
    for trial in all_trials:
        try:
            resolved = trial.path.resolve()
        except OSError:
            resolved = trial.path
        for ancestor in [resolved.parent, *resolved.parents]:
            for name in names:
                candidates.extend(
                    [
                        ancestor / "data" / "manifests" / name,
                        ancestor / "manifests" / name,
                        ancestor / "data" / name,
                        ancestor / name,
                    ]
                )

    cwd = Path.cwd().resolve()
    for name in names:
        candidates.extend(
            [
                cwd / "data" / "manifests" / name,
                cwd / "data" / name,
                cwd / "manifests" / name,
                cwd / name,
            ]
        )

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.expanduser().resolve()) if path.exists() else str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path.expanduser())
    return unique


# @brief Infer original Stage 1-5 trial identity from reused Stage 6 path.
# @param trial Stage 6 trial specification.
# @return Inferred TrialSpec or None when inference is not possible.
def _infer_original_stage_trial(trial: TrialSpec) -> TrialSpec | None:
    """
    Infer the original Stage 1–5 identity from a reused Stage 6 capture path.

    This is a fallback for portable handoffs where only the Stage 6 manifest was
    copied but the capture filenames still include their original stage labels,
    e.g. ``20260402_stage2_rest_after_warmup_trial01.csv``.
    """
    stem = trial.path.stem
    stage_match = _STAGE_RE.search(stem)
    if stage_match is None:
        return None
    stage = f"stage{stage_match.group('num')}"
    if stage == "stage6":
        return None
    trial_match = _TRIAL_RE.search(stem)
    session_match = _SESSION_RE.search(stem)
    parts = stem.split("_")
    condition = trial.condition
    trial_type = trial.trial_type
    try:
        stage_idx = parts.index(stage)
        trial_idx = next((idx for idx, part in enumerate(parts) if _TRIAL_RE.fullmatch(part)), len(parts))
        inferred_condition = "_".join(parts[stage_idx + 1 : trial_idx])
        if inferred_condition:
            condition = inferred_condition
            trial_type = inferred_condition
    except ValueError:
        pass
    return TrialSpec(
        stage=stage,
        condition=condition,
        trial_type=trial_type,
        trial_id=f"trial{trial_match.group('num')}" if trial_match else trial.trial_id,
        session_id=session_match.group("session") if session_match else trial.session_id,
        path=trial.path,
        channel=trial.channel,
        include=trial.include,
        load_nominal_n=trial.load_nominal_n,
        notes=f"Inferred original {stage} context from Stage 6 reused capture path.",
    )


# @brief Merge current trials with discovered Stage 1-5 context trials.
# @param all_trials Current trial sequence.
# @param cfg Stage configuration.
# @return Tuple of merged trials and loaded context-manifest paths.
def resolve_stage_context_trials(
    all_trials: Sequence[TrialSpec], cfg: StageConfig
) -> tuple[list[TrialSpec], list[Path]]:
    """Merge current manifest rows with discovered original Stage 1–5 context."""
    merged: list[TrialSpec] = list(all_trials)
    loaded_sources: list[Path] = []
    seen = {_trial_identity_key(trial) for trial in merged}

    for path in _candidate_context_manifest_paths(all_trials, cfg):
        if not path.exists() or not path.is_file():
            continue
        try:
            loaded = load_manifest(path)
        except Exception as exc:  # noqa: BLE001 - report context must degrade gracefully
            log.debug("stage6_report: skipped context manifest %s: %s", path, exc)
            continue
        context_rows = [trial for trial in loaded if trial.stage in _STAGE_CONTEXT_STAGES]
        if not context_rows:
            continue
        for trial in context_rows:
            key = _trial_identity_key(trial)
            if key not in seen:
                merged.append(trial)
                seen.add(key)
        loaded_sources.append(path)

    # Fallback: recover Stage 2/4 context from Stage 6 rows that reuse earlier
    # stage capture filenames. This is intentionally secondary to manifest
    # loading because a full manifest is the richer source of truth.
    for trial in all_trials:
        inferred = _infer_original_stage_trial(trial)
        if inferred is None:
            continue
        key = _trial_identity_key(inferred)
        if key not in seen:
            merged.append(inferred)
            seen.add(key)

    return merged, loaded_sources


# @brief Compute concise Stage 1-5 context insights for Stage 6 report.
# @param all_trials Current trial sequence.
# @param cfg Stage configuration.
# @return Stage-keyed context insight dictionary.
def collect_stage_context(all_trials: Sequence[TrialSpec], cfg: StageConfig) -> dict[str, dict[str, Any]]:
    """
    Compute concise Stage 1–5 insights from manifest or discovered context.

    The report uses the same analyzers that power the main stages. If Stage 6 is
    run from a Stage 6-only manifest, sibling/full manifests are auto-discovered
    from the capture-path layout before falling back to filename-based stage
    inference.
    """
    context_trials, loaded_sources = resolve_stage_context_trials(all_trials, cfg)
    context: dict[str, dict[str, Any]] = {
        "__sources__": {
            "available": True,
            "loaded_manifest_paths": [str(path) for path in loaded_sources],
            "used_filename_inference": _has_context_rows(context_trials)
            and not loaded_sources
            and not _has_context_rows(all_trials),
        }
    }
    for stage in ["stage1", "stage2", "stage3", "stage4", "stage5"]:
        selected = filter_trials(context_trials, stage=stage)
        if not selected:
            context[stage] = {
                "available": False,
                "reason": "No trials for this stage were found in the active manifest or discovered context manifests.",
            }
            continue
        module = get_stage_module(stage)
        results = [module.analyze_trial(spec, cfg) for spec in selected]
        info: dict[str, Any] = {"available": True, "n_trials": len(results)}
        if stage == "stage1":
            ready = [float(r.metrics.get("suggested_ready_time_s", np.nan)) for r in results]
            final_std = [float(r.metrics.get("final_std", np.nan)) for r in results]
            info.update({
                "median_ready_time_s": _median(ready),
                "median_final_std": _median(final_std),
                "decision_impact": "Used to ensure that filter conclusions are interpreted on stabilized post-warmup behavior, not startup transients.",
            })
        elif stage == "stage2":
            top_peak = [float(r.metrics.get("raw_top_peak_hz", np.nan)) for r in results]
            raw_std = [float(r.metrics.get("raw_std", np.nan)) for r in results]
            info.update({
                "median_raw_std": _median(raw_std),
                "dominant_noise_peak_hz": _most_common_rounded(top_peak),
                "decision_impact": "Used to quantify the stationary noise floor and whether a narrow interference line exists strongly enough to justify a notch.",
            })
        elif stage == "stage3":
            drift = [float(r.metrics.get("drift_slope_per_min", np.nan)) for r in results]
            return_zero = [float(r.metrics.get("return_to_zero_error", np.nan)) for r in results]
            info.update({
                "median_drift_slope_per_min": _median(drift),
                "median_return_to_zero_error": _median(return_zero),
                "decision_impact": "Used to decide that baseline management should be handled by tare / unloaded-state logic instead of a continuous high-pass in the main force path.",
            })
        elif stage == "stage4":
            peaks = [float(r.metrics.get("peak_value_max", np.nan)) for r in results]
            rise = [float(r.metrics.get("rise_10_90_s_median", np.nan)) for r in results]
            conditions = sorted({str(r.spec.condition) for r in results})
            info.update({
                "conditions": conditions,
                "median_peak_value": _median(peaks),
                "median_rise_10_90_s": _median(rise),
                "decision_impact": "Used to define the waveform-fidelity criteria for Stage 6 design: peak preservation, rise-time preservation, timing, and dF/dt behavior.",
            })
        elif stage == "stage5":
            top_peak = [float(r.metrics.get("top_peak_hz", np.nan)) for r in results]
            robust_std = [float(r.metrics.get("robust_std", np.nan)) for r in results]
            info.update({
                "dominant_interference_peak_hz": _most_common_rounded(top_peak),
                "median_robust_std": _median(robust_std),
                "decision_impact": "Used to compare external interference conditions. If absent, Stage 6 falls back to Stage 2 rest-noise evidence only.",
            })
        context[stage] = info
    return context


# @brief Resolve LSL_Bridge config path from StageConfig hints.
# @param cfg Stage configuration.
# @return Config path or None.
def resolve_lsl_bridge_config(cfg: StageConfig) -> Path | None:
    if getattr(cfg, "lsl_bridge_config", None) is not None:
        return Path(cfg.lsl_bridge_config)  # type: ignore[arg-type]
    if getattr(cfg, "lsl_bridge_root", None) is not None:
        root = Path(cfg.lsl_bridge_root)  # type: ignore[arg-type]
        candidate = root / "conf" / "config.yaml"
        if candidate.exists():
            return candidate
    return None


# @brief Load current LSL_Bridge processing context for report.
# @param cfg Stage configuration.
# @return Dictionary with availability, path, and processing config.
def load_lsl_bridge_context(cfg: StageConfig) -> dict[str, Any]:
    path = resolve_lsl_bridge_config(cfg)
    if path is None or not path.exists():
        return {"available": False, "path": None, "current_processing": None}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - report layer should degrade gracefully
        return {"available": False, "path": str(path), "error": str(exc), "current_processing": None}
    processing = payload.get("processing")
    return {"available": True, "path": str(path), "current_processing": processing}


# @brief Build markdown bullet insights from stage-context summary.
# @param stage_context Stage-keyed context dictionary.
# @return List of markdown lines.
def _insight_lines(stage_context: Mapping[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    labels = {
        "stage1": "Stage 1 — warmup / stabilization",
        "stage2": "Stage 2 — static rest noise",
        "stage3": "Stage 3 — loaded drift / return-to-zero",
        "stage4": "Stage 4 — dynamics",
        "stage5": "Stage 5 — interference comparison",
    }
    for stage in ["stage1", "stage2", "stage3", "stage4", "stage5"]:
        info = stage_context.get(stage, {})
        lines.append(f"### {labels[stage]}")
        lines.append("")
        if not info.get("available"):
            lines.append(f"- Status: not available. {info.get('reason', '')}".strip())
            lines.append("")
            continue
        lines.append(f"- Trials used: {info.get('n_trials')}")
        for key, label in [
            ("median_ready_time_s", "Median ready time [s]"),
            ("median_final_std", "Median final std"),
            ("median_raw_std", "Median raw std"),
            ("dominant_noise_peak_hz", "Dominant noise peak [Hz]"),
            ("median_drift_slope_per_min", "Median drift slope [signal/min]"),
            ("median_return_to_zero_error", "Median return-to-zero error"),
            ("median_peak_value", "Median Stage 4 peak"),
            ("median_rise_10_90_s", "Median Stage 4 rise 10–90 [s]"),
            ("dominant_interference_peak_hz", "Dominant interference peak [Hz]"),
            ("median_robust_std", "Median robust std"),
        ]:
            value = info.get(key)
            if value is not None:
                lines.append(f"- {label}: `{value}`")
        if info.get("conditions"):
            lines.append(f"- Conditions observed: {', '.join(map(str, info['conditions']))}")
        if info.get("decision_impact"):
            lines.append(f"- Why it mattered for Stage 6: {info['decision_impact']}")
        lines.append("")
    return lines


# @brief Build and write complete Stage 6 markdown recommendation report.
# @param outdir Stage output directory.
# @param cfg Stage configuration.
# @param all_trials Full trial sequence used for context resolution.
# @param artifact_tables Stage 6 artifact tables.
# @param figure_paths Generated figure-path mapping.
# @return Dictionary of generated report artifact paths.
def write_stage6_report(
    *,
    outdir: Path,
    cfg: StageConfig,
    all_trials: Sequence[TrialSpec],
    artifact_tables: Mapping[str, pd.DataFrame],
    figure_paths: Mapping[str, Path],
) -> dict[str, Path]:
    review = artifact_tables.get("filter_ranking_summary", pd.DataFrame())
    design = artifact_tables.get("filter_design_assessment", pd.DataFrame())
    decision = artifact_tables.get("filter_decision_summary", pd.DataFrame())
    selected = select_final_filter(decision, cfg)
    stage_context = collect_stage_context(all_trials, cfg)
    lsl_context = load_lsl_bridge_context(cfg)
    snippet = lsl_bridge_processing_snippet(selected, sample_rate_hz=100.0)

    # Persist machine-readable recommendation payloads.
    snippet_path = outdir / "lsl_bridge_processing_recommendation.yaml"
    snippet_path.write_text(yaml.safe_dump(to_jsonable(snippet), sort_keys=False), encoding="utf-8")

    import json
    selected_json_path = outdir / "selected_filter_recommendation.json"
    selected_json_path.write_text(json.dumps(to_jsonable(selected), indent=2, sort_keys=True), encoding="utf-8")

    figure_score = _safe_rel(figure_paths.get("figure_stage6_composite_score"), outdir)
    figure_rest = _safe_rel(figure_paths.get("figure_stage6_rest_psd_top_candidates"), outdir)
    figure_design = _safe_rel(figure_paths.get("figure_stage6_design_representative_overlay"), outdir)

    lines: list[str] = [
        "# Stage 6 — Filter Review, Design, and LSL_Bridge Recommendation",
        "",
        "## Executive conclusion",
        "",
    ]
    if selected:
        lines.extend([
            f"- **Final recommended filter:** `{selected.get('filter')}`",
            "- **Why:** It achieved the best combined decision score by balancing the multi-trial review (`70%`) with the representative-trial design pass (`30%`).",
            f"- **Review rank:** `{selected.get('review_rank')}`",
            f"- **Design rank:** `{selected.get('design_rank')}`",
            f"- **Combined score:** `{selected.get('combined_score')}`",
            "",
        ])
    else:
        lines.extend([
            "- No final filter could be selected because the Stage 6 artifact tables were empty.",
            "",
        ])

    lines.extend([
        "## What Stage 6 ran",
        "",
        "Stage 6 now runs **both** of the following:",
        "",
        "1. **Candidate review** — aggregate ranking over all available Stage 6 rest and dynamic trials.",
        "2. **Representative-trial design pass** — a focused waveform-fidelity comparison on the best representative dynamic trial (preferring `ramp_hold`, then `sustained_hold`, then `fast_max`).",
        "",
        "This means the final recommendation is not based only on one trial, and also not based only on a broad summary that could hide important waveform distortions.",
        "",
        "## Key insights from earlier stages and how they informed Stage 6",
        "",
    ])
    source_info = stage_context.get("__sources__", {})
    loaded_paths = source_info.get("loaded_manifest_paths") or []
    if loaded_paths:
        lines.extend(
            [
                "Context source: Stage 6 was run with a Stage 6-focused manifest, so the report loaded the following sibling/full manifest(s) for Stage 1–5 context:",
                "",
                *[f"- `{path}`" for path in loaded_paths],
                "",
            ]
        )
    elif source_info.get("used_filename_inference"):
        lines.extend(
            [
                "Context source: no sibling/full Stage 1–5 manifest was found, so available context was inferred from original stage labels embedded in the reused capture filenames.",
                "",
            ]
        )
    lines.extend(_insight_lines(stage_context))

    lines.extend([
        "## Candidate review result",
        "",
        "Primary artifacts:",
        "",
        "- `filter_ranking_summary.csv` — aggregate review ranking across all available Stage 6 trials.",
        "- `filter_validation_scores.csv` — validation-style summary table.",
        "- `figures/aggregate/stage6_composite_score.png` — visual ranking overview.",
        "- `figures/aggregate/stage6_rest_psd_top_candidates.png` — raw rest PSD compared against the top-ranked candidates.",
        "",
    ])
    if figure_score:
        lines.extend([
            f"![Stage 6 composite score]({figure_score})",
            "",
            "The composite-score figure above shows the broad robustness ranking. Lower is better.",
            "",
        ])
    if figure_rest:
        lines.extend([
            f"![Stage 6 rest PSD comparison]({figure_rest})",
            "",
            "The rest-PSD figure above shows whether the top candidates reduce high-frequency contamination without needing a more aggressive or narrower-band design.",
            "",
        ])

    if not review.empty:
        top_review = review.iloc[0]
        lines.extend([
            f"Top review-ranked candidate: `{top_review.get('filter')}` with score `{top_review.get('composite_score')}` over `{top_review.get('n_trials')}` represented trial(s).",
            "",
        ])

    lines.extend([
        "## Representative-trial design pass",
        "",
        "Primary artifacts:",
        "",
        "- `filter_design_assessment.csv` — per-candidate results on the representative dynamic trial.",
        "- `filter_decision_summary.csv` — merged review + design decision table used to select the final filter.",
        "- `figures/aggregate/stage6_design_representative_overlay.png` — raw signal overlaid with the top candidates on the representative dynamic trial.",
        "",
    ])
    if figure_design:
        lines.extend([
            f"![Stage 6 representative design overlay]({figure_design})",
            "",
            "The representative-trial overlay helps verify that the selected filter preserves event shape, timing, and slope behavior instead of only winning on stationary-noise suppression.",
            "",
        ])
    if not design.empty:
        top_design = design.iloc[0]
        lines.extend([
            f"Representative dynamic trial: `{top_design.get('representative_session_id')}` / `{top_design.get('representative_trial_id')}` (`{top_design.get('representative_condition')}`).",
            f"Top design-ranked candidate: `{top_design.get('filter')}` with design score `{top_design.get('design_score')}`.",
            "",
        ])

    lines.extend([
        "## How the final filter was selected",
        "",
        "The final selection table is `filter_decision_summary.csv`.",
        "",
        "Selection logic:",
        "",
        "- `review_rank` comes from the **multi-trial candidate review**.",
        "- `design_rank` comes from the **representative-trial design pass**.",
        "- `combined_score = 0.7 * normalized(review_score) + 0.3 * normalized(design_score)`.",
        "- Lower `combined_score` is better.",
        "",
        "This weighting intentionally gives **more authority to robustness across repeated trials**, while still ensuring that the final recommendation survives direct waveform inspection on a representative signal.",
        "",
    ])
    if selected:
        lines.extend([
            f"Final selected candidate: `{selected.get('filter')}`.",
            "This candidate won because it best balanced repeated-trial robustness and representative-trial waveform fidelity.",
            "",
        ])

    lines.extend([
        "## LSL_Bridge implementation recommendation",
        "",
        "The selected filter was translated into an `LSL_Bridge`-compatible `processing.filters` snippet where possible.",
        "",
    ])
    if lsl_context.get("available"):
        lines.extend([
            f"Detected reference config: `{lsl_context.get('path')}`",
            "",
            "### Current `processing` block",
            "",
            "```yaml",
            yaml.safe_dump(to_jsonable(lsl_context.get("current_processing")), sort_keys=False).rstrip(),
            "```",
            "",
        ])
    else:
        lines.extend([
            "No live `LSL_Bridge` config path was resolved at runtime, so the recommendation below is presented as a generic patch/snippet.",
            "",
        ])

    lines.extend([
        "### Recommended `processing.filters` snippet",
        "",
        f"Artifact file: `{snippet_path.name}`",
        "",
        "```yaml",
        yaml.safe_dump(to_jsonable(snippet), sort_keys=False).rstrip(),
        "```",
        "",
        "### How to apply it",
        "",
        "1. Open the `LSL_Bridge` configuration file (typically `conf/config.yaml`).",
        "2. Navigate to the `processing.filters` block.",
        "3. Replace the current filter list with the recommended snippet above, or merge it carefully if you maintain multiple processing branches.",
        "4. Keep the raw target stream logged for traceability; the filtered channel is a characterization / display / QA aid, not a replacement for raw engineering data.",
        "",
    ])

    lines.extend([
        "## Artifact index",
        "",
        "- `filter_per_trial_metrics.csv` — all per-trial, per-filter measurements.",
        "- `filter_validation_scores.csv` — aggregate review scores.",
        "- `filter_ranking_summary.csv` — ordered review ranking.",
        "- `filter_design_assessment.csv` — representative-trial design ranking.",
        "- `filter_decision_summary.csv` — merged review + design decision table.",
        "- `selected_filter_recommendation.json` — final selected filter payload.",
        f"- `{snippet_path.name}` — ready-to-apply `LSL_Bridge` snippet.",
        "",
    ])

    report_path = outdir / "stage6_review_design_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "stage6_review_design_report": report_path,
        "lsl_bridge_processing_recommendation": snippet_path,
        "selected_filter_recommendation": selected_json_path,
    }
