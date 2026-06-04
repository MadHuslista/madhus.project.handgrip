# Handgrip Calibration Recording

## Summary

- The recording process captures synchronized target/reference LSL data plus protocol events into a session folder.
- Required live streams are `HandgripTarget` and `HandgripReference`.
- The session folder is expected to contain enough raw data, events, and config snapshots to reproduce fitting and reporting.


## Workflow

The preflight, recording, fitting, and validation commands live in [Handgrip_Calibration/docs/workflow.md](workflow.md). This document owns what those steps depend on: session folder structure, preflight acceptance gates, and acquisition-board configuration.

During recording, follow operator prompts exactly. Do not skip baseline/preload/hold steps unless the protocol explicitly allows it.

**The quality of the calibration fit depends entirely on the quality of the recording.** 

## Session IDs

A session ID should uniquely identify a recording.

```text
YYYY-MM-DD_HHMMSS_<protocol_or_label>
```

Expected folder:

```text
Handgrip_Calibration/data/calibration/<session_id>/
```


## Captured files

Exact filenames are implementation-owned, but a complete session should contain these artifact classes:

| Artifact class         | Expected files           | Purpose                                  |
| ---------------------- | ------------------------ | ---------------------------------------- |
| target data            | `target.csv`             | Target stream samples and timing.        |
| reference data         | `reference.csv`          | Reference force samples and timing.      |
| protocol events        | `events.ndjson`          | Segment boundaries and operator markers. |
| live quality telemetry | `quality_live.ndjson`    | Gap/status/rate diagnostics.             |
| config snapshots       | copied YAML/config files | Reproducibility.                         |
| metadata               | JSON/YAML manifest       | Session identity and protocol metadata.  |


## Preflight acceptance gates

Do not start the protocol until all gates pass:

| Gate                   | Pass criterion                                                             |
| ---------------------- | -------------------------------------------------------------------------- |
| Reference live rate    | `498–500 Hz` preferred, `>= 495 Hz` minimum                               |
| Target live rate       | approximately `85–105 Hz`                                                  |
| Reference max gap      | below `0.020 s`                                                            |
| Target max gap         | below `0.100 s`                                                            |
| Reference zero noise   | low enough that a 3 s hold passes `max_hold_reference_std_N: 0.5`         |
| Force response sign    | reference and target move monotonically in the same physical direction     |
| No target parser drops | `target_status` does not show persistent not-ready/overflow conditions     |

These thresholds correspond to the `QualityConfig` defaults in the protocol YAML:

```yaml
quality:
  reference_expected_hz: 500
  reference_min_hz: 495
  reference_max_gap_s: 0.02
  target_expected_hz_min: 85
  target_expected_hz_max: 105
  target_max_gap_s: 0.1
  max_hold_reference_std_N: 0.5
  max_hold_reference_slope_N_per_s: 0.2
  max_baseline_drift_N_per_min: 0.5
  min_hold_target_samples: 20
  min_hold_reference_samples: 100
```

## Recommended acquisition board configuration for recording

Before recording, ensure the acquisition board is configured for clean calibration-quality reference output. Key settings:

| Setting                      | Recommended value | Why                                                            |
| ---------------------------- | ----------------- | -------------------------------------------------------------- |
| Internal sampling (`100.SP`) | `640 Hz`          | Preserves timing detail for the reference force trace          |
| ADC gain (`101.GA`)          | `128B`            | Matches PM58 sensitivity to ADC resolution                     |
| Median filter (`102.ME`)     | `3`               | Suppresses impulse outliers without adding significant lag     |
| Average filter (`103.rV`)    | `5`               | Modest smoothing while preserving dynamics                     |
| Unit (`105.uN`)              | `N`               | Ensures reference force is in Newtons, consistent with reports |
| Creep tracking (`400.CV`)    | `0`               | Disabled — hidden correction distorts calibration data         |
| Dynamic tracking (`402.tV`)  | `0`               | Disabled — can distort the force trace                         |
| Auto-zero (`409.AZ`)         | `0`               | Disabled — prevents silent drift correction during session     |
| Power-on zero (`406.PZ`)     | `0`               | Disabled — prevents baseline shift at startup                  |
| RS485 mode (`504.AS`)        | `1` (Active-Send) | Recommended 500 Hz push mode                                   |
| Active-Send rate (`505.AF`)  | `500 Hz`          | High enough to preserve timing detail                          |
| Baud (`501.br`)              | `460800`          | Required for 500 Hz Active-Send                                |

For the full per-register rationale behind these recommended values, see [docs/hardware/dual-device-calibration-configuration.md](../../docs/hardware/dual-device-calibration-configuration.md). For the complete board menu reference and commissioning sequence, see [docs/hardware/acquisition-board-reference.md](../../docs/hardware/acquisition-board-reference.md).
