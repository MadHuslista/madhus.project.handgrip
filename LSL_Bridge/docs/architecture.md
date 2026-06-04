# LSL Bridge Architecture

## Summary

- `LSL_Bridge` is a Hydra-driven runtime application that connects target firmware serial input and RS485 GUI IPC input to LSL outlets.
- The target loop runs in the foreground and auto-reconnects on serial exceptions.
- The reference IPC publisher runs in a background daemon thread.
- Component events are published as a sparse LSL marker stream.
- Optional CSV sinks persist the exact target/reference samples published by the bridge.

## Runtime lifecycle

```text
main()
  → Hydra config load
  → configure logging
  → build HandgripComponentEvents outlet
  → open target/reference CSV sinks
  → build HandgripReference outlet
  → start RS485 IPC reference publisher thread
  → build parser, processor, timestamp resolvers
  → serial reconnect loop
      → open target serial port
      → settle serial input
      → build HandgripTarget outlet
      → read D2 lines
      → parse target sample
      → resolve LSL timestamp
      → process target_current_units
      → push HandgripTarget sample
      → write target CSV
  → KeyboardInterrupt
      → emit bridge_stop
      → stop reference publisher
      → close CSV sinks
```

## Source module map

| Module                            | Responsibility                                                    |
| --------------------------------- | ----------------------------------------------------------------- |
| `lsl_bridge.app`                  | Main Hydra entry point and lifecycle orchestration.               |
| `lsl_bridge.core.parser`          | Strict D2/M2 target UART parser and metadata handling.            |
| `lsl_bridge.core.timestamping`    | Target LSL timestamp policy and processor-domain time resolution. |
| `lsl_bridge.core.filter`          | Current target processing implementation.                         |
| `lsl_bridge.core.processing`      | Runtime processor module loading / processor factory.             |
| `lsl_bridge.io.lsl_outlets`       | Build target/reference LSL StreamInfo and outlets.                |
| `lsl_bridge.io.csv_sinks`         | Persist target/reference samples to CSV.                          |
| `lsl_bridge.io.serial_utils`      | Serial port metadata and startup settling helpers.                |
| `lsl_bridge.publishers.reference` | Background RS485 IPC subscriber and reference LSL publisher.      |
| `lsl_bridge.publishers.events`    | Component event marker outlet.                                    |
| `lsl_bridge.types`                | Shared dataclass contracts.                                       |
| `lsl_bridge.logging_setup`        | Console/file logging configuration.                               |

## Serial input path

Target serial data path:

```text
Serial.readline()
  → D2LineParser.feed()
  → ParsedTargetSample
  → TargetTimestampResolver.resolve()
  → SampleTimeResolver.resolve()
  → processor.process()
  → target_outlet.push_sample()
  → TargetCsvSink.write()
```

Design points:

- Overlong target lines are dropped and serial input is flushed.
- Non-D2 lines are dropped and log-throttled.
- Sequence gaps emit `target_sequence_gap` events.
- Metadata frames emit `target_metadata` events.

## IPC input path

Reference IPC path:

```text
ZMQ SUB recv_multipart(NOBLOCK)
  → JSON decode
  → _decode_record()
  → ReferenceSample
  → reference_outlet.push_sample()
  → ReferenceCsvSink.write()
  → status logging / gap events
```

Design points:

- The expected schema is enforced on every IPC message.
- Legacy IPC aliases are not accepted.
- Malformed messages emit `reference_ipc_malformed` events.
- Sequence gaps emit `reference_sequence_gap` events.

## LSL outlets

| Outlet                    | Builder                    | Notes                                                                                                                     |
| ------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `HandgripTarget`          | `build_target_outlet()`    | Target stream metadata includes schema, session ID, firmware metadata, timestamping policy, and calibration signal notes. |
| `HandgripReference`       | `build_reference_outlet()` | Reference stream metadata includes schema, session ID, endpoint, nominal rate, and fit signal.                            |
| `HandgripComponentEvents` | `ComponentEventOutlet`     | One JSON string marker per infrastructure event.                                                                          |

## CSV persistence

CSV sinks write the samples the bridge publishes.

| Sink               | File path config     | Flush default | Notes                                                                                    |
| ------------------ | -------------------- | ------------- | ---------------------------------------------------------------------------------------- |
| `TargetCsvSink`    | `csv.target.path`    | every row     | Includes raw line and filtered target value.                                             |
| `ReferenceCsvSink` | `csv.reference.path` | every 25 rows | Includes reference mode, signal key, timestamp source, configured frequency, session ID. |

CSV persistence is useful for debugging. Calibration workflows should still use dedicated calibration session recordings when available.

## Processing path

Current processing:

- input: `target_current_units`,
- processor: `butterworth_lowpass_2nd`,
- output: `target_filtered_units`,
- default cutoff: `9 Hz`,
- filter-domain time source: `device_clock_us`.

Important boundary:

> `target_filtered_units` is a display/QA channel unless a future validated workflow explicitly promotes it. Calibration should preserve and fit `target_raw_count`.

## Failure isolation

| Failure                        | Likely module                                                |
| ------------------------------ | ------------------------------------------------------------ |
| target serial port cannot open | `app.py`, OS serial permissions, config `serial.port`        |
| D2 lines dropped               | `core/parser.py`, firmware serial output, `protocol` config  |
| reference missing              | `publishers/reference.py`, RS485 GUI IPC, config `rs485_ipc` |
| no LSL streams                 | `io/lsl_outlets.py`, pylsl runtime, app lifecycle            |
| CSV missing                    | `io/csv_sinks.py`, `csv.*.enabled`, path permissions         |
| growing XY delay               | `core/timestamping.py`, viewer alignment, device-clock drift |
| filtered signal unstable       | `core/filter.py`, processing config, input cadence           |

## Validation commands

```bash
uv run pytest tests/unit/test_parser.py
uv run pytest tests/unit/test_timestamping.py
uv run pytest tests/unit/test_filter.py
uv run pytest tests/integration/test_csv_sinks.py
```
