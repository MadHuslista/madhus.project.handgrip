# LSL Viewer Quickstart

## Summary

- Use this workflow to start `LSL_Viewer` and confirm the expected live plots.
- Start `RS485_GUI` and `LSL_Bridge` first when using live mode.
- The viewer should show target/reference time-series plots, timing diagnostics, and XY correlation.
- Stop before calibration if streams are missing, frozen, obviously misaligned, or if XY delay grows over time.

## Prerequisites

- `RS485_GUI` can read the acquisition board and publish `rs485.measurement.v1`.
- `LSL_Bridge` can publish `HandgripTarget` and `HandgripReference`.
- Firmware emits current D2 target frames.
- `LSL_Viewer/conf/config.yaml` stream names match the bridge outputs.

## Commands

### Default live viewer

From `LSL_Viewer/`:

```bash
cd LSL_Viewer
uv run lsl-viewer
```

Equivalent explicit mode:

```bash
uv run lsl-viewer mode=live
```

### Live with reference validation

```bash
uv run lsl-viewer mode=live_with_reference_validation
```

Use this when you want additional reference-chain validation in the UI.

### Override server host/port

```bash
uv run lsl-viewer viewer.server.host=127.0.0.1 viewer.server.port=8765
```

### Open without browser auto-show

```bash
uv run lsl-viewer viewer.server.show=false
```

## Expected result

A NiceGUI browser UI opens, normally at:

```text
http://127.0.0.1:8765
```

Expected panels / behavior:

| UI element | Expected behavior |
| --- | --- |
| Info panel | Shows mode, stream status, latest values, timing/diagnostic summary. |
| Target raw plot | Updates when force is applied to the target handgrip. |
| Target filtered/current units plot | Shows firmware/bridge filtered or current engineering value when available. |
| Reference plot | Updates from PM58/acquisition-board reference force. |
| Overlay / timing panels | Help compare target/reference timing and force behavior. |
| XY correlation | Shows relationship between reference force and selected target signal. |
| Clear control | Clears plots and resets post-clear display state. |
| Pause control | Pauses/resumes live or replay rendering. |
| XY lock control | Toggles adaptive axis behavior vs lock-largest-span behavior. |

## Where outputs/logs appear

| Output | Default / source |
| --- | --- |
| Browser UI | `viewer.server.host` + `viewer.server.port`, default `127.0.0.1:8765`. |
| Viewer log | `logging.log_file`, default `handgrip_realtime_viewer.log`. |
| LSL inputs | Live LSL network streams from `LSL_Bridge`. |
| Replay inputs | Paths under `reference.target_csv_path`, `reference.reference_csv_path`, or `reference.xdf_path`. |

The viewer generally does not create scientific source data. It displays live/replay data and writes diagnostic logs.

## Stop conditions

Stop before calibration if:

- `HandgripTarget` is missing,
- `HandgripReference` is missing,
- one stream is frozen while the other responds,
- reference force changes but target raw count does not,
- target raw count changes but reference force does not,
- XY correlation delay grows over time in `raw_lsl` mode,
- viewer logs repeated stream-resolution or channel-label errors,
- calibration preflight would fail stream discovery.

## Troubleshooting links

- [`xy-correlation.md`](xy-correlation.md)
- [`configuration.md`](configuration.md)
- [`live-csv-xdf-modes.md`](live-csv-xdf-modes.md)
- [`../../docs/architecture/timestamping-and-synchronization.md`](../../docs/architecture/timestamping-and-synchronization.md)
- [`../../docs/workflows/full-live-viewer-quickstart.md`](../../docs/workflows/full-live-viewer-quickstart.md)
