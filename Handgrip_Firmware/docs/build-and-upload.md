# Firmware Build and Upload

## Summary

- Build/upload is controlled by the root `platformio.ini`, not by a `platformio.ini` inside `Handgrip_Firmware/`.
- Open the **repository root** in VS Code so PlatformIO can resolve the correct `src_dir` and `include_dir`.
- The expected PlatformIO environment is `nanoatmega328`, using `platform = atmelavr`, `board = nanoatmega328`, and `framework = arduino`.
- The current target uses the Arduino Nano ATmega328 **old bootloader** environment.
- A successful upload must be followed by serial validation: one `M2` line near boot and continuous `D2` sample lines.

## Prerequisites

| Requirement           | Expected                                        |
| --------------------- | ----------------------------------------------- |
| Host IDE              | Visual Studio Code.                             |
| VS Code extension     | PlatformIO IDE.                                 |
| Repo open path        | Repository root, not only `Handgrip_Firmware/`. |
| Firmware target       | Arduino Nano ATmega328 old bootloader.          |
| Firmware source path  | `Handgrip_Firmware/Core/Src`.                   |
| Firmware include path | `Handgrip_Firmware/Core/Inc`.                   |
| USB connection        | Arduino Nano connected to host PC.              |

## Step 1 — Install VS Code

- **Do:** Install Visual Studio Code.
- **Expected result:** VS Code opens normally and can open the repository root folder.
- **Failure signal:** You only see individual component files and cannot see root `platformio.ini`.
- **Next branch:** Reopen the full repository root with `File → Open Folder...`.

## Step 2 — Install PlatformIO extension

- **Do:** Install the official `PlatformIO IDE` extension in VS Code.
- **Expected result:** PlatformIO sidebar appears and PlatformIO project tasks become available.
- **Failure signal:** No PlatformIO tasks, no PlatformIO sidebar, or build commands unavailable.
- **Next branch:** Reload VS Code and confirm the extension is enabled.

## Step 3 — Open repository root

- **Do:** Open the repository root directory.
- **Expected result:** root `platformio.ini` is visible next to `README.md`, `docs/`, and the component directories.
- **Failure signal:** PlatformIO reports no project, or build paths do not resolve.
- **Next branch:** Close folder and reopen the root directory.

Why this matters:

```ini
[platformio]
src_dir = Handgrip_Firmware/Core/Src
include_dir = Handgrip_Firmware/Core/Inc
```

Those paths are defined relative to the root PlatformIO project.

## Step 4 — Confirm PlatformIO environment

Open `platformio.ini` and confirm:

```ini
[env:nanoatmega328]
platform = atmelavr
board = nanoatmega328
framework = arduino
```

Expected dependencies:

```ini
lib_deps =
    robtillaart/HX711@^0.6.3
    paulstoffregen/TimerOne@^1.2
```

Expected serial settings:

```ini
upload_port = /dev/ttyUSB*
monitor_port = /dev/ttyUSB*
monitor_speed = 115200
```

## Step 5 — Identify the serial port

Linux quick check:

```bash
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

Prefer stable `/dev/serial/by-id/...` paths when multiple USB serial devices are attached.

## Step 6 — Build firmware

From repository root:

```bash
pio run -e nanoatmega328
```

If your shell exposes the long command name instead of `pio`, use:

```bash
platformio run -e nanoatmega328
```

VS Code alternative:

```text
PlatformIO sidebar → Project Tasks → nanoatmega328 → General → Build
```

Expected result:

- dependencies resolve,
- firmware compiles,
- no missing `HX711`, `TimerOne`, `config.h`, or `fifo_buffer.h` errors.

## Step 7 — Upload firmware

From repository root:

```bash
pio run -e nanoatmega328 -t upload
```

If multiple serial devices are connected, specify the upload port:

```bash
pio run -e nanoatmega328 -t upload --upload-port /dev/ttyUSB_TARGET
```

VS Code alternative:

```text
PlatformIO sidebar → Project Tasks → nanoatmega328 → General → Upload
```

Expected result:

- upload completes,
- board resets,
- serial monitor can connect at `115200` baud.

## Step 8 — Open serial monitor

```bash
pio device monitor -e nanoatmega328 -b 115200
```

If needed, specify the port explicitly:

```bash
pio device monitor -p /dev/ttyUSB_TARGET -b 115200
```

Expected boot metadata:

```text
M2,2,...
```

Expected data frames:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

## Step 9 — Validate D2 output

Checklist:

| Check          | Expected result                                                  |
| -------------- | ---------------------------------------------------------------- |
| Metadata       | One `M2` line appears near boot/reset.                           |
| Schema         | `M2` schema field is `2`.                                        |
| Data prefix    | Sample lines start with `D2,`.                                   |
| Field count    | Each D2 line has six comma-separated fields.                     |
| `seq`          | Increases monotonically.                                         |
| `timestamp_us` | Increases over time.                                             |
| `raw_count`    | Changes when force changes.                                      |
| `status`       | Usually `0`; persistent nonzero status requires troubleshooting. |

## Stop conditions

Stop before running `LSL_Bridge` if:

- build fails,
- upload fails,
- serial monitor is blank,
- output is garbled at `115200`,
- firmware emits legacy D-prefix frames instead of D2,
- `raw_count` does not change under force,
- `status` is persistently nonzero.

## Common command block

```bash
# From repository root
pio run -e nanoatmega328
pio run -e nanoatmega328 -t upload
pio device monitor -e nanoatmega328 -b 115200
```

## Next steps

- If D2 output is valid, run the target-only quickstart: `docs/workflows/target-only-quickstart.md`.
- If upload or serial validation fails, use [`troubleshooting.md`](troubleshooting.md).
- If you need to interpret D2 fields, use [`serial-protocol.md`](serial-protocol.md).
