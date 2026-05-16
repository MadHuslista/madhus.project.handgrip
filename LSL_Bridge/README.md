# LSL Bridge

## Summary

`LSL_Bridge` converts the two live acquisition sources into canonical Lab Streaming Layer streams:

- target Arduino/HX711 firmware UART → `HandgripTarget`,
- RS485 GUI ZeroMQ IPC → `HandgripReference`,
- operational diagnostics → `HandgripComponentEvents`.

It is the stream publication boundary for the Handgrip Suite. Viewer, calibration, and recording workflows should consume its LSL outputs instead of reading firmware serial or RS485 IPC directly.

## When to use this component

Use this component when you need to:

- publish target/reference LSL streams,
- validate firmware D2 parsing,
- consume the `RS485_GUI` IPC topic,
- inspect stream/channel contracts,
- debug timestamping, dropped samples, or stream discovery.

Do not use this component to:

- configure the acquisition-board front-panel menu,
- perform calibration fitting,
- render the main operator plots,
- modify target firmware constants.

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

| Area | Purpose |
| --- | --- |
| serial target input | Target Arduino port, baud, parser behavior. |
| reference IPC input | ZMQ endpoint/topic for `RS485_GUI`. |
| LSL outlets | Stream names, types, channel names, nominal rates, metadata. |
| timestamping | Host/device timestamp policy, gap detection, anchor behavior. |
| processing | Optional filtering/calibration/derived channels. |
| logging/CSV | Debug logs and optional saved target/reference data. |

Full configuration reference is planned at [`docs/configuration.md`](docs/configuration.md).

## Common workflows

| Goal | Document |
| --- | --- |
| Validate target path only | [`../docs/workflows/target-only-quickstart.md`](../docs/workflows/target-only-quickstart.md) |
| Run full live viewer stack | [`../docs/workflows/full-live-viewer-quickstart.md`](../docs/workflows/full-live-viewer-quickstart.md) |
| Understand bridge stream contracts | [`docs/stream-contracts.md`](docs/stream-contracts.md) |
| Understand root data contracts | [`../docs/architecture/stream-contracts.md`](../docs/architecture/stream-contracts.md) |
| Debug timing/synchronization | [`../docs/architecture/timestamping-and-synchronization.md`](../docs/architecture/timestamping-and-synchronization.md) |

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

## Further docs

- [`docs/index.md`](docs/index.md) — LSL Bridge documentation map.
- [`docs/stream-contracts.md`](docs/stream-contracts.md) — bridge-specific stream contracts.
- [`../docs/architecture/stream-contracts.md`](../docs/architecture/stream-contracts.md) — root stream/data contracts.
- [`../Handgrip_Firmware/docs/serial-protocol.md`](../Handgrip_Firmware/docs/serial-protocol.md) — firmware M2/D2 protocol.
