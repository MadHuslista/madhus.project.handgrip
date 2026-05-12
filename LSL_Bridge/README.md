# LSL Bridge

Publishes two native LSL streams consumed by the **Handgrip_Calibration** module:

| Stream              | Type         | Source                              | Rate                 |
| ------------------- | ------------ | ----------------------------------- | -------------------- |
| `HandgripTarget`    | Force (6 ch) | Arduino/HX711 over UART             | Irregular ~93–100 Hz |
| `HandgripReference` | Force (4 ch) | RS485 acquisition board via ZMQ IPC | Regular 500 Hz       |

An operational marker stream (`HandgripComponentEvents`) is also published for
component-level events (serial connects, timestamp anchor resets, IPC gaps).

---

## Requirements

- Python ≥ 3.11
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- `pylsl`, `pyserial`, `pyzmq`, `hydra-core`, `omegaconf`

---

## Installation

```bash
# With uv (recommended)
uv venv
uv pip install -e ".[dev]"

# With pip
pip install -e ".[dev]"
```

---

## Usage

```bash
# Default config
python -m lsl_bridge

# Override serial port
python -m lsl_bridge serial.port=/dev/ttyUSB0

# Debug logging (writes to lsl_bridge_debug.log)
python -m lsl_bridge logging=debug

# Override log level only
python -m lsl_bridge logging.level=DEBUG

# Disable file logging
python -m lsl_bridge logging.file=null

# Non-interactive / CI
python -m lsl_bridge session.session_id=session_001
```

---

## Configuration

All configuration lives in `conf/config.yaml`.  The full precedence chain is:

```
CLI overrides  >  conf/logging/<group>.yaml  >  conf/config.yaml  >  built-in defaults
```

Key sections:

| Section                                | Description                                                    |
| -------------------------------------- | -------------------------------------------------------------- |
| `streams.target` / `streams.reference` | LSL stream names, types, channels, chunk sizes, schema strings |
| `serial`                               | Port, baud rate, timeouts, reconnect backoff                   |
| `rs485_ipc`                            | ZMQ endpoint, topic, HWM, poll/backoff intervals               |
| `target_timestamping`                  | `host_receive` or `device_clock_anchor` policy                 |
| `processing`                           | Filter chain (butterworth, 1-pole, drift corrector)            |
| `csv`                                  | Output paths, append mode, flush interval                      |
| `logging`                              | Level, file path, format string                                |

---

## Project Structure

```
lsl_bridge/
├── pyproject.toml
├── conf/
│   ├── config.yaml
│   └── logging/
│       ├── default.yaml
│       └── debug.yaml
├── src/lsl_bridge/
│   ├── __init__.py          # version
│   ├── __main__.py          # python -m lsl_bridge
│   ├── app.py               # Hydra entry point + serial loop
│   ├── types.py             # shared dataclasses + Processor protocol
│   ├── logging_setup.py     # console + file handler wiring
│   ├── core/
│   │   ├── filter.py        # signal processing filters
│   │   ├── parser.py        # D2/M2 UART protocol parser
│   │   ├── timestamping.py  # device-clock → LSL clock resolvers
│   │   └── processing.py    # importlib processor loader
│   ├── io/
│   │   ├── csv_sinks.py     # target + reference CSV writers
│   │   ├── lsl_outlets.py   # StreamOutlet builders
│   │   └── serial_utils.py  # port metadata + settle helpers
│   └── publishers/
│       ├── events.py        # ComponentEventOutlet
│       └── reference.py     # RS485IpcReferencePublisher (ZMQ thread)
└── tests/
    ├── unit/
    │   ├── test_filter.py
    │   ├── test_parser.py
    │   └── test_timestamping.py
    └── integration/
        └── test_csv_sinks.py
```

---

## Running Tests

```bash
pytest tests/
```

Unit tests (`test_filter.py`, `test_parser.py`, `test_timestamping.py`) have
zero external dependencies — no LSL runtime, no serial port, no ZMQ required.

Integration tests (`test_csv_sinks.py`) write to a `tmp_path` fixture and
also require no hardware.

---

## Schema

Stream schema strings are configured under `streams.*.schema` and
`component_events.schema` in `conf/config.yaml`. The IPC message schema
enforced by the reference publisher is `rs485_ipc.expected_schema`.

---

## Changelog

### v2.0.0
- Migrated to `src/` layout with modular subpackages
- Logging wired to both console **and** file (configurable via `logging.file`)
- All magic constants promoted to `conf/config.yaml`
- Channel counts derived dynamically from config (no hardcoded `6` / `4`)
- Legacy RS485 IPC field aliases (`rs485_raw`, `rs485_clock`, `status_word`) removed
- `except Exception` in ZMQ receive loop narrowed to `except zmq.ZMQError`
- `except Exception` in optional ZMQ import narrowed to `except ImportError`
- Full unit and integration test suite added
