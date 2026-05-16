# RS485 GUI Logging and Outputs

## Summary

- `RS485_GUI` writes raw transport, interpreted engineering values, GUI-oriented CSV samples, event logs, and optional debug logs.
- Logging is controlled by the `logger` and `logging` sections of `RS485_GUI/config/config.yaml`.
- File logging is full-rate for acquisition frames unless the acquisition-level limiter is enabled.
- Browser display downsampling does not reduce file logging or IPC publication when default calibration-safe settings are used.

## Output locations

Default output directory:

```text
RS485_GUI/logs/
```

Default files:

| File                        | Format                 | Purpose                                                                                   |
| --------------------------- | ---------------------- | ----------------------------------------------------------------------------------------- |
| `raw_signal.ndjson`         | newline-delimited JSON | Raw transport audit trail: bytes/registers, mode, timestamps, board profile.              |
| `interpreted_signal.ndjson` | newline-delimited JSON | Decoded engineering values and metadata.                                                  |
| `gui_signal.csv`            | CSV                    | Spreadsheet-friendly flat signal log.                                                     |
| `event.log`                 | plain text             | Operator/runtime events such as connect, disconnect, parser config, logger paths, errors. |
| `acquisition_debug.log`     | Python log text        | Root/module logs when `logger.debug_log_to_file=true`.                                    |

## Config section

```yaml
logger:
  enabled: true
  directory: RS485_GUI/logs
  write_mode: overwrite
  raw_signal_filename: raw_signal.ndjson
  interpreted_signal_filename: interpreted_signal.ndjson
  gui_signal_filename: gui_signal.csv
  debug_log_to_file: true
  debug_log_filename: acquisition_debug.log
  event_log_filename: event.log
  flush_every_n_batches: 25
  flush_interval_s: 1.0
```

## Raw signal log

Default file:

```text
RS485_GUI/logs/raw_signal.ndjson
```

One JSON object per acquired frame.

Expected fields:

| Field             | Meaning                                 |
| ----------------- | --------------------------------------- |
| `host_ts_epoch_s` | Host Unix timestamp.                    |
| `host_ts_iso`     | Human-readable host timestamp.          |
| `session_id`      | Session identifier if configured.       |
| `mode`            | `active_send` or `modbus_rtu`.          |
| `raw_transport`   | Wire-level bytes/registers/diagnostics. |
| `board_profile`   | Board/runtime profile snapshot.         |

Use this file when debugging parser behavior, CRC failures, register maps, or source traceability.

## Interpreted signal log

Default file:

```text
RS485_GUI/logs/interpreted_signal.ndjson
```

One JSON object per decoded frame.

Expected fields:

| Field             | Meaning                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| `host_ts_epoch_s` | Host Unix timestamp.                                                                               |
| `host_ts_iso`     | Human-readable host timestamp.                                                                     |
| `session_id`      | Session identifier.                                                                                |
| `mode`            | Acquisition mode.                                                                                  |
| `interpreted`     | Decoded values: `net_value`, `gross_value`, `reference_force_N`, `status_word`, clocks, unit, etc. |
| `board_profile`   | Board/runtime profile snapshot.                                                                    |

Use this file for debugging engineering values and confirming what IPC should publish.

## GUI signal CSV

Default file:

```text
RS485_GUI/logs/gui_signal.csv
```

Header:

```csv
host_ts_epoch_s,host_ts_iso,session_id,mode,reference_force_N,reference_clock_s,reference_status,plot_signal_key,plot_value
```

Use this file for quick spreadsheet inspection. It is intentionally flatter than the NDJSON logs.

## Event log

Default file:

```text
RS485_GUI/logs/event.log
```

Events can include:

- worker start/stop,
- connect/disconnect,
- parser config,
- logger path summary,
- active-send warnings,
- acquisition errors,
- operator actions where implemented.

Use this file first when reconstructing what happened during a run.

## Debug log

Default file:

```text
RS485_GUI/logs/acquisition_debug.log
```

Controlled by:

```yaml
logger:
  debug_log_to_file: true
  debug_log_filename: acquisition_debug.log

logging:
  root_level: INFO
  module_levels: {}
```

Enable targeted debug output using module levels:

```bash
uv run rs485-gui \
  logging.module_levels.rs485_gui.transport.active_send=DEBUG \
  logging.module_levels.rs485_gui.io.publisher=DEBUG
```

## Write mode

| Mode        | Behavior                                | Use case                              | Risk                                         |
| ----------- | --------------------------------------- | ------------------------------------- | -------------------------------------------- |
| `overwrite` | Replaces previous logs at startup/open. | Clean single-run validation.          | Can erase prior run logs.                    |
| `append`    | Appends to existing logs.               | Long-running or cumulative debug log. | Can mix sessions unless `session_id` is set. |

For calibration, prefer a unique session/log directory or ensure logs are captured into the calibration session folder if the workflow supports it.

## Flush policy

| Setting                 | Default | Meaning                              |
| ----------------------- | ------- | ------------------------------------ |
| `flush_every_n_batches` | `25`    | Flush after this many write batches. |
| `flush_interval_s`      | `1.0`   | Flush at least this often.           |

Tradeoff:

- lower values improve crash durability,
- higher values reduce disk overhead and GUI/process jitter.

## Retention and cleanup

Recommended policy:

| Artifact                                | Keep?                        | Notes                                                   |
| --------------------------------------- | ---------------------------- | ------------------------------------------------------- |
| Logs from accepted calibration sessions | Yes                          | Preserve with session or archive.                       |
| Logs from smoke tests                   | Optional                     | Keep only if debugging later.                           |
| Logs from failed bring-up               | Keep until issue is resolved | Useful for reproducing hardware/communication failures. |
| Generated logs in documentation commits | Usually no                   | Do not commit routine logs unless curated as examples.  |

## Validation commands

```bash
cd RS485_GUI
uv run pytest tests/integration/test_file_logger.py

# After a manual run:
test -f logs/raw_signal.ndjson
test -f logs/interpreted_signal.ndjson
test -f logs/gui_signal.csv
test -f logs/event.log
head -1 logs/gui_signal.csv
```

Expected CSV header:

```text
host_ts_epoch_s,host_ts_iso,session_id,mode,reference_force_N,reference_clock_s,reference_status,plot_signal_key,plot_value
```
