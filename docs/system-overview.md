# System Overview — Handgrip Suite

## Summary

- The Handgrip Suite has two measurement chains: a **target chain** based on Arduino/HX711 and a **reference chain** based on PM58 + acquisition board + RS485.
- `RS485_GUI` acquires reference-board data and publishes it over ZeroMQ IPC.
- `LSL_Bridge` publishes the canonical LSL streams: `HandgripTarget` and `HandgripReference`.
- `LSL_Viewer`, `Handgrip_Calibration`, and `Handgrip_Analysis` consume live or recorded data for inspection, calibration, and offline analysis.
- Configuration is distributed by component; the root documentation map explains where each config lives.
- Canonical docs describe current workflows. Archive/reference docs preserve historical or source material and should not override canonical workflows.

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

The target and reference chains should experience the same mechanical force path during calibration. The planned force-fixture documentation should use these images once committed:

- `docs/hardware/assets/pm58_n_handgrip_setup.jpg`
- `docs/hardware/assets/acq_board_n_pm58_n_handgrip_setup.jpg`
- `docs/hardware/assets/force_application_setup.jpg`

## Software processes

| Process / command                               | Component              | Main input                      | Main output                                     |             Start order |
| ----------------------------------------------- | ---------------------- | ------------------------------- | ----------------------------------------------- | ----------------------: |
| `uv run rs485-gui`                              | `RS485_GUI`            | Acquisition board through RS485 | GUI plots, logs, ZeroMQ IPC messages            |                       1 |
| `uv run lsl-bridge`                             | `LSL_Bridge`           | Arduino serial + RS485 GUI IPC  | LSL streams and optional CSV logs               |                       2 |
| `uv run lsl-viewer`                             | `LSL_Viewer`           | LSL streams or replay files     | Browser visualization                           |                       3 |
| `uv run handgrip-cal ...`                       | `Handgrip_Calibration` | LSL streams / recorded sessions | Calibration datasets, fit results, reports      |                       4 |
| `uv run ha-stage ...` / `uv run ha-run-all ...` | `Handgrip_Analysis`    | CSV inputs and manifests        | Analysis reports, plots, filter recommendations | Offline / after capture |

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

| Contract                                                                                                   | Producer               | Consumer                             | Why it matters                                                     |
| ---------------------------------------------------------------------------------------------------------- | ---------------------- | ------------------------------------ | ------------------------------------------------------------------ |
| `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`                                             | `Handgrip_Firmware`    | `LSL_Bridge`                         | Exact firmware data-frame schema for target samples.               |
| `M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>` | `Handgrip_Firmware`    | `LSL_Bridge`, session metadata       | Firmware metadata for reproducibility.                             |
| `rs485.measurement.v1`                                                                                     | `RS485_GUI`            | `LSL_Bridge`                         | IPC topic carrying reference-board measurements.                   |
| `HandgripTarget`                                                                                           | `LSL_Bridge`           | `LSL_Viewer`, `Handgrip_Calibration` | Canonical target LSL stream.                                       |
| `HandgripReference`                                                                                        | `LSL_Bridge`           | `LSL_Viewer`, `Handgrip_Calibration` | Canonical reference LSL stream.                                    |
| `HandgripComponentEvents`                                                                                  | `LSL_Bridge`           | Diagnostics / recordings             | Operational markers for gaps, reconnects, and component events.    |
| Calibration session directory                                                                              | `Handgrip_Calibration` | Fit/report/analysis workflows        | Reproducible container for raw data, events, configs, and reports. |

Detailed stream definitions belong in [`architecture/stream-contracts.md`](architecture/stream-contracts.md) and [`LSL_Bridge/docs/stream-contracts.md`](../LSL_Bridge/docs/stream-contracts.md).

## Output locations

| Component              | Common output location                                                   | Output type                                                               |
| ---------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| `RS485_GUI`            | `RS485_GUI/logs/` or configured logger paths                             | Raw/interpreted/event logs, CSV, NDJSON                                   |
| `LSL_Bridge`           | `LSL_Bridge/logs/`, configured CSV paths                                 | Target/reference CSVs, bridge logs                                        |
| `LSL_Viewer`           | Usually display-only; replay paths configured under `conf/config.yaml`   | Browser UI, replay visualization                                          |
| `Handgrip_Calibration` | `Handgrip_Calibration/data/calibration/<session_id>/`                    | `target.csv`, `reference.csv`, events, quality logs, fit outputs, reports |
| `Handgrip_Analysis`    | `Handgrip_Analysis/data/analysis_results/`, `Handgrip_Analysis/outputs/` | Stage reports, figures, metrics, filter recommendations                   |

Generated outputs are not canonical documentation unless curated under [`examples/`](examples/).

## Where configs live

| Component      | Main config source                                              | Detailed docs                                                                                    |
| -------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Root workspace | `pyproject.toml`, `platformio.ini`                              | [`development/workspace-setup.md`](development/workspace-setup.md)                               |
| Firmware       | `Handgrip_Firmware/Core/Inc/config.h`, `platformio.ini`         | [`Handgrip_Firmware/docs/configuration.md`](../Handgrip_Firmware/docs/configuration.md)       |
| RS485 GUI      | `RS485_GUI/config/config.yaml`                                  | [`RS485_GUI/docs/configuration.md`](../RS485_GUI/docs/configuration.md)                       |
| LSL Bridge     | `LSL_Bridge/conf/config.yaml`, `LSL_Bridge/conf/logging/*.yaml` | [`LSL_Bridge/docs/configuration.md`](../LSL_Bridge/docs/configuration.md)                     |
| LSL Viewer     | `LSL_Viewer/conf/config.yaml`                                   | [`LSL_Viewer/docs/configuration.md`](../LSL_Viewer/docs/configuration.md)                     |
| Calibration    | `Handgrip_Calibration/conf/*.yaml`                              | [`Handgrip_Calibration/docs/configuration.md`](../Handgrip_Calibration/docs/configuration.md) |
| Analysis       | `Handgrip_Analysis/conf/**/*.yaml`                              | [`Handgrip_Analysis/docs/configuration.md`](../Handgrip_Analysis/docs/configuration.md)       |

## Next steps for readers

| Goal                              | Next document                                                                                      |
| --------------------------------- | -------------------------------------------------------------------------------------------------- |
| I need a friendly conceptual path | [`start-here.md`](start-here.md)                                                                   |
| I need to run hardware            | [`workflows/physical-setup.md`](workflows/physical-setup.md)                                       |
| I need to start apps              | [`workflows/full-live-viewer-quickstart.md`](workflows/full-live-viewer-quickstart.md)             |
| I need to calibrate               | [`workflows/handgrip-calibration.md`](workflows/handgrip-calibration.md)                           |
| I need to analyze data            | [`workflows/handgrip-analysis.md`](workflows/handgrip-analysis.md)                                 |
| I need to modify code             | [`development/python-project-structure-primer.md`](development/python-project-structure-primer.md) |
