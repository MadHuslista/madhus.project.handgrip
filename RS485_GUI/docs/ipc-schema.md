# RS485 GUI IPC Schema

## Summary

- `RS485_GUI` publishes reference acquisition data to `LSL_Bridge` over ZeroMQ PUB/SUB.
- Measurement topic: `rs485.measurement.v1`.
- Event topic: `rs485.event.v1`.
- The measurement payload includes canonical aliases consumed by `LSL_Bridge`: `reference_force_N`, `reference_clock_s`, `reference_status`, `board_profile`, and `session_id`.
- The IPC publisher is best-effort and can drop frames under backpressure when `ipc.drop_on_backpressure=true`.

## Configuration

```yaml
ipc:
  enabled: true
  transport: zmq_pub
  bind: tcp://127.0.0.1:5557
  topic: rs485.measurement.v1
  event_topic: rs485.event.v1
  signal_key: net_value
  send_hwm: 2000
  linger_ms: 0
  drop_on_backpressure: true
  start_on_app_launch: false
  start_on_connect: true
  stop_on_disconnect: true
  require_pylsl_clock: true
  publish_after_max_rate_filter: false
```

## Lifecycle

| Stage            | Behavior                                                                                                         |
| ---------------- | ---------------------------------------------------------------------------------------------------------------- |
| App construction | Publisher object can exist, but ZMQ endpoint should not bind when `start_on_app_launch=false`.                   |
| Connect          | Publisher binds when `start_on_connect=true`.                                                                    |
| Acquisition loop | Worker publishes frames at full acquisition rate before UI filtering when `publish_after_max_rate_filter=false`. |
| Disconnect       | Publisher closes when `stop_on_disconnect=true`.                                                                 |

The delayed bind is intentional: NiceGUI can re-execute the application module while serving pages, and binding during construction can cause false port-conflict errors.

## Measurement topic

| Field            | Value                        |
| ---------------- | ---------------------------- |
| Topic            | `rs485.measurement.v1`       |
| Transport        | ZeroMQ multipart PUB message |
| Producer         | `RS485_GUI`                  |
| Consumer         | `LSL_Bridge`                 |
| Payload encoding | JSON object encoded as UTF-8 |

### Measurement payload

Representative payload shape:

```json
{
  "schema": "rs485.measurement.v1",
  "seq": 1,
  "session_id": "2026-05-15_120000_handgrip_cal",
  "mode": "active_send",
  "signal_key": "net_value",
  "reference_force_N": 12.345,
  "reference_clock_s": 123456.789,
  "reference_status": 0,
  "rs485_raw": 12.345,
  "rs485_clock": 123456.789,
  "rs485_clock_source": "reconstructed_from_active_send_rate_batch_end_anchored",
  "host_lsl_ts": 123456.790,
  "host_unix_ts": 1778880000.123,
  "host_ts_iso": "2026-05-15T12:00:00.123",
  "unit_label": "N",
  "status_word": 0,
  "timestamp_source": "reconstructed_from_active_send_rate_batch_end_anchored",
  "configured_frequency_hz": 500,
  "parsed_from": "modbus_rtu_response_11regs",
  "board_profile": {}
}
```

### Canonical measurement fields

| Field               | Type    | Meaning                                           | Consumer behavior                                |
| ------------------- | ------- | ------------------------------------------------- | ------------------------------------------------ |
| `schema`            | string  | Payload schema name.                              | Should equal `rs485.measurement.v1`.             |
| `seq`               | integer | Publisher-local sequence number.                  | Detect publish drops/restarts.                   |
| `session_id`        | string  | Active session identifier.                        | Preserve calibration/run provenance.             |
| `mode`              | string  | `active_send` or `modbus_rtu`.                    | Debug acquisition mode.                          |
| `signal_key`        | string  | Source signal used for `reference_force_N`.       | Verify calibration signal.                       |
| `reference_force_N` | float   | Canonical reference value for bridge/calibration. | Primary value consumed by `LSL_Bridge`.          |
| `reference_clock_s` | float   | LSL-aligned reference timestamp.                  | Used by bridge timestamping/fusion.              |
| `reference_status`  | integer | Canonical reference status.                       | Used for QA and troubleshooting.                 |
| `board_profile`     | object  | Board/runtime profile snapshot.                   | Late subscribers still receive profile metadata. |

### Retained aliases

| Field                     | Meaning                                                    |
| ------------------------- | ---------------------------------------------------------- |
| `rs485_raw`               | Human/debug alias for published numeric value.             |
| `rs485_clock`             | Human/debug alias for reference clock.                     |
| `rs485_clock_source`      | Origin of reference clock.                                 |
| `host_lsl_ts`             | Host LSL clock at publication/build time.                  |
| `host_unix_ts`            | Host Unix timestamp.                                       |
| `host_ts_iso`             | Human-readable host timestamp.                             |
| `unit_label`              | Decoded board engineering unit.                            |
| `status_word`             | Raw board status word when available.                      |
| `timestamp_source`        | Timestamp origin from decoding path.                       |
| `configured_frequency_hz` | Active-Send configured/expected frame rate when available. |
| `parsed_from`             | Parser profile or decoding path.                           |

## Event topic

| Field            | Value                                        |
| ---------------- | -------------------------------------------- |
| Topic            | `rs485.event.v1`                             |
| Transport        | ZeroMQ multipart PUB message                 |
| Producer         | `RS485_GUI`                                  |
| Consumer         | diagnostics / bridge / logs where applicable |
| Payload encoding | JSON object encoded as UTF-8                 |

Representative event payload:

```json
{
  "schema": "rs485.event.v1",
  "session_id": "2026-05-15_120000_handgrip_cal",
  "event": "serial_connected",
  "host_unix_ts": 1778880000.123,
  "host_ts_iso": "2026-05-15T12:00:00.123",
  "board_profile": {},
  "port": "/dev/ttyUSB1",
  "mode": "active_send"
}
```

## Session IDs

`session_id` can come from:

| Source                      | Notes                                                          |
| --------------------------- | -------------------------------------------------------------- |
| `session.session_id` config | Manual/operator-specified.                                     |
| `AppState` runtime session  | Used when calibration/session integration sets it.             |
| empty string                | Allowed for non-calibration debug runs, but less reproducible. |

Calibration sessions should prefer a non-empty session ID so RS485 logs and IPC records can be joined with target/reference calibration outputs.

## Backpressure and drops

When `ipc.drop_on_backpressure=true`, the publisher uses non-blocking sends. This protects acquisition/UI responsiveness but can drop IPC messages if downstream subscribers cannot keep up.

| Setting                | Effect                         |
| ---------------------- | ------------------------------ |
| `send_hwm`             | ZMQ high-water mark.           |
| `drop_on_backpressure` | Non-blocking publish behavior. |
| `log_every_s`          | Status logging interval.       |

If bridge reference data is stale or missing:

1. Check GUI event/debug logs for publish drops.
2. Check that `LSL_Bridge` subscribes to the same endpoint/topic.
3. Check whether another process already bound `tcp://127.0.0.1:5557`.
4. Confirm `publish_after_max_rate_filter=false` for calibration/full-rate IPC.

## Contract change rules

Any change to IPC field names or topic names is a cross-component change. Update together:

1. `RS485_GUI/config/config.yaml`,
2. `RS485_GUI/src/rs485_gui/io/publisher.py`,
3. `LSL_Bridge` subscriber/parser/config,
4. [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md),
5. this document,
6. bridge and GUI tests.

## Validation commands

```bash
uv run pytest RS485_GUI/tests/integration/test_file_logger.py
```
