# LSL Viewer Documentation

## Summary

- `LSL_Viewer` provides real-time visualization of LSL streams and replay of saved CSV/XDF files.
- It displays target/reference time series, timing diagnostics, and XY correlation.
- It does not create scientific source data. Its outputs are browser visualization and diagnostic logs.

## Component contract

| Contract                | Value                                                                |
| ----------------------- | -------------------------------------------------------------------- |
| Primary command         | `uv run lsl-viewer`                                                  |
| Main config             | `LSL_Viewer/conf/config.yaml`                                        |
| Modes                   | `live`, `live_with_reference_validation`, `csv_replay`, `xdf_replay` |
| Default browser address | `http://127.0.0.1:8765`                                              |

## Reading guide

| I want to…                                      | Read                                                           |
| ----------------------------------------------- | -------------------------------------------------------------- |
| Start the viewer in any mode                    | [LSL_Viewer/docs/workflow.md](workflow.md)                     |
| Configure stream names, replay paths, or server | [LSL_Viewer/docs/configuration.md](configuration.md)           |
| Understand mode details and replay behavior     | [LSL_Viewer/docs/live-csv-xdf-modes.md](live-csv-xdf-modes.md) |
| Interpret the XY correlation panel              | [LSL_Viewer/docs/xy-correlation.md](xy-correlation.md)         |
| Understand core/viz internals                   | [LSL_Viewer/docs/architecture.md](architecture.md)             |
| Add panels, charts, or modes                    | [LSL_Viewer/docs/development.md](development.md)               |

## Related docs

- [docs/workflows/full-live-viewer-quickstart.md](../../docs/workflows/full-live-viewer-quickstart.md) — multi-component live viewer workflow
- [docs/architecture/timestamping-and-synchronization.md](../../docs/architecture/timestamping-and-synchronization.md)
- [docs/troubleshooting/viewer-lag-or-xy-delay.md](../../docs/troubleshooting/viewer-lag-or-xy-delay.md)
