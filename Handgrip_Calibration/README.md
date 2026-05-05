# Handgrip_Calibration

`Handgrip_Calibration` is a self-contained Python module for calibration sessions that use:

- an HX711/Arduino handgrip target stream, and
- a PM58/acquisition-board reference stream published through RS485 → IPC → LSL.

It adds the calibration workflow layer:

1. session creation and manifest capture,
2. LSL stream preflight,
3. live recording to canonical CSV files,
4. calibration marker logging and optional LSL marker stream,
5. live quality telemetry,
6. static-hold segmentation,
7. affine calibration fitting,
8. report and plot generation.

The module is intentionally CLI-first. This keeps the first calibration implementation simple, auditable, and easy to automate later. A richer GUI can be added after the real workflow stabilizes.

## Install

From this folder:

```bash
python -m pip install -e .
```

For live LSL recording:

```bash
python -m pip install -e '.[lsl]'
```

For importing `.xdf` recordings:

```bash
python -m pip install -e '.[xdf]'
```

## Fast validation without hardware

Generate a synthetic calibration session, fit it, and generate a report:

```bash
python -m handgrip_calibration.cli demo-data --output ./demo_sessions
python -m handgrip_calibration.cli fit ./demo_sessions/demo_handgrip_session
python -m handgrip_calibration.cli report ./demo_sessions/demo_handgrip_session
```

## Live workflow

1. Start `RS485_GUI` and verify acquisition-board data is being published.
2. Start `LSL_Bridge` and verify both LSL streams exist.
3. Optionally start `LSL_Viewer` for visualization.
4. Run:

```bash
handgrip-cal preflight --config conf/default.yaml
handgrip-cal record --config conf/protocol_static_staircase.yaml
handgrip-cal fit data/calibration/<session_id>
handgrip-cal report data/calibration/<session_id>
```

## Data products

A session folder contains:

```text
session_manifest.yaml
component_configs/
events.ndjson
quality_live.ndjson
target.csv
reference.csv
calibration_dataset.csv
fit_result.json
calibration_report.md
calibration_report.html
plots/
```

## Design boundary

The module assumes the current system continues to expose two LSL streams:

- target: Arduino/HX711 handgrip stream, irregular rate, ~93–100 Hz
- reference: RS485 acquisition board stream, typically Active-Send ~500 Hz

Future extensions to the other components can add richer raw-count payloads, firmware metadata, and marker overlays. This module already accepts those future fields when present.
