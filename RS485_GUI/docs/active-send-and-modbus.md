# Active-Send and Modbus RTU

## Summary

- `RS485_GUI` supports two acquisition modes for the high-speed acquisition board: `active_send` and `modbus_rtu`.
- **Active-Send** is the recommended high-rate reference acquisition mode for calibration after parser stability is validated.
- **Modbus RTU polling** is the simpler fallback/debug mode when Active-Send is not configured or not stable.
- Both modes produce the same internal `MeasurementFrame` abstraction and can feed the same logging, UI, and IPC publisher paths.

## Background: RS485 vs Modbus

RS485 and Modbus are complementary, not competing. RS485 (EIA/TIA-485) is the physical layer — differential signalling over twisted pair on a multipoint bus. Modbus is the application-layer message format (function codes and registers) that rides over that link. RS485 is the wire; Modbus is the language spoken on it.

- **Modbus RTU** is a passive poll/response scheme: the host requests registers and the board answers only when asked. It is deterministic and simple to inspect, but its effective rate is transaction-limited.
- **Active-Send** is not a Modbus protocol variant. The board is configured to autonomously and continuously push measurement frames over the same RS485 link, removing the per-sample request round-trip. This is what makes the high reference rate (500 Hz) used for calibration achievable.

Both modes carry the same 11-register board payload, which is decoded into one internal `MeasurementFrame` and published through the same path; see [RS485_GUI/docs/ipc-schema.md](ipc-schema.md) for the published field contract.

## Mode comparison

| Area              | Active-Send                                       | Modbus RTU polling                                   |
| ----------------- | ------------------------------------------------- | ---------------------------------------------------- |
| Config value      | `device.mode=active_send`                         | `device.mode=modbus_rtu`                             |
| Board behavior    | Board pushes measurement frames continuously.     | Host requests registers repeatedly.                  |
| Typical rate      | 500 Hz when `active_send_frequency_code=8`.       | Transaction-limited; usually lower than Active-Send. |
| Host timing       | Reconstructed from batch timing policy.           | Host poll/receive timestamp.                         |
| Commands to board | Not available through Active-Send transport.      | Available through command register path.             |
| Failure pattern   | CRC/resync/backlog warnings.                      | Timeout or Modbus response errors.                   |
| Best use          | Calibration/live reference stream once validated. | Bring-up, fallback, command testing, slow debug.     |

## Active-Send mode

Run:

```bash
cd RS485_GUI
uv run rs485-gui \
  serial.default_port=/dev/ttyUSB_RS485 \
  device.mode=active_send \
  serial.default_baudrate=460800
```

Important config keys:

| Key                                   | Recommended value            | Meaning                                                   |
| ------------------------------------- | ---------------------------- | --------------------------------------------------------- |
| `device.mode`                         | `active_send`                | Selects push-frame transport.                             |
| `device.active_send_frequency_code`   | `8`                          | Board code for 500 Hz.                                    |
| `active_send.default_parser_profile`  | `modbus_rtu_response_11regs` | Expected binary 11-register response payload.             |
| `active_send.timestamp_policy`        | `batch_end_anchored`         | Reconstructs frame timestamps inside each delivery batch. |
| `active_send.delivery_window_s`       | `0.010`                      | Low-latency delivery window.                              |
| `active_send.max_frames_per_delivery` | `16`                         | Keeps batches short enough for bridge freshness.          |
| `ipc.publish_after_max_rate_filter`   | `false`                      | Publishes full-rate frames before GUI display filtering.  |

### Active-Send timestamping

Default:

```yaml
active_send:
  timestamp_policy: batch_end_anchored
```

Meaning:

- The parser anchors each parsed batch to current LSL clock time.
- Frame times inside the batch are reconstructed from the configured board rate.
- This avoids long free-running drift when the effective RS485 frame rate is not exactly the nominal rate.

Use `host_receive` only as a debug fallback if timestamp reconstruction itself is suspect.

### Active-Send parser recovery

Active-Send byte streams can develop CRC/resync cascades if the serial buffer contains stale bytes or the board/host timing gets out of sync. Recovery settings:

| Key                                       | Purpose                                         |
| ----------------------------------------- | ----------------------------------------------- |
| `active_send.recovery_enabled`            | Enable stale-buffer recovery.                   |
| `active_send.recovery_warning_threshold`  | Number of warnings before recovery can trigger. |
| `active_send.recovery_min_interval_s`     | Minimum time between recoveries.                |
| `active_send.recovery_reset_input_buffer` | Reset OS serial input buffer on recovery.       |

Expected warning handling:

- A small number of warnings during connect may be acceptable.
- Continuous CRC/resync warnings mean the mode, baud, board output, or parser profile is wrong.
- Do not proceed to calibration while warnings continue.

## Modbus RTU polling mode

Run:

```bash
cd RS485_GUI
uv run rs485-gui \
  serial.default_port=/dev/ttyUSB_RS485 \
  device.mode=modbus_rtu
```

Important config keys:

| Key                          | Default | Meaning                                                            |
| ---------------------------- | ------- | ------------------------------------------------------------------ |
| `device.slave_address`       | `1`     | Board Modbus address.                                              |
| `device.poll_interval_s`     | `0.001` | Target host poll cadence; actual rate remains transaction-limited. |
| `device.read_start_register` | `0`     | First holding register to read.                                    |
| `device.read_register_count` | `11`    | Consecutive register count.                                        |
| `device.command_register`    | `11`    | Board command register.                                            |

Use Modbus RTU when:

- the board is not yet configured for Active-Send,
- you need to test board commands,
- Active-Send frames are malformed,
- you want a slower, more inspectable bring-up path.

## Shared decoded values

Both modes should produce interpreted fields such as:

| Field                     | Meaning                                                               |
| ------------------------- | --------------------------------------------------------------------- |
| `gross_value`             | Decimal-scaled gross board reading.                                   |
| `net_value`               | Decimal-scaled net board reading; recommended IPC/calibration signal. |
| `peak_value`              | Decimal-scaled peak board reading.                                    |
| `gross_raw_value`         | Raw gross register value.                                             |
| `net_raw_value`           | Raw net register value.                                               |
| `peak_raw_value`          | Raw peak register value.                                              |
| `internal_code_raw_value` | Board internal code.                                                  |
| `decimal_code`            | Board decimal-point code.                                             |
| `unit_label`              | Decoded engineering unit label.                                       |
| `status_word`             | Raw board status bitfield.                                            |
| `status_flags`            | Decoded status labels.                                                |
| `reference_force_N`       | Canonical alias used by IPC/bridge.                                   |
| `reference_clock_s`       | Canonical reference timestamp.                                        |
| `reference_status`        | Canonical status alias.                                               |

## Selecting mode during troubleshooting

| Symptom                             | Try                                                                                                 |
| ----------------------------------- | --------------------------------------------------------------------------------------------------- |
| No frames in Active-Send            | Confirm board Active-Send mode and baud; then test `device.mode=modbus_rtu`.                        |
| CRC failures / resyncs continuously | Verify baud, frame profile, board frequency, serial adapter quality, and cable.                     |
| Modbus timeouts                     | Verify A/B wiring, slave address, baud/parity/stop bits.                                            |
| GUI works but bridge is stale       | Confirm `ipc.publish_after_max_rate_filter=false` and Active-Send delivery window is not too large. |
| Viewer shows reference lag          | Inspect timestamp policy, delivery window, bridge timestamping, and viewer alignment.               |

## Calibration recommendation

For calibration after bring-up:

```yaml
device:
  mode: active_send
  active_send_frequency_code: 8

active_send:
  timestamp_policy: batch_end_anchored
  default_parser_profile: modbus_rtu_response_11regs
  delivery_window_s: 0.010
  max_frames_per_delivery: 16

ipc:
  signal_key: net_value
  publish_after_max_rate_filter: false
```

Stop before calibration if the GUI cannot produce stable, decoded `net_value` and IPC `reference_force_N` frames.
