# Handgrip Suite

- [Handgrip Suite](#handgrip-suite)
  - [Summary](#summary)
    - [System Architecture](#system-architecture)
    - [Components](#components)
  - [Quickstart](#quickstart)
    - [Firmware Workspace](#firmware-workspace)
    - [Python Workspace](#python-workspace)
    - [What to read and when](#what-to-read-and-when)
  - [Validation](#validation)
  - [Documentation map](#documentation-map)


## Summary

- **Handgrip Suite** is an end-to-end suite for acquiring, visualizing, calibrating, and analyzing handgrip force data.
- The system combines a **target handgrip device** based on Arduino Nano + HX711 load-cell acquisition with a **reference force chain** based on a PM58 load cell connected to a high-speed RS485 acquisition board.
- The host software stack is split into 5 focused components: `RS485_GUI`, `LSL_Bridge`, `LSL_Viewer`, `Handgrip_Calibration`, and `Handgrip_Analysis`.
- The documentation is organized for progressive discovery: each README provides a self-contained overview of its component, with links to more detailed workflows and references.
- This root README is intentionally short. The full documentation map starts at [docs/index.md](docs/index.md).

### System Architecture

```mermaid
flowchart TD
    Streams>"Dual Streams"]
    Hardware("PM58 Load Cell \n& Acquisition Board\n(reference)") -->|Modbus RS485| RS485_GUI(RS485 GUI)
    RS485_GUI -->|ZeroMQ IPC| Bridge(LSL_Bridge)
    FW("Handgrip_Firmware \nADC: HX711 &\nMCU: Arduino Nano\n(target)\n") -->|UART Serial| Bridge
    Bridge --> |s: HandgripReference| Streams
    Bridge ~~~ |"LSL Streams\n Sync capables"| Streams
    Bridge --> |s: HandgripTarget| Streams
    Streams -->| Live | Viewer(LSL_Viewer)
    Streams -->|Captured Data| Calibration(Handgrip_Calibration)
    Calibration -->|Calibration Data/Files| Analysis(Handgrip_Analysis)
```

### Components

Following the system architecture, here are the entry points and purposes for each module:

- [PM58 Load Cell & Acquisition Board](docs/workflows/physical-setup.md): Reference-force sensing hardware and wiring stack. 
- [RS485_GUI](RS485_GUI/docs/index.md): Control interface for reading PM58 data and streaming it to LSL_Bridge in real time. 
- [Handgrip_Firmware](Handgrip_Firmware/docs/index.md): Firmware that samples HX711 load-cell data and sends UART telemetry. 
- [LSL_Bridge](LSL_Bridge/docs/index.md): Middleware that ingests target/reference signals and publishes synchronized LSL streams.
- [LSL_Viewer](LSL_Viewer/docs/index.md): Real-time dashboard for monitoring synchronized LSL streams.
- [Handgrip_Calibration](Handgrip_Calibration/docs/index.md): Identifies the best mathematical model to map raw ADC counts to Newtons using reference-force ground truth. 
- [Handgrip_Analysis](Handgrip_Analysis/docs/index.md): DSP analysis workflow for selecting production filter parameters for LSL_Bridge.

## Quickstart

### Firmware Workspace

Install PlatformIO from: 

| Option                             | Link                                                                                                                                                           |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI Standalone                     | [https://docs.platformio.org/en/latest/core/installation/index.html](https://docs.platformio.org/en/latest/core/installation/index.html)                       |
| VSCode extension [**Recommended**] | [https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide](https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide) |

Ensure PlatformIO binaries are in your PATH: 
- [https://docs.platformio.org/en/stable/core/installation/shell-commands.html](https://docs.platformio.org/en/stable/core/installation/shell-commands.html)

Firmware is built with PlatformIO from the root `platformio.ini`
Run from the repository root:

```bash
pio run -e nanoatmega328
pio run -e nanoatmega328 -t upload
```

Validate connection and data reception with:

```bash
pio device monitor -e nanoatmega328
```
Expect to see a stream of telemetry lines with raw ADC counts and timestamps. 

Read [Handgrip_Firmware/docs/workflow.md](Handgrip_Firmware/docs/workflow.md) for the full workflow, or before uploading or changing firmware constants.

### Python Workspace

Install UV Python package manager from: 
- [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)

Run from the repository root:

```bash
uv venv .venv
source .venv/bin/activate
uv sync
```

Then run the live system in this order:

```bash
# Terminal 1 — reference acquisition board GUI / IPC publisher
uv run rs485-gui

# Terminal 2 — target/reference bridge to Lab Streaming Layer
uv run lsl-bridge

# Terminal 3 — live viewer
uv run lsl-viewer
```

This brings up the reference GUI/IPC publisher, the `HandgripTarget` and `HandgripReference` LSL streams, and the viewer UI. For the full operational path, read [docs/workflows/full-live-viewer-quickstart.md](docs/workflows/full-live-viewer-quickstart.md).

### What to read and when

| I want to…                   | Start here                                                                                     | Then                                                                                                                                                         |
| ---------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Understand the whole suite   | [docs/system-overview.md](docs/system-overview.md)                                             | [docs/workflows/handgrip-calibration.md](docs/workflows/handgrip-calibration.md), [docs/workflows/handgrip-analysis.md](docs/workflows/handgrip-analysis.md) |
| Connect hardware             | [docs/workflows/physical-setup.md](docs/workflows/physical-setup.md)                           | [Handgrip_Firmware/docs/workflow.md](Handgrip_Firmware/docs/workflow.md)                                                                                     |
| Start the full live system   | [docs/workflows/full-live-viewer-quickstart.md](docs/workflows/full-live-viewer-quickstart.md) | —                                                                                                                                                            |
| Validate target path only    | [docs/workflows/target-only-quickstart.md](docs/workflows/target-only-quickstart.md)           | —                                                                                                                                                            |
| Validate reference path only | [docs/workflows/reference-only-quickstart.md](docs/workflows/reference-only-quickstart.md)     | —                                                                                                                                                            |
| Build/upload firmware        | [Handgrip_Firmware/docs/workflow.md](Handgrip_Firmware/docs/workflow.md)                       | [Handgrip_Firmware/docs/index.md](Handgrip_Firmware/docs/index.md)                                                                                           |
| Calibrate the handgrip       | [docs/workflows/handgrip-calibration.md](docs/workflows/handgrip-calibration.md)               | [Handgrip_Calibration/docs/workflow.md](Handgrip_Calibration/docs/workflow.md)                                                                               |
| Run signal analysis          | [docs/workflows/handgrip-analysis.md](docs/workflows/handgrip-analysis.md)                     | [Handgrip_Analysis/docs/workflow.md](Handgrip_Analysis/docs/workflow.md)                                                                                     |
| Understand repo structure    | [docs/architecture/repository-layout.md](docs/architecture/repository-layout.md)               | —                                                                                                                                                            |
| Troubleshoot                 | [docs/troubleshooting/index.md](docs/troubleshooting/index.md)                                 | Component `*/docs/` links                                                                                                                                    |

## Validation

After the [Quickstart](#quickstart) install, validate the workspace from the repository root:

```bash
uv run pytest
```

The root `pyproject.toml` installs the local Python components as editable packages:

- `rs485-gui`
- `lsl-bridge`
- `lsl-viewer`
- `handgrip-calibration`
- `handgrip-analysis`

## Documentation map

The full documentation map — section tree and component entry points — starts at [docs/index.md](docs/index.md).
