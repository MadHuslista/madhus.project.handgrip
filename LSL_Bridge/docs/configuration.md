# LSL Bridge Configuration

## Summary

- `LSL_Bridge/conf/config.yaml` controls serial input, RS485 IPC input, LSL stream metadata, timestamping policy, optional processing, CSV persistence, and logging.
- The bridge is Hydra-driven, so most settings can be overridden from the command line using `key=value` syntax.
- Stream/channel settings are cross-component contracts. Change them only together with viewer, calibration, root architecture docs, and tests.

## Main config file

```text
LSL_Bridge/conf/config.yaml
```

## Override examples

```bash
cd LSL_Bridge
uv run lsl-bridge serial.port=/dev/serial/by-id/<target-arduino>
uv run lsl-bridge logging.level=DEBUG
uv run lsl-bridge rs485_ipc.enabled=false streams.reference.enabled=false
uv run lsl-bridge target_timestamping.policy=host_receive
```

## Top-level sections

| Section               | Purpose                                                           |
| --------------------- | ----------------------------------------------------------------- |
| `schema`              | Config/schema identity and description.                           |
| `session`             | Optional session metadata propagated into stream metadata.        |
| `streams`             | Target/reference LSL outlet names, types, metadata, and channels. |
| `component_events`    | LSL marker stream for bridge infrastructure events.               |
| `rs485_ipc`           | ZeroMQ subscriber for `RS485_GUI` reference measurements.         |
| `serial`              | Target Arduino serial port, baud, reconnect, and line limits.     |
| `target_timestamping` | LSL timestamp policy for target samples.                          |
| `protocol`            | D2/M2 parser delimiters/prefixes and numeric regex.               |
| `processing`          | Optional target processing/filter pipeline.                       |
| `csv`                 | Local CSV persistence for target/reference samples.               |
| `logging`             | Logging level, file path, and throttling.                         |
| `hydra`               | Working-directory behavior for Hydra runs.                        |

## `schema`

| Key                  | Default                  | Impact                                     | Safe edits                           |
| -------------------- | ------------------------ | ------------------------------------------ | ------------------------------------ |
| `schema.version`     | `handgrip_lsl_bridge.v2` | Identifies config schema in logs/metadata. | Change only with a config migration. |
| `schema.description` | text                     | Human-readable purpose.                    | Safe to edit.                        |

## `session`

| Key                    | Default      | Impact                                                                                         | Safe edits                               |
| ---------------------- | ------------ | ---------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `session.session_id`   | `null`       | Optional operator/session identifier propagated into stream metadata and CSVs where supported. | Safe to set per experiment.              |
| `session.component_id` | `LSL_Bridge` | Component identity.                                                                            | Do not change unless renaming component. |

## `streams.target`

Default target stream:

| Key              | Default                     | Impact                                                   | Safe edits                                              |
| ---------------- | --------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| `enabled`        | `true`                      | Enables target LSL outlet.                               | Disable only for reference-only debugging.              |
| `name`           | `HandgripTarget`            | LSL stream discovery name.                               | Cross-component change; update viewer/calibration/docs. |
| `type`           | `Force`                     | LSL stream type.                                         | Cross-component change.                                 |
| `source_id`      | `null`                      | If null, bridge builds a source ID from serial metadata. | Usually keep null.                                      |
| `manufacturer`   | `Arduino/HX711`             | LSL metadata.                                            | Safe if hardware changes.                               |
| `device_name`    | `HandgripTarget`            | LSL metadata.                                            | Keep aligned with stream role.                          |
| `nominal_srate`  | `0.0`                       | Irregular-rate target stream.                            | Keep `0.0` unless firmware becomes proven fixed-rate.   |
| `payload_schema` | `D2`                        | Documents firmware payload schema.                       | Change only with firmware/parser migration.             |
| `chunk_size`     | `1`                         | Push samples immediately.                                | Increase only after latency testing.                    |
| `schema`         | `handgrip_target_stream.v2` | Target stream schema metadata.                           | Change only with stream migration.                      |

Target channels:

| Config key        | Label                   | Type       | Unit       | Meaning                                    |
| ----------------- | ----------------------- | ---------- | ---------- | ------------------------------------------ |
| `seq`             | `seq`                   | `Sequence` | `count`    | Firmware sample sequence.                  |
| `device_clock_us` | `device_clock_us`       | `Time`     | `us`       | Firmware `micros()` timestamp.             |
| `raw_count`       | `target_raw_count`      | `ADCCount` | `count`    | Calibration-authoritative HX711 raw count. |
| `current_units`   | `target_current_units`  | `Force`    | `N`        | Firmware-scaled sanity value.              |
| `filtered_units`  | `target_filtered_units` | `Force`    | `N`        | Bridge-processed display/QA value.         |
| `status`          | `target_status`         | `Status`   | `bitfield` | Firmware status bitfield.                  |

## `streams.reference`

Default reference stream:

| Key             | Default                          | Impact                                          | Safe edits                                              |
| --------------- | -------------------------------- | ----------------------------------------------- | ------------------------------------------------------- |
| `enabled`       | `true`                           | Enables reference LSL outlet and IPC publisher. | Disable for target-only validation.                     |
| `name`          | `HandgripReference`              | LSL stream discovery name.                      | Cross-component change; update viewer/calibration/docs. |
| `type`          | `Force`                          | LSL stream type.                                | Cross-component change.                                 |
| `source_id`     | `rs485-acquisition-board-1`      | LSL source ID.                                  | Safe if hardware identity changes.                      |
| `manufacturer`  | `RS485 Acquisition Board`        | LSL metadata.                                   | Safe if board changes.                                  |
| `device_name`   | `HighSpeedAcquisitionInstrument` | LSL metadata.                                   | Safe if board model is renamed.                         |
| `nominal_srate` | `500.0`                          | Reference stream nominal rate.                  | Change only with board output profile.                  |
| `chunk_size`    | `1`                              | Push samples immediately.                       | Increase only after latency testing.                    |
| `schema`        | `handgrip_reference_stream.v2`   | Reference stream schema metadata.               | Change only with stream migration.                      |

Reference channels:

| Config key | Label               | Type       | Unit       | Meaning                                  |
| ---------- | ------------------- | ---------- | ---------- | ---------------------------------------- |
| `seq`      | `seq`               | `Sequence` | `count`    | RS485 GUI sequence value when available. |
| `clock`    | `reference_clock_s` | `Time`     | `s`        | Reference clock value from IPC payload.  |
| `force`    | `reference_force_N` | `Force`    | `N`        | Calibration ground-truth force channel.  |
| `status`   | `reference_status`  | `Status`   | `bitfield` | Reference/transport status.              |

## `component_events`

| Key         | Default                       | Impact                                             | Safe edits                                       |
| ----------- | ----------------------------- | -------------------------------------------------- | ------------------------------------------------ |
| `enabled`   | `true`                        | Publishes `HandgripComponentEvents` marker stream. | Keep enabled for diagnostics and calibration QA. |
| `name`      | `HandgripComponentEvents`     | LSL marker stream name.                            | Cross-component change.                          |
| `type`      | `Markers`                     | LSL marker type.                                   | Keep unless event consumers migrate.             |
| `source_id` | `handgrip-lsl-bridge-events`  | LSL event source ID.                               | Safe only if source identity changes.            |
| `schema`    | `handgrip_component_event.v1` | JSON marker schema metadata.                       | Change only with event schema migration.         |

## `rs485_ipc`

| Key                     | Default                | Impact                                  | Safe edits                                              |
| ----------------------- | ---------------------- | --------------------------------------- | ------------------------------------------------------- |
| `enabled`               | `true`                 | Enables RS485 GUI IPC subscriber.       | Disable only for target-only validation.                |
| `transport`             | `zmq_sub`              | Transport implementation.               | Change requires code migration.                         |
| `connect`               | `tcp://127.0.0.1:5557` | ZMQ endpoint to connect to `RS485_GUI`. | Change if RS485 GUI uses a different bind address/port. |
| `topic`                 | `rs485.measurement.v1` | Subscribed IPC topic.                   | Cross-component change with `RS485_GUI`.                |
| `receive_hwm`           | `5000`                 | ZMQ receive high-water mark.            | Increase if bursts are dropped; monitor memory.         |
| `log_status_every_s`    | `5.0`                  | Reference status log interval.          | Safe.                                                   |
| `expected_schema`       | `rs485.measurement.v1` | Enforced on every IPC message.          | Cross-component schema migration only.                  |
| `poll_interval_s`       | `0.001`                | Sleep when ZMQ queue is empty.          | Tune CPU vs latency.                                    |
| `error_backoff_s`       | `0.05`                 | Sleep after ZMQ transport error.        | Safe.                                                   |
| `log_malformed_every_n` | `100`                  | Malformed IPC log throttle.             | Lower for debugging, raise for noisy runs.              |

## `serial`

| Key                   | Default        | Impact                                                   | Safe edits                                                |
| --------------------- | -------------- | -------------------------------------------------------- | --------------------------------------------------------- |
| `port`                | `/dev/ttyUSB1` | Target Arduino serial device.                            | Common operator override. Prefer `/dev/serial/by-id/...`. |
| `baudrate`            | `115200`       | Firmware UART speed.                                     | Must match firmware.                                      |
| `timeout_s`           | `0.25`         | Serial read timeout.                                     | Safe if slow/noisy device.                                |
| `reconnect_backoff_s` | `2.0`          | Delay after serial failure.                              | Safe.                                                     |
| `startup_settle_s`    | `2.0`          | Time to let Arduino reset/settle after opening serial.   | Increase if boot metadata is missed.                      |
| `max_line_bytes`      | `256`          | Overlong line protection.                                | Increase only if protocol expands intentionally.          |
| `transport_latency_s` | `0.0`          | Constant correction for measured serial transport delay. | Keep zero unless measured.                                |

## `target_timestamping`

| Key                     | Default               | Impact                                                                                        | Safe edits                                           |
| ----------------------- | --------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `policy`                | `device_clock_anchor` | Publishes target samples in LSL time using device-clock deltas anchored to host receive time. | Use `host_receive` for lowest-risk debugging.        |
| `reset_on_nonmonotonic` | `true`                | Re-anchor if firmware clock moves backward.                                                   | Usually keep true.                                   |
| `max_gap_s`             | `1.0`                 | Re-anchor after large device-clock gaps.                                                      | Tune for long pauses/reconnects.                     |
| `max_anchor_drift_s`    | `0.050`               | Re-anchor if device-derived time drifts too far from host arrival.                            | Tune when viewer shows growing reference/target lag. |
| `monotonic_epsilon_s`   | `1e-9`                | Minimum monotonic increment guard.                                                            | Do not change unless debugging timestamp precision.  |

See [`timestamping.md`](timestamping.md).

## `protocol`

| Key                      | Default                        | Impact                                          | Safe edits                        |
| ------------------------ | ------------------------------ | ----------------------------------------------- | --------------------------------- |
| `delimiter`              | `,`                            | Serial field separator.                         | Must match firmware.              |
| `data_prefix`            | `D2`                           | Data frame prefix.                              | Must match firmware/parser/tests. |
| `metadata_prefix`        | `M2`                           | Metadata frame prefix.                          | Must match firmware/parser/tests. |
| `accepted_numeric_regex` | numeric regex with `nan`/`inf` | Controls strict numeric matching for D2 fields. | Change only with parser tests.    |

## `processing`

| Key                | Default                   | Impact                                         | Safe edits                                            |
| ------------------ | ------------------------- | ---------------------------------------------- | ----------------------------------------------------- |
| `module`           | `lsl_bridge.core.filter`  | Runtime module used to build target processor. | Change only if implementing a new processor module.   |
| `timestamp_source` | `device_clock_us`         | Filter-domain time source.                     | Use `lsl` if processor should use LSL timestamps.     |
| `filters[0].type`  | `butterworth_lowpass_2nd` | Processor/filter type.                         | Change with `test_filter.py` coverage.                |
| `filters[0].name`  | `butter_lowpass_9hz`      | Filter identifier.                             | Safe.                                                 |
| `sample_rate_hz`   | `100.0`                   | Assumed target filter sample rate.             | Must match expected target cadence for filter design. |
| `cutoff_hz`        | `9.0`                     | Low-pass cutoff.                               | Change only after analysis validation.                |
| `q`                | `0.7071067811865475`      | Butterworth Q.                                 | Keep unless filter design changes.                    |
| `reset_on_gap_s`   | `1.0`                     | Reset filter state after target gaps.          | Tune for dropout behavior.                            |
| `min_dt_s`         | `0.000001`                | Minimum dt guard.                              | Do not change unless filter stability requires it.    |

Important: the processing output `target_filtered_units` is for display/QA unless explicitly promoted by a validated workflow. Calibration should preserve and fit `target_raw_count`.

## `csv`

| Key                                | Default                                          | Impact                                 |
| ---------------------------------- | ------------------------------------------------ | -------------------------------------- |
| `csv.target.enabled`               | `true`                                           | Writes target samples to local CSV.    |
| `csv.target.path`                  | `LSL_Bridge/data/target_handgrip_samples_v2.csv` | Target CSV destination.                |
| `csv.target.append`                | `false`                                          | Truncate vs append.                    |
| `csv.target.flush_every_n_rows`    | `1`                                              | Low-latency target persistence.        |
| `csv.reference.enabled`            | `true`                                           | Writes reference samples to local CSV. |
| `csv.reference.path`               | `LSL_Bridge/data/reference_rs485_samples_v2.csv` | Reference CSV destination.             |
| `csv.reference.append`             | `false`                                          | Truncate vs append.                    |
| `csv.reference.flush_every_n_rows` | `25`                                             | Batches higher-rate reference writes.  |

See [`architecture.md`](architecture.md) for CSV sink ownership and [`stream-contracts.md`](stream-contracts.md) for CSV field meanings.

## `logging`

| Key                        | Default                               | Impact                                         |
| -------------------------- | ------------------------------------- | ---------------------------------------------- |
| `level`                    | `INFO`                                | Console/file log threshold.                    |
| `file`                     | `LSL_Bridge/logs/lsl_bridge.log`      | File handler destination. Set null to disable. |
| `format`                   | standard timestamp/name/level/message | Log line format.                               |
| `log_every_n_samples`      | `200`                                 | Target sample status log throttle.             |
| `log_parse_errors_every_n` | `20`                                  | Target parse error log throttle.               |

## `hydra`

| Key                   | Default | Impact                                                 |
| --------------------- | ------- | ------------------------------------------------------ |
| `hydra.run.dir`       | `.`     | Keeps Hydra from moving output to per-run directories. |
| `hydra.output_subdir` | `null`  | Avoids `.hydra` output subdir.                         |
| `hydra.job.chdir`     | `false` | Keeps process CWD stable for relative paths.           |

## Validation commands

```bash
# Confirm key config contracts.
rg 'name: HandgripTarget|name: HandgripReference|name: HandgripComponentEvents' LSL_Bridge/conf/config.yaml
rg 'topic: rs485.measurement.v1|expected_schema: rs485.measurement.v1' LSL_Bridge/conf/config.yaml
rg 'policy: device_clock_anchor|max_anchor_drift_s' LSL_Bridge/conf/config.yaml
rg 'data_prefix: D2|metadata_prefix: M2' LSL_Bridge/conf/config.yaml
```
