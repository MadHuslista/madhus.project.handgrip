# Phase 2 & 3 Refactor Notes

## Scope implemented

This update builds on the Phase 1 trial-aware analysis layer and implements:

1. **Phase 2 — CLI cleanup**
   - Added package-native CLI module: `src/handgrip_analysis/cli.py`.
   - Added primary entry points:
     - `ha-stage = handgrip_analysis.cli:main`
     - `ha-run-all = handgrip_analysis.cli:run_all_main`
   - Removed `runpy` from all package CLI wrappers under `src/handgrip_analysis/_cli/`.
   - Kept old stage-specific console entry points as compatibility shims that now delegate to the package-native CLI.
   - Supported both conventional flags and Hydra-style `key=value` overrides.

2. **Phase 3 — output contract**
   - Standardized every manifest-driven stage output to include:
     - `plan.json`
     - `per_trial_metrics.csv`
     - `condition_summary.csv`
     - `summary.json`
     - `figures/per_trial/`
     - `figures/aggregate/`
   - Preserved additional per-stage tables under `tables/`.
   - Added Stage 6-specific contract files:
     - `filter_per_trial_metrics.csv`
     - `filter_validation_scores.csv`
     - `filter_ranking_summary.csv`
     - `filter_acceptance_report.md`

## CLI examples

```bash
ha-stage stage=stage2 manifest=data/calibration_manifest.csv outdir=data/analysis_results/stage2
ha-stage --stage stage4 --manifest data/calibration_manifest.csv --outdir data/analysis_results/stage4 --condition fast_max
ha-stage stage=stage6 manifest=data/calibration_manifest.csv outdir=data/analysis_results/stage6 filter_config=conf/filters/candidates.yaml
ha-run-all manifest=data/calibration_manifest.csv base_outdir=data/analysis_results stages=stage1,stage2,stage3
```

## Design notes

- The new CLI follows the guideline pattern: parse/normalize at the boundary, construct typed config, then call the package pipeline.
- Phase 3 creates figure directories even before plotting is implemented so downstream tooling can rely on a stable artifact layout.
- Stage 6 `filter_validation_scores.csv` currently contains aggregate validation-style scores across available trials. Full grouped cross-trial validation remains the planned Phase 4 upgrade.

## Validation performed

```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python -m compileall -q src scripts tests
PYTHONPATH=src python -m handgrip_analysis.cli stage=stage1 manifest=data/calibration_manifest.csv outdir=/tmp/ha_phase23_smoke/stage1
PYTHONPATH=src python -m handgrip_analysis.cli stage=stage6 manifest=/tmp/ha_phase23_smoke/stage6_manifest.csv outdir=/tmp/ha_phase23_smoke/stage6 filter_config=conf/filters/candidates.yaml
```
