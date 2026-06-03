# Handgrip Firmware

## Summary

`Handgrip_Firmware` runs on the Arduino Nano target device. It reads the handgrip load-cell path through the HX711, emits schema-2 serial frames over USB UART, and provides the raw target signal consumed by `LSL_Bridge`.

Current firmware contract:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

`raw_count` is the calibration-authoritative target value. `current_units` is a firmware-scaled convenience value and should not replace raw-count fitting unless a workflow explicitly says so.

## First command

From the repository root:

```bash
platformio run -e nanoatmega328
```

Upload after a successful build:

```bash
platformio run -e nanoatmega328 -t upload
```

Open the serial monitor:

```bash
platformio device monitor --baud 115200
```

## Expected result

After upload and reset, the serial monitor should show one metadata line followed by D2 sample lines:

```text
M2,2,...
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Expected validation points:

- `seq` increases monotonically,
- `timestamp_us` increases over time,
- `raw_count` changes when force changes,
- `status` is usually `0` or only occasionally nonzero,
- downstream `LSL_Bridge` can publish `HandgripTarget`.

Stop if the serial monitor shows the deprecated legacy D-prefix frame instead of `D2`.

## Configuration

Primary configuration files:

| File                | Purpose                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| `Core/Inc/config.h` | Firmware constants: serial baud, payload schema, sampling period, scale factor, offset, status bits. |
| `Core/Src/main.cpp` | HX711 setup, TimerOne acquisition, FIFO handoff, M2/D2 emission.                                     |
| `../platformio.ini` | PlatformIO environment, board, dependencies, upload/monitor settings.                                |

Important constants:

| Constant / concept        | Meaning                                        |
| ------------------------- | ---------------------------------------------- |
| `SCALE_FACTOR`            | Firmware-side scale used for `current_units`.  |
| `SCALE_OFFSET`            | Firmware-side offset used for `current_units`. |
| `SAMPLING_PERIOD_US`      | Timer tick for non-blocking HX711 polling.     |
| `HANDGRIP_PAYLOAD_SCHEMA` | Current payload schema. Expected value: `2`.   |
| `HANDGRIP_FORCE_UNIT`     | Unit emitted in M2 metadata, normally `N`.     |

Full configuration reference is planned at [Handgrip_Firmware/docs/configuration.md](docs/configuration.md).

## Common workflows

| Goal                                        | Document                                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Build and upload firmware                   | [Handgrip_Firmware/docs/workflow.md](docs/workflow.md)                           |
| Understand D2/M2 serial output              | [Handgrip_Firmware/docs/serial-protocol.md](docs/serial-protocol.md)                                                   |
| Understand cross-component stream contracts | [docs/architecture/stream-contracts.md](../docs/architecture/stream-contracts.md)                 |
| Validate target-only stream path            | [docs/workflows/target-only-quickstart.md](../docs/workflows/target-only-quickstart.md)           |
| Run full live viewer workflow               | [docs/workflows/full-live-viewer-quickstart.md](../docs/workflows/full-live-viewer-quickstart.md) |

## Repository layout

```text
Handgrip_Firmware/
├── README.md
├── docs/
│   ├── index.md
│   └── serial-protocol.md
└── Core/
    ├── Inc/
    │   ├── config.h
    │   └── fifo_buffer.h
    └── Src/
        └── main.cpp
```

## Tests

There is no standalone firmware unit-test suite in this component. Validate firmware behavior through build/upload and serial output checks:

```bash
platformio run -e nanoatmega328
platformio run -e nanoatmega328 -t upload
platformio device monitor --baud 115200
```

Then verify D2 stream consumption through `LSL_Bridge` and the target-only quickstart.

## Further docs

- [Handgrip_Firmware/docs/index.md](docs/index.md) — firmware documentation map.
- [Handgrip_Firmware/docs/serial-protocol.md](docs/serial-protocol.md) — canonical M2/D2 serial protocol.
- [Handgrip_Firmware/docs/workflow.md](docs/workflow.md) — operator workflow.
- [docs/architecture/stream-contracts.md](../docs/architecture/stream-contracts.md) — root stream/data contracts.
