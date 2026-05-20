# Handgrip Analysis

## Summary

`Handgrip_Analysis` is the offline signal-analysis and filter-design package for captured handgrip data. It runs staged analyses to characterize startup drift, stationary noise, loaded drift/creep, real handgrip dynamics, interference conditions, and candidate digital filters.

It is file-based by design. Use it after acquisition/calibration data exists, not as the live acquisition authority.

## When to use this component

Use this component when you need to:

- analyze saved target/reference CSV data,
- quantify startup warm-up / zero drift,
- characterize rest noise and spectral behavior,
- measure loaded drift or creep,
- compare real handgrip dynamics,
- evaluate interference conditions,
- rank filter candidates and generate deployment recommendations.

Do not use this component to:

- run live RS485 acquisition,
- publish LSL streams,
- record calibration protocols,
- change firmware constants directly without validation.

## First command

From `Handgrip_Analysis/`:

```bash
uv run ha-run-all --help
```

Run a single stage with the relevant stage entry point or script. Example static-noise run:

```bash
uv run ha-stage2 analysis=stage2 \
  input=data/calibration_signals/example_static_rest.csv \
  outdir=data/analysis_results/stage_2
```

Run from a manifest when prepared:

```bash
uv run ha-run-all \
  manifest=path/to/capture_manifest.csv \
  base_outdir=outputs/batch_run
```

## Expected result

Expected successful behavior:

- input files/manifests resolve,
- the selected stage runs without missing-column errors,
- output folder is created,
- machine-readable metrics are written,
- plots/reports are generated,
- Stage 6 outputs include candidate comparison and a filter recommendation when applicable.

Stop if the manifest cannot be traced to source data or if the selected filter recommendation cannot be linked to metrics.

## Configuration

Primary config tree:

```text
Handgrip_Analysis/conf/
├── config.yaml
├── analysis/
│   ├── stage1.yaml
│   ├── stage2.yaml
│   ├── stage3.yaml
│   ├── stage4.yaml
│   ├── stage5.yaml
│   └── stage6.yaml
├── dsp/
├── filters/
└── io/
```

Main configuration areas:

| Area              | Purpose                                                       |
| ----------------- | ------------------------------------------------------------- |
| input / manifest  | Source CSVs, labels, channel mapping, batch dispatch.         |
| output / IO       | Output directory, overwrite policy, report paths.             |
| stage configs     | Stage-specific windows, metrics, plots, thresholds.           |
| DSP defaults      | Sampling assumptions, filtering utilities, spectral settings. |
| filter candidates | Candidate families and parameters for Stage 6 evaluation.     |

Full configuration reference is planned at [`docs/configuration.md`](docs/configuration.md).

## Common workflows

| Goal                         | Document                                                                                                 |
| ---------------------------- | -------------------------------------------------------------------------------------------------------- |
| Run offline analysis         | [`../docs/workflows/handgrip-analysis.md`](../docs/workflows/handgrip-analysis.md)                       |
| Navigate component docs      | [`docs/index.md`](docs/index.md)                                                                         |
| Understand stages            | [`docs/stages.md`](docs/stages.md)                                                                       |
| Interpret filter design      | [`docs/filter-design.md`](docs/filter-design.md)                                                         |

## Repository layout

```text
Handgrip_Analysis/
├── README.md
├── conf/
│   ├── config.yaml
│   ├── analysis/
│   ├── dsp/
│   ├── filters/
│   └── io/
├── docs/
│   └── index.md
├── scripts/
│   ├── stage1_startup_warmup.py
│   ├── stage2_static_noise.py
│   ├── stage3_loaded_drift.py
│   ├── stage4_grip_dynamics.py
│   ├── stage5_interference_compare.py
│   ├── stage6_filter_design.py
│   └── run_all.py
├── src/
│   └── handgrip_analysis/
└── tests/
```

## Tests

Run from `Handgrip_Analysis/` after dependencies are installed:

```bash
uv run pytest
```

For a quick CLI smoke check:

```bash
uv run ha-run-all --help
uv run ha-stage1 --help
uv run ha-stage6 --help
```

If your installed entry points differ, check the active `pyproject.toml` and update this README plus [`docs/workflows/handgrip-analysis.md`](../docs/workflows/handgrip-analysis.md) together.

## Further docs

- [`docs/index.md`](docs/index.md) — analysis documentation map.
- [`../docs/workflows/handgrip-analysis.md`](../docs/workflows/handgrip-analysis.md) — root analysis workflow.
- [`README_filter_design_report.md`](README_filter_design_report.md) — current filter-design report source until migrated into [`docs/filter-design.md`](docs/filter-design.md).
