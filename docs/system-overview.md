# System Overview — Handgrip Suite

## What the suite does

The Handgrip Suite measures handgrip force by comparing a target handgrip sensor against a PM58 reference load cell. It answers two questions:

- **Calibration:** how do I map target raw ADC counts to reference force in Newtons?
- **Analysis:** what are the signal quality, drift, noise, and dynamics, and which filter parameters should be used in production?

The suite has two physical measurement paths:

- **Target path:** Arduino Nano + HX711 load-cell ADC, emitting serial data to `LSL_Bridge`.
- **Reference path:** PM58 load cell → acquisition board → RS485 → `RS485_GUI` → ZeroMQ IPC → `LSL_Bridge`.

The normal live workflow starts the reference acquisition app first, then the LSL bridge, then the viewer.

## Physical chain

```text
Target handgrip sensor path
  Handgrip sensor(s)
    → HX711 load-cell ADC
    → Arduino Nano running Handgrip_Firmware
    → USB serial to host PC
    → LSL_Bridge target input
    → LSL stream: HandgripTarget

Reference force path
  PM58 reference load cell
    → High-speed acquisition board sensor input
    → RS485 output
    → USB-RS485 adapter
    → RS485_GUI on host PC
    → ZeroMQ IPC topic: rs485.measurement.v1
    → LSL_Bridge reference input
    → LSL stream: HandgripReference
```

During calibration the target and reference chains must experience the same mechanical force path. See [docs/hardware/force-fixture.md](hardware/force-fixture.md).

## Software processes

| Process / command                               | Component              | Main input                      | Main output                              | Start order |
| ----------------------------------------------- | ---------------------- | ------------------------------- | ---------------------------------------- | ----------- |
| `uv run rs485-gui`                              | `RS485_GUI`            | Acquisition board through RS485 | GUI plots, logs, ZeroMQ IPC              | 1           |
| `uv run lsl-bridge`                             | `LSL_Bridge`           | Arduino serial + RS485 GUI IPC  | LSL streams, optional CSV logs           | 2           |
| `uv run lsl-viewer`                             | `LSL_Viewer`           | LSL streams or replay files     | Browser visualization                    | 3           |
| `uv run handgrip-cal ...`                       | `Handgrip_Calibration` | LSL streams / recorded sessions | Calibration datasets, reports            | 4           |
| `uv run ha-stage ...` / `uv run ha-run-all ...` | `Handgrip_Analysis`    | CSV inputs and manifests        | Analysis reports, filter recommendations | Offline     |

## Runtime dataflow

```text
RS485_GUI
  ├── reads: /dev/ttyUSBx from acquisition board
  ├── writes: logs / CSV / NDJSON as configured
  └── publishes: ZeroMQ topic rs485.measurement.v1

Handgrip_Firmware
  └── emits: M2 metadata frames + D2 data frames over serial

LSL_Bridge
  ├── reads: target serial D2/M2 frames
  ├── reads: RS485_GUI ZeroMQ IPC messages
  ├── publishes: HandgripTarget LSL stream
  ├── publishes: HandgripReference LSL stream
  └── optionally writes: target/reference CSV logs

LSL_Viewer
  ├── reads: live LSL streams or replay files
  └── displays: time series, reference validation, XY correlation, markers

Handgrip_Calibration
  ├── reads: LSL streams during recording
  ├── writes: session CSVs, events, quality telemetry
  ├── fits: candidate calibration models
  └── writes: calibration reports and model exports

Handgrip_Analysis
  ├── reads: captured CSVs and manifests
  ├── computes: staged signal metrics and filter candidates
  └── writes: plots, reports, recommendations
```

## Stream and data contracts

| Contract                                                       | Producer               | Consumer                             |
| -------------------------------------------------------------- | ---------------------- | ------------------------------------ |
| `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>` | `Handgrip_Firmware`    | `LSL_Bridge`                         |
| `M2,<payload_schema>,<firmware_version>,...`                   | `Handgrip_Firmware`    | `LSL_Bridge`, session metadata       |
| `rs485.measurement.v1`                                         | `RS485_GUI`            | `LSL_Bridge`                         |
| `HandgripTarget`                                               | `LSL_Bridge`           | `LSL_Viewer`, `Handgrip_Calibration` |
| `HandgripReference`                                            | `LSL_Bridge`           | `LSL_Viewer`, `Handgrip_Calibration` |
| `HandgripComponentEvents`                                      | `LSL_Bridge`           | Diagnostics / recordings             |
| Calibration session directory                                  | `Handgrip_Calibration` | Fit/report/analysis workflows        |

Full stream definitions: [docs/architecture/stream-contracts.md](architecture/stream-contracts.md), [LSL_Bridge/docs/stream-contracts.md](../LSL_Bridge/docs/stream-contracts.md).

## Output locations

| Component              | Common output location                                | Output type                                    |
| ---------------------- | ----------------------------------------------------- | ---------------------------------------------- |
| `RS485_GUI`            | `RS485_GUI/logs/` or configured paths                 | Logs, CSV, NDJSON                              |
| `LSL_Bridge`           | `LSL_Bridge/logs/`, configured CSV paths              | Target/reference CSVs, bridge logs             |
| `LSL_Viewer`           | Display-only; replay paths in `conf/config.yaml`      | Browser UI                                     |
| `Handgrip_Calibration` | `Handgrip_Calibration/data/calibration/<session_id>/` | CSVs, events, fit outputs, reports             |
| `Handgrip_Analysis`    | `Handgrip_Analysis/data/analysis_results/`            | Stage reports, figures, filter recommendations |

Generated outputs are not canonical documentation unless curated under [docs/examples/](examples/).

## Where configs live

| Component   | Main config source                                      | Detailed docs                                                                               |
| ----------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Firmware    | `Handgrip_Firmware/Core/Inc/config.h`, `platformio.ini` | [Handgrip_Firmware/docs/configuration.md](../Handgrip_Firmware/docs/configuration.md)       |
| RS485 GUI   | `RS485_GUI/config/config.yaml`                          | [RS485_GUI/docs/configuration.md](../RS485_GUI/docs/configuration.md)                       |
| LSL Bridge  | `LSL_Bridge/conf/config.yaml`                           | [LSL_Bridge/docs/configuration.md](../LSL_Bridge/docs/configuration.md)                     |
| LSL Viewer  | `LSL_Viewer/conf/config.yaml`                           | [LSL_Viewer/docs/configuration.md](../LSL_Viewer/docs/configuration.md)                     |
| Calibration | `Handgrip_Calibration/conf/*.yaml`                      | [Handgrip_Calibration/docs/configuration.md](../Handgrip_Calibration/docs/configuration.md) |
| Analysis    | `Handgrip_Analysis/conf/**/*.yaml`                      | [Handgrip_Analysis/docs/configuration.md](../Handgrip_Analysis/docs/configuration.md)       |

Full configuration map: [docs/configuration/index.md](configuration/index.md).

## Where to go next

| If you want to…                     | Start here                                                                                            |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Connect hardware and wire PM58      | [docs/workflows/physical-setup.md](workflows/physical-setup.md)                                       |
| Upload firmware and validate serial | [Handgrip_Firmware/docs/workflow.md](../Handgrip_Firmware/docs/workflow.md)                           |
| Start the full live system          | [docs/workflows/full-live-viewer-quickstart.md](workflows/full-live-viewer-quickstart.md)             |
| Calibrate the handgrip              | [docs/workflows/handgrip-calibration.md](workflows/handgrip-calibration.md)                           |
| Run signal analysis                 | [docs/workflows/handgrip-analysis.md](workflows/handgrip-analysis.md)                                 |
| Understand a specific component     | Component `*/docs/index.md` files                                                                     |
| Modify or extend the code           | [docs/development/python-project-structure-primer.md](development/python-project-structure-primer.md) |
| Troubleshoot a problem              | [docs/troubleshooting/index.md](troubleshooting/index.md)                                             |
