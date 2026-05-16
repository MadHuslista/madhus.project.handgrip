# Firmware Configuration Reference

**Status:** Canonical root configuration reference  
**Component:** `Handgrip_Firmware`  
**Detailed component doc:** `Handgrip_Firmware/docs/configuration.md`  
**Config sources:** `platformio.ini`, `Handgrip_Firmware/Core/Inc/config.h`, selected private constants in `Core/Src/main.cpp`

## Summary

Firmware configuration controls the Arduino Nano build target, HX711 polling behavior, serial schema, serial baud rate, metadata, and firmware-side convenience scaling. `raw_count` remains calibration-authoritative; firmware scale/offset affect only `current_units`. The canonical data frame remains `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`.

## Configuration table

| Key                                      | Type          | Default                      | Allowed range / values                                                | Operational impact                                   | When to change                                                          | Failure risk                                                    |
| ---------------------------------------- | ------------- | ---------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------- |
| `platformio.env` / `[env:nanoatmega328]` | string        | `nanoatmega328`              | Valid PlatformIO environment name.                                    | Selects Arduino Nano old bootloader target.          | Only if hardware changes.                                               | Upload failure or wrong bootloader if changed incorrectly.      |
| `platformio.board`                       | string        | `nanoatmega328`              | Board ID supported by PlatformIO.                                     | Controls MCU/bootloader assumptions.                 | Only after confirming physical Nano bootloader variant.                 | Firmware upload fails or wrong timing assumptions.              |
| `SERIAL_BAUD_RATE`                       | unsigned int  | `115200U`                    | Must match host/bridge serial config.                                 | UART speed for `M2`/`D2` lines.                      | Only if serial throughput is insufficient and bridge config is updated. | Garbled/no serial output if host mismatch.                      |
| `HANDGRIP_PAYLOAD_SCHEMA`                | unsigned int  | `2U`                         | Current canonical value: `2`.                                         | Declares D2/M2 protocol schema.                      | Only during deliberate protocol migration.                              | Bridge/parser/calibration breakage if changed locally.          |
| `SAMPLING_PERIOD_US`                     | unsigned int  | `5000U`                      | Timer interval in microseconds; must respect HX711 conversion timing. | Sets TimerOne polling cadence.                       | Tune only with timing evidence.                                         | HX711 not-ready status, FIFO pressure, misleading nominal rate. |
| `HANDGRIP_EXPECTED_RATE_HZ`              | float         | `93.0F`                      | Metadata value; should match observed target rate.                    | Communicates expected target cadence to host tools.  | After empirical rate measurement.                                       | Bad operator expectations; not usually data loss.               |
| `SCALE_FACTOR`                           | float         | `1.0F`                       | Nonzero finite float.                                                 | Converts raw count to `current_units`.               | After accepted calibration if using firmware-side linear scaling.       | `current_units` wrong; raw count still valid.                   |
| `SCALE_OFFSET`                           | float         | `0.0F`                       | Finite float.                                                         | Offset used for `current_units`.                     | After accepted calibration if using firmware-side scaling.              | Biased displayed/derived value.                                 |
| `HANDGRIP_FORCE_UNIT`                    | string        | `N`                          | Unit label string.                                                    | Metadata label for `current_units`.                  | If deployment unit changes.                                             | Confusing reports/plots if inconsistent.                        |
| `HANDGRIP_STATUS_*` bit masks            | constants     | `0x0001`, `0x0002`, `0x0004` | Stable bitfield values.                                               | Flags FIFO overflow, HX711 not-ready, invalid scale. | Only during schema migration.                                           | Downstream status interpretation breaks.                        |
| HX711 `DAT` pin                          | code constant | `D2`                         | Valid Arduino digital pin.                                            | Reads HX711 data line.                               | Only if wiring changes.                                                 | No samples if wrong.                                            |
| HX711 `CLK` pin                          | code constant | `D3`                         | Valid Arduino digital pin.                                            | Clocks HX711.                                        | Only if wiring changes.                                                 | No samples or unstable data if wrong.                           |

## Critical rule

Changing firmware payload fields is not a local firmware edit. Update together:

1. firmware source/config,
2. `Handgrip_Firmware/docs/serial-protocol.md`,
3. `LSL_Bridge` parser/config/tests,
4. root `docs/architecture/stream-contracts.md`,
5. viewer/calibration/analysis docs that consume target channels.
