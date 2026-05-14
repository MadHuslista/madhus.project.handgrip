# LSL Viewer v0.3.0

Dual-native-stream handgrip force viewer with live LSL monitoring, CSV replay, and XDF replay modes.

## What changed in v0.3.0 — NiceGUI migration

**Root cause fixed:** The original Matplotlib/PyQt5 implementation called `plt.pause()` at 20 Hz, which triggered `QWidget.raise_()` + `QWidget.activateWindow()` on every frame via the Qt5Agg backend — **stealing OS keyboard focus 20 times per second**. This made the viewer unusable alongside any other application.

**Fix:** The rendering stack is replaced with **NiceGUI + Plotly**. NiceGUI serves the viewer in a browser tab over localhost; no native OS window is created, so focus-stealing is architecturally impossible.

**Secondary bug fixed:** `viz/markers.py` previously re-read the calibration events NDJSON from disk on every frame (20 Hz). The file is now cached and only reloaded when its mtime changes.

## Architecture

```
src/lsl_viewer/
├── cli.py                 # Hydra entry point; dispatches to viz.app runners
├── config.py              # Structured Hydra config (+ ServerCfg)
├── types.py               # DualWindow, ViewerState, FigureHandles
├── errors.py
├── logging_setup.py
├── core/                  # UNCHANGED — pure functional core
│   ├── alignment.py       #   XY interpolation, time-shift computation
│   ├── timing.py          #   LSL interval / clock metrics
│   ├── replay.py          #   CSV/XDF loaders, window_from_replay
│   └── stream.py          #   LSL stream connect + fetch
└── viz/                   # NEW — NiceGUI + Plotly rendering layer
    ├── state.py           #   compute_axis_limits, update_xy_max_span (pure)
    ├── dashboard.py       #   render_info_text (pure, 4-column monospace)
    ├── markers.py         #   Calibration marker loader + Plotly shape builder
    ├── charts.py          #   ChartHandles, build_chart_handles, update_charts
    ├── panels.py          #   NiceGUI page layout, keyboard/button controls
    └── app.py             #   run_live_mode_nicegui, run_replay_mode_nicegui
```

**Deleted:**
- `viz/figure.py` — Matplotlib figure creation
- `viz/plots.py` — Matplotlib per-frame updaters
- `runners/live.py` — `while/plt.pause()` live event loop
- `runners/replay.py` — `while/plt.pause()` replay event loop

**Core layer is 100% unchanged.** All four `core/` modules pass their existing test suites without modification.

## XY faded line collection

The time-faded line collection from the Matplotlib `LineCollection` implementation is reproduced using **20 pre-allocated Plotly Scatter traces** (`N_XY_BUCKETS = 20`). Each bucket covers a freshness band (0 = oldest, 1 = newest); its line colour carries the corresponding alpha. The trace count is constant across frames, which is critical for Plotly.js's `Plotly.react` diffing efficiency.

## Installation

```bash
pip install -e ".[dev]"
```

**Dependencies changed:**
- Removed: `matplotlib>=3.8`, `PyQt5>=5.15`
- Added: `nicegui>=1.4`, `plotly>=5.18`

## Usage

```bash
# Live mode (default)
lsl-viewer

# Live mode with reference validation overlay
lsl-viewer mode=live_with_reference_validation

# CSV replay
lsl-viewer mode=csv_replay \
  reference.target_csv_path=./data/target.csv \
  reference.reference_csv_path=./data/reference.csv

# XDF replay
lsl-viewer mode=xdf_replay reference.xdf_path=./data/session.xdf
```

The viewer opens at `http://127.0.0.1:8765` by default (configurable via `viewer.server.*`).

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `c` | Clear plots / reset post-clear cutoff |
| `p` | Pause / resume |
| `x` | Toggle XY axis lock-max-span |

Shortcuts are handled by NiceGUI's `ui.keyboard` (browser key events) — **OS focus on the viewer is not required**.

## Configuration

Key additions in `conf/config.yaml`:

```yaml
viewer:
  server:
    host: "127.0.0.1"
    port: 8765
    show: true       # auto-open browser on start
    dark: false
    title: "LSL Viewer"
```

All existing config keys are preserved.

## Tests

```bash
# All tiers
pytest

# By tier
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

**53 tests, 3 tiers:**
- `unit/` — Pure logic (alignment, timing, replay loaders, axis helpers, ViewerState adapter)
- `integration/` — Plotly figure construction and per-frame updates without a live server
- `e2e/` — Subprocess CLI smoke tests (help flag, invalid mode guard, missing file error)
