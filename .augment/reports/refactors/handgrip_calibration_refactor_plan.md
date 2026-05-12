# Handgrip Calibration — Architecture Refactor Plan

> *"Good taste in code is the ability to recognize the difference between a solution that merely works and one that is right."*

**Document version:** 1.0  
**Target package:** `handgrip-calibration` v0.1.0  
**Evaluated against:** Three-Pillar CLI Design Framework (Correctness · Operability · Maintainability)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Inventory](#2-system-inventory)
3. [Current Architecture Evaluation](#3-current-architecture-evaluation)
4. [Ideal Architecture Design](#4-ideal-architecture-design)
5. [Gap Analysis & Technical Debt Register](#5-gap-analysis--technical-debt-register)
6. [Refactoring Strategy](#6-refactoring-strategy)
   - 6.1 Structural Layout Migration (`src/`)
   - 6.2 Dependency Management (`pyproject.toml` with `uv` + `hatchling`)
   - 6.3 Configuration Management (Hydra Structured Configs)
   - 6.4 Observability (Hierarchical Logging)
   - 6.5 Code Pruning & Dead Code Removal
7. [Proposed File Tree](#7-proposed-file-tree)
8. [Configuration Migration Mapping](#8-configuration-migration-mapping)
9. [Deprecation & Pruning Checklist](#9-deprecation--pruning-checklist)

---

## 1. Executive Summary

The `handgrip_calibration` package demonstrates **strong domain logic** and **solid correctness foundations**: validated frozen dataclasses, a clean Validate→Plan→Execute pipeline, functional core/imperative shell separation in the fitting engine, and a thoughtful marker/event schema. These are genuine senior-engineering instincts that must be preserved through the refactor.

However, three structural issues prevent the package from reaching production-grade quality:

| Pillar | Current State | Target State |
|--------|--------------|--------------|
| **Correctness** | ✅ Strong domain logic, validated configs | ✅ Preserve all features |
| **Operability** | ⚠️ `print()` everywhere, no log files, no `--dry-run`, no `--yes` | ✅ Hierarchical logging, file handler, automation flags |
| **Maintainability** | ❌ Flat layout, raw dict escape hatch, un-schematized sub-configs, `setuptools` | ✅ `src/` layout, Hydra structured configs, `hatchling` + `uv` |

The refactor touches **structure, packaging, config loading, and observability** only. All existing CLI endpoints, domain algorithms, and test contracts are preserved.

---

## 2. System Inventory

### 2.1 CLI Endpoints (Entry Point: `handgrip-cal`)

| Subcommand | Module | Description |
|------------|--------|-------------|
| `validate-config` | `cli.py` | Load and validate a YAML config |
| `preflight` | `cli.py` → `lsl_io.py` | Resolve configured LSL streams |
| `record` | `cli.py` → `recorder.py` | Run live recording protocol |
| `segment` | `cli.py` → `segmentation.py` | Segment accepted holds → `calibration_dataset.csv` |
| `fit` | `cli.py` → `fitting.py` | Fit candidate models, select deployment model |
| `validate-holdout` | `cli.py` → `validation.py` | Validate holdout session against existing `fit_result.json` |
| `report` | `cli.py` → `report.py` | Generate Markdown/HTML reports + diagnostic plots |
| `import-xdf` | `cli.py` → `xdf_import.py` | Convert XDF recording to canonical session files |
| `demo-data` | `cli.py` → `synthetic.py` | Generate synthetic session for testing |

### 2.2 Module Inventory

| Module | Role | Layer | LOC |
|--------|------|-------|-----|
| `config_schema.py` | Full config hierarchy — all dataclasses + YAML loading | Config | ~630 |
| `fitting.py` | All candidate model fitters + model selection + CV | Functional Core | ~710 |
| `report.py` | Report generation + plot generation | Imperative Shell | ~440 |
| `recorder.py` | Live session orchestration — all protocol types | Imperative Shell | ~310 |
| `segmentation.py` | Offline hold segmentation → calibration dataset | Functional Core + I/O | ~200 |
| `protocol_analysis.py` | Post-hoc summaries (creep, dynamic, hysteresis) | Analysis | ~190 |
| `lsl_io.py` | LSL stream discovery, `CsvStreamRecorder` thread | Imperative Shell | ~170 |
| `session.py` | Session-directory and manifest management | Imperative Shell | ~150 |
| `markers.py` | Marker events, LSL outlet, NDJSON logger | Imperative Shell | ~115 |
| `quality.py` | `RateMonitor`, window quality, gap detection | Functional Core | ~110 |
| `validation.py` | Holdout validation (no refit) | Functional Core + I/O | ~105 |
| `xdf_import.py` | XDF → canonical CSV/NDJSON conversion | Imperative Shell | ~100 |
| `export.py` | JSON/NDJSON file helpers | Utility | ~55 |
| `synthetic.py` | Demo session generator | Test Support | ~90 |
| `protocol.py` | Static trial generation from protocol config | Functional Core | ~45 |
| `cli.py` | Argument parsing, subcommand dispatch | Imperative Shell | ~130 |

### 2.3 Configuration Files

| File | Protocol Type | Notes |
|------|--------------|-------|
| `conf/default.yaml` | `static_staircase` | Primary config; maps both streams |
| `conf/template.yaml` | `static_staircase` | Multi-candidate channel maps for forward-compat |
| `conf/protocol_static_staircase.yaml` | `static_staircase` | Same as default, explicit `type` field |
| `conf/protocol_static_reversible_staircase_v3.yaml` | `static_staircase` | Reversible staircase variant |
| `conf/protocol_low_force_refinement.yaml` | `low_force_refinement` | Low-force ladder |
| `conf/protocol_creep_zero_return.yaml` | `creep_zero_return` | Creep/drift characterization |
| `conf/protocol_dynamic_validation.yaml` | `dynamic_validation` | Ramps + squeeze stress tests |
| `conf/protocol_holdout_verification.yaml` | `holdout_verification` | Independent model validation |
| `conf/protocol_reference_verification.yaml` | `reference_verification` | Reference path verification |
| `conf/protocol_fast_smoke_test.yaml` | `static_staircase` | Reduced protocol for CI/smoke testing |

### 2.4 Test Suite

| Test File | What It Tests | Type |
|-----------|--------------|------|
| `test_fitting_affine.py` | End-to-end fit on synthetic session; checks `force_N_a/b` recovery | Integration |
| `test_marker_schema.py` | `MarkerEvent` → JSON round-trip | Unit |
| `test_quality_rules.py` | `compute_window_quality`, `detect_sequence_gaps` | Unit |
| `test_segmentation.py` | Full segmentation on synthetic session; checks row count | Integration |

---

## 3. Current Architecture Evaluation

### 3.1 ✅ What the Package Gets Right

These patterns show genuine architectural taste and **must be preserved unchanged**:

**Validated Frozen Dataclasses as Config**  
`config_schema.py` already implements the Configuration-as-First-Class-Citizen pattern: immutable `@dataclass(frozen=True)` with `__post_init__` or `validate()` methods that fail fast. This is exactly the right pattern. The Hydra migration strengthens it — it does not replace it.

**Functional Core / Imperative Shell in `fitting.py`**  
`compute_shard_plan` style separation is present: `_FitData`, `_ModelSpec`, and the `_fit_*` functions are pure. `execute_plan`-style I/O lives in `fit_session()`. The planner is unit-testable with no mocking.

**Validate → Plan → Execute in `segmentation.py`**  
Events are indexed and accepted holds are identified before any window data is extracted. No interleaving.

**Typed Exception Hierarchy**  
`ConfigError`, `SegmentationError`, `LSLUnavailableError`, `XDFImportError` follow the Structured Error Hierarchy pattern correctly.

**Explicit Side Effect Interfaces (partial)**  
`CsvStreamRecorder` delegates filesystem ops through well-defined methods. LSL and pyxdf are lazy-imported so offline analysis works without hardware dependencies.

**Idempotent Session Structure**  
Session directories are deterministically named. Re-running `segment` or `fit` overwrites the same output files. Re-running `record` creates a new session ID. This is the correct split.

**Protocol-Agnostic Marker Schema**  
`MarkerEvent` is protocol-agnostic JSON. The segmenter only reads event names and timestamps. This decoupling enables the full protocol campaign without changing the offline pipeline.

---

### 3.2 ❌ Critical Issues

#### Issue #1: Flat Package Layout (Violates Import Safety)

```
Handgrip_Calibration/
├── handgrip_calibration/   ← Package at project root
├── tests/
└── pyproject.toml
```

The package lives at the project root. Running `python` from `Handgrip_Calibration/` will silently import from the working directory instead of the installed package. Tests can pass locally against uninstalled source and fail after `pip install`.

**Impact:** CI/CD parity is broken. The test suite in `tests/` currently imports `handgrip_calibration` and is testing the **local editable directory**, not the installed package.

#### Issue #2: No Logging System — `print()` Throughout

The entire recorder, CLI, and quality loop use `print()` for all runtime output. There is no call to `logging.getLogger(__name__)` anywhere in the codebase.

**Impact:**
- No log file is ever written — session provenance is limited to the YAML manifest.
- No way to configure verbosity without modifying source code.
- Console output cannot be filtered (e.g., suppress progress during CI).
- Downstream code consuming this as a library has no hook to capture messages.

#### Issue #3: `AppConfig.raw` — Un-Schematized Escape Hatch

`AppConfig` carries a `raw: dict[str, Any]` field holding the entire raw YAML dict. Two modules depend on it:

```python
# recorder.py — reads un-schematized sub-configs
raw_protocol = self.config.raw.get("protocol", {}) or {}
cfg = raw_protocol.get("creep_zero_return", {}) or {}
force_levels = cfg.get("force_levels_N") or [...]
```

```python
# validation.py — reads un-schematized holdout thresholds
raw = config.raw.get("validation", {}) if isinstance(config.raw, dict) else {}
holdout = raw.get("holdout", {}) if isinstance(raw, dict) else {}
```

**Impact:** These config values bypass all validation. A typo in `conf/protocol_creep_zero_return.yaml` under `protocol.creep_zero_return` will silently fall back to hard-coded defaults, making the YAML appear to work when it is actually being ignored.

#### Issue #4: `setuptools` + Missing `uv` Support

`pyproject.toml` uses `setuptools>=68` as the build backend and does not define dev/optional dependency groups correctly. `pytest` is listed as a runtime dependency alongside `numpy` and `pandas` — this ships the test framework to end users.

#### Issue #5: No `--dry-run` Flag

For a tool that writes session directories, calibration datasets, fit results, and reports, `--dry-run` is non-negotiable. Currently, every command that writes files does so unconditionally.

#### Issue #6: No `--yes` Flag

The `record` command blocks on `input()` prompts (operator confirmation). There is no bypass for CI/automated test scenarios, even though `auto_accept_holds: true` exists in the config. A `--yes` CLI flag is needed to skip the top-level confirmation.

---

### 3.3 ⚠️ Design Improvements

#### Improvement #1: Duplicated `_finite_or_none` Helper

`_finite_or_none()` is copy-pasted identically in both `fitting.py` and `validation.py`. It belongs in `export.py` or a new `_utils.py`.

#### Improvement #2: `__import__("time")` Inline in `fitting.py`

```python
# fitting.py — this is jarring
"host_time_unix": __import__("time").time(),
```

`time` is a stdlib module. It should be imported at the top of the file.

#### Improvement #3: `ProtocolConfig` Does Not Model Creep/Dynamic Sub-Schemas

`conf/protocol_creep_zero_return.yaml` contains:
```yaml
protocol:
  creep_zero_return:
    force_levels_N: [0, 80, 0]
    durations_s: [120, 300, 300]
    read_times_s: [30, 300]
```

None of this is in `ProtocolConfig`. The recorder reads it through `AppConfig.raw`. These need proper dataclasses: `CreepZeroReturnConfig` and `DynamicValidationConfig`.

#### Improvement #4: Missing `py.typed` Declaration in `pyproject.toml`

The `py.typed` marker file exists but `pyproject.toml` uses setuptools package-data discovery to include it. The `hatchling` migration must explicitly re-include it.

#### Improvement #5: `baseline.require_stable` in YAML is Silently Ignored

`conf/default.yaml` has `baseline.require_stable: true`. `ProtocolConfig.from_mapping()` never reads it. This dead config key will confuse operators.

---

## 4. Ideal Architecture Design

### 4.1 Architecture Diagram

```
handgrip-calibration/
│
│  ┌─────────────────────────────────────────────────────┐
│  │               IMPERATIVE SHELL                       │
│  │  cli.py · recorder.py · lsl_io.py · session.py       │
│  │  xdf_import.py · report.py · markers.py · export.py  │
│  │                                                       │
│  │   ┌─────────────────────────────────────────────┐    │
│  │   │           FUNCTIONAL CORE                   │    │
│  │   │  fitting.py · segmentation.py · quality.py  │    │
│  │   │  protocol.py · protocol_analysis.py         │    │
│  │   │  validation.py · synthetic.py               │    │
│  │   └─────────────────────────────────────────────┘    │
│  │                                                       │
│  │  ┌──────────────────────────────────────────────┐    │
│  │  │         CONFIGURATION LAYER                  │    │
│  │  │  config_schema.py (Hydra Structured Configs) │    │
│  │  │  conf/ (Hydra config groups)                 │    │
│  │  └──────────────────────────────────────────────┘    │
│  └─────────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────────┐
│  │              OBSERVABILITY LAYER                     │
│  │  logging.getLogger(__name__) — per module            │
│  │  Configurable level via Hydra: logging.level=DEBUG   │
│  │  Dual handler: stderr console + rotating .log file   │
│  └─────────────────────────────────────────────────────┘
```

### 4.2 Design Decisions

**Hydra Integration Strategy — Compose API, Not `@hydra.main`**

The existing CLI uses `argparse` subcommands. Hydra's `@hydra.main` decorator conflicts with this pattern: it takes over `sys.argv` and does not support positional `subcommand` dispatch.

The correct integration strategy is the **Hydra Compose API** (`hydra.initialize` + `hydra.compose`), which loads Hydra configs programmatically without replacing `argparse`. This lets the CLI keep its subcommand structure while getting config composition, override syntax, and structured config validation.

```python
# ✅ How load_config() becomes Hydra-aware (no @hydra.main conflict)
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

def load_config(path: str | Path) -> AppConfig:
    """Load config using Hydra's compose API for override support."""
    config_dir = Path(path).parent.resolve()
    config_name = Path(path).stem
    with initialize_config_dir(config_dir=str(config_dir), version_base=None):
        cfg = compose(config_name=config_name)
    return AppConfig.from_dict(OmegaConf.to_container(cfg, resolve=True))
```

This approach:
- Keeps the existing `argparse` CLI contract intact
- Enables Hydra override syntax from CLI: `handgrip-cal fit session_dir --config conf/default.yaml fit.operating_range_N=120`
- Adds Hydra config composition and interpolation
- Does not require converting all callers to `@hydra.main`

**Structured Configs as Hydra Config Stores**

The existing frozen dataclasses become Hydra structured configs registered in a `ConfigStore`. This replaces the manual `from_mapping()` constructors with OmegaConf instantiation while keeping the `validate()` methods.

```python
# config_schema.py — add Hydra registration
from hydra.core.config_store import ConfigStore

cs = ConfigStore.instance()
cs.store(name="app_config", node=AppConfig)
cs.store(group="protocol", name="static_staircase", node=ProtocolConfig)
```

---

## 5. Gap Analysis & Technical Debt Register

| # | Area | Severity | Current State | Target State | Effort |
|---|------|----------|--------------|--------------|--------|
| T-01 | Package layout | 🔴 Critical | Flat — `handgrip_calibration/` at root | `src/handgrip_calibration/` | Low |
| T-02 | Logging system | 🔴 Critical | `print()` everywhere, no log files | `logging.getLogger(__name__)` per module, file handler via Hydra | Medium |
| T-03 | `AppConfig.raw` escape hatch | 🔴 Critical | Un-validated `dict[str, Any]` carrying raw YAML | Promote to `CreepConfig` + `DynamicConfig` dataclasses | Medium |
| T-04 | Build system | 🟡 Moderate | `setuptools`, `pytest` in runtime deps | `hatchling`, `uv`, proper dev group | Low |
| T-05 | Config loading | 🟡 Moderate | Manual `yaml.safe_load` + custom parsing | Hydra compose API + structured configs | Medium |
| T-06 | No `--dry-run` | 🟡 Moderate | All write commands execute unconditionally | `--dry-run` flag for `record`, `segment`, `fit`, `report` | Medium |
| T-07 | No `--yes` flag | 🟡 Moderate | `record` blocks on `input()` | `--yes` bypass for CI/automation | Low |
| T-08 | Duplicate `_finite_or_none` | 🟢 Minor | Copy-pasted in `fitting.py` and `validation.py` | Extract to `_utils.py` | Trivial |
| T-09 | `__import__("time")` inline | 🟢 Minor | `fitting.py` line 498 | `import time` at module top | Trivial |
| T-10 | `baseline.require_stable` silently ignored | 🟢 Minor | YAML key exists, never read | Add `baseline_require_stable: bool` to `ProtocolConfig` | Low |
| T-11 | `AffineFitResult` alias | 🟢 Minor | Backward compat alias in `fitting.py` | Deprecate after one cycle | Low |
| T-12 | `run_static_staircase()` wrapper | 🟢 Minor | Backward compat method in `recorder.py` | Deprecate after one cycle | Low |
| T-13 | `fit_affine_from_dataset()` wrapper | 🟢 Minor | Backward compat function in `fitting.py` | Deprecate after one cycle | Low |

---

## 6. Refactoring Strategy

### 6.1 Structural Layout Migration (`src/`)

**Step 1: Move the package**

```bash
mkdir -p src
mv handgrip_calibration src/
```

**Step 2: Update `pyproject.toml` build target**

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/handgrip_calibration"]
```

**Step 3: Update `pyproject.toml` package data**

```toml
[tool.hatch.build.targets.wheel.sources]
"src" = ""

[tool.hatch.build.targets.wheel.include-packages]
"handgrip_calibration" = "src/handgrip_calibration"

# py.typed must be explicitly included
[tool.hatch.build.targets.wheel.force-include]
"src/handgrip_calibration/py.typed" = "handgrip_calibration/py.typed"
```

**Step 4: Update the dev workflow**

```bash
# Install in editable mode (forces src-layout import resolution)
uv pip install -e ".[dev]"

# Tests now run against installed package, not the local directory
pytest tests/
```

**Verification:** After migration, `python -c "import handgrip_calibration; print(handgrip_calibration.__file__)"` should resolve to the installed site-packages path, not the project directory.

---

### 6.2 Dependency Management (`pyproject.toml`)

**Target `pyproject.toml`:**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "handgrip-calibration"
version = "0.1.0"
description = "Calibration session recorder, QA, fitting, and report tooling for dual-device handgrip calibration."
readme = "README.md"
requires-python = ">=3.10"
authors = [{name = "Nicolás Schiappacasse", email = "nicolaschiappacase@gmail.com"}]
dependencies = [
  "numpy>=1.23",
  "pandas>=1.5",
  "matplotlib>=3.6",
  "hydra-core>=1.3",        # ← replaces PyYAML (Hydra brings OmegaConf + PyYAML)
  "omegaconf>=2.3",
  "tabulate>=0.9",
]

[project.optional-dependencies]
lsl = ["pylsl>=1.16"]
xdf = ["pyxdf>=1.16"]
dev = [
  "pytest>=7.0",            # ← moved OUT of runtime deps
  "pytest-cov>=4.0",
  "mypy>=1.0",
  "ruff>=0.4",
]

[project.scripts]
handgrip-cal = "handgrip_calibration.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/handgrip_calibration"]

[tool.hatch.build.targets.wheel.force-include]
"src/handgrip_calibration/py.typed" = "handgrip_calibration/py.typed"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
src = ["src"]
```

**`uv` Development Workflow:**

```bash
# Create environment and install all extras
uv venv
uv pip install -e ".[dev,lsl,xdf]"

# Run tests
uv run pytest tests/

# Run linter
uv run ruff check src/ tests/

# Run type checker
uv run mypy src/handgrip_calibration
```

---

### 6.3 Configuration Management (Hydra Structured Configs)

#### 6.3.1 Promote `AppConfig.raw` Sub-Configs to Proper Dataclasses

The two un-schematized sub-configs accessed through `AppConfig.raw` must be promoted:

**New dataclass: `CreepZeroReturnConfig`**

```python
# config_schema.py — new addition
@dataclass(frozen=True)
class CreepZeroReturnConfig:
    """Creep/zero-return characterization sub-protocol settings."""
    force_levels_N: list[float] = field(default_factory=lambda: [0.0, 80.0, 0.0])
    durations_s: list[float] = field(default_factory=lambda: [120.0, 300.0, 300.0])
    read_times_s: list[float] = field(default_factory=lambda: [30.0, 300.0])

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "CreepZeroReturnConfig":
        data = data or {}
        return cls(
            force_levels_N=[float(x) for x in data.get("force_levels_N", cls.force_levels_N.fget(None))],  # type: ignore
            durations_s=[float(x) for x in data.get("durations_s", [120.0, 300.0, 300.0])],
            read_times_s=sorted(float(x) for x in data.get("read_times_s", [30.0, 300.0])),
        )

    def validate(self) -> None:
        if len(self.force_levels_N) < 1:
            raise ConfigError("creep_zero_return.force_levels_N must not be empty")
        if len(self.durations_s) < len(self.force_levels_N):
            raise ConfigError("creep_zero_return.durations_s must cover all force levels")
```

**New dataclass: `DynamicValidationConfig`**

```python
@dataclass(frozen=True)
class RampSpec:
    label: str = "slow"
    count: int = 2
    peak_force_N: float = 100.0
    speed_N_per_s: float = 5.0

@dataclass(frozen=True)
class SqueezeSpec:
    label: str = "fast_squeeze"
    count: int = 5
    peak_force_N: float = 100.0
    rest_s: float = 3.0

@dataclass(frozen=True)
class DynamicValidationConfig:
    ramps: list[RampSpec] = field(default_factory=lambda: [
        RampSpec(label="slow", count=2, peak_force_N=100.0, speed_N_per_s=5.0),
    ])
    squeezes: list[SqueezeSpec] = field(default_factory=lambda: [
        SqueezeSpec(label="fast_squeeze", count=5, peak_force_N=100.0, rest_s=3.0),
    ])

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "DynamicValidationConfig":
        ...
```

**New dataclass: `HoldoutValidationThresholds`**

```python
@dataclass(frozen=True)
class HoldoutValidationThresholds:
    """Release-gate thresholds for holdout validation."""
    max_rmse_N: float | None = None          # None = derive from operating_range_N
    max_abs_error_N: float | None = None
    max_bias_N: float | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "HoldoutValidationThresholds":
        data = data or {}
        return cls(
            max_rmse_N=float(data["max_rmse_N"]) if "max_rmse_N" in data else None,
            max_abs_error_N=float(data["max_abs_error_N"]) if "max_abs_error_N" in data else None,
            max_bias_N=float(data["max_bias_N"]) if "max_bias_N" in data else None,
        )
```

**Extend `AppConfig` — Remove `raw`:**

```python
@dataclass(frozen=True)
class AppConfig:
    session: SessionConfig
    streams: dict[str, StreamConfig]
    markers: MarkerConfig
    protocol: ProtocolConfig
    quality: QualityConfig
    fit: FitConfig
    creep: CreepZeroReturnConfig          # ← new
    dynamic: DynamicValidationConfig      # ← new
    holdout_thresholds: HoldoutValidationThresholds  # ← new
    # raw: dict[str, Any]                 # ← REMOVED
```

#### 6.3.2 Hydra Compose API Integration

The `load_config()` function is the single integration point. All CLI subcommand handlers call it unchanged.

```python
# config_schema.py — updated load_config
from pathlib import Path
from typing import Any

def load_config(path: str | Path) -> AppConfig:
    """Load config using Hydra compose API.

    Supports Hydra override syntax when called from the CLI:
      handgrip-cal fit session_dir --config conf/default.yaml

    Supports programmatic overrides for testing:
      cfg = load_config("conf/default.yaml")
    """
    path = Path(path).resolve()
    try:
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf
        with initialize_config_dir(
            config_dir=str(path.parent),
            version_base="1.3",
        ):
            raw_cfg = compose(config_name=path.stem)
            data: dict[str, Any] = OmegaConf.to_container(raw_cfg, resolve=True, throw_on_missing=True)  # type: ignore
    except ImportError:
        # Graceful fallback if hydra-core is not installed (e.g., lightweight embedded use)
        import yaml
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")
    return AppConfig.from_dict(data)
```

**Conflict Avoidance Note:** Hydra's `initialize_config_dir` must not be called concurrently or nested. The `with` context manager ensures proper teardown. In test environments, use `hydra.core.global_hydra.GlobalHydra.instance().clear()` after each test that calls `load_config`.

#### 6.3.3 YAML Config Group Structure for Hydra

```
conf/
├── config.yaml                        ← top-level Hydra defaults list
├── session/
│   └── default.yaml                   ← session defaults
├── streams/
│   ├── default.yaml                   ← default stream config
│   └── template.yaml                  ← multi-candidate fallback stream config
├── protocol/
│   ├── static_staircase.yaml          ← primary fit protocol
│   ├── static_reversible_staircase_v3.yaml
│   ├── low_force_refinement.yaml
│   ├── creep_zero_return.yaml
│   ├── dynamic_validation.yaml
│   ├── holdout_verification.yaml
│   ├── reference_verification.yaml
│   └── fast_smoke_test.yaml
├── quality/
│   └── default.yaml
└── fit/
    └── default.yaml
```

**`conf/config.yaml` (top-level defaults list):**

```yaml
defaults:
  - session: default
  - streams: default
  - protocol: static_staircase
  - quality: default
  - fit: default
  - _self_

markers:
  stream_name: HandgripCalibrationMarkers
  stream_type: Markers
  source_id_prefix: handgrip-calibration
  emit_lsl: true
  write_ndjson: true
```

---

### 6.4 Observability (Hierarchical Logging)

#### 6.4.1 Logging Setup Module

Create `src/handgrip_calibration/logging_setup.py`:

```python
"""Logging configuration for handgrip_calibration.

Sets up:
- Console handler: stderr, configurable level
- File handler: <session_dir>/session.log, always DEBUG
- Loggers are scoped to modules via logging.getLogger(__name__)

Usage:
    from handgrip_calibration.logging_setup import configure_logging
    configure_logging(level="INFO", log_file=paths.log)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

def configure_logging(
    *,
    level: str = "INFO",
    log_file: Path | None = None,
) -> None:
    """Configure root logger with console + optional file handler."""
    root = logging.getLogger("handgrip_calibration")
    root.setLevel(logging.DEBUG)  # Root always DEBUG; handlers filter
    root.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — respects the configured level
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler — always DEBUG so the log file is complete
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        root.addHandler(fh)
```

#### 6.4.2 Logger Usage Pattern (All Modules)

Every module replaces `print()` with:

```python
import logging
log = logging.getLogger(__name__)

# Where previously: print(f"Session recorded: {paths.root}")
log.info("Session recorded: %s", paths.root)

# Where previously: print(f"ERROR: {exc}", file=sys.stderr)
log.error("Command failed: %s", exc)

# Where previously: print(f"Baseline: recording {duration:.1f}s")
log.debug("Baseline: recording %.1f s", duration)
```

#### 6.4.3 CLI Integration

```python
# cli.py — add logging init at top of main()
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Initialize logging before any command runs
    from .logging_setup import configure_logging
    configure_logging(level=getattr(args, "log_level", "INFO"))

    try:
        return int(args.func(args))
    except (ConfigError, FileNotFoundError, TimeoutError, RuntimeError, ValueError) as exc:
        logging.getLogger("handgrip_calibration.cli").error("%s", exc)
        return 2
```

**Add `--log-level` flag to all subcommands:**

```python
# cli.py — add to build_parser()
parser.add_argument(
    "--log-level",
    default="INFO",
    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    help="Set log verbosity (default: INFO)",
)
```

**Session log file integration:**

In `recorder.py`, after `paths = self.manager.create(...)`:

```python
from .logging_setup import configure_logging
configure_logging(level="DEBUG", log_file=paths.root / "session.log")
log.info("Session started: %s (protocol=%s)", self.manager.session_id, protocol.protocol_type)
```

#### 6.4.4 `print()` → `log.*()` Migration Map

| File | Current | Replacement |
|------|---------|-------------|
| `cli.py` | `print(f"OK: config loaded...")` | `log.info("Config loaded. Protocol=%s ...", ...)` |
| `cli.py` | `print(f"ERROR: {exc}", file=sys.stderr)` | `log.error("%s", exc)` |
| `recorder.py` | `print(f"Warmup: wait {duration:.1f}s")` | `log.info("Warmup: waiting %.1f s", duration)` |
| `recorder.py` | `print(f"Preload cycle {cycle}/...")` | `log.info("Preload cycle %d/%d ...", cycle, total)` |
| `recorder.py` | `input(f"Apply {force:g} N ...")` | Keep `input()` but add `log.info("Operator prompt: ...")` before |
| `recorder.py` | `print(f"Resting {rest_s:g}s ...")` | `log.debug("Resting %.1f s before next squeeze", rest_s)` |
| `lsl_io.py` | `CsvStreamRecorder` errors | `log.error("Stream recorder error: %s", exc)` |
| `quality.py` | *(none)* | N/A — pure functions |
| `fitting.py` | *(none)* | Add `log.debug()` at fold boundaries |
| `segmentation.py` | *(none)* | Add `log.info()` for accepted hold count |

---

### 6.5 Code Pruning & Dead Code Removal

#### 6.5.1 Backward Compatibility Aliases — Deprecation Plan

These exist only for callers from before the multi-model upgrade. No internal code depends on them post-refactor.

**`fitting.py` — `AffineFitResult` alias:**
```python
# BEFORE — silently aliases to the new class
AffineFitResult = CalibrationFitResult

# AFTER — emit deprecation warning
import warnings
def AffineFitResult(*args, **kwargs):  # type: ignore
    warnings.warn(
        "AffineFitResult is deprecated. Use CalibrationFitResult.",
        DeprecationWarning, stacklevel=2,
    )
    return CalibrationFitResult(*args, **kwargs)
```

**`fitting.py` — `fit_affine_from_dataset()` wrapper:**
```python
# AFTER — emit deprecation warning
def fit_affine_from_dataset(dataset: pd.DataFrame, config: AppConfig) -> CalibrationFitResult:
    """Deprecated. Use fit_model_selection_from_dataset() instead."""
    warnings.warn(
        "fit_affine_from_dataset() is deprecated. Use fit_model_selection_from_dataset().",
        DeprecationWarning, stacklevel=2,
    )
    _, result, _ = fit_model_selection_from_dataset(dataset, config)
    return result
```

**`recorder.py` — `run_static_staircase()` wrapper:**
```python
def run_static_staircase(self) -> SessionPaths:
    """Deprecated. Use run_protocol() instead."""
    warnings.warn(
        "run_static_staircase() is deprecated. Use run_protocol().",
        DeprecationWarning, stacklevel=2,
    )
    return self.run_protocol()
```

#### 6.5.2 Dead Config Key — `baseline.require_stable`

This YAML key appears in `default.yaml` and `template.yaml` but is never read by `ProtocolConfig.from_mapping()`. Resolution:

```python
# config_schema.py — add to ProtocolConfig
baseline_require_stable: bool = True

# In from_mapping():
baseline_require_stable=bool(baseline.get("require_stable", True)),
```

And add the corresponding `validate()` check in `segmentation.py` if quality monitoring during baseline is desired.

#### 6.5.3 `_finite_or_none` Duplication

**Extract to `src/handgrip_calibration/_utils.py`:**

```python
# _utils.py — new file
"""Internal utilities shared across handgrip_calibration modules."""
from __future__ import annotations
import math
import numpy as np

def finite_or_none(value: float | int | None) -> float | int | None:
    """Return value if finite, else None. Handles numpy scalars."""
    if value is None:
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    value = float(value)
    return value if math.isfinite(value) else None
```

Remove the duplicate private definitions from `fitting.py` and `validation.py`.

#### 6.5.4 `__import__("time")` Anti-Pattern

```python
# fitting.py — BEFORE (line ~498 in fit_session)
"host_time_unix": __import__("time").time(),

# AFTER — add at top of fitting.py
import time
# ... 
"host_time_unix": time.time(),
```

#### 6.5.5 Evaluate Over-Defensive Error Handling

**`lsl_io.py` — `_labels_from_info()`:**

```python
# CURRENT — broad except swallowing structural parse errors
try:
    channels = info.desc().child("channels").child("channel")
    for _ in range(info.channel_count()):
        label = channels.child_value("label") or channels.child_value("name")
        ...
except Exception:     # ← catches everything silently
    labels = []
```

The `except Exception` here is appropriate — LSL channel descriptor parsing is notoriously fragile and the fallback (`ch0`, `ch1`, ...) is correct. **Keep as-is.** Log at DEBUG level instead of silently discarding:

```python
except Exception as exc:
    log.debug("Could not parse LSL channel labels (%s); using ch0..chN fallback", exc)
    labels = []
```

**`CsvStreamRecorder.run()` — broad exception at top level:**

```python
# CURRENT
except Exception as exc:
    self.stats.errors.append(str(exc))

# AFTER — add logging
except Exception as exc:
    log.error("Stream recorder [%s] failed: %s", self.key, exc)
    self.stats.errors.append(str(exc))
```

This is not over-defensive — background threads must catch broadly to prevent silent thread death. The change is to make the failure visible.

**`fitting.py` — `fit_candidates_from_dataset()` candidate failure catch:**

```python
# CURRENT — silently catches fitter failures
except Exception as exc:
    failed_metrics = ...
    candidates.append(CandidateResult(..., notes=[str(exc)]))

# AFTER — add DEBUG log so failures are visible during development
except Exception as exc:
    log.debug("Candidate fitter [%s] failed: %s", model_id, exc)
    candidates.append(CandidateResult(..., notes=[str(exc)]))
```

The broad catch here is **intentional and correct** — a failed candidate should not abort the entire fitting session. The change is logging, not restructuring.

---

## 7. Proposed File Tree

```
handgrip-calibration/                    # Project root
├── pyproject.toml                       # ✏️  hatchling + uv, dev group, optional lsl/xdf
├── README.md
├── .github/
│   └── workflows/
│       └── ci.yml                       # ✨ new — pytest + ruff + mypy
├── conf/                                # Hydra config groups
│   ├── config.yaml                      # ✨ new — Hydra defaults list
│   ├── session/
│   │   └── default.yaml                 # ✨ new — session sub-config
│   ├── streams/
│   │   ├── default.yaml                 # ✨ new
│   │   └── template.yaml               # ✨ new
│   ├── protocol/
│   │   ├── static_staircase.yaml        # ✏️  extracted from conf/default.yaml
│   │   ├── static_reversible_staircase_v3.yaml
│   │   ├── low_force_refinement.yaml
│   │   ├── creep_zero_return.yaml       # ✏️  add creep_zero_return sub-section
│   │   ├── dynamic_validation.yaml      # ✏️  add dynamic sub-section
│   │   ├── holdout_verification.yaml
│   │   ├── reference_verification.yaml
│   │   └── fast_smoke_test.yaml
│   ├── quality/
│   │   └── default.yaml                 # ✨ new
│   └── fit/
│       └── default.yaml                 # ✨ new
├── scripts/
│   └── run_demo_validation.sh           # ← unchanged
├── src/
│   └── handgrip_calibration/            # ✏️  MOVED from project root
│       ├── __init__.py                  # ← unchanged
│       ├── __main__.py                  # ✨ new — `python -m handgrip_calibration`
│       ├── py.typed                     # ← unchanged
│       ├── cli.py                       # ✏️  add --log-level, --dry-run, --yes; replace print()
│       ├── config_schema.py             # ✏️  add CreepConfig, DynamicConfig, HoldoutThresholds,
│       │                                #     remove AppConfig.raw, add Hydra compose in load_config()
│       ├── logging_setup.py             # ✨ new — configure_logging()
│       ├── _utils.py                    # ✨ new — finite_or_none(), shared utilities
│       ├── export.py                    # ← unchanged
│       ├── markers.py                   # ✏️  replace print() with log.*()
│       ├── protocol.py                  # ← unchanged (pure, no I/O)
│       ├── quality.py                   # ← unchanged (pure functions)
│       ├── segmentation.py              # ✏️  replace print() with log.*(); use new config fields
│       ├── fitting.py                   # ✏️  fix __import__("time"); add log.debug(); deprecate compat
│       ├── recorder.py                  # ✏️  replace print()/input() with log.*(); use CreepConfig, DynamicConfig
│       ├── lsl_io.py                    # ✏️  add log.debug() to exception handlers
│       ├── session.py                   # ✏️  add session.log path to SessionPaths
│       ├── report.py                    # ✏️  replace print() with log.*()
│       ├── protocol_analysis.py         # ← unchanged (pure functions + pandas)
│       ├── synthetic.py                 # ← unchanged
│       ├── validation.py                # ✏️  use finite_or_none from _utils; use HoldoutThresholds
│       └── xdf_import.py               # ✏️  add log.debug()
└── tests/                               # ← unchanged location (outside src/)
    ├── conftest.py                      # ✨ new — Hydra GlobalHydra teardown fixture
    ├── unit/
    │   ├── test_marker_schema.py        # ✏️  moved to unit/
    │   └── test_quality_rules.py        # ✏️  moved to unit/
    └── integration/
        ├── test_fitting_affine.py       # ✏️  moved to integration/
        └── test_segmentation.py         # ✏️  moved to integration/
```

---

## 8. Configuration Migration Mapping

### 8.1 `AppConfig.raw` Consumers → Proper Config Fields

| Current access via `raw` | New config field | New dataclass |
|--------------------------|-----------------|---------------|
| `config.raw["protocol"]["creep_zero_return"]["force_levels_N"]` | `config.creep.force_levels_N` | `CreepZeroReturnConfig` |
| `config.raw["protocol"]["creep_zero_return"]["durations_s"]` | `config.creep.durations_s` | `CreepZeroReturnConfig` |
| `config.raw["protocol"]["creep_zero_return"]["read_times_s"]` | `config.creep.read_times_s` | `CreepZeroReturnConfig` |
| `config.raw["protocol"]["dynamic_validation"]["ramps"]` | `config.dynamic.ramps` | `DynamicValidationConfig` |
| `config.raw["protocol"]["dynamic_validation"]["squeezes"]` | `config.dynamic.squeezes` | `DynamicValidationConfig` |
| `config.raw["validation"]["holdout"]["max_rmse_N"]` | `config.holdout_thresholds.max_rmse_N` | `HoldoutValidationThresholds` |
| `config.raw["validation"]["holdout"]["max_abs_error_N"]` | `config.holdout_thresholds.max_abs_error_N` | `HoldoutValidationThresholds` |
| `config.raw["validation"]["holdout"]["max_bias_N"]` | `config.holdout_thresholds.max_bias_N` | `HoldoutValidationThresholds` |

### 8.2 YAML Structure Changes

The protocol-specific configs need their sub-sections promoted from under `protocol:` to top-level config groups. Example for `conf/protocol_creep_zero_return.yaml`:

```yaml
# BEFORE — raw dict accessed via AppConfig.raw
protocol:
  name: creep_zero_return_characterization
  type: creep_zero_return
  creep_zero_return:          ← accessed via AppConfig.raw, not validated
    force_levels_N: [0, 80, 0]
    durations_s: [120, 300, 300]
    read_times_s: [30, 300]

# AFTER — top-level validated key
protocol:
  name: creep_zero_return_characterization
  type: creep_zero_return
creep:                         ← top-level, parsed by AppConfig.from_dict()
  force_levels_N: [0, 80, 0]
  durations_s: [120, 300, 300]
  read_times_s: [30, 300]
```

### 8.3 `FitConfig` Backward-Compatible Alias

The `primary_model: affine` alias in `FitConfig.from_mapping()` remains supported:

```python
if primary_model == "affine":
    primary_model = "affine_wls" if cfg.weighted_by_reference_noise else "affine_ols"
    log.warning(
        "fit.primary_model='affine' is deprecated. Set 'affine_wls' or 'affine_ols' explicitly."
    )
```

---

## 9. Deprecation & Pruning Checklist

### Pre-Implementation Checklist (Architecture Review)

- [ ] `src/` layout migration planned and approved
- [ ] `AppConfig.raw` consumers fully identified (recorder.py, validation.py) — confirmed above
- [ ] Hydra compose API integration does not conflict with argparse subcommand dispatch — confirmed above
- [ ] `OmegaConf` container types (`DictConfig`, `ListConfig`) are converted to native Python before passing to dataclass constructors
- [ ] Hydra `initialize_config_dir` teardown fixture added to `tests/conftest.py`
- [ ] `py.typed` marker included in hatchling build config

### Code Changes Checklist

- [ ] **T-01** Move `handgrip_calibration/` → `src/handgrip_calibration/`
- [ ] **T-01** Update `pyproject.toml` build target to `src/handgrip_calibration`
- [ ] **T-02** Create `src/handgrip_calibration/logging_setup.py`
- [ ] **T-02** Add `log = logging.getLogger(__name__)` to every module
- [ ] **T-02** Replace all `print()` calls in `cli.py`, `recorder.py`, `lsl_io.py`, `report.py`
- [ ] **T-02** Add `--log-level` flag to `build_parser()` 
- [ ] **T-02** Call `configure_logging()` at the start of `main()` in `cli.py`
- [ ] **T-02** Add `session.log: Path` to `SessionPaths` dataclass in `session.py`
- [ ] **T-02** Call `configure_logging(log_file=paths.session_log)` in `CalibrationRecorder.run_protocol()`
- [ ] **T-03** Create `CreepZeroReturnConfig` dataclass with `from_mapping()` and `validate()`
- [ ] **T-03** Create `DynamicValidationConfig` dataclass (with `RampSpec`, `SqueezeSpec`)
- [ ] **T-03** Create `HoldoutValidationThresholds` dataclass
- [ ] **T-03** Add `creep`, `dynamic`, `holdout_thresholds` fields to `AppConfig`
- [ ] **T-03** Remove `raw: dict[str, Any]` field from `AppConfig`
- [ ] **T-03** Update `AppConfig.from_dict()` to parse new top-level keys
- [ ] **T-03** Update `recorder.py` `_run_creep_zero_return()` to use `config.creep`
- [ ] **T-03** Update `recorder.py` `_run_dynamic_validation()` to use `config.dynamic`
- [ ] **T-03** Update `validation.py` `_thresholds()` to use `config.holdout_thresholds`
- [ ] **T-03** Update all `conf/*.yaml` files to place creep/dynamic/holdout under top-level keys
- [ ] **T-04** Replace `setuptools` with `hatchling` in `[build-system]`
- [ ] **T-04** Move `pytest` from `dependencies` to `[project.optional-dependencies].dev`
- [ ] **T-04** Add `hydra-core>=1.3` and `omegaconf>=2.3` to `dependencies`
- [ ] **T-04** Add `pylsl` and `pyxdf` as optional extras `lsl` and `xdf`
- [ ] **T-05** Update `load_config()` to use Hydra compose API with PyYAML fallback
- [ ] **T-05** Restructure `conf/` into Hydra config groups (session/, streams/, protocol/, quality/, fit/)
- [ ] **T-05** Add `conf/config.yaml` with Hydra defaults list
- [ ] **T-06** Add `--dry-run` / `-n` flag to `record`, `segment`, `fit`, `report` subcommands
- [ ] **T-06** Implement `DryRunFileSystem` protocol in `export.py` for `--dry-run` mode
- [ ] **T-07** Add `--yes` / `-y` flag to `record` subcommand; pass through to `CalibrationRecorder`
- [ ] **T-07** Update `_operator_continue()` to bypass `input()` when `yes=True`
- [ ] **T-08** Create `src/handgrip_calibration/_utils.py` with `finite_or_none()`
- [ ] **T-08** Remove `_finite_or_none()` from `fitting.py`
- [ ] **T-08** Remove `_finite_or_none()` from `validation.py`
- [ ] **T-08** Import `finite_or_none` from `._utils` in both modules
- [ ] **T-09** Add `import time` to top of `fitting.py`; remove `__import__("time")` inline
- [ ] **T-10** Add `baseline_require_stable: bool = True` to `ProtocolConfig`
- [ ] **T-11** Wrap `AffineFitResult` with `DeprecationWarning`
- [ ] **T-12** Wrap `run_static_staircase()` with `DeprecationWarning`
- [ ] **T-13** Wrap `fit_affine_from_dataset()` with `DeprecationWarning`

### Exception Handling Review Checklist

- [ ] `lsl_io._labels_from_info()` — add `log.debug()` to `except Exception` — ✅ keep broad catch
- [ ] `lsl_io.CsvStreamRecorder.run()` — add `log.error()` to `except Exception` — ✅ keep broad catch
- [ ] `fitting.fit_candidates_from_dataset()` — add `log.debug()` to `except Exception` — ✅ keep broad catch
- [ ] `xdf_import.import_xdf()` — no broad catches; structured exceptions only — ✅ already correct
- [ ] `segmentation.segment_accepted_holds()` — no broad catches — ✅ already correct

### Documentation / Post-Implementation Checklist

- [ ] `README.md` updated with `uv` workflow, new `--log-level`, `--dry-run`, `--yes` flags
- [ ] `conf/template.yaml` updated to reflect new top-level creep/dynamic/holdout keys
- [ ] Hydra override examples added to `README.md`:
  ```bash
  # Override operating range for a larger device
  handgrip-cal fit ./session_dir --config conf/default.yaml fit.operating_range_N=150
  ```
- [ ] `CHANGELOG.md` created to document breaking changes to `AppConfig.raw` removal
- [ ] Deprecation timeline stated: compat aliases removed at v0.3.0

---

*"Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away."* — Antoine de Saint-Exupéry
