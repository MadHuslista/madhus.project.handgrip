# Handgrip Firmware Documentation

## Summary

- `Handgrip_Firmware` is the Arduino Nano + HX711 firmware that owns target-side handgrip acquisition.
- It emits schema-2 serial output: `M2` metadata frames and `D2` sample frames over USB UART.
- `raw_count` is the calibration-authoritative target signal. `current_units` is a firmware-scaled convenience channel.
- Host-side ownership belongs to the Python suite: `LSL_Bridge` publishes LSL streams, `LSL_Viewer` visualizes, and `Handgrip_Calibration` fits calibration models.

## Firmware serial contract

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Minimum validation: `seq` increases monotonically, `raw_count` changes when force changes, `LSL_Bridge` can parse D2 frames and publish `HandgripTarget`.

## Reading guide

| I want to…                                               | Read                                                            |
| -------------------------------------------------------- | --------------------------------------------------------------- |
| Build, upload, and validate the firmware                 | [Handgrip_Firmware/docs/workflow.md](workflow.md)               |
| Understand the M2/D2 frames, fields, and status bitfield | [Handgrip_Firmware/docs/serial-protocol.md](serial-protocol.md) |
| Safely edit firmware constants                           | [Handgrip_Firmware/docs/configuration.md](configuration.md)     |
| Understand firmware internals (TimerOne, HX711, FIFO)    | [Handgrip_Firmware/docs/architecture.md](architecture.md)       |
| Diagnose build, upload, or no-D2 failures                | [Handgrip_Firmware/docs/troubleshooting.md](troubleshooting.md) |

## Related docs

- [docs/workflows/target-only-quickstart.md](../../docs/workflows/target-only-quickstart.md) — validates firmware → bridge → `HandgripTarget`
- [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md) — cross-component serial and stream contracts
- [docs/workflows/handgrip-calibration.md](../../docs/workflows/handgrip-calibration.md) — why `raw_count` is preserved for calibration

## Source map

| Source file              | Role                                                                              |
| ------------------------ | --------------------------------------------------------------------------------- |
| `Core/Src/main.cpp`      | Runtime firmware: setup, ISR sampling, FIFO pop/emit, frame emission              |
| `Core/Inc/config.h`      | Public firmware constants: baud, schema, sampling period, scale, offset, status   |
| `Core/Inc/fifo_buffer.h` | Fixed-size circular FIFO for interrupt-to-loop handoff                            |
| `../platformio.ini`      | Root PlatformIO project: board target, source/include paths, upload/monitor ports |

## Safe edit order

1. Read [Handgrip_Firmware/docs/configuration.md](configuration.md) before changing constants.
2. Read [Handgrip_Firmware/docs/serial-protocol.md](serial-protocol.md) before changing anything emitted over UART.
3. Read [Handgrip_Firmware/docs/architecture.md](architecture.md) before changing ISR/FIFO behavior.
4. After any schema change, update `LSL_Bridge`, root stream contracts, calibration docs, and tests together.
