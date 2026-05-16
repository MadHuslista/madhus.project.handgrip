# Hardware and Wiring Troubleshooting

**Status:** Canonical symptom-first troubleshooting doc  
**Symptoms covered:** No board display, wrong load sign, unstable reading, overload  
**Related docs:** `docs/workflows/physical-setup.md`, `docs/hardware/pm58-wiring-and-bringup.md`, `docs/hardware/force-fixture.md`

## Summary

Start here when the physical system does not behave correctly before software acquisition. Do not debug Python until the board display and force path make physical sense.

## Symptom: no board display

### Likely causes

| Cause                     | Check                                 | Fix                                                  |
| ------------------------- | ------------------------------------- | ---------------------------------------------------- |
| No power                  | AC input disconnected or switched off | Verify power source and disconnect/reconnect safely. |
| Wrong board power variant | Board not actually AC-powered         | Confirm label before applying power.                 |
| Loose L/N wiring          | Terminal not clamped                  | Power down, re-seat wiring.                          |
| Board fault               | No display despite verified power     | Stop and replace/inspect board.                      |

### Stop condition

Stop immediately if there is heat, smell, flicker, exposed mains wiring, or uncertain board power rating.

## Symptom: wrong load sign

### Likely causes

| Cause                                   | Check                                   | Fix                                                               |
| --------------------------------------- | --------------------------------------- | ----------------------------------------------------------------- |
| Signal pair reversed                    | PM58 `S+`/`S-` swapped                  | Swap signal pair after powering down.                             |
| Mechanical direction reversed           | Compression/tension convention differs  | Document sign convention; only invert if consistent and intended. |
| Board display scaling/inversion setting | Board menu sign/scaling setting changed | Compare against acquisition-board menu reference.                 |

### Validation

Apply a small known force. The reference and target should move in the expected direction for the calibration workflow.

## Symptom: unstable reading

### Likely causes

| Cause                           | Check                                    | Fix                                                                |
| ------------------------------- | ---------------------------------------- | ------------------------------------------------------------------ |
| Loose sensor wire               | Reading changes when cable moves         | Power down and re-seat terminals.                                  |
| Shield/drain misused            | Noise changes with cable position        | Keep shield isolated initially unless grounding plan is validated. |
| Mechanical slip                 | Reading jumps during hold                | Rebuild fixture, add clamping/stops.                               |
| Hidden board filtering/tracking | Display value behaves non-physically     | Review acquisition-board menu reference.                           |
| Electrical noise                | Noise correlated with mains/USB movement | Separate sensor wiring from power wiring.                          |

## Symptom: overload / saturated reading

### Likely causes

| Cause                    | Check                             | Fix                                                        |
| ------------------------ | --------------------------------- | ---------------------------------------------------------- |
| Sensor overloaded        | Force exceeds PM58 range          | Release load immediately.                                  |
| Wrong gain/range setting | Board saturates under small force | Restore recommended calibration configuration.             |
| Wiring fault             | Saturated with no load            | Re-check E+/E-/S+/S- wiring.                               |
| Mechanical preload       | Fixture starts loaded             | Release screw press, zero only after stable no-load state. |

## Minimum physical validation before software

- [ ] Acquisition board powers on normally.
- [ ] PM58 display responds to small force.
- [ ] Force path is stable and does not slip.
- [ ] Target handgrip wiring is secure.
- [ ] No overload or unstable baseline is present.
- [ ] Screw press force path is visually aligned.
