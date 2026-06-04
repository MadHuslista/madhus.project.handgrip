# Handgrip Analysis — Refactor Plan

> *"Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away."*
> — Antoine de Saint-Exupéry

**Module:** `handgrip-analysis`  
**Date:** 2026-05-06  
**Scope:** Architecture standardization, dependency management, configuration consolidation, observability  

---

## Table of Contents

1. [System Inventory](#1-system-inventory)
2. [Ideal vs Current Architecture](#2-ideal-vs-current-architecture)
3. [Technical Debt Catalogue](#3-technical-debt-catalogue)
4. [Refactoring Strategy](#4-refactoring-strategy)
5. [Proposed File Tree](#5-proposed-file-tree)
6. [Configuration Migration Map](#6-configuration-migration-map)
7. [Deprecation & Pruning Checklist](#7-deprecation--pruning-checklist)

---

## 1. System Inventory

### 1.1 Feature Inventory

| Feature | Location | Description |
|---|---|---|
| CSV capture loading | `io.py::load_capture` | Reads sensor CSVs; auto-selects monotonic time column from `device_clock_us`, `lsl_timestamp_s`, or `host_unix_time_ns` |
| Sampling statistics | `io.py::sampling_summary` | Returns `n_samples`, `duration_s`, `fs_median_hz`, dt stats |
| Sample rate estimation | `io.py::estimate_fs` | Median-based Fs from time vector |
| Path creation utility | `io.py::ensure_dir` | `mkdir -p` wrapper |
| Rolling mean/std/slope | `dsp.py::rolling_mean_std_slope` | Windowed statistics for warmup analysis |
| Ready-time suggestion | `dsp.py::suggest_ready_time` | Detects signal stabilization |
| Welch PSD | `dsp.py::welch_psd` | Adaptive-windowed power spectral density |
| Alias hinting | `dsp.py::alias_hint` | Flags 50/60 Hz mains aliases at given output rate |
| PSD peak detection | `dsp.py::dominant_psd_peaks` | Top-N peaks by prominence |
| Allan deviation | `dsp.py::allan_deviation` | Log-spaced τ sweep for noise characterization |
| Linear trend | `dsp.py::linear_trend` | `np.polyfit` wrapper for drift analysis |
| Band power | `dsp.py::bandpower` | Trapezoidal integration within frequency band |
| Event detection | `dsp.py::detect_events` | Threshold/merge/pad approach for grip events |
| Event metrics | `dsp.py::event_metrics` | Per-event DataFrame: peak, rise time, max df/dt, hold std |
| Robust STD | `dsp.py::robust_std` | MAD-based outlier-robust standard deviation |
| Filter application | `dsp.py::apply_filter_spec` | Dispatches: `identity`, `butter_lowpass`, `one_pole_lowpass`, `moving_average`, `median`, `notch`, `chain` |
| Filter spec loading | `dsp.py::load_filter_specs` | YAML → list of filter dicts |
| JSON serialization | `report.py::save_json` | Indented JSON writer |
| CSV serialization | `report.py::save_csv` | `DataFrame.to_csv` wrapper |
| Stage 1 — Warmup | `scripts/stage1_startup_warmup.py` | Rolling stats, suggests ready time, exports summary.json + 4 PNG plots |
| Stage 2 — Static Noise | `scripts/stage2_static_noise.py` | Multi-channel noise floor: PSD, histogram, Allan deviation, PSD peak CSV |
| Stage 3 — Loaded Drift | `scripts/stage3_loaded_drift.py` | Linear trend, detrended residual, return-to-zero error |
| Stage 4 — Grip Dynamics | `scripts/stage4_grip_dynamics.py` | Multi-file event detection, per-event metrics CSV, overlay and hold-segment PSD |
| Stage 5 — Interference Compare | `scripts/stage5_interference_compare.py` | Multi-label PSD overlay and peak CSV comparison |
| Stage 6a — Filter Design | `scripts/stage6_filter_design.py` | Single-signal filter benchmark: event fidelity metrics, time/PSD overlays |
| Stage 6b — Filter Family Review | `scripts/stage6_filter_family_review.py` | Multi-signal filter ranking: composite score, ranked CSV, bar chart |
| Batch runner | `scripts/run_all.py` | CSV-manifest dispatcher: routes rows to stage scripts via subprocess |
| Filter YAML config | `configs/filter_candidates.yaml` | 11 named filter candidates |

### 1.2 Source Package Inventory

| Package | Files | Status |
|---|---|---|
| `handgrip_analysis` | `io.py`, `dsp.py`, `report.py` | **Primary** — used by stages 1–5 |
| `handgrip_review` | `common.py` | **Legacy duplicate** — used only by stage6a and stage6b |

### 1.3 External Dependencies

| Library | Used for | Declared in |
|---|---|---|
| `numpy` | Numerical arrays throughout | `pyproject.toml`, `requirements.txt` |
| `pandas` | DataFrames, CSV I/O | `pyproject.toml`, `requirements.txt` |
| `scipy` | `signal.butter`, `signal.welch`, `signal.find_peaks` | `pyproject.toml`, `requirements.txt` |
| `matplotlib` | All plot generation | `pyproject.toml`, `requirements.txt` |
| `pyyaml` | Filter spec loading | `pyproject.toml`, `requirements.txt` |

---

## 2. Ideal vs Current Architecture

### 2.1 Current Architecture

```
Handgrip_Analysis/
├── pyproject.toml              ← incomplete (no build-system, no entry points)
├── requirements.txt            ← duplicates pyproject.toml
├── .python-version
├── configs/
│   └── filter_candidates.yaml  ← loaded via raw yaml.safe_load
├── scripts/                    ← 8 scripts; all use sys.path.insert hack
│   ├── run_all.py              ← stage5 skipped; no stage6 support
│   ├── stage1_startup_warmup.py
│   ├── stage2_static_noise.py
│   ├── stage3_loaded_drift.py
│   ├── stage4_grip_dynamics.py
│   ├── stage5_interference_compare.py
│   ├── stage6_filter_design.py      ← imports handgrip_REVIEW, not analysis
│   └── stage6_filter_family_review.py ← imports handgrip_REVIEW, not analysis
└── src/
    ├── handgrip_analysis/      ← primary library, missing butter_highpass/bandpass
    │   ├── __init__.py
    │   ├── io.py
    │   ├── dsp.py
    │   └── report.py
    └── handgrip_review/        ← legacy duplicate with weaker load_capture
        ├── __init__.py
        └── common.py
```

**Characterization:** The current structure is a *partially evolved* codebase. It has a `src/` layout (good), typed dataclasses (good), and a functional core pattern in `dsp.py` (good). However, it has accumulated two overlapping libraries, no configuration management, no logging, and a build configuration that cannot produce an installable package.

### 2.2 Ideal Architecture

```
handgrip-analysis/
├── pyproject.toml              ← PEP 621 + hatchling + entry points; uv-managed
├── uv.lock                     ← deterministic lockfile
├── .python-version
├── README.md
├── conf/                       ← Hydra configuration tree
│   ├── config.yaml             ← root: defaults list, logging, output
│   ├── analysis/               ← per-stage parameter groups
│   │   ├── stage1.yaml
│   │   ├── stage2.yaml
│   │   ├── stage3.yaml
│   │   ├── stage4.yaml
│   │   ├── stage5.yaml
│   │   └── stage6.yaml
│   ├── io/
│   │   └── defaults.yaml       ← time_source, default channel
│   ├── dsp/
│   │   └── defaults.yaml       ← bandpower bands, PSD params, event params
│   └── filters/
│       └── candidates.yaml     ← migrated from configs/
├── src/
│   └── handgrip_analysis/
│       ├── __init__.py
│       ├── io.py               ← unchanged (strong design)
│       ├── dsp.py              ← add: butter_highpass, butter_bandpass, best_event_metrics
│       ├── report.py           ← unchanged
│       └── _logging.py         ← NEW: setup_logging() helper
└── scripts/
    ├── run_all.py              ← add stage5/stage6 support; Hydra; logging
    ├── stage1_startup_warmup.py    ← Hydra config; logging; no sys.path hack
    ├── stage2_static_noise.py
    ├── stage3_loaded_drift.py
    ├── stage4_grip_dynamics.py
    ├── stage5_interference_compare.py
    ├── stage6_filter_design.py     ← migrated to handgrip_analysis
    └── stage6_filter_family_review.py ← migrated to handgrip_analysis
```

### 2.3 Gap Analysis: Current vs Ideal

| Dimension | Current State | Ideal State | Gap Severity |
|---|---|---|---|
| **Package installability** | No `[build-system]` → `pip install` fails | `hatchling` build; `uv` lockfile | 🔴 Critical |
| **Duplicate library** | `handgrip_review` shadows `handgrip_analysis` | Single authoritative package | 🔴 Critical |
| **Filter type coverage** | `apply_filter_spec` missing `butter_highpass`, `butter_bandpass` | All YAML-declared types implemented | 🔴 Critical |
| **Stage6 dependency** | Stage6 imports `handgrip_review` (legacy) | Stage6 imports `handgrip_analysis` | 🔴 Critical |
| **Configuration management** | Magic numbers in argparse defaults; raw YAML load | Hydra with typed schemas; constants in conf/ | 🟡 High |
| **Observability / Logging** | Zero logging anywhere | `logging` hierarchy; file + console handlers | 🟡 High |
| **sys.path hacks** | All 8 scripts do `sys.path.insert` | Proper package install; no path manipulation | 🟡 High |
| **Dependency duplication** | `requirements.txt` duplicates `pyproject.toml` | Single source of truth in `pyproject.toml` | 🟠 Medium |
| **run_all.py coverage** | stage5 explicitly skipped; stage6 absent | All 8 stages dispatchable | 🟠 Medium |
| **`best_event_metrics`** | Only in legacy `handgrip_review.common` | Promoted to `handgrip_analysis.dsp` | 🟡 High |
| **`load_capture` API** | Legacy version only supports `device_clock_us` | Unified `io.load_capture` with `time_source` param | 🔴 Critical (for portability) |

---

## 3. Technical Debt Catalogue

### 3.1 Critical Gaps

#### Gap A: `apply_filter_spec` is incomplete vs. the YAML config

`handgrip_analysis/dsp.py::apply_filter_spec` handles 7 filter types, but the deployed `configs/filter_candidates.yaml` declares two types that are entirely absent:

| YAML filter name | Declared `type` | Present in `dsp.apply_filter_spec` | Present in `handgrip_review.common.apply_filter` |
|---|---|---|---|
| `highpass_0p05hz` | `butter_highpass` | ❌ Missing | ✅ |
| `highpass_0p10hz` | `butter_highpass` | ❌ Missing | ✅ |
| `bandpass_0p05_12hz` | `butter_bandpass` | ❌ Missing | ✅ |
| `bandpass_0p10_12hz` | `butter_bandpass` | ❌ Missing | ✅ |

**This is the root cause of the `handgrip_review` dependency in stage6 scripts.** The stage6 authors could not use the main library because it would raise `ValueError: Unsupported filter type` for half the YAML candidates. The fix is to add the two missing branches to `dsp.apply_filter_spec`.

#### Gap B: `best_event_metrics` lives only in the legacy package

`handgrip_review.common::best_event_metrics` provides a single-value summary (peak, rise time, plateau std) for the dominant event in a capture. This function has no equivalent in `handgrip_analysis`. Stage6 scripts depend on it for filter benchmarking. It must be promoted to `dsp.py`.

#### Gap C: `handgrip_review.common::load_capture` is a regression

The `handgrip_review` version hardcodes `device_clock_us` as the only time source, discarding the adaptive `time_source` parameter logic from `io.py`. Stage6 scripts are therefore silently incompatible with LSL-timestamped or host-timestamped captures.

#### Gap D: `dominant_psd_peaks` has divergent return types

| Location | Return type | Consumer |
|---|---|---|
| `dsp.py::dominant_psd_peaks` | `list[PeakInfo]` | stages 2, 4, 5 |
| `handgrip_review.common::dominant_psd_peaks` | `pd.DataFrame` | stage6b |

Stage6b calls `.to_csv()` directly on the return value. After consolidation, the unified function must return `list[PeakInfo]` (the stronger, typed contract), and stage6b must be updated to convert to DataFrame where needed.

### 3.2 Architecture Debt

#### Debt A: `sys.path` injection in all scripts

All 8 scripts contain:

```python
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
```

This is a development-only workaround for an uninstalled package. It makes scripts order-dependent, breaks `pytest` discovery, and is rendered unnecessary by `pip install -e .` / `uv sync`. Once the build system is configured, remove from all scripts.

#### Debt B: `pyproject.toml` is non-functional as a build config

The current file is missing the `[build-system]` table. The package cannot be built or installed:

```toml
# ❌ CURRENT — no build-system → pip/uv cannot install
[project]
name = "handgrip-analysis"
...
```

```toml
# ✅ REQUIRED
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### Debt C: `requirements.txt` is a maintenance liability

Dependencies are declared in both `pyproject.toml` and `requirements.txt` with no single source of truth. After migration to `uv`, all dependencies live in `pyproject.toml`; `uv.lock` serves the reproducibility role that `requirements.txt` was approximating.

### 3.3 Magic Values Scattered Across Scripts

The following numeric constants appear as argparse defaults or inline literals with no central declaration:

| Value | Meaning | Locations |
|---|---|---|
| `10.0` | Warmup / baseline window duration (s) | `stage1` `--window-s`, `stage3` `--pre-window-s`, `stage3` `--post-window-s` |
| `5.0` | Event detection threshold (sigma) | `stage4` `--threshold-sigma`, `handgrip_review.common::detect_events` |
| `0.0, 1.0, 4.0, 12.0, 30.0` | Bandpower band edges (Hz) | `stage2`, `stage5`, `stage6a` |
| `30.0, 49.0` | HF noise assessment range (Hz) | `stage6a`, `stage6b` |
| `0.8` | Tail fraction for plateau std | `dsp::event_metrics`, `dsp::suggest_ready_time`, `common::best_event_metrics` |
| `0.25` | Event padding (s) | `dsp::detect_events`, `common::detect_events` |
| `0.15` | Merge gap for event grouping (s) | `dsp::detect_events`, `common::detect_events` |
| `0.20` | Minimum event duration (s) | `dsp::detect_events`, `common::detect_events` |
| `2.0` | Baseline window for event detection (s) | `dsp::detect_events`, `common::detect_events` |
| `150` | Plot DPI | Every script |
| `3.0` | PSD peak prominence threshold (dB) | `dsp::dominant_psd_peaks` |
| `0.25, 0.35, 0.10, 0.10, 0.20` | Composite score weights | `stage6b` |

All of these should be defined in the Hydra configuration schema and referenced by name, not as inline literals.

### 3.4 Dead Code

#### Dead A: `run_all.py` — `stage5: None` mapping

```python
STAGE_TO_SCRIPT = {
    ...
    "stage5": None,   # ← dead: immediately followed by "if stage == 'stage5': continue"
}
```

The `None` entry is unreachable. The `continue` guard fires before the dict lookup is used. Additionally, stage5 is a fully functional, standalone script (`stage5_interference_compare.py`) but is never invoked by `run_all.py`, and stage6 scripts are not registered at all.

#### Dead B: `handgrip_review.common::apply_filter` — `one_pole_lowpass`, `moving_average`, `median` are absent

The legacy `apply_filter` handles only 5 filter types vs. 7 in `dsp.apply_filter_spec`. The three missing types (`one_pole_lowpass`, `moving_average`, `median`) exist in the primary library but were never backported. These are not dead code in `dsp.py` — they are dead in `common.py` (those branches were never written).

#### Dead C: `handgrip_review/common.py::load_capture` `df` return value

The function returns `(t, y, fs, df)` — a 4-tuple. The raw DataFrame `df` is captured as `_` in every call site across both stage6 scripts. It is never used.

---

## 4. Refactoring Strategy

### 4.1 Structural Layout

The project already uses `src/` layout — this is correct and must be preserved. The changes are:

1. **Remove `src/handgrip_review/`** entirely after consolidating all unique functionality into `src/handgrip_analysis/`.
2. **Rename `configs/`** to `conf/` to align with Hydra conventions.
3. **Add `conf/` subtree** with structured Hydra config groups.
4. **Add `src/handgrip_analysis/_logging.py`** for centralized logging setup.

No packages should be renamed. The public API of `handgrip_analysis` must remain stable.

### 4.2 Dependency Management (`pyproject.toml` + `uv`)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "handgrip-analysis"
version = "0.2.0"
description = "Handgrip sensor signal analysis pipeline"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "matplotlib>=3.8",
    "numpy>=1.26",
    "pandas>=2.2",
    "pyyaml>=6.0",
    "scipy>=1.13",
    "hydra-core>=1.3",       # ← NEW: configuration management
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
ha-stage1 = "handgrip_analysis._cli.stage1:main"
ha-stage2 = "handgrip_analysis._cli.stage2:main"
ha-stage3 = "handgrip_analysis._cli.stage3:main"
ha-stage4 = "handgrip_analysis._cli.stage4:main"
ha-stage5 = "handgrip_analysis._cli.stage5:main"
ha-stage6-design = "handgrip_analysis._cli.stage6_design:main"
ha-stage6-review = "handgrip_analysis._cli.stage6_review:main"
ha-run-all = "handgrip_analysis._cli.run_all:main"

[tool.hatch.build.targets.wheel]
packages = ["src/handgrip_analysis"]

[tool.uv]
python = "3.11"
```

**Development workflow:**

```bash
# One-time setup (replaces pip install -e . + venv creation)
uv sync

# Run any script
uv run ha-stage1 --input capture.csv --outdir ./out/stage1

# Or directly (after uv sync, venv is activated)
python -m handgrip_analysis._cli.stage1 ...
```

Delete `requirements.txt` after merging all dependencies into `pyproject.toml`.

### 4.3 Configuration Management (Hydra)

Replace raw `yaml.safe_load` and argparse defaults with Hydra's structured configuration. **Important:** Hydra uses its own `OmegaConf` config system and must not conflict with the existing `pyyaml` usage for filter spec loading (which can remain as-is inside `dsp.load_filter_specs`).

#### Root config (`conf/config.yaml`)

```yaml
defaults:
  - io: defaults
  - dsp: defaults
  - analysis: stage1    # overridden per-script
  - _self_

hydra:
  run:
    dir: outputs/${now:%Y-%m-%d_%H-%M-%S}

logging:
  level: INFO
  file: ${hydra:run.dir}/run.log
```

#### DSP defaults (`conf/dsp/defaults.yaml`)

```yaml
# Bandpower frequency bands [Hz]
bandpower_bands:
  - [0.0, 1.0]
  - [1.0, 4.0]
  - [4.0, 12.0]
  - [12.0, 30.0]
  - [30.0, 49.0]      # HF noise assessment band

# Welch PSD
welch:
  max_nperseg: 2048
  min_nperseg: 256
  window: hann

# Event detection
event_detection:
  baseline_s: 2.0
  threshold_sigma: 5.0
  min_duration_s: 0.20
  merge_gap_s: 0.15
  pad_s: 0.25
  tail_fraction: 0.80   # for plateau std

# PSD peak finder
psd_peaks:
  prominence_db: 3.0
  max_peaks: 8

# Plot output
plot:
  dpi: 150
  figsize_wide: [12, 5]
  figsize_square: [10, 5]
```

#### Stage-specific configs (example: `conf/analysis/stage1.yaml`)

```yaml
# Stage 1: Startup warmup analysis
warmup_window_s: 10.0
channel: raw
time_source: auto
```

#### Stage 6b scoring weights (`conf/analysis/stage6.yaml`)

```yaml
# Filter family composite score weights (must sum to 1.0)
composite_weights:
  rest_std_norm: 0.25
  mean_peak_relative_error: 0.35
  mean_rise_relative_error: 0.10
  mean_peak_time_shift_norm: 0.10
  mean_dfdt_deviation: 0.20

hf_noise_band_hz: [30.0, 49.0]
```

**Hydra integration pattern for scripts:**

```python
# ✅ After refactor: clean, no argparse, no sys.path hack
import hydra
from omegaconf import DictConfig
import logging

log = logging.getLogger(__name__)

@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    log.info("Stage 1 starting with config: %s", cfg)
    cap = load_capture(cfg.input, time_source=cfg.io.time_source)
    ...
```

> **Compatibility note:** Hydra takes over CLI argument parsing. The `--input`, `--outdir`, and other flags are replaced by Hydra overrides: `ha-stage1 input=capture.csv outdir=./out`. If strict backward CLI compatibility is required, add a thin `argparse` shim that constructs the Hydra config and calls `main()` — but this is only needed if external callers depend on the current flag names.

### 4.4 Observability: Hierarchical Logging

Add `src/handgrip_analysis/_logging.py`:

```python
"""Logging setup for the handgrip-analysis package."""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
) -> None:
    """
    Configure root logger with console + optional file handler.
    
    Call once at application entry point (main script or Hydra post_run hook).
    Library modules use logging.getLogger(__name__) — they do NOT call this.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler (mirrors console output)
    if log_file is not None:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
```

Each library module gains a module-level logger:

```python
# In io.py, dsp.py, report.py — add at top of file:
import logging
log = logging.getLogger(__name__)

# Usage examples:
log.debug("load_capture: selected time column %r for %s", selected_col, path)
log.info("load_capture: loaded %d samples, fs=%.1f Hz", len(time_s), fs)
log.warning("estimate_fs: fewer than 2 valid dt values — returning NaN")
log.error("apply_filter_spec: unsupported filter type %r", filter_type)
```

**Logging level guidance:**

| Level | Used for |
|---|---|
| `DEBUG` | Per-sample decisions, column selection, filter dispatch |
| `INFO` | Stage start/end, file loaded, events detected, outputs written |
| `WARNING` | Skipped channel (no `value_filtered` column), NaN estimates |
| `ERROR` | Unsupported filter type, missing required column, non-monotonic time |
| `CRITICAL` | Reserved for unrecoverable I/O failures before exit |

### 4.5 Library Changes for Feature Completeness

All changes preserve existing public API. No renames, no signature changes.

#### Add `butter_highpass` and `butter_bandpass` to `dsp.apply_filter_spec`

```python
# In dsp.py::apply_filter_spec — insert after butter_lowpass block:

if filter_type == "butter_highpass":
    order = int(spec.get("order", 2))
    cutoff_hz = float(spec["cutoff_hz"])
    sos = signal.butter(order, cutoff_hz, btype="high", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, y)

if filter_type == "butter_bandpass":
    order = int(spec.get("order", 2))
    low_hz = float(spec["low_hz"])
    high_hz = float(spec["high_hz"])
    sos = signal.butter(
        order, [low_hz, high_hz], btype="bandpass", fs=fs, output="sos"
    )
    return signal.sosfiltfilt(sos, y)
```

#### Promote `best_event_metrics` to `dsp.py`

Port the function from `handgrip_review.common` to `dsp.py`, updating it to use `dsp.detect_events` (which returns `list[EventWindow]`, not `list[tuple]`). The public signature and return dict keys must remain identical so stage6 scripts require only an import change:

```python
def best_event_metrics(
    y: np.ndarray, time_s: np.ndarray, fs: float
) -> dict[str, float]:
    """
    Summarise the dominant grip event in a capture.
    
    Returns keys: n_events, peak_value, peak_time_s, rise_10_90_s,
                  max_dfdt, plateau_std_last20pct, event_start_s, event_end_s
    """
    events = detect_events(y, fs)
    if not events:
        return {k: float("nan") for k in (
            "peak_value", "peak_time_s", "rise_10_90_s",
            "max_dfdt", "plateau_std_last20pct", "event_start_s", "event_end_s"
        )} | {"n_events": 0}
    
    best = max(events, key=lambda ev: float(y[ev.peak_idx] - y[ev.start_idx]))
    seg_y = y[best.start_idx : best.end_idx + 1]
    seg_t = time_s[best.start_idx : best.end_idx + 1]
    # ... (existing logic from common.py, adapted to EventWindow)
```

#### Update `__init__.py` exports

```python
# src/handgrip_analysis/__init__.py
__all__ = ["io", "dsp", "report"]
# No functional change needed; public API is module-level
```

#### Fix stage6 scripts after library consolidation

Both `stage6_filter_design.py` and `stage6_filter_family_review.py` must replace:

```python
# ❌ Before
from handgrip_review.common import (
    apply_filter, best_event_metrics, ensure_dir,
    load_capture, load_filter_specs, save_json, welch_psd,
)
t, y, fs, _ = load_capture(args.input)   # legacy 4-tuple API
```

With:

```python
# ✅ After
from handgrip_analysis.dsp import (
    apply_filter_spec as apply_filter,
    best_event_metrics, dominant_psd_peaks, welch_psd,
)
from handgrip_analysis.io import ensure_dir, load_capture
from handgrip_analysis.dsp import load_filter_specs
from handgrip_analysis.report import save_json

cap = load_capture(args.input, time_source=cfg.io.time_source)
t, y, fs = cap.time_s, cap.series("raw"), cap.fs_estimate_hz
```

Additionally, stage6b calls `peaks.to_csv(...)` on the return of `dominant_psd_peaks`. After the switch to `list[PeakInfo]`, replace with:

```python
peaks = dominant_psd_peaks(f_rest, p_rest, cap.fs_estimate_hz)
peak_df = pd.DataFrame([
    {"frequency_hz": p.frequency_hz, "psd": p.psd,
     "prominence_db": p.prominence_db, "alias_hint": p.alias_hint or ""}
    for p in peaks
])
peak_df.to_csv(outdir / "rest_psd_peaks.csv", index=False)
```

#### Fix `run_all.py` to cover all 8 stages

```python
# ✅ Updated STAGE_TO_SCRIPT
STAGE_TO_SCRIPT = {
    "stage1": "stage1_startup_warmup.py",
    "stage2": "stage2_static_noise.py",
    "stage3": "stage3_loaded_drift.py",
    "stage4": "stage4_grip_dynamics.py",
    "stage5": "stage5_interference_compare.py",
    "stage6_design": "stage6_filter_design.py",
    "stage6_review": "stage6_filter_family_review.py",
}
```

Remove the `if stage == "stage5": continue` guard and the `None` mapping. Add logging for dispatched and skipped rows.

---

## 5. Proposed File Tree

```
handgrip-analysis/
├── pyproject.toml                      # Build + deps + entry points (hatchling)
├── uv.lock                             # Deterministic lock (generated by uv sync)
├── .python-version                     # 3.11
├── README.md
│
├── conf/                               # Hydra configuration tree
│   ├── config.yaml                     # Root: defaults list + logging config
│   ├── io/
│   │   └── defaults.yaml               # time_source, required_columns
│   ├── dsp/
│   │   └── defaults.yaml               # bandpower bands, event params, PSD, plot DPI
│   ├── analysis/
│   │   ├── stage1.yaml                 # warmup_window_s, channel
│   │   ├── stage2.yaml                 # channels list
│   │   ├── stage3.yaml                 # pre_window_s, post_window_s, channel
│   │   ├── stage4.yaml                 # threshold_sigma, channel
│   │   ├── stage5.yaml                 # channel
│   │   └── stage6.yaml                 # composite_weights, hf_noise_band_hz
│   └── filters/
│       └── candidates.yaml             # (migrated from configs/filter_candidates.yaml)
│
├── src/
│   └── handgrip_analysis/
│       ├── __init__.py                 # unchanged
│       ├── _logging.py                 # NEW: setup_logging() helper
│       ├── io.py                       # unchanged (strong design)
│       ├── dsp.py                      # + butter_highpass, butter_bandpass,
│       │                               #   best_event_metrics; + module logger
│       └── report.py                   # + module logger
│
├── scripts/                            # Analysis entry points
│   ├── run_all.py                      # + stage5/stage6 support; + logging
│   ├── stage1_startup_warmup.py        # Hydra @hydra.main; no sys.path hack
│   ├── stage2_static_noise.py
│   ├── stage3_loaded_drift.py
│   ├── stage4_grip_dynamics.py
│   ├── stage5_interference_compare.py
│   ├── stage6_filter_design.py         # migrated from handgrip_review
│   └── stage6_filter_family_review.py  # migrated from handgrip_review
│
└── tests/                              # NEW: test scaffolding
    ├── unit/
    │   ├── test_dsp.py                 # Pure function tests (no mocking)
    │   └── test_io.py                  # Config validation tests
    └── integration/
        └── test_pipeline.py            # Synthetic data end-to-end
```

**Removed from tree:**

- `src/handgrip_review/` — entire directory deprecated and deleted
- `requirements.txt` — replaced by `pyproject.toml` + `uv.lock`
- `configs/` — migrated to `conf/filters/`

---

## 6. Configuration Migration Map

### 6.1 `configs/filter_candidates.yaml` → `conf/filters/candidates.yaml`

No content changes. Path and filename change only. Update all `--config` references in scripts.

### 6.2 Argparse defaults → Hydra config keys

| Script | Old argparse flag | New Hydra path | Value |
|---|---|---|---|
| `stage1` | `--window-s` (default `10.0`) | `analysis.warmup_window_s` | `10.0` |
| `stage1` | `--channel` (default `"raw"`) | `analysis.channel` | `"raw"` |
| `stage1` | `--time-source` (default `"auto"`) | `io.time_source` | `"auto"` |
| `stage2` | `--channels` (default `["raw","filtered"]`) | `analysis.channels` | `["raw","filtered"]` |
| `stage2` | `--time-source` | `io.time_source` | `"auto"` |
| `stage3` | `--pre-window-s` (default `10.0`) | `analysis.pre_window_s` | `10.0` |
| `stage3` | `--post-window-s` (default `10.0`) | `analysis.post_window_s` | `10.0` |
| `stage3` | `--channel` | `analysis.channel` | `"raw"` |
| `stage4` | `--threshold-sigma` (default `5.0`) | `dsp.event_detection.threshold_sigma` | `5.0` |
| `stage4` | `--channel` | `analysis.channel` | `"raw"` |
| `stage5` | `--channel` | `analysis.channel` | `"raw"` |
| `stage6a/b` | `--config` | `analysis.filter_config` | `"${hydra:runtime.cwd}/conf/filters/candidates.yaml"` |
| All | `--outdir` | `hydra.run.dir` | Auto-managed by Hydra |

### 6.3 Inline constants → `conf/dsp/defaults.yaml`

| Current location | Constant | New config key |
|---|---|---|
| `stage2`, `stage5` | `bandpower(f, pxx, 0.0, 1.0)` | `dsp.bandpower_bands[0]` |
| `stage2`, `stage5` | `bandpower(f, pxx, 1.0, 4.0)` | `dsp.bandpower_bands[1]` |
| `stage2`, `stage5` | `bandpower(f, pxx, 4.0, 12.0)` | `dsp.bandpower_bands[2]` |
| `stage2`, `stage5` | `bandpower(f, pxx, 12.0, 30.0)` | `dsp.bandpower_bands[3]` |
| `stage6a`, `stage6b` | HF band `(30.0, 49.0)` | `dsp.bandpower_bands[4]` |
| All scripts | `dpi=150` | `dsp.plot.dpi` |
| `dsp.py` | `prominence=3.0` | `dsp.psd_peaks.prominence_db` |
| `dsp.py::detect_events` | `baseline_s=2.0` | `dsp.event_detection.baseline_s` |
| `dsp.py::detect_events` | `threshold_sigma=5.0` | `dsp.event_detection.threshold_sigma` |
| `dsp.py::detect_events` | `merge_gap_s=0.15` | `dsp.event_detection.merge_gap_s` |
| `dsp.py::detect_events` | `min_duration_s=0.20` | `dsp.event_detection.min_duration_s` |
| `dsp.py::detect_events` | `pad` (`0.25 * fs`) | `dsp.event_detection.pad_s` |
| `dsp.py` | tail fraction `0.8` | `dsp.event_detection.tail_fraction` |
| `stage6b` | composite score weights | `analysis.composite_weights.*` |

> **Implementation note:** DSP functions that accept these as parameters (e.g., `detect_events`) keep their default-argument signatures for library use. Scripts read from Hydra config and pass explicitly. This preserves the functional core/imperative shell boundary.

---

## 7. Deprecation & Pruning Checklist

### 7.1 Files Scheduled for Deletion

- [ ] `src/handgrip_review/__init__.py`
- [ ] `src/handgrip_review/common.py`
- [ ] `requirements.txt`
- [ ] `configs/filter_candidates.yaml` *(after migration to `conf/filters/`)*

### 7.2 Dead Code to Remove

- [ ] `run_all.py` — `STAGE_TO_SCRIPT["stage5"] = None` entry
- [ ] `run_all.py` — `if stage == "stage5": continue` guard
- [ ] `handgrip_review.common::load_capture` — `df` 4th return value (all call sites use `_`)
- [ ] All scripts — `ROOT = Path(...).parents[1]` block and `sys.path.insert` guard

### 7.3 Code to Consolidate (Remove Duplicates)

These functions exist in **both** `handgrip_review.common` and `handgrip_analysis.*`. The `handgrip_review` versions are deleted; the `handgrip_analysis` versions are authoritative:

| `handgrip_review.common` function | Canonical location | Notes |
|---|---|---|
| `ensure_dir` | `handgrip_analysis.io.ensure_dir` | Identical |
| `save_json` | `handgrip_analysis.report.save_json` | Identical |
| `welch_psd` | `handgrip_analysis.dsp.welch_psd` | `common` version has fixed `nperseg=2048`; canonical is adaptive |
| `bandpower` | `handgrip_analysis.dsp.bandpower` | Identical |
| `robust_std` | `handgrip_analysis.dsp.robust_std` | Identical |
| `load_filter_specs` | `handgrip_analysis.dsp.load_filter_specs` | Identical |
| `apply_filter` | `handgrip_analysis.dsp.apply_filter_spec` | `common` missing 3 types; add missing types to canonical |
| `dominant_psd_peaks` | `handgrip_analysis.dsp.dominant_psd_peaks` | Return type divergence — canonical returns `list[PeakInfo]`; stage6b caller updated |
| `detect_events` | `handgrip_analysis.dsp.detect_events` | `common` returns `list[tuple]`; canonical returns `list[EventWindow]` |

### 7.4 Functions to Promote (Missing from `handgrip_analysis`)

- [ ] `handgrip_review.common::best_event_metrics` → promote to `handgrip_analysis.dsp.best_event_metrics`

### 7.5 Feature Gaps to Close (Never Existed in Either Package)

- [ ] `butter_highpass` filter type in `dsp.apply_filter_spec`
- [ ] `butter_bandpass` filter type in `dsp.apply_filter_spec`
- [ ] `_logging.py` module with `setup_logging()` helper
- [ ] Module-level `log = logging.getLogger(__name__)` in `io.py`, `dsp.py`, `report.py`
- [ ] Logging calls at appropriate levels throughout all library functions
- [ ] `[build-system]` table in `pyproject.toml`
- [ ] Entry points `[project.scripts]` in `pyproject.toml`
- [ ] `uv.lock` generated by `uv sync`
- [ ] `run_all.py` support for stage5, stage6_design, stage6_review

### 7.6 Pre-Implementation Review Checklist (per CLAUDE.md)

- [ ] `src/` layout preserved ✅ (already present)
- [ ] Input/output contracts clearly defined? ✅ (typed dataclasses in `io.py`)
- [ ] All side effects identified and controllable? (needs logging interface)
- [ ] Validation phase separate from execution? ✅ (Hydra validates config at startup)
- [ ] Planning phase inspectable? (N/A — analysis scripts, not infrastructure tools)
- [ ] Error cases categorized with clear remediation? (logging levels address this)
- [ ] Configuration separated from code? ⬜ (target of this refactor)
- [ ] Can run unattended? ✅ (no interactive prompts)
- [ ] Operation idempotent? ✅ (all scripts are read-only; outputs are overwritten)
- [ ] Functional core (pure functions) separated from imperative shell (I/O)? ✅ (`dsp.py` / scripts boundary)

---

## Appendix: Execution Order

### Recommended Refactor Sequence

Implement in this order to maintain a working codebase at each step:

1. **Fix `pyproject.toml`** — add `[build-system]`, run `uv sync`, verify `pip install -e .` works
2. **Remove `requirements.txt`** — all deps now in `pyproject.toml`
3. **Add missing filter types** to `dsp.apply_filter_spec` (`butter_highpass`, `butter_bandpass`)
4. **Promote `best_event_metrics`** to `dsp.py`
5. **Migrate stage6 scripts** to import from `handgrip_analysis` only; verify equivalence
6. **Delete `handgrip_review/`** — run all scripts to confirm no broken imports
7. **Remove `sys.path` hacks** from all scripts — verify after `uv sync` creates proper env
8. **Add `_logging.py`** and wire `setup_logging()` into each script's main
9. **Add `log = logging.getLogger(__name__)` + log calls** to library modules
10. **Migrate `configs/`** to `conf/` and wire Hydra into scripts
11. **Extract magic constants** to `conf/dsp/defaults.yaml` and `conf/analysis/*.yaml`
12. **Fix `run_all.py`** — add stage5/stage6 support, logging
13. **Write unit tests** for promoted/modified functions

> Steps 1–6 address correctness. Steps 7–9 address operability. Steps 10–13 address maintainability.
