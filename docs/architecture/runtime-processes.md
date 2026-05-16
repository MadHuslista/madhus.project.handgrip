# Runtime Processes

**Status:** Canonical root architecture document  
**Audience:** Operators and maintainers  
**Scope:** Which processes run during each workflow and in what order  
**Related docs:** [`docs/workflows/full-live-viewer-quickstart.md`](../workflows/full-live-viewer-quickstart.md), [`docs/architecture/dataflow.md`](dataflow.md)

## Summary

- A full live workflow normally runs three host-side processes: `RS485_GUI`, `LSL_Bridge`, and `LSL_Viewer`.
- Calibration adds a fourth short-lived CLI process: `handgrip-cal`.
- Offline analysis is separate from live acquisition and uses `Handgrip_Analysis` commands on saved files/manifests.
- Process start order matters because downstream components expect upstream data sources to exist.

## Full live process chain

```text
Terminal 1: RS485_GUI
  └── reads acquisition board and publishes rs485.measurement.v1

Terminal 2: LSL_Bridge
  ├── reads Arduino firmware UART
  ├── subscribes to RS485_GUI IPC
  └── publishes LSL streams

Terminal 3: LSL_Viewer
  └── discovers LSL streams and renders browser plots
```

Recommended start order:

1. `RS485_GUI`
2. `LSL_Bridge`
3. `LSL_Viewer`

Why this order:

- `RS485_GUI` must be publishing before `LSL_Bridge` can build the reference stream.
- `LSL_Bridge` must be publishing before `LSL_Viewer` can discover streams.
- Starting the viewer early is safe, but it will show missing-stream states until outlets appear.

## Calibration process chain

```text
Terminal 1: RS485_GUI
Terminal 2: LSL_Bridge
Terminal 3: optional LSL_Viewer
Terminal 4: handgrip-cal preflight / record / fit / report
```

Calibration commands are usually run from the `Handgrip_Calibration/` directory so relative protocol/config paths and component-config snapshots behave as documented.

## Offline analysis process chain

```text
Handgrip_Analysis CLI
  ├── reads manifests / CSVs / prior outputs
  ├── runs one or more stages
  └── writes reports, metrics, figures, and recommendations
```

Offline analysis does not require live LSL streams unless a specific future stage says so.

## Process ownership table

| Process             | Command                   | Inputs                                | Outputs                                          | Stop condition                                    |
| ------------------- | ------------------------- | ------------------------------------- | ------------------------------------------------ | ------------------------------------------------- |
| `RS485_GUI`         | `uv run rs485-gui`        | RS485 serial adapter and board config | GUI, logs, ZMQ IPC                               | Reference values visible or expected error shown. |
| `LSL_Bridge`        | `uv run lsl-bridge`       | Arduino UART and RS485 IPC            | LSL target/reference streams, optional CSVs/logs | Streams visible and parser health OK.             |
| `LSL_Viewer`        | `uv run lsl-viewer`       | LSL streams or replay files           | Browser UI                                       | Target/reference traces visible.                  |
| `handgrip-cal`      | `uv run handgrip-cal ...` | LSL streams or session folder         | Calibration session, fit, report                 | Requested subcommand completes.                   |
| `Handgrip_Analysis` | component CLI commands    | Manifest/CSV/session data             | Analysis output folders                          | Stage reports and metrics generated.              |

## Common runtime failure modes

| Symptom                                   | Likely owner                             | Start here                                                                                 |
| ----------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------ |
| No `/dev/ttyUSB*` appears                 | OS/adapter/cable                         | [`docs/troubleshooting/serial-and-rs485.md`](../troubleshooting/serial-and-rs485.md)       |
| Board display reacts but GUI does not     | RS485 wiring or board communication menu | [`docs/workflows/reference-only-quickstart.md`](../workflows/reference-only-quickstart.md) |
| Firmware serial monitor shows no D2 lines | Firmware/upload/HX711 wiring             | [`docs/workflows/firmware-setup.md`](../workflows/firmware-setup.md)                       |
| Viewer cannot find streams                | Bridge not running or wrong stream names | [`docs/troubleshooting/lsl-streams.md`](../troubleshooting/lsl-streams.md)                 |
| Calibration preflight fails               | Missing LSL stream or wrong config       | [`docs/workflows/handgrip-calibration.md`](../workflows/handgrip-calibration.md)           |

## Validation checklist

- [ ] `RS485_GUI` can run alone and show reference data.
- [ ] `LSL_Bridge` can run with target-only mode or with both target/reference paths.
- [ ] `LSL_Viewer` discovers stream names from [`docs/architecture/stream-contracts.md`](stream-contracts.md).
- [ ] `handgrip-cal preflight` passes before `record`.
- [ ] Analysis commands run on saved files without live hardware.
