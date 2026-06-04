# RS485 GUI Documentation

## Summary

- `RS485_GUI` owns the PM58/acquisition-board host acquisition path.
- It connects to the acquisition board over RS485, displays reference measurements in a browser UI, logs raw/interpreted data, and publishes normalized measurements over ZeroMQ IPC.
- `LSL_Bridge` consumes its IPC output and publishes the `HandgripReference` LSL stream.
- Start this component before `LSL_Bridge` in the full live workflow.

## Reading guide

| I want to…                                        | Read                                                                  |
| ------------------------------------------------- | --------------------------------------------------------------------- |
| Start the GUI and validate reference data         | [RS485_GUI/docs/workflow.md](workflow.md)                             |
| Edit serial or device configuration               | [RS485_GUI/docs/configuration.md](configuration.md)                   |
| Understand Active-Send vs Modbus                  | [RS485_GUI/docs/active-send-and-modbus.md](active-send-and-modbus.md) |
| Understand the IPC output format                  | [RS485_GUI/docs/ipc-schema.md](ipc-schema.md)                         |
| Understand log files and output paths             | [RS485_GUI/docs/logging-and-outputs.md](logging-and-outputs.md)       |
| Understand core/transport/io/ui internals         | [RS485_GUI/docs/architecture.md](architecture.md)                     |
| Add parser fields, UI controls, or logger outputs | [RS485_GUI/docs/development.md](development.md)                       |

## Related docs

- [docs/workflows/reference-only-quickstart.md](../../docs/workflows/reference-only-quickstart.md) — validate the reference chain alone
- [docs/hardware/pm58-wiring-and-bringup.md](../../docs/hardware/pm58-wiring-and-bringup.md) — PM58 wiring and board bring-up
- [docs/hardware/acquisition-board-reference.md](../../docs/hardware/acquisition-board-reference.md) — full acquisition-board menu reference
- [docs/troubleshooting/serial-and-rs485.md](../../docs/troubleshooting/serial-and-rs485.md)
