# RS485 GUI

High-speed RS485 acquisition board GUI with real-time Plotly visualization,
ZeroMQ IPC publishing, and Lab Streaming Layer (LSL) integration.

## Features

- **Modbus RTU** polling mode and **Active-Send** (500 Hz push-frame) binary mode
- Real-time Plotly signal plot with configurable downsampling
- ZeroMQ PUB socket for downstream consumers (LSL Bridge, recorders)
- Structured NDJSON and CSV file logging
- Hierarchical per-module logging configurable via Hydra

## Quickstart

```bash
# Install with uv
uv sync

# Run
uv run python -m rs485_gui

# Or via entry point
uv run rs485-gui

# With config overrides
uv run rs485-gui ui.port=8090 serial.default_port=/dev/ttyUSB1

# With numpy acceleration
uv sync --extra fast
```

## Configuration

All settings live in `config/config.yaml`. Override any key on the CLI with
`key.subkey=value` (OmegaConf dotlist syntax).

## Architecture

```
src/rs485_gui/
├── constants.py        # Protocol lookup tables (pure data)
├── models.py           # Data transfer objects (frozen dataclasses)
├── state.py            # Mutable runtime state (AppState)
├── worker.py           # Acquisition loop thread
├── app.py              # Application entry point
├── core/               # Pure functional core (zero I/O dependencies)
│   ├── codec.py        # Modbus CRC, register decode
│   ├── signals.py      # Signal key helpers
│   ├── sampling.py     # Sampling rate statistics
│   └── ports.py        # Serial port discovery
├── transport/          # Hardware I/O layer
│   ├── base.py         # Abstract transport interface
│   ├── modbus.py       # Modbus RTU transport
│   └── active_send.py  # Active-send binary push transport
├── io/                 # Side-effect I/O layer
│   ├── logger.py       # File logger (NDJSON/CSV/event)
│   └── publisher.py    # ZeroMQ IPC publisher
├── ui/                 # NiceGUI presentation layer
│   ├── layout.py       # Page construction
│   ├── plots.py        # Plotly figure builder
│   └── refresh.py      # UI timer callback
└── config/             # Configuration layer
    ├── schema.py       # Hydra structured config dataclasses
    └── loader.py       # Config loading and logging setup
```
