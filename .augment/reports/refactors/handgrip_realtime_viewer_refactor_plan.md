# Refactor Plan: `handgrip_realtime_viewer`

**Module version audited:** `LSL_Viewer` (flat single-file package)  
**Target architecture:** `src`-layout Python package with Hydra configuration, hierarchical logging, and clean module separation  
**Guiding standard:** PyPA `src`-layout, PEP 621 metadata, `uv` toolchain, `hatchling` build backend

---

## 1. System Inventory & Evaluation

### 1.1 Feature Inventory

| Feature | Location | Status |
|---|---|---|
| Live dual-stream LSL viewer (`live` mode) | `run_live_mode()` | ✅ Keep |
| Live viewer with reference clock validation (`live_with_reference_validation`) | `run_live_mode(validate_reference=True)` | ✅ Keep |
| CSV replay from dual native CSVs (`csv_replay`) | `load_csv_replay()`, `run_replay_mode()` | ✅ Keep |
| XDF replay from `.xdf` file (`xdf_replay`) | `load_xdf_replay()`, `run_replay_mode()` | ✅ Keep |
| Hydra-managed configuration (`conf/config.yaml`) | `@hydra.main` decorator | ✅ Keep, extend |
| Multi-panel matplotlib figure (8 subplots) | `init_figure()` | ✅ Keep |
| Interactive keyboard controls (clear/pause/XY-lock) | `on_key()` inside `init_figure()` | ✅ Keep |
| XY correlation with time-faded `LineCollection` | `_update_xy_line_collection()` | ✅ Keep |
| Adaptive / snap / manual reference time alignment | `_compute_xy_reference_time_shift_s()` | ✅ Keep |
| Reference-to-target interpolation for XY | `_interpolate_reference_to_target()` | ✅ Keep |
| Clock validation metrics panel | `_clock_validation_metrics()` | ✅ Keep |
| LSL/device-clock interval diagnostics | `_lsl_interval_ms()`, `_clock_interval_ms()` | ✅ Keep |
| Optional calibration-marker NDJSON overlay | `_load_marker_events_from_ndjson()`, `_draw_marker_overlays()` | ✅ Keep |
| Expand-only XY axis locking | `update_axis_expand_only()` | ✅ Keep |
| Info-panel text renderer | `_render_info_panel()`, `_zip_columns()` | ✅ Keep |
| Logging to console via `basicConfig` | `configure_logging()` | ⚠️ Refactor — add `FileHandler`, module-scoped loggers |
| Module-level color constants (`RAW_COLOR`, etc.) | Module globals | ⚠️ Move to config schema |
| `_candidate_columns()` fallback mechanism | `load_csv_replay()` | 🔴 Dead code — see §3 |
| `_cfg_str_path()` / `_cfg_bool_path()` wrappers | Config helpers | 🔴 Bloat — structured config eliminates these |
| Legacy fused CSV replay | Removed (comment in source confirms) | ✅ Already pruned |

### 1.2 Ideal Architecture

The tool is a pure **visualization consumer**. Its ideal shape follows the **Functional Core, Imperative Shell** pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                        IMPERATIVE SHELL                         │
│  cli.py · runners/live.py · runners/replay.py                   │
│  (Hydra entry, plt.pause loop, stream connect/disconnect)        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    FUNCTIONAL CORE                      │   │
│   │  core/timing.py  · core/alignment.py · core/replay.py  │   │
│   │  (pure numpy/pandas transforms, zero side-effects)      │   │
│   │  Input arrays ──► Statistical transforms ──► Arrays     │   │
│   └─────────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                  VISUALIZATION LAYER                    │   │
│   │  viz/figure.py · viz/plots.py · viz/markers.py          │   │
│   │  (matplotlib artists; depends on core, not on I/O)      │   │
│   └─────────────────────────────────────────────────────────┘   │
│  core/stream.py  (mne-lsl fetch, shape validation)              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Current vs. Ideal: Architecture Contrast

| Dimension | Current State | Ideal State | Debt Level |
|---|---|---|---|
| **Layout** | Flat single file (1 412 lines) | `src/handgrip_viewer/` package | 🔴 Critical |
| **Module boundaries** | None — all logic co-located | `core/`, `viz/`, `runners/` sub-packages | 🔴 Critical |
| **Logger scope** | Single `LOGGER` at module level, `basicConfig(force=True)` | `logging.getLogger(__name__)` per module, Hydra-aware setup | 🟡 Major |
| **Log file output** | Absent (empty `.log` file in repo) | Tee to rotating `FileHandler` via `configure_logging()` | 🟡 Major |
| **Config schema** | Stringly-typed `OmegaConf.select` scattered in 20+ call sites | Structured `@dataclass`-backed Hydra config groups | 🟡 Major |
| **Magic constants** | `RAW_COLOR`, `FILTERED_COLOR`, `GRID_ALPHA`, line widths hardcoded | Moved to `conf/config.yaml` under `viewer.style` | 🟡 Major |
| **Dependency management** | None (no `pyproject.toml`) | PEP 621 `pyproject.toml`, `uv` lockfile | 🟡 Major |
| **Testability** | Zero tests; all pure logic intermixed with I/O | Unit-testable `core/` functions with no mock needed | 🟡 Major |
| **Dead code** | `_candidate_columns`, `_cfg_str_path`, `_cfg_bool_path` | Pruned | 🟢 Minor |

---

## 2. Refactoring Strategy

### 2.1 Proposed File Tree

```
handgrip_realtime_viewer/                   ← project root (rename from LSL_Viewer/)
├── pyproject.toml                          ← PEP 621 metadata + hatchling build
├── uv.lock                                 ← generated by `uv lock`
├── README.md
├── conf/                                   ← Hydra config (outside src/)
│   ├── config.yaml                         ← top-level defaults
│   └── viewer/
│       └── style.yaml                      ← NEW: visual style constants
├── src/
│   └── handgrip_viewer/                    ← installable package
│       ├── __init__.py
│       ├── __main__.py                     ← `python -m handgrip_viewer`
│       ├── cli.py                          ← @hydra.main entry point
│       ├── config.py                       ← Structured config dataclasses (OmegaConf)
│       ├── types.py                        ← StreamLayout, TargetWindow, ReferenceWindow,
│       │                                      DualWindow, DualReplayData, FigureHandles
│       ├── errors.py                       ← ViewerError, StreamError, ReplayError
│       ├── logging_setup.py                ← configure_logging(): console + FileHandler
│       ├── core/
│       │   ├── __init__.py
│       │   ├── stream.py                   ← build_streams(), fetch_live_window(),
│       │   │                                  _stream_data_to_window(), slice helpers
│       │   ├── timing.py                   ← _lsl_interval_ms(), _clock_interval_ms(),
│       │   │                                  _clock_validation_metrics()  [PURE]
│       │   ├── alignment.py                ← _compute_xy_reference_time_shift_s(),
│       │   │                                  _interpolate_reference_to_target()  [PURE]
│       │   └── replay.py                   ← load_csv_replay(), load_xdf_replay(),
│       │                                      _window_from_replay(), XDF helpers  [PURE*]
│       ├── viz/
│       │   ├── __init__.py
│       │   ├── figure.py                   ← init_figure(), clear_plot_artists(),
│       │   │                                  update_axis(), update_axis_expand_only()
│       │   ├── plots.py                    ← update_plots(), _render_info_panel(),
│       │   │                                  _update_xy_line_collection(), _zip_columns(),
│       │   │                                  _format_latest()
│       │   └── markers.py                  ← _load_marker_events_from_ndjson(),
│       │                                      _draw_marker_overlays()
│       └── runners/
│           ├── __init__.py
│           ├── live.py                     ← run_live_mode(),
│           │                                  _establish_live_cutoff_from_latest_window(),
│           │                                  _slice_dual_after_cutoffs()
│           └── replay.py                   ← run_replay_mode()
└── tests/
    ├── unit/
    │   ├── test_timing.py                  ← _lsl_interval_ms, _clock_validation_metrics
    │   ├── test_alignment.py               ← _interpolate_reference_to_target
    │   └── test_replay_loaders.py          ← _window_from_replay, _normalize_common_timebases
    └── integration/
        └── test_csv_replay.py              ← load_csv_replay with fixture CSVs
```

> `*` `load_csv_replay` / `load_xdf_replay` are "mostly pure": they accept a `DictConfig` and
> return a `DualReplayData`. The only I/O is `pd.read_csv` / `pyxdf.load_xdf`. Keep these in
> `core/replay.py` but do not mix them with alignment math.

---

### 2.2 `pyproject.toml` (PEP 621 + hatchling + uv)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "handgrip-realtime-viewer"
version = "0.2.0"
description = "Dual-native-stream LSL handgrip force viewer with live, CSV, and XDF replay modes"
requires-python = ">=3.11"
dependencies = [
    "hydra-core>=1.3",
    "omegaconf>=2.3",
    "matplotlib>=3.8",
    "numpy>=1.26",
    "pandas>=2.1",
    "PyQt5>=5.15",           # Qt5Agg backend
]

[project.optional-dependencies]
live = [
    "mne-lsl>=1.2",          # StreamLSL; live/live_with_reference_validation only
]
xdf = [
    "pyxdf>=1.16",           # xdf_replay mode only
]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
]

[project.scripts]
handgrip-viewer = "handgrip_viewer.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/handgrip_viewer"]

[tool.uv]
dev-dependencies = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.4"]
```

**Development workflow with `uv`:**

```bash
# Bootstrap
uv venv
uv pip install -e ".[live,xdf,dev]"

# Run
python -m handgrip_viewer           # uses __main__.py
handgrip-viewer                     # via entry point
handgrip-viewer mode=csv_replay     # Hydra CLI override

# Test
uv run pytest tests/

# Lock dependencies for reproducible builds
uv lock
```

---

### 2.3 Structured Configuration Schema

Replace the 20+ scattered `OmegaConf.select(cfg, "viewer.xy_correlation.time_alignment.mode", default="tail_aligned_lsl")` call sites with a typed `@dataclass` config tree registered via `hydra.core.config_store`.

**`src/handgrip_viewer/config.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from omegaconf import MISSING
from hydra.core.config_store import ConfigStore


@dataclass
class StreamCfg:
    name: str = MISSING
    stype: str = MISSING
    source_id: str | None = None
    buffer_samples: int = 1600          # target only
    buffer_seconds: float = 12.0        # reference only
    acquisition_delay: float = 0.01
    timeout: float = 5.0
    expected_rate_hz: float = 500.0


@dataclass
class ChannelCfg:
    clock_label: str = MISSING
    raw_label: str = MISSING
    filtered_label: str | None = None


@dataclass
class TimeAlignmentCfg:
    mode: str = "raw_lsl"               # raw_lsl | tail_aligned_lsl | manual
    manual_reference_shift_s: float = 0.0
    max_auto_shift_s: float | None = None
    min_auto_shift_s: float = 0.0
    snap_threshold_s: float = 0.250
    smoothing_alpha: float = 1.0


@dataclass
class XYCorrelationCfg:
    lock_max_span: bool = False
    toggle_key: str = "x"
    line_width: float = 1.6
    target_signal: str = "raw"
    time_alignment: TimeAlignmentCfg = field(default_factory=TimeAlignmentCfg)


@dataclass
class StyleCfg:
    """Visual constants previously hardcoded as module globals."""
    raw_color: str = "red"
    filtered_color: str = "green"
    reference_color: str = "purple"
    timing_color: str = "blue"
    grid_alpha: float = 0.3
    xy_alpha_old: float = 0.12
    xy_alpha_new: float = 0.92
    xy_color: str = "red"


@dataclass
class ViewerCfg:
    window_seconds: float = 10.0
    target_window_samples: int = 1600
    reference_window_extra_s: float = 1.0
    expected_target_rate_hz: float = 100.0
    refresh_s: float = 0.05
    force_unit_label: str = "N"
    target_raw_unit_label: str = "count"
    dt_unit_label: str = "ms"
    xy_correlation: XYCorrelationCfg = field(default_factory=XYCorrelationCfg)
    style: StyleCfg = field(default_factory=StyleCfg)
    controls: dict = field(default_factory=lambda: {"clear_key": "c", "pause_key": "p"})


@dataclass
class AlignmentCfg:
    interpolation: str = "linear"
    max_reference_gap_s: float = 0.020
    allow_extrapolation: bool = False


@dataclass
class CalibrationMarkersCfg:
    enabled: bool = False
    events_ndjson_path: str | None = None
    draw_events: list[str] = field(
        default_factory=lambda: [
            "hold_start", "stable_window_start", "hold_end",
            "trial_accept", "trial_reject"
        ]
    )


@dataclass
class ReferenceCfg:
    target_csv_path: str = "./data/target_handgrip_samples_v2.csv"
    reference_csv_path: str = "./data/reference_rs485_samples_v2.csv"
    xdf_path: str | None = None


@dataclass
class ReplayCfg:
    speed: float = 1.0
    loop: bool = False
    start_offset_s: float = 0.0


@dataclass
class LoggingCfg:
    level: str = "INFO"
    log_file: str = "handgrip_realtime_viewer.log"   # NEW: explicit log-file path
    max_bytes: int = 10_485_760                       # 10 MB
    backup_count: int = 3


@dataclass
class AppConfig:
    mode: str = "live"
    streams: dict = field(default_factory=dict)
    channels: dict = field(default_factory=dict)
    viewer: ViewerCfg = field(default_factory=ViewerCfg)
    alignment: AlignmentCfg = field(default_factory=AlignmentCfg)
    calibration_markers: CalibrationMarkersCfg = field(default_factory=CalibrationMarkersCfg)
    reference: ReferenceCfg = field(default_factory=ReferenceCfg)
    replay: ReplayCfg = field(default_factory=ReplayCfg)
    logging: LoggingCfg = field(default_factory=LoggingCfg)


def register_config() -> None:
    cs = ConfigStore.instance()
    cs.store(name="app_config", node=AppConfig)
```

**Key benefit:** Every previously scattered `OmegaConf.select(cfg, "viewer.xy_correlation.time_alignment.snap_threshold_s", default=0.250)` becomes `cfg.viewer.xy_correlation.time_alignment.snap_threshold_s` — typed, IDE-navigable, and default-declared in one place.

---

### 2.4 Logging Refactor

#### 2.4.1 Problem with the Current Implementation

```python
# Current — problematic on three counts:
LOGGER = logging.getLogger("handgrip_realtime_viewer")   # ① single name for entire app
logging.basicConfig(..., force=True)                       # ② force=True tears out Hydra's handler
                                                           # ③ no FileHandler
```

Hydra installs its own log handler at startup. Calling `basicConfig(force=True)` inside `app()` **removes** that handler, which is why the repo's `.log` file is empty — Hydra's file sink was destroyed before any logs were written.

#### 2.4.2 Solution: `logging_setup.py`

```python
# src/handgrip_viewer/logging_setup.py
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level_name: str,
    log_file: str | Path,
    max_bytes: int = 10_485_760,
    backup_count: int = 3,
) -> None:
    """Configure root logger with a console handler and a rotating file handler.

    This must be called AFTER Hydra has initialised (i.e., inside the @hydra.main
    body), so it appends handlers rather than replacing them.  Using force=True
    would tear out Hydra's own file sink, which is why the log file was empty.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers on repeated calls (e.g., during tests)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(console)

    file_path = Path(log_file)
    if not any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        and getattr(h, "baseFilename", None) == str(file_path.resolve())
        for h in root.handlers
    ):
        fh = logging.handlers.RotatingFileHandler(
            file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(fh)
```

#### 2.4.3 Module-Scoped Loggers (apply in every module)

```python
# Every module uses its own __name__-scoped logger:
import logging
log = logging.getLogger(__name__)

# e.g., in core/stream.py:   handgrip_viewer.core.stream
# e.g., in viz/figure.py:    handgrip_viewer.viz.figure
# e.g., in runners/live.py:  handgrip_viewer.runners.live
```

This enables log filtering per subsystem (e.g., suppress `handgrip_viewer.viz.*` in CI while keeping `handgrip_viewer.core.*`).

#### 2.4.4 Call Site in `cli.py`

```python
@hydra.main(version_base=None, config_path="../../conf", config_name="config")
def app(cfg: AppConfig) -> int:
    # Call AFTER Hydra init — appends handlers, does not tear them out
    configure_logging(
        cfg.logging.level,
        log_file=cfg.logging.log_file,
        max_bytes=cfg.logging.max_bytes,
        backup_count=cfg.logging.backup_count,
    )
    log.info("Starting viewer: mode=%s", cfg.mode)
    ...
```

---

### 2.5 Configuration Migration Map

Changes to `conf/config.yaml` required by the refactor:

| Old key / location | New key | Change type | Notes |
|---|---|---|---|
| (module global) `RAW_COLOR = "red"` | `viewer.style.raw_color` | New | Moved from Python to YAML |
| (module global) `FILTERED_COLOR = "green"` | `viewer.style.filtered_color` | New | |
| (module global) `REFERENCE_COLOR = "purple"` | `viewer.style.reference_color` | New | |
| (module global) `TIMING_COLOR = "blue"` | `viewer.style.timing_color` | New | |
| (module global) `GRID_ALPHA = 0.3` | `viewer.style.grid_alpha` | New | |
| `viewer.xy_correlation.color` | `viewer.style.xy_color` | Rename | Consolidate style section |
| `viewer.xy_correlation.alpha_old` | `viewer.style.xy_alpha_old` | Move | |
| `viewer.xy_correlation.alpha_new` | `viewer.style.xy_alpha_new` | Move | |
| `logging.level` | `logging.level` | Unchanged | |
| _(absent)_ | `logging.log_file` | New | Explicit log path |
| _(absent)_ | `logging.max_bytes` | New | `10485760` (10 MB) |
| _(absent)_ | `logging.backup_count` | New | `3` |
| `hydra.run.dir: .` | unchanged | Unchanged | Keeps outputs local |

**Proposed new `conf/viewer/style.yaml` config group** (loaded via `defaults:` list):

```yaml
# conf/viewer/style.yaml
raw_color: "red"
filtered_color: "green"
reference_color: "purple"
timing_color: "blue"
grid_alpha: 0.3
xy_color: "red"
xy_alpha_old: 0.12
xy_alpha_new: 0.92
```

---

### 2.6 Hydra Conflict Avoidance

Hydra sets `OmegaConf`'s struct mode on the composed config. Two known friction points and their resolutions:

| Friction | Resolution |
|---|---|
| `configure_logging(force=True)` destroys Hydra's file sink | Remove `force=True`; use the additive `configure_logging()` in §2.4.2 |
| `OmegaConf.select(cfg, path, default=X)` bypasses struct validation | Replace with direct attribute access on typed dataclass config |
| Hydra writes its own `outputs/` directory | `hydra.run.dir: .` and `hydra.output_subdir: null` already set — keep as-is |
| Structured config `MISSING` fields cause instantiation errors | Validate required fields in `cli.py` before mode dispatch |

---

## 3. Code Pruning & Debt Identification

### 3.1 Dead Code — Mark for Removal

#### `_candidate_columns()` (line 1095–1100)

```python
def _candidate_columns(preferred: str, fallbacks: list[str]) -> list[str]:
    seen = []
    for col in [preferred, *fallbacks]:
        if col not in seen:
            seen.append(col)
    return seen
```

**Why dead:** `load_csv_replay()` is the only caller. Every call site passes a single-element list with no fallbacks:

```python
target_clock = _pick_existing_column(target_cols, [str(cfg.channels.target.clock_label)], "target clock")
```

The deduplication logic has no effect. The function is never called in the pattern it was designed for (`_candidate_columns(preferred, fallbacks)`). **Remove both the function and any call sites.** `_pick_existing_column` already handles the search correctly.

---

#### `_cfg_str_path()` and `_cfg_bool_path()` (lines 119–128)

```python
def _cfg_str_path(cfg: DictConfig, path: str, default: str) -> str: ...
def _cfg_bool_path(cfg: DictConfig, path: str, default: bool) -> bool: ...
```

**Why bloat:** These were defensive wrappers around untyped `OmegaConf.select` to coerce stray `None` values. With a structured `@dataclass` config (§2.3), the types are enforced at Hydra construction time. These functions have no role in the refactored codebase. **Remove.**

---

#### Scattered `OmegaConf.select(cfg, ..., default=...)` calls (20+ sites)

Entire pattern is legacy defensive programming against an untyped config. After migration to structured config in §2.3, every `OmegaConf.select` call becomes a direct attribute access. **Remove all `OmegaConf.select` call sites.**

---

#### `ALLOWED_MODES` module constant (line 31)

```python
ALLOWED_MODES = {"live", "live_with_reference_validation", "csv_replay", "xdf_replay"}
```

**Observation:** This is a valid sentinel, but it belongs in `cli.py` (or the config schema as a `Literal` type), not as a module-level global in the main file. **Relocate to `cli.py`** where the mode dispatch lives.

---

### 3.2 Legacy Compatibility — Verify & Confirm Removal

#### Legacy fused CSV replay

The docstring in `load_csv_replay()` (line 1128) already states:

> *"Legacy fused CSV replay was removed in the calibration-schema upgrade."*

The function now exclusively expects two separate native-stream CSVs (`target_csv_path`, `reference_csv_path`). **No action needed — already clean.**

#### `source_type` string `"csv_replay_dual_native_v2"`

The `v2` suffix implies a previous `v1` format. Search confirms no v1 loading path exists in the codebase. The string is an audit label only; no branching on it. **No action needed.**

---

### 3.3 Bloated Defensive Programming

#### Multiple `float(cfg.viewer.window_seconds)` casts at every call site

```python
# Current: explicit cast at every use
float(cfg.viewer.window_seconds)
float(cfg.viewer.refresh_s)
float(target_cfg.acquisition_delay)
```

**Why:** Original `DictConfig` fields are untyped `Any`; defensive `float()` casts prevent type errors. With a structured config (`ViewerCfg.window_seconds: float`), the type is guaranteed at construction. **Remove all defensive `float()` / `int()` / `bool()` / `str()` casts on config values.** Keep casts on numpy operations and user-supplied strings where the type genuinely varies.

#### `_stream_data_to_window` shape guard (lines 255–259)

```python
if matrix.ndim != 2:
    return None
if role == "target":
    if matrix.shape[0] < 3:
        return None
```

**Assessment:** `mne-lsl`'s `get_data()` always returns a 2D array; the `ndim != 2` check guards against a scenario the library does not produce. The channel-count checks (`< 3`, `< 2`) are legitimate — they guard against misconfigured streams and should be **kept**, but with a `log.warning` instead of silent `None` return to aid debugging.

---

## 4. Refactor Execution Checklist

### Phase 1 — Structural Setup

- [ ] Create `src/handgrip_viewer/` package skeleton with `__init__.py` in all directories
- [ ] Add `pyproject.toml` per §2.2
- [ ] Run `uv venv && uv pip install -e ".[live,xdf,dev]"` and verify import succeeds
- [ ] Verify `handgrip-viewer --help` resolves via entry point

### Phase 2 — Configuration Schema

- [ ] Implement `config.py` with all `@dataclass` config nodes (§2.3)
- [ ] Call `register_config()` in `cli.py` before `@hydra.main`
- [ ] Update `conf/config.yaml` with new keys from §2.5 migration map
- [ ] Add `conf/viewer/style.yaml` config group
- [ ] Run `handgrip-viewer --cfg job` and confirm all keys resolve without `MISSING` errors

### Phase 3 — Logging

- [ ] Implement `logging_setup.py` per §2.4.2 (additive handlers, rotating file)
- [ ] Rename all `LOGGER` → `log = logging.getLogger(__name__)` in every module
- [ ] Remove `configure_logging(force=True)` pattern
- [ ] Smoke-test: run any mode; confirm both console output and `.log` file are populated

### Phase 4 — Module Decomposition

- [ ] Extract `types.py`: `StreamLayout`, `TargetWindow`, `ReferenceWindow`, `DualWindow`, `DualReplayData`, `FigureHandles`
- [ ] Extract `errors.py`: `ViewerError`, `StreamConnectionError`, `ReplayLoadError`
- [ ] Extract `core/timing.py`: `_lsl_interval_ms`, `_clock_interval_ms`, `_clock_validation_metrics`
- [ ] Extract `core/alignment.py`: `_compute_xy_reference_time_shift_s`, `_interpolate_reference_to_target`, `_latest_finite_timestamp`
- [ ] Extract `core/replay.py`: `load_csv_replay`, `load_xdf_replay`, `_window_from_replay`, `_normalize_common_timebases`, XDF helpers, CSV helpers
- [ ] Extract `core/stream.py`: `build_streams`, `fetch_live_window`, `_stream_data_to_window`, `_slice_*` helpers
- [ ] Extract `viz/figure.py`: `init_figure`, `clear_plot_artists`, `update_axis`, `update_axis_expand_only`, `_compute_axis_limits`, `_finite_xy`
- [ ] Extract `viz/plots.py`: `update_plots`, `_render_info_panel`, `_update_xy_line_collection`, `_zip_columns`, `_format_latest`
- [ ] Extract `viz/markers.py`: `_load_marker_events_from_ndjson`, `_draw_marker_overlays`
- [ ] Extract `runners/live.py`: `run_live_mode`, `_establish_live_cutoff_from_latest_window`, `_slice_dual_after_cutoffs`
- [ ] Extract `runners/replay.py`: `run_replay_mode`
- [ ] Move mode dispatch and `@hydra.main` decorator to `cli.py`

### Phase 5 — Code Pruning

- [ ] Delete `_candidate_columns()` and its (unused) call pattern
- [ ] Delete `_cfg_str_path()` and `_cfg_bool_path()`
- [ ] Replace all `OmegaConf.select(cfg, path, default=X)` with direct typed attribute access
- [ ] Remove defensive `float()` / `int()` / `str()` casts on config attributes
- [ ] Add `log.warning` to `_stream_data_to_window` shape guards (do not silently return `None`)
- [ ] Move `ALLOWED_MODES` into `cli.py` as a local constant or `Literal` type

### Phase 6 — Feature Completeness Verification

- [ ] `mode=live` starts, renders 8-panel figure, keyboard controls respond
- [ ] `mode=live_with_reference_validation` — identical to live; `validate_reference` flag propagated
- [ ] `mode=csv_replay` — loads v2 dual CSVs, animates replay at configured speed, loops correctly
- [ ] `mode=xdf_replay` — loads `.xdf`, stream selection by name/stype/source_id, replay animates
- [ ] `--dry-run` not applicable (viewer only), but `mode=csv_replay` + fixture CSV constitutes an offline smoke test
- [ ] Log file (`handgrip_realtime_viewer.log`) is non-empty after any mode run
- [ ] Ctrl-C exits cleanly: streams disconnected, figure closed, exit code `0`

### Phase 7 — Tests

- [ ] `tests/unit/test_timing.py`: `_lsl_interval_ms` with known arrays; `_clock_validation_metrics` with synthetic data
- [ ] `tests/unit/test_alignment.py`: `_interpolate_reference_to_target` with controlled target/reference pairs; gap rejection
- [ ] `tests/unit/test_replay_loaders.py`: `_window_from_replay` with a `DualReplayData` fixture; `_normalize_common_timebases`
- [ ] `tests/integration/test_csv_replay.py`: `load_csv_replay` against fixture CSVs copied from `data/`

---

## 5. Summary Table

| Aspect | Current State | After Refactor |
|---|---|---|
| **Layout** | Single 1 412-line flat file | 14-module `src/` package |
| **Dependency management** | None | `pyproject.toml` + `uv.lock` |
| **Config schema** | Untyped YAML + 20+ `OmegaConf.select` call sites | Structured `@dataclass` config; 0 `OmegaConf.select` calls |
| **Magic constants** | 5 module-level color globals | Moved to `conf/viewer/style.yaml` |
| **Logging** | Single logger, `force=True`, empty log file | Module-scoped `__name__` loggers, rotating `FileHandler`, file populated |
| **Dead code** | `_candidate_columns`, `_cfg_str_path`, `_cfg_bool_path` | Deleted |
| **Testable surface** | 0% (all logic colocated with I/O) | `core/` modules are pure; unit-testable without mocks |
| **Entry point** | `python handgrip_realtime_viewer.py` | `python -m handgrip_viewer` and `handgrip-viewer` CLI |
| **Feature completeness** | All 4 modes | All 4 modes preserved; backward-compatible config |

---

*Refactor plan produced per the Three-Pillar framework (Correctness · Operability · Maintainability) and PyPA `src`-layout standards.*
