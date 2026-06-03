# Handgrip Calibration Recording

## Summary

- The recording process captures synchronized target/reference LSL data plus protocol events into a session folder.
- Required live streams are `HandgripTarget` and `HandgripReference`.
- The session folder is expected to contain enough raw data, events, and config snapshots to reproduce fitting and reporting.


## Preflight before recording

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Preflight verify:

- required LSL streams are visible,
- required channel labels are present or mappable,
- reference stream is live,
- target stream is live,
- protocol config parses,
- output root is writable,
- component config snapshot paths exist.

## Recording command

```bash
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
```

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
