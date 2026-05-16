# Handgrip Firmware

## Summary

- This firmware runs on an Arduino Nano ATmega328 connected to an HX711 load-cell amplifier.
- It samples the target handgrip load-cell path and streams calibration-ready serial frames over UART.
- The current protocol is **schema 2**: `M2` metadata frames plus strict `D2` data frames.
- `raw_count` is always emitted and is the calibration-authoritative target signal.
- Host-side calibration, fitting, reporting, stream publication, and analysis belong to the Python tools, not to the firmware.

## Status

| Field                 | Value                                       |
| --------------------- | ------------------------------------------- |
| Component             | `Handgrip_Firmware`                         |
| Board                 | Arduino Nano ATmega328, old bootloader      |
| Framework             | PlatformIO + Arduino                        |
| HX711 pins            | `DAT = D2`, `CLK = D3`                      |
| Serial baud           | `115200`                                    |
| Current serial schema | `M2` + `D2`                                 |
| Detailed protocol doc | `Handgrip_Firmware/docs/serial-protocol.md` |

## When to use this component

Use this component when you need to:

- build or upload firmware to the target handgrip Arduino,
- validate raw target sensor output,
- update firmware calibration constants after an accepted calibration report,
- debug target-side timing/status issues,
- modify the low-level HX711 acquisition path.

Do not use this component to:

- run calibration protocols,
- segment static holds,
- fit calibration models,
- publish Lab Streaming Layer streams,
- visualize target/reference correlation.

Those are handled by the host-side Python components.

## Source layout

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

Important files:

| File                     | Purpose                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------- |
| `Core/Src/main.cpp`      | HX711 setup, TimerOne sampling, FIFO handoff, `M2`/`D2` UART emission.                |
| `Core/Inc/config.h`      | Serial rate, scale constants, sampling period, payload schema, status bits, metadata. |
| `Core/Inc/fifo_buffer.h` | FIFO used to decouple interrupt capture from serial output.                           |
| `../platformio.ini`      | PlatformIO environment, dependencies, upload/monitor settings.                        |

## Prerequisites

Install the required VS Code extension:

1. Install Visual Studio Code.
2. Open the Extensions view.
3. Install the official `PlatformIO IDE` extension published by `PlatformIO`.

You do not need to install PlatformIO Core separately when using the VS Code extension.

## Open and configure the project in VS Code

Open the **repository root** in VS Code, not only `Handgrip_Firmware/`.

PlatformIO reads the project configuration from the root file:

```text
platformio.ini
```

The current project environment is:

| Field       | Value                  |
| ----------- | ---------------------- |
| Environment | `nanoatmega328`        |
| Platform    | `atmelavr`             |
| Framework   | `arduino`              |
| Board       | Arduino Nano ATmega328 |

Important: this project uses the Arduino Nano variant with the **old bootloader**. Keep the board as `nanoatmega328`. Do not switch to the PlatformIO board labeled `Arduino Nano ATmega328 (New Bootloader)` unless the physical board has been replaced and validated.

## Runtime defaults

| Setting                             | Current value        | Source              |
| ----------------------------------- | -------------------- | ------------------- |
| HX711 data pin                      | Arduino `D2`         | `Core/Src/main.cpp` |
| HX711 clock pin                     | Arduino `D3`         | `Core/Src/main.cpp` |
| Serial baud                         | `115200`             | `Core/Inc/config.h` |
| Sampling period                     | `5000 us` timer tick | `Core/Inc/config.h` |
| Expected HX711 output rate metadata | `93.0 Hz`            | `Core/Inc/config.h` |
| Payload schema                      | `2`                  | `Core/Inc/config.h` |

The firmware polls the HX711 in a non-blocking timer interrupt. A timer tick does not guarantee a new sample; if the HX711 is not ready, the firmware records a status bit and returns without blocking.

## Firmware workflow

### 1. Review calibration constants

Before building, open:

```text
Handgrip_Firmware/Core/Inc/config.h
```

Review:

| Constant              | Meaning                                                |
| --------------------- | ------------------------------------------------------ |
| `SCALE_FACTOR`        | Firmware scaling factor used only for `current_units`. |
| `SCALE_OFFSET`        | Firmware offset used only for `current_units`.         |
| `SAMPLING_PERIOD_US`  | Timer tick period for non-blocking HX711 polling.      |
| `HANDGRIP_FORCE_UNIT` | Unit label emitted in `M2` metadata.                   |

During calibration, `raw_count` remains the authoritative target signal even if `SCALE_FACTOR` and `SCALE_OFFSET` are still placeholders.

### 2. Confirm PlatformIO environment

From the repository root, inspect:

```text
platformio.ini
```

Expected environment:

```ini
[env:nanoatmega328]
platform = atmelavr
board = nanoatmega328
framework = arduino
```

Expected dependencies:

- `robtillaart/HX711@^0.6.3`
- `paulstoffregen/TimerOne@^1.2`

PlatformIO installs them automatically during the first build.

### 3. Build the project

Command-line build from the repository root:

```bash
pio run -e nanoatmega328
```

VS Code alternatives:

- click the PlatformIO `Build` checkmark,
- or run `Project Tasks > nanoatmega328 > General > Build`.

### 4. Connect the Arduino Nano

Connect the Arduino Nano by USB.

Linux-style serial examples:

```text
/dev/ttyUSB0
/dev/ttyACM0
```

The project currently uses wildcard-style PlatformIO serial settings. If needed, update `platformio.ini` to the specific connected port.

### 5. Upload firmware

Command-line upload:

```bash
pio run -e nanoatmega328 -t upload
```

VS Code alternatives:

- click the PlatformIO `Upload` arrow,
- or run `Project Tasks > nanoatmega328 > General > Upload`.

If upload fails immediately, re-check:

- board uses the old bootloader,
- serial port is correct,
- no other process has the serial port open.

### 6. Open the serial monitor

```bash
pio device monitor -b 115200
```

Expected metadata frame near boot:

```text
M2,2,2.0.0-calibration-schema,unknown,93.000,1.000000000,0.000,N
```

Expected data frames while running:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Example:

```text
D2,42,1234567,-842133,12.345678,0
```

If you see legacy lines like this, the firmware or documentation is stale:

```text
legacy D-prefix three-field value frame
```

Do not update downstream tools for the legacy schema unless you are intentionally supporting old recordings.

## Current serial protocol

See the detailed protocol reference:

```text
Handgrip_Firmware/docs/serial-protocol.md
```

Current data frame:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Field summary:

| Field           | Meaning                                                     |
| --------------- | ----------------------------------------------------------- |
| `seq`           | Monotonic sample sequence number.                           |
| `timestamp_us`  | Device timestamp in microseconds from `micros()`.           |
| `raw_count`     | HX711 raw ADC count before firmware scale/offset.           |
| `current_units` | Current scaled force/value according to firmware constants. |
| `status`        | Acquisition status bitfield.                                |

Status bit summary:

| Bit mask | Meaning                          |
| -------: | -------------------------------- |
| `0x0000` | OK.                              |
| `0x0001` | FIFO overflow.                   |
| `0x0002` | HX711 not ready on a timer tick. |
| `0x0004` | Scale conversion invalid.        |

## Hardware connections

Current topology:

- Arduino Nano with old bootloader,
- HX711 load-cell amplifier,
- load cell connected to HX711,
- host PC connected to Arduino over USB serial.

### HX711 module to Arduino Nano

| HX711 pin | Arduino Nano pin |
| --------- | ---------------- |
| `VCC`     | `5V`             |
| `DAT`     | `D2`             |
| `CLK`     | `D3`             |
| `GND`     | `GND`            |

### Load cell to HX711 module

Use the wiring for the active target handgrip hardware revision. Older exploratory HX710B/ADC photos are not canonical for the current handoff path unless specifically restored by a maintainer.

## Expected build and runtime result

After the environment is configured correctly:

1. PlatformIO resolves the `HX711` and `TimerOne` dependencies.
2. The project builds for `env:nanoatmega328`.
3. The firmware uploads to the Arduino Nano over USB.
4. The serial monitor shows one `M2` line near boot.
5. The serial monitor shows continuous `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>` lines at `115200` baud.
6. `LSL_Bridge` can parse the target stream and publish `HandgripTarget`.

## Troubleshooting

| Symptom                       | Likely cause                                  | First check                                                |
| ----------------------------- | --------------------------------------------- | ---------------------------------------------------------- |
| Upload fails                  | Wrong bootloader/port                         | Confirm `nanoatmega328`, serial port, and no open monitor. |
| No serial output              | Firmware not running or wrong baud            | Open monitor at `115200`; reset board.                     |
| Only legacy `D,` lines appear | Old firmware image or stale branch            | Rebuild/upload current firmware.                           |
| Bridge drops target lines     | Malformed D2 schema or wrong firmware         | Compare serial monitor against `docs/serial-protocol.md`.  |
| Frequent nonzero status       | HX711 not ready, FIFO pressure, invalid scale | Inspect `status` bitfield and host serial consumption.     |
| `current_units` is `nan`      | Invalid scale factor                          | Check `SCALE_FACTOR`; use `raw_count` for calibration.     |

## Further documentation

| Goal                             | Document                                    |
| -------------------------------- | ------------------------------------------- |
| Understand D2/M2 serial protocol | `Handgrip_Firmware/docs/serial-protocol.md` |
| Understand root stream contracts | `docs/architecture/stream-contracts.md`     |
| Understand bridge output         | `LSL_Bridge/docs/stream-contracts.md`       |
| Run calibration workflow         | `docs/workflows/handgrip-calibration.md`    |
