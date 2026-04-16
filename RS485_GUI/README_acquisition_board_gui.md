# Acquisition Board GUI

A basic Python web UI for the **High-Speed Acquisition Instrument** board documented in the uploaded manual. It is built around the board's RS485 communication section (`C5.CoM`) and the documented Modbus-RTU register table. The UI lets you:

- discover likely USB-to-RS485 serial adapters,
- match the host serial settings to the board's `500.Ar / 501.br / 502.Vb / 503.so / 504.AS / 505.AF` settings,
- work in both documented communication modes:
  - **Modbus RTU** (`500.AS = 0`),
  - **Active send** (`500.AS = 1`),
- visualize the live time series using **host timestamps**,
- inspect raw transport frames vs decoded values side by side,
- send the documented command-register actions in Modbus RTU mode.

---

## 1. Why this UI uses NiceGUI

From the attached framework comparison, **NiceGUI** is the cleanest fit for this use case because it is described as a FastAPI-based framework with selective UI refreshing and as suitable for custom reactive web interfaces. That makes it a good match for a serial-device monitor with live plotting and continuously refreshing logs. fileciteturn0file3

The script uses NiceGUI's standard `ui.run()` server entrypoint and its Plotly component for the live chart. citeturn141647search2turn141647search0

---

## 2. Files

- `acquisition_board_gui.py` — main application
- `config.yaml` — Hydra defaults
- `README_acquisition_board_gui.md` — this document

---

## 3. Install

Recommended with `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install nicegui hydra-core omegaconf pyserial plotly
```

Run:

```bash
python acquisition_board_gui.py
```

Then open:

```text
http://127.0.0.1:8088
```

You can override Hydra values from CLI, for example:

```bash
python acquisition_board_gui.py ui.port=8090 serial.default_baudrate=115200 device.slave_address=3
```

---

## 4. What the UI exposes

### Connection panel

The top card exposes the exact communication parameters documented in the manual:

- `500.Ar` — slave address `1..253`
- `501.br` — baud code mapped to the documented baud table
- `502.Vb` — parity code
- `503.so` — stop bits
- `504.AS` — mode selector:
  - `0` = Modbus RTU
  - `1` = Active send
- `505.AF` — active-send frequency code with the documented `1 Hz .. 1000 Hz` range

The script does **not** reconfigure those board-side values by magic. It configures the **host side** so it matches the values you already set on the instrument. That is necessary because if the serial settings do not match, no valid Modbus communication is possible. The manual documents the full baud table, parity codes, stop-bit selection, and active-send frequency codes in section `C5.CoM`. fileciteturn1file12 fileciteturn1file13

### Live signal chart

The chart shows:

- **x-axis**: host-relative time in seconds,
- **y-axis**: `raw_value`.

In Modbus mode, `raw_value` is the board's raw gross-weight integer before decimal scaling.
In active-send mode, `raw_value` is the parser's best-effort numeric extraction from the incoming payload.

### Parallel logs

Left:
- raw transport material, such as Modbus request/response hex or active-send raw bytes.

Right:
- semantic interpretation of the data.

### Event log

Shows connect/disconnect, command writes, and acquisition errors.

### Modbus commands panel

In Modbus RTU mode the UI can write to the documented **command register** `40012`:

- `1` temp tare
- `2` saved tare
- `3` cancel tare
- `4` temp zero
- `5` saved zero
- `6` clear peak
- `7` calibration
- `9` factory reset

These actions are taken from the board's Modbus register map. fileciteturn4file3 fileciteturn4file6

---

## 5. Under the hood

## 5.1 USB / serial interface layer

The app talks to the USB-RS485 adapter through `pyserial`.

Port discovery is done by enumerating local serial ports and scoring them using common USB-serial hints such as:

- `USB`
- `RS485`
- `FTDI`
- `CH340`
- `CP210`
- `PL2303`
- `ttyUSB`
- `ttyACM`

This is host-side discovery only. It does not identify the board model itself; it identifies likely serial adapters that can reach the board.

## 5.2 Modbus RTU protocol implementation

The script uses a **minimal in-script Modbus RTU implementation**, not `pymodbus`.
That choice keeps the dependency surface smaller and makes the exact request/response frames explicit.

Implemented function codes:

- `0x03` — read holding registers
- `0x06` — write single register

It also implements:

- Modbus CRC16,
- frame construction,
- frame validation,
- exception detection,
- register decoding.

The poll loop reads holding registers starting at address `0x0000` / PLC `40001` and reads the first 11 registers, which the manual documents as:

- total weight low/high
- net weight low/high
- peak low/high
- internal code low/high
- decimal point
- unit
- status

Those mappings come directly from the manual's Modbus register table. fileciteturn4file5 fileciteturn4file18

### Register decoding

The script combines low/high word pairs into signed 32-bit values and exposes:

- gross raw value
- net raw value
- peak raw value
- internal ADC code raw value
- decimal code
- unit code
- status word
- scaled engineering values using the board's decimal-point code

The decimal-point map and unit codes also come directly from the manual. fileciteturn4file3 fileciteturn4file18

## 5.3 Active-send mode handling

The manual documents that active-send mode exists, and that `505.AF` supports `1, 2, 5, 10, 20, 25, 60, 100, 500, 1000 Hz`. However, the manual **does not document the active-send payload format**. That means there is no authoritative frame schema in the uploaded documentation for how each pushed sample is encoded. fileciteturn3file4

Because of that, the active-send implementation is intentionally **best-effort**:

- it reads line-oriented ASCII when possible,
- it can parse a single ASCII float,
- it can parse CSV and extract a configurable numeric field,
- it can parse the first 4 bytes of a hex string as a signed 32-bit integer.

This is enough to make the GUI usable as a live inspector while you characterize the board's actual active-send format on your hardware.

### Active-send parser profiles

Available parser profiles:

- `line_ascii_auto`
- `line_ascii_float`
- `line_ascii_csv`
- `hex_s32`

Relevant Hydra keys:

```yaml
active_send:
  default_parser_profile: line_ascii_auto
  default_numeric_index: 0
  default_hex_word_endianness: big
```

---

## 6. Manual-backed communication settings

The following board-side RS485 options are documented by the manual and represented in the UI:

### `500.Ar` — address

Range: `1..253`. fileciteturn1file12

### `501.br` — baud code mapping

| Code | Baud |
|---:|---:|
| 1 | 2400 |
| 2 | 4800 |
| 3 | 9600 |
| 4 | 19200 |
| 5 | 22800 |
| 6 | 38400 |
| 7 | 57600 |
| 8 | 115200 |
| 9 | 128000 |
| 10 | 230400 |
| 11 | 256000 |
| 12 | 460800 |
| 13 | 500000 |
| 14 | 512000 |
| 15 | 600000 |

The manual also notes that the display truncates the last two digits when showing baud values on the board UI. fileciteturn1file12

### `502.Vb` — parity

- `0` = none
- `1` = even
- `2` = odd fileciteturn1file12

### `503.so` — stop bits

- `1`
- `2` fileciteturn1file12

### `504.AS` — mode

- `0` = Modbus RTU
- `1` = active send fileciteturn1file12

### `505.AF` — active-send frequency codes

- `0` = 1 Hz
- `1` = 2 Hz
- `2` = 5 Hz
- `3` = 10 Hz
- `4` = 20 Hz
- `5` = 25 Hz
- `6` = 60 Hz
- `7` = 100 Hz
- `8` = 500 Hz
- `9` = 1000 Hz fileciteturn1file13

---

## 7. Example usage

### 7.1 Modbus RTU mode

1. On the board, set:
   - `500.Ar = 1`
   - `501.br = 3` for `9600`
   - `502.Vb = 0`
   - `503.so = 1`
   - `504.AS = 0`
2. In the UI, select:
   - slave address `1`
   - baud `9600`
   - parity `None`
   - stop bits `1`
   - mode `Modbus RTU`
3. Press **Connect**.
4. The raw panel will show RTU request/response hex and decoded register words.
5. The interpreted panel will show scaled gross/net/peak values and status flags.

### 7.2 Active-send mode

1. On the board, set:
   - `504.AS = 1`
   - `505.AF` to the desired send rate
2. In the UI, mirror the serial settings.
3. Start with parser profile `line_ascii_auto`.
4. If the interpreted side does not resolve numeric values correctly, switch to:
   - `line_ascii_csv` and set the numeric field index, or
   - `hex_s32` if the payload is hex text.

---

## 8. Config reference

```yaml
app:
  log_level: INFO

ui:
  host: 127.0.0.1
  port: 8088
  refresh_interval_s: 0.2
  plot_height_px: 360
  log_height_px: 380
  event_log_height_px: 180

serial:
  default_port: ""
  default_baudrate: 9600
  default_parity: N
  default_stopbits: 1
  timeout_s: 0.2
  inter_frame_gap_s: 0.01

device:
  mode: modbus_rtu
  slave_address: 1
  active_send_frequency_code: 2
  poll_interval_s: 0.1
  error_backoff_s: 0.25

active_send:
  default_parser_profile: line_ascii_auto
  default_numeric_index: 0
  default_hex_word_endianness: big
  read_timeout_s: 0.5
  read_chunk_bytes: 256
  max_binary_frame_bytes: 64
```

---

## 9. Limitations

1. **Active-send payload is undocumented in the uploaded manual.** The app supports active-send inspection, but its semantic decode is heuristic until you verify the real payload format on your device. fileciteturn3file4
2. The app currently uses **host receive time** as the chart timestamp because the documented Modbus register block does not expose a transport timestamp. fileciteturn4file5
3. The script focuses on **RS485 / Modbus / active-send monitoring**. It does not attempt to expose every non-communication parameter from the instrument menus.
4. The script assumes the adapter already appears as a normal serial device in the OS.

---

## 10. Next useful extension

The highest-ROI next step is to capture a few seconds of real **active-send raw frames** from your hardware and then lock the parser to the actual payload schema. That will turn active-send mode from best-effort decoding into deterministic decoding.
