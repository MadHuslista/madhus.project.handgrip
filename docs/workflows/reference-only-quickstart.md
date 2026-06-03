# Reference-Only Quickstart

## Summary

Use this workflow to validate the reference chain independently. The expected endpoint is live reference values in `RS485_GUI` and IPC publication to `rs485.measurement.v1`.

## Prerequisites

- PM58 wired to acquisition board.
- Acquisition board display reacts to force.
- USB-RS485 adapter connected and serial port identified.
- Board communication settings match `RS485_GUI/config/config.yaml`.

## Commands

From `RS485_GUI/`:

```bash
cd RS485_GUI
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
```

Replace `/dev/ttyUSB_RS485` with the USB-RS485 adapter path.

After GUI opens, click "Connect" to start acquisition and IPC publishing.   

## Expected result

- GUI opens in the browser.
- Reference value updates when force changes.
- Logs show valid measurement frames.
- IPC publisher is active on the configured endpoint/topic.

## Related docs

- [docs/workflows/physical-setup.md](physical-setup.md)
- [docs/hardware/pm58-wiring-and-bringup.md](../hardware/pm58-wiring-and-bringup.md)

## Troubleshooting links

- [RS485_GUI/docs/active-send-and-modbus.md](../../RS485_GUI/docs/active-send-and-modbus.md)
- [docs/troubleshooting/serial-and-rs485.md](../troubleshooting/serial-and-rs485.md)
