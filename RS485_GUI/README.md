# RS485 GUI

## Summary

`RS485_GUI` is the reference-chain acquisition application. It connects to the high-speed acquisition board over RS485, displays reference measurements in a browser UI, logs acquisition data, and publishes normalized reference measurements over ZeroMQ IPC for `LSL_Bridge`.

It owns the PM58/acquisition-board host-side acquisition path. Downstream components should consume its IPC output through `LSL_Bridge`, not reimplement board parsing independently.

## First command

From `RS485_GUI/`:
> This should be enough to start the application with default settings ready to connect to the acquisition board if it's on a standard port. 
> Adjustments could be done directly on the UI or by providing config overrides as needed.

```bash
uv run rs485-gui
```

With an explicit serial port:

```bash
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
```

With a custom UI port:

```bash
uv run rs485-gui ui.port=8090 serial.default_port=/dev/ttyUSB_RS485
```

## Expected result

Expected successful behavior:

- the NiceGUI browser interface opens,
- the acquisition board value updates when force changes,
- logs show valid board measurements,
- the IPC publisher is active on the configured endpoint/topic,
- `LSL_Bridge` can consume the `rs485.measurement.v1` IPC stream and publish `HandgripReference`.

Stop if the acquisition-board front display changes but the GUI receives no valid measurements.

## Configuration

Primary config:

```text
RS485_GUI/config/config.yaml
```

Main configuration areas:

| Area                          | Purpose                                                     |
| ----------------------------- | ----------------------------------------------------------- |
| `serial` / transport settings | Port, baud, mode, Modbus/Active-Send profile.               |
| `ui`                          | Browser UI host/port, refresh cadence, plot behavior.       |
| `logger`                      | CSV/NDJSON/event logging behavior and output paths.         |
| `ipc`                         | ZeroMQ publisher endpoint and topic configuration.          |
| `parser` / signal settings    | Board payload interpretation and selected displayed signal. |

Full configuration reference is planned at [RS485_GUI/docs/configuration.md](docs/configuration.md).

## Library layout

```text
RS485_GUI/
├── README.md
├── config/
│   └── config.yaml
├── docs/
│   └── index.md
├── src/
│   └── rs485_gui/
│       ├── app.py
│       ├── worker.py
│       ├── core/
│       ├── transport/
│       ├── io/
│       ├── ui/
│       └── config/
└── tests/
```

## Tests

Run from `RS485_GUI/` after dependencies are installed:

```bash
uv run pytest
```

Use targeted tests when changing one layer:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
```

If hardware is unavailable, prioritize parser/config/unit tests and validate live acquisition later with the reference-only quickstart.

## Documentation

Full reading guide, per-document map, and related cross-component docs: [RS485_GUI/docs/index.md](docs/index.md).
