# Handgrip Calibration Configuration

## Summary

- Calibration behavior is controlled by YAML files under `Handgrip_Calibration/conf/`.
- Protocol YAML files define what the operator does, which LSL streams are required, where outputs go, which quality gates apply, and how fit/report steps behave.
- The canonical production protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- The correct RS485 GUI config snapshot path is `../RS485_GUI/config/config.yaml`.
- Configuration edits should be validated with `preflight` before recording.

## Configuration areas

| Area                  | Purpose                                                       |
| --------------------- | ------------------------------------------------------------- |
| `metadata`            | Names/version/purpose of the protocol.                        |
| `session`             | Session ID, output root, config snapshots, operator behavior. |
| `lsl` / stream config | Required stream names, channel aliases, timeouts.             |
| `recording`           | Duration, prompt behavior, output formats, event logging.     |
| `protocol` / steps    | Baseline, preload, hold levels, repeats, dynamic trials.      |
| `quality`             | Minimum samples, gap limits, slope/std thresholds.            |
| `segmentation`        | Stable-window extraction and accepted-hold dataset.           |
| `fit`                 | Candidate models, thresholds, operating range.                |
| `report`              | Plots/tables/sections to emit.                                |
| `validation`          | Holdout model path, thresholds, pass/fail criteria.           |


## Fit configuration reference

| Key / concept                                | Meaning                                              | Recommended default behavior                                                              |
| -------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `operating_range_N`                          | Force range used to express percent-of-range errors. | Match intended calibration range, often `100.0`.                                          |
| `residual_threshold_percent_operating_range` | Deployment threshold as percent of range.            | Use strict threshold before firmware/bridge deployment.                                   |
| `primary_model`                              | Explicit selected model or `auto`.                   | Prefer `auto` for model comparison workflow.                                              |
| `candidate_models`                           | Candidate fit/model list.                            | Include affine, robust affine, nonlinear diagnostic, monotone piecewise, and diagnostics. |
| `selection.primary_metric`                   | Main ranking metric, often cross-validated RMSE.     | Prefer robust cross-validated metric.                                                     |
| `require_monotonic`                          | Reject non-monotone deployable mappings.             | Keep enabled for force calibration.                                                       |
| `allow_diagnostics_as_primary`               | Allow diagnostic-only models to be selected.         | Keep false unless deliberately changed.                                                   |
