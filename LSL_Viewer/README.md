# LSL Viewer

## Summary

`LSL_Viewer` is the browser-based visualization tool for the Handgrip Suite. It reads live LSL streams or replay files and displays target/reference signals, XY correlation, and optional validation/marker overlays.

It is an observer and diagnostic tool. It should not redefine acquisition semantics, calibration math, or firmware/bridge contracts.

## First command

From `LSL_Viewer/`:

```bash
uv run lsl-viewer
```

## Expected result

Expected successful behavior:

- viewer web UI opens, typically at `http://127.0.0.1:8765`,
- target and reference streams are discovered when `LSL_Bridge` is running,
- target/reference time series update under applied force,
- XY correlation reacts to synchronized force changes,
- controls such as clear/pause behave as documented.

Stop before calibration if the viewer shows missing/frozen streams or persistent growing XY delay.

## Configuration

Primary config:

```text
LSL_Viewer/conf/config.yaml
```

Main configuration areas:

| Area             | Purpose                                                 |
| ---------------- | ------------------------------------------------------- |
| mode             | live, validation, CSV replay, XDF replay.               |
| stream discovery | Expected LSL stream names and channel labels.           |
| buffers          | Retention windows and sample handling.                  |
| plots            | Time-series, XY correlation, dimensions, axis behavior. |
| server           | Host, port, browser UI behavior.                        |
| keyboard/UI      | Clear, pause, XY lock, toggles.                         |

Full configuration reference is planned at [`docs/configuration.md`](docs/configuration.md).

## Common workflows

| Goal                          | Document                                                                                                               |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Run full live viewer stack    | [`../docs/workflows/full-live-viewer-quickstart.md`](../docs/workflows/full-live-viewer-quickstart.md)                 |
| Understand live process order | [`../docs/architecture/runtime-processes.md`](../docs/architecture/runtime-processes.md)                               |
| Understand stream contracts   | [`../docs/architecture/stream-contracts.md`](../docs/architecture/stream-contracts.md)                                 |
| Debug timestamp/XY delay      | [`../docs/architecture/timestamping-and-synchronization.md`](../docs/architecture/timestamping-and-synchronization.md) |
| Navigate component docs       | [`docs/index.md`](docs/index.md)                                                                                       |

## Repository layout

```text
LSL_Viewer/
├── README.md
├── conf/
│   └── config.yaml
├── docs/
│   └── index.md
├── src/
│   └── lsl_viewer/
│       ├── app/
│       ├── ui/
│       ├── streams/
│       └── ...
└── tests/
```

## Tests

Run from `LSL_Viewer/` after dependencies are installed:

```bash
uv run pytest
```

Useful targeted subsets:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e
```

## Further docs

- [`docs/index.md`](docs/index.md) — LSL Viewer documentation map.
- [`../docs/workflows/full-live-viewer-quickstart.md`](../docs/workflows/full-live-viewer-quickstart.md) — operator workflow.
- [`../docs/architecture/stream-contracts.md`](../docs/architecture/stream-contracts.md) — root stream/data contracts.
- [`../docs/architecture/timestamping-and-synchronization.md`](../docs/architecture/timestamping-and-synchronization.md) — timing and alignment model.
