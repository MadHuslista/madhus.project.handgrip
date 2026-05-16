# RS485 GUI Documentation

## Summary

- `RS485_GUI` owns the PM58/acquisition-board host acquisition path.
- It connects to the high-speed acquisition board over RS485, displays reference measurements in a NiceGUI browser UI, logs raw/interpreted data, and publishes normalized reference measurements over ZeroMQ IPC.
- `LSL_Bridge` consumes its IPC output and publishes the canonical `HandgripReference` Lab Streaming Layer (LSL) stream.
- Operators should start this component before `LSL_Bridge` in the full live workflow.
- Maintainers should treat `RS485_GUI/config/config.yaml` as the component configuration source of truth.

## Audience

| Reader | Use this page to... |
| --- | --- |
| Operator | Find the minimal workflow for connecting the reference acquisition board and validating live reference data. |
| Calibration operator | Confirm the GUI is publishing `rs485.measurement.v1` before running `handgrip-cal preflight` or `record`. |
| Student maintainer | Find configuration, IPC, logging, and architecture references before editing code. |
| Developer | Understand where to add parser fields, UI controls, logger outputs, and tests. |

## Component contract

| Contract | Value |
| --- | --- |
| Component | `RS485_GUI` |
| Primary command | `uv run rs485-gui` |
| Main config | `RS485_GUI/config/config.yaml` |
| Reference acquisition modes | `active_send`, `modbus_rtu` |
| IPC topic | `rs485.measurement.v1` |
| IPC event topic | `rs485.event.v1` |
| Recommended published signal | `net_value` as `reference_force_N` |
| Downstream consumer | `LSL_Bridge` |
| Root contract doc | `../../docs/architecture/stream-contracts.md` |

## Documentation map

| Document | Purpose |
| --- | --- |
| [`quickstart.md`](quickstart.md) | Run the GUI, connect to the acquisition board, and validate UI/log/IPC output. |
| [`configuration.md`](configuration.md) | Full `config/config.yaml` reference: session, UI, logger, IPC, serial, device, Active-Send, logging. |
| [`active-send-and-modbus.md`](active-send-and-modbus.md) | Explain Modbus RTU polling vs vendor Active-Send in this board/app. |
| [`ipc-schema.md`](ipc-schema.md) | ZMQ topics, measurement payload, event payload, aliases, session IDs, and LSL bridge expectations. |
| [`logging-and-outputs.md`](logging-and-outputs.md) | NDJSON/CSV/event logs, debug logs, output paths, retention, and overwrite/append behavior. |
| [`architecture.md`](architecture.md) | Core/transport/io/ui/config layers and runtime dataflow. |
| [`development.md`](development.md) | How to add parser fields, UI controls, logger outputs, and tests. |

## Related system docs

| System doc | Why it matters |
| --- | --- |
| [`../../docs/workflows/reference-only-quickstart.md`](../../docs/workflows/reference-only-quickstart.md) | Root operator workflow for validating the reference chain alone. |
| [`../../docs/workflows/full-live-viewer-quickstart.md`](../../docs/workflows/full-live-viewer-quickstart.md) | Start order for GUI → bridge → viewer. |
| [`../../docs/hardware/pm58-wiring-and-bringup.md`](../../docs/hardware/pm58-wiring-and-bringup.md) | PM58 wiring, board power, and RS485 bring-up. |
| [`../../docs/hardware/acquisition-board-reference.md`](../../docs/hardware/acquisition-board-reference.md) | Full acquisition-board menu/reference fallback. |
| [`../../docs/architecture/dataflow.md`](../../docs/architecture/dataflow.md) | End-to-end data path from PM58 to `HandgripReference`. |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Root IPC/LSL stream contract. |
| [`../../docs/troubleshooting/serial-and-rs485.md`](../../docs/troubleshooting/serial-and-rs485.md) | Symptom-first serial/RS485 troubleshooting. |

## Minimal workflow

```bash
cd RS485_GUI
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
```

Expected result:

- NiceGUI browser UI opens.
- Acquisition-board measurements update when force changes.
- `RS485_GUI/logs/` receives configured logs.
- IPC publisher binds to `tcp://127.0.0.1:5557` when acquisition starts.
- `LSL_Bridge` can consume `rs485.measurement.v1` and publish `HandgripReference`.

## Validation checklist

- [ ] `RS485_GUI/README.md` links to this component docs index.
- [ ] `quickstart.md` can be followed by an operator without reading source code.
- [ ] `configuration.md` documents each top-level config section.
- [ ] `ipc-schema.md` preserves `rs485.measurement.v1`, `reference_force_N`, `reference_clock_s`, `reference_status`, `board_profile`, and `session_id`.
- [ ] `logging-and-outputs.md` explains `raw_signal.ndjson`, `interpreted_signal.ndjson`, `gui_signal.csv`, `event.log`, and `acquisition_debug.log`.
- [ ] `architecture.md` keeps the source layers clear: `core`, `transport`, `io`, `ui`, `config`, `worker`, `app`.
- [ ] `development.md` explains which tests to update when adding parser fields, UI controls, or logger outputs.
