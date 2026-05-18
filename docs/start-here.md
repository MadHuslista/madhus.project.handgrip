# Start Here — Handgrip Suite

## Summary

- The Handgrip Suite is a multi-component system for measuring handgrip force, comparing a target handgrip sensor against a PM58 reference load cell, and producing calibration/analysis reports.
- The system has two physical measurement paths: a **target path** using Arduino + HX711 and a **reference path** using PM58 + acquisition board + RS485.
- The normal live workflow starts the reference acquisition app first, then the Lab Streaming Layer bridge, then the viewer.
- **Calibration** answers: “How do I map target raw counts to reference force?”
- **Analysis** answers: “What are the signal quality, drift/noise/dynamics, and best filter choices?”
- Read [`system-overview.md`](system-overview.md) after this page for the architecture-level map.

## Hardware overview

| Hardware                       | Role                                                        | Connected to                                  |
| ------------------------------ | ----------------------------------------------------------- | --------------------------------------------- |
| HX711                          | ADC used to read the target handgrip load-cell signal       | Arduino Nano ATmega328                        |
| Arduino Nano ATmega328         | Reads HX711 and runs `Handgrip_Firmware`, emits serial data | Host PC over USB serial                       |
| PM58 load cell                 | Reference force sensor                                      | High-speed acquisition board sensor terminals |
| High-speed acquisition board   | Reads PM58 reference force and exposes RS485 output         | Host PC through USB-RS485 adapter             |
| USB-RS485 adapter              | Physical serial bridge for reference board                  | Host PC                                       |

For wiring and photos, start with [`workflows/physical-setup.md`](workflows/physical-setup.md) once that workflow is created.

## Quickstart: full live viewer

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

## Calibration & Analysis overview

### Handgrip Calibration

It compares the target handgrip readings against the PM58 reference force chain, fits a calibration model, and produces a report with validation results and recommended constants/model output for downstream use. 

Primary component:

- [`Handgrip_Calibration`](../Handgrip_Calibration/README.md)

Primary planned workflow:

- [`workflows/handgrip-calibration.md`](workflows/handgrip-calibration.md)

### Handgrip Analysis

It characterizes the target handgrip signal quality, drift, noise profile, and dynamics, and recommends filter parameters to preserve dynamics while reducing noise. 
This informs the choice of filter parameters for the optional LSL Bridge path.

Primary component:

- [`Handgrip_Analysis`](../Handgrip_Analysis/README.md)

Primary planned workflow:

- [`workflows/handgrip-analysis.md`](workflows/handgrip-analysis.md)

## Which path should I follow?

| Goal                                   | Path                                                                                                                                                        |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I only want a high-level understanding | This page → [`system-overview.md`](system-overview.md)                                                                                                      |
| I need to connect hardware             | [`workflows/physical-setup.md`](workflows/physical-setup.md) → [`hardware/index.md`](hardware/index.md)                                                     |
| I need to upload firmware              | [`workflows/firmware-setup.md`](workflows/firmware-setup.md) → [`Handgrip_Firmware/docs/index.md`](../Handgrip_Firmware/docs/index.md)                   |
| I need to see live signals             | [`workflows/full-live-viewer-quickstart.md`](workflows/full-live-viewer-quickstart.md)                                                                      |
| I need to calibrate                    | [`workflows/handgrip-calibration.md`](workflows/handgrip-calibration.md) → [`Handgrip_Calibration/docs/index.md`](../Handgrip_Calibration/docs/index.md) |
| I need to analyze captured data        | [`workflows/handgrip-analysis.md`](workflows/handgrip-analysis.md) → [`Handgrip_Analysis/docs/index.md`](../Handgrip_Analysis/docs/index.md)             |
| I need to edit code                    | [`development/python-project-structure-primer.md`](development/python-project-structure-primer.md) → relevant component docs                                |
| I need to debug                        | [`troubleshooting/index.md`](troubleshooting/index.md)                                                                                                      |

## Glossary

| Name                     | Meaning                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| `HandgripTarget`         | LSL stream published from target Arduino/HX711 data.                                               |
| `HandgripReference`      | LSL stream published from PM58/acquisition-board reference data.                                   |
| `D2`                     | Current target firmware serial data frame schema.                                                  |
| `M2`                     | Current target firmware serial metadata frame schema.                                              |

## Next page

Read [`system-overview.md`](system-overview.md) next.
