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

## Documentation map

| Document                                 | Purpose                                                                       |
| ---------------------------------------- | ----------------------------------------------------------------------------- |
| [Handgrip_Firmware/docs/workflow.md](workflow.md)               | Build, upload, and serial validation workflow                                 |
| [Handgrip_Firmware/docs/serial-protocol.md](serial-protocol.md) | Canonical M2/D2 schema, field meanings, status bitfield, parser contract      |
| [Handgrip_Firmware/docs/configuration.md](configuration.md)     | `config.h`, `platformio.ini`, sampling, scale factor, offset, safe-edit rules |
| [Handgrip_Firmware/docs/architecture.md](architecture.md)       | TimerOne acquisition, non-blocking HX711 polling, FIFO handoff, serial output |
| [Handgrip_Firmware/docs/troubleshooting.md](troubleshooting.md) | Upload errors, bootloader mismatch, serial permissions, no D2 output          |

## Reading guide

- To build and validate the firmware: [Handgrip_Firmware/docs/workflow.md](workflow.md)
- To understand the serial frame format: [Handgrip_Firmware/docs/serial-protocol.md](serial-protocol.md)
- To safely edit configuration constants: [Handgrip_Firmware/docs/configuration.md](configuration.md)
- To understand the firmware internals: [Handgrip_Firmware/docs/architecture.md](architecture.md)
- To diagnose build or upload failures: [Handgrip_Firmware/docs/troubleshooting.md](troubleshooting.md)

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
