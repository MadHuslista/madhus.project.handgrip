# Handgrip Calibration Architecture

## Summary

- `Handgrip_Calibration` is a CLI-oriented calibration package.
- The CLI coordinates preflight, recording, fitting, reporting, and validation modules.
- The component consumes canonical LSL streams from `LSL_Bridge` and writes reproducible session folders under `data/calibration/`.
- The architecture should preserve a clean separation between protocol definition, data capture, model fitting, and report rendering.

## High-level flow

```text
CLI command
  ├── load YAML config/protocol
  ├── validate required streams/channels
  ├── run subcommand
  │   ├── preflight
  │   ├── record
  │   ├── segment / reduce holds
  │   ├── fit
  │   ├── report
  │   └── validate-holdout
  └── write outputs to session folder
```

## Module responsibilities

| Area                   | Expected responsibility                                               |
| ---------------------- | --------------------------------------------------------------------- |
| `cli.py`               | Parse subcommands, config path, session paths, and dispatch.          |
| config schema/loading  | Validate YAML structure, defaults, protocol fields, and overrides.    |
| preflight              | Check LSL stream discovery, channels, output paths, config snapshots. |
| recorder               | Pull LSL target/reference samples and write session artifacts.        |
| protocol/event layer   | Emit/record baseline, holds, validation markers, operator prompts.    |
| segmentation/reduction | Convert recorded holds into accepted calibration dataset rows.        |
| fitting                | Evaluate candidate models, metrics, thresholds, and selected model.   |
| validation             | Evaluate accepted model on holdout sessions.                          |
| report                 | Render Markdown/HTML, plots, tables, and deployment recommendations.  |

## Input boundaries

`Handgrip_Calibration` should consume:

- `HandgripTarget` LSL stream,
- `HandgripReference` LSL stream,
- optional component events,
- operator/protocol markers,
- YAML protocol/config files.

It should not:

- read RS485 hardware directly,
- parse firmware serial directly,
- publish LSL force streams,
- silently change acquisition-board settings.

## Output boundaries

The component owns:

- session folder creation,
- calibration event records,
- target/reference capture files,
- fit artifacts,
- reports,
- holdout validation artifacts.

It does not own:

- firmware flashing,
- RS485 GUI logs,
- LSL Bridge stream publication,
- viewer display state.

## Command architecture

| Command            | Input                            | Output                              |
| ------------------ | -------------------------------- | ----------------------------------- |
| `preflight`        | protocol config + live streams   | pass/fail diagnostics.              |
| `record`           | protocol config + live streams   | session folder with samples/events. |
| `segment`          | session folder + config          | accepted-hold dataset.              |
| `fit`              | session folder + config          | model artifacts and metrics.        |
| `report`           | session folder + artifacts       | human-readable report.              |
| `validate-holdout` | holdout session + model artifact | validation result artifacts.        |
| `demo-data`        | synthetic/session options        | hardware-free demo session.         |

## Reproducibility principles

- Every session should have a stable session ID.
- Every production session should copy upstream component configs.
- Every report should identify protocol, session, selected model, and source artifacts.
- Every deployment should be traceable to a fit session and validation session.

## Architecture validation checklist

- [ ] CLI subcommands are documented in `quickstart.md` and this architecture doc.
- [ ] Config path behavior is documented in `configuration.md`.
- [ ] LSL inputs are documented in `recording.md`.
- [ ] Model selection is documented in `fitting-and-model-selection.md`.
- [ ] Outputs are documented in `reports-and-outputs.md`.
- [ ] Deployment is documented in `applying-calibration-results.md`.
