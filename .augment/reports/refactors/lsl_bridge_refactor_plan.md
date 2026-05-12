# LSL Bridge Refactor Plan

> *"Good taste in code is the ability to recognize the difference between a solution that merely works and one that is right."*

**Module:** `lsl_bridge` (refactored from `LSL_Bridge/`)
**Audit Date:** 2026-05-06
**Schema Version under audit:** `handgrip_lsl_bridge.v2`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Inventory & Feature Map](#2-system-inventory--feature-map)
3. [Ideal Architecture](#3-ideal-architecture)
4. [Current vs. Ideal: Gap Analysis](#4-current-vs-ideal-gap-analysis)
5. [Technical Debt Register](#5-technical-debt-register)
6. [Refactoring Strategy](#6-refactoring-strategy)
7. [Proposed File Tree (src Layout)](#7-proposed-file-tree-src-layout)
8. [Configuration Migration Map](#8-configuration-migration-map)
9. [Logging Architecture](#9-logging-architecture)
10. [Code Pruning & Deprecation Checklist](#10-code-pruning--deprecation-checklist)
11. [Dependency Specification (pyproject.toml)](#11-dependency-specification-pyprojecttoml)
12. [Migration Execution Checklist](#12-migration-execution-checklist)

---

## 1. Executive Summary

`LSL_Bridge` is a production-grade streaming bridge that publishes two LSL (Lab Streaming Layer) streams from two hardware sources — an Arduino/HX711 handgrip sensor over serial (UART) and an RS485 acquisition board over ZMQ IPC. The core logic is well-reasoned and demonstrates strong instincts around strict protocol parsing, sequence gap detection, device-clock anchoring, and atomic filter state management.

However, the entire codebase lives in a flat two-file layout (`handgrip_lsl_bridge.py`, `filter.py`) with no package isolation, no pyproject.toml, ad-hoc logging that never writes to a file programmatically, and a number of hard-coded "magic" values and legacy protocol aliases that create silent technical debt.

This plan standardizes the module to a `src/` layout, modularizes the God Module, properly wires logging to both console and file via Hydra, and promotes all magic constants to the configuration schema.

**Pillars evaluation:**

| Pillar | Current State | Target State |
|--------|--------------|--------------|
| **Correctness** | ✅ Core logic is sound | Preserve all behaviour; add unit tests for core |
| **Operability** | 🟡 No file logging in code; no version flag; config magic values | File handler via Hydra; constants in config schema |
| **Maintainability** | 🔴 God module (830 lines); flat layout; dead code | Modular `src/` layout; pruned dead code; typed interfaces |

---

## 2. System Inventory & Feature Map

### 2.1 Files Under Audit

| File | Lines | Role |
|------|-------|------|
| `handgrip_lsl_bridge.py` | ~830 | Entry point + ALL application logic |
| `filter.py` | ~250 | Signal processing pipeline |
| `conf/config.yaml` | ~130 | Hydra configuration |
| `handgrip_lsl_bridge.log` | — | Runtime log artifact (not source) |

### 2.2 Feature Inventory

**Data Types / Contracts**

| Class | Location | Purpose |
|-------|----------|---------|
| `FirmwareMetadata` | `handgrip_lsl_bridge.py` | Parsed M2 boot-frame metadata from firmware |
| `ParsedTargetSample` | `handgrip_lsl_bridge.py` | Canonical D2 UART sample |
| `ReferenceSample` | `handgrip_lsl_bridge.py` | Canonical RS485 IPC decoded sample |
| `Processor` (Protocol) | `handgrip_lsl_bridge.py` | Interface contract for filter module |

**LSL Stream Publishers**

| Feature | Location | Description |
|---------|----------|-------------|
| `ComponentEventOutlet` | `handgrip_lsl_bridge.py` | Irregular marker stream for operational events |
| `build_target_outlet()` | `handgrip_lsl_bridge.py` | Constructs 6-channel irregular HandgripTarget LSL outlet |
| `build_reference_outlet()` | `handgrip_lsl_bridge.py` | Constructs 4-channel regular HandgripReference LSL outlet |
| `RS485IpcReferencePublisher` | `handgrip_lsl_bridge.py` | Background ZMQ SUB thread → LSL push |

**Protocol Parsing**

| Feature | Location | Description |
|---------|----------|-------------|
| `D2LineParser.feed()` | `handgrip_lsl_bridge.py` | Strict regex-based D2 data line parser |
| `D2LineParser._parse_metadata()` | `handgrip_lsl_bridge.py` | M2 firmware metadata frame parser |
| `RS485IpcReferencePublisher._decode_record()` | `handgrip_lsl_bridge.py` | JSON IPC schema decoder with legacy alias fallback |

**Timestamp Resolution**

| Feature | Location | Description |
|---------|----------|-------------|
| `SampleTimeResolver` | `handgrip_lsl_bridge.py` | Resolves filter-domain time from LSL or device-clock deltas |
| `TargetTimestampResolver` | `handgrip_lsl_bridge.py` | Maps device clock into LSL domain via anchor policy |

**Signal Processing**

| Feature | Location | Description |
|---------|----------|-------------|
| `FirstOrderLowPass` | `filter.py` | 1-pole RC IIR low-pass filter |
| `SecondOrderBiquadLowPass` | `filter.py` | 2nd-order Butterworth biquad IIR |
| `DriftCorrector` | `filter.py` | Adaptive baseline drift corrector |
| `FilterPipeline` | `filter.py` | Ordered chain of `FilterNode` instances |
| `ProcessorAdapter` | `filter.py` | Hydra-config factory wrapper |
| `build_processor()` | `filter.py` | Public factory for `handgrip_lsl_bridge.py` |

**I/O Sinks**

| Feature | Location | Description |
|---------|----------|-------------|
| `TargetCsvSink` | `handgrip_lsl_bridge.py` | Buffered CSV writer for target samples |
| `ReferenceCsvSink` | `handgrip_lsl_bridge.py` | Buffered CSV writer for reference samples |

**Configuration & Utilities**

| Feature | Location | Description |
|---------|----------|-------------|
| `configure_logging()` | `handgrip_lsl_bridge.py` | Sets root logger level + `basicConfig` formatter |
| `build_target_source_id()` | `handgrip_lsl_bridge.py` | Resolves LSL source_id from USB serial number |
| `find_port_metadata()` | `handgrip_lsl_bridge.py` | Queries `serial.tools.list_ports` for port metadata |
| `settle_serial_input()` | `handgrip_lsl_bridge.py` | Flushes UART input buffer during startup settle |
| `app()` | `handgrip_lsl_bridge.py` | Hydra `@hydra.main` entry point |
| `main()` | `handgrip_lsl_bridge.py` | `sys.exit` wrapper |

---

## 3. Ideal Architecture

For a long-running daemon of this nature, the ideal architecture follows the **Functional Core, Imperative Shell** principle, separating pure protocol logic from I/O side effects and configuration concerns.

```
┌────────────────────────────────────────────────────────────────────┐
│                         IMPERATIVE SHELL                           │
│                                                                    │
│  app.py          publishers/          io/                          │
│  (Hydra entry,   (Serial loop,        (CSV sinks,                  │
│   lifecycle)     ZMQ subscriber)      LSL outlets)                 │
│                                                                    │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │                     FUNCTIONAL CORE                        │   │
│   │                                                            │   │
│   │  core/parser.py         core/filter.py                    │   │
│   │  (D2/M2 parsing,        (Biquad/RC filters,               │   │
│   │   pure regex→dataclass)  pure float→float)                │   │
│   │                                                            │   │
│   │  core/timestamping.py   types.py                          │   │
│   │  (Anchor resolution,    (Frozen dataclasses:              │   │
│   │   pure state machine)    contracts between layers)        │   │
│   └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  conf/                  logging_setup.py                           │
│  (Hydra schemas,        (Console + file handlers,                  │
│   structured config)    configured from Hydra)                     │
└────────────────────────────────────────────────────────────────────┘
```

**Key design principles applied:**

1. **Configuration as a first-class citizen** — All numeric constants and string literals currently embedded in code promoted to `conf/config.yaml` with schema documentation.
2. **Structured logging** — `logging.getLogger(__name__)` throughout, `configure_logging()` wires both a `StreamHandler` (console) and a `FileHandler` (`.log` file) from Hydra config.
3. **Modular package** — Each concern lives in its own module; no module exceeds ~200 lines.
4. **Stable public API** — `app()` entry point and `__main__.py` keep full CLI compatibility.
5. **Testable pure core** — Parser, filters, and timestamp resolvers have zero I/O dependencies and can be tested without mocking.

---

## 4. Current vs. Ideal: Gap Analysis

### 4.1 Structural Layout

| Dimension | Current | Ideal |
|-----------|---------|-------|
| Package layout | Flat — two `.py` files at project root | `src/lsl_bridge/` with modular subpackages |
| Import safety | `python handgrip_lsl_bridge.py` works from anywhere (CWD pollution) | `python -m lsl_bridge` requires `pip install -e .` |
| Packaging metadata | None — no `pyproject.toml` | PEP 621 compliant `pyproject.toml` with `hatchling` |
| Dependency locking | None | `uv` managed `uv.lock` |
| Testability | Cannot `import` modules without side effects | Each module independently importable |

### 4.2 Configuration

| Dimension | Current | Ideal |
|-----------|---------|-------|
| Magic values in code | 12+ literal constants scattered (see §5) | All promoted to `conf/config.yaml` |
| Config validation | None — config errors surface as `AttributeError` at runtime | Hydra structured config with `@dataclass` schema |
| Log file path | Not configurable — not even wired in code | `conf/config.yaml`: `logging.file: ./lsl_bridge.log` |

### 4.3 Observability / Logging

| Dimension | Current | Ideal |
|-----------|---------|-------|
| File logging | **Not implemented in code** — `.log` artifact likely produced by shell redirect | `FileHandler` wired in `configure_logging()` |
| Log format | Hard-coded `[%(asctime)s][%(name)s][%(levelname)s] - %(message)s` | Format string in config |
| Logger names | ✅ `logging.getLogger(__name__)` already used | Preserve as-is |
| Per-module levels | Not supported | Via `logging.level` override dict in config |

### 4.4 Modularity

| Current Module Responsibility | Lines | Ideal Split |
|-------------------------------|-------|-------------|
| Data contracts + I/O + parsing + timestamping + LSL outlets + main loop | ~830 | 5–6 focused modules of ~100–150 lines each |
| All filter logic | ~250 | Preserved as `core/filter.py` (already well-structured) |

---

## 5. Technical Debt Register

### 🔴 Critical

**TD-01: No `pyproject.toml` — undeclared dependencies**
- Risk: Silent breakage when any dependency upgrades; no reproducible install
- Fix: Add `pyproject.toml` (see §11)

**TD-02: File logging not wired in code**
- The `.log` file is present as a runtime artifact but `configure_logging()` only calls `logging.basicConfig()` with a `StreamHandler`. No `FileHandler` is ever attached.
- Risk: Log loss in headless deployments; operators believe logging is persisted when it isn't
- Fix: Wire `FileHandler` in `configure_logging()`, controlled by `logging.file` config key

**TD-03: Flat layout — no `src/` directory**
- Risk: Accidental import of project-root files; tests pass locally but fail in CI/CD after packaging
- Fix: Migrate to `src/lsl_bridge/` layout (see §7)

### 🟡 Significant

**TD-04: God Module — `handgrip_lsl_bridge.py` (830 lines)**
- 8+ distinct concerns in one file: data types, LSL outlet construction, serial I/O, ZMQ threading, CSV sinks, timestamping, logging setup, Hydra entry point
- Fix: Split into modules as per §7

**TD-05: Hard-coded magic values in source**

| Location | Magic Value | Proposed Config Key |
|----------|-------------|---------------------|
| `build_target_outlet()` | `chunk_size=1` | `streams.target.chunk_size` |
| `build_reference_outlet()` | `chunk_size=1` | `streams.reference.chunk_size` |
| `build_target_outlet()` | `6` (channel count) | Derived from `len(cfg.streams.target.channels)` |
| `build_reference_outlet()` | `4` (channel count) | Derived from `len(cfg.streams.reference.channels)` |
| `_decode_record()` | `"rs485.measurement.v1"` | `rs485_ipc.expected_schema` |
| `configure_logging()` | Format string literal | `logging.format` |
| `RS485IpcReferencePublisher._run()` | `time.sleep(0.001)` | `rs485_ipc.poll_interval_s` |
| `RS485IpcReferencePublisher._run()` | `time.sleep(0.05)` | `rs485_ipc.error_backoff_s` |
| `RS485IpcReferencePublisher._run()` | Malformed log every `100` | `rs485_ipc.log_malformed_every_n` |
| `ComponentEventOutlet.__init__()` | `"handgrip_component_event.v1"` | `component_events.schema` |
| `build_target_outlet()` | `"handgrip_target_stream.v2"` | `streams.target.schema` |
| `build_reference_outlet()` | `"handgrip_reference_stream.v2"` | `streams.reference.schema` |

**TD-06: `except Exception:` over-broad catch in `RS485IpcReferencePublisher._run()`**
```python
# Current — catches everything including programmer errors
except Exception as exc:
    LOGGER.warning("Reference IPC receive warning: %s", exc)
    time.sleep(0.05)
```
- Should narrow to `zmq.ZMQError` for transport errors; let `RuntimeError`/`AttributeError` propagate
- Fix: Replace with `except zmq.ZMQError as exc:`

**TD-07: `except Exception:` in optional ZMQ import guard**
```python
try:
    import zmq
except Exception:  # should be ImportError
    zmq = None
```
- Fix: Narrow to `except ImportError:`

### 🟢 Minor / Nice-to-Have

**TD-08: `configure_logging` called inside Hydra `app()` after Hydra has already initialized logging**
- Hydra installs its own log interceptors at startup. Calling `logging.basicConfig()` after `@hydra.main` decorates the function may be a no-op or produce double-formatted log lines
- Fix: Move logging setup to a Hydra `logging` config group (see §9)

**TD-09: `_append_metadata()` silently drops `None` values without documentation**
- Minor — the silencing is intentional but undocumented
- Fix: Add inline comment

---

## 6. Refactoring Strategy

### Step 1 — Scaffold the `src` layout

Create the directory tree from §7. Move `filter.py` → `src/lsl_bridge/core/filter.py`. Add `__init__.py` files.

### Step 2 — Extract pure types

Create `src/lsl_bridge/types.py` with `FirmwareMetadata`, `ParsedTargetSample`, `ReferenceSample`, and the `Processor` Protocol. These have zero external dependencies beyond stdlib `dataclasses`.

### Step 3 — Extract core modules (pure / near-pure)

Move with no logic changes:
- `D2LineParser` → `src/lsl_bridge/core/parser.py`
- `SampleTimeResolver`, `TargetTimestampResolver` → `src/lsl_bridge/core/timestamping.py`

These modules only need `types.py` and `omegaconf`. They are the testable pure core.

### Step 4 — Extract I/O modules

Move with no logic changes:
- `TargetCsvSink`, `ReferenceCsvSink` → `src/lsl_bridge/io/csv_sinks.py`
- `build_target_outlet()`, `build_reference_outlet()`, `_append_channel()`, `_append_metadata()`, `build_target_source_id()`, `find_port_metadata()` → `src/lsl_bridge/io/lsl_outlets.py`
- `settle_serial_input()` → `src/lsl_bridge/io/serial_utils.py`
- `build_processor()` (the `importlib` dispatch) → `src/lsl_bridge/core/processing.py`

### Step 5 — Extract publishers

- `ComponentEventOutlet` → `src/lsl_bridge/publishers/events.py`
- `RS485IpcReferencePublisher` → `src/lsl_bridge/publishers/reference.py`

At this step, fix **TD-06** (narrow `except Exception` → `except zmq.ZMQError`) and wire the `poll_interval_s` and `error_backoff_s` constants from config.

### Step 6 — Wire logging to file

Rewrite `configure_logging()` → `src/lsl_bridge/logging_setup.py`. Add a `FileHandler`. Promote log format string to config (see §9).

### Step 7 — Promote magic constants

Update `conf/config.yaml` with all new keys from TD-05 table. Update all call sites to read from `cfg`.

Channel counts in `build_target_outlet` and `build_reference_outlet` should be derived dynamically:
```python
n_channels = len(cfg.streams.target.channels)  # replaces hardcoded 6
```

### Step 8 — Update entry points

Create `src/lsl_bridge/__main__.py` and `src/lsl_bridge/app.py`. The `@hydra.main` decorator moves to `app.py`. `__main__.py` calls `main()`.

Keep `conf/` at the project root (not inside `src/`). Hydra's `config_path` in `@hydra.main` updates to `../../conf` relative to `app.py`.

### Step 9 — Prune dead code (see §10)

### Step 10 — Add `pyproject.toml` and wire `uv`

---

## 7. Proposed File Tree (src Layout)

```
lsl_bridge/                             ← project root (renamed from LSL_Bridge/)
├── pyproject.toml                      ← PEP 621 metadata, hatchling build, uv
├── README.md
├── uv.lock                             ← generated by `uv lock`
├── .python-version                     ← pinned Python version for uv
├── conf/
│   ├── config.yaml                     ← primary Hydra config (updated, see §8)
│   └── logging/
│       ├── default.yaml                ← INFO level, file + console handlers
│       └── debug.yaml                  ← DEBUG level, verbose format
├── src/
│   └── lsl_bridge/
│       ├── __init__.py                 ← version export: __version__ = "2.0.0"
│       ├── __main__.py                 ← `python -m lsl_bridge` entry point
│       ├── app.py                      ← @hydra.main app(), main(), lifecycle
│       ├── types.py                    ← FirmwareMetadata, ParsedTargetSample,
│       │                                  ReferenceSample, Processor Protocol
│       ├── logging_setup.py            ← configure_logging(): console + file handlers
│       ├── core/
│       │   ├── __init__.py
│       │   ├── filter.py               ← moved from root; no logic changes
│       │   ├── parser.py               ← D2LineParser (extracted from god module)
│       │   ├── timestamping.py         ← SampleTimeResolver, TargetTimestampResolver
│       │   └── processing.py           ← build_processor() importlib dispatch
│       ├── io/
│       │   ├── __init__.py
│       │   ├── csv_sinks.py            ← TargetCsvSink, ReferenceCsvSink
│       │   ├── lsl_outlets.py          ← build_target_outlet, build_reference_outlet,
│       │   │                              build_target_source_id, helpers
│       │   └── serial_utils.py         ← settle_serial_input, find_port_metadata
│       └── publishers/
│           ├── __init__.py
│           ├── events.py               ← ComponentEventOutlet
│           └── reference.py            ← RS485IpcReferencePublisher
└── tests/
    ├── unit/
    │   ├── test_filter.py              ← FirstOrderLowPass, SecondOrderBiquadLowPass
    │   ├── test_parser.py              ← D2LineParser with synthetic UART lines
    │   └── test_timestamping.py        ← SampleTimeResolver, TargetTimestampResolver
    └── integration/
        └── test_csv_sinks.py           ← TargetCsvSink/ReferenceCsvSink with tmp_path
```

**Why this split:**

| Module | Testability | Dependency boundary |
|--------|-------------|---------------------|
| `core/filter.py` | Unit-testable, zero I/O | stdlib + math only |
| `core/parser.py` | Unit-testable (mock events outlet) | `types.py`, `omegaconf` |
| `core/timestamping.py` | Unit-testable (no I/O) | `types.py`, `omegaconf` |
| `io/csv_sinks.py` | Integration-testable (`tmp_path`) | stdlib, `types.py` |
| `io/lsl_outlets.py` | Requires LSL runtime; skip in CI | `pylsl`, `types.py` |
| `publishers/reference.py` | Requires ZMQ runtime; skip in CI | `zmq`, `pylsl` |
| `app.py` | E2E only | All of the above |

---

## 8. Configuration Migration Map

### 8.1 New Keys to Add to `conf/config.yaml`

```yaml
# --- NEW SECTION: logging file handler ---
logging:
  level: INFO
  file: ./lsl_bridge.log          # NEW: path for FileHandler (null = console-only)
  format: "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"  # NEW: promoted from code
  log_every_n_samples: 200
  log_parse_errors_every_n: 20

# --- NEW KEYS in rs485_ipc ---
rs485_ipc:
  # ... existing keys ...
  expected_schema: rs485.measurement.v1    # NEW: was hardcoded in _decode_record
  poll_interval_s: 0.001                   # NEW: was hardcoded sleep in _run()
  error_backoff_s: 0.05                    # NEW: was hardcoded sleep on ZMQError
  log_malformed_every_n: 100               # NEW: was hardcoded in malformed counter

# --- NEW KEYS in streams.target ---
streams:
  target:
    # ... existing keys ...
    chunk_size: 1                          # NEW: was hardcoded in StreamOutlet
    schema: handgrip_target_stream.v2      # NEW: was hardcoded string literal

  reference:
    # ... existing keys ...
    chunk_size: 1                          # NEW: was hardcoded in StreamOutlet
    schema: handgrip_reference_stream.v2  # NEW: was hardcoded string literal

# --- NEW KEY in component_events ---
component_events:
  # ... existing keys ...
  schema: handgrip_component_event.v1     # NEW: was hardcoded string literal
```

### 8.2 Keys with Changed Semantics (Non-Breaking)

| Key | Current | After Refactor | Notes |
|-----|---------|----------------|-------|
| `streams.target` channel count | Hardcoded `6` in `build_target_outlet` | `len(cfg.streams.target.channels)` | Derived dynamically |
| `streams.reference` channel count | Hardcoded `4` in `build_reference_outlet` | `len(cfg.streams.reference.channels)` | Derived dynamically |

### 8.3 Hydra Logging Group (Optional Enhancement)

Adding a `conf/logging/` group allows switching verbosity without editing the primary config:

```bash
# Run with debug logging:
python -m lsl_bridge logging=debug

# Default INFO level:
python -m lsl_bridge
```

`conf/logging/default.yaml`:
```yaml
# @package _global_
logging:
  level: INFO
  file: ./lsl_bridge.log
  format: "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
```

`conf/logging/debug.yaml`:
```yaml
# @package _global_
logging:
  level: DEBUG
  file: ./lsl_bridge_debug.log
  format: "[%(asctime)s][%(name)s][%(levelname)s][%(funcName)s:%(lineno)d] - %(message)s"
```

---

## 9. Logging Architecture

### Current State (Broken File Logging)

```python
def configure_logging(level_name: str) -> None:
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.basicConfig(level=level, format="[%(asctime)s][%(name)s][%(levelname)s] - %(message)s")
    # ❌ No FileHandler — .log file must be a shell redirect artifact
```

### Target State

```python
# src/lsl_bridge/logging_setup.py

import logging
import sys
from pathlib import Path
from omegaconf import DictConfig

def configure_logging(cfg: DictConfig) -> None:
    """Wire console + optional file logging from Hydra config.
    
    All loggers in the lsl_bridge.* hierarchy inherit this configuration.
    Both handlers receive the same level and format for consistency.
    """
    level_name = str(cfg.logging.level).upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = str(cfg.logging.format)
    formatter = logging.Formatter(fmt)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)

    # File handler (optional — null disables)
    log_file = cfg.logging.get("file")
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
```

The call site in `app.py` changes from:
```python
configure_logging(str(cfg.logging.level))   # old
```
to:
```python
configure_logging(cfg)                       # new — passes full config
```

---

## 10. Code Pruning & Deprecation Checklist

### 10.1 Legacy Protocol Aliases — Mark for Removal

**Location:** `RS485IpcReferencePublisher._decode_record()` in `handgrip_lsl_bridge.py`

The method contains field-name fallback aliases that were present in older RS485 IPC schema versions:

```python
# These are legacy fallback aliases — candidates for removal
force = record.get("reference_force_N", record.get("rs485_raw"))   # rs485_raw = legacy
clock = record.get("reference_clock_s", record.get("rs485_clock")) # rs485_clock = legacy
status_raw = record.get("reference_status", record.get("status_word", 0))  # status_word = legacy
clock_source = record.get("rs485_clock_source", record.get("clock_source", "unknown"))
```

**Action:** If `rs485.measurement.v1` is the only schema version in active use (as enforced by the `expected_schema` config check), these secondary `.get()` fallbacks are dead code. **Remove** them and rely solely on the canonical field names. If cross-version compatibility must be preserved, document it explicitly rather than silently accepting both forms.

**Checklist:**
- [ ] Confirm with RS485_GUI team that `rs485_raw`, `rs485_clock`, `status_word` keys are no longer emitted
- [ ] Remove fallback aliases from `_decode_record()`
- [ ] Add schema version assertion at message receipt (not just check): `assert record["schema"] == cfg.rs485_ipc.expected_schema`

### 10.2 Unused Filter Types — Evaluate for Removal

**Location:** `filter.py`

| Class | Referenced in `conf/config.yaml`? | Active in production? | Action |
|-------|-----------------------------------|-----------------------|--------|
| `SecondOrderBiquadLowPass` | ✅ Yes (`butterworth_lowpass_2nd`) | Yes | **Keep** |
| `FirstOrderLowPass` | ❌ No (`lowpass_1pole` type not in config) | Unknown | **Investigate** |
| `DriftCorrector` | ❌ No (`drift_corrector` type not in config) | Unknown | **Investigate** |
| `IdentityProcessor` | ❌ No (used as fallback internally) | Fallback only | **Keep** (defensive) |

**Recommendation:**
- `FirstOrderLowPass` and `DriftCorrector` are fully implemented, well-tested-by-construction, and may be used in other configurations or downstream tools. **Do not remove** without confirming they are never exercised.
- Mark both with a `# NOTE: Not used in default config — retained for optional filter chains` comment.
- Add unit tests for both in `tests/unit/test_filter.py` to prevent silent bitrot.

**Checklist:**
- [ ] Search codebase for any other `config.yaml` files using `lowpass_1pole` or `drift_corrector`
- [ ] If no usages found after broader search: deprecate with a `# deprecated` comment and a `DeprecationWarning` in `_build_filter_node()`
- [ ] Add unit tests for `FirstOrderLowPass` and `DriftCorrector` regardless

### 10.3 Over-Defensive Error Handling

**Location:** `RS485IpcReferencePublisher._run()` in `handgrip_lsl_bridge.py`

```python
# Current — overly broad
except Exception as exc:
    LOGGER.warning("Reference IPC receive warning: %s", exc)
    time.sleep(0.05)
```

ZMQ's own error model is well-defined. `zmq.ZMQError` covers transport-level failures. Catching `Exception` here swallows programmer errors (e.g., `AttributeError` on a bad attribute access in `_decode_record`) that should propagate and crash loudly.

**Action:**
```python
# After refactor — precise
except zmq.ZMQError as exc:
    LOGGER.warning("Reference IPC transport error: %s", exc)
    time.sleep(float(cfg.rs485_ipc.error_backoff_s))
```

**Checklist:**
- [ ] Replace `except Exception` with `except zmq.ZMQError` in `_run()`
- [ ] Replace `except Exception` with `except ImportError` in ZMQ optional-import guard

### 10.4 Dead Code in `handgrip_lsl_bridge.py` — Stale After Modularisation

After the God Module is split, the following helpers in `handgrip_lsl_bridge.py` become redundant (they move to dedicated modules):

| Function / Class | Moves To | Remove from original |
|-----------------|----------|----------------------|
| `_append_channel()` | `io/lsl_outlets.py` | ✅ |
| `_append_metadata()` | `io/lsl_outlets.py` | ✅ |
| `_open_target_sink()` | `io/csv_sinks.py` (or inline `app.py`) | ✅ |
| `_open_reference_sink()` | `io/csv_sinks.py` (or inline `app.py`) | ✅ |
| `configure_logging()` | `logging_setup.py` | ✅ |
| `find_port_metadata()` | `io/serial_utils.py` | ✅ |
| `settle_serial_input()` | `io/serial_utils.py` | ✅ |

**Checklist:**
- [ ] Verify no external scripts import directly from `handgrip_lsl_bridge` by function name
- [ ] Remove above from `handgrip_lsl_bridge.py` after moves are confirmed working

---

## 11. Dependency Specification (pyproject.toml)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lsl-bridge"
version = "2.0.0"
description = "LSL bridge for Handgrip system: publishes HandgripTarget and HandgripReference streams"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "hydra-core>=1.3",
    "omegaconf>=2.3",
    "pylsl>=1.16",
    "pyserial>=3.5",
    "pyzmq>=25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
lsl-bridge = "lsl_bridge.app:main"

[tool.hatch.build.targets.wheel]
packages = ["src/lsl_bridge"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=lsl_bridge --cov-report=term-missing"
```

**Development workflow with `uv`:**
```bash
# Create venv and install
uv venv
uv pip install -e ".[dev]"

# Run the bridge
python -m lsl_bridge

# Or via entry point
lsl-bridge

# Run tests
uv run pytest tests/
```

---

## 12. Migration Execution Checklist

### Pre-Migration
- [ ] Verify `handgrip_lsl_bridge.log` is currently produced only by shell redirection (not a `FileHandler`)
- [ ] Confirm RS485 IPC schema version in use: `rs485.measurement.v1` only, or are older versions still active?
- [ ] Confirm whether `FirstOrderLowPass` and `DriftCorrector` are exercised in any other config files
- [ ] Tag the current flat-layout state in version control before any changes

### Structural Migration
- [ ] Create `src/lsl_bridge/` directory tree as per §7
- [ ] Create all `__init__.py` stubs
- [ ] Move `filter.py` → `src/lsl_bridge/core/filter.py`; update logger name `"handgrip_lsl_bridge.filter"` → `__name__`
- [ ] Create `types.py` with extracted dataclasses; confirm all field types preserved exactly
- [ ] Extract `D2LineParser` → `core/parser.py`; run smoke test against existing `.log` replay
- [ ] Extract timestamping classes → `core/timestamping.py`
- [ ] Extract CSV sinks → `io/csv_sinks.py`; test with `tmp_path` fixture
- [ ] Extract LSL outlet builders → `io/lsl_outlets.py`
- [ ] Extract serial utilities → `io/serial_utils.py`
- [ ] Extract `ComponentEventOutlet` → `publishers/events.py`
- [ ] Extract `RS485IpcReferencePublisher` → `publishers/reference.py`
- [ ] Create `app.py` with `@hydra.main` app and `main()`; update `config_path`
- [ ] Create `__main__.py`

### Configuration
- [ ] Add all new keys from §8.1 to `conf/config.yaml`
- [ ] Create `conf/logging/default.yaml` and `conf/logging/debug.yaml`
- [ ] Dynamically derive channel counts from `len(cfg.streams.*.channels)`
- [ ] Promote all magic literal strings and sleep constants

### Logging
- [ ] Implement `configure_logging(cfg)` in `logging_setup.py` with `FileHandler`
- [ ] Update call site in `app.py`
- [ ] Verify `.log` file is created in the working directory on first run
- [ ] Verify console output is identical to current

### Code Pruning
- [ ] Narrow `except Exception` → `except zmq.ZMQError` in `reference.py`
- [ ] Narrow `except Exception` → `except ImportError` in ZMQ import guard
- [ ] After RS485 schema confirmation: remove legacy field aliases from `_decode_record()`
- [ ] Add `# NOTE: Not used in default config` comments to `FirstOrderLowPass`, `DriftCorrector`

### Testing
- [ ] Write `tests/unit/test_filter.py` — cover `SecondOrderBiquadLowPass`, `FirstOrderLowPass`, `DriftCorrector`, gap reset behaviour
- [ ] Write `tests/unit/test_parser.py` — cover D2 nominal parse, M2 metadata parse, malformed line rejection, sequence gap detection
- [ ] Write `tests/unit/test_timestamping.py` — cover `host_receive` policy, `device_clock_anchor` policy, nonmonotonic reset, gap reset
- [ ] Write `tests/integration/test_csv_sinks.py` — cover target and reference CSV round-trip with `tmp_path`

### Packaging
- [ ] Create `pyproject.toml` as per §11
- [ ] Run `uv lock` to generate `uv.lock`
- [ ] Run `uv pip install -e ".[dev]"` and confirm `lsl-bridge --help` works
- [ ] Confirm `python -m lsl_bridge` is equivalent

### Validation
- [ ] Run bridge against live hardware for one full session; confirm `.log` file is produced at the configured path
- [ ] Confirm LSL stream metadata is unchanged (schema strings, channel labels, types, units)
- [ ] Confirm CSV output schema is unchanged (field names, order, precision)
- [ ] Confirm Hydra override syntax still works: `python -m lsl_bridge serial.port=/dev/ttyUSB0`
- [ ] Confirm `logging=debug` Hydra group override switches to debug format

---

*"Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away."*
— Antoine de Saint-Exupéry
