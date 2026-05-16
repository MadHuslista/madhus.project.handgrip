# Handgrip Firmware Serial Protocol

## Summary

- The current firmware protocol is **schema 2**, identified by `M2` metadata frames and `D2` data frames.
- `D2` is the only data frame schema that should be treated as current for the handoff documentation.
- The legacy `legacy D-prefix three-field value frame` format is deprecated and should not be used in new bridge, viewer, calibration, or analysis docs.
- `raw_count` is the calibration-authoritative signal. `current_units` is a convenience channel computed from firmware constants.
- `status` is a bitfield that makes timing/acquisition problems visible instead of hiding them.

## Audience

Read this document if you need to:

- validate target firmware output in a serial monitor,
- understand what `LSL_Bridge` expects from the target device,
- debug dropped target samples,
- update calibration constants in firmware,
- extend the target stream with additional fields.

## Status

| Field        | Value                                                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Canonical    | Yes                                                                                                                      |
| Applies to   | `Handgrip_Firmware` schema 2 / `HANDGRIP_PAYLOAD_SCHEMA = 2U`                                                            |
| Source files | `Handgrip_Firmware/Core/Inc/config.h`, `Handgrip_Firmware/Core/Src/main.cpp`, `LSL_Bridge/src/lsl_bridge/core/parser.py` |
| Consumers    | `LSL_Bridge`, `LSL_Viewer`, `Handgrip_Calibration`, downstream analysis outputs                                          |
| Replaces     | Legacy `legacy D-prefix three-field value frame` documentation                                                           |

## Frame types

The firmware emits two ASCII CSV frame families over UART at `SERIAL_BAUD_RATE = 115200`.

### Metadata frame: `M2`

The firmware emits an `M2` metadata frame at boot:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

Example:

```text
M2,2,2.0.0-calibration-schema,unknown,93.000,1.000000000,0.000,N
```

| Field              | Meaning                              | Notes                                                           |
| ------------------ | ------------------------------------ | --------------------------------------------------------------- |
| `M2`               | Metadata frame prefix                | Used by the bridge to identify boot/build metadata.             |
| `payload_schema`   | Firmware payload schema version      | Current supported value: `2`.                                   |
| `firmware_version` | Firmware semantic/source version     | Human-readable.                                                 |
| `git_sha`          | Source build identifier              | Defaults to `unknown` unless injected at compile time.          |
| `expected_rate_hz` | Expected practical HX711 output rate | Metadata only; target stream remains irregular.                 |
| `scale_factor`     | Current firmware scale factor        | Used only for `current_units`; raw counts remain authoritative. |
| `scale_offset`     | Current firmware offset              | Used only for `current_units`; raw counts remain authoritative. |
| `unit`             | Engineering unit for `current_units` | Recommended calibration unit: `N`.                              |

### Data frame: `D2`

The firmware emits one strict `D2` record per captured HX711 sample:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Example:

```text
D2,42,1234567,-842133,12.345678,0
```

| Field           | Type                      | Meaning                                               | Calibration relevance                                           |
| --------------- | ------------------------- | ----------------------------------------------------- | --------------------------------------------------------------- |
| `D2`            | literal                   | Data-frame prefix                                     | Must match `LSL_Bridge.protocol.data_prefix`.                   |
| `seq`           | unsigned integer          | Monotonic sample sequence number                      | Used to detect dropped samples and sequence gaps.               |
| `timestamp_us`  | unsigned integer          | Device-local `micros()` timestamp in microseconds     | Used to audit timing and reconstruct device-clock behavior.     |
| `raw_count`     | signed integer            | HX711 raw ADC count before firmware scale/offset      | **Primary target signal for calibration fitting.**              |
| `current_units` | float or `nan`            | Convenience engineering value from firmware constants | Useful for sanity display; not the source of truth for fitting. |
| `status`        | unsigned integer bitfield | Acquisition status flags                              | Used for QA and troubleshooting.                                |

## Status bitfield

The `status` field is an integer bitfield. Multiple bits can be set in the same sample.

| Bit mask | Name                             | Meaning                                                                                  | Operator action                                                                                                         |
| -------: | -------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `0x0000` | `HANDGRIP_STATUS_OK`             | No known acquisition issue for this sample                                               | Continue.                                                                                                               |
| `0x0001` | `HANDGRIP_STATUS_FIFO_OVERFLOW`  | Interrupt-to-main-loop FIFO overflowed                                                   | Reduce serial/logging load, check host consumption, inspect missed samples.                                             |
| `0x0002` | `HANDGRIP_STATUS_HX711_NOTREADY` | Timer tick occurred before HX711 had a new conversion ready                              | Occasional events are expected with non-blocking polling; persistent events indicate rate/config mismatch or ADC issue. |
| `0x0004` | `HANDGRIP_STATUS_SCALE_INVALID`  | Firmware `current_units` conversion invalid, usually because scale factor is zero or NaN | Do not trust `current_units`; use `raw_count`; fix firmware constants before operator-facing use.                       |

## Why `raw_count` is authoritative

Calibration should fit:

```text
reference_force_N = f(target_raw_count)
```

not:

```text
reference_force_N = f(current_units)
```

Reason:

- `raw_count` is emitted before firmware scale/offset transformation.
- `current_units` can change whenever `SCALE_FACTOR` or `SCALE_OFFSET` changes.
- Calibration reports are expected to produce or recommend firmware constants later.
- Using `current_units` as the fitting input can accidentally fit against a mutable previous calibration.

Use `current_units` only as a convenience/sanity channel unless a protocol explicitly states otherwise.

## Expected serial monitor workflow

### Step 1 — Open the serial monitor

```bash
pio device monitor -b 115200
```

### Step 2 — Verify metadata frame

Expected near boot:

```text
M2,2,...
```

Success condition:

- at least one `M2` line appears after reset,
- schema field is `2`,
- unit is the expected unit, normally `N`.

Failure signal:

- no `M2` line appears after reset,
- bridge logs “metadata missing” for the target,
- schema is not `2`.

### Step 3 — Verify data frames

Expected while running:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Success condition:

- line starts with `D2,`,
- there are exactly six comma-separated fields,
- `seq` increases monotonically,
- `timestamp_us` increases over time,
- `raw_count` changes when force changes,
- `status` is usually `0` or only occasionally nonzero.

Failure signal:

- lines start with legacy `D,`,
- field count is not six,
- `seq` jumps frequently,
- `raw_count` is constant under applied force,
- status is persistently nonzero.

## `LSL_Bridge` parser contract

`LSL_Bridge` expects the D2/M2 protocol exactly.

Current D2 regex shape:

```text
^D2,<seq>,<clock>,<raw>,<units>,<status>$
```

Bridge output mapping:

| D2 field        | Bridge parsed field    | LSL/channel meaning           |
| --------------- | ---------------------- | ----------------------------- |
| `seq`           | `sequence`             | Target sample sequence.       |
| `timestamp_us`  | `device_clock_us`      | Device-local clock.           |
| `raw_count`     | `target_raw_count`     | Raw target count.             |
| `current_units` | `target_current_units` | Firmware-scaled sanity value. |
| `status`        | `target_status`        | Target acquisition status.    |

If the bridge logs dropped non-D2 target lines, inspect the serial monitor first. Do not relax the parser unless the firmware schema is intentionally changed and every consumer is updated.

## Deprecated legacy protocol

The old format:

```text
legacy D-prefix three-field value frame
```

is deprecated for the current Handgrip Suite.

Do not use it in:

- new firmware docs,
- bridge docs,
- calibration docs,
- analysis docs,
- troubleshooting examples,
- stream schema references.

If legacy data must be replayed, treat it as a separate compatibility pathway and label it clearly as legacy.

## Modification rules

Changing the serial protocol is a cross-component change.

If any field is added, removed, renamed, or reordered, update all of these together:

1. `Handgrip_Firmware/Core/Src/main.cpp`
2. `Handgrip_Firmware/Core/Inc/config.h`
3. `Handgrip_Firmware/docs/serial-protocol.md`
4. `LSL_Bridge/src/lsl_bridge/core/parser.py`
5. `LSL_Bridge/conf/config.yaml`
6. `LSL_Bridge/tests/unit/test_parser.py`
7. `LSL_Bridge/docs/stream-contracts.md`
8. `docs/architecture/stream-contracts.md`
9. `Handgrip_Calibration` stream/channel assumptions
10. viewer and analysis docs that mention target channels

## Validation checklist

Before handoff, validate:

```bash
# From repo root
rg "D,<seq>|legacy engineering-value field" README.md docs Handgrip_Firmware LSL_Bridge Handgrip_Calibration LSL_Viewer Handgrip_Analysis || true
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" README.md docs Handgrip_Firmware LSL_Bridge
```

Expected result:

- no canonical docs advertise the legacy `legacy D-prefix frame` schema as current,
- D2 schema appears in firmware and stream-contract docs,
- `LSL_Bridge` parser tests pass.
