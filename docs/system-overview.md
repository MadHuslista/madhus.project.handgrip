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

The target path runs: Handgrip sensor → HX711 ADC → Arduino Nano firmware → USB serial → `LSL_Bridge` → `HandgripTarget` LSL stream. The reference path runs: PM58 load cell → acquisition board → RS485 → `RS485_GUI` → ZeroMQ IPC → `LSL_Bridge` → `HandgripReference` LSL stream. For the full dataflow diagram see [docs/architecture/dataflow.md](architecture/dataflow.md).

During calibration the target and reference chains must experience the same mechanical force path. See [docs/hardware/force-fixture.md](hardware/force-fixture.md).

## Software processes

| Process / command                               | Component              | Main input                      | Main output                              | Start order |
| ----------------------------------------------- | ---------------------- | ------------------------------- | ---------------------------------------- | ----------- |
| `uv run rs485-gui`                              | `RS485_GUI`            | Acquisition board through RS485 | GUI plots, logs, ZeroMQ IPC              | 1           |
| `uv run lsl-bridge`                             | `LSL_Bridge`           | Arduino serial + RS485 GUI IPC  | LSL streams, optional CSV logs           | 2           |
| `uv run lsl-viewer`                             | `LSL_Viewer`           | LSL streams or replay files     | Browser visualization                    | 3           |
| `uv run handgrip-cal ...`                       | `Handgrip_Calibration` | LSL streams / recorded sessions | Calibration datasets, reports            | 4           |
| `uv run ha-stage ...` / `uv run ha-run-all ...` | `Handgrip_Analysis`    | CSV inputs and manifests        | Analysis reports, filter recommendations | Offline     |

For end-to-end dataflow see [docs/architecture/dataflow.md](architecture/dataflow.md).

## Stream and data contracts

Contracts in this suite: firmware UART (`M2`/`D2`), RS485 IPC (`rs485.measurement.v1`), and three LSL streams (`HandgripTarget`, `HandgripReference`, `HandgripComponentEvents`). Full ownership map and authoritative definitions: [docs/architecture/stream-contracts.md](architecture/stream-contracts.md).

## Output locations

| Component              | Common output location                                | Output type                                    |
| ---------------------- | ----------------------------------------------------- | ---------------------------------------------- |
| `RS485_GUI`            | `RS485_GUI/logs/` or configured paths                 | Logs, CSV, NDJSON                              |
| `LSL_Bridge`           | `LSL_Bridge/logs/`, configured CSV paths              | Target/reference CSVs, bridge logs             |
| `LSL_Viewer`           | Display-only; replay paths in `conf/config.yaml`      | Browser UI                                     |
| `Handgrip_Calibration` | `Handgrip_Calibration/data/calibration/<session_id>/` | CSVs, events, fit outputs, reports             |
| `Handgrip_Analysis`    | `Handgrip_Analysis/data/analysis_results/`            | Stage reports, figures, filter recommendations |

Generated outputs are not canonical documentation unless curated under [docs/examples](examples/).

Full configuration map: [docs/configuration/index.md](configuration/index.md).

## Typical first-time sequence

1. Connect hardware and wire PM58. See [docs/workflows/physical-setup.md](workflows/physical-setup.md).
2. Upload firmware and validate serial output. See [Handgrip_Firmware/docs/workflow.md](../Handgrip_Firmware/docs/workflow.md).
3. Validate the reference chain. See [docs/workflows/reference-only-quickstart.md](workflows/reference-only-quickstart.md).
4. Validate the target chain. See [docs/workflows/target-only-quickstart.md](workflows/target-only-quickstart.md).
5. Start the full live viewer. See [docs/workflows/full-live-viewer-quickstart.md](workflows/full-live-viewer-quickstart.md).
6. Calibrate the handgrip. See [docs/workflows/handgrip-calibration.md](workflows/handgrip-calibration.md).
7. Run signal analysis. See [docs/workflows/handgrip-analysis.md](workflows/handgrip-analysis.md).

## Where to go next

| If you want to…                     | Start here                                                                                            |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Connect hardware and wire PM58      | [docs/workflows/physical-setup.md](workflows/physical-setup.md)                                       |
| Upload firmware and validate serial | [Handgrip_Firmware/docs/workflow.md](../Handgrip_Firmware/docs/workflow.md)                           |
| Start the full live system          | [docs/workflows/full-live-viewer-quickstart.md](workflows/full-live-viewer-quickstart.md)             |
| Calibrate the handgrip              | [docs/workflows/handgrip-calibration.md](workflows/handgrip-calibration.md)                           |
| Run signal analysis                 | [docs/workflows/handgrip-analysis.md](workflows/handgrip-analysis.md)                                 |
| Understand a specific component     | Component `*/docs/index.md` files                                                                     |
| Modify or extend the code           | Component `*/docs/development.md` files                                                               |
| Troubleshoot a problem              | [docs/troubleshooting/index.md](troubleshooting/index.md)                                             |
