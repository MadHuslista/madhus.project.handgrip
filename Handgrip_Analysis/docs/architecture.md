# Handgrip Analysis Architecture

## Summary

- `Handgrip_Analysis` is an offline package organized around CLI entry points, staged analysis modules, configuration, IO, DSP utilities, plotting, and report generation.
- The architecture should keep numerical computation testable and separate from command-line parsing, file IO, and report rendering.
- Generated outputs must be reproducible from source input files and config snapshots.

## Layer map

```text
CLI layer
  ├── ha-run-all
  ├── ha-stage / stage-specific commands
  └── argument/config overrides

Config layer
  ├── root config
  ├── stage configs
  ├── DSP/filter configs
  └── IO/report configs

IO layer
  ├── manifest loader
  ├── CSV/session loader
  ├── output directory manager
  └── config snapshot writer

Stage layer
  ├── stage1_startup_warmup
  ├── stage2_static_noise
  ├── stage3_loaded_drift
  ├── stage4_grip_dynamics
  ├── stage5_interference_compare
  └── stage6_filter_design

Core/DSP layer
  ├── signal validation
  ├── window/event selection
  ├── PSD/noise metrics
  ├── filter candidate application
  └── metric computation

Report layer
  ├── markdown reports
  ├── tables/CSV/JSON
  ├── figures/plots
  └── recommendation YAML
```

## CLI layer

Responsibilities:

- parse command-line arguments,
- load config,
- dispatch all stages or one stage,
- print output location,
- exit with clear status.

It should not contain stage math directly.

## Config layer

Responsibilities:

- define defaults,
- merge CLI overrides,
- validate required fields,
- provide stage-specific settings,
- preserve config used for each run.

Avoid hidden constants in stage code when a value should be configurable or reportable.

## IO layer

Responsibilities:

- load CSV/session/manifest inputs,
- validate columns,
- normalize timestamps if needed,
- create output directories,
- write metrics/reports/figures,
- snapshot config and command context.

IO should fail early on missing data rather than returning empty arrays that create misleading reports.

## Stage layer

Each stage should follow the same shape:

```text
load inputs → validate schema → compute metrics → render figures → write report/artifacts
```

Recommended stage function boundary:

```python
def run_stage(config, inputs, output_dir) -> StageResult:
    ...
```

## Core/DSP layer

Responsibilities:

- pure numerical transformations,
- metrics,
- filter design/application,
- PSD/spectral functions,
- reusable plotting data preparation.

Keep this layer independent from CLI and filesystem when practical so it can be unit-tested.

## Report layer

Responsibilities:

- summarize results,
- explain interpretation,
- include key assumptions and limitations,
- write human-readable and machine-readable outputs.

Stage reports should be useful without opening source code.

## Data contract with upstream components

Analysis usually consumes outputs that originated from:

- `Handgrip_Calibration` session files,
- `LSL_Bridge` CSV recordings,
- `RS485_GUI` logs or curated reference exports,
- manually curated CSV captures.

The analysis layer should document which columns it requires rather than assuming a single hidden format.

## Validation checklist

- [ ] CLI commands show `--help`.
- [ ] Missing input files produce clear errors.
- [ ] Missing required columns produce clear errors.
- [ ] Output directory is created once per run/stage.
- [ ] Stage math is testable without CLI invocation.
- [ ] Report and metrics artifacts are written for each successful stage.
