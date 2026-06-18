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
| Set `manual_reference_shift_s` | Saved data shows a stable reference offset (relay latency). Measure it with the calibration preflight (below). |

## Measure and compensate the reference offset

The reference path (`board → RS485 → RS485_GUI → IPC → LSL_Bridge`) is stamped at GUI read time and lags the directly-connected target by a stable **relay offset** — see [docs/architecture/timestamping-and-synchronization.md](../architecture/timestamping-and-synchronization.md). When the saved CSVs (not just the browser) show that offset, compensate it with a constant viewer shift rather than changing acquisition.

Run the calibration preflight (from the `Handgrip_Calibration` directory):

```bash
uv run python scripts/calibration_preflight.py \
  --viewer-session ../diagnostics/<ts> \
  --bridge-target-csv ../LSL_Bridge/data/target_*.csv \
  --bridge-reference-csv ../LSL_Bridge/data/reference_*.csv \
  --gui-ndjson ../RS485_GUI/logs/raw_signal.ndjson
```

It validates that the capture config/logs are correct, confirms the ratchet/throughput/jitter issues are absent, and — when the offset is stable — prints the exact `manual_reference_shift_s` plus the file and key to set in `LSL_Viewer/conf/config.yaml` (`viewer.xy_correlation.time_alignment`). Re-measure after any setup change (cabling, ports, host, baud, rates); the offset is physical.


**Related docs:** [LSL_Viewer/docs/xy-correlation.md](../../LSL_Viewer/docs/xy-correlation.md), [docs/architecture/timestamping-and-synchronization.md](../architecture/timestamping-and-synchronization.md), [LSL_Bridge/docs/timestamping.md](../../LSL_Bridge/docs/timestamping.md)
