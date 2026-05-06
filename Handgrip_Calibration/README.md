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
7. candidate-model fitting and selection,
8. report and plot generation.

The module is intentionally CLI-first. This keeps the first calibration implementation simple, auditable, and easy to automate later. A richer GUI can be added after the real workflow stabilizes.

## Protocol suite

Six protocol families are supported via named config files in `conf/`:

| Config file                                    | Purpose                                                                |
| ---------------------------------------------- | ---------------------------------------------------------------------- |
| `protocol_reference_verification.yaml`         | Verify the reference instrument chain before any calibration recording |
| `protocol_static_reversible_staircase_v3.yaml` | Primary calibration: stepped static holds with up/down reversal        |
| `protocol_low_force_refinement.yaml`           | Refine the low-force region of the calibration curve                   |
| `protocol_creep_zero_return.yaml`              | Measure creep under sustained load and zero-return error               |
| `protocol_dynamic_validation.yaml`             | Dynamic ramp/squeeze sequences for dynamic linearity checks            |
| `protocol_holdout_verification.yaml`           | Independent holdout set for out-of-sample accuracy validation          |

The `protocol.type` / `protocol_type` field in each config selects the protocol family. The `config_schema` validates the field and associated timing parameters (preload hold/recovery, holdout validation mode metadata).

### Lifecycle markers emitted during recording

`recorder.py` emits explicit lifecycle markers into `events.ndjson`:

- `reference_verification_start` / `reference_verification_end`
- `preload_start` / `preload_end`
- `series_start` / `series_end`
- `creep_start`, `creep_read_30s`, `creep_read_300s`, `zero_return_start`, `zero_return_end`
- `ramp_start` / `ramp_end`, `squeeze_start` / `squeeze_end`
- `holdout_start` / `holdout_end`

The legacy `run_static_staircase()` entry point remains as a wrapper around `run_protocol()`.

## Calibration model selection

The fit stage performs model comparison across multiple candidate families and selects a final export model using quality and plausibility checks.

Implemented candidates:

- weighted affine fit (`affine_wls`)
- robust affine fit (`affine_huber`)
- quadratic degree-2 fit (`quadratic_wls`)
- monotone piecewise-linear multipoint fit (`piecewise_linear_monotone`)

Implemented diagnostics:

- ODR-like affine diagnostic via pure-NumPy Deming regression (`odr_affine`)
- hysteresis-aware up/down diagnostic (`hysteresis_affine_diagnostic`)
- drift/time-term diagnostic (`drift_affine_diagnostic`)

Selection outputs include model metrics, ranking, rejection reasons, and likelihood-style decision weights. The fit stage also appends lifecycle events `calibration_candidate_selected` and `firmware_constants_exported` to the session event log.

Generated plots include candidate curves, residual diagnostics, metric comparisons, model likelihoods, robust weights, and hysteresis views.

## Calibration report sections

The generated report (`calibration_report.md` / `.html`) includes:

1. Reference-chain verification summary
2. Static fit summary
3. Holdout accuracy summary
4. Hysteresis/reversibility summary
5. Creep/zero-return summary
6. Dynamic validation summary
7. Previous calibration comparison
8. Firmware deployment recommendation

Report tables are computed by `protocol_analysis.py`, which covers stream health, hold quality, hysteresis/reversibility, creep/zero-return, and dynamic validation events.

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

Full validation run (including holdout):

```bash
PYTHONPATH=. timeout 30s pytest -q -p no:ddtrace -p no:asyncio -p no:anyio \
  tests/test_marker_schema.py tests/test_quality_rules.py tests/test_segmentation.py tests/test_fitting_affine.py
# 5 passed

PYTHONPATH=. python -m handgrip_calibration.cli demo-data --output /tmp/hg_demo
PYTHONPATH=. python -m handgrip_calibration.cli fit /tmp/hg_demo/demo_handgrip_session --config conf/default.yaml
PYTHONPATH=. python -m handgrip_calibration.cli report /tmp/hg_demo/demo_handgrip_session
PYTHONPATH=. python -m handgrip_calibration.cli validate-holdout /tmp/hg_demo/demo_handgrip_session \
  --model /tmp/hg_demo/demo_handgrip_session/fit_result.json
```

## Live workflow

1. Start `RS485_GUI` and verify acquisition-board data is being published.
2. Start `LSL_Bridge` and verify both LSL streams exist.
3. Optionally start `LSL_Viewer` for visualization.
4. Run the full calibration sequence:

```bash
handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
handgrip-cal record --config conf/protocol_reference_verification.yaml
handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
handgrip-cal fit data/calibration/<fit_session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
handgrip-cal report data/calibration/<fit_session_id>
handgrip-cal record --config conf/protocol_holdout_verification.yaml
handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
handgrip-cal report data/calibration/<holdout_session_id>
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
fit_candidates.json
model_selection_report.json
holdout_validation.json        # written by validate-holdout
holdout_predictions.csv        # written by validate-holdout
calibration_report.md
calibration_report.html
plots/
```

`fit_result.json` is the firmware-facing selected model export. `holdout_validation.json` and `holdout_predictions.csv` are produced by the `validate-holdout` command via `validation.py`, which evaluates out-of-sample accuracy against an existing `fit_result.json` without refitting.

## Module reference

| Module                 | Role                                                                                      |
| ---------------------- | ----------------------------------------------------------------------------------------- |
| `config_schema.py`     | Config loading and validation; `protocol.type` and timing parameters                      |
| `recorder.py`          | Protocol-aware live recording; lifecycle marker emission                                  |
| `fitting.py`           | Candidate model fitting, selection, and export                                            |
| `validation.py`        | Independent holdout validation without refitting                                          |
| `protocol_analysis.py` | Report table computation for all protocol sections                                        |
| `report.py`            | Calibration report and plot generation                                                    |
| `cli.py`               | CLI entry points: `preflight`, `record`, `fit`, `report`, `validate-holdout`, `demo-data` |

## Design boundary

The module assumes the current system continues to expose two LSL streams:

- target: Arduino/HX711 handgrip stream, irregular rate, ~93–100 Hz
- reference: RS485 acquisition board stream, typically Active-Send ~500 Hz

Future extensions to the other components can add richer raw-count payloads, firmware metadata, and marker overlays. This module already accepts those future fields when present.
