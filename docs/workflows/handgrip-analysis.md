# Handgrip Analysis Workflow

## Summary

This workflow runs offline signal characterization and filter design on recorded target signals. It runs after calibration session data exists.

For the full step-by-step workflow — recording and exporting source data, building manifests, running each stage, and applying the Stage 6 filter recommendation — see [Handgrip_Analysis/docs/workflow.md](../../Handgrip_Analysis/docs/workflow.md).

## Required upstream state

Before running analysis:

1. Calibration sessions recorded and their `target.csv` files exported into `Handgrip_Analysis/data/calibration_signals/`. See [docs/workflows/handgrip-calibration.md](handgrip-calibration.md) to record sessions, and [Handgrip_Analysis/docs/workflow.md](../../Handgrip_Analysis/docs/workflow.md) (Phase 1) for the export naming and column convention.
2. A manifest CSV under `Handgrip_Analysis/data/manifests/` listing the exported files. See [Handgrip_Analysis/docs/workflow.md](../../Handgrip_Analysis/docs/workflow.md).
3. `uv sync` completed from the repo root.

## Detailed documentation

- [Handgrip_Analysis/docs/workflow.md](../../Handgrip_Analysis/docs/workflow.md) — complete step-by-step workflow
- [Handgrip_Analysis/docs/stages.md](../../Handgrip_Analysis/docs/stages.md) — stage-by-stage purpose, input, and output
- [Handgrip_Analysis/docs/filter-design.md](../../Handgrip_Analysis/docs/filter-design.md) — Stage 6 candidate review and interpretation
- [Handgrip_Analysis/docs/configuration.md](../../Handgrip_Analysis/docs/configuration.md) — config reference
- [docs/troubleshooting/analysis-pipeline.md](../troubleshooting/analysis-pipeline.md)
