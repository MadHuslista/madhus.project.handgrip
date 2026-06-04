# LSL Viewer Lag or XY Delay Troubleshooting

**Symptoms covered:** XY delay, reference lag, display-only shift vs real timestamp issue

**Prerequisite:** [docs/troubleshooting/lsl-streams.md](lsl-streams.md) — confirm both streams are visible and not stale before diagnosing viewer timing.

## Summary

A delayed XY plot is a symptom to diagnose, not automatic proof that recorded data is delayed. Separate display/render issues from timestamping/acquisition issues before changing code.

## Symptom: XY delay grows over time

### Likely causes

| Cause                                   | Why                                | Check                                                                                    |
| --------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------- |
| Reference interpolation window mismatch | Target/reference rates differ      | [LSL_Viewer/docs/xy-correlation.md](../../LSL_Viewer/docs/xy-correlation.md) settings. |
| Timestamp anchor drift                  | Device clock and host time diverge | [LSL_Bridge/docs/timestamping.md](../../LSL_Bridge/docs/timestamping.md).              |
| Buffer pruning bug                      | Viewer keeps unmatched old samples | Viewer alignment tests/logs.                                                             |
| Display render backlog                  | Browser cannot keep up             | Compare saved data vs visual plot.                                                       |

### Reference lag only in XY plot

If time-series plots react live but XY correlation lags, suspect viewer alignment/interpolation logic before changing acquisition or bridge code. Check: XY alignment mode, target/reference signal labels, interpolation gap threshold, max XY points, manual reference shift, render downsampling.

## Symptom: display-only shift vs real timestamp issue

Use this decision table:

| Observation                                                     | Likely class                                                  |
| --------------------------------------------------------------- | ------------------------------------------------------------- |
| Saved CSV target/reference align correctly, but browser XY lags | viewer display/alignment issue.                               |
| Saved CSV and viewer both show delay                            | timestamp/acquisition issue.                                  |
| Only reference stream lags                                      | RS485 GUI, IPC, or reference timestamping issue.              |
| Only target stream lags                                         | firmware serial, bridge parser, or target timestamping issue. |

## Diagnostic workflow

1. Confirm `RS485_GUI` live value reacts to force.
2. Confirm target firmware D2 `raw_count` reacts to force.
3. Confirm `LSL_Bridge` publishes both streams.
4. Compare viewer time-series plots.
5. Compare viewer XY plot.
6. Record short calibration/preflight data.
7. Inspect saved target/reference timestamps.
8. Only then change viewer or bridge alignment settings.

## Common fixes

| Fix                          | Use when                                                   |
| ---------------------------- | ---------------------------------------------------------- |
| Reduce viewer max points     | Browser/render lag dominates.                              |
| Adjust XY interpolation mode | XY only is misaligned.                                     |
| Use tail-aligned LSL mode    | Comparing most recent target/reference tails is preferred. |
| Reanchor target timestamping | Device clock drift exceeds bridge threshold.               |
| Validate RS485 profile       | Reference stream itself is delayed or bursty.              |


**Related docs:** [LSL_Viewer/docs/xy-correlation.md](../../LSL_Viewer/docs/xy-correlation.md), [docs/architecture/timestamping-and-synchronization.md](../architecture/timestamping-and-synchronization.md), [LSL_Bridge/docs/timestamping.md](../../LSL_Bridge/docs/timestamping.md)
