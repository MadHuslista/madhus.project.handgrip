# RS485 GUI Configuration

## Summary

- Main config path: `RS485_GUI/config/config.yaml`.
- The config is loaded directly through OmegaConf, not through `@hydra.main`, because NiceGUI can re-execute the application module while serving pages.
- CLI overrides use dotlist syntax, for example `serial.default_port=/dev/ttyUSB1`.
- The most important calibration-safe defaults are `device.mode=active_send`, `serial.default_baudrate=460800`, `ipc.topic=rs485.measurement.v1`, and `ipc.signal_key=net_value`.
- GUI display throttling is separate from file logging and IPC publication. Do not confuse display downsampling with acquisition downsampling.

## Configuration precedence

```text
CLI key=value overrides > RS485_GUI/config/config.yaml defaults
```

Examples:

```bash
cd RS485_GUI
uv run rs485-gui serial.default_port=/dev/ttyUSB1
uv run rs485-gui ui.port=8090 serial.default_port=/dev/ttyUSB1
uv run rs485-gui device.mode=modbus_rtu
uv run rs485-gui app.log_level=DEBUG logging.module_levels.rs485_gui.transport.active_send=DEBUG
```

## Top-level sections

| Section       | Purpose                                                                                      |
| ------------- | -------------------------------------------------------------------------------------------- |
| `session`     | Optional calibration/session identifier propagated to logs and IPC.                          |
| `hydra`       | Compatibility settings that keep runtime output in the current directory.                    |
| `app`         | Application-wide runtime behavior and log level.                                             |
| `ui`          | Browser UI host/port, plot/log sizes, refresh cadence, and display downsampling.             |
| `logger`      | NDJSON/CSV/event/debug logging behavior.                                                     |
| `ipc`         | ZeroMQ publisher endpoint, topics, payload signal, and backpressure behavior.                |
| `serial`      | Port, baud, parity, stop bits, timeout, and port discovery hints.                            |
| `device`      | Acquisition mode, slave address, poll cadence, register map, and active-send frequency code. |
| `active_send` | Active-Send parser, buffering, timestamping, delivery, and recovery settings.                |
| `logging`     | Root and per-module log-level overrides.                                                     |

## `session`

| Key                  | Default | Type / range   | Impact                                           | When to change                                             | Failure risk                                                                 |
| -------------------- | ------- | -------------- | ------------------------------------------------ | ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `session.session_id` | `null`  | string or null | Propagates session ID into logs and IPC records. | Set when coordinating GUI logs with a calibration session. | Wrong value can make logs appear to belong to the wrong calibration session. |

## `app`

| Key                         | Default | Type / range         | Impact                                        | When to change                                                     | Failure risk                                                              |
| --------------------------- | ------- | -------------------- | --------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| `app.log_level`             | `INFO`  | Python logging level | Root app logging verbosity.                   | Use `DEBUG` while diagnosing acquisition, parser, or IPC problems. | Too verbose at high rates can add noise and reduce operator readability.  |
| `app.worker_join_timeout_s` | `1.5`   | seconds              | Time allowed for acquisition worker shutdown. | Increase only if clean shutdown routinely needs more time.         | Too low can leave hardware cleanup incomplete; too high slows disconnect. |

## `ui`

| Key                                       | Default                                 | Type / range      | Impact                                           | When to change                                                     | Failure risk                                                            |
| ----------------------------------------- | --------------------------------------- | ----------------- | ------------------------------------------------ | ------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| `ui.page_title`                           | `High-Speed Acquisition Instrument GUI` | string            | Browser page title.                              | Cosmetic / lab-specific naming.                                    | None.                                                                   |
| `ui.host`                                 | `127.0.0.1`                             | host/IP           | NiceGUI bind host.                               | Use `0.0.0.0` only for trusted LAN access.                         | Exposing UI on a network can create unwanted access.                    |
| `ui.port`                                 | `8088`                                  | TCP port          | Browser UI port.                                 | Change if port is already occupied.                                | Port conflict prevents app startup.                                     |
| `ui.refresh_interval_s`                   | `0.1`                                   | seconds           | UI refresh cadence.                              | Increase for lower CPU load; decrease for more responsive display. | Too low can load browser/CPU; too high makes UI sluggish.               |
| `ui.plot_height_px`                       | `360`                                   | pixels            | Signal plot height.                              | Adjust display layout.                                             | None.                                                                   |
| `ui.log_height_px`                        | `380`                                   | pixels            | Text log area height.                            | Adjust layout.                                                     | None.                                                                   |
| `ui.event_log_height_px`                  | `180`                                   | pixels            | Event log height.                                | Adjust layout.                                                     | None.                                                                   |
| `ui.visible_log_entries`                  | `40`                                    | count             | Visible log lines.                               | Operator preference.                                               | Too high can slow browser rendering.                                    |
| `ui.visible_event_entries`                | `120`                                   | count             | Visible event entries.                           | Debugging events.                                                  | Too high can slow browser rendering.                                    |
| `ui.max_retained_log_entries`             | `160`                                   | count             | In-memory log retention.                         | Debugging longer sessions.                                         | Higher memory/UI overhead.                                              |
| `ui.max_retained_event_entries`           | `500`                                   | count             | In-memory event retention.                       | Debugging.                                                         | Higher memory/UI overhead.                                              |
| `ui.max_plot_points`                      | `3000`                                  | count             | Browser-facing retained plot history.            | Longer visible window.                                             | Larger browser memory/render load.                                      |
| `ui.max_render_plot_points`               | `700`                                   | count             | Rendered plot points after display downsampling. | Tune browser performance.                                          | Too low hides visible details; too high slows UI.                       |
| `ui.default_plot_signal_key`              | `net_value`                             | signal key        | Initial plotted signal.                          | Select raw/peak/internal code views.                               | Wrong key can show misleading signal.                                   |
| `ui.plot_signal_key`                      | `net_value`                             | signal key        | Active plotted signal.                           | Runtime/operator override.                                         | Wrong key can confuse operator.                                         |
| `ui.clear_plot_on_connect`                | `true`                                  | bool              | Clears plot traces on new connection.            | Disable only when comparing consecutive connects visually.         | Old samples can be confused with current acquisition.                   |
| `ui.sampling_rate_window_samples`         | `5000`                                  | count             | Rolling sample window for rate estimates.        | Tune stability/responsiveness.                                     | Too small = noisy estimate; too large = slow to reflect changes.        |
| `ui.sampling_rate_outlier_low_ratio`      | `0.25`                                  | ratio             | Rejects gross too-fast dt outliers.              | Rarely change.                                                     | Bad setting can distort displayed rate estimate.                        |
| `ui.sampling_rate_outlier_high_ratio`     | `4.0`                                   | ratio             | Rejects gross too-slow dt outliers.              | Rarely change.                                                     | Bad setting can hide real gaps.                                         |
| `ui.sampling_rate_outlier_min_samples`    | `16`                                    | count             | Minimum samples before outlier rejection.        | Rarely change.                                                     | Too low can over-filter early estimates.                                |
| `ui.max_signal_samples_per_second`        | `0`                                     | Hz, `0` disables  | Acquisition-level max-rate limiter.              | Keep `0` for calibration so logs/IPC receive full-rate frames.     | Setting nonzero can drop acquisition frames before logs/IPC.            |
| `ui.display_max_samples_per_second`       | `30`                                    | Hz                | Display-only limiter.                            | Tune UI performance.                                               | Does not affect logs/IPC; operator may mistake it for acquisition rate. |
| `ui.active_send_render_downsample_factor` | `2`                                     | integer >=1       | Extra render downsampling for Active-Send.       | Browser performance at high rates.                                 | Too high can hide plot detail.                                          |
| `ui.modbus_rtu_render_downsample_factor`  | `1`                                     | integer >=1       | Extra render downsampling for Modbus mode.       | Usually leave at 1.                                                | Same display-only risk.                                                 |
| `ui.plot_trace_type`                      | `scattergl`                             | Plotly trace type | Browser plot rendering mode.                     | Use standard scatter only if WebGL causes issues.                  | Non-WebGL can be slower at high point counts.                           |
| `ui.light_mode`                           | `true`                                  | bool              | UI theme.                                        | Operator preference.                                               | None.                                                                   |

## `logger`

| Key                                  | Default                     | Type / range            | Impact                                 | When to change                                                 | Failure risk                                                        |
| ------------------------------------ | --------------------------- | ----------------------- | -------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------- |
| `logger.enabled`                     | `true`                      | bool                    | Enables file logging.                  | Disable only for temporary UI-only debugging.                  | Disabling loses acquisition audit trail.                            |
| `logger.directory`                   | `RS485_GUI/logs`            | path                    | Output directory.                      | Change per session/project.                                    | Wrong path can scatter logs or overwrite prior outputs.             |
| `logger.write_mode`                  | `overwrite`                 | `overwrite` or `append` | File open mode.                        | Use `append` for continuous log accumulation.                  | `overwrite` replaces previous logs; `append` can mix sessions.      |
| `logger.raw_signal_filename`         | `raw_signal.ndjson`         | filename                | Raw transport log.                     | Rarely change.                                                 | Consumers/tools may expect default names.                           |
| `logger.interpreted_signal_filename` | `interpreted_signal.ndjson` | filename                | Decoded engineering log.               | Rarely change.                                                 | Same.                                                               |
| `logger.gui_signal_filename`         | `gui_signal.csv`            | filename                | Flat CSV for spreadsheet/quick review. | Rarely change.                                                 | Same.                                                               |
| `logger.debug_log_to_file`           | `true`                      | bool                    | Mirrors Python logs to file.           | Disable for quick ephemeral runs.                              | Disabling loses debug trail.                                        |
| `logger.debug_log_filename`          | `acquisition_debug.log`     | filename                | Debug log filename.                    | Rarely change.                                                 | Same.                                                               |
| `logger.event_log_filename`          | `event.log`                 | filename                | Operator/runtime event log.            | Rarely change.                                                 | Same.                                                               |
| `logger.flush_every_n_batches`       | `25`                        | count                   | Batch-based flush cadence.             | Lower for safer immediate disk writes; higher for less jitter. | Too low can add jitter; too high risks losing recent data on crash. |
| `logger.flush_interval_s`            | `1.0`                       | seconds                 | Time-based flush cadence.              | Tune durability vs overhead.                                   | Same.                                                               |

## `ipc`

| Key                                 | Default                | Type / range        | Impact                                                               | When to change                                                  | Failure risk                                                           |
| ----------------------------------- | ---------------------- | ------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `ipc.enabled`                       | `true`                 | bool                | Enables ZMQ IPC publisher.                                           | Disable only when bridge is not used.                           | `LSL_Bridge` cannot publish `HandgripReference`.                       |
| `ipc.transport`                     | `zmq_pub`              | currently `zmq_pub` | IPC backend.                                                         | Do not change unless implementation supports another transport. | Unsupported value raises error.                                        |
| `ipc.bind`                          | `tcp://127.0.0.1:5557` | ZMQ bind endpoint   | Publisher endpoint.                                                  | Change to avoid port conflicts.                                 | Bridge must subscribe to matching endpoint.                            |
| `ipc.topic`                         | `rs485.measurement.v1` | string              | Measurement topic consumed by bridge.                                | Change only as cross-component migration.                       | Bridge stops receiving reference frames.                               |
| `ipc.event_topic`                   | `rs485.event.v1`       | string              | Operational event topic.                                             | Change only with bridge/diagnostic update.                      | Diagnostics lost.                                                      |
| `ipc.signal_key`                    | `net_value`            | signal key          | MeasurementFrame interpreted value published as `reference_force_N`. | Change if calibration should use another board signal.          | Wrong key can publish non-force or unscaled value.                     |
| `ipc.send_hwm`                      | `2000`                 | messages            | ZMQ high-water mark.                                                 | Increase if subscribers are intermittently slow.                | Too high can grow memory; too low can drop more frames.                |
| `ipc.linger_ms`                     | `0`                    | milliseconds        | ZMQ close behavior.                                                  | Rarely change.                                                  | Nonzero can slow shutdown.                                             |
| `ipc.drop_on_backpressure`          | `true`                 | bool                | Non-blocking publish behavior.                                       | Keep true for acquisition responsiveness.                       | Drops IPC frames if bridge/subscriber cannot keep up.                  |
| `ipc.start_on_app_launch`           | `false`                | bool                | Bind at app construction.                                            | Keep false due to NiceGUI re-execution behavior.                | True can cause false port conflicts.                                   |
| `ipc.start_on_connect`              | `true`                 | bool                | Start IPC when acquisition starts.                                   | Keep true for bridge integration.                               | False requires manual publisher start not currently operator-friendly. |
| `ipc.stop_on_disconnect`            | `true`                 | bool                | Stop IPC on disconnect.                                              | Keep true.                                                      | False can leave stale endpoint bound.                                  |
| `ipc.require_pylsl_clock`           | `true`                 | bool                | Requires `pylsl` clock for LSL-aligned timestamps.                   | Disable only for debug without LSL.                             | Timestamps may diverge from bridge expectations.                       |
| `ipc.publish_after_max_rate_filter` | `false`                | bool                | Whether IPC sees UI/acquisition-limited frames.                      | Keep false for full-rate bridge publication.                    | True can starve bridge/calibration at high rates.                      |
| `ipc.log_every_s`                   | `5.0`                  | seconds             | Publisher status log interval.                                       | Debugging.                                                      | Too low can add log noise.                                             |

## `serial`

| Key                        | Default             | Type / range    | Impact                                      | When to change                                   | Failure risk                                                               |
| -------------------------- | ------------------- | --------------- | ------------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------- |
| `serial.default_port`      | `""`                | path/string     | Preselected serial port.                    | Set to USB-RS485 adapter.                        | Wrong port can steal Arduino target or fail communication.                 |
| `serial.excluded_ports`    | empty list          | list of paths   | Protects reserved ports from GUI ownership. | Add Arduino/LSL bridge serial port.              | If omitted, operator can accidentally connect GUI to target firmware port. |
| `serial.default_baudrate`  | `460800`            | baud            | Board serial baud.                          | Must match acquisition-board communication menu. | Baud mismatch causes no frames/malformed frames.                           |
| `serial.default_parity`    | `N`                 | `N`, `E`, `O`   | Serial parity.                              | Must match board.                                | Mismatch prevents valid frames.                                            |
| `serial.default_stopbits`  | `1`                 | usually 1 or 2  | Stop bits.                                  | Must match board.                                | Mismatch prevents valid frames.                                            |
| `serial.bytesize`          | `8`                 | bits            | Data bits.                                  | Usually keep 8.                                  | Wrong value breaks decoding.                                               |
| `serial.timeout_s`         | `0.2`               | seconds         | Serial read timeout.                        | Tune for board/adapter behavior.                 | Too low increases timeout noise; too high slows disconnect/recovery.       |
| `serial.inter_frame_gap_s` | `0.001`             | seconds         | RTU gap/pacing.                             | Modbus tuning.                                   | Too small can stress device; too large lowers rate.                        |
| `serial.port_hints`        | USB/RS485/FTDI/etc. | list of strings | Port scoring in UI.                         | Add adapter-specific strings.                    | Poor hints only affect convenience.                                        |

## `device`

| Key                                 | Default       | Type / range                  | Impact                                          | When to change                                                   | Failure risk                                           |
| ----------------------------------- | ------------- | ----------------------------- | ----------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------ |
| `device.mode`                       | `active_send` | `active_send` or `modbus_rtu` | Transport backend.                              | Use Active-Send for high-rate reference; Modbus RTU as fallback. | Wrong mode produces no data or wrong command behavior. |
| `device.slave_address`              | `1`           | Modbus address                | Board address.                                  | Match board menu.                                                | Wrong address prevents Modbus communication.           |
| `device.active_send_frequency_code` | `8`           | code; 8 = 500 Hz              | Expected Active-Send frequency metadata/timing. | Match board Active-Send configuration.                           | Wrong value can distort reconstructed timestamps.      |
| `device.poll_interval_s`            | `0.001`       | seconds                       | Modbus polling target cadence.                  | Modbus performance tuning.                                       | Actual rate remains transaction-limited.               |
| `device.error_backoff_s`            | `0.25`        | seconds                       | Delay after worker errors.                      | Debugging noisy hardware.                                        | Too low can spam logs; too high slows recovery.        |
| `device.read_start_register`        | `0`           | register address              | First holding register read by Modbus.          | Alternate board firmware/register map.                           | Wrong map gives wrong values.                          |
| `device.read_register_count`        | `11`          | count                         | Number of registers per Modbus read.            | Alternate register map.                                          | Active-Send/calibration expects 11-register payload.   |
| `device.command_register`           | `11`          | register address              | Board command write register.                   | Alternate board firmware.                                        | Wrong register can send invalid commands.              |

## `active_send`

| Key                                           | Default                      | Type / range                                                     | Impact                                            | When to change                                        | Failure risk                                                 |
| --------------------------------------------- | ---------------------------- | ---------------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| `active_send.timestamp_policy`                | `batch_end_anchored`         | `batch_end_anchored`, `host_receive`, other implemented policies | Timestamp reconstruction policy.                  | Use host receive as debug fallback.                   | Wrong policy can create reference drift/lag.                 |
| `active_send.default_parser_profile`          | `modbus_rtu_response_11regs` | supported parser profile                                         | Active-Send binary payload format.                | Do not change unless parser supports another profile. | Unsupported/wrong profile fails parser.                      |
| `active_send.default_numeric_index`           | `0`                          | integer                                                          | Parser fallback index.                            | Rarely change.                                        | Wrong value can select wrong measurement.                    |
| `active_send.default_hex_word_endianness`     | `big`                        | endian string                                                    | Hex word decoding.                                | Alternate debug profile only.                         | Wrong endian corrupts numeric decode.                        |
| `active_send.read_timeout_s`                  | `0.5`                        | seconds                                                          | Read timeout in Active-Send mode.                 | Tune for slow/unstable board.                         | Too low creates false timeouts; too high slows recovery.     |
| `active_send.delivery_window_s`               | `0.010`                      | seconds                                                          | Batch delivery window.                            | Tune IPC latency vs overhead.                         | Too high makes bridge-side reference intermittently stale.   |
| `active_send.max_frames_per_delivery`         | `16`                         | count                                                            | Max frames delivered per batch.                   | Tune latency/CPU.                                     | Too high can add latency; too low can increase overhead.     |
| `active_send.read_chunk_bytes`                | `1024`                       | bytes                                                            | Serial read chunk size.                           | Adapter/performance tuning.                           | Too small may under-drain buffer; too large usually safe.    |
| `active_send.max_read_bytes_per_cycle`        | `8192`                       | bytes                                                            | Upper bound per worker cycle.                     | High-rate recovery tuning.                            | Too small can backlog; too large can monopolize loop.        |
| `active_send.clock_reanchor_max_drift_s`      | `0.050`                      | seconds                                                          | Free-running timestamp drift threshold.           | Only for non-default timing policies.                 | Bad value can reanchor too often or too late.                |
| `active_send.recovery_enabled`                | `true`                       | bool                                                             | Enables parser recovery from CRC/resync cascades. | Keep true for live operation.                         | False can leave parser stuck with stale buffer.              |
| `active_send.recovery_warning_threshold`      | `48`                         | count                                                            | Warnings before recovery.                         | Tune for noisy lines.                                 | Too low may discard unnecessarily; too high delays recovery. |
| `active_send.recovery_min_interval_s`         | `1.0`                        | seconds                                                          | Minimum time between recoveries.                  | Tune noisy hardware.                                  | Too low can thrash; too high can delay recovery.             |
| `active_send.recovery_reset_input_buffer`     | `true`                       | bool                                                             | Clears OS input buffer on recovery.               | Keep true for live stream recovery.                   | False may preserve stale bytes.                              |
| `active_send.max_binary_frame_bytes`          | `64`                         | bytes                                                            | Safety bound for frame size.                      | Only for alternate payloads.                          | Too low can reject valid frames.                             |
| `active_send.max_buffer_bytes`                | `8192`                       | bytes                                                            | Parser buffer cap.                                | Tune high-rate/backlog behavior.                      | Too low can discard data; too high uses memory.              |
| `active_send.frame_slave_id`                  | `1`                          | integer                                                          | Expected frame slave ID.                          | Match board.                                          | Mismatch rejects frames.                                     |
| `active_send.frame_function_code`             | `3`                          | Modbus function code                                             | Expected function code.                           | Match board payload.                                  | Mismatch rejects frames.                                     |
| `active_send.frame_register_count`            | `11`                         | count                                                            | Expected register payload.                        | Keep 11 for calibration QA.                           | Wrong count breaks decode.                                   |
| `active_send.log_first_n_good_frames`         | `5`                          | count                                                            | Initial good-frame logging.                       | Debug parser.                                         | Too high adds log noise.                                     |
| `active_send.log_summary_every_n_good_frames` | `250`                        | count                                                            | Periodic good-frame summary.                      | Debug long runs.                                      | Too low adds log noise.                                      |
| `active_send.log_bad_frame_hex_bytes`         | `64`                         | bytes                                                            | Bad-frame diagnostic hex length.                  | Debug parser.                                         | Too high creates large logs.                                 |
| `active_send.warning_emit_interval_s`         | `5.0`                        | seconds                                                          | Warning summary interval.                         | Debug parser warnings.                                | Too low floods logs.                                         |
| `active_send.detailed_warning_limit`          | `2`                          | count                                                            | Initial detailed warnings.                        | Debug.                                                | Too high floods logs.                                        |

## `logging`

| Key                     | Default | Type / range     | Impact                              | When to change                         | Failure risk                     |
| ----------------------- | ------- | ---------------- | ----------------------------------- | -------------------------------------- | -------------------------------- |
| `logging.root_level`    | `INFO`  | Python log level | Preferred root logging level alias. | Debugging.                             | Too verbose can add noise.       |
| `logging.module_levels` | `{}`    | mapping          | Per-module log overrides.           | Enable debug for specific module only. | Wrong module name has no effect. |

## Signal keys

| Signal key                | Meaning                                                            | Typical use                                             |
| ------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------- |
| `net_value`               | Net interpreted engineering value after tare/zero/decimal scaling. | Recommended reference force signal for IPC/calibration. |
| `gross_value`             | Gross interpreted value after decimal scaling.                     | Debug board gross vs net behavior.                      |
| `peak_value`              | Peak interpreted value.                                            | Peak capture workflows.                                 |
| `gross_raw_value`         | Raw signed 32-bit gross register pair.                             | Debug scaling/decimal behavior.                         |
| `net_raw_value`           | Raw signed 32-bit net register pair.                               | Debug raw reference chain.                              |
| `peak_raw_value`          | Raw peak register pair.                                            | Debug peak behavior.                                    |
| `internal_code_raw_value` | Internal board measurement code.                                   | Advanced diagnostics.                                   |
| `raw_value`               | Compatibility alias for primary raw value.                         | Legacy/debug only.                                      |

## Calibration-safe defaults

Use these unless a validation session proves a better profile:

```yaml
device:
  mode: active_send
  active_send_frequency_code: 8  # 500 Hz

serial:
  default_baudrate: 460800
  default_parity: N
  default_stopbits: 1

ipc:
  enabled: true
  topic: rs485.measurement.v1
  signal_key: net_value
  publish_after_max_rate_filter: false

ui:
  max_signal_samples_per_second: 0
  display_max_samples_per_second: 30
```

## Validation checklist

```bash
cd RS485_GUI
uv run pytest tests/unit/test_config.py
uv run rs485-gui --help
```

Also validate from root docs:

```bash
rg "rs485.measurement.v1|reference_force_N|reference_clock_s|reference_status" RS485_GUI/docs ../../docs/architecture/stream-contracts.md
```
