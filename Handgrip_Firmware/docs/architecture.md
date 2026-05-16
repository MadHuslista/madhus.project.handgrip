# Handgrip Firmware Architecture

## Summary

- The firmware is intentionally small: initialize serial/HX711, emit M2 metadata, capture HX711 samples from a TimerOne interrupt, pass samples through a FIFO, and emit strict D2 lines from the main loop.
- The ISR is non-blocking: it checks `HX711::is_ready()` and returns immediately if no conversion is available.
- A fixed-size FIFO decouples interrupt-time sample capture from serial printing in `loop()`.
- Status bits expose acquisition issues such as HX711-not-ready ticks, FIFO overflow, and invalid scale conversion.
- Calibration ownership remains host-side; firmware preserves raw counts and current constants for traceability.

## Source files

| File | Responsibility |
| --- | --- |
| `Core/Src/main.cpp` | Setup, ISR, raw-to-units conversion, metadata emission, D2 sample emission. |
| `Core/Inc/config.h` | Public constants, status bits, schema, metadata, scale/offset, timing. |
| `Core/Inc/fifo_buffer.h` | Fixed-size circular FIFO template. |
| `../platformio.ini` | Build environment, board selection, library dependencies, source/include paths. |

## Runtime dataflow

```text
setup()
  ├── Serial.begin(SERIAL_BAUD_RATE)
  ├── _scale.begin(GPIO_DATA_PIN, GPIO_CLOCK_PIN)
  ├── _scale.set_scale(SCALE_FACTOR)
  ├── _scale.set_offset(SCALE_OFFSET)
  ├── _emit_metadata()                         → M2 line
  └── Timer1.initialize(SAMPLING_PERIOD_US)
      Timer1.attachInterrupt(sample_scale)

TimerOne ISR: sample_scale()
  ├── if HX711 not ready: set HANDGRIP_STATUS_HX711_NOTREADY and return
  ├── timestamp_us = micros()
  ├── raw_count = _scale.read()
  ├── current_units = _raw_to_units(raw_count)
  ├── seq = _seq++
  ├── status = _sticky_status plus scale-invalid if needed
  └── push SensorSample into FIFO

loop()
  ├── pop sample from FIFO
  ├── if timestamp_us == 0: return
  └── _emit_sample(sample)                      → D2 line
```

## Setup phase

`setup()` performs four important actions:

1. Starts UART at `SERIAL_BAUD_RATE`.
2. Initializes HX711 on the configured Arduino pins.
3. Applies firmware scale/offset constants for `current_units` sanity output.
4. Emits an `M2` metadata line before starting TimerOne acquisition.

Design intent:

- Metadata should be available to the host/session before data samples begin.
- Firmware constants are visible to the bridge/calibration metadata path.
- `raw_count` remains preserved regardless of scale/offset.

## TimerOne acquisition

The firmware uses TimerOne with:

```text
SAMPLING_PERIOD_US = 5000U
```

This is a 200 Hz timer tick. The HX711 practical output rate is lower, expected around 93 Hz in this firmware metadata.

The ISR does not block waiting for HX711. Instead:

```text
if (!_scale.is_ready()) {
    _sticky_status |= HANDGRIP_STATUS_HX711_NOTREADY;
    return;
}
```

Why this is correct:

- blocking inside the ISR would increase timing risk,
- non-ready ticks are expected when timer tick is faster than ADC conversion rate,
- status bits make timing irregularity visible to the host.

## Sensor sample structure

Runtime sample fields:

| Field | Source | Purpose |
| --- | --- | --- |
| `raw_count` | `_scale.read()` | HX711 raw count; calibration-authoritative. |
| `current_units` | `_raw_to_units(raw_count)` | firmware-scaled sanity value. |
| `timestamp_us` | `micros()` | device-local timestamp. |
| `seq` | `_seq++` | monotonic sequence number. |
| `status` | `_sticky_status` + scale status | acquisition/scaling QA bitfield. |

## FIFO handoff

The FIFO decouples sample capture from serial printing.

| Side | Action |
| --- | --- |
| ISR | Pushes `SensorSample` into `_sensor_fifo`. |
| Main loop | Pops one `SensorSample` and emits it over serial. |

Why this matters:

- serial printing from an ISR would be unsafe and slow,
- the main loop can spend variable time printing without blocking acquisition,
- FIFO overflow is detected and surfaced through `HANDGRIP_STATUS_FIFO_OVERFLOW`.

Current FIFO depth:

```text
MAX_FIFO_SIZE = 80U
```

## Sticky status behavior

`_sticky_status` accumulates acquisition issues observed before the next successful sample push.

Examples:

- HX711 not ready before the next real sample: next sample may include `HANDGRIP_STATUS_HX711_NOTREADY`.
- FIFO push fails: overflow status is retained so a later emitted sample can expose the problem.
- successful push: `_sticky_status` resets to `HANDGRIP_STATUS_OK`.

This design makes intermittent ISR-side problems visible in emitted data.

## Serial output

### Metadata output

`_emit_metadata()` emits:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

### Sample output

`_emit_sample()` emits:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

If `current_units` is NaN, firmware prints literal `nan`.

## HX711 dependency

The firmware depends on:

```text
robtillaart/HX711@^0.6.3
```

Used calls include:

| Call | Purpose |
| --- | --- |
| `_scale.begin(data_pin, clock_pin)` | Initialize HX711 pins. |
| `_scale.set_scale(SCALE_FACTOR)` | Set library scale used for sanity behavior. |
| `_scale.set_offset(SCALE_OFFSET)` | Set library offset used for sanity behavior. |
| `_scale.is_ready()` | Non-blocking readiness check. |
| `_scale.read()` | Read raw ADC count. |

## TimerOne dependency

The firmware depends on:

```text
paulstoffregen/TimerOne@^1.2
```

Used calls include:

| Call | Purpose |
| --- | --- |
| `Timer1.initialize(SAMPLING_PERIOD_US)` | Configure timer tick period. |
| `Timer1.attachInterrupt(sample_scale)` | Register sample ISR. |

## Architecture boundaries

| Belongs in firmware | Does not belong in firmware |
| --- | --- |
| raw HX711 acquisition | calibration protocol sequencing |
| device timestamp | static hold segmentation |
| monotonic sequence number | model fitting |
| status bitfield | report generation |
| current firmware constants metadata | reference/target synchronization policy beyond exposed timestamps |
| simple raw-to-units sanity conversion | DSP model selection |

## Change-risk map

| Change | Risk | Required validation |
| --- | --- | --- |
| Change pins | No data if wiring/config mismatch. | Serial monitor + force response. |
| Change sampling period | More not-ready ticks or FIFO pressure. | Status histogram and sequence gaps. |
| Change FIFO depth | SRAM pressure or overflow behavior. | Long-run serial test. |
| Change D2 fields | Cross-component breakage. | Bridge parser tests + root stream contract update. |
| Change scale/offset | `current_units` changes. | Calibration/holdout validation. |

## Validation checklist

- [ ] Build succeeds with `pio run -e nanoatmega328`.
- [ ] Upload succeeds with target board connected.
- [ ] M2 metadata appears after reset.
- [ ] D2 samples appear continuously.
- [ ] `raw_count` reacts to force.
- [ ] `seq` is monotonic.
- [ ] nonzero status bits are understood and not ignored.
- [ ] `LSL_Bridge` target-only quickstart parses firmware output.
