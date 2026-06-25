# Timestamping and Synchronization

## Summary

- Timing is a system property, not a single-module detail.
- The target stream is device-paced and should be treated as irregular due limitations of the HX711 ADC.
- The reference stream is expected to be faster and more regular, typically using the acquisition board Active-Send profile.
- LSL timestamps should preserve enough information to support post-hoc alignment, interpolation, and lag diagnostics.
- Viewer downsampling is display-only and must not be confused with acquisition downsampling.

## Timing model

```markdown
Target path timing
  HX711 conversion → firmware timestamp_us → USB serial receive → LSL_Bridge timestamp → 
  emits LSL sample @ `irregular` 93 ~ 100 Hz

Reference path timing
  acquisition-board ADC/sample → RS485 frame → RS485_GUI receive → IPC publish → LSL_Bridge receive → 
  emits LSL sample @ `regular` 500 Hz (Active-Send)
```

## Target stream timing

The target firmware includes `timestamp_us` in D2 frames. This is valuable because it helps separate:

- physical sampling time,
- serial transport delay,
- host receive time,
- LSL publication time.

Recommended treatment:

- Advertise target as irregular unless a future firmware version proves stable fixed-rate behavior.
- Preserve `seq` for drop detection.
- Preserve `timestamp_us` for gap and drift diagnostics.

## Reference stream timing

The acquisition board is configured in `Active-Send` mode, which sets the board to emit frames at a fixed rate.
This is valuable because it makes the effective sampling rate, regular and independent of the inherent jitter of the Host's OS scheduler reading rate.

However, the frames carry **no acquisition timestamp** —force/status only—, so the reference sample timestamp must be reconstructed from the host read time (`rs485_clock = host_lsl_ts`) of the last batch of buffered frames, and the known frame interval `rs485_frame_dt_s` (the reciprocal of the Active-Send rate). 

This means the reference is effectively timestamped when the GUI reads it.

The reference chain should be faster than the target chain. 
The recommended calibration profile uses high-rate acquisition and Active-Send when parser stability by the board control interface (`RS485_GUI`) has been validated.

Recommended treatment:

- Use a high enough serial baud rate for the chosen reference output rate.
- Keep hidden board features such as auto-zero, dynamic tracking, and display-only zero masking disabled during calibration captures.
- Treat Modbus RTU polling as a documented fallback if Active-Send parsing or timing is not stable (not recommended).

## Reference relay offset and host-read-time stamping

The reference is effectively timestamped when the GUI *reads* the latest batch of buffered frames, i.e. after the relay hop `board → RS485 → RS485_GUI → IPC → LSL_Bridge`. 
The target, by contrast, reaches the bridge directly over USB. 

For the *same physical instant*, the two streams receive LSL timestamps that differ by the difference in those read latencies — a stable **relay offset** (order ~100 ms), not a rendering bug.

If present, this relay offset will be observed in the LSL Viewer XY plot (reference vs. target), as a **staircasing** waveform. 

To trigger it, set the `LSL_Viewer` parameter `manual_reference_shift_s = 0`, reload the viewer, and apply the same sudden change on force to both devices simultaneously (i.e. with both devices set as done on the calibration setup).

Under this condition, the signals should rise together drawing a 1:1 diagonal line, but the reference will arrive late, so the plot will first jump vertically (target changes, reference not yet updated), and then horizontally (reference updates to match target).

To compensate for this, an utility script `calibration_preflight.py` is [provided](../../Handgrip_Calibration/scripts/calibration_preflight.py) to measure the relay offset and confirm the absence of other timing issues (see [Handgrip_Calibration/docs/recording.md](../../Handgrip_Calibration/docs/recording.md) for instructions).

The result is a single scalar value that quantifies the relay offset, which needs to be set in the viewer as `manual_reference_shift_s` to align the reference timestamps with the target timestamps.

> Note that this is a compensation for the relay offset, not a correction of the acquisition timestamps, so it is **topology/host dependent**: re-measure it whenever the physical or runtime setup changes.


## LSL timing responsibilities

`LSL_Bridge` is responsible for publishing target/reference samples to LSL. It should also expose enough operational information for debugging timing problems.

| Responsibility                                     | Why it matters                                                              |
| -------------------------------------------------- | --------------------------------------------------------------------------- |
| Preserve target sequence numbers                   | Detect dropped target samples.                                              |
| Preserve or derive timestamps consistently         | Align target and reference streams.                                         |
| Emit component events                              | Diagnose connects, disconnects, parser failures, gaps.                      |
| Avoid display-only transformations in data streams | Calibration must use raw/reference data, not viewer convenience transforms. |


## Practical validation tests

### Target timing test

- Run firmware serial monitor.
- Collect at least 10 seconds of D2 frames.
- Check `seq` monotonicity.
- Check `timestamp_us` increments and gap distribution.

### Reference timing test

- Run `RS485_GUI` in the intended mode.
- Confirm frame rate near target profile.
- Check logs for parser recovery or malformed frames.

### LSL timing test

- Run bridge and viewer.
- Confirm target/reference streams update simultaneously under a visible force change.
- Record a short calibration/preflight session and inspect saved sample counts.

## Related docs:
- [docs/architecture/stream-contracts.md](stream-contracts.md)
- [docs/workflows/handgrip-calibration.md](../workflows/handgrip-calibration.md)
