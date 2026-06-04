# `lsl_viewer` Refactor Plan
**Version:** 1.0.0  
**Scope:** GUI migration from Matplotlib/PyQt5 to NiceGUI + Plotly  
**Status:** Pre-implementation design document

---

## Table of Contents

1. [Pain Point Diagnostic](#1-pain-point-diagnostic)
2. [System Inventory & Evaluation](#2-system-inventory--evaluation)
3. [Refactoring Strategy](#3-refactoring-strategy)
4. [Code Pruning & Debt Identification](#4-code-pruning--debt-identification)
5. [Implementation Checklist](#5-implementation-checklist)

---

## 1. Pain Point Diagnostic

### 1.1 Symptom

> The Matplotlib GUI captures focus on every frame, making it impossible to interact with the calibration CLI or any other window while the viewer is running.

### 1.2 Plausible Causes (Code-Justified)

#### Cause A — `plt.pause()` is the primary focus thief ⚠️ **ROOT CAUSE**

`runners/live.py` lines 89–126 and `runners/replay.py` lines 64–86 both drive their event loops exclusively through `plt.pause()`:

```python
# runners/live.py — every refresh iteration, including the idle-paused path
while plt.fignum_exists(handles.fig.number):
    ...
    plt.pause(cfg.viewer.refresh_s)     # ← called unconditionally
```

```python
# runners/replay.py — same pattern
while plt.fignum_exists(handles.fig.number):
    ...
    plt.pause(cfg.viewer.refresh_s)     # ← called on every frame
```

`matplotlib.pyplot.pause(interval)` is implemented as:

```
plt.show(block=False)          # → QWidget.raise_() + QWidget.activateWindow()
canvas.start_event_loop(interval) OR time.sleep(interval) + canvas.flush_events()
```

On the **Qt5Agg backend** (forced by `PyQt5` in `pyproject.toml`), `show()` calls
`QWidget.raise_()` and `QWidget.activateWindow()` on every invocation. At
`refresh_s = 0.05` this fires **20 times per second**, raising the Matplotlib
window and stealing keyboard focus on every cycle.

This is not a bug in the application code — it is the documented, expected
behaviour of `plt.pause()` on Qt backends. The fix requires eliminating
`plt.pause()` as the event-loop driver.

#### Cause B — `canvas.draw_idle()` inside `update_plots()` triggers repaint + event flush

`viz/plots.py` (last line of `update_plots`) and `viz/figure.py` (`clear_plot_artists`):

```python
handles.fig.canvas.draw_idle()    # viz/plots.py — every frame
handles.fig.canvas.draw_idle()    # viz/figure.py — on clear
```

`draw_idle()` schedules a deferred repaint. When `plt.pause()` then pumps the Qt
event loop, all pending repaints are processed, which in turn triggers the
`QWidget.update()` → `paintEvent()` chain. On some Qt/platform combinations this
re-raises the window. This amplifies Cause A but is not independently sufficient
to steal focus.

#### Cause C — Keyboard event handler requires Qt window focus

`viz/figure.py` wires a `key_press_event` callback:

```python
fig.canvas.mpl_connect("key_press_event", on_key)
```

Because Matplotlib's Qt canvas only receives key events when the window has OS
focus, the current design **requires** the viewer window to be focused for
keyboard controls (`c`, `p`, `x`) to function. This is an emergent constraint
that reinforces the focus-stealing behaviour: the window must be front and active
for the tool to be interactive.

### 1.3 Root Cause Summary

| Cause | Location | Severity | Independently sufficient? |
|-------|----------|----------|--------------------------|
| A — `plt.pause()` raises window on Qt backend | `runners/live.py:89–126`, `runners/replay.py:64–86` | **Critical** | **Yes** |
| B — `draw_idle()` triggers repaint during Qt event flush | `viz/plots.py` (last line), `viz/figure.py:clear_plot_artists` | Moderate | No (amplifier) |
| C — keyboard controls require OS window focus | `viz/figure.py:on_key` | Low | No (constraint) |

### 1.4 Ideal Fix Options

#### Option 1: Refactor Matplotlib — Replace `plt.pause()` with a `QTimer`

```python
# Replace the while/plt.pause loop with:
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
timer = QTimer()
timer.timeout.connect(update_callback)
timer.start(int(cfg.viewer.refresh_s * 1000))

# Also add to figure init:
fig.canvas.window().setWindowFlag(Qt.WindowStaysOnTopHint, False)
fig.canvas.window().setAttribute(Qt.WA_ShowWithoutActivating, True)
```

**Advantages:**
- Minimal code change; no new framework
- Preserves the existing Matplotlib 8-panel layout pixel-for-pixel
- Preserves `mpl_connect` keyboard handling

**Disadvantages:**
- Still tied to PyQt5; `WA_ShowWithoutActivating` behaviour is platform-dependent (unreliable on Windows/macOS)
- Requires intimate knowledge of Qt internals; fragile against Matplotlib backend changes
- Does not fix Cause C (keyboard focus requirement)
- No path to browser-accessible UI
- Still blocks the Python process's main thread (no true parallelism)

#### Option 2: Port to NiceGUI + Plotly ✅ **Recommended**

Replace `viz/` and `runners/` with NiceGUI components. NiceGUI runs its UI in a
browser tab served by a local FastAPI/Starlette server. The Python process never
owns a native OS window, so window focus stealing is architecturally impossible.

**Advantages:**
- Eliminates Cause A/B/C at the root: no native OS window, no Qt event loop
- `core/`, `types.py`, `errors.py`, `config.py`, `logging_setup.py` are **completely unchanged**
- `ui.timer()` replaces the `while/plt.pause` pattern non-blockingly (runs in asyncio)
- `ui.plotly()` provides interactive pan/zoom/hover for free, without re-render
- NiceGUI is already proven in the LSL_Bridge system
- Keyboard shortcuts become browser `ui.keyboard` events — no focus requirement
- Future: multi-client (multiple browser tabs observe the same live stream)
- Aligns with the overall system direction

**Disadvantages:**
- Requires rewriting `viz/` (~250 LoC) and `runners/` (~130 LoC)
- Plotly has different update semantics than Matplotlib (Plotly `extendData` vs. `set_data`)
- A browser must be open (minor — NiceGUI can open it automatically)
- Adds `nicegui` and `plotly` to the dependency tree

### 1.5 Comparison Table

| Criterion | Matplotlib Fix (QTimer) | NiceGUI Port |
|-----------|------------------------|--------------|
| Fixes focus-stealing | Partially (platform-dependent) | **Yes — architecturally** |
| Core code changes | None | None |
| Viz code changes | Moderate (runner refactor) | High (full viz rewrite) |
| Risk of regression | Low | Medium |
| Keyboard controls | Same (Qt focus still needed) | **Browser-native, no focus needed** |
| Interactive plot pan/zoom | No | **Yes (Plotly built-in)** |
| System alignment | Diverges from NiceGUI stack | **Converges** |
| Long-term maintainability | Lower (Qt internals) | Higher |

**Decision: NiceGUI port.** The existing architecture has an excellent
Functional Core / Imperative Shell split. The functional core (`core/`,
`types.py`) does not need to change at all. Only the imperative shell
(`viz/`, `runners/`) is replaced.

---

## 2. System Inventory & Evaluation

### 2.1 Existing Features

#### Operational Modes
| Mode | Entry Point | Description |
|------|------------|-------------|
| `live` | `runners/live.py:run_live_mode(validate_reference=False)` | Live dual-stream LSL viewer |
| `live_with_reference_validation` | `runners/live.py:run_live_mode(validate_reference=True)` | Live mode with reference validation label |
| `csv_replay` | `runners/replay.py` + `core/replay.py:load_csv_replay` | Replay from dual-CSV (v2 schema) |
| `xdf_replay` | `runners/replay.py` + `core/replay.py:load_xdf_replay` | Replay from XDF file |

#### Visualization Panels (8 total, 5-row × 2-col layout)
| Panel Key | Content | Data Source |
|-----------|---------|-------------|
| `info` | Monospace text dashboard: source, target metrics, reference metrics, control hints | Computed each frame |
| `target_raw` | Target ADC raw counts vs. relative LSL time | `TargetWindow.raw` |
| `reference_raw` | Reference force (N) vs. relative LSL time | `ReferenceWindow.raw` |
| `target_filtered` | Target filtered/engineering-unit signal vs. relative LSL time | `TargetWindow.filtered` |
| `overlay` | Target filtered + reference raw overlaid on common LSL time axis | Both streams |
| `target_dt` | Target LSL inter-arrival intervals (ms) | `lsl_interval_ms(target.timestamps_s)` |
| `reference_dt` | Reference LSL inter-arrival intervals (ms) | `lsl_interval_ms(reference.timestamps_s)` |
| `xy` | Sensor curve: reference force vs. target raw (LineCollection, time-faded) | `interpolate_reference_to_target()` |

#### Interactive Controls
| Control | Mechanism | Action |
|---------|-----------|--------|
| `c` key | `mpl_connect key_press_event` | Clear all plot artists, reset window |
| `p` key | `mpl_connect key_press_event` | Pause/resume live data acquisition |
| `x` key | `mpl_connect key_press_event` | Toggle XY axis lock-max-span mode |

#### XY Correlation Features
- **Time alignment modes**: `raw_lsl`, `tail_aligned_lsl`, `manual` (configured via `viewer.xy_correlation.time_alignment.mode`)
- **Lock-max-span**: XY axis only grows, never shrinks (useful for calibration)
- **Time-faded LineCollection**: oldest segments fade to `xy_alpha_old`, newest at `xy_alpha_new`
- **Reference interpolation**: `interpolate_reference_to_target()` with gap rejection

#### Info Panel Columns (4 columns, monospace, horizontally concatenated)
- `SOURCE/MODE`: source name, type, mode, state (running/paused), sync method
- `TARGET`: raw, filtered, clock, LSL Hz, device Hz, dt error
- `REFERENCE`: raw, clock, LSL Hz, clock Hz, clock-LSL offset, span error, XY pair count
- `METRICS`: new samples (live) or replay progress, window size, XY shift, clip flag, active keys

#### Calibration Marker Overlay
- Optional NDJSON event file overlay on time-domain axes
- Filtered by event type (`draw_events` config list)
- Vertical `axvline` markers on `target_raw`, `reference_raw`, `target_filtered`, `overlay`

#### Live Mode Specific
- **Clear with cutoff**: records current buffer tail timestamp; only renders samples newer than cutoff after clear
- **Pause with cutoff**: same mechanism on resume
- **Reference validation mode**: identical data flow, different info-panel label

#### Replay Mode Specific
- Configurable `speed`, `loop`, `start_offset_s`
- Progress display: `time : elapsed/total s` + speed multiplier
- Hold-on-final-frame behaviour when replay ends and `loop=False`

#### Configuration (Hydra structured)
- Full schema in `config.py` with `ConfigStore` registration
- All visual constants (colors, alphas, linewidths) configurable via `viewer.style`
- All channel labels configurable via `channels.*`
- Layered override: YAML → env → CLI

#### Observability
- Module-scoped loggers (`logging.getLogger(__name__)`) throughout
- `RotatingFileHandler` + console handler (no `force=True` — Hydra handlers preserved)
- Log level configurable via `logging.level`

### 2.2 Current Architecture Map

```
lsl_viewer/
├── cli.py            [imperative shell] Hydra entry point, mode dispatch
├── config.py         [config] Structured dataclass schema + ConfigStore
├── logging_setup.py  [infra]  Console + rotating file handler setup
├── types.py          [pure]   Data containers (StreamLayout, TargetWindow, …)
├── errors.py         [pure]   Typed exception hierarchy
├── core/
│   ├── timing.py     [pure]   lsl_interval_ms, clock_validation_metrics
│   ├── alignment.py  [pure]   compute_xy_reference_time_shift_s, interpolate_reference_to_target
│   ├── replay.py     [imperative] CSV/XDF loaders, window_from_replay
│   └── stream.py     [imperative] mne-lsl connection, fetch_live_window
├── viz/
│   ├── figure.py     [imperative] plt.figure creation, mpl_connect callbacks ← REPLACE
│   ├── plots.py      [imperative] update_plots(): per-frame matplotlib artist updates ← REPLACE
│   └── markers.py    [mixed]  NDJSON loader (pure) + axvline drawing (imperative) ← SPLIT
└── runners/
    ├── live.py       [imperative] while/plt.pause event loop ← REPLACE
    └── replay.py     [imperative] while/plt.pause animation loop ← REPLACE
```

### 2.3 Ideal Architecture

```
lsl_viewer/
├── cli.py            [imperative shell] — unchanged API
├── config.py         [config]           — unchanged
├── logging_setup.py  [infra]            — unchanged
├── types.py          [pure]             — unchanged + add NiceGUI state types
├── errors.py         [pure]             — unchanged
├── core/
│   ├── timing.py     [pure]   — UNCHANGED
│   ├── alignment.py  [pure]   — UNCHANGED
│   ├── replay.py     [imperative] — UNCHANGED (loaders) + minor: remove matplotlib import guard
│   └── stream.py     [imperative] — UNCHANGED
└── viz/
    ├── app.py        [NEW] NiceGUI app factory: ui.run() wrapper, layout scaffold
    ├── panels.py     [NEW] NiceGUI panel construction (replaces figure.py)
    ├── charts.py     [NEW] Plotly figure builders + per-frame updaters (replaces plots.py)
    ├── markers.py    [SPLIT] Keep _load_marker_events() pure; replace axvline with plotly shapes
    ├── dashboard.py  [NEW] Info-panel text rendering as NiceGUI ui.label / ui.markdown
    └── state.py      [NEW] ViewerState dataclass: mutable render state (replaces FigureHandles)
    (runners no longer needed as separate module — event loops become ui.timer callbacks)
```

### 2.4 Architecture Gap Analysis

| Layer | Current | Ideal | Gap |
|-------|---------|-------|-----|
| Event loop | `while/plt.pause()` — blocks main thread, steals focus | `ui.timer()` — asyncio, non-blocking | **High** — full runner rewrite |
| Rendering | Matplotlib artists (`set_data`, `LineCollection`) | Plotly traces via `ui.plotly()` + `extendData` | **High** — full viz rewrite |
| Interactivity | `mpl_connect key_press_event` (requires Qt focus) | `ui.keyboard` or `ui.button` (browser, no focus required) | **Medium** |
| Info panel | `ax.text()` monospace block | `ui.label` / `ui.markdown` or HTML grid | **Low** — straightforward |
| Marker overlay | `ax.axvline()` per frame | Plotly `layout.shapes` | **Low** |
| State container | `FigureHandles` (wraps fig + axes + artists + state) | `ViewerState` (wraps Plotly fig refs + mutable state) | **Medium** |
| Core / config / types | Pure, well-structured | Unchanged | **None** |

---

## 3. Refactoring Strategy

### 3.1 Structural Layout

The `src/` layout is preserved as-is. No restructuring of the project root.

**Proposed new file tree after refactor:**

```
LSL_Viewer/
├── pyproject.toml                         ← updated dependencies (see §3.2)
├── conf/
│   └── config.yaml                        ← unchanged
├── src/
│   └── lsl_viewer/
│       ├── __init__.py                    ← unchanged
│       ├── __main__.py                    ← unchanged
│       ├── cli.py                         ← minimal change: remove PyQt5 guard, same dispatch API
│       ├── config.py                      ← unchanged
│       ├── logging_setup.py               ← unchanged
│       ├── types.py                       ← add ViewerState dataclass
│       ├── errors.py                      ← unchanged
│       ├── core/
│       │   ├── __init__.py               ← unchanged
│       │   ├── timing.py                 ← UNCHANGED (pure)
│       │   ├── alignment.py              ← UNCHANGED (pure)
│       │   ├── replay.py                 ← UNCHANGED
│       │   └── stream.py                 ← UNCHANGED
│       └── viz/
│           ├── __init__.py               ← updated exports
│           ├── app.py                    ← NEW: NiceGUI app factory + ui.run()
│           ├── panels.py                 ← NEW: NiceGUI layout (replaces figure.py)
│           ├── charts.py                 ← NEW: Plotly builders + updaters (replaces plots.py)
│           ├── markers.py                ← SPLIT: pure loader kept; Plotly shapes replaces axvline
│           ├── dashboard.py              ← NEW: info-panel text rendering
│           └── state.py                  ← NEW: ViewerState (replaces FigureHandles)
│           # REMOVED: figure.py, plots.py (replaced by above)
│           # runners/ is REMOVED — event loops become ui.timer() callbacks in app.py
└── tests/
    ├── unit/
    │   ├── test_alignment.py             ← UNCHANGED
    │   ├── test_timing.py                ← UNCHANGED
    │   ├── test_replay_loaders.py        ← UNCHANGED
    │   └── test_state.py                 ← NEW: ViewerState unit tests
    ├── integration/
    │   ├── test_csv_replay.py            ← UNCHANGED (tests core/replay, not viz)
    │   └── test_charts.py                ← NEW: Plotly figure shape/trace tests
    └── e2e/
        └── test_cli.py                   ← NEW: subprocess CLI smoke tests
```

**Files removed:**
- `src/lsl_viewer/viz/figure.py` → superseded by `panels.py` + `state.py`
- `src/lsl_viewer/viz/plots.py` → superseded by `charts.py` + `dashboard.py`
- `src/lsl_viewer/runners/live.py` → logic moved into `viz/app.py` timer callbacks
- `src/lsl_viewer/runners/replay.py` → logic moved into `viz/app.py` timer callbacks

### 3.2 Dependency Management

**`pyproject.toml` — updated:**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lsl-viewer"
version = "0.3.0"
description = "Dual-native-stream LSL handgrip force viewer with live, CSV, and XDF replay modes"
requires-python = ">=3.11"
dependencies = [
    "hydra-core>=1.3",
    "omegaconf>=2.3",
    "nicegui>=1.4",          # replaces matplotlib + PyQt5
    "plotly>=5.18",           # replaces matplotlib artists
    "numpy>=1.26",
    "pandas>=2.1",
    "mne-lsl>=1.2",
    "pyxdf>=1.16",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "pytest-asyncio>=0.23",   # NEW: NiceGUI async test support
]

[project.scripts]
lsl-viewer = "lsl_viewer.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/lsl_viewer"]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "pytest-asyncio>=0.23",
]
```

**Removed dependencies:**
- `matplotlib>=3.8` — superseded by `plotly` via NiceGUI
- `PyQt5>=5.15` — was only needed as Matplotlib backend; no longer required

**Package manager:** `uv` as specified. Development workflow:
```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest tests/
uv run lsl-viewer --help
```

### 3.3 Configuration

Hydra structured config is **unchanged**. All existing `conf/config.yaml` keys and
`config.py` dataclass schema remain identical.

**Config migrations required:** None — all config keys are preserved.

One addition to `conf/config.yaml` for NiceGUI-specific settings:

```yaml
# Add under viewer: section
viewer:
  ...existing keys unchanged...
  server:
    host: "127.0.0.1"       # NiceGUI server bind address
    port: 8765              # NiceGUI server port
    reload: false           # Development auto-reload
    show: true              # Auto-open browser on start
    dark: false             # Dark mode
```

**Corresponding `config.py` addition:**

```python
@dataclass
class ServerCfg:
    host: str = "127.0.0.1"
    port: int = 8765
    reload: bool = False
    show: bool = True
    dark: bool = False

@dataclass
class ViewerCfg:
    ...  # all existing fields unchanged
    server: ServerCfg = field(default_factory=ServerCfg)
```

**Hydra / NiceGUI conflict note:**  
NiceGUI calls `uvicorn` internally and may interfere with Hydra's working directory
management if Hydra is configured to change `cwd`. The existing config already
disables this correctly:

```yaml
hydra:
  run:
    dir: .
  job:
    chdir: false    # ← this is critical — must remain false
```

No additional changes needed. `@hydra.main` decorates `cli.py:app()` as before;
NiceGUI's `ui.run()` is called from within that function after all Hydra
initialization is complete.

### 3.4 Observability

Logging strategy is **unchanged**:
- `logging_setup.py` and all `logging.getLogger(__name__)` calls remain as-is
- NiceGUI's internal logging uses the `nicegui` logger name, which inherits the
  root handler configured by `configure_logging()`
- Add one log call in `viz/app.py` on server startup:

```python
log.info(
    "NiceGUI server starting: host=%s port=%d show=%s",
    cfg.viewer.server.host,
    cfg.viewer.server.port,
    cfg.viewer.server.show,
)
```

### 3.5 Feature Completeness Mapping

Every feature present in the current implementation must be present in the
refactored implementation. The table below maps each feature to its new location.

#### Visualization Panels

| Current (Matplotlib) | New (NiceGUI + Plotly) | Parity |
|---------------------|------------------------|--------|
| `axes["target_raw"]` line plot | `ui.plotly()` with `scatter` trace + `extendData` | ✅ Full |
| `axes["reference_raw"]` line plot | `ui.plotly()` with `scatter` trace + `extendData` | ✅ Full |
| `axes["target_filtered"]` line plot | `ui.plotly()` with `scatter` trace + `extendData` | ✅ Full |
| `axes["overlay"]` dual-line plot | `ui.plotly()` with two `scatter` traces | ✅ Full |
| `axes["target_dt"]` interval plot | `ui.plotly()` with `scatter` trace | ✅ Full |
| `axes["reference_dt"]` interval plot | `ui.plotly()` with `scatter` trace | ✅ Full |
| `axes["xy"]` LineCollection (faded) | `ui.plotly()` with `scatter` mode=`lines`, colorscale alpha | ✅ Full |
| `axes["info"]` monospace text | `ui.label` or `ui.html` with `<pre>` | ✅ Full |

**Note on XY LineCollection:** Plotly's `scatter` with `mode='lines'` and per-segment
color arrays via `marker.color` and a custom colorscale is the exact equivalent of
the current `LineCollection` with per-segment RGBA. The `_update_xy_line_collection`
function logic is reused directly; only the rendering call changes.

#### Interactive Controls

| Current (Matplotlib key) | New (NiceGUI) | Parity |
|--------------------------|---------------|--------|
| `c` — clear plots | `ui.keyboard` shortcut OR `ui.button('Clear')` | ✅ Full |
| `p` — pause/resume | `ui.keyboard` shortcut OR `ui.button('Pause')` | ✅ Full |
| `x` — toggle XY lock-max-span | `ui.keyboard` shortcut OR `ui.button('Lock XY')` | ✅ Full |

`ui.keyboard` binds to the browser window — no OS focus required.
Additionally, NiceGUI `ui.button` elements provide a GUI control that was never
available in the Matplotlib version.

#### Live Mode Controls

| Feature | Current | New | Parity |
|---------|---------|-----|--------|
| Pause with cutoff | `live_paused` state + `_establish_live_cutoff()` | Same logic, `ViewerState.paused` flag | ✅ Full |
| Clear with cutoff | `live_reset_from_latest_window` flag | Same logic in timer callback | ✅ Full |
| Stream cutoff timestamps | `target_live_cutoff_timestamp_s` in `handles.state` | `ViewerState.target_cutoff_s` | ✅ Full |

#### XY Correlation Features

| Feature | Current | New | Parity |
|---------|---------|-----|--------|
| Time alignment modes | `compute_xy_reference_time_shift_s()` in `core/alignment.py` | **UNCHANGED** (pure function) | ✅ Full |
| Lock-max-span axis | `update_axis_expand_only()` in `viz/figure.py` | `ViewerState.xy_max_span` dict; passed to Plotly `range` | ✅ Full |
| Time-faded LineCollection | `_update_xy_line_collection()` in `viz/plots.py` | Logic preserved; Plotly `marker.color` alpha array | ✅ Full |
| Reference interpolation | `interpolate_reference_to_target()` in `core/alignment.py` | **UNCHANGED** | ✅ Full |

#### Calibration Marker Overlay

| Feature | Current | New | Parity |
|---------|---------|-----|--------|
| NDJSON loader | `_load_marker_events()` in `viz/markers.py` | **UNCHANGED** (pure, extracted to `markers.py`) | ✅ Full |
| axvline per axis | `ax.axvline()` calls in `draw_marker_overlays()` | Plotly `layout.shapes` with `type='line'`, `x=event_x` | ✅ Full |
| Marker count in info panel | `marker_count` return value | Passed to `dashboard.py` render | ✅ Full |

#### Replay Mode Features

| Feature | Current | New | Parity |
|---------|---------|-----|--------|
| CSV loader | `load_csv_replay()` in `core/replay.py` | **UNCHANGED** | ✅ Full |
| XDF loader | `load_xdf_replay()` in `core/replay.py` | **UNCHANGED** | ✅ Full |
| Window slicing | `window_from_replay()` in `core/replay.py` | **UNCHANGED** | ✅ Full |
| Speed, loop, offset | `runners/replay.py` | Same logic in `ui.timer` callback | ✅ Full |
| Hold-on-final-frame | `while plt.fignum_exists` + break | `ui.timer` paused on final frame | ✅ Full |
| Progress display | `replay_progress_text` arg to `update_plots` | `ViewerState.replay_progress` → `dashboard.py` | ✅ Full |

#### CLI & API Compatibility

| Endpoint | Status |
|----------|--------|
| `lsl-viewer` entry point | **UNCHANGED** (`cli.py:app`) |
| `python -m lsl_viewer` | **UNCHANGED** (`__main__.py`) |
| All Hydra CLI overrides | **UNCHANGED** (same config schema) |
| `mode=live` | **UNCHANGED** |
| `mode=live_with_reference_validation` | **UNCHANGED** |
| `mode=csv_replay` | **UNCHANGED** |
| `mode=xdf_replay` | **UNCHANGED** |

---

## 4. Code Pruning & Debt Identification

### 4.1 Files Scheduled for Removal

| File | Reason | Replacement |
|------|--------|-------------|
| `src/lsl_viewer/viz/figure.py` | Matplotlib-specific figure init + Qt keyboard handler | `viz/panels.py` + `viz/state.py` |
| `src/lsl_viewer/viz/plots.py` | Matplotlib artist updates | `viz/charts.py` + `viz/dashboard.py` |
| `src/lsl_viewer/runners/live.py` | `while/plt.pause` event loop | `viz/app.py` `ui.timer` callback |
| `src/lsl_viewer/runners/replay.py` | `while/plt.pause` animation loop | `viz/app.py` `ui.timer` callback |

### 4.2 Dead Code in Current Codebase

#### `core/replay.py` — `_candidate_columns()` (already removed, per docstring)

The docstring for `core/replay.py` confirms:
> `_candidate_columns()` — was never exercised with actual fallbacks; every call site passed a single-element list. Replaced by direct `_pick_existing_column` calls.

This removal is already done. No further action needed.

#### `core/replay.py` — Legacy fused-CSV replay path

The docstring states:
> Legacy fused-CSV replay — already removed prior to this refactor (confirmed by comment in original source).

Confirmed removed. No further action needed.

#### `runners/live.py` — `_slice_dual_after_cutoffs()` and `_establish_live_cutoff()`

These are not dead code — they implement the pause/clear cutoff mechanism. They must
be **migrated** (not deleted) into `viz/app.py` as helper functions of the live
timer callback.

#### `viz/figure.py` — `update_axis()` and `update_axis_expand_only()`

These functions compute axis limits for Matplotlib. The limit-computation logic
(`_compute_axis_limits`) is pure and should be **extracted** into a helper in
`viz/state.py` or `core/` before `figure.py` is deleted, since `update_axis_expand_only`
implements the lock-max-span XY feature that must be preserved.

```python
# Extract to viz/state.py or keep in charts.py:
def compute_axis_limits(
    x: np.ndarray, y: np.ndarray, margin_ratio: float = 0.05
) -> tuple[float, float, float, float] | None:
    """Pure: compute (xmin, xmax, ymin, ymax) with margin. No matplotlib dependency."""
    ...  # identical to current _compute_axis_limits
```

### 4.3 Over-Defensive Error Handling to Simplify

#### `viz/markers.py:draw_marker_overlays` — bare `except Exception: pass`

```python
# Current (over-broad):
for artist in handles.state.get("marker_artists", []):
    try:
        artist.remove()
    except Exception:
        pass
```

This swallows all errors. In the Plotly port, marker cleanup is deterministic
(shapes removed by index, not by artist reference), so this try/except becomes
unnecessary and should be removed.

#### `core/stream.py:_stream_data_to_window` — multiple redundant shape checks

```python
if matrix.ndim != 2:
    log.warning(...)
    return None
if matrix.shape[0] < 3:
    log.warning(...)
    return None
```

This defensive layering is appropriate for untrusted external LSL data and should
be **kept**. It is not over-defensive — mne-lsl does not guarantee shape contract.

#### `core/replay.py:load_xdf_replay` — multiple length guards on `streams`

```python
if not matches:
    raise RuntimeError(...)
if len(matches) > 1:
    log.warning(...)
```

Appropriate. XDF files can legitimately have duplicate stream names. Keep as-is.

### 4.4 Legacy Compatibility Items

#### `config.py` — `TargetStreamCfg.source_id: str | None = None`

The `source_id` field accepts `null` in YAML (which becomes `None`). This was
introduced to support both the target stream (no source_id filter needed) and the
reference stream (filtered by `rs485-acquisition-board-1`). The handling is correct
and should be kept. No change needed.

#### `config.py` — `ReferenceCfg.xdf_path: str | None = None`

Appropriate. Keep as-is.

#### `viz/markers.py` — `_load_marker_events()` reads NDJSON on every frame

```python
def draw_marker_overlays(handles, cfg, t_end):
    ...
    marker_events = _load_marker_events(cfg)   # ← re-reads file every frame!
```

This is **not legacy code** but it is a correctness issue: the NDJSON file is
re-opened and re-parsed on every render cycle (20 Hz = 20 reads/second).
The Plotly port should cache the loaded events in `ViewerState.marker_events` and
only reload when the file modification time changes or `calibration_markers.enabled`
changes.

#### `cli.py` — `LIBRARY_ROOT` path resolution

```python
LIBRARY_ROOT = Path(__file__).parent.parent.parent.absolute()

@hydra.main(version_base=None, config_path=f"{LIBRARY_ROOT}/conf", ...)
```

This resolves the `conf/` directory relative to the installed package location.
This works correctly for both editable (`pip install -e .`) and production installs.
**Keep as-is.**

### 4.5 Deprecation Checklist

```
REMOVE (Matplotlib/Qt specific):
  [ ] src/lsl_viewer/viz/figure.py           — entire file
  [ ] src/lsl_viewer/viz/plots.py            — entire file
  [ ] src/lsl_viewer/runners/live.py         — entire file
  [ ] src/lsl_viewer/runners/runners/__init__.py — if empty after runner removal

MIGRATE (logic preserved, location changes):
  [ ] runners/live.py:_slice_dual_after_cutoffs()    → viz/app.py (live timer)
  [ ] runners/live.py:_establish_live_cutoff()       → viz/app.py (live timer)
  [ ] viz/figure.py:_compute_axis_limits()           → viz/state.py (pure helper)
  [ ] viz/figure.py:update_axis_expand_only() logic  → viz/state.py:ViewerState
  [ ] viz/markers.py:draw_marker_overlays() drawing  → viz/charts.py (Plotly shapes)
  [ ] viz/plots.py:_update_xy_line_collection()      → viz/charts.py (Plotly version)
  [ ] viz/plots.py:_zip_columns()                    → viz/dashboard.py (info panel)

KEEP UNCHANGED:
  [ ] src/lsl_viewer/core/timing.py
  [ ] src/lsl_viewer/core/alignment.py
  [ ] src/lsl_viewer/core/replay.py
  [ ] src/lsl_viewer/core/stream.py
  [ ] src/lsl_viewer/types.py         (+ add ViewerState)
  [ ] src/lsl_viewer/errors.py
  [ ] src/lsl_viewer/config.py        (+ add ServerCfg)
  [ ] src/lsl_viewer/logging_setup.py
  [ ] src/lsl_viewer/__init__.py
  [ ] src/lsl_viewer/__main__.py
  [ ] src/lsl_viewer/cli.py           (minimal: remove matplotlib import guard if any)
  [ ] conf/config.yaml                (+ add viewer.server section)
  [ ] tests/unit/test_alignment.py
  [ ] tests/unit/test_timing.py
  [ ] tests/unit/test_replay_loaders.py
  [ ] tests/integration/test_csv_replay.py

FIX (bug in current code):
  [ ] viz/markers.py:_load_marker_events()   — cache result in ViewerState; do not re-read file every frame

REMOVE (over-broad exception handling):
  [ ] viz/markers.py:draw_marker_overlays():
        try: artist.remove() except Exception: pass   → deterministic shape removal

UPDATE pyproject.toml:
  [ ] Remove: matplotlib>=3.8
  [ ] Remove: PyQt5>=5.15
  [ ] Add:    nicegui>=1.4
  [ ] Add:    plotly>=5.18
  [ ] Add (dev): pytest-asyncio>=0.23
  [ ] Bump version: 0.2.0 → 0.3.0
```

---

## 5. Implementation Checklist

### Phase 1 — Infrastructure (no feature changes)

- [ ] Update `pyproject.toml`: swap `matplotlib`/`PyQt5` for `nicegui`/`plotly`
- [ ] Add `ServerCfg` dataclass to `config.py`; add `viewer.server` to `conf/config.yaml`
- [ ] Add `ViewerState` dataclass to `types.py`
- [ ] Extract `_compute_axis_limits()` from `viz/figure.py` into `viz/state.py`

### Phase 2 — NiceGUI app scaffold

- [ ] Create `viz/app.py`: `build_app(cfg)` → returns NiceGUI app with full layout
- [ ] Create `viz/panels.py`: 8-panel layout using `ui.row()`, `ui.column()`, `ui.plotly()`
- [ ] Create `viz/state.py`: `ViewerState` + axis-limit helpers

### Phase 3 — Chart rendering

- [ ] Create `viz/charts.py`: Plotly figure builders for all 8 panels
- [ ] Port `_update_xy_line_collection()` to Plotly `scatter` with RGBA color array
- [ ] Port `update_axis_expand_only()` logic to `ViewerState.update_xy_span()`
- [ ] Create `viz/dashboard.py`: info-panel text renderer using `ViewerState`

### Phase 4 — Event loops (runners → ui.timer)

- [ ] Migrate `runners/live.py` live event loop to `ui.timer` callback in `viz/app.py`
- [ ] Migrate `_slice_dual_after_cutoffs()` and `_establish_live_cutoff()` to `viz/app.py`
- [ ] Migrate `runners/replay.py` replay loop to `ui.timer` callback in `viz/app.py`

### Phase 5 — Controls

- [ ] Port `c`/`p`/`x` keyboard controls to `ui.keyboard` shortcuts in `viz/panels.py`
- [ ] Add `ui.button` equivalents for all three controls
- [ ] Verify clear/pause cutoff mechanism functions correctly in timer-based loop

### Phase 6 — Markers

- [ ] Fix marker caching bug: cache `_load_marker_events()` result in `ViewerState`
- [ ] Port `draw_marker_overlays()` from `axvline` to Plotly `layout.shapes`
- [ ] Remove bare `except Exception: pass` from marker cleanup

### Phase 7 — Cleanup

- [ ] Delete `viz/figure.py`
- [ ] Delete `viz/plots.py`
- [ ] Delete `runners/live.py`
- [ ] Delete `runners/replay.py`
- [ ] Clean up `runners/__init__.py` (remove if empty)

### Phase 8 — Tests

- [ ] Add `tests/unit/test_state.py`: `ViewerState` unit tests
- [ ] Add `tests/integration/test_charts.py`: Plotly trace shape assertions
- [ ] Add `tests/e2e/test_cli.py`: subprocess smoke tests for all modes
- [ ] Verify all existing tests still pass: `uv run pytest tests/`

### Phase 9 — Documentation

- [ ] Update `README.md`: replace PyQt5/Matplotlib references; document browser-based UI
- [ ] Update architecture diagram in `README.md`
- [ ] Add `viewer.server` section to README key-sections table

---

## Appendix A: `ViewerState` Design

```python
# src/lsl_viewer/types.py — new addition

from dataclasses import dataclass, field
from typing import Any
import numpy as np

@dataclass
class ViewerState:
    """Mutable render state for the NiceGUI viewer.

    Replaces the `handles.state` dict from FigureHandles.
    All fields have typed names; no dict key typos possible.
    """
    # XY axis lock
    xy_lock_max_span: bool = False
    xy_max_span: dict[str, float] = field(default_factory=dict)  # xmin/xmax/ymin/ymax
    xy_reference_time_shift_s: float = 0.0
    xy_reference_tail_delta_s: float = 0.0
    xy_reference_shift_clipped: bool = False

    # Live mode control
    live_paused: bool = False
    live_reset_from_latest_window: bool = False
    target_cutoff_s: float | None = None
    reference_cutoff_s: float | None = None

    # Replay mode
    replay_progress: str = ""

    # Calibration markers (cached to avoid per-frame file reads)
    marker_events: list[dict[str, Any]] = field(default_factory=list)
    marker_file_mtime: float = 0.0
```

## Appendix B: NiceGUI Event Loop Pattern

```python
# viz/app.py — pattern for live mode timer

import asyncio
from nicegui import ui

async def _live_refresh(state: ViewerState, cfg, streams, charts) -> None:
    """Called by ui.timer every refresh_s seconds. No plt.pause(), no Qt."""
    if state.live_paused:
        return
    if state.live_reset_from_latest_window:
        _establish_cutoff(state, streams, cfg)
        return
    window = fetch_live_window(*streams, cfg)
    if window is None:
        return
    window = _slice_after_cutoffs(window, state)
    if window is None:
        return
    charts.update(window, state, cfg)   # Plotly extendData calls


def run_live_mode_nicegui(cfg, validate_reference: bool) -> int:
    streams = build_streams(cfg)
    state = ViewerState()
    charts = build_charts(cfg)        # returns Plotly figure refs

    @ui.page('/')
    def page():
        build_panels(cfg, charts, state)
        ui.timer(cfg.viewer.refresh_s, lambda: asyncio.create_task(
            _live_refresh(state, cfg, streams, charts)
        ))

    ui.run(
        host=cfg.viewer.server.host,
        port=cfg.viewer.server.port,
        show=cfg.viewer.server.show,
        reload=cfg.viewer.server.reload,
        dark=cfg.viewer.server.dark,
        title="LSL Viewer",
    )
    return 0
```

## Appendix C: `cli.py` Change Surface

The only change to `cli.py` is the import path for the runner:

```python
# BEFORE
if mode == "live":
    from lsl_viewer.runners.live import run_live_mode
    return run_live_mode(cfg, validate_reference=False)

# AFTER
if mode == "live":
    from lsl_viewer.viz.app import run_live_mode_nicegui
    return run_live_mode_nicegui(cfg, validate_reference=False)
```

The `@hydra.main` decorator, mode dispatch logic, logging setup call,
mode validation, and all other CLI behaviour are **unchanged**.
