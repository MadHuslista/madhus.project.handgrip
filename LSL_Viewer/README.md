# Handgrip Realtime Viewer

Dual-native-stream LSL handgrip force viewer with live, CSV, and XDF replay modes.

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install core + live-streaming dependencies
pip install -e ".[live,xdf,dev]"

# Or with uv (recommended)
uv venv
uv pip install -e ".[live,xdf,dev]"
```

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
lsl-viewer mode=xdf_replay reference.xdf_path=./data/recording.xdf

# Preview config without running
lsl-viewer --cfg job

# Override any config value via CLI
lsl-viewer viewer.window_seconds=5.0 logging.level=DEBUG
```

## Running Tests

```bash
pytest tests/
```

## Architecture

```
src/lsl_viewer/
├── cli.py                  # @hydra.main entry point, mode dispatch
├── config.py               # Structured Hydra config dataclasses
├── logging_setup.py        # Console + rotating file handler setup
├── types.py                # Shared dataclasses (StreamLayout, TargetWindow, …)
├── errors.py               # Typed exception hierarchy
├── core/
│   ├── timing.py           # Pure: LSL/clock interval & validation metrics
│   ├── alignment.py        # Pure: XY time-shift computation & interpolation
│   ├── replay.py           # CSV/XDF loaders + window slicing
│   └── stream.py           # LSL stream connection & live window fetching
├── viz/
│   ├── figure.py           # Figure init, axis helpers, artist reset
│   ├── plots.py            # Per-frame update_plots()
│   └── markers.py          # Calibration NDJSON marker overlay
└── runners/
    ├── live.py             # Live mode event loop
    └── replay.py           # Replay mode animation loop
```

## Configuration

All settings live in `conf/config.yaml` and can be overridden at the CLI
using Hydra's override syntax (`key=value`).  See `conf/config.yaml` for
documentation on each setting.

### Key sections

| Section | Purpose |
|---|---|
| `streams` | LSL stream names and buffer settings |
| `channels` | Channel label mappings |
| `viewer` | Window size, refresh rate, style (colors), XY correlation |
| `alignment` | Reference interpolation policy |
| `calibration_markers` | Optional NDJSON event overlay |
| `reference` | Replay file paths |
| `replay` | Replay speed, loop, start offset |
| `logging` | Level, log file path, rotation settings |
