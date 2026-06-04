# Serial and RS485 Troubleshooting

## Summary
**Symptoms covered:** No serial port, wrong A/B, baud mismatch, no Active-Send frames

**Prerequisite:** [docs/troubleshooting/hardware-and-wiring.md](hardware-and-wiring.md) — confirm board powers on and force path is valid before debugging serial.

Use this guide when the host PC cannot see the Arduino target or USB-RS485 adapter, or when `RS485_GUI` cannot receive acquisition-board frames.

## Symptom: no serial port

### Checks

```bash
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
dmesg | tail -80
```

### Likely causes

| Cause                   | Fix                                                                 |
| ----------------------- | ------------------------------------------------------------------- |
| USB cable is power-only | Use a known data-capable USB cable.                                 |
| Device permissions      | Add user to `dialout` or use udev rules; re-login.                  |
| Adapter not enumerating | Try another USB port/cable.                                         |
| Port occupied           | Close serial monitor, GUI, bridge, or other process using the port. |

## Symptom: wrong A/B wiring

### Signs

- Adapter appears, but no valid RS485 frames arrive.
- Board display works locally.
- Modbus polling times out.
- Active-Send parser sees nothing or continuous malformed data.

### Fix

Power down if required by lab practice, then swap A/B on the RS485 adapter side and retry.

Typical mapping:

| Board | Adapter |
| ----- | ------- |
| A+    | A / D+  |
| B-    | B / D-  |

## Symptom: baud mismatch

### Signs

- Garbled serial output.
- Parser receives bytes but no valid frames.
- Modbus CRC errors.
- Active-Send payloads appear with wrong length or invalid values.

### Fix

Ensure acquisition board communication menu and `RS485_GUI/config/config.yaml` agree on:

- baud rate,
- parity,
- stop bits,
- device address when using Modbus,
- Active-Send enabled/disabled state.

## Symptom: no Active-Send frames

### Likely causes

| Cause                            | Fix                                                             |
| -------------------------------- | --------------------------------------------------------------- |
| Active-Send not enabled on board | Enable vendor Active-Send mode from board menu.                 |
| Wrong output rate                | Set a supported rate, typically 500 Hz for calibration profile. |
| Wrong serial profile             | Align baud/parity/stop bits.                                    |
| Wrong parser profile             | Update `RS485_GUI/config/config.yaml`.                          |
| A/B swapped                      | Swap RS485 pair and retry.                                      |

## Fallback path

If Active-Send is unstable, validate the chain with Modbus RTU polling first. Polling is slower and introduces jitter on the sampling rate, but easier to debug.


**Related docs:** [docs/workflows/target-only-quickstart.md](../workflows/target-only-quickstart.md), [docs/workflows/reference-only-quickstart.md](../workflows/reference-only-quickstart.md), [RS485_GUI/docs/active-send-and-modbus.md](../../RS485_GUI/docs/active-send-and-modbus.md)
