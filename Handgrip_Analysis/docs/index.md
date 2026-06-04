# Handgrip Analysis Documentation

## Summary

- `Handgrip_Analysis` is the offline signal-analysis and filter-design component for saved handgrip data.
- It operates on saved files and manifests — not live streams.
- Analysis covers six stages: startup/warm-up, static noise, loaded drift, real grip dynamics, interference comparison, and filter design.
- Stage 6 bridges from analysis to deployment: it reviews filter candidates and produces recommendations for `LSL_Bridge`, firmware, viewer display, or analysis-only use.

## Component contract

| Contract           | Value                                         |
| ------------------ | --------------------------------------------- |
| Run all stages     | `uv run ha-run-all`                           |
| Run a single stage | `uv run ha-stage stage=<stage_name>`          |
| Input root         | `Handgrip_Analysis/data/calibration_signals/` |
| Manifest root      | `Handgrip_Analysis/data/manifests/`           |
| Output root        | `Handgrip_Analysis/data/analysis_results/`    |

## Reading guide

| I want to…                                          | Read                                                                                                                                         |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Prepare data, build manifests, and run stages       | [Handgrip_Analysis/docs/workflow.md](workflow.md)                                                                                            |
| Understand what each stage 1–6 produces             | [Handgrip_Analysis/docs/stages.md](stages.md)                                                                                                |
| Safely edit configuration                           | [Handgrip_Analysis/docs/configuration.md](configuration.md)                                                                                  |
| Interpret Stage 6 filter results                    | [Handgrip_Analysis/docs/filter-design.md](filter-design.md)                                                                                  |
| Read the output tree, reports, figures, and metrics | [Handgrip_Analysis/docs/reports-and-outputs.md](reports-and-outputs.md)                                                                      |
| Understand CLI/stage/IO/DSP internals               | [Handgrip_Analysis/docs/architecture.md](architecture.md)                                                                                    |
| Add a stage, metric, or filter family               | [Handgrip_Analysis/docs/development.md](development.md)                                                                                      |
| Apply a filter recommendation to `LSL_Bridge`       | [Handgrip_Analysis/docs/filter-design.md](filter-design.md), then [LSL_Bridge/docs/configuration.md](../../LSL_Bridge/docs/configuration.md) |

## Related docs

- [docs/workflows/handgrip-analysis.md](../../docs/workflows/handgrip-analysis.md) — multi-component analysis workflow
- [Handgrip_Calibration/docs/workflow.md](../../Handgrip_Calibration/docs/workflow.md) — how to record source sessions
- [docs/troubleshooting/analysis-pipeline.md](../../docs/troubleshooting/analysis-pipeline.md)
