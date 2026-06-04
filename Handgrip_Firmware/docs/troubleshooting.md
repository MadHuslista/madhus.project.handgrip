# Handgrip Firmware Troubleshooting

## Summary

Use this document when firmware build/upload or target serial validation fails.

Most firmware-side handoff failures fall into one of these buckets:

1. PlatformIO project opened from the wrong directory.
2. Wrong Arduino Nano bootloader/board environment.
3. Serial port selection or permissions problem.
4. Firmware uploaded but no valid D2 output appears.
5. HX711 not wired or not ready.
6. FIFO/status bits indicate runtime pressure.
7. Firmware constants produce invalid `current_units`.

## Fast triage table

| Symptom                             | Likely cause                                                        | First action                                                    |
| ----------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------- |
| PlatformIO cannot find project      | VS Code opened `Handgrip_Firmware/` instead of repo root            | Reopen repository root.                                         |
| Build cannot find `config.h`        | root `platformio.ini` not loaded or include path wrong              | Confirm root `platformio.ini`.                                  |
| Upload sync error                   | Wrong bootloader or wrong serial port                               | Confirm `board = nanoatmega328`; select correct port.           |
| Permission denied on `/dev/ttyUSB*` | Linux serial permissions                                            | Add user to `dialout` or use appropriate udev/permissions flow. |
| Serial monitor blank                | wrong port, wrong baud, firmware not running                        | Monitor at `115200`; reset board; confirm target port.          |
| Garbled serial output               | baud mismatch or wrong device                                       | Confirm `SERIAL_BAUD_RATE` and monitor speed.                   |
| No D2 lines                         | old firmware, wrong monitor device, firmware stuck, HX711 not ready | Rebuild/upload and inspect status/metadata.                     |
| `current_units` is `nan`            | invalid scale factor                                                | Check `SCALE_FACTOR`; use `raw_count` for calibration.          |
| Frequent FIFO overflow status       | serial/loop cannot drain samples fast enough                        | Check host monitor/bridge load and FIFO depth.                  |

## Upload errors

### Symptom

```text
avrdude: stk500_recv(): programmer is not responding
```

### Likely causes

- wrong serial port,
- serial monitor already open,
- wrong bootloader profile,
- bad USB cable,
- board not powered or not resettable.

### Fix workflow

1. Close serial monitor and any bridge process using the port.
2. Identify the target device:

```bash
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

3. Confirm `platformio.ini` uses:

```ini
board = nanoatmega328
```

4. Upload explicitly:

```bash
pio run -e nanoatmega328 -t upload --upload-port /dev/ttyUSB_TARGET
```

## Old bootloader mismatch

The expected board environment is:

```ini
[env:nanoatmega328]
board = nanoatmega328
```

Do not switch to a new-bootloader Nano environment unless the physical board is replaced and validated.

Failure pattern:

- compile succeeds,
- upload fails with sync/timeout errors,
- different board profiles behave inconsistently.

Fix:

- keep `nanoatmega328`,
- use explicit upload port,
- verify cable and board reset behavior.

## Serial port permissions

### Symptom

```text
Permission denied: /dev/ttyUSB0
```

### Linux checks

```bash
groups
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

Typical fix on Debian/Ubuntu/Linux Mint-style systems:

```bash
sudo usermod -aG dialout "$USER"
```

Then log out and log back in.

Temporary test only:

```bash
sudo chmod a+rw /dev/ttyUSB0
```

Do not rely on temporary permissions as the permanent lab setup.

## No D2 output

### Symptom

Serial monitor opens but no valid D2 lines appear.

### Checks

1. Confirm baud:

```bash
pio device monitor -e nanoatmega328 -b 115200
```

2. Press/reset the Arduino and look for:

```text
M2,2,...
```

3. Confirm the monitor is attached to the Arduino, not the USB-RS485 adapter.
4. Rebuild/upload current firmware.
5. Inspect HX711 wiring and power.

### Possible causes

| Cause               | Evidence                                   | Fix                                   |
| ------------------- | ------------------------------------------ | ------------------------------------- |
| wrong serial port   | no M2; RS485 noise/board data instead      | use `/dev/serial/by-id/` target path. |
| wrong baud          | garbled text                               | use `115200`.                         |
| old firmware        | output does not use D2                     | rebuild/upload.                       |
| firmware reset loop | repeated M2, no stable D2                  | inspect power/wiring/source changes.  |
| HX711 never ready   | M2 appears but no samples or status issues | inspect HX711 pins/load cell wiring.  |

## Status-bit diagnosis

| Status bit | Meaning         | Likely cause                                      | Action                                                                                                   |
| ---------: | --------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
|   `0x0000` | OK              | Normal sample                                     | Continue.                                                                                                |
|   `0x0001` | FIFO overflow   | main loop/serial emission cannot keep up          | reduce host blocking, close slow monitor, inspect bridge load, consider FIFO depth only after measuring. |
|   `0x0002` | HX711 not ready | timer tick occurred before HX711 conversion ready | occasional is expected; persistent means rate/wiring/HX711 issue.                                        |
|   `0x0004` | scale invalid   | `SCALE_FACTOR == 0.0F` or invalid unit conversion | fix `SCALE_FACTOR`; trust `raw_count` over `current_units`.                                              |

## Raw count does not change under force

Likely causes:

- load cell not wired to HX711,
- HX711 data/clock pins wrong,
- target mechanical force path not loading the sensor,
- board powered but target sensor not powered,
- wrong device is being monitored.

Validation:

```bash
pio device monitor -e nanoatmega328 -b 115200
```

Watch `raw_count` while applying small force. If `raw_count` is flat, this is not a calibration-model problem yet; validate mechanics and HX711 wiring first.

## `current_units` looks wrong but `raw_count` works

This usually means firmware constants are not calibrated yet.

Expected during early bring-up:

```c
#define SCALE_FACTOR 1.0F
#define SCALE_OFFSET 0.0F
```

In this state, `current_units` is only a placeholder/sanity value. Continue calibration with `raw_count` and update firmware constants only after an accepted report/holdout validation.

## Bridge cannot parse target output

If `LSL_Bridge` drops target lines:

1. Open serial monitor directly.
2. Confirm D2 field count:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

3. Confirm there are no extra commas or missing fields.
4. Confirm bridge parser docs and firmware docs agree.
5. Run bridge parser tests if available.

## Stop conditions

Stop firmware-side debugging and escalate before calibration if:

- upload cannot be made reproducible,
- serial output is not D2,
- `raw_count` is static under real force,
- status bits are persistently nonzero and unexplained,
- bridge parser fails on direct firmware output,
- firmware constants were changed without documenting the build.

## Useful commands

```bash
# Build
pio run -e nanoatmega328

# Upload
pio run -e nanoatmega328 -t upload

# Monitor
pio device monitor -e nanoatmega328 -b 115200

# Identify serial devices
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true

```
