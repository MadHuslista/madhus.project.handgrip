# RS485 GUI Quickstart

## Summary

- This workflow validates the PM58/acquisition-board reference chain through `RS485_GUI`.
- The expected endpoint is live reference data in the browser UI, configured logs on disk, and ZeroMQ IPC publication for `LSL_Bridge`.
- Run this before the full live-viewer workflow and before calibration.
- Do not continue to calibration if the acquisition-board display changes but the GUI receives no valid measurements.

## Prerequisites

| Requirement | Expected state |
| --- | --- |
| PM58 wiring | PM58 is wired to the acquisition board sensor terminals and the board display reacts to force. |
| Acquisition-board power | Board powers on safely and exits startup state. |
| RS485 adapter | USB-RS485 adapter appears on the host, preferably under `/dev/serial/by-id/`. |
| Board communication settings | Board baud/parity/address/mode match `RS485_GUI/config/config.yaml`. |
| Python environment | `uv sync` has been run at the repo root or component root. |
| Port ownership | The Arduino target serial port is not selected by the GUI. Use `serial.excluded_ports` if needed. |

## Commands

### 1. Identify candidate serial ports

```bash
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

Use the USB-RS485 adapter path, not the Arduino/HX711 target serial path.

### 2. Run the GUI with default config

```bash
cd RS485_GUI
uv run rs485-gui
```

### 3. Run with explicit RS485 port

```bash
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
```

### 4. Optional: run on a different browser/UI port

```bash
uv run rs485-gui ui.port=8090 serial.default_port=/dev/ttyUSB_RS485
```

### 5. Optional: force Modbus RTU fallback mode

```bash
uv run rs485-gui \
  serial.default_port=/dev/ttyUSB_RS485 \
  device.mode=modbus_rtu
```

### 6. Optional: force Active-Send mode

```bash
uv run rs485-gui \
  serial.default_port=/dev/ttyUSB_RS485 \
  device.mode=active_send \
  serial.default_baudrate=460800
```

## Expected UI result

| UI element | Expected behavior |
| --- | --- |
| Browser page | Opens at the configured host/port, default `127.0.0.1:8088`. |
| Connection state | Shows connected after selecting the RS485 port and starting acquisition. |
| Main signal plot | Updates when the PM58/acquisition-board value changes. |
| Selected signal info | Shows selected signal metadata such as `net_value`, unit, status, and timestamp source. |
| Event log | Shows connect/disconnect, parser profile, logger paths, and errors/warnings if any. |
| Sampling estimate | Updates based on recent received frames. |

## Expected log output

Default output directory:

```text
RS485_GUI/logs/
```

Expected files when `logger.enabled=true`:

| File | Expected content |
| --- | --- |
| `raw_signal.ndjson` | Raw transport bytes/registers and board profile per frame. |
| `interpreted_signal.ndjson` | Decoded engineering values and metadata per frame. |
| `gui_signal.csv` | Spreadsheet-friendly flattened samples. |
| `event.log` | Operational events. |
| `acquisition_debug.log` | Python logging output when `logger.debug_log_to_file=true`. |

## Expected IPC output

When `ipc.enabled=true` and `ipc.start_on_connect=true`, the GUI binds:

```text
tcp://127.0.0.1:5557
```

Measurement topic:

```text
rs485.measurement.v1
```

Event topic:

```text
rs485.event.v1
```

`LSL_Bridge` should be able to subscribe and publish `HandgripReference` after the GUI is connected.

## Stop conditions

Stop and troubleshoot before running `LSL_Bridge` or calibration if:

- the acquisition-board display does not change under force,
- the GUI receives no valid frames,
- Active-Send mode continuously reports CRC/resync warnings,
- Modbus RTU polling times out repeatedly,
- the GUI accidentally connects to the Arduino target serial port,
- no logs are written even though `logger.enabled=true`,
- the IPC publisher cannot bind because another GUI process is already running.

## Troubleshooting links

- [`active-send-and-modbus.md`](active-send-and-modbus.md)
- [`ipc-schema.md`](ipc-schema.md)
- [`logging-and-outputs.md`](logging-and-outputs.md)
- [`../../docs/workflows/reference-only-quickstart.md`](../../docs/workflows/reference-only-quickstart.md)
- [`../../docs/troubleshooting/serial-and-rs485.md`](../../docs/troubleshooting/serial-and-rs485.md)
