# Physical Setup Workflow

## Summary

This workflow brings the physical system from disconnected hardware to a validated force path ready for software acquisition.

Required flow:

1. Identify hardware.
2. Wire PM58 to acquisition board.
3. Wire target handgrip / Arduino / HX711.
4. Wire RS485 adapter.
5. Apply power safely.
6. Validate acquisition-board display.
7. Validate host serial ports.
8. Validate force path with screw press.

## Prerequisites

- PM58 reference load cell.
- High-speed acquisition board.
- Arduino Nano target handgrip firmware device with HX711 path.
- USB-RS485 adapter.
- Host PC.
- Screw press / controlled-force fixture if running calibration.
- Canonical images under `docs/hardware/assets/`.

## Step 1 — Identify hardware

Checklist:

| Item                | Expected                                                                 |
| ------------------- | ------------------------------------------------------------------------ |
| PM58 load cell      | Label visible and range known.                                           |
| Acquisition board   | Rear terminal map visible.                                               |
| Arduino target      | USB serial cable available.                                              |
| HX711 wiring        | Connected to target load cell path (internally done within the Handgrip) |
| USB-RS485 adapter   | A/B or D+/D- terminals visible.                                          |
| Screw press fixture | Stable mechanical alignment possible.                                    |

## Step 2 — Wire PM58 to acquisition board

- **Do:** Wire the PM58 bridge leads to the acquisition board sensor terminals.
- **Expected result:** PM58 is connected to excitation and signal terminals.
- **Failure signal:** Reading is saturated, frozen, very noisy, or sign-inverted unexpectedly.
- **More info:** Use [docs/hardware/pm58-wiring-and-bringup.md](../hardware/pm58-wiring-and-bringup.md).

Canonical mapping:

| PM58 wire    | Function     | Board terminal                                         |
| ------------ | ------------ | ------------------------------------------------------ |
| Red          | excitation + | `E+`                                                   |
| Black        | excitation - | `E-`                                                   |
| Green        | signal +     | `S+`                                                   |
| White        | signal -     | `S-`                                                   |
| Shield/drain | shield       | isolate initially unless grounding plan says otherwise |

## Step 3 — Wire target Handgrip  (Arduino / HX711)

- **Do:** Connect the Handgrip USB serial cable, and review it's output with a serial monitor.
- **Expected result:** Arduino powers over USB and firmware emits D2 frames after upload.
- **Failure signal:** No serial device appears, no D2 frames appear, or status indicates acquisition faults.
- **More info:** 
  - Use [Handgrip_Firmware/docs/workflow.md](../../Handgrip_Firmware/docs/workflow.md) to upload a new firmware
  - and [Handgrip_Firmware/docs/serial-protocol.md](../../Handgrip_Firmware/docs/serial-protocol.md) to understand the D2 frames.

Minimum validation:

```bash
# Identify possible serial devices
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

## Step 4 — Wire RS485 adapter

- **Do:** Connect acquisition-board RS485 terminals to the USB-RS485 adapter.
- **Expected result:** Host PC sees a second serial device for the RS485 adapter.
- **Failure signal:** GUI cannot read board; adapter appears but no data arrives.
- **Next branch:** Swap A/B once if all software settings are correct.

Typical mapping:

| Board | Adapter |
| ----- | ------- |
| A+    | A / D+  |
| B-    | B / D-  |

## Step 5 — Apply power safely

- **Do:** Apply acquisition-board power only after sensor and RS485 wiring are secure.
- **Expected result:** Board display turns on and exits startup state.
- **Failure signal:** No display, smell/heat/noise, flickering power, or unstable terminal wiring.
- **Next branch:** Disconnect power immediately and inspect wiring.

Safety rules:

- Do not move wires while powered.
- Do not open the board enclosure while powered.
- Keep mains wiring physically separated from sensor and RS485 wiring.
- Use a switch/fused power strip or equivalent safe disconnect.

## Step 6 — Validate acquisition-board display

- **Do:** Observe the front display under no-load and small-load conditions.
- **Expected result:** Display changes consistently when force is applied to PM58.
- **Failure signal:** Display remains frozen, shows overload, or changes randomly.
- **Next branch:** Re-check PM58 wiring and board menu configuration.

## Step 7 — Validate host serial ports

- **Do:** Identify which device is Arduino target and which is USB-RS485 adapter.
- **Expected result:** Two stable device paths are known.
- **Failure signal:** Only one device appears or device numbers change unpredictably.
- **Next branch:** Use `/dev/serial/by-id/` paths where available.

Useful command:

```bash
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

## Step 8 — Validate force path with screw press

- **Do:** Install PM58 in series with the handgrip and apply controlled force using the screw press.
- **Expected result:** PM58 board display, target raw counts, viewer plots, and calibration streams all change in the same physical direction.
- **Failure signal:** Reference changes but target does not, target changes but reference does not, or force path binds/slips.
- **Next branch:** Use [docs/hardware/force-fixture.md](../hardware/force-fixture.md).

Expected fixture images:

- `docs/hardware/assets/pm58_n_handgrip_setup.jpg`
- `docs/hardware/assets/acq_board_n_pm58_n_handgrip_setup.jpg`
- `docs/hardware/assets/force_application_setup.jpg`

## Stop conditions

Stop before software acquisition if:

- PM58 wiring is uncertain.
- Acquisition-board display does not react to force.
- Arduino serial port is not identifiable.
- RS485 adapter is not identifiable.
- Screw press force path is not mechanically stable.
- Any mains wiring is exposed or loose.

## Related docs

- [docs/hardware/pm58-wiring-and-bringup.md](../hardware/pm58-wiring-and-bringup.md)
- [docs/hardware/force-fixture.md](../hardware/force-fixture.md)
- [docs/troubleshooting/hardware-and-wiring.md](../troubleshooting/hardware-and-wiring.md)
- [docs/troubleshooting/serial-and-rs485.md](../troubleshooting/serial-and-rs485.md)

