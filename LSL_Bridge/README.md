# LSL Bridge

## Summary

`LSL_Bridge` converts the two live acquisition sources into canonical Lab Streaming Layer streams:

- target Arduino/HX711 firmware UART → `HandgripTarget`,
- RS485 GUI ZeroMQ IPC → `HandgripReference`,
- operational diagnostics → `HandgripComponentEvents`.

It is the stream publication boundary for the Handgrip Suite. Viewer, calibration, and recording workflows should consume its LSL outputs instead of reading firmware serial or RS485 IPC directly.

## First command

From `LSL_Bridge/`:

```bash
uv run lsl-bridge
```

With explicit target serial port:

```bash
uv run lsl-bridge serial.port=/dev/ttyUSB_TARGET
```

For older invocation style, this may also work depending on the active environment:

```bash
uv run python -m lsl_bridge serial.port=/dev/ttyUSB_TARGET
```

## Expected result

Expected successful behavior:

- target serial connection opens,
- firmware `M2` metadata is observed,
- firmware `D2` lines are parsed,
- `RS485_GUI` IPC messages are consumed when the reference GUI is running,
- `HandgripTarget` and `HandgripReference` LSL streams appear,
- `LSL_Viewer` and `Handgrip_Calibration preflight` can discover the streams.

Stop if parser errors are continuous or only one expected stream appears.

## Configuration

Primary config:

```text
LSL_Bridge/conf/config.yaml
```

Main configuration areas:

| Area                | Purpose                                                       |
| ------------------- | ------------------------------------------------------------- |
| serial target input | Target Arduino port, baud, parser behavior.                   |
| reference IPC input | ZMQ endpoint/topic for `RS485_GUI`.                           |
| LSL outlets         | Stream names, types, channel names, nominal rates, metadata.  |
| timestamping        | Host/device timestamp policy, gap detection, anchor behavior. |
| processing          | Optional filtering/calibration/derived channels.              |
| logging/CSV         | Debug logs and optional saved target/reference data.          |

Full configuration reference: [LSL_Bridge/docs/configuration.md](docs/configuration.md).

## Documentation

Full reading guide, per-document map, and related cross-component docs: [LSL_Bridge/docs/index.md](docs/index.md).

## Repository layout

```text
LSL_Bridge/
├── README.md
├── conf/
│   ├── config.yaml
│   └── logging/
├── docs/
│   ├── index.md
│   └── stream-contracts.md
├── src/
│   └── lsl_bridge/
│       ├── core/
│       ├── io/
│       └── ...
└── tests/
```

## Tests

Run from `LSL_Bridge/` after dependencies are installed:

```bash
uv run pytest
```

Targeted checks commonly used after stream/parser edits:

```bash
uv run pytest tests/unit/test_parser.py
uv run pytest tests/unit/test_timestamping.py
uv run pytest tests/integration/test_csv_sinks.py
```
