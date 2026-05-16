# Handgrip Analysis Reports and Outputs

## Summary

- Analysis outputs are generated artifacts, not canonical documentation.
- Every output folder should be traceable to input data, config, command, and run/stage ID.
- Reports and figures should explain interpretation; metrics files should support reproducibility and automated comparison.
- Stage 6 outputs are decision artifacts and should include both human-readable rationale and machine-readable recommendations when possible.

## Output tree

Typical output layout:

```text
Handgrip_Analysis/
├── data/
│   └── analysis_results/
│       ├── stage1_startup_warmup/
│       ├── stage2_static_noise/
│       ├── stage3_loaded_drift/
│       ├── stage4_grip_dynamics/
│       ├── stage5_interference_compare/
│       └── stage6_filter_design/
└── outputs/
    └── <optional_batch_or_report_run>/
```

Exact paths are config-owned. The run command should print or log the output directory.

## Common artifacts

| Artifact                                                                    | Purpose                                      |
| --------------------------------------------------------------------------- | -------------------------------------------- |
| [`README.md`](../../README.md) or stage report markdown                                        | Human-readable explanation of stage results. |
| `metrics.json`                                                              | Machine-readable metrics.                    |
| `metrics.csv`                                                               | Tabular metrics for review/spreadsheets.     |
| `figures/` or `plots/`                                                      | Diagnostic plots.                            |
| `run_config.yaml` or config snapshot                                        | Reproducibility.                             |
| `filter_comparison.csv`                                                     | Stage 6 candidate ranking/metrics.           |
| `filter_recommendation.yaml` or `lsl_bridge_processing_recommendation.yaml` | Deployment-oriented filter recommendation.   |

## Stage-specific outputs

| Stage   | Output examples                                      | Interpretation                                          |
| ------- | ---------------------------------------------------- | ------------------------------------------------------- |
| Stage 1 | warm-up plots, drift metrics, stabilization interval | Decide capture discard/warm-up policy.                  |
| Stage 2 | PSD plot, noise floor metrics, peak frequency table  | Decide whether noise/contamination justifies filtering. |
| Stage 3 | drift/creep slopes, hold stability plots             | Decide whether baseline/fixture behavior is acceptable. |
| Stage 4 | event dynamics table, rise/peak/release plots        | Protect dynamic waveform realism.                       |
| Stage 5 | condition comparison report                          | Identify setup/environment effects.                     |
| Stage 6 | candidate comparison, recommendation YAML/report     | Decide filter deployment candidate.                     |

## Figures

Figures should include:

- clear title,
- units,
- source file/session ID,
- stage ID,
- raw vs filtered labels when relevant,
- whether data is raw, calibrated, filtered, or derived.

Avoid unlabeled “nice looking” plots. A plot that cannot be traced to input/config should not be used for handoff decisions.

## Reports

Reports should start with:

- conclusion / recommended action,
- input data used,
- config used,
- key metrics,
- interpretation,
- limitations,
- next validation step.

For Stage 6, include:

- candidate list,
- ranking table,
- selected candidate,
- rejected alternatives and reason,
- deployment target,
- validation checks after deployment.

## Retention policy

| Output class              | Keep?                  | Rule                                          |
| ------------------------- | ---------------------- | --------------------------------------------- |
| Raw input data            | Yes                    | Preserve; never edit in place.                |
| Stage metrics             | Yes                    | Needed for reproducibility.                   |
| Figures                   | Yes if used in reports | Regenerate if source/config changes.          |
| Temporary debug logs      | Optional               | Keep only while debugging.                    |
| Curated examples          | Yes                    | Store under `docs/examples/analysis-output/`. |
| Stale exploratory outputs | Archive/delete         | Do not present as current documentation.      |

## Validation checklist

- [ ] Output folder has unique run/stage ID.
- [ ] Input files are listed or linked.
- [ ] Config snapshot is present or command/config is logged.
- [ ] Figures have labels and units.
- [ ] Stage 6 recommendation is traceable to metrics.
- [ ] Generated outputs are not linked as canonical docs unless curated under `docs/examples/`.
