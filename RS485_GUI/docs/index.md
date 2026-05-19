# RS485 GUI Documentation

## Summary

- `RS485_GUI` owns the PM58/acquisition-board host acquisition path.
- It connects to the acquisition board over RS485, displays reference measurements in a browser UI, logs raw/interpreted data, and publishes normalized measurements over ZeroMQ IPC.
- `LSL_Bridge` consumes its IPC output and publishes the `HandgripReference` LSL stream.
- Start this component before `LSL_Bridge` in the full live workflow.

## Documentation map

| Document                                               | Purpose                                                          |
| ------------------------------------------------------ | ---------------------------------------------------------------- |
| [workflow.md](workflow.md)                             | Connect to the acquisition board, validate UI/log/IPC output     |
| [configuration.md](configuration.md)                   | Full `config/config.yaml` reference                              |
| [active-send-and-modbus.md](active-send-and-modbus.md) | Modbus RTU polling vs Active-Send                                |
| [ipc-schema.md](ipc-schema.md)                         | ZMQ topics, measurement payload, event payload                   |
| [logging-and-outputs.md](logging-and-outputs.md)       | Log files, output paths, overwrite/append behavior               |
| [architecture.md](architecture.md)                     | Core/transport/io/ui/config layers and runtime dataflow          |
| [development.md](development.md)                       | How to add parser fields, UI controls, logger outputs, and tests |

## Reading guide

- To start the GUI and validate reference data: [RS485_GUI/docs/workflow.md](workflow.md)
- To edit serial or device configuration: [RS485_GUI/docs/configuration.md](configuration.md)
- To understand Active-Send vs Modbus: [RS485_GUI/docs/active-send-and-modbus.md](active-send-and-modbus.md)
- To understand the IPC output format: [RS485_GUI/docs/ipc-schema.md](ipc-schema.md)
- To understand the codebase: [RS485_GUI/docs/architecture.md](architecture.md)

## Related docs

- [docs/workflows/reference-only-quickstart.md](../../docs/workflows/reference-only-quickstart.md) — validate the reference chain alone
- [docs/hardware/pm58-wiring-and-bringup.md](../../docs/hardware/pm58-wiring-and-bringup.md) — PM58 wiring and board bring-up
- [docs/hardware/acquisition-board-reference.md](../../docs/hardware/acquisition-board-reference.md) — full acquisition-board menu reference
- [docs/troubleshooting/serial-and-rs485.md](../../docs/troubleshooting/serial-and-rs485.md)
## Minimal workflow

```bash
cd RS485_GUI
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
``` 

Expected result:

- NiceGUI browser UI opens
- Acquisition-board can be connected successfully and measurements update when force changes.
- `RS485_GUI/logs/` receives configured logs.
- IPC publisher binds to `tcp://127.0.0.1:5557` when acquisition starts.
- `LSL_Bridge` can consume `rs485.measurement.v1` and publish `HandgripReference`.

