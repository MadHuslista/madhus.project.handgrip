# handgrip-lsl-bridge

Serial-to-LSL bridge for an Arduino handgrip sensor.

## What it does

- reads `clock,value` data from the Arduino over serial
- republishes it as an **LSL irregular stream**
- writes every accepted sample to a CSV file
- supports reconnect on serial failure
- supports three parser modes:
  - `tagged_csv` (recommended)
  - `simple_csv`
  - `legacy_pair_lines` (compatible with the currently attached Arduino code)

## Recommended Arduino wire format

Prefer one line per sample:

```text
D,<seq>,<timestamp_us>,<value>\n
```

Example:

```text
D,1532,41876250,12.437500
```

Optional CRC16 line format:

```text
D,<seq>,<timestamp_us>,<value>,<crc16_hex>\n
```

Example:

```text
D,1532,41876250,12.437500,7A4C
```

If you need a minimal protocol first, this also works:

```text
41876250,12.437500
```

## Install with uv

```bash
uv sync
```

## Run

```bash
uv run python handgrip_lsl_bridge.py
```

Example override:

```bash
uv run python handgrip_lsl_bridge.py serial.port=/dev/ttyUSB0 csv.path=./captures/run01.csv
```

## Notes on timestamps

The stream is published as an **irregular** LSL stream.

- LSL timestamp = host-side `local_clock()` at the instant the serial frame is received
- channel 0 = Arduino device clock in microseconds
- channel 1 = measured value

This keeps the Arduino clock available for offline analysis without pretending it is already synchronized to the host clock.
