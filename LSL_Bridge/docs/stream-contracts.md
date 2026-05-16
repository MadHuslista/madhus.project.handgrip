# LSL Bridge Stream Contracts

## Summary

- `LSL_Bridge` owns runtime conversion from target UART and RS485 IPC into Lab Streaming Layer streams.
- The target side consumes current firmware `M2` / `D2` frames.
- The reference side consumes `RS485_GUI` ZeroMQ messages on `rs485.measurement.v1`.
- This document is the component-specific implementation contract. The root contract remains [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md).

## Inputs

### Target UART input

Current metadata frame:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

Current data frame:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

The parser is strict. Malformed lines are dropped/logged instead of guessed.

### Reference IPC input

| Field     | Value                                         |
| --------- | --------------------------------------------- |
| Producer  | `RS485_GUI`                                   |
| Consumer  | `LSL_Bridge`                                  |
| Topic     | `rs485.measurement.v1`                        |
| Transport | ZeroMQ PUB/SUB                                |
| Decoder   | `RS485IpcReferencePublisher._decode_record()` |

Required IPC fields:

| Field               | Meaning                                 |
| ------------------- | --------------------------------------- |
| `schema`            | Must match `rs485.measurement.v1`.      |
| `reference_force_N` | Reference-force value published to LSL. |
| `reference_clock_s` | Reference clock/sample time in seconds. |
| `host_lsl_ts`       | Host-side LSL timestamp from RS485 GUI. |

Optional IPC fields preserved in `ReferenceSample`/CSV:

| Field                     | Meaning                                          |
| ------------------------- | ------------------------------------------------ |
| `seq`                     | Reference sequence, if available.                |
| `reference_status`        | Reference/transport status.                      |
| `mode`                    | Acquisition mode label.                          |
| `signal_key`              | Source signal key, normally `reference_force_N`. |
| `host_unix_ts`            | Host UNIX timestamp.                             |
| `clock_source`            | Reference clock source label.                    |
| `unit_label`              | Unit label, normally `N`.                        |
| `timestamp_source`        | Timestamp-source label.                          |
| `configured_frequency_hz` | Configured board/source rate.                    |
| `session_id`              | Optional session ID.                             |
| `board_profile`           | Optional board profile metadata.                 |

## Outputs

### `HandgripTarget`

| Property        | Value                                            |
| --------------- | ------------------------------------------------ |
| Producer        | `LSL_Bridge` target serial loop                  |
| Source          | firmware D2 frames                               |
| LSL name        | `HandgripTarget`                                 |
| LSL type        | `Force`                                          |
| Nominal rate    | `0.0` / irregular                                |
| Schema metadata | `handgrip_target_stream.v2`                      |
| Main consumers  | `LSL_Viewer`, `Handgrip_Calibration`, recordings |

Channel order pushed to LSL:

| Position | Label                   | Source                   | Meaning                                         |
| -------: | ----------------------- | ------------------------ | ----------------------------------------------- |
|        0 | `seq`                   | D2 `seq`                 | Target sample sequence.                         |
|        1 | `device_clock_us`       | D2 `timestamp_us`        | Firmware device clock in microseconds.          |
|        2 | `target_raw_count`      | D2 `raw_count`           | HX711 raw ADC count; calibration-authoritative. |
|        3 | `target_current_units`  | D2 `current_units`       | Firmware-scaled force/value.                    |
|        4 | `target_filtered_units` | bridge processing output | Filtered display/QA channel.                    |
|        5 | `target_status`         | D2 `status`              | Firmware status bitfield.                       |

### `HandgripReference`

| Property        | Value                                            |
| --------------- | ------------------------------------------------ |
| Producer        | `LSL_Bridge` RS485 IPC background publisher      |
| Source          | `RS485_GUI` IPC                                  |
| LSL name        | `HandgripReference`                              |
| LSL type        | `Force`                                          |
| Nominal rate    | `500.0`                                          |
| Schema metadata | `handgrip_reference_stream.v2`                   |
| Main consumers  | `LSL_Viewer`, `Handgrip_Calibration`, recordings |

Channel order pushed to LSL:

| Position | Label               | Source                  | Meaning                                           |
| -------: | ------------------- | ----------------------- | ------------------------------------------------- |
|        0 | `seq`               | IPC `seq` or `-1`       | Reference sample sequence.                        |
|        1 | `reference_clock_s` | IPC `reference_clock_s` | Reference/sample clock in seconds.                |
|        2 | `reference_force_N` | IPC `reference_force_N` | Reference force used as calibration ground truth. |
|        3 | `reference_status`  | IPC `reference_status`  | Reference/transport status bitfield.              |

### `HandgripComponentEvents`

| Property | Value                                       |
| -------- | ------------------------------------------- |
| Producer | `LSL_Bridge` `ComponentEventOutlet`         |
| LSL name | `HandgripComponentEvents`                   |
| LSL type | `Markers`                                   |
| Schema   | `handgrip_component_event.v1`               |
| Payload  | single JSON string per event                |
| Purpose  | Infrastructure markers for audit/debugging. |

Representative event names:

| Event                       | Meaning                                         |
| --------------------------- | ----------------------------------------------- |
| `bridge_start`              | Bridge process started.                         |
| `bridge_stop`               | Bridge process stopped.                         |
| `target_serial_connected`   | Target serial port opened and LSL outlet ready. |
| `target_serial_error`       | Serial exception/reconnect path.                |
| `target_metadata`           | Firmware M2 metadata received.                  |
| `target_sequence_gap`       | D2 `seq` discontinuity detected.                |
| `target_timestamp_reanchor` | Timestamp resolver re-anchored target stream.   |
| `reference_ipc_connected`   | ZMQ reference IPC subscriber connected.         |
| `reference_ipc_malformed`   | IPC message failed schema/field decoding.       |
| `reference_sequence_gap`    | Reference `seq` discontinuity detected.         |

The bridge event stream is intentionally separate from calibration trial markers. `Handgrip_Calibration` owns experiment/protocol markers.

## CSV persistence contract

Target CSV field order:

```text
host_unix_time_ns,lsl_timestamp_s,seq,device_clock_us,target_raw_count,target_current_units,target_filtered_units,target_status,raw_line
```

Reference CSV field order:

```text
host_unix_ts,received_lsl_ts,lsl_timestamp_s,seq,reference_clock_s,reference_force_N,reference_status,rs485_mode,rs485_signal_key,rs485_clock_source,unit_label,timestamp_source,configured_frequency_hz,session_id
```

CSV files are local persistence of what the bridge published. They are useful for debug and replay, but calibration sessions should still use the canonical recording workflow when available.

## Calibration implications

Calibration should fit:

```text
reference_force_N = f(target_raw_count)
```

Do not fit primarily against `target_current_units` or `target_filtered_units` unless a protocol explicitly states that it is validating already-deployed processing.

## Change-control rule

If any field, channel label, channel order, stream name, or IPC field changes, update together:

1. `LSL_Bridge/conf/config.yaml`,
2. bridge source code,
3. parser/reference publisher tests,
4. root `docs/architecture/stream-contracts.md`,
5. this document,
6. `LSL_Viewer` config/docs,
7. `Handgrip_Calibration` config/docs.

## Validation commands

```bash
uv run pytest tests/unit/test_parser.py
uv run pytest tests/unit/test_timestamping.py
uv run pytest tests/integration/test_csv_sinks.py

rg "HandgripTarget|HandgripReference|HandgripComponentEvents" LSL_Bridge/conf/config.yaml LSL_Bridge/docs
rg "rs485.measurement.v1" LSL_Bridge/conf/config.yaml LSL_Bridge/docs ../../docs/architecture/stream-contracts.md
```
