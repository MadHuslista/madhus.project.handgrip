# Live, CSV, and XDF Modes

## Summary

- `LSL_Viewer` supports four mode strings: `live`, `live_with_reference_validation`, `csv_replay`, and `xdf_replay`.
- Live modes consume LSL streams directly.
- Replay modes load files from disk and pass them through the same NiceGUI plotting model.
- CSV replay expects separate target/reference CSV files.
- XDF replay requires `pyxdf` and an XDF file containing the expected streams/channels.

## Supported modes

| Mode | Input | Use for |
| --- | --- | --- |
| `live` | live LSL streams | Normal operator visualization. |
| `live_with_reference_validation` | live LSL streams | Extra reference validation during setup/calibration prep. |
| `csv_replay` | target/reference CSV files | Inspect bridge/calibration outputs without hardware. |
| `xdf_replay` | XDF file | Inspect LSL recordings with stream metadata. |

## Live mode

Command:

```bash
cd LSL_Viewer
uv run lsl-viewer mode=live
```

Expected inputs:

| Stream | Expected producer |
| --- | --- |
| `HandgripTarget` | `LSL_Bridge` target outlet. |
| `HandgripReference` | `LSL_Bridge` reference outlet. |

Expected result:

- viewer UI opens,
- target/reference plots update,
- XY correlation updates under force changes,
- info panel reports live stream status.

## Live with reference validation

Command:

```bash
uv run lsl-viewer mode=live_with_reference_validation
```

Use this mode when:

- validating RS485/reference chain before calibration,
- checking reference stream timing/sample-rate behavior,
- diagnosing a frozen or delayed reference plot.

## CSV replay mode

Command:

```bash
uv run lsl-viewer mode=csv_replay \
  reference.target_csv_path=./data/target_handgrip_samples_v2.csv \
  reference.reference_csv_path=./data/reference_rs485_samples_v2.csv
```

Expected target CSV columns are selected from config labels:

| Role | Default label |
| --- | --- |
| target clock | `device_clock_us` or timestamp candidates derived by loader |
| target raw | `target_raw_count` |
| target filtered/current | `target_filtered_units` |

Expected reference CSV columns:

| Role | Default label |
| --- | --- |
| reference clock | `reference_clock_s` |
| reference force | `reference_force_N` |

If required columns are missing, fix the CSV export, replay config, or channel labels instead of modifying plot code.

## XDF replay mode

Command:

```bash
uv run lsl-viewer mode=xdf_replay reference.xdf_path=./data/session.xdf
```

Dependency:

```text
pyxdf
```

If `pyxdf` is not installed, the loader exits with an explicit error. Install through the project-supported dependency workflow rather than ad-hoc site-package edits.

Expected XDF streams:

| Stream | Expected role |
| --- | --- |
| `HandgripTarget` | target stream with target channel labels. |
| `HandgripReference` | reference stream with reference channel labels. |

## Replay controls

Config:

```yaml
replay:
  speed: 1.0
  loop: false
  start_offset_s: 0.0
```

| Key | Effect |
| --- | --- |
| `speed` | Playback speed multiplier. |
| `loop` | Restart at end of data. |
| `start_offset_s` | Begin replay after this offset. |

## Calibration marker overlays

Replay/analysis can optionally draw calibration markers from events NDJSON:

```yaml
calibration_markers:
  enabled: true
  events_ndjson_path: ../Handgrip_Calibration/data/calibration/<session_id>/events.ndjson
```

Marker overlays are visual aids. They do not change replay data.

## Mode selection checklist

| Need | Use mode |
| --- | --- |
| Live pre-calibration signal check | `live` |
| Reference timing/quality check | `live_with_reference_validation` |
| Inspect bridge CSVs | `csv_replay` |
| Inspect XDF recording | `xdf_replay` |
| Debug XY lag from a saved session | `csv_replay` or `xdf_replay` |

## Tests that guard mode behavior

| Test file | Coverage |
| --- | --- |
| `tests/e2e/test_cli.py` | Hydra help, invalid mode errors, missing replay paths. |
| `tests/integration/test_csv_replay.py` | CSV replay loading and validation. |
| `tests/unit/test_replay_loaders.py` | Replay timebase/window helper behavior. |
