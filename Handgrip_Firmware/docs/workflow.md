# Handgrip Firmware Workflow

## Summary

This document covers the complete firmware workflow: installing dependencies, building the firmware, uploading to the Arduino Nano, and validating serial output.

Build and upload are controlled by the root `platformio.ini`. Open the **repository root** in VS Code so PlatformIO resolves `src_dir` and `include_dir` correctly.

## Prerequisites

| Requirement | Expected |
| --- | --- |
| Host IDE | Visual Studio Code |
| VS Code extension | PlatformIO IDE |
| Repo open path | Repository root, not only `Handgrip_Firmware/` |
| Firmware target | Arduino Nano ATmega328 old bootloader |
| USB connection | Arduino Nano connected to host PC |

## 1 — Install VS Code and PlatformIO

Install Visual Studio Code and the PlatformIO IDE extension. After installation, reload VS Code and confirm the PlatformIO sidebar appears.

Open the **repository root** folder (`File → Open Folder...`). Confirm that `platformio.ini` is visible at the root alongside `README.md`, `docs/`, and the component directories.

Why this matters:

```ini
[platformio]
src_dir = Handgrip_Firmware/Core/Src
include_dir = Handgrip_Firmware/Core/Inc
```

These paths are relative to the root project. Opening only `Handgrip_Firmware/` causes build path failures.

## 2 — Confirm PlatformIO environment

Open `platformio.ini` and confirm:

```ini
[env:nanoatmega328]
platform = atmelavr
board = nanoatmega328
framework = arduino
```

If a `nanoatmega328new` environment exists, do not use it for the old-bootloader Nano. Use `nanoatmega328`.

## 3 — Review configuration before build

Before building, check `Handgrip_Firmware/Core/Inc/config.h` for:

- sampling period (`SAMPLING_PERIOD_MS`),
- serial baud rate (must match `LSL_Bridge` config),
- scale factor and offset constants (should only change when a new calibration is deployed).

See [Handgrip_Firmware/docs/configuration.md](configuration.md) before editing these values.

## 4 — Build

From the PlatformIO sidebar, select the `nanoatmega328` environment and run **Build**.

Or from terminal at the repository root:

```bash
pio run -e nanoatmega328
```

Expected result: build completes with no errors. Warnings about deprecated AVR headers are acceptable.

## 5 — Upload

Connect the Arduino Nano to the host PC over USB. From the PlatformIO sidebar, run **Upload** for the `nanoatmega328` environment.

Or from terminal:

```bash
pio run -e nanoatmega328 -t upload
```

Expected result: upload completes. The Arduino resets after upload.

Common failure: wrong COM port or driver. Check device manager (Windows) or `/dev/ttyUSB*` / `/dev/ttyACM*` (Linux/macOS).

## 6 — Validate serial output

Open a serial monitor at 115200 baud:

```bash
pio device monitor -e nanoatmega328
```

Expected output within the first few seconds:

```text
M2,<firmware_version>,<sampling_period_ms>,<scale_factor>,<scale_offset>
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
...
```

One `M2` metadata line near boot is followed by continuous `D2` sample lines. If `D2` lines do not appear, check the HX711 wiring and power.

See [Handgrip_Firmware/docs/serial-protocol.md](serial-protocol.md) for the full frame format.

## Stop conditions

Stop and troubleshoot if:

- build fails with a missing source path — reopen the repository root,
- upload fails with no port found — check USB connection and driver,
- serial monitor shows no output — check baud rate is 115200,
- serial monitor shows only `M2` lines and no `D2` lines — check HX711 power and wiring,
- `D2` lines show `raw_count` of zero continuously — HX711 DOUT/SCK wiring issue.

## Troubleshooting links

- [Handgrip_Firmware/docs/serial-protocol.md](serial-protocol.md)
- [Handgrip_Firmware/docs/configuration.md](configuration.md)
- [Handgrip_Firmware/docs/troubleshooting.md](troubleshooting.md)
- [docs/troubleshooting/serial-and-rs485.md](../../docs/troubleshooting/serial-and-rs485.md)
