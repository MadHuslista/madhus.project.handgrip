# Handgrip Calibration Workflow Manual — D2 / LSL v2 / Static Staircase v2

**Scope:** calibration of the Arduino Nano + HX711 handgrip target using the PM58 + RS485 acquisition board as the reference sensor.

**Reviewed components:** `Handgrip_Firmware.zip`, `RS485_GUI.zip`, `LSL_Bridge.zip`, `LSL_Viewer.zip`, and `Handgrip_Calibration.zip`.

**Document sync status:** reviewed against current repository code state on 2026-05-06.

---

## 0. Executive Summary

Use the RS485 acquisition board as the force reference and the Arduino/HX711 as the target under calibration. Mechanically place both force sensors in the same load path, record both native streams through LSL, fit the target raw count to reference force from static holds, and use dynamic trials only for validation.

Recommended default workflow:

1. Configure the reference board for calibrated force in Newtons, Active-Send at 500 Hz, and no hidden zero/drift/dynamic tracking.
2. Run `RS485_GUI`, `LSL_Bridge`, and optionally `LSL_Viewer`.
3. Verify stream availability with:

```bash
handgrip-cal preflight --config conf/default.yaml
```

4. Record the static staircase protocol:

```bash
handgrip-cal record --config conf/protocol_static_staircase.yaml
```

5. Fit and report:

```bash
handgrip-cal fit data/calibration/<session_id> --config conf/default.yaml
handgrip-cal report data/calibration/<session_id>
```

6. Validate deployment robustness on holdout data before firmware updates:

```bash
handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/default.yaml
```

A successful calibration requires the selected deployment model to pass:

```text
max_abs_error_percent_range <= residual_threshold_percent_operating_range
```

With the current `conf/protocol_static_staircase.yaml`, that means:

```text
max_abs_error_percent_range <= 0.5% of 100 N = 0.5 N max absolute error
```

---

## 1. Epistemic Status

### Known from the reviewed project state

- `Handgrip_Firmware` emits schema-2 metadata/data frames intended for `LSL_Bridge`:
  - `M2,<schema>,<fw_version>,<git_sha>,<hx711_rate_hz>,<scale_factor>,<scale_offset>,<unit>`
  - `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`
- `LSL_Bridge` publishes two force streams plus one operational marker stream:
  - `HandgripTarget`, 6 channels, irregular nominal rate.
  - `HandgripReference`, 4 channels, nominal 500 Hz.
  - `HandgripComponentEvents`, JSON markers for component diagnostics.
- `Handgrip_Calibration` expects canonical target/reference stream names and channel labels matching the bridge v2 schema.
- `Handgrip_Calibration` records canonical `target.csv`, `reference.csv`, `events.ndjson`, and `quality_live.ndjson`.
- Static holds are segmented from accepted trial markers. The tail `stable_window_s` of each hold is used for fitting.
- The fitting stage now evaluates multiple candidates, including affine, robust affine, quadratic, monotone piecewise-linear, ODR/Deming-style affine diagnostic, hysteresis diagnostic, and drift diagnostic.

### Historical parser-compatibility issue and current status

A prior review flagged a potential D2 delimiter mismatch. In the current firmware state, the expected line format is:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

`LSL_Bridge` parsing is intentionally strict for this schema. Keep a raw-serial check in preflight as a regression gate:

1. If D2 lines match the expected schema, proceed.
2. If any line contains an empty field after `seq` (double comma), treat it as a regression and stop calibration until firmware emission is corrected.

### Could be known with one bench run

- Actual target rate and jitter from `device_clock_us` and LSL timestamps.
- Actual reference rate and timestamp stability from `reference_clock_s` and LSL timestamps.
- Whether the mechanical fixture shares force sufficiently between both sensors.
- Actual noise floor and baseline drift of the PM58/acquisition-board chain.

### Cannot be known from software alone

- Whether the physical load path has compliance, off-axis load, friction, backlash, or fixture hysteresis.
- Whether the PM58 reference calibration is traceable unless external calibration documentation or known loads are used.
- Whether dynamic squeeze disagreement is caused by sensor physics, mechanical lag, firmware timing, or reference timestamping without targeted tests.

---

## 2. Physical Setup & Mechanical Requirements

### 2.1 Load path principle

The PM58 reference sensor and HX711 target sensor must be mounted mechanically in series so the same axial force flows through both sensors.

The goal is:

```text
Applied force -> fixture -> target sensor -> fixture link -> PM58 reference sensor -> reaction support
```

or the reverse order. The order is less important than ensuring both sensors see the same force vector.

### 2.2 Mechanical requirements

Use the following mechanical constraints before trusting any calibration run:

1. **Same force path**: no parallel structural path may bypass either sensor.
2. **Axial alignment**: the load must be applied along the sensitive axis of both load cells.
3. **Minimal bending/torsion**: off-axis load contaminates both the PM58 reading and the HX711 target response.
4. **Rigid fixture**: compliance produces lag and hysteresis during ramps/squeezes.
5. **Repeatable contact surfaces**: avoid soft pads or shifting contact points unless they are part of the final intended product.
6. **Controlled zero state**: both sensors must be unloaded at baseline. Do not leave preload in the fixture unless explicitly part of the operating condition.
7. **Safe overload margin**: keep the 100 N calibration protocol inside fixture and sensor limits.

### 2.3 Reference board wiring checklist

Reference PM58 to acquisition board:

| PM58 wire               |     Function |                                    Board terminal |
| ----------------------- | -----------: | ------------------------------------------------: |
| Red                     | Excitation + |                                            5 / E+ |
| Black                   | Excitation - |                                            6 / E- |
| White                   |     Signal - |                                            7 / S- |
| Green                   |     Signal + |                                            8 / S+ |
| Shield / yellow / drain |       Shield | Isolate unless deliberately single-point grounded |

Host connection:

| Board terminal | Function | Host path        |
| -------------: | -------- | ---------------- |
|              1 | RS485 A+ | USB-RS485 A / D+ |
|              2 | RS485 B- | USB-RS485 B / D- |

Power on the observed AC unit through:

| Board terminal | Function    |
| -------------: | ----------- |
|             19 | L / Live    |
|             20 | N / Neutral |

### 2.4 Reference board recommended profile

Use this as the calibration profile unless you have measured a better alternative:

| Menu     | Parameter             | Recommended value | Reason                                            |
| -------- | --------------------- | ----------------: | ------------------------------------------------- |
| `100.SP` | internal sampling     |          `640 Hz` | faster than target, lower stress than 1280 Hz     |
| `101.GA` | gain                  |            `128B` | good match for PM58 sensitivity at 5 V excitation |
| `102.ME` | median filter         |               `3` | impulse suppression with low lag                  |
| `103.rV` | average filter        |               `5` | modest SNR improvement                            |
| `105.uN` | unit                  |               `N` | direct force calibration                          |
| `106.bi` | decimal point         |               `1` | 0.1 N display granularity                         |
| `107.dV` | graduation            |               `1` | best display granularity                          |
| `108.ro` | max weighing          |         `900.0 N` | below nominal 100 kg full scale                   |
| `109.di` | DI input              |            `NoNE` | prevents accidental tare/zero                     |
| `400.CV` | creep tracking        |               `0` | no hidden correction                              |
| `401.dZ` | display zero mask     |               `0` | no cosmetic zero hiding                           |
| `402.tV` | dynamic tracking      |               `0` | avoid undocumented transform                      |
| `404.SV` | stable weight switch  |               `0` | show live signal, not final-state abstraction     |
| `406.PZ` | power-on zero         |               `0` | explicit manual zero only                         |
| `409.AZ` | auto-zero             |               `0` | no slow baseline drag                             |
| `412.Wr` | stability gating      |               `0` | prevent division-based nuisance gating            |
| `500.Ar` | RS485 address         |               `1` | single-device bench                               |
| `501.br` | baud                  |     `12 / 460800` | headroom for 500 Hz stream                        |
| `502.Vb` | parity                |            `none` | 8N1                                               |
| `503.so` | stop bits             |               `1` | 8N1                                               |
| `504.AS` | Active-Send           |               `1` | device-paced reference stream                     |
| `505.AF` | Active-Send frequency |      `8 / 500 Hz` | matches LSL_Bridge and calibration config         |

Fallback transport if Active-Send parsing is not stable:

```text
504.AS = 0
serial = 460800 8N1
poll documented Modbus net-force registers at the highest stable rate
```

---

## 3. Software Architecture Recap

### 3.1 Target stream: `HandgripTarget`

Published by `LSL_Bridge` from Arduino/HX711 `D2` UART payload.

Expected channels:

```text
seq
device_clock_us
target_raw_count
target_current_units
target_filtered_units
target_status
```

Calibration fitting should use:

```yaml
fit:
  target_signal: raw
```

which maps to `target_raw_count` through the `streams.target.channel_map` in `conf/default.yaml`.

### 3.2 Reference stream: `HandgripReference`

Published by `LSL_Bridge` from `RS485_GUI` IPC messages.

Expected channels:

```text
seq
reference_clock_s
reference_force_N
reference_status
```

Calibration fitting should use:

```yaml
fit:
  reference_signal: raw
```

which maps to `reference_force_N` through the `streams.reference.channel_map` in `conf/default.yaml`.

### 3.3 Channel-map resolution behavior

`Handgrip_Calibration` resolves configured signals using ordered candidates from `channel_map`:

1. String candidates are matched against LSL channel labels.
2. Integer candidates are interpreted as direct channel indices.

This allows safe fallback when upstream labels evolve while preserving canonical names in default configs.

### 3.4 Events stream

`Handgrip_Calibration` owns calibration trial events through:

```yaml
markers:
  stream_name: HandgripCalibrationMarkers
  stream_type: Markers
  emit_lsl: true
  write_ndjson: true
```

`LSL_Bridge` separately emits `HandgripComponentEvents` for operational diagnostics.

---

## 4. Preflight Procedure

### 4.1 Start upstream components

From separate terminals:

```bash
# Terminal 1: RS485 acquisition GUI
cd RS485_GUI
python acquisition_board_gui.py
```

Use the GUI to connect the PM58 acquisition board in `active_send` mode. Confirm that the live value responds to force and that the observed rate is close to 500 Hz.

```bash
# Terminal 2: LSL bridge
cd LSL_Bridge
python handgrip_lsl_bridge.py
```

Optionally:

```bash
# Terminal 3: live viewer
cd LSL_Viewer
python handgrip_realtime_viewer.py
```

### 4.2 Raw firmware payload gate

Before relying on `LSL_Bridge`, inspect the Arduino serial output once:

```bash
pio device monitor -b 115200
```

Expected:

```text
M2,2,2.0.0-calibration-schema,<git_sha>,93.000,<scale_factor>,<scale_offset>,N
D2,42,1234567,-210637,-210637.000000,0
```

Reject/fix if you see:

```text
D2,42,,1234567,-210637,-210637.000000,0
```

because the strict bridge parser will drop it. In the current codebase this malformed line should not appear; treat it as a firmware regression.

### 4.3 LSL stream preflight

From `Handgrip_Calibration`:

```bash
cd Handgrip_Calibration
handgrip-cal validate-config --config conf/default.yaml
handgrip-cal preflight --config conf/default.yaml
```

Expected output properties:

- `target`: name `HandgripTarget`, type `Force`, 6 channels, nominal rate `0.0` or equivalent irregular rate.
- `reference`: name `HandgripReference`, type `Force`, 4 channels, nominal rate close to `500`.
- Channel labels must include the configured canonical labels.

### 4.4 Acceptance gates before recording

Do not start the static staircase until all gates pass:

| Gate                   | Pass criterion                                                         |
| ---------------------- | ---------------------------------------------------------------------- |
| Reference live rate    | `498–500 Hz` preferred, `>= 495 Hz` minimum                            |
| Target live rate       | approximately `85–105 Hz`                                              |
| Reference max gap      | normally below `0.020 s`                                               |
| Target max gap         | normally below `0.100 s`                                               |
| Reference zero noise   | low enough that a 3 s hold can pass `max_hold_reference_std_N: 0.5`    |
| Force response sign    | reference and target move monotonically in the same physical direction |
| No target parser drops | `target_status` does not show persistent not-ready/overflow conditions |

Relevant `QualityConfig` defaults:

```yaml
quality:
  reference_expected_hz: 500
  reference_min_hz: 495
  reference_max_gap_s: 0.02
  target_expected_hz_min: 85
  target_expected_hz_max: 105
  target_max_gap_s: 0.1
  max_hold_reference_std_N: 0.5
  max_hold_reference_slope_N_per_s: 0.2
  max_baseline_drift_N_per_min: 0.5
  min_hold_target_samples: 20
  min_hold_reference_samples: 100
```

---

## 5. Calibration Protocol: Static Staircase

Use:

```bash
handgrip-cal record --config conf/protocol_static_staircase.yaml
```

This creates:

```text
data/calibration/<session_id>/
  session_manifest.yaml
  component_configs/
  events.ndjson
  quality_live.ndjson
  target.csv
  reference.csv
```

### 5.1 Protocol from `ProtocolConfig`

Current relevant configuration:

```yaml
protocol:
  name: static_staircase_model_selection_v2
  warmup_s: 0
  prompt_operator: true
  baseline:
    duration_s: 10
    require_stable: true
  preload:
    enabled: true
    cycles: 3
    max_force_N: 100
  holds:
    levels_N: [0, 10, 20, 40, 60, 80, 100, 80, 60, 40, 20, 10, 0]
    hold_duration_s: 5
    stable_window_s: 3
    repeats: 2
    auto_accept: false
  dynamic_validation:
    slow_ramps: 2
    fast_squeezes: 5
```

If you want the exact user-requested staircase `[0, 20, 40, 60, 80, 100, 80, ..., 0]`, edit:

```yaml
protocol:
  holds:
    levels_N: [0, 20, 40, 60, 80, 100, 80, 60, 40, 20, 0]
```

The currently reviewed config includes `10 N` on both the ascending and descending sides, which improves low-force characterization.

### 5.2 Operator sequence

#### Phase A — Baseline

1. Remove all load.
2. Let the fixture settle.
3. Press `ENTER` when prompted.
4. The recorder emits:

```text
baseline_start
baseline_end
```

5. Baseline duration is `10 s`.

Reject the baseline/run if the reference drifts more than:

```yaml
max_baseline_drift_N_per_min: 0.5
```

#### Phase B — Preload / mechanical conditioning

Purpose: reduce first-cycle hysteresis and seat the fixture.

1. Apply force up to approximately `100 N`.
2. Release to zero.
3. Repeat for `3` cycles.
4. Avoid abrupt impacts.
5. Do not treat preload data as fit data.

Current config:

```yaml
preload:
  enabled: true
  cycles: 3
  max_force_N: 100
```

#### Phase C — Static staircase holds

For each prompted hold:

1. Apply the target force level.
2. Wait until the reference reading is stable.
3. Press `ENTER` to start the hold.
4. Maintain the force for `5 s`.
5. The recorder uses the last `3 s` as the stable analysis window.
6. Accept the hold only if the force was stable, no slip occurred, and no operator mistake happened.

The recorder emits:

```text
hold_start
stable_window_start
hold_end
trial_accept / trial_reject
```

The segmenter uses `stable_window_start` to `hold_end` when present, so the initial 2 s settling transient is excluded from fitting.

#### Phase D — Dynamic validation

After the static holds:

1. Perform `2` slow ramps across the operating range.
2. Perform `5` fast squeezes/releases.
3. These are not used for the primary fit.
4. Use them to detect lag, bandwidth issues, mechanical hysteresis, and dynamic overshoot.

The recorder currently emits a coarse `dynamic_validation` marker with phase `slow_ramp` or `fast_squeeze`. For deeper future analysis, add per-trial start/end markers later; do not delay the current static calibration workflow for that extension.

---

## 6. Data Acquisition and Reduction

### 6.1 Native acquisition rates

- Target stream: native irregular `~93–100 Hz`, based on HX711 readiness and firmware timing.
- Reference stream: nominal `500 Hz`, device-paced through RS485 Active-Send and IPC.

The correct architecture is not 1:1 sample pairing. The reference stream is faster and is reduced onto target timestamps only where comparison requires it.

### 6.2 Canonical CSV schema

`handgrip-cal record` writes each stream independently.

Target rows include:

```text
timestamp_lsl
seq
clock
raw
filtered
current_units
status
channel_0 ... channel_5
```

Reference rows include:

```text
timestamp_lsl
seq
clock
raw
status
channel_0 ... channel_3
```

Because the config maps `raw` to `target_raw_count` for target and `reference_force_N` for reference, downstream code can stay stable even if upstream labels evolve.

### 6.3 Reference-to-target interpolation

For hold segmentation and live XY plots, reference force is interpolated at target LSL timestamps:

```text
reference_force_at_target_t = linear_interpolation(reference_time_lsl, reference_force_N, target_time_lsl)
```

Rules:

1. Use LSL sample timestamps as the synchronization authority.
2. Use linear interpolation only inside the available reference time range.
3. Do not extrapolate beyond reference coverage.
4. Reject/flag target samples near reference gaps larger than `reference_max_gap_s` or viewer `alignment.max_reference_gap_s`.

This preserves the native 500 Hz reference stream while making calibration features comparable at the target’s actual sample times.

### 6.4 Accepted hold segmentation

`handgrip-cal fit` internally runs segmentation, or you can run it explicitly:

```bash
handgrip-cal segment data/calibration/<session_id> --config conf/default.yaml
```

The output is:

```text
calibration_dataset.csv
```

Each row corresponds to one accepted static hold and includes:

```text
trial_id
target_force_nominal_N
direction
repeat_index
level_index
t_start_lsl
t_end_lsl
target_raw_median
target_raw_std
target_sample_rate_hz
target_max_gap_s
target_seq_gap_count
reference_force_median_N
reference_force_std_N
reference_sample_rate_hz
reference_max_gap_s
reference_slope_N_s
reference_interpolated_to_target_median_N
accepted_by_quality
quality_rejection_reason
```

A hold is quality-accepted if it passes at least:

| Metric               |     Default threshold |
| -------------------- | --------------------: |
| target samples       |               `>= 20` |
| reference samples    |              `>= 100` |
| reference max gap    |          `<= 0.020 s` |
| reference slope      | `<= 0.2 N/s` absolute |
| reference std        |            `<= 0.5 N` |
| target sequence gaps |                  none |

Operator acceptance is necessary but not sufficient; the final fitting stage prefers rows with `accepted_by_quality == true`.

---

## 7. Model Fitting and Accuracy Criteria

### 7.1 Default fitting command

```bash
handgrip-cal fit data/calibration/<session_id> --config conf/default.yaml
```

Generated files:

```text
calibration_dataset.csv
fit_result.json
fit_candidates.json
model_selection_report.json
```

### 7.2 Primary model form

The simplest deployable calibration is affine:

```text
force_N = a * raw_count + b
```

This maps the target HX711 raw count to reference force in Newtons.

### 7.3 Candidate model set

Current `FitConfig` candidate models:

```yaml
fit:
  primary_model: auto
  candidate_models:
    - affine_ols
    - affine_wls
    - affine_huber
    - quadratic_wls
    - piecewise_linear_monotone
    - odr_affine
    - hysteresis_affine_diagnostic
    - drift_affine_diagnostic
```

Interpretation:

| Candidate                      | Role                                                            |
| ------------------------------ | --------------------------------------------------------------- |
| `affine_ols`                   | baseline straight-line fit                                      |
| `affine_wls`                   | preferred affine if reference noise varies by hold              |
| `affine_huber`                 | robust affine when some holds are mildly contaminated           |
| `quadratic_wls`                | possible nonlinear correction, only if materially justified     |
| `piecewise_linear_monotone`    | firmware-friendly multipoint correction                         |
| `odr_affine`                   | diagnostic errors-in-variables / Deming-style affine comparison |
| `hysteresis_affine_diagnostic` | ascending vs descending split diagnostic                        |
| `drift_affine_diagnostic`      | time-dependent drift diagnostic                                 |

Diagnostics should explain failure modes; they should not become the default deployment model unless deliberately configured.

### 7.4 Selection policy

The selector ranks models by:

```yaml
selection:
  primary_metric: cv_rmse_N
  max_error_metric: max_abs_error_percent_range
  prefer_simpler_within_cv_rmse_se: true
  require_monotonic: true
  allow_diagnostics_as_primary: false
  cv_group_by: target_force_nominal_N
  max_cv_folds: 12
  alpha_cv_rmse: 40.0
  beta_max_error: 60.0
  lambda_complexity: 0.15
```

Practical meaning:

1. Prefer lower cross-validated RMSE.
2. Penalize high max absolute error.
3. Penalize model complexity.
4. Reject non-monotone deployable models.
5. Prefer the simpler model when performance is statistically similar.

### 7.5 Success criterion

Current threshold:

```yaml
fit:
  operating_range_N: 100.0
  residual_threshold_percent_operating_range: 0.5
```

That means:

```text
success if max_abs_error_N <= 0.005 * 100 N = 0.5 N
```

A calibration is deployable only if:

1. `passes_residual_threshold == true` in `fit_result.json`.
2. Selected model is deployable to firmware.
3. Residual plot has no obvious structured curve, discontinuity, or hysteresis split.
4. Dynamic validation does not reveal unacceptable lag or overshoot.
5. The accepted holds cover the intended operating range.

### 7.6 Firmware constants

`fit_result.json` includes:

```json
{
  "force_N": {"a": ..., "b": ...},
  "recommended_firmware_constants": {...}
}
```

For affine deployment, verify firmware semantics carefully. Current firmware comments use:

```text
current_units = (raw_count - SCALE_OFFSET) / SCALE_FACTOR
```

while calibration fit uses:

```text
force_N = a * raw_count + b
```

Equivalent conversion if `a != 0`:

```text
SCALE_FACTOR = 1 / a
SCALE_OFFSET = -b / a
```

Always validate with a replay or bench check after updating firmware constants.

---

## 8. Dynamic Validation and Iteration

### 8.1 What dynamic validation is for

Dynamic trials are not for estimating `a` and `b`. They are for checking whether the calibrated target behaves correctly outside static equilibrium.

Use dynamic data to assess:

| Check             | Symptom                                 | Likely cause                                          |
| ----------------- | --------------------------------------- | ----------------------------------------------------- |
| Lag               | target peak occurs later than reference | firmware/filtering/serial/fixture lag                 |
| Bandwidth         | target attenuates fast squeeze peaks    | HX711 bandwidth or filtering                          |
| Hysteresis        | ramp up/down curves differ              | mechanical fixture or sensor hysteresis               |
| Overshoot         | target spikes relative to reference     | fixture impact, electrical noise, interpolation error |
| Baseline recovery | target does not return to zero          | drift, mechanical settling, offset instability        |

### 8.2 Minimum dynamic validation workflow

After report generation:

1. Open `calibration_report.html`.
2. Inspect `target_timeseries.png` and `reference_timeseries.png` for gross timing gaps.
3. Use `LSL_Viewer` live or replay mode to inspect time-series overlay and XY curve.
4. Verify slow ramps produce a mostly monotone sensor curve.
5. Verify fast squeezes do not produce clinically/experimentally unacceptable lag or peak attenuation.

### 8.3 Quantitative dynamic metrics to add or compute manually

For a future extension, compute:

```text
lag_s = argmax_cross_correlation(calibrated_target_force, reference_force)
peak_error_N = target_peak_N - reference_peak_N
peak_error_percent = 100 * peak_error_N / operating_range_N
ramp_up_down_area_N = area_between_curves(up, down)
baseline_recovery_error_N = post_trial_baseline_median_N - pre_trial_baseline_median_N
```

Acceptance suggestions for a 100 N operating range:

| Metric                         |                                        Good initial target |
| ------------------------------ | ---------------------------------------------------------: |
| static max abs error           |                                                 `<= 0.5 N` |
| static RMSE                    |                                 `<= 0.25–0.35 N` preferred |
| dynamic lag                    | document first; set limit after experiment needs are known |
| post-squeeze baseline recovery |                                  `<= 0.5 N` after settling |
| slow-ramp monotonicity         |                  no large reversals outside measured noise |

Do not optimize dynamic metrics until the static fit is stable.

---

## 9. Comparing Sessions and Tracking Drift

### 9.1 Session artifacts to compare

For every calibration session, keep:

```text
session_manifest.yaml
component_configs/
quality_live.ndjson
calibration_dataset.csv
fit_result.json
fit_candidates.json
model_selection_report.json
calibration_report.html
plots/
```

### 9.2 Minimum drift comparison table

Build a comparison table across sessions with:

```text
session_id
created_utc
selected_model_id
a
b
rmse_N
max_abs_error_N
max_abs_error_percent_range
passes_residual_threshold
selection_likelihood
reference_force_std_N median
target_raw_std median
baseline drift estimate
```

### 9.3 Drift interpretation

| Observation                         | Interpretation                           | Action                                          |
| ----------------------------------- | ---------------------------------------- | ----------------------------------------------- |
| `a` changes, `b` stable             | sensitivity/span change                  | inspect HX711/load-cell gain path and mechanics |
| `b` changes, `a` stable             | offset/zero shift                        | inspect preload, tare, thermal zero drift       |
| both `a` and `b` shift              | mechanical setup changed or sensor aging | repeat reference-only verification              |
| RMSE rises but coefficients similar | noisy holds or operator instability      | improve hold stability / fixture                |
| hysteresis diagnostic worsens       | fixture compliance/contact issue         | inspect load path and preloading                |
| drift diagnostic worsens            | warm-up or creep                         | add warm-up, inspect auto-zero disabled state   |

### 9.4 Example comparison command

This assumes `jq` is installed:

```bash
for f in data/calibration/*/fit_result.json; do
  session=$(basename "$(dirname "$f")")
  jq -r --arg session "$session" '
    [
      $session,
      .selected_model_id,
      .force_N.a,
      .force_N.b,
      .metrics.rmse_N,
      .metrics.max_abs_error_N,
      .metrics.max_abs_error_percent_range,
      .passes_residual_threshold,
      .selection_likelihood
    ] | @csv
  ' "$f"
done > calibration_session_comparison.csv
```

---

## 10. Reporting Interpretation

Run:

```bash
handgrip-cal report data/calibration/<session_id>
```

Generated files:

```text
calibration_report.md
calibration_report.html
plots/
```

### 10.1 Report summary

Read first:

- selected model
- model-selection likelihood
- affine-compatible equation
- RMSE
- CV RMSE
- max absolute error
- max abs error / operating range
- residual threshold pass/fail

Decision rule:

```text
If threshold fails, do not deploy without either improving data quality or proving a nonlinear correction is repeatable.
```

### 10.2 Candidate ranking table

Use it to answer:

1. Did affine perform almost as well as nonlinear models?
2. Did any model get rejected for non-monotonicity?
3. Did robust Huber down-weight specific holds?
4. Did diagnostics indicate hysteresis or drift?

Default deployment preference:

```text
affine_wls or affine_huber > piecewise_linear_monotone > quadratic_wls
```

unless evidence strongly justifies otherwise.

### 10.3 Plots

| Plot                              | Meaning                                    | What to look for                                    |
| --------------------------------- | ------------------------------------------ | --------------------------------------------------- |
| `target_timeseries.png`           | target raw/units over time                 | gaps, jumps, FIFO/status problems                   |
| `reference_timeseries.png`        | PM58/reference force over time             | stable holds, drift, rate/backlog artifacts         |
| `model_comparison_curve.png`      | candidate model curves over accepted holds | whether nonlinear models are materially different   |
| `selected_residuals_by_force.png` | selected model residuals vs force          | curvature, bias, outlier holds                      |
| `model_comparison_residuals.png`  | residuals for multiple candidates          | whether nonlinear model actually improves structure |
| `model_metric_bars.png`           | RMSE and max error comparison              | best model vs acceptable simple model               |
| `model_likelihoods.png`           | relative decision weight                   | whether winner is decisive or marginal              |
| `robust_huber_weights.png`        | robust-fit hold weights                    | contaminated holds                                  |
| `hysteresis_up_down.png`          | ascending/descending split                 | mechanical hysteresis or load-path asymmetry        |

### 10.4 Sensor-curve / XY live viewer interpretation

In `LSL_Viewer`, the XY plot uses:

```text
x = reference_force_N interpolated at target timestamps
y = target_raw_count or target_filtered_units
```

For calibration intuition, keep:

```yaml
viewer:
  xy_correlation:
    target_signal: raw
    time_alignment:
      mode: raw_lsl
alignment:
  interpolation: linear
  max_reference_gap_s: 0.020
  allow_extrapolation: false
```

Good signs:

- curve is monotone;
- ascending and descending traces nearly overlap;
- no loop opening after preload;
- no multi-second `ref_shift` growth in `raw_lsl` mode;
- reference and target tails remain temporally aligned.

Bad signs:

- widening loop between ascending and descending holds;
- abrupt steps at constant force;
- XY curve moving while reference is stable;
- `ref_shift` grows continuously, indicating timestamp/backlog issue, not a calibration model issue.

---

## 11. End-to-End Runbook

### 11.1 One-time installation

```bash
cd Handgrip_Calibration
python -m pip install -e '.[lsl,xdf]'
```

Or, if using `uv`, adapt to your environment:

```bash
uv pip install -e '.[lsl,xdf]'
```

### 11.2 Daily calibration run

```bash
# 1. Start RS485 GUI
cd RS485_GUI
python acquisition_board_gui.py

# 2. Start LSL Bridge
cd ../LSL_Bridge
python handgrip_lsl_bridge.py

# 3. Optional viewer
cd ../LSL_Viewer
python handgrip_realtime_viewer.py

# 4. Calibration preflight
cd ../Handgrip_Calibration
handgrip-cal validate-config --config conf/default.yaml
handgrip-cal preflight --config conf/default.yaml

# 5. Record protocol
handgrip-cal record --config conf/protocol_static_staircase.yaml

# 6. Fit selected model
handgrip-cal fit data/calibration/<session_id> --config conf/default.yaml

# 7. Generate report
handgrip-cal report data/calibration/<session_id>
```

### 11.3 Required runtime validation gate (manual sync acceptance)

Before accepting this manual as up-to-date for bench operations, run this minimum validation sequence:

```bash
# A. Config and stream contract gate
cd Handgrip_Calibration
handgrip-cal validate-config --config conf/default.yaml
handgrip-cal preflight --config conf/default.yaml

# B. Firmware wire-format regression gate (in a separate terminal)
pio device monitor -b 115200

# C. One short acquisition + fit + report cycle
handgrip-cal record --config conf/protocol_fast_smoke_test.yaml
handgrip-cal fit data/calibration/<session_id> --config conf/default.yaml
handgrip-cal report data/calibration/<session_id>
```

Required pass criteria:

1. `preflight` resolves both `HandgripTarget` and `HandgripReference` with expected channel counts.
2. Raw serial lines include valid `M2` and `D2` payloads with no empty D2 field after `seq`.
3. `record`, `fit`, and `report` complete and produce expected artifacts in `data/calibration/<session_id>/`.

### 11.4 Holdout validation path

Use holdout sessions to validate model generalization without refitting:

```bash
handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/default.yaml
```

Expected outputs:

```text
holdout_validation.json
holdout_predictions.csv
```

### 11.5 Optional XDF import path

If recording with LabRecorder/XDF instead of direct CSV:

```bash
handgrip-cal import-xdf recording.xdf data/calibration/<session_id> --config conf/default.yaml
handgrip-cal fit data/calibration/<session_id> --config conf/default.yaml
handgrip-cal report data/calibration/<session_id>
```

### 11.6 Optional synthetic-session generation

Use synthetic sessions to test pipeline behavior without bench hardware:

```bash
handgrip-cal demo-data --output ./demo_sessions --seed 42
```

---

## 12. Failure Modes and Triage

| Failure                                                         | Likely cause                                                      | Immediate action                                                                                     |
| --------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `preflight` cannot resolve `HandgripTarget`                     | firmware not parsed, serial port wrong, D2 format mismatch        | inspect raw serial; verify no extra comma; check LSL_Bridge logs                                     |
| `preflight` cannot resolve `HandgripReference`                  | RS485_GUI IPC not publishing, bridge not subscribed               | check ZMQ endpoint `tcp://127.0.0.1:5557`, topic `rs485.measurement.v1`                              |
| bridge logs show repeated IPC reconnect or no reference samples | endpoint/topic mismatch between publisher and subscriber          | verify RS485_GUI publisher endpoint/topic and LSL_Bridge `reference_ipc` config match exactly        |
| RS485 GUI fails to start publisher                              | local endpoint already in use                                     | stop conflicting process on `tcp://127.0.0.1:5557` and restart RS485_GUI                             |
| reference rate < 495 Hz                                         | serial backlog, Active-Send config mismatch, parser recovery loop | reduce GUI load, check baud 460800, check board `505.AF=8`                                           |
| target gaps > 100 ms                                            | HX711 not ready, firmware FIFO overflow, serial disruption        | inspect `target_status`, USB cable, sampling ISR behavior                                            |
| reference stream present but values invalid/intermittent        | malformed RS485 IPC payloads or field mismatch                    | inspect RS485_GUI payload keys (`reference_force_N`, `reference_clock_s`, `seq`) and bridge warnings |
| many holds rejected for std                                     | operator instability or fixture compliance                        | improve mechanical support, longer hold, lower threshold only after measuring noise                  |
| many holds rejected for slope                                   | force drifting during stable window                               | wait longer before pressing ENTER, improve load application method                                   |
| affine fails but nonlinear passes                               | possible nonlinearity or bad holds                                | inspect residuals; repeat session before deploying nonlinear model                                   |
| hysteresis diagnostic large                                     | mechanical hysteresis/contact issue                               | improve fixture/preload, compare ascending/descending holds                                          |
| drift diagnostic large                                          | warm-up/creep/auto-zero problem                                   | warm up longer, verify auto-zero/dynamic tracking disabled                                           |

---

## 13. Recommended Calibration Acceptance Checklist

A session is acceptable for deployment when:

- [ ] Raw firmware line format matches strict D2 parser.
- [ ] `handgrip-cal preflight` resolves both streams.
- [ ] Target stream has expected labels and no persistent parser/status errors.
- [ ] Reference stream is close to 500 Hz and max gaps stay below threshold.
- [ ] Baseline is stable and low drift.
- [ ] At least one full ascending and descending staircase was accepted; two repeats preferred.
- [ ] Each force level has enough accepted samples.
- [ ] `fit_result.json` has `passes_residual_threshold: true`.
- [ ] Holdout validation was run with `validate-holdout` for the intended deployment model.
- [ ] Residuals show no obvious systematic curvature or hysteresis loop.
- [ ] Dynamic validation shows acceptable lag and recovery for the intended use.
- [ ] Firmware constants are validated on a fresh short staircase after deployment.

---

## 14. Recommended Future Improvements

1. Add explicit `dynamic_trial_start` / `dynamic_trial_end` events around each ramp and squeeze.
2. Add a `compare-sessions` CLI command that summarizes drift from multiple `fit_result.json` files.
3. Add automatic baseline drift extraction from `baseline_start` / `baseline_end` windows.
4. Add dynamic lag and peak attenuation metrics to `calibration_report.html`.
5. Add a preflight D2 raw-line parser self-test to fail fast on firmware/bridge schema mismatch.
6. Add a fixture checklist to `session_manifest.yaml` so mechanical changes are tracked as first-class metadata.

---

## 15. What Changed In This Revision

1. Replaced stale blocking language about a D2 delimiter bug with current-state wording plus an explicit regression gate.
2. Added `validate-holdout` and `demo-data` workflow coverage to align with the current CLI surface.
3. Added a required runtime validation gate under the runbook for config, stream, wire-format, and artifact verification.
4. Documented channel-map label/index fallback behavior used by calibration stream resolution.
5. Expanded triage with RS485/bridge IPC endpoint-topic mismatch and publisher binding failure scenarios.

