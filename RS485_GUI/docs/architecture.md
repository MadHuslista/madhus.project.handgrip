# RS485 GUI Architecture

## Summary

- `RS485_GUI` is organized as a decoupled acquisition application: pure core helpers, transport implementations, side-effect IO, UI rendering, configuration loading, and a worker thread.
- `MeasurementFrame` is the central data object flowing through transport → worker → state → logger/publisher/UI.
- The GUI should own reference-board parsing and IPC publication, but it should not publish LSL streams directly.
- The source layout is intentionally split so parser logic, UI, logging, and transport can be tested independently.

## Runtime dataflow

```text
config/config.yaml + CLI overrides
  ↓
config.loader.load_app_config()
  ↓
app.run_app() / app.main()
  ↓
AppState + RuntimeSettings
  ↓
connect_state()
  ├── SignalFileLogger.open()
  ├── BoardTransport.connect()
  ├── MeasurementFramePublisher.start()
  └── acquisition_worker thread
        ↓
      transport.read_frames()
        ↓
      list[MeasurementFrame]
        ├── full-rate logger.write_frames()
        ├── full-rate publisher.publish_frames()
        └── display-filtered AppState.push_frames()
              ↓
            NiceGUI / Plotly UI refresh
```

## Source tree

```text
RS485_GUI/src/rs485_gui/
├── app.py
├── worker.py
├── state.py
├── models.py
├── constants.py
├── core/
│   ├── codec.py
│   ├── ports.py
│   ├── sampling.py
│   └── signals.py
├── transport/
│   ├── base.py
│   ├── modbus.py
│   └── active_send.py
├── io/
│   ├── logger.py
│   └── publisher.py
├── ui/
│   ├── layout.py
│   ├── plots.py
│   └── refresh.py
└── config/
    ├── loader.py
    └── schema.py
```

## Layer responsibilities

| Layer     | Files                               | Responsibility                                                                         | Should not do                           |
| --------- | ----------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------- |
| Entry/app | `app.py`, `__main__.py`             | Compose config, state, UI, logger, publisher, transport, worker.                       | Decode low-level frame fields directly. |
| Worker    | `worker.py`                         | Run acquisition loop, rate-limit acquisition/display, dispatch frames.                 | Own parser details or UI layout.        |
| State     | `state.py`, `models.py`             | Hold runtime settings and frame buffers; define DTOs.                                  | Perform serial IO.                      |
| Core      | `core/*.py`                         | Pure functions: CRC, register decode, signal extraction, sampling stats, port scoring. | Bind serial ports, files, ZMQ, or UI.   |
| Transport | `transport/*.py`                    | Board IO: Modbus polling and Active-Send parsing.                                      | Render UI or write logs directly.       |
| IO        | `io/logger.py`, `io/publisher.py`   | File logs and ZMQ IPC.                                                                 | Decode board frames.                    |
| UI        | `ui/*.py`                           | NiceGUI layout, Plotly figures, refresh callbacks.                                     | Own acquisition semantics.              |
| Config    | `config/*.py`, `config/config.yaml` | Load config and schema defaults.                                                       | Start global Hydra runtime.             |

## `MeasurementFrame`

The central data unit is `MeasurementFrame`:

| Field           | Meaning                                  |
| --------------- | ---------------------------------------- |
| `host_ts`       | Host timestamp as epoch seconds.         |
| `host_ts_iso`   | Human-readable timestamp.                |
| `mode`          | `active_send` or `modbus_rtu`.           |
| `raw_transport` | Wire/register/diagnostic data.           |
| `interpreted`   | Decoded engineering values and metadata. |
| `session_id`    | Active session ID if configured.         |
| `board_profile` | Runtime board/profile snapshot.          |

Consumers:

| Consumer                    | Uses                                                    |
| --------------------------- | ------------------------------------------------------- |
| `SignalFileLogger`          | `raw_transport`, `interpreted`, timestamps, session ID. |
| `MeasurementFramePublisher` | `interpreted` selected signal and canonical aliases.    |
| UI plots                    | selected signal from `interpreted`.                     |
| Sampling stats              | frame timestamps.                                       |

## Transport architecture

### Modbus RTU transport

File:

```text
src/rs485_gui/transport/modbus.py
```

Responsibilities:

- open configured serial port,
- perform Modbus register reads,
- decode 11-register payload,
- send board commands where supported,
- assign host/LSL receive timestamps.

### Active-Send transport

File:

```text
src/rs485_gui/transport/active_send.py
```

Responsibilities:

- read binary push frames from serial stream,
- detect frame boundaries,
- validate CRC,
- decode 11-register Modbus-style response payload,
- reconstruct timestamps using the configured timestamp policy,
- recover from stale-buffer / CRC-resync cascades.

## IO architecture

### File logger

File:

```text
src/rs485_gui/io/logger.py
```

Writes:

- `raw_signal.ndjson`,
- `interpreted_signal.ndjson`,
- `gui_signal.csv`,
- `event.log`.

### IPC publisher

File:

```text
src/rs485_gui/io/publisher.py
```

Publishes:

- measurement topic `rs485.measurement.v1`,
- event topic `rs485.event.v1`.

Important behavior:

- ZMQ bind is lazy and usually happens on connect, not app construction.
- Publication is best-effort by default to avoid blocking acquisition.
- The record includes canonical bridge aliases such as `reference_force_N`.

## UI architecture

| File            | Responsibility                  |
| --------------- | ------------------------------- |
| `ui/layout.py`  | Page construction and controls. |
| `ui/plots.py`   | Plotly figure construction.     |
| `ui/refresh.py` | Periodic UI refresh logic.      |

Display-only throttling happens before UI state updates. It should not affect file logs or IPC when calibration-safe defaults are used.

## Configuration architecture

`load_app_config()`:

1. loads `RS485_GUI/config/config.yaml`,
2. applies CLI dotlist overrides,
3. configures logging exactly once,
4. avoids `@hydra.main` to prevent NiceGUI re-execution issues.

The dataclass schema in `config/schema.py` is documentation/validation support, not the runtime Hydra singleton.

## Extension principles

- Add new board decode fields in `core/codec.py` or transport decode code, not UI first.
- Register new plot signals in `core/signals.py`.
- Expose new persisted fields in `io/logger.py`.
- Expose bridge-required fields in `io/publisher.py` and update [RS485_GUI/docs/ipc-schema.md](ipc-schema.md).
- Add UI controls in `ui/layout.py` and refresh behavior in `ui/refresh.py`.
- Add tests in the smallest layer that owns the behavior.

## Validation map

| Change             | Tests/docs to update                                                                                      |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| Register decode    | `tests/unit/test_codec.py`, [RS485_GUI/docs/active-send-and-modbus.md](active-send-and-modbus.md).                     |
| Signal registry    | `tests/unit/test_signals.py`, [RS485_GUI/docs/configuration.md](configuration.md).                                     |
| File logging       | `tests/integration/test_file_logger.py`, [RS485_GUI/docs/logging-and-outputs.md](logging-and-outputs.md).              |
| IPC payload        | publisher tests/bridge tests where available, [RS485_GUI/docs/ipc-schema.md](ipc-schema.md), root stream contracts.    |
| Active-Send parser | `tests/integration/test_active_send_parser.py`, [RS485_GUI/docs/active-send-and-modbus.md](active-send-and-modbus.md). |
| Config key         | `tests/unit/test_config.py`, [RS485_GUI/docs/configuration.md](configuration.md).                                      |
