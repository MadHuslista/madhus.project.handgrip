# RS485 GUI Workflow

## Summary

This document covers the complete RS485 GUI workflow: identifying the RS485 serial port, starting the GUI, validating reference-board data, and confirming ZeroMQ IPC publication for downstream consumers.

Run this workflow before the full live-viewer workflow and before calibration. Do not proceed to calibration if the acquisition-board display responds to force but the GUI receives no valid measurements.

## Prerequisites

| Requirement                  | Expected state                                                             |
| ---------------------------- | -------------------------------------------------------------------------- |
| PM58 wiring                  | PM58 wired to acquisition board sensor terminals; display reacts to force  |
| Acquisition-board power      | Board powered on and past startup state                                    |
| RS485 adapter                | USB-RS485 adapter visible on host                                          |
| Board communication settings | Board baud, parity, address, and mode match `RS485_GUI/config/config.yaml` |
| Python environment           | `uv sync` run at repo root or component root                               |

## 1 — Identify the RS485 serial port

```bash
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

Use the USB-RS485 adapter path. Confirm it is not the Arduino/HX711 target serial path.

Stable Linux path (preferred):

```bash
/dev/serial/by-id/<rs485-adapter-id>
```

## 2 — Review configuration

Before starting, confirm `RS485_GUI/config/config.yaml` has the correct:

- `serial.default_port` — matches the RS485 adapter path,
- `device.mode` — `active_send` (recommended) or `modbus_rtu` (fallback),
- `serial.default_baudrate` — `460800` for Active-Send, `9600`–`115200` for Modbus RTU.

See [RS485_GUI/docs/configuration.md](configuration.md) and [RS485_GUI/docs/active-send-and-modbus.md](active-send-and-modbus.md).

## 3 — Start the GUI

From the repository root:

```bash
cd RS485_GUI
uv run rs485-gui
```

Or with an explicit port override:

```bash
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
```

For Active-Send at 500 Hz:

```bash
uv run rs485-gui \
  serial.default_port=/dev/ttyUSB_RS485 \
  device.mode=active_send \
  serial.default_baudrate=460800
```

For Modbus RTU fallback:

```bash
uv run rs485-gui \
  serial.default_port=/dev/ttyUSB_RS485 \
  device.mode=modbus_rtu
```

## 4 — Validate reference data

Open the browser UI (default: `http://localhost:8080`).

Expected result:

- acquisition-board plot updates continuously,
- applying force to the PM58 changes the displayed value,
- log shows no repeated CRC errors or timeout messages,
- IPC publisher status shows active publication on `rs485.measurement.v1`.

Apply a small manual force to the PM58. The displayed value should change consistently and return near zero when force is released.

## 5 — Confirm ZeroMQ IPC

If `LSL_Bridge` will be started next, confirm the IPC topic is publishing:

```bash
# Optional: check IPC activity in the log
grep "ipc" RS485_GUI/logs/rs485_gui.log | tail -20
```

The bridge will subscribe to `rs485.measurement.v1`. No separate confirmation step is required if the GUI shows live data.

## Stop conditions

Stop and troubleshoot if:

- GUI opens but shows no acquisition-board data — check serial port, baud rate, A/B wiring,
- CRC errors repeat continuously — check RS485 A/B polarity and termination,
- force applied to PM58 produces no display change — check sensor terminal wiring (E+/E-/S+/S-),
- IPC status shows no messages published — check ZMQ config and port availability.

## Troubleshooting links

- [RS485_GUI/docs/active-send-and-modbus.md](active-send-and-modbus.md)
- [RS485_GUI/docs/configuration.md](configuration.md)
- [RS485_GUI/docs/ipc-schema.md](ipc-schema.md)
- [docs/hardware/pm58-wiring-and-bringup.md](../../docs/hardware/pm58-wiring-and-bringup.md)
- [docs/troubleshooting/serial-and-rs485.md](../../docs/troubleshooting/serial-and-rs485.md)
