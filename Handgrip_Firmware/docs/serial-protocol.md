# Handgrip Firmware Serial Protocol

## Summary

- The current firmware protocol is **schema 2**, identified by `M2` metadata frames and `D2` data frames.
- `D2` is the only current data frame schema for the handoff documentation.
- `raw_count` is the calibration-authoritative signal. `current_units` is a firmware-scaled convenience/sanity channel.
- `status` is a bitfield that makes acquisition/timing problems explicit instead of hidden.
- `LSL_Bridge` expects a strict D2 parser contract; do not make the parser permissive without a deliberate cross-component migration.

## Audience

Read this document if you need to:

- validate target firmware output in a serial monitor,
- understand what `LSL_Bridge` expects from the target device,
- debug dropped target samples,
- update calibration constants in firmware,
- extend the target stream with additional fields.

## Status

| Field | Value |
| --- | --- |
| Canonical | Yes |
| Applies to | `Handgrip_Firmware` schema 2 / `HANDGRIP_PAYLOAD_SCHEMA = 2U` |
| Source files | `Core/Inc/config.h`, `Core/Src/main.cpp`, `LSL_Bridge/src/lsl_bridge/core/parser.py` |
| Consumers | `LSL_Bridge`, `LSL_Viewer`, `Handgrip_Calibration`, downstream analysis outputs |
| Replaces | Legacy D-prefix target output documentation |

## Frame types

The firmware emits ASCII CSV lines over UART at `SERIAL_BAUD_RATE = 115200`.

### Metadata frame: `M2`

The firmware emits an `M2` metadata frame at boot:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

Example:

```text
M2,2,2.0.0-calibration-schema,unknown,93.000,1.000000000,0.000,N
```

| Field | Meaning | Notes |
| --- | --- | --- |
| `M2` | Metadata frame prefix | Used by the bridge/session metadata path to identify firmware context. |
| `payload_schema` | Firmware payload schema version | Current supported value: `2`. |
| `firmware_version` | Firmware semantic/source version | Human-readable version string. |
| `git_sha` | Source build identifier | Defaults to `unknown` unless injected at compile time. |
| `expected_rate_hz` | Expected practical HX711 output rate | Metadata only; target stream remains irregular. |
| `scale_factor` | Current firmware scale factor | Used for `current_units`; raw counts remain authoritative. |
| `scale_offset` | Current firmware offset | Used for `current_units`; raw counts remain authoritative. |
| `unit` | Engineering unit for `current_units` | Recommended calibration unit: `N`. |

### Data frame: `D2`

The firmware emits one strict `D2` record per captured HX711 sample:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Example:

```text
D2,42,1234567,-842133,12.345678,0
```

| Field | Type | Meaning | Calibration relevance |
| --- | --- | --- | --- |
| `D2` | literal | Data-frame prefix | Must match the `LSL_Bridge` data-prefix/parser expectation. |
| `seq` | unsigned integer | Monotonic sample sequence number | Used to detect dropped samples and sequence gaps. |
| `timestamp_us` | unsigned integer | Device-local `micros()` timestamp in microseconds | Used to audit timing and reconstruct device-clock behavior. |
| `raw_count` | signed integer | HX711 raw ADC count before firmware scale/offset | **Primary target signal for calibration fitting.** |
| `current_units` | float or `nan` | Convenience engineering value from firmware constants | Useful for sanity display; not the source of truth for fitting. |
| `status` | unsigned integer bitfield | Acquisition status flags | Used for QA and troubleshooting. |

## Status bitfield

The `status` field is an integer bitfield. Multiple bits can be set in the same sample.

| Bit mask | Name | Meaning | Operator action |
| ---: | --- | --- | --- |
| `0x0000` | `HANDGRIP_STATUS_OK` | No known acquisition issue for this sample | Continue. |
| `0x0001` | `HANDGRIP_STATUS_FIFO_OVERFLOW` | Interrupt-to-loop FIFO overflowed | Reduce serial/logging load, check host consumption, inspect missed samples. |
| `0x0002` | `HANDGRIP_STATUS_HX711_NOTREADY` | Timer tick occurred before HX711 had a new conversion ready | Occasional events may happen with non-blocking polling; persistent events require diagnosis. |
| `0x0004` | `HANDGRIP_STATUS_SCALE_INVALID` | Firmware `current_units` conversion invalid, usually because scale factor is zero or NaN | Do not trust `current_units`; use `raw_count`; fix firmware constants before operator-facing use. |

## Why `raw_count` is authoritative

Calibration should fit:

```text
reference_force_N = f(target_raw_count)
```

not firmware-scaled convenience values.

Reason:

- `raw_count` is emitted before firmware scale/offset transformation.
- `current_units` can change whenever `SCALE_FACTOR` or `SCALE_OFFSET` changes.
- Calibration reports are expected to recommend firmware constants later.
- Using `current_units` as the fitting input can accidentally validate a previous or placeholder calibration.

Use `current_units` only as a convenience/sanity channel unless a workflow explicitly states otherwise.

## Parser contract

`LSL_Bridge` expects the D2/M2 protocol exactly.

Expected data shape:

```text
^D2,<seq>,<clock>,<raw>,<units>,<status>$
```

Valid examples:

```text
D2,0,123456,-842133,0.000000,0
D2,1,134002,-842129,nan,4
```

Invalid examples:

```text
D,1,134002,12.3
D2,42,,123456,-842133,12.3,0
D2,42,123456,-842133,12.3
```

Invalid target lines should trigger bridge logs. Do not relax the parser unless the firmware schema is intentionally changed and every consumer is updated.

## Bridge output mapping

Recommended semantic mapping:

| D2 field | Bridge semantic field | LSL/channel meaning |
| --- | --- | --- |
| `seq` | `target_sequence` | Target sample sequence. |
| `timestamp_us` | `device_clock_us` | Device-local clock. |
| `raw_count` | `target_raw_count` | Raw target count. |
| `current_units` | `target_current_units` | Firmware-scaled sanity value. |
| `status` | `target_status` | Target acquisition status. |

If channel order differs from this semantic table, keep active config and component docs authoritative but preserve these semantic names across docs and downstream outputs.

## Modification rules

Changing the serial protocol is a cross-component migration. If any field is added, removed, renamed, or reordered, update all of these together:

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

## Serial monitor validation

```bash
pio device monitor -e nanoatmega328 -b 115200
```

Expected near boot:

```text
M2,2,...
```

Expected while running:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Validation points:

- at least one `M2` line appears after reset,
- schema field is `2`,
- sample lines start with `D2,`,
- each D2 sample has six comma-separated fields,
- `seq` and `timestamp_us` increase,
- `raw_count` responds to force,
- `status` is understood if nonzero.

## Documentation validation

```bash
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" \
  README.md docs Handgrip_Firmware LSL_Bridge

# Optional: fail if canonical docs advertise the old target schema as current.
if rg "legacy D-prefix target frame" README.md docs Handgrip_Firmware LSL_Bridge; then
  echo "ERROR: stale target schema found in canonical docs" >&2
  exit 1
fi
```
