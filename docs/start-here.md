# Start Here — Handgrip Suite

## Summary

- The Handgrip Suite is a multi-component system for measuring handgrip force, comparing a target handgrip sensor against a PM58 reference load cell, and producing calibration/analysis reports.
- The system has two physical measurement paths: a **target path** using Arduino + HX711 and a **reference path** using PM58 + acquisition board + RS485.
- The normal live workflow starts the reference acquisition app first, then the Lab Streaming Layer bridge, then the viewer.
- **Calibration** answers: “How do I map target raw counts to reference force?”
- **Analysis** answers: “What are the signal quality, drift/noise/dynamics, and best filter choices?”
- Read [`system-overview.md`](system-overview.md) after this page for the architecture-level map.

## What is the suite?

The Handgrip Suite is an end-to-end research/engineering toolkit for a force-sensing handgrip setup.

It covers:

1. **Firmware acquisition** from the target handgrip device.
2. **Reference acquisition** from the PM58 load cell through the high-speed acquisition board.
3. **Live stream publication** through Lab Streaming Layer (LSL).
4. **Live visualization** through the LSL viewer.
5. **Calibration sessions** that fit target readings to reference force.
6. **Offline analysis** for signal characterization and filter selection.

The repository is intentionally split into separate modules because each one owns a different part of the system.

## What hardware is involved?

| Hardware                       | Role                                                | Connected to                                  |
| ------------------------------ | --------------------------------------------------- | --------------------------------------------- |
| Handgrip target device         | Sensor under calibration / target stream source     | Arduino Nano + HX711 path                     |
| Arduino Nano                   | Runs `Handgrip_Firmware` and emits serial data      | Host PC over USB serial                       |
| HX711 load-cell ADC            | Reads the target handgrip load-cell signal          | Arduino Nano pins configured in firmware      |
| PM58 load cell                 | Reference force sensor                              | High-speed acquisition board sensor terminals |
| High-speed acquisition board   | Reads PM58 reference force and exposes RS485 output | Host PC through USB-RS485 adapter             |
| USB-RS485 adapter              | Physical serial bridge for reference board          | Host PC                                       |
| Host PC                        | Runs Python apps and records/visualizes data        | All software components                       |
| Optional screw press / fixture | Applies controlled force during calibration         | PM58 + handgrip mechanical setup              |

For wiring and photos, start with [`workflows/physical-setup.md`](workflows/physical-setup.md) once that workflow is created.

## Which app do I open first?

For the full live system, start processes in this order:

```text
1. RS485_GUI       → talks to the reference acquisition board
2. LSL_Bridge     → publishes target/reference LSL streams
3. LSL_Viewer     → visualizes live/replay data
4. Handgrip_Calibration or Handgrip_Analysis as needed
```

Recommended terminal order:

```bash
# Terminal 1
uv run rs485-gui

# Terminal 2
uv run lsl-bridge

# Terminal 3
uv run lsl-viewer
```

Why this order:

- `RS485_GUI` must publish reference-board data before the bridge can consume it.
- `LSL_Bridge` must publish LSL streams before the viewer or calibration module can discover them.
- `LSL_Viewer` is an observer/diagnostic tool; it should not be the first process started.

## What is calibration vs analysis?

### Calibration

Calibration is the workflow that compares target handgrip readings against the PM58 reference force chain.

Use calibration when you need to answer:

- What is the mapping from target raw counts to Newtons?
- Which fitted model should be exported?
- Are the fit residuals acceptable?
- Does an independent holdout session validate the calibration?
- Which constants or model output should be used downstream?

Primary component:

- [`Handgrip_Calibration`](../Handgrip_Calibration/README.md)

Primary planned workflow:

- [`workflows/handgrip-calibration.md`](workflows/handgrip-calibration.md)

### Analysis

Analysis is the workflow that characterizes signal quality and processing choices after data has been captured.

Use analysis when you need to answer:

- How much startup drift exists?
- What is the stationary noise profile?
- How does the signal behave under load?
- Which filter candidates preserve force dynamics while reducing noise?
- What filter recommendation should be applied to the bridge/viewer/firmware path?

Primary component:

- [`Handgrip_Analysis`](../Handgrip_Analysis/README.md)

Primary planned workflow:

- [`workflows/handgrip-analysis.md`](workflows/handgrip-analysis.md)

## Which path should I follow?

| Goal                                   | Path                                                                                                                                                        |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I only want a high-level understanding | This page → [`system-overview.md`](system-overview.md)                                                                                                      |
| I need to connect hardware             | [`workflows/physical-setup.md`](workflows/physical-setup.md) → [`hardware/index.md`](hardware/index.md)                                                     |
| I need to upload firmware              | [`workflows/firmware-setup.md`](workflows/firmware-setup.md) → [`../Handgrip_Firmware/docs/index.md`](../Handgrip_Firmware/docs/index.md)                   |
| I need to see live signals             | [`workflows/full-live-viewer-quickstart.md`](workflows/full-live-viewer-quickstart.md)                                                                      |
| I need to calibrate                    | [`workflows/handgrip-calibration.md`](workflows/handgrip-calibration.md) → [`../Handgrip_Calibration/docs/index.md`](../Handgrip_Calibration/docs/index.md) |
| I need to analyze captured data        | [`workflows/handgrip-analysis.md`](workflows/handgrip-analysis.md) → [`../Handgrip_Analysis/docs/index.md`](../Handgrip_Analysis/docs/index.md)             |
| I need to edit code                    | [`development/python-project-structure-primer.md`](development/python-project-structure-primer.md) → relevant component docs                                |
| I need to debug                        | [`troubleshooting/index.md`](troubleshooting/index.md)                                                                                                      |

## Important names to recognize

| Name                     | Meaning                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| `HandgripTarget`         | LSL stream published from target Arduino/HX711 data.                                               |
| `HandgripReference`      | LSL stream published from PM58/acquisition-board reference data.                                   |
| `RS485_GUI`              | Host app that talks to the acquisition board and publishes reference measurements over ZeroMQ IPC. |
| `LSL_Bridge`             | Host app that converts target serial + reference IPC into LSL streams.                             |
| `LSL_Viewer`             | Browser-based live/replay signal viewer.                                                           |
| `handgrip-cal`           | CLI entry point for calibration sessions.                                                          |
| `ha-stage`, `ha-run-all` | CLI entry points for offline analysis stages.                                                      |
| `D2`                     | Current target firmware serial data frame schema.                                                  |
| `M2`                     | Current target firmware serial metadata frame schema.                                              |

## Next page

Read [`system-overview.md`](system-overview.md) next.
