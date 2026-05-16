# Handgrip Analysis Documentation

## Summary

- `Handgrip_Analysis` is the offline signal-analysis and filter-design component for saved handgrip data.
- It is used after acquisition/calibration data exists; it is not the live acquisition authority.
- The documentation is organized around staged analysis: startup/warm-up, static noise, loaded drift, real grip dynamics, interference comparison, and filter design.
- Stage 6 is the bridge from analysis to deployment decisions: it reviews filter candidates and produces recommendations that may be applied to `LSL_Bridge`, viewer display, firmware, or analysis-only workflows.
- Generated analysis outputs are results, not canonical documentation, unless curated under `docs/examples/analysis-output/`.

## Audience

| Reader | Use this page to... |
| --- | --- |
| Principal investigator / analyst | Understand what the offline analysis can answer and how to interpret outputs. |
| Student operator | Run all stages or an individual stage on prepared data. |
| Maintainer | Find config, architecture, and development references before editing code. |
| Student developer | Add stages, metrics, filters, plots, or report sections without breaking pipeline contracts. |

## Component contract

- Inputs are saved files, manifests, calibration/session exports, or curated CSV datasets.
- Outputs are reports, figures, metrics, recommendations, and generated artifacts.
- Analysis must preserve source-data provenance: input path, session ID, protocol, channel mapping, and config used.
- Stage 6 recommendations should be validated before changing live acquisition paths.
- Raw data should be preserved even when filtered or calibrated derivatives are generated.

## Documentation map

| Document | Purpose |
| --- | --- |
| [`quickstart.md`](quickstart.md) | Run all stages and individual stages. |
| [`stages.md`](stages.md) | Stage 1–6 purpose, input, output, and interpretation. |
| [`configuration.md`](configuration.md) | Full analysis config tree reference and safe-edit guidance. |
| [`filter-design.md`](filter-design.md) | Candidate review/design workflow and Stage 6 interpretation. |
| [`reports-and-outputs.md`](reports-and-outputs.md) | Output tree, generated reports, figures, metrics, and recommendation files. |
| [`architecture.md`](architecture.md) | CLI, stages, config, IO, DSP, plotting, and report layers. |
| [`development.md`](development.md) | How to add stages, metrics, filter families, report sections, and tests. |

## Related system docs

| System doc | Why it matters |
| --- | --- |
| [`../../docs/start-here.md`](../../docs/start-here.md) | High-level introduction to the full suite. |
| [`../../docs/system-overview.md`](../../docs/system-overview.md) | Physical/software/dataflow map. |
| [`../../docs/workflows/handgrip-analysis.md`](../../docs/workflows/handgrip-analysis.md) | Root operator workflow for offline analysis. |
| [`../../docs/architecture/data-and-output-lifecycle.md`](../../docs/architecture/data-and-output-lifecycle.md) | Generated-output policy and data lifecycle. |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Upstream target/reference stream and session contracts. |
| [`../../docs/configuration/index.md`](../../docs/configuration/index.md) | Cross-component configuration ownership. |
| [`../../docs/troubleshooting/index.md`](../../docs/troubleshooting/index.md) | Symptom-first debugging entry point. |

## Required reading by task

| Task | Read |
| --- | --- |
| Run analysis for the first time | [`quickstart.md`](quickstart.md), then [`stages.md`](stages.md) |
| Understand what each stage means | [`stages.md`](stages.md) |
| Edit config safely | [`configuration.md`](configuration.md) |
| Interpret Stage 6 | [`filter-design.md`](filter-design.md), then [`reports-and-outputs.md`](reports-and-outputs.md) |
| Apply a filter recommendation | [`filter-design.md`](filter-design.md), then `LSL_Bridge/docs/configuration.md` if deploying to bridge processing |
| Add a stage/filter/metric | [`development.md`](development.md), then [`architecture.md`](architecture.md) |

## Validation checklist for this docs index

- [ ] `Handgrip_Analysis/README.md` links to this `docs/index.md`.
- [ ] Every linked component doc exists.
- [ ] Links to root docs use `../../docs/...` and resolve from `Handgrip_Analysis/docs/`.
- [ ] No generated output folder is presented as maintained documentation.
- [ ] Stage 6 recommendations are described as candidates requiring validation, not automatic deployment.
