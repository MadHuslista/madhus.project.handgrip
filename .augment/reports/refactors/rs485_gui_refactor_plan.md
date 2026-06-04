# RS485_GUI Refactor Plan

> *"Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away."*
> — Antoine de Saint-Exupéry

**Author:** Senior Architecture Review  
**Module:** `RS485_GUI` → `rs485_gui`  
**Source:** `acquisition_board_gui.py` (2,927 lines) + `config.yaml` + `pyproject.toml`  
**Objective:** Migrate to `src-layout`, structured Hydra config, hierarchical logging, and a modular, testable package architecture while preserving 100% feature and API compatibility.

---

## Table of Contents

1. [System Inventory](#1-system-inventory)
2. [Ideal Architecture](#2-ideal-architecture)
3. [Current vs. Ideal Contrast](#3-current-vs-ideal-contrast)
4. [Technical Debt Register](#4-technical-debt-register)
5. [Refactoring Strategy](#5-refactoring-strategy)
   - 5.1 [Structural Layout (src-layout)](#51-structural-layout-src-layout)
   - 5.2 [Dependency Management (pyproject.toml + uv)](#52-dependency-management-pyprojecttoml--uv)
   - 5.3 [Configuration (Hydra + OmegaConf)](#53-configuration-hydra--omegaconf)
   - 5.4 [Observability (Hierarchical Logging)](#54-observability-hierarchical-logging)
   - 5.5 [Feature Completeness Contract](#55-feature-completeness-contract)
6. [Code Pruning & Deprecation Checklist](#6-code-pruning--deprecation-checklist)
7. [Migration Map: Config Keys](#7-migration-map-config-keys)
8. [Module Responsibility Map](#8-module-responsibility-map)
9. [Implementation Phasing](#9-implementation-phasing)

---

## 1. System Inventory

### 1.1 Features

The single file `acquisition_board_gui.py` implements the following distinct subsystems:

| Feature Area | Description | Lines (approx.) |
|---|---|---|
| **Protocol constants** | `BAUD_CODE_TO_VALUE`, `STATUS_FLAGS`, `COMMANDS`, `UNIT_CODE_TO_LABEL`, etc. | 45–135 |
| **Data models** | `MeasurementFrame`, `SerialSettings`, `PortInfo`, `ActiveSendStats`, `SamplingStats` | 155–290 |
| **Utility functions** | `truncate_text`, `lsl_local_clock`, `build_log_text`, `format_rate`, `downsample_points_for_render` | 290–620 |
| **Signal definitions** | `SIGNAL_DEFINITIONS` dict, `get_plot_signal_key`, `extract_signal_value` | 340–475 |
| **IPC publisher** | `MeasurementFramePublisher` — ZeroMQ PUB socket, topic encoding, sequence numbering | 680–870 |
| **File logger** | `SignalFileLogger` — raw NDJSON, interpreted NDJSON, GUI CSV, event log | 865–985 |
| **App state** | `AppState` — central mutable state, frame buffer, display throttling, log queues | 985–1130 |
| **Port discovery** | `enumerate_ports`, `filter_excluded_ports` | 1130–1175 |
| **Modbus RTU codec** | `crc16_modbus`, `MinimalModbusRTU`, `decode_modbus_measurement`, `combine_s32_from_words` | 1175–1380 |
| **Legacy ASCII parsers** | `parse_active_send_frame` — `line_ascii_float/csv/hex_s32/auto` profiles | 1379–1515 |
| **Transport layer** | `BoardTransport` (base), `ModbusBoardTransport`, `ActiveSendBoardTransport` | 1512–2175 |
| **Active-send binary parser** | `_extract_modbus_response_frames`, resync/recovery, timestamp reconstruction | 1740–2060 |
| **Worker thread** | `acquisition_worker` — poll/push loop, rate limiting, IPC/log dispatch | 2175–2250 |
| **UI helpers** | `build_plot_figure`, `build_signal_metadata_text`, `build_board_profile_snapshot` | 2250–2310 |
| **Logging setup** | `configure_logging` — dual handler (stream + file) | 2298–2328 |
| **App entry point** | `load_app_config`, `run_app`, `main` — config loading, NiceGUI wiring, UI timer | 2330–2927 |

### 1.2 External Dependencies

| Library | Role | Optional? |
|---|---|---|
| `nicegui` | Web UI framework | No |
| `plotly` | Live signal chart | No |
| `pyserial` | RS485/serial I/O | No |
| `omegaconf` (via `hydra-core`) | Configuration merging | No |
| `pyzmq` | ZeroMQ IPC publisher | Yes (when `ipc.enabled=false`) |
| `pylsl` | LSL local clock for timestamp accuracy | Yes (warned if absent when IPC enabled) |
| `numpy` | Vectorised downsampling acceleration | Yes (pure-Python fallback exists) |

---

## 2. Ideal Architecture

The target architecture separates the monolith into six well-defined layers, following the **Functional Core, Imperative Shell** pattern:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        IMPERATIVE SHELL                             │
│  ui/  ·  io/  ·  transport/  ·  worker.py  ·  app.py               │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    FUNCTIONAL CORE                          │   │
│   │  core/codec.py  ·  core/ports.py  ·  models.py             │   │
│   │  constants.py   ·  core/signals.py                         │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Configuration boundary:  config/ → rs485_gui/config.py (schema)   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 Proposed File Tree

```
RS485_GUI/
├── pyproject.toml                        # PEP 621 + hatchling + uv
├── README.md
├── .python-version                       # unchanged (3.11)
├── config/
│   └── config.yaml                       # moved from project root
├── logs/
│   └── .gitignore                        # unchanged
├── src/
│   └── rs485_gui/
│       ├── __init__.py                   # version re-export
│       ├── __main__.py                   # `python -m rs485_gui` entry
│       ├── app.py                        # run_app(), load_app_config()
│       ├── constants.py                  # protocol enums/maps (pure data)
│       ├── models.py                     # frozen dataclasses (MeasurementFrame etc.)
│       ├── state.py                      # AppState, mutable runtime state
│       ├── worker.py                     # acquisition_worker thread
│       ├── config/
│       │   ├── __init__.py
│       │   ├── schema.py                 # Hydra structured config dataclasses
│       │   └── loader.py                 # load_app_config(), configure_logging()
│       ├── core/
│       │   ├── __init__.py
│       │   ├── codec.py                  # crc16, register decode, Modbus frame math
│       │   ├── signals.py                # signal key helpers, SIGNAL_DEFINITIONS
│       │   ├── sampling.py               # SamplingStats, downsample_points_for_render
│       │   └── ports.py                  # enumerate_ports, filter_excluded_ports
│       ├── transport/
│       │   ├── __init__.py
│       │   ├── base.py                   # BoardTransport ABC (Protocol)
│       │   ├── modbus.py                 # MinimalModbusRTU + ModbusBoardTransport
│       │   └── active_send.py            # ActiveSendBoardTransport
│       ├── io/
│       │   ├── __init__.py
│       │   ├── logger.py                 # SignalFileLogger (file I/O)
│       │   └── publisher.py              # MeasurementFramePublisher (ZMQ)
│       └── ui/
│           ├── __init__.py
│           ├── layout.py                 # NiceGUI page builder (connection panel, logs)
│           ├── plots.py                  # build_plot_figure, render downsampling
│           └── refresh.py               # refresh_ui timer callback
└── tests/
    ├── unit/
    │   ├── test_codec.py                 # crc16, register decode, CRC mismatch
    │   ├── test_signals.py               # extract_signal_value, get_plot_signal_key
    │   ├── test_sampling.py              # SamplingStats, outlier rejection
    │   └── test_models.py               # MeasurementFrame construction
    ├── integration/
    │   ├── test_active_send_parser.py    # binary frame extraction, recovery
    │   └── test_file_logger.py           # SignalFileLogger open/write/close
    └── e2e/
        └── test_cli.py                   # `python -m rs485_gui --help`
```

---

## 3. Current vs. Ideal Contrast

| Dimension | Current State | Target State |
|---|---|---|
| **Layout** | Flat: single `.py` at project root | `src/rs485_gui/` with proper isolation |
| **Testability** | Cannot unit-test codec without importing all of NiceGUI | Pure `core/codec.py` is zero-dependency |
| **Separation of concerns** | UI wiring, business logic, I/O, protocol in one 2927-line file | Six layers, each independently importable |
| **Config loading** | `OmegaConf.load()` inline in `load_app_config()` | `config/loader.py` with Hydra structured schema |
| **Config schema** | Implicit (YAML-only, no typed schema) | Typed `dataclass`-based Hydra structured config |
| **Magic values** | Constants scattered at module top (`COMMAND_REGISTER = 11`) | All in `constants.py`; device-tunable ones in config schema |
| **Logging setup** | `configure_logging()` called twice (lines 2512 & 2521) | Called once in `load_app_config()`, scoped per-module |
| **Build system** | `pyproject.toml` has no build backend | `hatchling` build backend, `uv` workflow |
| **Installability** | Not installable as a package | `pip install -e .` → `python -m rs485_gui` |
| **Dead code** | `parse_active_send_frame()` is unreachable (300+ lines) | Removed (see §6) |
| **Config mutation** | `cfg.device.slave_address = int(...)` in UI handlers — mutates OmegaConf | UI state separated from config; runtime overrides in `AppState` |

---

## 4. Technical Debt Register

### 4.1 Structural Debt

**D-001 · Flat layout / non-installable package** (Severity: HIGH)

`acquisition_board_gui.py` sits at the project root with no `src/` boundary. This means:
- `import rs485_gui` resolves to the project directory, not the installed package
- Tests would run against unpackaged source
- CI environments cannot reliably reproduce local imports

**D-002 · God Module** (Severity: HIGH)

2,927 lines in a single file with six distinct semantic layers. Any change to the UI timer risks touching the Modbus codec. Untestable without a running NiceGUI instance.

**D-003 · Missing build backend in pyproject.toml** (Severity: MEDIUM)

Current `pyproject.toml`:
```toml
[project]
name = "rs485-gui"
version = "0.1.0"
```
No `[build-system]` table — the package cannot be built or installed.

**D-004 · `configure_logging()` called twice** (Severity: LOW)

`load_app_config()` calls it at line 2512; `run_app()` calls it again at line 2521. The second call re-clears and re-adds handlers. In production this is harmless but produces duplicate handlers in testing.

### 4.2 Configuration Debt

**D-005 · Implicit config schema** (Severity: MEDIUM)

Config is valid only by convention. Misspelling `serial.default_baudrate` silently uses no value. A Hydra structured config dataclass raises `MissingMandatoryValue` at startup.

**D-006 · Protocol constants not in config** (Severity: LOW)

`COMMAND_REGISTER = 11`, `READ_START_REGISTER = 0`, `READ_REGISTER_COUNT = 11` are hardcoded. These map directly to device registers that differ between board firmware revisions. They should be either in `constants.py` with clear docstrings, or promoted to `device:` config keys.

**D-007 · Config mutation in UI callbacks** (Severity: MEDIUM)

UI handlers directly mutate `DictConfig`:
```python
# Line 2648 — side-effectful mutation inside a closure
cfg.device.slave_address = int(address_input.value)
cfg.ui.plot_signal_key = str(signal_select.value)
```
This couples the UI layer to the config object and makes the runtime state invisible to the logger or IPC publisher unless they re-read config on every frame.

**Recommendation:** Introduce a small `RuntimeSettings` dataclass in `AppState` to hold the UI-writable subset. Config becomes read-only after `load_app_config()`.

### 4.3 Defensive Programming Debt

**D-008 · Pervasive `getattr(cfg.xxx, 'yyy', default)` guards** (Severity: LOW)

Over 40 occurrences of patterns like:
```python
float(getattr(cfg.active_send, 'delivery_window_s', 0.05))
```
These exist because the config schema was not enforced at load time. With a typed Hydra structured config, all keys are guaranteed to exist. The `getattr` guards become dead code and can be replaced with direct attribute access:
```python
cfg.active_send.delivery_window_s
```
**Exception:** The three optional-import guards (`numpy`, `zmq`, `pylsl`) are correct and must be retained.

**D-009 · Overlapping exception handling in transport cleanup** (Severity: LOW)

`connect_state()` and `disconnect_state()` both wrap `transport.disconnect()` in broad `except Exception` blocks that call `push_event()`. While defensive, this hides the distinction between "expected teardown noise" and "genuine resource leak." After the refactor, cleanup errors should be logged at `WARNING` level with the exception chain preserved:
```python
LOGGER.warning("Transport cleanup error", exc_info=True)
```
This is not an over-defensiveness removal — it is a signal quality improvement.

---

## 5. Refactoring Strategy

### 5.1 Structural Layout (src-layout)

**Step 1:** Create the directory skeleton.

```bash
mkdir -p RS485_GUI/src/rs485_gui/{core,transport,io,ui,config}
touch RS485_GUI/src/rs485_gui/__init__.py
touch RS485_GUI/src/rs485_gui/__main__.py
```

**Step 2:** Move `config.yaml` to `RS485_GUI/config/config.yaml`. The loader must resolve this relative to `__file__`:

```python
# config/loader.py
from pathlib import Path
_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
```

> **NiceGUI re-execution caveat (preserved):** The existing `load_app_config()` correctly avoids `@hydra.main` because NiceGUI re-executes the script to serve the root page. This custom loader pattern **must be preserved**. The Hydra structured config (§5.3) is used purely for schema validation, not for the global Hydra runtime.

**Step 3:** Split the monolith file-by-file using the module map in §8. No logic changes at this stage — only moves.

**Step 4:** Verify no circular imports exist by checking the dependency graph:

```
models.py           ← no internal imports
constants.py        ← no internal imports
core/codec.py       ← imports: models, constants
core/signals.py     ← imports: models
core/sampling.py    ← no internal imports
core/ports.py       ← imports: models
transport/base.py   ← imports: models
transport/modbus.py ← imports: models, constants, core/codec
transport/active_send.py ← imports: models, constants, core/codec, state
io/logger.py        ← imports: models, core/signals
io/publisher.py     ← imports: models, core/signals
state.py            ← imports: models, io/logger, io/publisher, core/signals
worker.py           ← imports: state, transport/base
ui/plots.py         ← imports: state, core/signals
ui/refresh.py       ← imports: state, ui/plots
ui/layout.py        ← imports: state, ui/refresh, constants, core/ports
config/schema.py    ← no internal imports
config/loader.py    ← imports: config/schema
app.py              ← imports: everything
```

No cycles. The functional core (models, constants, core/) has zero dependencies on UI or I/O layers.

---

### 5.2 Dependency Management (pyproject.toml + uv)

Replace the minimal `pyproject.toml` with a fully specified PEP 621 manifest:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "rs485-gui"
version = "0.1.0"
description = "High-speed RS485 acquisition board GUI with ZeroMQ IPC and LSL bridge integration"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "hydra-core>=1.3",       # OmegaConf + structured config
    "nicegui>=1.4",          # Web UI
    "plotly>=5.0",           # Live signal chart
    "pyserial>=3.5",         # RS485/UART
    "pyzmq>=25.0",           # ZeroMQ IPC publisher
    "pylsl>=1.16",           # LSL local clock
]

[project.optional-dependencies]
# numpy acceleration for downsampling — safe to omit, pure-Python fallback is present
fast = ["numpy>=1.24"]
dev = [
    "pytest>=7.4",
    "pytest-cov>=4.0",
    "ruff>=0.4",
]

[project.scripts]
rs485-gui = "rs485_gui.app:main"

[tool.hatch.build.targets.wheel]
packages = ["src/rs485_gui"]

[tool.hatch.build.targets.sdist]
include = [
    "src/",
    "config/",
    "pyproject.toml",
    "README.md",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

**Development workflow with `uv`:**

```bash
# Install all dependencies (including optional numpy)
uv sync --extra fast --extra dev

# Run the app
uv run python -m rs485_gui

# Or via entry point
uv run rs485-gui

# Run tests
uv run pytest tests/

# Lint
uv run ruff check src/
```

> **Why `hatchling` over `setuptools`?** Hatchling has no implicit source discovery surprises — it packages exactly `src/rs485_gui/`. The `config/` directory is included in the sdist but is **not** part of the wheel (runtime config is user-owned, not package-owned).

---

### 5.3 Configuration (Hydra + OmegaConf)

#### The NiceGUI Re-execution Constraint

The existing code documents this correctly:

> *"NiceGUI internally re-executes the script to serve the root page / 404 fallback. Using the `@hydra.main` decorator here causes a second GlobalHydra initialization and crashes the app."*

**Decision: retain the custom loader.** `@hydra.main` is NOT used. Instead, Hydra's structured config system (`dataclasses` + `MISSING`) is used purely for schema definition and validation at load time. The global Hydra runtime is never initialised.

#### Structured Config Schema (`config/schema.py`)

Replace implicit YAML-only config with typed dataclasses. This eliminates all `getattr(cfg.xxx, 'yyy', default)` guards (D-008).

```python
# src/rs485_gui/config/schema.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from omegaconf import MISSING


@dataclass
class SessionConfig:
    session_id: Optional[str] = None


@dataclass
class AppConfig:
    log_level: str = "INFO"
    worker_join_timeout_s: float = 1.5


@dataclass
class UiConfig:
    page_title: str = "High-Speed Acquisition Instrument GUI"
    host: str = "127.0.0.1"
    port: int = 8088
    refresh_interval_s: float = 0.1
    plot_height_px: int = 360
    log_height_px: int = 380
    event_log_height_px: int = 180
    visible_log_entries: int = 40
    visible_event_entries: int = 120
    max_retained_log_entries: int = 160
    max_retained_event_entries: int = 500
    max_plot_points: int = 3000
    max_render_plot_points: int = 700
    default_plot_signal_key: str = "net_value"
    plot_signal_key: str = "net_value"
    clear_plot_on_connect: bool = True
    sampling_rate_window_samples: int = 5000
    sampling_rate_outlier_low_ratio: float = 0.25
    sampling_rate_outlier_high_ratio: float = 4.0
    sampling_rate_outlier_min_samples: int = 16
    max_signal_samples_per_second: float = 0.0
    display_max_samples_per_second: float = 30.0
    active_send_render_downsample_factor: int = 2
    modbus_rtu_render_downsample_factor: int = 1
    max_ui_entry_chars: int = 300
    max_log_textarea_chars: int = 30000
    max_event_textarea_chars: int = 20000
    plot_update_every_n_refreshes: int = 1
    log_update_every_n_refreshes: int = 5
    sampling_update_every_n_refreshes: int = 5
    metadata_update_every_n_refreshes: int = 10
    board_config_update_every_n_refreshes: int = 10
    controls_update_every_n_refreshes: int = 10
    plot_skip_if_unchanged: bool = True
    plot_trace_type: str = "scattergl"
    light_mode: bool = True


@dataclass
class LoggerConfig:
    enabled: bool = True
    directory: str = "./logs"
    write_mode: str = "overwrite"
    raw_signal_filename: str = "raw_signal.ndjson"
    interpreted_signal_filename: str = "interpreted_signal.ndjson"
    gui_signal_filename: str = "gui_signal.csv"
    debug_log_to_file: bool = True
    debug_log_filename: str = "acquisition_debug.log"
    event_log_filename: str = "event.log"
    flush_every_n_batches: int = 25
    flush_interval_s: float = 1.0


@dataclass
class IpcConfig:
    enabled: bool = True
    transport: str = "zmq_pub"
    bind: str = "tcp://127.0.0.1:5557"
    topic: str = "rs485.measurement.v1"
    event_topic: str = "rs485.event.v1"
    signal_key: str = "net_value"
    send_hwm: int = 2000
    linger_ms: int = 0
    drop_on_backpressure: bool = True
    start_on_app_launch: bool = False
    start_on_connect: bool = True
    stop_on_disconnect: bool = True
    require_pylsl_clock: bool = True
    publish_after_max_rate_filter: bool = False
    log_every_s: float = 5.0


@dataclass
class SerialConfig:
    default_port: str = ""
    excluded_ports: List[str] = field(default_factory=list)
    default_baudrate: int = 460800
    default_parity: str = "N"
    default_stopbits: int = 1
    bytesize: int = 8
    timeout_s: float = 0.2
    inter_frame_gap_s: float = 0.001
    port_hints: List[str] = field(default_factory=lambda: [
        "USB", "RS485", "FTDI", "CH340", "CP210", "PL2303", "ttyUSB", "ttyACM"
    ])


@dataclass
class DeviceConfig:
    mode: str = "active_send"
    slave_address: int = 1
    active_send_frequency_code: int = 8
    poll_interval_s: float = 0.001
    error_backoff_s: float = 0.25


@dataclass
class ActiveSendConfig:
    timestamp_policy: str = "batch_end_anchored"
    default_parser_profile: str = "modbus_rtu_response_11regs"
    default_numeric_index: int = 0
    default_hex_word_endianness: str = "big"
    read_timeout_s: float = 0.5
    delivery_window_s: float = 0.010
    max_frames_per_delivery: int = 16
    read_chunk_bytes: int = 1024
    max_read_bytes_per_cycle: int = 8192
    clock_reanchor_max_drift_s: float = 0.050
    recovery_enabled: bool = True
    recovery_warning_threshold: int = 48
    recovery_min_interval_s: float = 1.0
    recovery_reset_input_buffer: bool = True
    max_binary_frame_bytes: int = 64
    max_buffer_bytes: int = 8192
    frame_slave_id: int = 1
    frame_function_code: int = 3
    frame_register_count: int = 11
    log_first_n_good_frames: int = 5
    log_summary_every_n_good_frames: int = 250
    log_bad_frame_hex_bytes: int = 64
    warning_emit_interval_s: float = 5.0
    detailed_warning_limit: int = 2


@dataclass
class Rs485GuiConfig:
    """Root structured config for rs485_gui.
    
    Used for schema validation only. The Hydra global runtime is NOT
    initialised (NiceGUI re-executes the module; @hydra.main would
    crash on the second execution with a GlobalHydra conflict).
    """
    session: SessionConfig = field(default_factory=SessionConfig)
    app: AppConfig = field(default_factory=AppConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    logger: LoggerConfig = field(default_factory=LoggerConfig)
    ipc: IpcConfig = field(default_factory=IpcConfig)
    serial: SerialConfig = field(default_factory=SerialConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    active_send: ActiveSendConfig = field(default_factory=ActiveSendConfig)
```

#### Config Loader (`config/loader.py`)

```python
# src/rs485_gui/config/loader.py
import logging
import sys
from pathlib import Path
from typing import List, Optional

from omegaconf import DictConfig, OmegaConf

LOGGER = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"


def load_app_config(argv: Optional[List[str]] = None) -> DictConfig:
    """Load config.yaml and apply OmegaConf dotlist overrides from CLI args.
    
    Does NOT use @hydra.main to avoid GlobalHydra re-initialisation conflicts
    when NiceGUI re-executes this script during page serving.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    cfg = OmegaConf.load(_CONFIG_PATH)

    overrides, ignored = [], []
    for arg in args:
        if arg in {'-h', '--help'}:
            _print_help()
            raise SystemExit(0)
        if arg.startswith('hydra.') or not ('=' in arg and not arg.startswith('--')):
            ignored.append(arg)
        else:
            overrides.append(arg)

    if overrides:
        cfg = OmegaConf.merge(cfg, OmegaConf.from_dotlist(overrides))

    # One-time logging setup — NOT called again in run_app()
    configure_logging(cfg)

    if ignored:
        LOGGER.warning("Ignoring unsupported CLI args: %s", ignored)

    return cfg


def configure_logging(cfg: DictConfig) -> None:
    """Configure root logger with stream + optional file handler.
    
    Called exactly once from load_app_config(). Idempotent via handler check.
    """
    import logging
    level = getattr(logging, str(cfg.app.log_level).upper(), logging.INFO)
    root = logging.getLogger()
    
    # Idempotency guard — NiceGUI may call this path again on page re-serve
    if root.handlers:
        return
        
    root.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if cfg.logger.debug_log_to_file:
        log_dir = Path(cfg.logger.directory).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)
        file_mode = "a" if cfg.logger.write_mode == "append" else "w"
        file_handler = logging.FileHandler(
            log_dir / cfg.logger.debug_log_filename,
            mode=file_mode,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
```

> **Key change from current code:** `configure_logging()` now guards against re-entry via `if root.handlers: return`. This removes the duplicate-call issue (D-004) without changing external behaviour.

#### Hydra/OmegaConf Conflict Avoidance

`hydra-core` imports `omegaconf` as a dependency. The only risk of conflict is if `hydra.main` decorator initialises the global Hydra singleton. Since the loader uses only `OmegaConf.load()` and `OmegaConf.merge()`, no Hydra singleton is initialised. `config/schema.py` uses plain `dataclasses` — no `@dataclass` decorator from Hydra's `hydra.core.config_store` is used, which would trigger registration.

---

### 5.4 Observability (Hierarchical Logging)

#### Module-scoped Loggers

Every module gets its own logger. This allows per-module log level control via Hydra config:

```python
# transport/active_send.py
import logging
LOGGER = logging.getLogger(__name__)
# → 'rs485_gui.transport.active_send'

# io/publisher.py
LOGGER = logging.getLogger(__name__)
# → 'rs485_gui.io.publisher'
```

#### Log Level Configuration via Hydra

Add a `logging` key to `config/config.yaml`:

```yaml
# config/config.yaml  (new section)
logging:
  root_level: INFO
  module_levels:
    rs485_gui.transport.active_send: DEBUG   # verbose parser diagnostics
    rs485_gui.io.publisher: WARNING           # suppress routine IPC stats
    rs485_gui.core.codec: INFO
```

Loader reads this during `configure_logging()`:

```python
# After setting root level:
module_levels = OmegaConf.to_container(
    getattr(cfg, 'logging', {}).get('module_levels', {}), 
    resolve=True
) or {}
for module_name, level_str in module_levels.items():
    lvl = getattr(logging, str(level_str).upper(), logging.INFO)
    logging.getLogger(module_name).setLevel(lvl)
```

#### File + Console Mirroring (already implemented, to be preserved)

The existing dual-handler pattern (stream to stdout + `FileHandler` to `logs/acquisition_debug.log`) is correct and must be preserved. The refactor only moves it into `config/loader.py` and makes it idempotent.

---

### 5.5 Feature Completeness Contract

Every feature listed in §1.1 must remain functional after the refactor. The table below maps each feature to its target module and notes any intentional changes:

| Feature | Target Module | Change |
|---|---|---|
| Modbus RTU codec | `core/codec.py` | None — pure function extraction |
| Active-send binary parser | `transport/active_send.py` | None — class move |
| Timestamp reconstruction | `transport/active_send.py` | None |
| ZMQ IPC publisher | `io/publisher.py` | None — class move |
| File logger (NDJSON/CSV/event) | `io/logger.py` | None — class move |
| Port discovery + exclusion | `core/ports.py` | None — function move |
| Signal definitions / metadata | `core/signals.py` | None — dict + function move |
| Sampling rate statistics | `core/sampling.py` | None — class move |
| App state | `state.py` | UI-mutable fields moved to `RuntimeSettings` inside `AppState` (D-007 fix) |
| NiceGUI UI / page builder | `ui/layout.py` | None — function move |
| Plotly live chart | `ui/plots.py` | None — function move |
| UI refresh timer | `ui/refresh.py` | None — function move |
| CLI config loading | `config/loader.py` | `configure_logging` called once, idempotent guard added |
| `python -m rs485_gui` entry | `__main__.py` | Thin wrapper: `from rs485_gui.app import main; main()` |

**CLI compatibility:** The dotlist override interface (`python acquisition_board_gui.py ui.port=8090 serial.default_port=/dev/ttyUSB0`) is preserved verbatim via the same `OmegaConf.from_dotlist()` path. The entry point name changes from `python acquisition_board_gui.py` to `python -m rs485_gui` or `rs485-gui`, but the override syntax is identical.

---

## 6. Code Pruning & Deprecation Checklist

### 6.1 Dead Code — Remove

- [ ] **`parse_active_send_frame()` (lines 1379–1514)** — REMOVE

  This function implements the `line_ascii_float`, `line_ascii_csv`, `hex_s32`, and `line_ascii_auto` parser profiles. It is **unreachable** at runtime:

  - `ActiveSendBoardTransport.read_frames()` (line 1995) processes only `modbus_rtu_response_11regs` via `_read_modbus_response_frames_batch()`; all other profiles fall through to `read_once()`
  - `ActiveSendBoardTransport.read_once()` (line 2131) raises `RuntimeError` for any profile other than `modbus_rtu_response_11regs`
  - `parse_active_send_frame()` has zero call sites in the execution path

  The UI parser selector still shows `line_ascii_auto`, `line_ascii_float`, `line_ascii_csv`, `hex_s32` as options. These UI options should also be removed or reduced to just the supported profile:

  ```python
  # Before (ui/layout.py parser_select):
  options={
      'modbus_rtu_response_11regs': 'modbus_rtu_response_11regs',
      'line_ascii_auto': 'line_ascii_auto',     # ← remove
      'line_ascii_float': 'line_ascii_float',   # ← remove
      'line_ascii_csv': 'line_ascii_csv',       # ← remove
      'hex_s32': 'hex_s32',                     # ← remove
  }

  # After:
  options={'modbus_rtu_response_11regs': 'Modbus RTU Response (11 registers)'}
  ```

- [ ] **`BoardTransport` base class `read_once()` and `read_frames()` with implicit `raise NotImplementedError`** — REPLACE with ABC

  ```python
  # Before: silently returns [self.read_once()] and raises NotImplementedError
  class BoardTransport:
      def read_once(self) -> MeasurementFrame:
          raise NotImplementedError
      def read_frames(self) -> List[MeasurementFrame]:
          return [self.read_once()]

  # After: explicit abstract base
  from abc import ABC, abstractmethod

  class BoardTransport(ABC):
      @abstractmethod
      def connect(self) -> None: ...
      @abstractmethod
      def disconnect(self) -> None: ...
      @abstractmethod
      def read_frames(self) -> List[MeasurementFrame]: ...
      @abstractmethod
      def send_command(self, command_name: str) -> None: ...
  ```

- [ ] **`SIGNAL_DEFINITIONS` alias entries** (lines 361–395) — EVALUATE

  `gross_raw`, `net_raw`, `peak_raw` are documented as aliases of `gross_raw_value`, `net_raw_value`, `peak_raw_value`. These aliases exist in `interpreted` dicts (set in `decode_modbus_measurement`) and in `SIGNAL_DEFINITIONS`. If no downstream subscriber uses these short alias keys, remove them from `SIGNAL_DEFINITIONS` to reduce the signal selector dropdown noise. The short-form keys in `interpreted` dicts can remain for backward compatibility with existing IPC consumers.

- [ ] **`get_plot_signal_label()` fallback to `cfg.ui.plot_signal_label`** (line 456)

  The config has no `plot_signal_label` key. This `getattr` guard is dead. Remove it with the D-008 cleanup.

### 6.2 Legacy Compatibility — Remove

- [ ] **Legacy ASCII/hex profile options in the UI parser selector** (see above)

- [ ] **`continuous_rate` timestamp policy path** (lines 2076–2117)

  The code comment explicitly labels this as "Legacy behavior: useful only if the RS485 device is proven to emit at exactly configured_frequency_hz." The default is `batch_end_anchored`. Evaluate whether `continuous_rate` is still exercised in any deployment. If not, remove it and simplify the timestamp reconstruction to the single `batch_end_anchored` + `host_receive` pair. This removes ~40 lines of branching in the critical acquisition path.

  > **Conservative recommendation:** Retain `continuous_rate` in the first refactor pass but mark it `# DEPRECATED: remove in next major version`. The branching cost is low and the production risk of a silent removal is high.

### 6.3 Over-defensive Error Handling — Simplify

- [ ] **`getattr(cfg.xxx, 'yyy', default)` guards (D-008)** — Remove all ~40 instances

  After the Hydra structured schema is in place, all config keys are guaranteed to exist with their default values. Replace:
  ```python
  float(getattr(cfg.active_send, 'delivery_window_s', 0.05))
  ```
  With:
  ```python
  cfg.active_send.delivery_window_s
  ```
  The three optional-import `try/except` blocks (`numpy`, `zmq`, `pylsl`) are NOT in scope for this cleanup and must be retained.

- [ ] **Double `configure_logging()` call** (D-004)

  Remove the call from `run_app()` (line 2521). The call in `load_app_config()` suffices. The idempotency guard added in §5.3 makes this safe.

- [ ] **`build_board_profile_snapshot()` getattr guards** (lines 655–677)

  This function uses `getattr` for every field because it is called before config validation. After the schema is in place, replace with direct attribute access.

- [ ] **`ACQ_GUI_CONFIG_LOGGED_ONCE` environment variable guard** (lines 2522–2524)

  This env-var guard was added to suppress config re-logging on NiceGUI re-execution. With the idempotent `configure_logging()` and the guard moved inside `load_app_config()`, this env-var trick is no longer necessary. Remove it.

### 6.4 Deprecation Summary Table

| Symbol | Location | Action | Reason |
|---|---|---|---|
| `parse_active_send_frame()` | codec section | **Remove** | Unreachable (D-001 dead code) |
| `line_ascii_*` / `hex_s32` UI options | UI parser select | **Remove** | Unreachable profiles |
| `BoardTransport` implicit raise | transport base | **Replace with ABC** | Latent `NotImplementedError` |
| `getattr(cfg.xxx, ...)` guards | ~40 locations | **Remove** | Redundant after schema |
| `configure_logging()` in `run_app()` | `app.py` | **Remove** | Double-call (D-004) |
| `ACQ_GUI_CONFIG_LOGGED_ONCE` env var | `app.py` | **Remove** | Superseded by idempotent guard |
| `continuous_rate` timestamp policy | `transport/active_send.py` | **Deprecate** (Phase 2 remove) | Legacy path, comment-documented |
| `gross_raw` / `net_raw` / `peak_raw` in `SIGNAL_DEFINITIONS` | `core/signals.py` | **Evaluate** | UI-only aliases; `interpreted` dict aliases retained |

---

## 7. Migration Map: Config Keys

The `config.yaml` structure is **unchanged**. All existing keys remain in the same paths. The migration adds one new top-level section:

| Config Path | Status | Notes |
|---|---|---|
| `session.*` | Unchanged | |
| `app.*` | Unchanged | |
| `ui.*` | Unchanged | `plot_signal_label` key removed (was never in YAML, only in dead `getattr`) |
| `logger.*` | Unchanged | |
| `ipc.*` | Unchanged | |
| `serial.*` | Unchanged | |
| `device.*` | Unchanged | |
| `active_send.*` | Unchanged | |
| `hydra.*` | Unchanged | Kept for backward CLI compatibility (silently ignored by loader) |
| `logging.root_level` | **NEW** | Replaces `app.log_level` (backward-compatible; `app.log_level` kept as alias) |
| `logging.module_levels` | **NEW** | Per-module log level overrides |

### Magic Values Promoted to Config

The following are currently hardcoded in Python. They should be promoted to the `device:` config section to support multi-register-set firmware variants:

```yaml
# config/config.yaml  (additions to device: section)
device:
  # ...existing keys...
  read_start_register: 0        # Modbus address 0x0000 / PLC 40001
  read_register_count: 11       # number of holding registers to read
  command_register: 11          # 0x000B / PLC 40012
```

This allows the GUI to work with boards that use different register maps without code changes.

---

## 8. Module Responsibility Map

| Module | Single Responsibility | Key Exports |
|---|---|---|
| `constants.py` | Protocol-level lookup tables and register addresses | `BAUD_CODE_TO_VALUE`, `COMMANDS`, `STATUS_FLAGS`, `UNIT_CODE_TO_LABEL`, `DECIMAL_CODE_TO_DIGITS`, `ACTIVE_SEND_FREQ_CODE_TO_VALUE`, `PARITY_CODE_TO_VALUE`, `COMMAND_METADATA` |
| `models.py` | Frozen/mutable data transfer objects | `MeasurementFrame`, `SerialSettings`, `PortInfo`, `ActiveSendStats` |
| `core/codec.py` | Pure Modbus/RS485 byte-level codec | `crc16_modbus`, `combine_s32_from_words`, `decode_status_word`, `apply_decimal`, `decode_modbus_measurement`, `extract_registers_from_modbus_response`, `decode_active_send_modbus_response` |
| `core/signals.py` | Signal key resolution and metadata | `SIGNAL_DEFINITIONS`, `get_plot_signal_key`, `extract_signal_value`, `get_plot_signal_options` |
| `core/sampling.py` | Thread-safe sampling rate statistics | `SamplingStats`, `downsample_points_for_render` |
| `core/ports.py` | Serial port enumeration and filtering | `enumerate_ports`, `filter_excluded_ports`, `get_excluded_serial_ports`, `is_serial_port_excluded` |
| `transport/base.py` | Transport interface contract | `BoardTransport` (ABC) |
| `transport/modbus.py` | Modbus RTU polling transport | `MinimalModbusRTU`, `ModbusBoardTransport`, `ModbusError` |
| `transport/active_send.py` | Binary push-frame transport | `ActiveSendBoardTransport` |
| `io/logger.py` | Batch file I/O for acquisition data | `SignalFileLogger` |
| `io/publisher.py` | ZeroMQ frame publication | `MeasurementFramePublisher` |
| `state.py` | Central mutable runtime state | `AppState`, `RuntimeSettings` |
| `worker.py` | Acquisition loop thread | `acquisition_worker` |
| `ui/layout.py` | NiceGUI page construction | `run_ui_page` |
| `ui/plots.py` | Plotly figure construction | `build_plot_figure` |
| `ui/refresh.py` | UI timer callback | `build_refresh_callback` |
| `config/schema.py` | Hydra structured config schema | `Rs485GuiConfig` |
| `config/loader.py` | Config load, merge, and logging setup | `load_app_config`, `configure_logging` |
| `app.py` | Application wiring — connects all layers | `run_app`, `main` |
| `__main__.py` | CLI entry point | delegates to `app.main` |

---

## 9. Implementation Phasing

Break the refactor into three independent phases. Each phase leaves the application fully functional.

### Phase 1 — Structural (Low Risk)

Goal: Achieve `src-layout`, installability, and build system. Zero logic changes.

- [ ] Create `src/rs485_gui/` directory structure
- [ ] Move `config.yaml` to `config/config.yaml`
- [ ] Split `acquisition_board_gui.py` into the target modules by cut-and-paste (no refactoring of internals)
- [ ] Update `pyproject.toml` with `hatchling` build system
- [ ] Add `__main__.py` entry
- [ ] Verify `uv run python -m rs485_gui` starts the application
- [ ] Verify `uv run pytest tests/` passes (stub tests for importability)

### Phase 2 — Configuration & Observability (Medium Risk)

Goal: Typed schema, single-call logging, remove magic `getattr` guards.

- [ ] Implement `config/schema.py` dataclasses
- [ ] Implement `config/loader.py` with idempotent `configure_logging()`
- [ ] Remove duplicate `configure_logging()` call from `run_app()`
- [ ] Remove `ACQ_GUI_CONFIG_LOGGED_ONCE` env-var guard
- [ ] Replace all `getattr(cfg.xxx, 'yyy', default)` with direct attribute access
- [ ] Add `logging.module_levels` section to `config.yaml`
- [ ] Add scoped `LOGGER = logging.getLogger(__name__)` to each module
- [ ] Promote `READ_START_REGISTER`, `READ_REGISTER_COUNT`, `COMMAND_REGISTER` to `device:` config
- [ ] Add unit tests for `configure_logging()` idempotency

### Phase 3 — Pruning & Hardening (Low Risk, High Confidence)

Goal: Remove confirmed dead code, harden transport base class.

- [ ] Remove `parse_active_send_frame()` and its unreachable profile branches
- [ ] Remove legacy parser options from UI parser selector
- [ ] Replace `BoardTransport` with ABC
- [ ] Separate `RuntimeSettings` from `AppState` for UI-mutable fields (D-007)
- [ ] Evaluate and prune `SIGNAL_DEFINITIONS` aliases
- [ ] Mark `continuous_rate` timestamp policy as deprecated
- [ ] Add unit tests for `core/codec.py` (CRC, register decode, CRC mismatch detection)
- [ ] Add unit tests for `core/sampling.py` (outlier rejection, thread safety)
- [ ] Add integration tests for `io/logger.py` (open/write/close cycle)

---

*End of refactor plan. Total estimated effort: ~3 engineering days across the three phases, with Phase 1 achievable in a single focused session.*
