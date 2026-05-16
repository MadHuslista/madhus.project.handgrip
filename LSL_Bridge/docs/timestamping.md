# LSL Bridge Timestamping

## Summary

- LSL timestamps are the synchronization authority for downstream live consumers.
- `device_clock_us` and `reference_clock_s` are preserved as diagnostic/sample-clock channels.
- Target timestamps can use either `host_receive` or `device_clock_anchor` policy.
- The default `device_clock_anchor` policy preserves target native cadence while preventing unbounded drift from host LSL time.
- Reference timestamps use the RS485 GUI `host_lsl_ts` when available, falling back to bridge receive time.

## Timestamp domains

| Domain                             | Field                                       | Owner                          | Role                                          |
| ---------------------------------- | ------------------------------------------- | ------------------------------ | --------------------------------------------- |
| Firmware device clock              | `device_clock_us`                           | `Handgrip_Firmware`            | Target diagnostic/sample clock.               |
| Target host arrival                | `arrival_lsl_time`                          | `LSL_Bridge` serial loop       | Host-side arrival time for D2 line.           |
| Target LSL timestamp               | `sample.lsl_timestamp`                      | `TargetTimestampResolver`      | Timestamp used for target LSL sample.         |
| Reference source clock             | `reference_clock_s`                         | `RS485_GUI` / acquisition path | Reference diagnostic/sample clock.            |
| Reference host LSL timestamp       | `host_lsl_ts`                               | `RS485_GUI`                    | Preferred reference LSL timestamp.            |
| Reference bridge receive timestamp | `received_lsl_ts`                           | `LSL_Bridge` IPC thread        | Fallback reference timestamp.                 |
| Processor-domain time              | configured by `processing.timestamp_source` | `SampleTimeResolver`           | Time fed into target processing/filter chain. |

## Target timestamp policies

Configured at:

```yaml
target_timestamping:
  policy: device_clock_anchor
```

### `host_receive`

Uses the LSL arrival time captured when the serial line is read.

Use when:

- firmware `micros()` quality is unknown,
- target device clock appears unstable,
- you need the lowest-risk debug policy,
- you are diagnosing device-clock drift behavior.

Tradeoff:

- robust to firmware clock problems,
- preserves host receive timing, not native device cadence.

### `device_clock_anchor`

Anchors the first target sample to host LSL arrival time, then advances timestamps using `device_clock_us` deltas.

Use when:

- firmware device clock is monotonic enough,
- you want to preserve native target cadence,
- viewer XY behavior should not accumulate reference lag due to target clock walk.

Safety guards:

| Key                     | Meaning                                                                 |
| ----------------------- | ----------------------------------------------------------------------- |
| `reset_on_nonmonotonic` | Re-anchor if target device clock goes backward.                         |
| `max_gap_s`             | Re-anchor if a large target device-clock gap appears.                   |
| `max_anchor_drift_s`    | Re-anchor if device-derived time drifts too far from host arrival time. |
| `monotonic_epsilon_s`   | Enforce strictly increasing LSL timestamps.                             |

## Drift and gap behavior

The resolver emits component events when it re-anchors. These are important for post-hoc QA.

Typical reasons:

| Reason                      | Meaning                                                               |
| --------------------------- | --------------------------------------------------------------------- |
| `device_clock_anchor_drift` | Predicted device-clock timestamp drifted beyond `max_anchor_drift_s`. |
| `device_clock_gap`          | Target device-clock gap exceeded `max_gap_s`.                         |
| nonmonotonic clock reset    | Device clock moved backward and reset policy is enabled.              |

If these happen rarely around reconnects or startup, they are usually acceptable. If they happen continuously during stable acquisition, inspect firmware timing, USB serial stability, and host load.

## Reference timestamp behavior

The RS485 reference publisher computes the LSL timestamp as:

```python
timestamp = sample.host_lsl_ts if finite else sample.received_lsl_ts
```

This means:

- `RS485_GUI` host timestamp is preferred,
- bridge receive time is fallback,
- `reference_clock_s` remains a diagnostic/sample-clock channel.

## Processing-domain time

Target processing/filtering uses `SampleTimeResolver` and `processing.timestamp_source`.

Default:

```yaml
processing:
  timestamp_source: device_clock_us
```

Supported behavior:

| Source            | Meaning                                                      |
| ----------------- | ------------------------------------------------------------ |
| `device_clock_us` | Filter uses target device-clock deltas converted to seconds. |
| `lsl`             | Filter uses resolved LSL timestamps.                         |

Changing processor time source affects filter dynamics. Validate with `tests/unit/test_filter.py` and signal-level analysis before promoting changes.

## Viewer delay interpretation

A visual XY delay does not automatically mean the saved data is wrong.

Debug order:

1. Check target time-series response.
2. Check reference time-series response.
3. Check bridge logs for timestamp re-anchors.
4. Check target sequence gaps.
5. Check reference IPC malformed/gap events.
6. Check viewer interpolation/alignment settings.
7. Compare saved CSV/session data.

## Validation commands

```bash
uv run pytest tests/unit/test_timestamping.py
rg "target_timestamping" LSL_Bridge/conf/config.yaml LSL_Bridge/docs
rg "device_clock_anchor|max_anchor_drift_s|host_receive" LSL_Bridge/docs/timestamping.md
```
