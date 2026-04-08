# Handgrip LSL Bridge

Serial-to-LSL bridge for the Arduino handgrip sensor.

This script reads serial samples, parses one of several wire formats, applies a configurable filter pipeline, publishes to an LSL irregular stream, and logs accepted samples to CSV.

## Directory Contents

```text
LSL_Bridge/
  handgrip_lsl_bridge.py       # Main serial -> LSL + CSV bridge
  filter.py                    # Processing/filter pipeline implementation
  conf/config.yaml             # Hydra config (serial, protocol, stream, processing, csv)
  data/handgrip_samples.csv    # Default CSV output path
  handgrip_lsl_bridge.log      # Runtime log file (if generated locally)
```

## Features

- Serial reconnect loop on port failure
- Parser modes: `auto`, `tagged_csv`, `simple_csv`, `legacy_pair_lines`
- Optional CRC16 check for tagged frames
- LSL stream with 3 channels:
  - `device_clock_us`
  - `grip_force_raw`
  - `grip_force_filtered`
- CSV logging with both raw and filtered values
- Configurable processing timestamp source:
  - `device_clock_us` (default)
  - `lsl`
- Configurable filter pipeline with sample-by-sample processing nodes

## Requirements

Dependencies are managed from the repository root `pyproject.toml`.

```bash
uv sync
```

Python `>=3.11` is required.

## Run

From the `LSL_Bridge` directory:

```bash
uv run python handgrip_lsl_bridge.py
```

Or from repository root:

```bash
uv run python LSL_Bridge/handgrip_lsl_bridge.py
```

Override config values at runtime (Hydra style):

```bash
uv run python handgrip_lsl_bridge.py serial.port=/dev/ttyUSB0 serial.baudrate=115200 csv.path=./data/run01.csv
```

## Input Protocols

`protocol.mode` in `conf/config.yaml` controls parsing.

### 1) `tagged_csv` (recommended)

```text
D,<seq>,<timestamp_us>,<value>
```

Example:

```text
D,1532,41876250,12.437500
```

Optional CRC format (enable `protocol.expect_crc16: true`):

```text
D,<seq>,<timestamp_us>,<value>,<crc16_hex>
```

### 2) `simple_csv`

```text
<timestamp_us>,<value>
```

### 3) `legacy_pair_lines`

```text
>read_sample.timestamp:<timestamp_us>
>read_sample.value:<value>
```

`auto` mode attempts `tagged_csv`, then `simple_csv`, then `legacy_pair_lines`.

## LSL Stream Model

- Stream rate is irregular (`IRREGULAR_RATE`)
- LSL timestamp is host-side receive time (`local_clock()`), optionally shifted by `serial.transport_latency_s`
- Channel layout:
  - channel 0: device clock in microseconds
  - channel 1: raw sensor value
  - channel 2: filtered value

## Processing Pipeline

`processing.module` defaults to `filter`, which builds a chain from `processing.filters`.

### Default filtered channel

The default `grip_force_filtered` channel now implements the filter recommended in `Handgrip_Analysis/README_filter_design_report.md` for the primary characterization path:

1. **2nd-order Butterworth low-pass**
2. **Cutoff = 15 Hz**
3. **Nominal sample rate = 100 Hz**

This keeps the filtered channel aligned with the current design recommendation for reconstructing the most realistic handgrip force curve while preserving the raw channel untouched.

### Supported filter types in `filter.py`

- `butterworth_lowpass_2nd`
- `biquad_lowpass`
- `lowpass_1pole`
- `drift_corrector`
- `identity`

`butterworth_lowpass_2nd` is a convenience alias for a biquad low-pass with Butterworth damping (`q = 1/sqrt(2)`).

### Default config

```yaml
processing:
  module: filter
  timestamp_source: device_clock_us
  filters:
    - type: butterworth_lowpass_2nd
      name: characterization_lowpass_15hz
      sample_rate_hz: 100.0
      cutoff_hz: 15.0
      q: 0.7071067811865476
      reset_on_gap_s: 1.0
      min_dt_s: 0.000001
```

### Why drift correction is not in the default filtered channel anymore

The latest filter-design report recommends keeping **baseline / zero handling separate** from the primary force waveform reconstruction path. So the bridge no longer applies continuous drift correction in the default filtered channel. If you need gated baseline tracking for a separate downstream path, you can still add it explicitly through `processing.filters`.

### Example overrides

Use the optional steadier display-style channel recommended by the report:

```bash
uv run python handgrip_lsl_bridge.py   processing.filters='[{type: butterworth_lowpass_2nd, name: ui_lowpass_10hz, sample_rate_hz: 100.0, cutoff_hz: 10.0, q: 0.7071067811865476}]'
```

Temporarily disable filtering:

```bash
uv run python handgrip_lsl_bridge.py processing.filters='[{type: identity, name: bypass}]'
```

Add a custom chained path:

```bash
uv run python handgrip_lsl_bridge.py   processing.filters='[
    {type: butterworth_lowpass_2nd, name: lp15, sample_rate_hz: 100.0, cutoff_hz: 15.0, q: 0.7071067811865476},
    {type: drift_corrector, name: optional_baseline_tracker, baseline_cutoff_hz: 0.02, rest_band: 5.0, stable_slope_threshold_per_s: 5.0, warmup_samples: 20}
  ]'
```

## CSV Output

Default file: `LSL_Bridge/data/handgrip_samples.csv`

Columns:

- `host_unix_time_ns`
- `lsl_timestamp_s`
- `device_clock_us`
- `value_raw`
- `value_filtered`
- `sequence`
- `parser_mode`
- `raw_line`

## Configuration Reference

Main sections in `conf/config.yaml`:

- `stream`: LSL stream metadata and channel labels
- `serial`: port, baudrate, timeout, reconnect behavior
- `protocol`: parser mode and wire format details
- `processing`: module, timestamp source, filter chain
- `csv`: output path and flush behavior
- `logging`: log level and sample/parse log cadence

Useful overrides:

```bash
# Select parser mode explicitly
uv run python handgrip_lsl_bridge.py protocol.mode=tagged_csv

# Enable tagged frame CRC checking
uv run python handgrip_lsl_bridge.py protocol.expect_crc16=true

# Use host LSL time inside processing filters
uv run python handgrip_lsl_bridge.py processing.timestamp_source=lsl
```

## Notes

- If the serial device resets on connect, tune `serial.startup_settle_s`.
- Overlong serial lines are dropped when they exceed `serial.max_line_bytes`.
- On serial errors, the bridge retries after `serial.reconnect_backoff_s`.
- The default 2nd-order low-pass assumes the current nominal device output rate is 100 Hz. If the firmware sample rate changes, update `processing.filters[0].sample_rate_hz` accordingly so the cutoff remains correct.
