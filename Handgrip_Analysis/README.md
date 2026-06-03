# Handgrip Analysis

## Summary

`Handgrip_Analysis` is the offline signal-analysis and filter-design package for captured handgrip data. It runs staged analyses to characterize startup drift, stationary noise, loaded drift/creep, real handgrip dynamics, interference conditions, and candidate digital filters.

It is file-based by design. Use it after acquisition/calibration data exists, not as the live acquisition authority.

## First command

New recordings can be done with the `LSL_Bridge`. 
After recording, copy the generated CSV files to `Handgrip_Analysis/data/calibration_signals/` and update the corresponding manifest in `Handgrip_Analysis/data/manifests/` before running the analysis.

From `Handgrip_Analysis/`:

```bash
uv run ha-run-all --help
```

Run a single stage with the relevant stage entry point. Example static-noise run:

```bash
uv run ha-stage2 manifest=data/manifests/stage2_manifest.csv outdir=data/analysis_results/stage2
```

Run from a manifest when prepared:

```bash
uv run ha-run-all \
  manifest=path/to/capture_manifest.csv \
  base_outdir=outputs/batch_run
```

## Quickstart 
  
Initial Handgrip recordings done following [Handgrip_Analysis/docs/stages.md](docs/stages.md) are available in `data/calibration_signals/` and indexed in `data/manifests/`.

To observe the analysis results on these example recordings, go to `Handgrip_Analysis` and run:

```bash
# Per-stage analysis:
ha-run-all manifest=data/manifests/analysis_stages_1_4_manifest.csv base_outdir=data/analysis_results stages=stage1,stage2,stage3,stage4
```

```bash
# Filter design review:
ha-stage stage=stage6 manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6 filter_config=conf/filters/candidates.yaml
```

On new recordings, make sure to clean the output directory to ensure that the analysis runs with a clean slate and that all expected outputs are generated.

## Expected results

**Stage 1-5**: Metrics and plots characterizing startup drift, stationary noise, loaded drift/creep, real handgrip dynamics, and interference conditions.

**Stage 6**: 
Candidate filter performance metrics, plots, and a filter recommendation based on the selected policy.
In particular review: 
- Filter Design Report  : `data/analysis_results/stage6/stage6_review_design_report.md`
- Acceptance Report     : `data/analysis_results/stage6/filter_acceptance_report.md`


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

Full configuration reference is planned at [Handgrip_Analysis/docs/configuration.md](docs/configuration.md).

## Documentation

Full reading guide, per-document map, and related cross-component docs: [Handgrip_Analysis/docs/index.md](docs/index.md).

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
uv run ha-stage6-design --help
```

If your installed entry points differ, check the active `pyproject.toml` and update this README plus [docs/workflows/handgrip-analysis.md](../docs/workflows/handgrip-analysis.md) together.
