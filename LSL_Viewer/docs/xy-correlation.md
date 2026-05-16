# XY Correlation

## Summary

- The XY correlation panel visualizes the relationship between reference force and selected target signal.
- X-axis: reference force from `HandgripReference`.
- Y-axis: target raw count or target filtered/current units from `HandgripTarget`.
- XY reference interpolation/alignment is **display-only** and does not modify LSL buffers, CSV/XDF replay files, or calibration data.
- The default `raw_lsl` mode is intentionally diagnostic: growing lag should be investigated, not hidden.

## What the XY plot means

The XY plot answers:

```text
When reference force changes, how does the target handgrip signal respond?
```

Recommended calibration visualization:

```yaml
viewer:
  xy_correlation:
    target_signal: raw
```

Reason: raw target counts are the calibration-authoritative target signal.

## XY signal selection

| Setting                   | Meaning                                      | Use case                                                    |
| ------------------------- | -------------------------------------------- | ----------------------------------------------------------- |
| `target_signal: raw`      | Use `target_raw_count` on Y-axis.            | Calibration visualization and raw sensor validation.        |
| `target_signal: filtered` | Use `target_filtered_units` / current units. | Display-only experiments and deployed-filter sanity checks. |

## Alignment policy

Config section:

```yaml
viewer:
  xy_correlation:
    time_alignment:
      mode: raw_lsl
      manual_reference_shift_s: 0.0
      max_auto_shift_s: null
      min_auto_shift_s: 0.0
      snap_threshold_s: 0.250
      smoothing_alpha: 1.0
```

| Mode               | Meaning                                                            | Recommended use                                                |
| ------------------ | ------------------------------------------------------------------ | -------------------------------------------------------------- |
| `raw_lsl`          | Use native LSL timestamps with no viewer-side reference shift.     | Default and calibration diagnostic mode.                       |
| `tail_aligned_lsl` | Display-only auto-shift based on target/reference tail timestamps. | Temporary visual aid when diagnosing backlog/alignment issues. |
| `manual`           | Apply fixed `manual_reference_shift_s`.                            | Temporary debugging or controlled demonstration.               |

## Reference interpolation

Config section:

```yaml
alignment:
  interpolation: linear
  max_reference_gap_s: 0.020
  allow_extrapolation: false
```

Behavior:

- reference samples are interpolated to target sample timestamps for XY display,
- interpolation rejects large reference gaps using `max_reference_gap_s`,
- extrapolation is disabled by default to avoid invented endpoint behavior.

## Axis behavior

Config section:

```yaml
viewer:
  xy_correlation:
    lock_max_span: false
    toggle_key: x
```

| Mode                   | Behavior                                               |
| ---------------------- | ------------------------------------------------------ |
| `lock_max_span: false` | Adaptive autoscale on each refresh.                    |
| `lock_max_span: true`  | Preserve largest observed XY axis span; only zoom out. |

Keyboard toggle:

```text
x
```

## Rendering model

The XY graph uses connected ECharts line-path buckets rather than point-only scatter. Sample age is mapped to opacity, so older path segments fade while newer segments remain prominent.

Rendering downsampling:

```yaml
viewer:
  render:
    downsample_enabled: true
    max_points_xy: 1500
```

This is browser-rendering only. It does not alter raw buffers, replay files, calibration data, or reports.

## Lag troubleshooting

### Symptom: XY reference delay grows over time

Likely causes:

| Cause                                 | How to distinguish                                                      |
| ------------------------------------- | ----------------------------------------------------------------------- |
| Real upstream timestamp/backlog issue | Time-series and saved data also show reference lag.                     |
| Viewer alignment mode hiding problem  | `tail_aligned_lsl` looks okay but `raw_lsl` drifts.                     |
| Browser render overload               | UI is sluggish, but logs/data timestamps remain valid.                  |
| Reference frame parsing backlog       | `RS485_GUI`/`LSL_Bridge` logs show drops, queueing, or parser warnings. |
| Wrong channel labels                  | XY plot empty or uses unintended signal.                                |

### Recommended diagnostic sequence

1. Switch to `raw_lsl` mode.
2. Verify target and reference time-series plots independently.
3. Check `LSL_Bridge` logs for target/reference parser warnings.
4. Check `RS485_GUI` logs for malformed frames/backlog.
5. Check viewer render payload settings.
6. Record a short session and inspect saved timestamps before changing acquisition code.

## Stop conditions before calibration

Stop before calibration if:

- XY delay grows in `raw_lsl` mode,
- reference interpolation drops many samples due to `max_reference_gap_s`,
- target raw count and reference force are not monotonic under controlled force,
- one stream visibly freezes,
- the XY relationship differs between live and replay for the same recorded session.

## Tests that guard XY behavior

| Test file                          | Coverage                                                                    |
| ---------------------------------- | --------------------------------------------------------------------------- |
| `tests/unit/test_alignment.py`     | Reference interpolation, time shift, gap rejection, raw/filtered selection. |
| `tests/unit/test_state.py`         | XY axis span locking and viewer state round-trip.                           |
| `tests/integration/test_charts.py` | XY ECharts series, render downsampling, clear behavior, marker integration. |
