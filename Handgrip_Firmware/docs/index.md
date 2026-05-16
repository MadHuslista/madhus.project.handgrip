# Handgrip Firmware Documentation

## Summary

- `Handgrip_Firmware` is the Arduino Nano + HX711 firmware that owns target-side handgrip acquisition.
- It emits schema-2 serial output over USB UART: `M2` metadata frames and strict `D2` sample frames.
- `raw_count` is the calibration-authoritative target signal. `current_units` is a firmware-scaled sanity/convenience channel.
- The firmware should remain simple: acquire raw samples, timestamp them, expose status, and stream them to the host.
- Host-side ownership belongs to the Python suite: `LSL_Bridge` publishes LSL streams, `LSL_Viewer` visualizes, and `Handgrip_Calibration` fits calibration models.

## Audience

| Reader | Use this docs section to... |
| --- | --- |
| Operator | Build/upload firmware and verify D2 serial output. |
| Student maintainer | Understand safe configuration values before editing `config.h`. |
| Firmware developer | Understand acquisition, FIFO handoff, serial emission, and status bits. |
| Calibration maintainer | Verify that firmware output preserves raw-count traceability. |

## Firmware contract

Current firmware serial contract:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Minimum validation points:

- `payload_schema` is `2`.
- `seq` increases monotonically.
- `timestamp_us` increases over time.
- `raw_count` changes when force changes.
- `status` is usually `0` or only occasionally nonzero.
- `LSL_Bridge` can parse D2 frames and publish `HandgripTarget`.

## Documentation map

| Document | Purpose |
| --- | --- |
| [`build-and-upload.md`](build-and-upload.md) | PlatformIO extension, root-open requirement, build/upload/monitor workflow, old Nano bootloader notes. |
| [`serial-protocol.md`](serial-protocol.md) | Canonical M2/D2 schema, field meanings, examples, status bitfield, parser contract. |
| [`configuration.md`](configuration.md) | `config.h`, `platformio.ini`, sampling, calibration mode, scale factor, offset, and safe-edit rules. |
| [`architecture.md`](architecture.md) | TimerOne acquisition, non-blocking HX711 polling, FIFO handoff, serial output, and dependency boundaries. |
| [`troubleshooting.md`](troubleshooting.md) | Upload errors, old bootloader mismatch, serial permissions, no D2 output, status-bit diagnosis. |

## Related root docs

| Root doc | Why it matters |
| --- | --- |
| [`../../docs/workflows/firmware-setup.md`](../../docs/workflows/firmware-setup.md) | Operator-level firmware setup workflow. |
| [`../../docs/workflows/target-only-quickstart.md`](../../docs/workflows/target-only-quickstart.md) | Validates firmware → bridge → `HandgripTarget` without the reference chain. |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Root cross-component stream and serial contracts. |
| [`../../docs/architecture/dataflow.md`](../../docs/architecture/dataflow.md) | Places firmware output in the full system dataflow. |
| [`../../docs/workflows/handgrip-calibration.md`](../../docs/workflows/handgrip-calibration.md) | Explains why `raw_count` is preserved for calibration fitting. |

## Source map

| Source file | Role |
| --- | --- |
| `Core/Src/main.cpp` | Runtime firmware: setup, ISR sampling, FIFO pop/emit, metadata/data frame emission. |
| `Core/Inc/config.h` | Public firmware constants: serial baud, schema, sampling period, scale factor, offset, status bits, metadata. |
| `Core/Inc/fifo_buffer.h` | Fixed-size circular FIFO used for interrupt-to-loop handoff. |
| `../platformio.ini` | Root PlatformIO project configuration, board target, source/include paths, dependencies, upload/monitor ports. |

## Safe edit order

1. Read [`configuration.md`](configuration.md) before changing constants.
2. Read [`serial-protocol.md`](serial-protocol.md) before changing anything emitted over UART.
3. Read [`architecture.md`](architecture.md) before changing ISR/FIFO behavior.
4. After any firmware change, run the validation checklist in [`build-and-upload.md`](build-and-upload.md).
5. If the serial schema changes, update `LSL_Bridge`, root stream contracts, calibration docs, and tests in the same branch.

## Validation checklist

```bash
# From repository root
pio run -e nanoatmega328
pio run -e nanoatmega328 -t upload
pio device monitor -e nanoatmega328 -b 115200

# Documentation/schema sanity
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" \
  Handgrip_Firmware README.md docs LSL_Bridge
```
