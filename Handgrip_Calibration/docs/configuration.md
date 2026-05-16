# Handgrip Calibration Configuration

## Summary

- Calibration behavior is controlled by YAML files under `Handgrip_Calibration/conf/`.
- Protocol YAML files define what the operator does, which LSL streams are required, where outputs go, which quality gates apply, and how fit/report steps behave.
- The canonical production protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- The correct RS485 GUI config snapshot path is `../RS485_GUI/config/config.yaml`.
- Configuration edits should be validated with `preflight` before recording.

## Main config files

| File                                                | Role                                                      | Status                 |
| --------------------------------------------------- | --------------------------------------------------------- | ---------------------- |
| `conf/protocol_static_reversible_staircase_v3.yaml` | Primary reversible static staircase calibration protocol. | Canonical primary.     |
| `conf/protocol_reference_verification.yaml`         | Reference chain verification.                             | Canonical pre-check.   |
| `conf/protocol_holdout_verification.yaml`           | Independent validation after fitting.                     | Canonical validation.  |
| `conf/protocol_static_staircase.yaml`               | Older/static baseline workflow.                           | Legacy/basic baseline. |
| `conf/protocol_low_force_refinement.yaml`           | Optional low-force refinement.                            | Optional.              |
| `conf/protocol_creep_zero_return.yaml`              | Creep and zero-return diagnostic.                         | Optional.              |
| `conf/protocol_dynamic_validation.yaml`             | Dynamic ramps/squeezes diagnostic.                        | Optional.              |
| `conf/protocol_fast_smoke_test.yaml`                | Fast operator/developer smoke test.                       | Non-production.        |
| `conf/default.yaml` / `conf/config.yaml`            | Base/default settings depending on command path.          | Support/base.          |
| `conf/template.yaml`                                | Starting point for new protocols.                         | Authoring template.    |

## Configuration areas

| Area                  | Purpose                                                       | Typical risk if wrong                                   |
| --------------------- | ------------------------------------------------------------- | ------------------------------------------------------- |
| `metadata`            | Names/version/purpose of the protocol.                        | Reports become ambiguous.                               |
| `session`             | Session ID, output root, config snapshots, operator behavior. | Data cannot be traced or reproduced.                    |
| `lsl` / stream config | Required stream names, channel aliases, timeouts.             | Preflight fails or records wrong channels.              |
| `recording`           | Duration, prompt behavior, output formats, event logging.     | Missing files, incomplete sessions, operator confusion. |
| `protocol` / steps    | Baseline, preload, hold levels, repeats, dynamic trials.      | Bad fit coverage or unsafe loads.                       |
| `quality`             | Minimum samples, gap limits, slope/std thresholds.            | Poor holds accepted or good holds rejected.             |
| `segmentation`        | Stable-window extraction and accepted-hold dataset.           | Model trained on unstable data.                         |
| `fit`                 | Candidate models, thresholds, operating range.                | Wrong deployment model selected.                        |
| `report`              | Plots/tables/sections to emit.                                | Report lacks deployment/validation evidence.            |
| `validation`          | Holdout model path, thresholds, pass/fail criteria.           | Deployment accepted without out-of-sample evidence.     |

## Stream/channel configuration

The canonical root contract is [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md).

Minimum calibration input contract:

| Input                  | Expected semantic name                             |
| ---------------------- | -------------------------------------------------- |
| Target stream          | `HandgripTarget`                                   |
| Reference stream       | `HandgripReference`                                |
| Target fit input       | `target_raw_count`                                 |
| Reference ground truth | `reference_force_N` or mapped net force equivalent |
| Target timing          | LSL timestamp and/or `device_clock_us`             |
| Reference timing       | LSL timestamp and/or reference clock metadata      |
| Markers/events         | `HandgripCalibrationMarkers` / `events.ndjson`     |

## Component config snapshots

Production protocols should snapshot upstream configs:

```yaml
session:
  copy_component_configs:
    - ../LSL_Bridge/conf/config.yaml
    - ../LSL_Viewer/conf/config.yaml
    - ../RS485_GUI/config/config.yaml
```

If this list is wrong, calibration may still run but reproducibility is weakened.

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

## Quality gate reference

| Gate                                   | Why it matters                                                 |
| -------------------------------------- | -------------------------------------------------------------- |
| minimum target samples                 | Prevents fitting on too few target observations.               |
| minimum reference samples              | Ensures stable reference statistics.                           |
| reference max gap                      | Prevents interpolation over missing reference data.            |
| reference slope threshold              | Ensures a static hold is actually stable.                      |
| reference standard deviation threshold | Rejects noisy holds.                                           |
| target sequence gap count              | Rejects target acquisition discontinuities.                    |
| operator accepted marker               | Ensures protocol intent and software quality gates both agree. |

## Safe override examples

From `Handgrip_Calibration/`:

```bash
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Run a different protocol explicitly:

```bash
uv run handgrip-cal record --config conf/protocol_reference_verification.yaml
```

Avoid undocumented ad-hoc changes to stream names or channel labels. If the stream contract changes, update [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md), `LSL_Bridge` docs/config, viewer docs/config, and calibration docs/config together.

## Validation checklist

```bash
# Protocol config references v3 primary.
rg "protocol_static_reversible_staircase_v3.yaml" Handgrip_Calibration/README.md Handgrip_Calibration/docs

# Correct config snapshot path.
rg "\.\./RS485_GUI/config/config\.yaml" Handgrip_Calibration/conf

# No stale path.
if rg "\.\./RS485_GUI/config\.yaml" Handgrip_Calibration/conf Handgrip_Calibration/docs; then
  echo "ERROR: stale RS485_GUI config snapshot path found" >&2
  exit 1
fi
```
