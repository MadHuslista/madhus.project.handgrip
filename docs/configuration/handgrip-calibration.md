# Handgrip Calibration Configuration Reference

**Status:** Canonical root configuration reference  
**Component:** `Handgrip_Calibration`  
**Detailed component doc:** `Handgrip_Calibration/docs/configuration.md`  
**Config sources:** `Handgrip_Calibration/conf/*.yaml`

## Summary

Calibration configs define the operator protocol, required LSL streams, output session structure, quality gates, segmentation behavior, model candidates, reporting, and holdout validation. The primary protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.

## Configuration table

| Key                                  | Type         | Default                                           | Allowed range / values                                                             | Operational impact                                         | When to change                        | Failure risk                                       |
| ------------------------------------ | ------------ | ------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------- | -------------------------------------------------- |
| `session.root_dir`                   | path         | `data/calibration`                                | Writable path.                                                                     | Session output root.                                       | Organize data.                        | Lost/misplaced session outputs.                    |
| `session.operator`                   | string       | `unknown`                                         | Operator name/ID.                                                                  | Report/provenance metadata.                                | Every real session.                   | Poor traceability.                                 |
| `session.purpose`                    | string       | `primary_static_reversible_staircase_calibration` | Descriptive label.                                                                 | Report/session intent.                                     | New protocol or study.                | Ambiguous session.                                 |
| `session.copy_component_configs`     | list[path]   | includes bridge, viewer, RS485 GUI configs        | Must point to existing files; RS485 GUI path is `../RS485_GUI/config/config.yaml`. | Reproducibility snapshot.                                  | When component config paths change.   | Missing provenance if stale path used.             |
| `streams.target.name`                | string       | `HandgripTarget`                                  | Must match bridge outlet.                                                          | Target stream discovery.                                   | Only coordinated stream migration.    | Preflight/recording fails.                         |
| `streams.target.channel_map.raw`     | string       | `target_raw_count`                                | Target stream channel label.                                                       | Calibration model input.                                   | If bridge channel labels change.      | Wrong/missing target signal.                       |
| `streams.reference.name`             | string       | `HandgripReference`                               | Must match bridge outlet.                                                          | Reference stream discovery.                                | Only coordinated stream migration.    | Preflight/recording fails.                         |
| `streams.reference.nominal_srate_hz` | float        | `500`                                             | Expected Hz.                                                                       | Reference QA thresholds.                                   | Board rate changes.                   | False pass/fail timing checks.                     |
| `markers.stream_name`                | string       | `HandgripCalibrationMarkers`                      | Marker stream name.                                                                | Protocol event alignment.                                  | Only marker contract migration.       | Viewer/session reconstruction misses markers.      |
| `protocol.name`                      | string       | `static_reversible_staircase_v3`                  | Protocol identifier.                                                               | Report and session metadata.                               | New protocol.                         | Report ambiguity.                                  |
| `protocol.baseline.duration_s`       | float        | `30`                                              | Positive seconds.                                                                  | Baseline stability estimate.                               | Short demos or stricter validation.   | Poor zero/drift evidence.                          |
| `protocol.preload.enabled`           | bool         | `true`                                            | `true`/`false`.                                                                    | Preconditioning cycles before fit holds.                   | Smoke tests or special protocols.     | Mechanical settling contaminates holds if skipped. |
| `protocol.holds.levels_N`            | list[number] | v3 reversible force-level list                    | Safe intended operating force levels.                                              | Different force range/study.                               | Unsafe load or poor model coverage.   |
| `protocol.holds.hold_duration_s`     | float        | `10`                                              | Positive seconds.                                                                  | Static hold length.                                        | Faster/slower protocols.              | Too few stable samples.                            |
| `protocol.holds.stable_window_s`     | float        | `5`                                               | Positive seconds <= hold duration.                                                 | Accepted segment used for fitting.                         | Tune stability extraction.            | Model trained on transient sections.               |
| `quality.reference_expected_hz`      | float        | `500`                                             | Expected reference Hz.                                                             | Reference-rate QA.                                         | Board rate changes.                   | Incorrect failure/pass criteria.                   |
| `quality.target_expected_hz_min/max` | float        | `85` / `105`                                      | Expected target range.                                                             | Target-rate QA.                                            | Firmware rate changes.                | False timing warnings.                             |
| `quality.max_hold_reference_std_N`   | float        | `0.5`                                             | Nonnegative N.                                                                     | Static hold stability threshold.                           | Study-specific force noise tolerance. | Unstable holds accepted or good holds rejected.    |
| `fit.candidate_models`               | list[string] | affine/robust/quadratic/piecewise/diagnostics     | Supported model names.                                                             | New candidate model.                                       | Bad model selected or code failure.   |
| `fit.target_signal`                  | string       | `raw`                                             | `raw` recommended.                                                                 | Selects target input.                                      | Rare; only explicit validation.       | Fitting against mutable `current_units`.           |
| `fit.reference_signal`               | string       | `raw`                                             | Valid reference signal alias.                                                      | Selects reference output.                                  | If reference channel map changes.     | Wrong ground-truth signal.                         |
| `fit.operating_range_N`              | float        | `100.0`                                           | Positive N.                                                                        | Percent-range metrics.                                     | Different intended force range.       | Misleading percent error.                          |
| `fit.export_firmware_constants`      | bool         | `true`                                            | `true`/`false`.                                                                    | Generates firmware constants for simple linear deployment. | Disable for host-side-only models.    | Operator may miss deployment values.               |
| `fit.selection.primary_metric`       | string       | `cv_rmse_N`                                       | Supported metric.                                                                  | Model-selection policy.                                    | Formal change in acceptance criteria. | Overfit/underfit selection.                        |
| `holdout_thresholds.*`               | number/null  | `null` unless defined                             | Study-defined thresholds.                                                          | Pass/fail holdout validation.                              | Before final deployment acceptance.   | No objective holdout gate.                         |

## Required path invariant

Use this path in calibration configs:

```yaml
- ../RS485_GUI/config/config.yaml
```

Do not use the stale path:

```yaml
- ../RS485_GUI/config.yaml
```
