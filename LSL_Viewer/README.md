# LSL Viewer v0.5.0

Dual-native-stream handgrip force viewer — live LSL, CSV replay, and XDF replay modes.

## What changed in v0.5.0 — XY-first square ECharts layout

**Root cause fixed (v0.3.0):** `plt.pause()` called `QWidget.activateWindow()` at 20 Hz, stealing OS keyboard focus on every frame.

**v0.3.0 fix:** NiceGUI renders in a browser tab — no native OS window, focus stealing is architecturally impossible.

**v0.4.0 fix:** Real-time rendering performance. The v0.3.0 Plotly backend was too slow for the data rate. Every `chart.update()` call serialised full trace arrays to JSON, transmitted them over the WebSocket, and Plotly.js ran a full diff before painting — repeating for all 7 panels at 20 Hz.

**v0.4.1 fix:** Robust ECharts render handoff. The browser chart element owns the authoritative `options` object, chart updates are pushed through an explicit EChart sink boundary, ECharts `large` mode is disabled by default, and display-only render budgets bound the payload sent to the browser.

**v0.5.0 changes:** The XY correlation panel is now first in the page, rendered as a connected faded line path, and all chart boxes use square aspect ratio. Downsampling is configurable from the Hydra config with `viewer.render.downsample_enabled`.

**Current backend:** Apache ECharts via NiceGUI's `ui.echart()`. Key improvements:

| Concern | Plotly (v0.3.0) | ECharts (v0.5.0) |
|---|---|---|
| Renderer | SVG (DOM node per point) | HTML5 Canvas (pixel buffer) |
| Update model | `Plotly.react()` + JSON diff | Element-owned `options` + explicit update sink |
| Large-data path | None | Explicit display-only render budgets |
| Animation overhead | Always present | `animation: False` throughout |
| Marker overlay | Separate shape layer | `markLine` on first series |
| Dependency | `plotly>=5.18` | Built into NiceGUI (ECharts bundled) |

---

## Architecture

```
src/lsl_viewer/
├── cli.py                  # Hydra entry point
├── config.py               # Structured config (AppConfig, ServerCfg, …)
├── types.py                # DualWindow, ViewerState, FigureHandles
├── errors.py
├── logging_setup.py
├── core/                   # UNCHANGED — pure functional core
│   ├── alignment.py        #   XY interpolation, time-shift computation
│   ├── timing.py           #   LSL interval / clock metrics
│   ├── replay.py           #   CSV/XDF loaders, window_from_replay
│   └── stream.py           #   LSL stream connect + fetch
└── viz/                    # NiceGUI + ECharts rendering layer
    ├── state.py            #   compute_axis_limits, update_xy_span (pure)
    ├── dashboard.py        #   render_info_text (pure, 4-column monospace)
    ├── markers.py          #   NDJSON loader + get_marker_x_positions (ECharts)
    ├── charts.py           #   ChartHandles, build_chart_handles, update_charts
    ├── panels.py           #   NiceGUI page layout — ui.echart, ui.keyboard
    └── app.py              #   run_live_mode_nicegui, run_replay_mode_nicegui
```

**Core layer is 100% unchanged** across all three versions.

### XY faded line collection

20 pre-allocated ECharts line series (`N_XY_BUCKETS`). Each bucket covers a freshness band; its `lineStyle.color` carries the corresponding alpha. Data entries are display-ready `[x, y]` points, with no `None` line-break sentinels and no ECharts `large` mode. Boundary points are duplicated only between occupied age buckets to preserve a continuous-looking path while keeping a constant series count.

### Render budgeting

Raw acquisition/replay windows remain intact. Only the browser payload is bounded:

```yaml
viewer:
  render:
    downsample_enabled: true
    max_points_time_series: 1200
    max_points_xy: 1500
```

Set `downsample_enabled: false` to send the full current display window to ECharts. Keeping it enabled protects the browser renderer from unbounded per-refresh payloads while preserving correctness and replayability in the core data path.

### Calibration marker overlay

`refresh_marker_cache()` reads the NDJSON file only when its mtime changes (fixes the original per-frame re-read bug). `get_marker_x_positions()` returns relative x positions. `_apply_markline()` attaches them as an ECharts `markLine` on series 0 of each time-domain panel — no separate shape layer needed.

---

## Installation

```bash
uv sync --extra dev
```

**Dependency change from v0.3.0:** `plotly>=5.18` removed. ECharts is bundled with NiceGUI.

---

## Usage

```bash
# Live mode (default)
lsl-viewer

# Live mode with reference validation
lsl-viewer mode=live_with_reference_validation

# CSV replay
lsl-viewer mode=csv_replay \
  reference.target_csv_path=./data/target.csv \
  reference.reference_csv_path=./data/reference.csv

# XDF replay
lsl-viewer mode=xdf_replay reference.xdf_path=./data/session.xdf
```

Opens at `http://127.0.0.1:8765` by default (configure via `viewer.server.*`).

## Keyboard shortcuts

| Key | Action |
|---|---|
| `c` | Clear plots |
| `p` | Pause / resume |
| `x` | Toggle XY lock-max-span |

Handled by `ui.keyboard` (browser key events — OS focus on viewer not required).

## Tests

```bash
uv run pytest            # all tests
uv run pytest tests/unit/      # pure logic
uv run pytest tests/integration/  # ECharts model/sink/update logic
uv run pytest tests/e2e/       # subprocess CLI smoke tests
```
