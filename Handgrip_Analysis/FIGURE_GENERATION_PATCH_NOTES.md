# Figure Generation Patch Notes

## Problem fixed

The Phase 2/3 manifest-driven pipeline created the standard figure directories:

- `figures/per_trial/`
- `figures/aggregate/`

but only placed `README.md` placeholders there. The previous implementation intentionally established the Phase 3 output contract first, but did not yet wire the plotting layer into the package-native `ha-stage` / `ha-run-all` pipeline.

## What changed

- Added `src/handgrip_analysis/plotting.py`.
- Connected `generate_stage_figures(...)` into `pipeline.write_stage_outputs(...)`.
- Generated real PNG figures for manifest-driven execution.
- Kept the placeholder `README.md` only as a directory explanation, not as a replacement for plots.
- Added tests that assert PNG files are produced by the package-native pipeline.

## Figures now generated

### Stage 1

Per trial:

- warm-up diagnostic plot: raw signal, rolling mean, rolling std, absolute slope

Aggregate:

- ready time by trial
- final rolling standard deviation by trial

### Stage 2

Per trial:

- time series
- histogram
- Welch power spectral density
- Allan deviation

Aggregate:

- condition-level median power spectral density
- raw standard deviation by trial
- top spectral peak by trial

### Stage 3

Per trial:

- loaded-drift trace with linear trend
- detrended residual

Aggregate:

- drift slope by trial
- return-to-zero error by trial

### Stage 4

Per trial:

- signal with detected event windows and peak markers

Aggregate:

- event-aligned overlay
- peak value by trial
- rise time by trial

### Stage 5

Per trial:

- time series
- histogram
- power spectral density

Aggregate:

- condition-level median power spectral density
- top spectral peak by trial
- robust standard deviation by trial

### Stage 6

Per trial:

- input signal plots for rest/dynamic filter-review trials

Aggregate:

- composite filter score chart
- rest PSD: raw versus top-ranked candidates

## Validation

Validated in split test groups because a single full-suite invocation exceeded the execution-tool wall-time in this environment:

```text
PYTHONPATH=src pytest -q tests/unit/test_dsp.py
38 passed

PYTHONPATH=src pytest -q tests/unit/test_io.py
12 passed

PYTHONPATH=src pytest -q tests/unit/test_manifest_phase1.py
5 passed

PYTHONPATH=src pytest -q tests/integration/test_cli_overrides.py
3 passed

PYTHONPATH=src pytest -q tests/integration/test_pipeline.py
5 passed

PYTHONPATH=src pytest -q tests/integration/test_phase23_cli.py
2 passed

PYTHONPATH=src python -m compileall -q src scripts tests
compile_ok
```

Smoke-tested on the existing real trial manifests:

```text
stage1 -> 4 PNG figures
stage2 -> 11 PNG figures
stage3 -> 4 PNG figures
stage4 -> 9 PNG figures
stage6 -> 10 PNG figures
```

## Small-n uncertainty optimization

The bootstrap helper now uses the observed min/max interval for exactly two trials instead of running thousands of resamples. This is faster and more honest for the current small-N repeated-trial dataset.
