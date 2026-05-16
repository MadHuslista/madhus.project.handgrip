# Handgrip Firmware Configuration

## Summary

- Firmware configuration is split between root `platformio.ini`, public constants in `Core/Inc/config.h`, and a few private implementation constants in `Core/Src/main.cpp`.
- `config.h` owns serial rate, schema version, scale/offset, sampling period, status bits, firmware metadata, and expected HX711 rate.
- `SCALE_FACTOR` and `SCALE_OFFSET` affect `current_units` only; `raw_count` remains calibration-authoritative.
- `SAMPLING_PERIOD_US = 5000U` sets a 200 Hz timer tick for non-blocking HX711 polling, while the expected practical HX711 output rate metadata is `93.0 Hz`.
- Any change to payload schema or emitted fields is a cross-component migration, not a local firmware-only change.

## Configuration sources

| Source | Scope | Safe to edit? |
| --- | --- | --- |
| `../platformio.ini` | PlatformIO board/environment, source/include dirs, libraries, upload/monitor ports. | Yes, with build/upload validation. |
| `Core/Inc/config.h` | Public firmware behavior constants and metadata. | Yes, with serial/bridge/calibration validation. |
| `Core/Src/main.cpp` | HX711 pins, FIFO depth, runtime ISR/loop behavior. | Only with firmware architecture review. |
| `Core/Inc/fifo_buffer.h` | Generic FIFO implementation. | Avoid unless fixing a proven FIFO behavior issue. |

## Root `platformio.ini`

Expected project configuration:

```ini
[platformio]
src_dir = Handgrip_Firmware/Core/Src
include_dir = Handgrip_Firmware/Core/Inc

[env:nanoatmega328]
platform = atmelavr
board = nanoatmega328
framework = arduino
lib_deps =
    robtillaart/HX711@^0.6.3
    paulstoffregen/TimerOne@^1.2
upload_port = /dev/ttyUSB*
monitor_port = /dev/ttyUSB*
monitor_speed = 115200
```

### PlatformIO settings table

| Key | Current value | Impact | When to change | Failure risk |
| --- | --- | --- | --- | --- |
| `src_dir` | `Handgrip_Firmware/Core/Src` | Tells PlatformIO where `main.cpp` lives. | Only if firmware source tree moves. | Build cannot find source. |
| `include_dir` | `Handgrip_Firmware/Core/Inc` | Tells PlatformIO where `config.h` and `fifo_buffer.h` live. | Only if include tree moves. | Build cannot find headers. |
| `platform` | `atmelavr` | Selects AVR platform/toolchain. | Only if target MCU family changes. | Wrong toolchain/build. |
| `board` | `nanoatmega328` | Selects Arduino Nano ATmega328 old bootloader profile. | Only if physical board/bootloader changes. | Upload sync errors or wrong clock/bootloader. |
| `framework` | `arduino` | Uses Arduino runtime and APIs. | Do not change for current handoff. | Source no longer builds. |
| `lib_deps` | `HX711`, `TimerOne` | Resolves runtime dependencies. | Pin/update only after testing. | API mismatch or build failure. |
| `upload_port` | `/dev/ttyUSB*` | Auto-selects USB serial for upload. | Use explicit `/dev/serial/by-id/...` when multiple adapters exist. | Upload may target wrong device. |
| `monitor_port` | `/dev/ttyUSB*` | Auto-selects serial monitor port. | Use explicit port when target and RS485 adapter are both attached. | Monitor may attach to wrong device. |
| `monitor_speed` | `115200` | Must match `SERIAL_BAUD_RATE`. | Only if firmware serial baud changes too. | Garbled/no serial output. |

## `config.h` constants

### Serial communication

| Constant | Current value | Impact | When to change | Failure risk |
| --- | --- | --- | --- | --- |
| `SERIAL_BAUD_RATE` | `115200U` | UART baud rate for M2/D2 output. | Only if serial throughput is insufficient and host configs are updated. | Garbled output or bridge cannot parse. |

If this value changes, update:

- `platformio.ini` monitor speed,
- firmware setup docs,
- `LSL_Bridge` serial config,
- any operator scripts or launch commands.

### Calibration constants

| Constant | Current value | Impact | When to change | Failure risk |
| --- | --- | --- | --- | --- |
| `SCALE_FACTOR` | `1.0F` | Converts raw counts to `current_units` using `(raw_count - SCALE_OFFSET) / SCALE_FACTOR`. | After an accepted calibration report recommends firmware constants. | `current_units` wrong; if zero, status marks scale invalid and units become `nan`. |
| `SCALE_OFFSET` | `0.0F` | Offset used in firmware-side `current_units`. | After accepted calibration or tare strategy decision. | Biases `current_units`; raw count remains preserved. |

Important rule:

> Calibration fitting should use `raw_count`, not `current_units`, unless the workflow explicitly says it is validating already-deployed firmware constants.

### Sampling

| Constant | Current value | Impact | When to change | Failure risk |
| --- | --- | --- | --- | --- |
| `SAMPLING_PERIOD_US` | `5000U` | TimerOne ISR tick period, 5 ms / 200 Hz tick. | Only after reviewing HX711 readiness and FIFO/serial behavior. | More `HX711_NOTREADY`, FIFO pressure, or unnecessary ISR load. |
| `HX711_EXPECTED_OUTPUT_RATE_HZ` | `93.0F` | Metadata only; expected practical HX711 output rate. | If empirical HX711 output rate changes after hardware/config validation. | Misleading metadata, but not direct sampling behavior. |

Design intent:

- Timer tick is faster than actual HX711 sample availability.
- ISR checks `_scale.is_ready()` and returns without blocking if data is not ready.
- This makes timing irregularity visible through `status` instead of hiding it with blocking reads.

### Payload schema

| Constant | Current value | Impact | When to change | Failure risk |
| --- | --- | --- | --- | --- |
| `HANDGRIP_PAYLOAD_SCHEMA` | `2U` | Schema emitted in M2 metadata and expected by bridge/docs. | Only during deliberate protocol migration. | Bridge/parser/calibration incompatibility. |

Changing schema requires updating:

- `main.cpp` emit logic,
- `serial-protocol.md`,
- root `docs/architecture/stream-contracts.md`,
- `LSL_Bridge` parser/tests/config,
- viewer/calibration/analysis assumptions.

### Status bitfield

| Constant | Value | Meaning |
| --- | ---: | --- |
| `HANDGRIP_STATUS_OK` | `0x0000U` | No known problem for sample. |
| `HANDGRIP_STATUS_FIFO_OVERFLOW` | `0x0001U` | FIFO push failed because interrupt-to-loop buffer was full. |
| `HANDGRIP_STATUS_HX711_NOTREADY` | `0x0002U` | Timer tick occurred before HX711 was ready. |
| `HANDGRIP_STATUS_SCALE_INVALID` | `0x0004U` | Firmware unit conversion invalid, usually `SCALE_FACTOR == 0.0F`. |

### Metadata

| Constant | Current value | Impact |
| --- | --- | --- |
| `HANDGRIP_FORCE_UNIT` | `"N"` | Unit label in M2 metadata. |
| `HANDGRIP_FIRMWARE_VERSION` | `"2.0.0-calibration-schema"` | Human-readable firmware version in M2. |
| `HANDGRIP_FIRMWARE_GIT_SHA` | `"unknown"` by default | Build/source identifier; can be overridden at compile time. |

Optional compile-time SHA injection pattern:

```ini
build_flags = -DHANDGRIP_FIRMWARE_GIT_SHA=\"<git-sha>\"
```

Validate quoting in PlatformIO before relying on this in release builds.

## Private implementation constants in `main.cpp`

| Constant | Current value | Impact | When to change | Failure risk |
| --- | --- | --- | --- | --- |
| `GPIO_DATA_PIN` | `2U` | HX711 data pin. | Only if rewiring Arduino/HX711. | No readings if wrong. |
| `GPIO_CLOCK_PIN` | `3U` | HX711 clock pin. | Only if rewiring Arduino/HX711. | No readings if wrong. |
| `MAX_FIFO_SIZE` | `80U` | Usable FIFO depth for ISR-to-loop sample handoff. | Only if serial output or loop latency causes overflow. | Too small: overflow; too large: unnecessary SRAM use. |

## Safe configuration workflow

1. Change one firmware/config value at a time.
2. Build firmware.
3. Upload firmware.
4. Verify M2 metadata reflects expected constants.
5. Verify D2 output field count and status.
6. Run target-only quickstart through `LSL_Bridge`.
7. If calibration constants changed, run at least a validation/holdout workflow before trusting `current_units`.

## Validation commands

```bash
pio run -e nanoatmega328
pio run -e nanoatmega328 -t upload
pio device monitor -e nanoatmega328 -b 115200

rg "SCALE_FACTOR|SCALE_OFFSET|SAMPLING_PERIOD_US|HANDGRIP_PAYLOAD_SCHEMA" \
  Handgrip_Firmware/Core/Inc/config.h
```
