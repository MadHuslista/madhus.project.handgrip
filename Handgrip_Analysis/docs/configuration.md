# Handgrip Analysis Configuration

## Summary

- `Handgrip_Analysis` uses a config tree to select inputs, outputs, stages, DSP settings, filter candidates, and report behavior.
- Config values affect interpretation and reproducibility; do not edit them without recording which run/session they apply to.
- This document describes the intended full config tree. If the active source tree differs, update this reference and the root analysis workflow together.

## Expected config tree

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

## Root config areas

| Area | Purpose | Impact | Failure risk |
| --- | --- | --- | --- |
| `input` / `manifest` | Source data paths and channel mapping. | Controls what data is analyzed. | Missing/wrong columns, wrong session, wrong signal. |
| `output` / `io` | Output directory and overwrite policy. | Controls where reports/plots/metrics are written. | Overwrite prior results or lose provenance. |
| `stages` | Select enabled stages and stage order. | Controls which analyses run. | Missing expected reports or using stale output. |
| `analysis.stageN` | Stage-specific windows, metrics, thresholds. | Controls computation and interpretation. | Wrong windows/thresholds produce misleading metrics. |
| `dsp` | Sampling rate, filtering helpers, PSD settings. | Controls signal-processing assumptions. | Invalid frequency assumptions or unstable filters. |
| `filters` | Candidate filter families and parameters. | Controls Stage 6 search/recommendation. | Candidate bank too narrow or unsafe to deploy. |
| `reports` | Report format/sections/figures. | Controls human-facing outputs. | Missing interpretation or incomplete handoff artifacts. |

## Input / manifest settings

| Key class | Type | Required | Operational impact | Failure risk |
| --- | --- | --- | --- | --- |
| `manifest` | path | for batch/all-stage runs | Dispatches multiple files/conditions. | Missing source data or labels. |
| `input` | path | for single-file runs | Selects one CSV/session artifact. | Wrong file analyzed. |
| `time_column` | string | yes | Defines sample times. | Incorrect sampling or event timing. |
| `signal_column` | string | yes | Defines primary signal. | Analyzes wrong channel. |
| `condition_column` | string | optional | Enables condition comparisons. | Stage 5 grouping fails. |
| `sampling_rate_hz` | number | required for DSP when timestamps insufficient | Defines normalized filter/PSD frequencies. | Invalid cutoff frequencies. |

## Stage config reference

| Stage | Config file | Key settings | Notes |
| --- | --- | --- | --- |
| Stage 1 | `conf/analysis/stage1.yaml` | startup window, stabilization criteria, drift fit method | Use to decide discard/warm-up interval. |
| Stage 2 | `conf/analysis/stage2.yaml` | rest window, PSD method, bandpower settings | Use to quantify noise and narrowband components. |
| Stage 3 | `conf/analysis/stage3.yaml` | hold windows, drift/creep fit, zero-return window | Use to evaluate loaded stability. |
| Stage 4 | `conf/analysis/stage4.yaml` | event windows, rise/peak/release definitions | Use to characterize realistic force events. |
| Stage 5 | `conf/analysis/stage5.yaml` | condition labels, comparison metrics | Use to compare setup/environment conditions. |
| Stage 6 | `conf/analysis/stage6.yaml` | candidate set, ranking metrics, deployment outputs | Use to choose filters. |

## DSP settings

| Setting | Type | Impact | Safe-edit guidance |
| --- | --- | --- | --- |
| `sampling_rate_hz` | number | Defines Nyquist frequency and cutoff validity. | Must match actual data or timestamp-derived rate. |
| `psd.nperseg` | integer | Controls spectral resolution vs variance. | Use enough samples; document changes. |
| `filter.order` | integer | Controls steepness and phase/latency behavior. | Prefer low order unless justified. |
| `filter.cutoff_hz` | number/list | Defines pass/stop behavior. | Must be below Nyquist and validated against dynamics. |
| `zero_phase` | boolean | Controls offline zero-phase vs causal deployment behavior. | Do not compare zero-phase offline filters to causal real-time deployment without noting difference. |

## Filter candidate settings

Candidate config should record:

- candidate ID,
- filter family,
- order,
- cutoff/band/notch frequency,
- sampling rate assumption,
- whether it is causal or zero-phase,
- target deployment path.

Example candidate concept:

```yaml
filters:
  candidates:
    - id: butter_lowpass_15hz
      family: butter_lowpass
      order: 2
      cutoff_hz: 15.0
      sampling_rate_hz: 100.0
      deployment_target: lsl_bridge_processing
```

## Output settings

| Key class | Purpose | Recommended behavior |
| --- | --- | --- |
| `base_outdir` | Root folder for analysis outputs. | Include run/stage ID to avoid accidental overwrite. |
| `overwrite` | Whether prior outputs can be overwritten. | Default false for reproducibility. |
| `save_figures` | Enable/disable plot export. | True for reports and handoff. |
| `save_metrics` | Enable JSON/CSV metrics. | True for reproducibility. |
| `write_recommendation_yaml` | Emit deployment recommendation. | True for Stage 6. |

## Override examples

```bash
uv run ha-run-all manifest=data/manifests/capture_manifest.csv base_outdir=data/analysis_results/batch_run
```

```bash
uv run ha-stage stage=stage6 filter_config=conf/filters/candidates.yaml outdir=data/analysis_results/stage6
```

## Validation checklist

- [ ] Input paths resolve.
- [ ] Required columns exist.
- [ ] Sampling rate is known or derivable.
- [ ] Filter cutoffs are below Nyquist.
- [ ] Output directory is unique or overwrite is explicit.
- [ ] Stage 6 candidate set includes identity/raw baseline.
- [ ] Config used for the run is copied or logged with outputs.
