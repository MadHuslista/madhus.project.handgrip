# Firmware Setup Workflow

**Status:** Canonical operator workflow  
**Audience:** Operators and student maintainers  
**Scope:** VS Code + PlatformIO setup, build/upload, serial monitor, D2 validation  
**Related docs:** [`Handgrip_Firmware/README.md`](../../Handgrip_Firmware/README.md), [`Handgrip_Firmware/docs/serial-protocol.md`](../../Handgrip_Firmware/docs/serial-protocol.md)

## Summary

This workflow uploads the target firmware and verifies that the Arduino/HX711 handgrip device emits canonical D2 frames.

Required flow:

1. Install VS Code.
2. Install PlatformIO extension.
3. Open repo root, not only firmware subfolder.
4. Confirm `platformio.ini` and old Nano bootloader environment.
5. Build.
6. Upload.
7. Open serial monitor.
8. Verify D2 lines.

## Prerequisites

- Arduino Nano target connected by USB.
- PlatformIO extension installed in VS Code.
- Repository opened at the repo root.
- `platformio.ini` present at repo root.

## Step 1 — Install VS Code

- **Do:** Install Visual Studio Code.
- **Expected result:** VS Code opens the repository root.
- **Failure signal:** Opening only `Handgrip_Firmware/` hides root `platformio.ini` or docs.
- **Next branch:** Reopen the full repo root.

## Step 2 — Install PlatformIO extension

- **Do:** Install the PlatformIO IDE extension from VS Code extensions.
- **Expected result:** PlatformIO sidebar appears.
- **Failure signal:** No PlatformIO commands are available.
- **Next branch:** Reload VS Code and confirm the extension is enabled.

## Step 3 — Open repo root

- **Do:** Open the repository root directory.
- **Expected result:** `platformio.ini` is visible at the top level.
- **Failure signal:** PlatformIO cannot find an environment.
- **Next branch:** Use `File → Open Folder...` and select repo root.

## Step 4 — Confirm PlatformIO environment

- **Do:** Open `platformio.ini`.
- **Expected result:** It references the Arduino Nano / ATmega328P old bootloader environment.
- **Failure signal:** Environment does not match the connected target board.
- **Next branch:** Confirm board/bootloader before upload.

## Step 5 — Build firmware

From repo root:

```bash
platformio run
```

Or use VS Code PlatformIO Build.

- **Expected result:** Build succeeds.
- **Failure signal:** Missing library, wrong board, compile error.
- **Next branch:** Check PlatformIO environment and dependency installation.

## Step 6 — Upload firmware

From repo root:

```bash
platformio run --target upload
```

If multiple serial devices exist, specify upload port as needed in PlatformIO or CLI.

- **Expected result:** Upload completes and board resets.
- **Failure signal:** Sync error, permission error, wrong port, old bootloader mismatch.
- **Next branch:** Check port, user permissions, bootloader setting, USB cable.

## Step 7 — Open serial monitor

```bash
platformio device monitor --baud 115200
```

- **Expected result:** Firmware emits metadata and D2 sample lines.
- **Failure signal:** No output, garbled output, or non-D2 legacy output.
- **Next branch:** Confirm baud rate and firmware version.

## Step 8 — Verify D2 lines

Expected metadata:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

Expected data:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Field meanings:

| Field           | Meaning                                            |
| --------------- | -------------------------------------------------- |
| `seq`           | sample sequence number                             |
| `timestamp_us`  | device timestamp in microseconds                   |
| `raw_count`     | HX711 raw ADC count                                |
| `current_units` | firmware-scaled value                              |
| `status`        | status/bitfield for acquisition/scaling conditions |

## Stop conditions

Stop before live workflow if:

- serial monitor does not show D2 frames,
- lines show stale legacy `D,<seq>,...` format,
- sequence number is not monotonic,
- status indicates persistent acquisition failure,
- raw counts do not react to force.

## Troubleshooting links

- [`Handgrip_Firmware/docs/serial-protocol.md`](../../Handgrip_Firmware/docs/serial-protocol.md)
- [`docs/troubleshooting/serial-and-rs485.md`](../troubleshooting/serial-and-rs485.md)
- [`docs/architecture/stream-contracts.md`](../architecture/stream-contracts.md)
