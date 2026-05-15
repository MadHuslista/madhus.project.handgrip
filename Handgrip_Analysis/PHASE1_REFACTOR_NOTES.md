# Phase 1 Refactor Notes — Trial-Aware Analysis

## What changed

Phase 1 adds a manifest-driven multi-trial analysis layer without removing the existing stage scripts.

New package modules:

- `handgrip_analysis.domain` — immutable analysis contracts: `TrialSpec`, `StageConfig`, `TrialResult`, `ConditionSummary`, `AnalysisPlan`.
- `handgrip_analysis.manifest` — manifest normalization, validation, legacy filename inference, and trial filtering.
- `handgrip_analysis.uncertainty` — robust summaries and bootstrap confidence intervals.
- `handgrip_analysis.aggregation` — trial-result flattening and condition-level aggregation.
- `handgrip_analysis.pipeline` — validation → plan → execute → write output orchestration.
- `handgrip_analysis.stages.*` — stage analyzers exposing the Phase 1 contract:
  - `analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult`
  - `summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]`

## Usage

```bash
ha-run-manifest \
  --manifest data/calibration_manifest.csv \
  --stage stage1 \
  --outdir data/analysis_results/stage1
```

Equivalent direct script:

```bash
python scripts/run_manifest_analysis.py \
  --manifest data/calibration_manifest.csv \
  --stage stage4 \
  --outdir data/analysis_results/stage4
```

For Stage 6 filter review:

```bash
ha-run-manifest \
  --manifest data/stage6_filter_manifest.csv \
  --stage stage6 \
  --outdir data/analysis_results/stage6 \
  --filter-config conf/filters/candidates.yaml
```

## Standard outputs

Each manifest-driven stage run writes:

- `plan.json`
- `per_trial_metrics.csv`
- `condition_summary.csv`
- `summary.json`
- `tables/*.csv` when the stage produces detailed tables such as PSD, Allan deviation, event metrics, or filter metrics.

## Compatibility

The original Hydra-style scripts are still present. A small `handgrip_analysis.hydra_compat` layer preserves their behavior in lightweight environments where `hydra-core` is not installed, while using real Hydra if it is installed.

## Validation

Validated in this handoff with:

```bash
PYTHONPATH=src pytest -q
# 62 passed
```

Manual smoke runs were also performed for `stage1`, `stage2`, `stage3`, `stage4`, and a synthetic `stage6` filter-review manifest.
