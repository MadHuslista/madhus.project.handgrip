# LSL Viewer Configuration

## Summary

- Main config file: `LSL_Viewer/conf/config.yaml`.
- The config is Hydra/OmegaConf driven and supports command-line dotlist overrides.
- `mode` selects live/replay behavior.
- `streams` and `channels` must match `LSL_Bridge` stream contracts.
- `viewer.render` controls browser payload size only; it does not change acquisition or replay data.
- XY alignment options under `viewer.xy_correlation.time_alignment` are display-only.

## Main config path

```text
LSL_Viewer/conf/config.yaml
```

Run examples:

```bash
cd LSL_Viewer
uv run lsl-viewer
uv run lsl-viewer mode=live_with_reference_validation
uv run lsl-viewer viewer.server.port=8766 viewer.server.show=false
```

## Top-level keys

| Key | Type | Default | Purpose | When to change | Failure risk |
| --- | --- | --- | --- | --- | --- |
| `mode` | string | `live` | Selects live/replay runner. | Use `csv_replay` or `xdf_replay` for offline inspection. | Unsupported mode exits with error. |
| `streams` | map | see below | LSL stream discovery settings. | If bridge stream names/source IDs change. | Viewer cannot find streams. |
| `channels` | map | see below | Channel labels inside target/reference streams. | If bridge channel labels change. | Plots/replay fail due to missing labels. |
| `viewer` | map | see below | Window size, refresh, UI, XY, rendering, server. | Tune display/UX. | UI lag, unreadable plots, misleading XY behavior. |
| `calibration_markers` | map | disabled | Optional marker overlay from calibration events. | Replay/analysis with calibration markers. | Missing event file gives no markers. |
| `alignment` | map | linear/no extrapolation | Reference interpolation/gap policy. | Diagnose or tune XY pairing. | Extrapolation or large gaps can mislead. |
| `reference` | map | replay paths | CSV/XDF replay input paths. | Replay saved sessions. | Missing paths cause replay error. |
| `replay` | map | normal speed/no loop | Replay playback controls. | Demonstration or analysis review. | Loop/speed can confuse interpretation if unlabeled. |
| `logging` | map | INFO + rotating file | Viewer log level and file. | Debug viewer behavior. | Too much logging or missing log file. |

## `mode`

| Value | Meaning |
| --- | --- |
| `live` | Discover live `HandgripTarget` and `HandgripReference` streams. |
| `live_with_reference_validation` | Live mode with extra reference validation in the UI. |
| `csv_replay` | Load target/reference CSV files and replay through the same UI model. |
| `xdf_replay` | Load target/reference streams from XDF using `pyxdf`. |

## `streams`

```yaml
streams:
  target:
    name: HandgripTarget
    stype: Force
    source_id: null
    buffer_samples: 1600
    acquisition_delay: 0.01
    timeout: 5.0
  reference:
    name: HandgripReference
    stype: Force
    source_id: rs485-acquisition-board-1
    buffer_seconds: 12.0
    acquisition_delay: 0.01
    timeout: 5.0
    expected_rate_hz: 500.0
```

| Key | Default | Impact | When to change |
| --- | --- | --- | --- |
| `streams.target.name` | `HandgripTarget` | Target stream lookup. | Only if `LSL_Bridge` stream name changes. |
| `streams.target.stype` | `Force` | Stream type filter. | Rarely. Keep aligned with bridge. |
| `streams.target.source_id` | `null` | Optional source ID filter. | Set when multiple target streams are visible. |
| `streams.target.buffer_samples` | `1600` | Target live buffer length by sample count. | Increase for longer history. |
| `streams.target.acquisition_delay` | `0.01` | Pull delay for LSL inlet handling. | Tune only if stream pull behavior requires it. |
| `streams.target.timeout` | `5.0` | Discovery/pull timeout. | Increase for slow startup. |
| `streams.reference.name` | `HandgripReference` | Reference stream lookup. | Only if bridge stream name changes. |
| `streams.reference.source_id` | `rs485-acquisition-board-1` | Optional reference source ID filter. | Change if bridge reference `source_id` changes. |
| `streams.reference.buffer_seconds` | `12.0` | Reference live buffer length by time. | Increase if XY window/reference extra history needs it. |
| `streams.reference.expected_rate_hz` | `500.0` | Used for replay/fallback assumptions and diagnostics. | Change if board profile changes. |

## `channels`

```yaml
channels:
  target:
    clock_label: device_clock_us
    raw_label: target_raw_count
    filtered_label: target_filtered_units
  reference:
    clock_label: reference_clock_s
    raw_label: reference_force_N
```

| Key | Default | Meaning | Contract owner |
| --- | --- | --- | --- |
| `channels.target.clock_label` | `device_clock_us` | Firmware device-clock channel from D2 `timestamp_us`. | `LSL_Bridge` stream contract. |
| `channels.target.raw_label` | `target_raw_count` | Calibration-authoritative target signal. | `LSL_Bridge` stream contract. |
| `channels.target.filtered_label` | `target_filtered_units` | Display/filtered/current target engineering signal. | Bridge/processing config. |
| `channels.reference.clock_label` | `reference_clock_s` | Reference acquisition clock channel. | `LSL_Bridge` reference contract. |
| `channels.reference.raw_label` | `reference_force_N` | Reference force channel. | `LSL_Bridge` reference contract. |

## `viewer`

| Key | Default | Purpose |
| --- | --- | --- |
| `viewer.window_seconds` | `10.0` | Live/replay display window size. |
| `viewer.target_window_samples` | `1600` | Maximum target samples in live target window. |
| `viewer.reference_window_extra_s` | `1.0` | Extra reference history around target window for interpolation/alignment. |
| `viewer.expected_target_rate_hz` | `100.0` | Target-rate diagnostic expectation. |
| `viewer.refresh_s` | `0.05` | UI update cadence. |
| `viewer.force_unit_label` | `N` | Axis/unit label for force. |
| `viewer.target_raw_unit_label` | `count` | Axis/unit label for raw target counts. |
| `viewer.dt_unit_label` | `ms` | Timing interval label. |

### `viewer.style`

Controls chart colors and line styling. This is visual only.

| Key | Default |
| --- | --- |
| `raw_color` | `red` |
| `filtered_color` | `green` |
| `reference_color` | `purple` |
| `timing_color` | `blue` |
| `grid_alpha` | `0.3` |
| `xy_color` | `red` |
| `xy_alpha_old` | `0.12` |
| `xy_alpha_new` | `0.92` |
| `xy_line_width` | `1.6` |

### `viewer.xy_correlation`

| Key | Default | Purpose |
| --- | --- | --- |
| `lock_max_span` | `false` | If true, XY axes only zoom out and preserve largest observed span. |
| `toggle_key` | `x` | Keyboard toggle for XY lock. |
| `target_signal` | `raw` | Choose `raw` or `filtered` target signal for XY Y-axis. |
| `time_alignment.mode` | `raw_lsl` | Display-only reference alignment mode. |
| `time_alignment.manual_reference_shift_s` | `0.0` | Fixed reference shift for `manual` mode. |
| `time_alignment.max_auto_shift_s` | `null` | Auto-shift clip; null means use `viewer.window_seconds`. |
| `time_alignment.min_auto_shift_s` | `0.0` | Deadband below which auto shift becomes zero. |
| `time_alignment.snap_threshold_s` | `0.250` | Large shift changes snap instead of smoothing. |
| `time_alignment.smoothing_alpha` | `1.0` | EWMA smoothing factor. |

Allowed alignment modes:

| Mode | Meaning |
| --- | --- |
| `raw_lsl` | Use native LSL timestamps without viewer-side shift. Recommended default. |
| `tail_aligned_lsl` | Display-only auto-shift based on target/reference tail alignment. Temporary diagnostic aid. |
| `manual` | Apply fixed `manual_reference_shift_s`. Diagnostic only. |

### `viewer.controls`

| Key | Default | Purpose |
| --- | --- | --- |
| `clear_key` | `c` | Clear plots and reset post-clear display state. |
| `pause_key` | `p` | Pause/resume live or replay rendering. |

### `viewer.render`

| Key | Default | Purpose |
| --- | --- | --- |
| `downsample_enabled` | `true` | Limit browser payload size for rendering only. |
| `max_points_time_series` | `1200` | Max points sent per time-series panel per refresh. |
| `max_points_xy` | `1500` | Max XY points sent per refresh. |

Rendering downsampling does not alter LSL buffers, CSV/XDF replay data, calibration sessions, or saved data.

### `viewer.server`

| Key | Default | Purpose |
| --- | --- | --- |
| `host` | `127.0.0.1` | NiceGUI server bind address. |
| `port` | `8765` | NiceGUI server port. |
| `reload` | `false` | NiceGUI reload behavior. Keep false for normal operation. |
| `show` | `true` | Auto-open browser. |
| `dark` | `false` | UI theme preference. |
| `title` | `LSL Viewer` | Browser/page title. |

## `calibration_markers`

| Key | Default | Purpose |
| --- | --- | --- |
| `enabled` | `false` | Enable optional marker overlay from events NDJSON. |
| `events_ndjson_path` | `null` | Path to calibration event file. |
| `draw_events` | hold/trial marker names | Event names to draw as marker lines. |

## `alignment`

```yaml
alignment:
  interpolation: linear
  max_reference_gap_s: 0.020
  allow_extrapolation: false
```

| Key | Default | Purpose |
| --- | --- | --- |
| `interpolation` | `linear` | Interpolate reference values to target timestamps inside the viewer. |
| `max_reference_gap_s` | `0.020` | Reject XY interpolation across large reference gaps. |
| `allow_extrapolation` | `false` | Prevent using reference values outside available time range. |

## `reference`

Replay input paths:

| Key | Default | Purpose |
| --- | --- | --- |
| `target_csv_path` | `./data/target_handgrip_samples_v2.csv` | Target CSV replay input. |
| `reference_csv_path` | `./data/reference_rs485_samples_v2.csv` | Reference CSV replay input. |
| `xdf_path` | `null` | XDF replay input. |

## `replay`

| Key | Default | Purpose |
| --- | --- | --- |
| `speed` | `1.0` | Replay speed multiplier. |
| `loop` | `false` | Loop replay when it reaches the end. |
| `start_offset_s` | `0.0` | Start replay after this offset. |

## `logging`

| Key | Default | Purpose |
| --- | --- | --- |
| `level` | `INFO` | Log verbosity. |
| `log_file` | `handgrip_realtime_viewer.log` | Explicit viewer log file path. |
| `max_bytes` | `10485760` | Rotating log max size. |
| `backup_count` | `3` | Rotating log backup count. |

## Validation commands

```bash
rg 'mode: live' LSL_Viewer/conf/config.yaml
rg 'name: HandgripTarget' LSL_Viewer/conf/config.yaml
rg 'name: HandgripReference' LSL_Viewer/conf/config.yaml
rg 'raw_label: target_raw_count' LSL_Viewer/conf/config.yaml
rg 'raw_label: reference_force_N' LSL_Viewer/conf/config.yaml
rg 'mode: raw_lsl' LSL_Viewer/conf/config.yaml
```
