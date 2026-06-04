# LSL Viewer Workflow

## Summary

This document covers starting `LSL_Viewer` in live, CSV replay, and XDF replay modes, and validating expected display behavior.

Start `RS485_GUI` and `LSL_Bridge` first when using live mode. Stop before calibration if streams are missing, frozen, or if XY delay grows over time.

## Prerequisites

- `RS485_GUI` can read the acquisition board and publish `rs485.measurement.v1`.
- `LSL_Bridge` can publish `HandgripTarget` and `HandgripReference`.
- Firmware emits current `D2` target frames.
- `LSL_Viewer/conf/config.yaml` stream names match the bridge outputs.

## Live mode

```bash
cd LSL_Viewer
uv run lsl-viewer
```

Or explicitly:

```bash
uv run lsl-viewer mode=live
```

With reference validation:

```bash
uv run lsl-viewer mode=live_with_reference_validation
```

A NiceGUI browser UI opens at `http://127.0.0.1:8765` by default. Expected panels:

| UI element              | Expected behavior                                            |
| ----------------------- | ------------------------------------------------------------ |
| Target raw plot         | Updates when force is applied to the target handgrip         |
| Reference plot          | Updates from PM58/acquisition-board reference force          |
| XY correlation          | Shows relationship between reference force and target signal |
| Timing / overlay panels | Compare target/reference timing                              |

## CSV replay mode

To replay saved CSV files without live streams:

```bash
cd LSL_Viewer
uv run lsl-viewer mode=csv_replay \
  reference.target_csv_path=../LSL_Bridge/data/target_handgrip_samples_v2.csv \
  reference.reference_csv_path=../LSL_Bridge/data/reference_rs485_samples_v2.csv
```

See [LSL_Viewer/docs/live-csv-xdf-modes.md](live-csv-xdf-modes.md) for full replay options.

## XDF replay mode

```bash
cd LSL_Viewer
uv run lsl-viewer mode=xdf_replay reference.xdf_path=path/to/recording.xdf
```

## Configuration overrides

```bash
# Different server port
uv run lsl-viewer viewer.server.port=8090

# No auto-open browser
uv run lsl-viewer viewer.server.show=false
```

See [LSL_Viewer/docs/configuration.md](configuration.md).

## Output locations

| Output     | Default                                                           |
| ---------- | ----------------------------------------------------------------- |
| Browser UI | `http://127.0.0.1:8765`                                           |
| Viewer log | `handgrip_realtime_viewer.log` (controlled by `logging.log_file`) |

## Troubleshooting links

- [LSL_Viewer/docs/xy-correlation.md](xy-correlation.md)
- [LSL_Viewer/docs/configuration.md](configuration.md)
- [LSL_Viewer/docs/live-csv-xdf-modes.md](live-csv-xdf-modes.md)
- [docs/architecture/timestamping-and-synchronization.md](../../docs/architecture/timestamping-and-synchronization.md)
- [docs/troubleshooting/viewer-lag-or-xy-delay.md](../../docs/troubleshooting/viewer-lag-or-xy-delay.md)
