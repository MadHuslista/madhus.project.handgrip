# LSL Viewer Architecture

## Summary

- `LSL_Viewer` is a NiceGUI/ECharts browser application with a thin Hydra CLI entry point.
- Core modules keep alignment, replay loading, stream windowing, and timing calculations separated from UI rendering.
- Live mode resolves LSL streams and updates stream buffers; replay mode loads file-backed data and feeds the same chart update path.
- Browser rendering can downsample plotted payloads without mutating acquisition/replay buffers.

## Source layout

```text
LSL_Viewer/
├── conf/
│   └── config.yaml
├── src/lsl_viewer/
│   ├── cli.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── types.py
│   ├── core/
│   │   ├── alignment.py
│   │   ├── replay.py
│   │   ├── stream.py
│   │   └── timing.py
│   └── viz/
│       ├── app.py
│       ├── charts.py
│       ├── dashboard.py
│       ├── markers.py
│       ├── panels.py
│       └── state.py
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

## Runtime composition

```text
cli.py
  ├── register Hydra config schema
  ├── configure logging
  ├── validate mode
  └── dispatch to app runner

Live mode
  ├── resolve/pull LSL streams
  ├── maintain target/reference windows
  ├── compute alignment/diagnostics
  └── update ECharts UI

Replay mode
  ├── load CSV or XDF
  ├── normalize timebases
  ├── slice replay windows
  └── update ECharts UI
```

## Layer responsibilities

| Layer | Files | Responsibility |
| --- | --- | --- |
| CLI/config | `cli.py`, `config.py` | Hydra config, mode dispatch, logging setup. |
| Types | `types.py` | Dataclasses / typed containers for windows, replay data, viewer state, chart handles. |
| Core stream | `core/stream.py` | LSL channel resolution, stream window extraction, target/reference buffers. |
| Core alignment | `core/alignment.py` | Display-only XY reference shift and interpolation. |
| Core replay | `core/replay.py` | CSV/XDF loading and replay time windows. |
| Core timing | `core/timing.py` | Timing interval and clock validation metrics. |
| Viz app | `viz/app.py` | NiceGUI app lifecycle and live/replay refresh loops. |
| Viz charts | `viz/charts.py` | ECharts options, chart updates, render downsampling, XY buckets. |
| Viz panels | `viz/panels.py` | Page layout, controls, keyboard callbacks. |
| Viz markers | `viz/markers.py` | Calibration marker cache and marker-line positioning. |
| Viz state | `viz/state.py` | Axis limit helpers and XY max-span state helpers. |

## Stream buffers

Live mode keeps separate target/reference windows because the streams have different rates:

| Buffer | Config | Notes |
| --- | --- | --- |
| Target | `streams.target.buffer_samples`, `viewer.target_window_samples` | Sample-count based because target is irregular/device-paced. |
| Reference | `streams.reference.buffer_seconds`, `viewer.reference_window_extra_s` | Time-window based because reference is faster and nominally regular. |

## UI refresh model

Config:

```yaml
viewer:
  refresh_s: 0.05
```

At each refresh, the viewer:

1. obtains current target/reference windows,
2. updates timing and dashboard diagnostics,
3. computes display-only XY alignment/interpolation,
4. applies render-only downsampling if enabled,
5. pushes ECharts option updates to the browser.

## Plotting model

The UI uses ECharts through NiceGUI.

Plot classes:

| Plot | Purpose |
| --- | --- |
| Target raw | Raw target count / calibration-authoritative target signal. |
| Target filtered/current | Display or processed target engineering value. |
| Reference | PM58/reference force value. |
| Overlay/timing panels | Compare target/reference behavior and timing. |
| XY correlation | Reference force vs selected target signal. |

## XY rendering

XY correlation uses preallocated line buckets for path fading. This avoids point-only scatter behavior and makes trajectory/history easier to inspect.

The number of buckets is implementation-owned in `viz/charts.py`; tests assert the expected bucket behavior.

## Data immutability boundaries

Viewer transformations are display-local:

| Operation | Mutates saved/live source data? |
| --- | --- |
| render downsampling | No |
| XY interpolation | No |
| tail-aligned display shift | No |
| manual reference shift | No |
| pause/clear UI | No source mutation; affects displayed state only |
| marker overlay | No |

## Failure containment

The viewer should fail loudly for:

- unsupported mode,
- missing replay file paths,
- missing CSV/XDF channel labels,
- stream discovery timeout,
- invalid config keys/types.

It should not silently invent channels, ignore missing reference streams during calibration validation, or apply hidden correction to acquisition data.
