# Handgrip Calibration Recording

## Summary

- Recording captures synchronized target/reference LSL data plus protocol events into a session folder.
- Required live streams are `HandgripTarget` and `HandgripReference`.
- The session folder must contain enough raw data, events, and config snapshots to reproduce fitting and reporting.
- A valid recording is not merely “a file exists”; it must pass stream discovery, data presence, event coverage, and quality gates.

## Required LSL inputs

| Input | Producer | Use |
| --- | --- | --- |
| `HandgripTarget` | `LSL_Bridge` from firmware UART | Target raw counts, target timing, status. |
| `HandgripReference` | `LSL_Bridge` from RS485 GUI IPC | Reference force ground truth. |
| `HandgripComponentEvents` | `LSL_Bridge` | Optional diagnostics: gaps, reconnects, parse issues. |
| `HandgripCalibrationMarkers` | `Handgrip_Calibration` / session events | Protocol segmentation: baseline, holds, validation trials. |

## Preflight before recording

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Preflight should verify:

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

## Session IDs

A session ID should uniquely identify a recording. Recommended format:

```text
YYYY-MM-DD_HHMMSS_<protocol_or_label>
```

Expected folder:

```text
Handgrip_Calibration/data/calibration/<session_id>/
```

Use the full session ID in lab notes, commit messages, reports, and handoff communications.

## Captured files

Exact filenames are implementation-owned, but a complete session should contain these artifact classes:

| Artifact class | Expected examples | Purpose |
| --- | --- | --- |
| target data | `target.csv` or equivalent | Target stream samples and timing. |
| reference data | `reference.csv` or equivalent | Reference force samples and timing. |
| protocol events | `events.ndjson` or equivalent | Segment boundaries and operator markers. |
| live quality telemetry | `quality_live.ndjson` or equivalent | Gap/status/rate diagnostics. |
| config snapshots | copied YAML/config files | Reproducibility. |
| metadata | JSON/YAML manifest | Session identity and protocol metadata. |

## Data contract during recording

Target data should preserve:

- LSL timestamp,
- firmware `seq`,
- firmware `timestamp_us` / device clock,
- `target_raw_count`,
- `target_current_units`,
- `target_status`.

Reference data should preserve:

- LSL timestamp,
- reference force / net force value,
- board/reference clock if available,
- reference status if available,
- enough metadata to diagnose gaps.

## Quality checks after recording

Before fitting, inspect:

| Check | Pass condition |
| --- | --- |
| files exist | target, reference, events, config snapshots present. |
| sample counts | enough target/reference samples for all holds. |
| target gaps | no unexplained sequence gaps during accepted holds. |
| reference gaps | below configured max gap threshold. |
| force coverage | holds cover intended force levels. |
| stable tails | accepted holds have stable reference force. |
| operator markers | protocol events match performed actions. |

## Failure modes

| Symptom | Likely cause | Action |
| --- | --- | --- |
| missing target file | target stream not discovered or recording failed | rerun preflight, validate firmware/bridge. |
| missing reference file | RS485 GUI/bridge IPC issue | rerun reference-only and full-live quickstarts. |
| events missing | marker/event writer disabled or crashed | do not fit; rerun recording. |
| few target samples | HX711/firmware/status issue | validate target D2 stream. |
| reference gaps | RS485 parser/backlog/serial rate issue | validate RS485 GUI and board config. |
| force levels wrong | operator prompt/fixture issue | rerun protocol with documented fixture setup. |

## Stop condition

Do not proceed to `fit` if the session cannot be traced to:

- a protocol config,
- target and reference data,
- event markers,
- component config snapshots,
- physical fixture validation notes.
