# Handgrip Analysis Workflow

## Summary

This workflow runs after calibration session data exists. It covers preparing inputs, running analysis stages, and applying filter recommendations from Stage 6.

For the full step-by-step workflow — including recording source data, exporting files, creating manifests, and running each stage — see [Handgrip_Analysis/docs/workflow.md](../../Handgrip_Analysis/docs/workflow.md).

## Required upstream state

Before running analysis:

1. At least one calibration session recorded and files exported. See [docs/workflows/handgrip-calibration.md](handgrip-calibration.md).
2. Target signal CSVs placed in `Handgrip_Analysis/data/calibration_signals/`.
3. A manifest CSV created or updated under `Handgrip_Analysis/data/manifests/`. See [Handgrip_Analysis/docs/workflow.md — Phase 1](../../Handgrip_Analysis/docs/workflow.md).
4. `uv sync` completed.

## Quick command reference

```bash
cd Handgrip_Analysis

# Run all stages from a manifest
uv run ha-run-all \
  manifest=data/manifests/all_runnable_manifest.csv \
  base_outdir=data/analysis_results/batch_run

# Run Stage 6 filter design
uv run ha-stage stage=stage6 \
  manifest=data/manifests/stage6_filter_review_manifest.csv \
  outdir=data/analysis_results/stage6 \
  filter_config=conf/filters/candidates.yaml
```

## Stage summary

| Stage   | Purpose                                       |
| ------- | --------------------------------------------- |
| Stage 1 | Startup and warm-up behavior                  |
| Stage 2 | Static rest noise                             |
| Stage 3 | Loaded drift and creep                        |
| Stage 4 | Real grip dynamics                            |
| Stage 5 | Interference/condition comparison             |
| Stage 6 | Filter candidate benchmark and recommendation |

## Applying filter recommendations

After Stage 6, apply the recommendation based on target:

| Target                  | Action                                                       |
| ----------------------- | ------------------------------------------------------------ |
| `LSL_Bridge` processing | Update processing config; validate live stream behavior      |
| Viewer display only     | Update viewer config only                                    |
| Firmware                | Only if filter must exist on-device; re-validate calibration |
| Analysis only           | Keep in analysis config/report                               |

## Detailed documentation

- [Handgrip_Analysis/docs/workflow.md](../../Handgrip_Analysis/docs/workflow.md) — complete step-by-step workflow
- [Handgrip_Analysis/docs/stages.md](../../Handgrip_Analysis/docs/stages.md) — stage details and interpretation
- [Handgrip_Analysis/docs/filter-design.md](../../Handgrip_Analysis/docs/filter-design.md) — Stage 6 interpretation
- [Handgrip_Analysis/docs/configuration.md](../../Handgrip_Analysis/docs/configuration.md) — config reference
- [docs/troubleshooting/analysis-pipeline.md](../troubleshooting/analysis-pipeline.md)
