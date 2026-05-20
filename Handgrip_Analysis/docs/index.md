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

## Documentation map

| Document                                         | Purpose                                                                 |
| ------------------------------------------------ | ----------------------------------------------------------------------- |
| [workflow.md](workflow.md)                       | Data preparation, running stages, applying filter recommendations       |
| [stages.md](stages.md)                           | Stage 1–6 purpose, input, output, and interpretation                    |
| [configuration.md](configuration.md)             | Full config tree reference and safe-edit guidance                       |
| [filter-design.md](filter-design.md)             | Stage 6 candidate review workflow and interpretation                    |
| [reports-and-outputs.md](reports-and-outputs.md) | Output tree, generated reports, figures, metrics, recommendation files  |
| [architecture.md](architecture.md)               | CLI, stages, config, IO, DSP, plotting, and report layers               |
| [development.md](development.md)                 | How to add stages, metrics, filter families, report sections, and tests |

## Reading guide

- To record source data, build manifests, and run stages: [Handgrip_Analysis/docs/workflow.md](workflow.md)
- To understand what each stage produces: [Handgrip_Analysis/docs/stages.md](stages.md)
- To safely edit configuration: [Handgrip_Analysis/docs/configuration.md](configuration.md)
- To interpret Stage 6 filter results: [Handgrip_Analysis/docs/filter-design.md](filter-design.md)
- To apply a filter recommendation to `LSL_Bridge`: [Handgrip_Analysis/docs/filter-design.md](filter-design.md), then [LSL_Bridge/docs/configuration.md](../../LSL_Bridge/docs/configuration.md)
- To add a stage, metric, or filter family: [Handgrip_Analysis/docs/development.md](development.md)

## Related docs

- [docs/workflows/handgrip-analysis.md](../../docs/workflows/handgrip-analysis.md) — multi-component analysis workflow
- [Handgrip_Calibration/docs/workflow.md](../../Handgrip_Calibration/docs/workflow.md) — how to record source sessions
- [docs/troubleshooting/analysis-pipeline.md](../../docs/troubleshooting/analysis-pipeline.md)
