# Timestamping and Synchronization

## Summary

- Timing is a system property, not a single-module detail.
- The target stream is device-paced and should be treated as irregular.
- The reference stream is expected to be faster and more regular, typically using the acquisition board Active-Send profile.
- LSL timestamps should preserve enough information to support post-hoc alignment, interpolation, and lag diagnostics.
- Viewer downsampling is display-only and must not be confused with acquisition downsampling.

## Timing model

```text
Target path timing
  HX711 conversion → firmware timestamp_us → USB serial receive → LSL_Bridge timestamp → LSL sample

Reference path timing
  acquisition-board ADC/sample → RS485 frame → RS485_GUI receive → IPC publish → LSL_Bridge receive → LSL sample
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

The reference chain should be faster than the target chain. The recommended calibration profile uses high-rate acquisition and Active-Send when parser stability has been validated.

Recommended treatment:

- Use a high enough serial baud rate for the chosen reference output rate.
- Keep hidden board features such as auto-zero, dynamic tracking, and display-only zero masking disabled during calibration captures.
- Treat Modbus RTU polling as a documented fallback if Active-Send parsing or timing is not stable.

## LSL timing responsibilities

`LSL_Bridge` is responsible for publishing target/reference samples to LSL. It should also expose enough operational information for debugging timing problems.

| Responsibility                                     | Why it matters                                                              |
| -------------------------------------------------- | --------------------------------------------------------------------------- |
| Preserve target sequence numbers                   | Detect dropped target samples.                                              |
| Preserve or derive timestamps consistently         | Align target and reference streams.                                         |
| Emit component events                              | Diagnose connects, disconnects, parser failures, gaps.                      |
| Avoid display-only transformations in data streams | Calibration must use raw/reference data, not viewer convenience transforms. |

## Viewer alignment

The viewer is for operator insight, not the final source of truth for calibration math.

Key rule:

> A visually delayed XY plot is a symptom to investigate, not proof that the saved data is delayed.

When investigating lag:

1. Check target and reference time-series plots independently.
2. Check LSL timestamps and sample counts.
3. Check interpolation/alignment mode in viewer config.
4. Check whether viewer render downsampling is display-only.
5. Check saved calibration session files before changing acquisition code.

## Calibration alignment

Calibration should fit static holds where timing uncertainty is less dominant. Dynamic trials are useful for validation, lag, hysteresis, and bandwidth checks, but they should not replace stable static-hold fitting unless the protocol explicitly supports that model.

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

## Stop conditions

Stop before calibration if:

- target `seq` is not monotonic,
- reference samples freeze or jump discontinuously under steady load,
- bridge logs parser failures continuously,
- viewer finds only one stream,
- preflight reports missing target/reference channels,
- config snapshot paths fail to copy expected component configs.

## Related docs:
- [`docs/architecture/stream-contracts.md`](stream-contracts.md)
- [`docs/workflows/handgrip-calibration.md`](../workflows/handgrip-calibration.md)
