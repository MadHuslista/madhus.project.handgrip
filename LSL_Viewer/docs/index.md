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

## Documentation map

| Document                                       | Purpose                                                                    |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| [LSL_Viewer/docs/workflow.md](workflow.md)                     | Live, CSV replay, and XDF replay modes; expected display behavior          |
| [LSL_Viewer/docs/configuration.md](configuration.md)           | Full config reference: mode, stream names, replay paths, server, rendering |
| [LSL_Viewer/docs/live-csv-xdf-modes.md](live-csv-xdf-modes.md) | Mode details and replay-specific behavior                                  |
| [LSL_Viewer/docs/xy-correlation.md](xy-correlation.md)         | XY correlation panel interpretation and axis-lock behavior                 |
| [LSL_Viewer/docs/architecture.md](architecture.md)             | Core/viz layers and runtime dataflow                                       |
| [LSL_Viewer/docs/development.md](development.md)               | How to add panels, charts, modes, and tests                                |

## Reading guide

- To start the viewer in any mode: [LSL_Viewer/docs/workflow.md](workflow.md)
- To configure stream names or replay paths: [LSL_Viewer/docs/configuration.md](configuration.md)
- To understand XY correlation behavior: [LSL_Viewer/docs/xy-correlation.md](xy-correlation.md)
- To understand the codebase: [LSL_Viewer/docs/architecture.md](architecture.md)

## Related docs

- [docs/workflows/full-live-viewer-quickstart.md](../../docs/workflows/full-live-viewer-quickstart.md) — multi-component live viewer workflow
- [docs/architecture/timestamping-and-synchronization.md](../../docs/architecture/timestamping-and-synchronization.md)
- [docs/troubleshooting/viewer-lag-or-xy-delay.md](../../docs/troubleshooting/viewer-lag-or-xy-delay.md)
