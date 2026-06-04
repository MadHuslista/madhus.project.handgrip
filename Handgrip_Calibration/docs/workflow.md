
# Workflow - From init to firmware deployment

Assumption: `RS485_GUI` and `LSL_Bridge` are already alive, and `LSL_Bridge` is publishing `HandgripTarget` and `HandgripReference`. That matches the architecture: `LSL_Bridge` is the canonical publisher for both target/reference LSL streams, while `Handgrip_Calibration` records sessions and fits `reference_force_N = f(target_raw_count)`. 

The canonical stream/config invariants are:

* target stream: `HandgripTarget`
* reference stream: `HandgripReference`
* primary target fit channel: `target_raw_count`
* primary reference force channel: `reference_force_N`
* protocol: `protocol_static_reversible_staircase_v3.yaml` 

## Prerequisites

Complete the upstream setup before recording:

* [docs/workflows/physical-setup.md](../../docs/workflows/physical-setup.md) — PM58 and target in the same force path
* [Handgrip_Firmware/docs/workflow.md](../../Handgrip_Firmware/docs/workflow.md) — firmware emits `D2` frames
* [RS485_GUI/docs/workflow.md](../../RS485_GUI/docs/workflow.md) — `RS485_GUI` running, reference data updating
* [LSL_Bridge/docs/workflow.md](../../LSL_Bridge/docs/workflow.md) — `LSL_Bridge` publishing `HandgripTarget` and `HandgripReference`

---

## Step 0 — One-time environment setup

Run from repo root:

```bash
uv sync
```

Then enter the calibration component:

```bash
cd Handgrip_Calibration
```

### What happens

`uv sync` installs the editable local packages and dependencies declared by the repo and component `pyproject.toml`. The `handgrip-cal` entry point becomes available through `uv run`.

### Expected result

This should work:

```bash
uv run handgrip-cal --help
```

Expected: CLI help showing subcommands such as:

```text
validate-config
preflight
record
segment
fit
validate-holdout
report
import-xdf
demo-data
```

---

## Step 1 — Validate the calibration config

```bash
uv run handgrip-cal validate-config \
  --config conf/protocol_static_reversible_staircase_v3.yaml
```

### What happens

The YAML config is loaded and validated against the internal schema. This checks protocol structure, stream config, quality thresholds, fit configuration, and output paths.

Relevant config values in `conf/protocol_static_reversible_staircase_v3.yaml`:

```yaml
streams:
  target:
    name: HandgripTarget
    channel_map:
      raw: target_raw_count
      current_units: target_current_units
      filtered: target_filtered_units

  reference:
    name: HandgripReference
    nominal_srate_hz: 500
    channel_map:
      raw: reference_force_N

fit:
  target_signal: raw
  reference_signal: raw
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

### Expected result

The command exits with `0` and logs something equivalent to:

```text
Config OK — protocol=static_reversible_staircase_v3,
target_stream=HandgripTarget,
reference_stream=HandgripReference
```

### Stop condition

Do not continue if this fails. A config failure means the CLI cannot safely interpret the session structure.

---

## Step 2 — LSL preflight

```bash
uv run handgrip-cal preflight \
  --config conf/protocol_static_reversible_staircase_v3.yaml
```

### What happens

The tool searches the active LSL network for:

```text
HandgripTarget
HandgripReference
```

Then it checks metadata/channel availability against the config.

### Expected result

You should see both streams resolved:

```text
LSL preflight OK
  target: name='HandgripTarget', ...
  reference: name='HandgripReference', ...
```

Expected target channels include, semantically:

```text
seq
device_clock_us
target_raw_count
target_current_units
target_filtered_units
target_status
```

Expected reference channel includes:

```text
reference_force_N
```

### Stop condition

Stop if either stream is missing, has wrong channel semantics, or the reference stream is not near the expected 500 Hz. Fix `LSL_Bridge`, `RS485_GUI`, or firmware before recording.

---

## Step 3 — Record the primary calibration session

```bash
uv run handgrip-cal record \
  --config conf/protocol_static_reversible_staircase_v3.yaml \
  --session-id 20260603_primary_cal_v1
```

The `--session-id` is optional but recommended for traceability.

### What happens

The calibration protocol starts and prompts the operator through:

1. baseline,
2. preload cycles,
3. static reversible staircase holds.

The configured primary hold sequence is:

```text
0, 5, 10, 20, 30, 40, 55, 70, 85, 100,
85, 70, 55, 40, 30, 20, 10, 5, 0 N
```

with:

```yaml
baseline:
  duration_s: 30

preload:
  enabled: true
  cycles: 3
  max_force_N: 100
  hold_duration_s: 20
  recovery_duration_s: 10

holds:
  hold_duration_s: 10
  stable_window_s: 5
  repeats: 2
  auto_accept: false
```

During each hold, the operator applies the target force level, waits for stability, then accepts or rejects the hold.

### Expected result

A session folder appears:

```text
data/calibration/20260603_primary_cal_v1/
```

Expected artifacts:

```text
target.csv
reference.csv
events.ndjson
session_manifest.yaml
session.log
quality_live.ndjson
component_configs/
```

The important semantic outcome is: you now have raw target counts and reference force captured under known protocol markers.

For session folder structure, preflight acceptance gates, quality thresholds, and the recommended acquisition-board configuration, see [Handgrip_Calibration/docs/recording.md](recording.md).

---

## Step 4 — Fit calibration model candidates

```bash
uv run handgrip-cal fit \
  data/calibration/20260603_primary_cal_v1 \
  --config conf/protocol_static_reversible_staircase_v3.yaml
```

### What happens

The tool:

1. segments accepted holds,
2. computes per-hold summary statistics,
3. builds `calibration_dataset.csv`,
4. fits all configured candidate models,
5. ranks models,
6. writes the selected model and deployment metadata.

The core model relationship is:

```text
reference_force_N = f(target_raw_count)
```

This is the correct calibration relationship; do **not** fit against `target_current_units` unless you are specifically validating already-deployed firmware constants. This is the core fitting invariant.

### Expected result

Files written into the session folder:

```text
calibration_dataset.csv
fit_result.json
fit_candidates.json
model_selection_report.json
events.ndjson  # appended fit events
```

The CLI logs something like:

```text
Fit complete — <n> points, model=<selected_model_id>
family=<selected_model_family>
RMSE=<...> N, max_abs=<...> N
Wrote fit_result.json, fit_candidates.json, model_selection_report.json
```

### Key file to inspect

```bash
cat data/calibration/20260603_primary_cal_v1/fit_result.json
```

Important fields:

```json
{
  "selected_model_id": "...",
  "selected_model_family": "...",
  "model_parameters": {},
  "metrics": {},
  "cv_metrics": {},
  "passes_residual_threshold": true,
  "recommended_firmware_constants": {}
}
```

### Gate

Do not deploy if:

```json
"passes_residual_threshold": false
```

or if the report shows structured residuals, poor low-force behavior, hysteresis, drift, or insufficient coverage.

---

## Step 5 — Generate the primary calibration report

The `report` command takes only the session path; unlike `fit`, it does not accept `--config`.

Use:

```bash
uv run handgrip-cal report \
  data/calibration/20260603_primary_cal_v1
```

### What happens

The report generator reads session artifacts, fit artifacts, candidate rankings, residuals, and deployment metadata.

### Expected result

Files such as:

```text
calibration_report.md
calibration_report.html
plots/
```

Expected report sections include:

```text
selected model
model candidate ranking
residual plots
firmware deployment recommendation
firmware export JSON
limitations
```

### Human decision

At this point you decide whether the model is even eligible for holdout validation.

If the selected model is affine-compatible, firmware deployment is straightforward.

If the selected model is nonlinear, you need to decide whether to:

1. implement nonlinear firmware support,
2. deploy the nonlinear model in `LSL_Bridge`,
3. keep it report-only/downstream.

---

## Step 6 — Record independent holdout session before firmware deployment

This is the critical gate.

```bash
uv run handgrip-cal record \
  --config conf/protocol_holdout_verification.yaml \
  --session-id 20260603_holdout_cal_v1
```

### What happens

You record a **separate** staircase session using different force levels:

```text
0, 7, 15, 25, 45, 65, 75, 95,
75, 65, 45, 25, 15, 7, 0 N
```

This data is not used to refit. It is independent validation data.

### Expected result

A new folder:

```text
data/calibration/20260603_holdout_cal_v1/
```

with the same artifact classes:

```text
target.csv
reference.csv
events.ndjson
session_manifest.yaml
quality_live.ndjson
component_configs/
```

---

## Step 7 — Validate the saved model against the holdout session

```bash
uv run handgrip-cal validate-holdout \
  data/calibration/20260603_holdout_cal_v1 \
  --model data/calibration/20260603_primary_cal_v1/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
```

### What happens

This is the important part:

1. The tool loads the already-selected model from `fit_result.json`.
2. It segments accepted holds from the holdout session.
3. It extracts holdout `target_raw_median`.
4. It applies the selected model to predict force.
5. It compares predicted force against `reference_force_median_N`.
6. It writes validation artifacts.
7. It does **not** refit the model.

So, validation works like this:

```text
holdout target_raw_count
        ↓
saved model from fit_result.json
        ↓
predicted_force_N
        ↓ compare against
holdout reference_force_N
```

### Expected result

Files written:

```text
holdout_predictions.csv
holdout_validation.json
```

Important fields in `holdout_validation.json`:

```json
{
  "passes_holdout_gate": true,
  "firmware_deployment_recommendation": "approve_constants_for_deployment",
  "metrics": {
    "rmse_N": ...,
    "max_abs_error_N": ...,
    "bias_N": ...
  },
  "thresholds": {
    "max_rmse_N": ...,
    "max_abs_error_N": ...,
    "max_bias_N": ...
  }
}
```

Default derived thresholds, given `operating_range_N: 100.0`, are effectively:

```text
max_rmse_N      = 1.0 N
max_abs_error_N = 2.0 N
max_bias_N      = 0.5 N
```

### Gate

Only continue to firmware deployment if:

```json
"passes_holdout_gate": true
```

and residual plots do not show unacceptable structure.

---

## Step 8 — Implement model into firmware

This is the correct point to implement the model.

Not before fitting.
Not immediately after fitting.
Only after independent holdout validation passes.

Firmware is only one deployment target. Depending on the accepted model and traceability needs, the validated parameters from `fit_result.json` can instead be applied:

* **Bridge-side** — in the `LSL_Bridge` processing config, for host-side calibration and filtering. Useful when the model is nonlinear or when raw counts must stay untouched in firmware.
* **Report-only / analysis-only** — when raw-count preservation is preferred and conversion to force is applied downstream.

Preserve raw counts regardless of where conversion happens. The firmware path below is the detailed reference; bridge-side and downstream use the same `fit_result.json` parameters.

---

### Case A — Affine / linear model

If selected model is:

```text
force_N = a * raw_count + b
```

and firmware computes:

```cpp
current_units = (raw_count - SCALE_OFFSET) / SCALE_FACTOR;
```

then:

```text
SCALE_FACTOR = 1 / a
SCALE_OFFSET = -b / a
```

Only apply this if:

* `a != 0`,
* the firmware formula has not changed,
* the selected model is affine-compatible and the report recommends firmware deployment,
* post-deployment validation is run (Step 9).

The fit result usually includes this under:

```json
"recommended_firmware_constants": {
  "type": "affine_force_N_equals_a_raw_plus_b",
  "hx711_get_units_style_approximation": {
    "scale": ...,
    "offset": ...
  }
}
```

Edit:

```text
Handgrip_Firmware/Core/Inc/config.h
```

Example:

```cpp
#define SCALE_FACTOR  123.456F
#define SCALE_OFFSET  789012.0F
```

Then build/upload from repo root:

```bash
cd ..
pio run -e nanoatmega328
pio run -e nanoatmega328 -t upload
pio device monitor -e nanoatmega328 -b 115200
```

### Expected result

The firmware emits `M2` metadata showing the new scale/offset, followed by `D2` samples.

Expected semantic result:

```text
target_raw_count      still present
target_current_units  now approximately force in N
```

The raw count remains preserved, which is essential.

---

### Case B — Nonlinear model: quadratic

If the selected model is:

```text
force_N = a2 * raw_count^2 + a1 * raw_count + a0
```

then current firmware must be extended. Current firmware’s `SCALE_FACTOR` / `SCALE_OFFSET` path is not enough.

You would modify:

```text
Handgrip_Firmware/Core/Src/main.cpp
```

specifically `_raw_to_units()`.

Naive direct implementation:

```cpp
static float _raw_to_units(int32_t raw_count)
{
    const float x = (float)raw_count;
    return A2 * x * x + A1 * x + A0;
}
```

But for AVR this is numerically risky because raw counts are large and `float` is 32-bit. Better implementation:

```cpp
static float _raw_to_units(int32_t raw_count)
{
    const float dx = (float)(raw_count - RAW_CENTER);
    return C2 * dx * dx + C1 * dx + C0;
}
```

That requires converting the polynomial to a centered form before deployment.

### Expected result

Firmware still emits the same `D2` shape:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

but `current_units` is produced by the nonlinear function.

### Required caution

If metadata still only reports `scale_factor` and `scale_offset`, then nonlinear deployment is not fully represented in `M2`. Either:

1. keep `D2` unchanged and document nonlinear firmware version carefully, or
2. perform a cross-component metadata migration.

Do not casually change `D2` or `M2` shape; those are cross-component invariants. 

---

### Case C — Nonlinear model: monotone piecewise lookup table

This is often safer than quadratic on AVR.

Fit result contains something like:

```json
{
  "type": "monotone_piecewise_linear_lookup_table",
  "x_raw_knots": [...],
  "force_N_knots": [...],
  "extrapolation": "reject"
}
```

Firmware implementation pattern:

```cpp
static const int32_t RAW_KNOTS[] = {
    /* raw knot values */
};

static const float FORCE_KNOTS_N[] = {
    /* force values */
};

static float _raw_to_units(int32_t raw_count)
{
    const size_t n = sizeof(RAW_KNOTS) / sizeof(RAW_KNOTS[0]);

    if (raw_count < RAW_KNOTS[0] || raw_count > RAW_KNOTS[n - 1])
    {
        return NAN;  // or clamp, but reject is semantically cleaner
    }

    for (size_t i = 0; i < n - 1; ++i)
    {
        const int32_t x0 = RAW_KNOTS[i];
        const int32_t x1 = RAW_KNOTS[i + 1];

        if (raw_count >= x0 && raw_count <= x1)
        {
            const float y0 = FORCE_KNOTS_N[i];
            const float y1 = FORCE_KNOTS_N[i + 1];
            const float t = (float)(raw_count - x0) / (float)(x1 - x0);
            return y0 + t * (y1 - y0);
        }
    }

    return NAN;
}
```

### Expected result

The firmware now maps raw counts to force using the validated knot table.

### Gate

For nonlinear firmware, add tests before trusting it:

```text
raw knot input → expected force output
midpoint raw input → interpolated force output
below-range raw input → NAN/status
above-range raw input → NAN/status
```

---

## Step 9 — Post-deployment firmware verification

After flashing firmware, restart the live stack as needed:

```text
RS485_GUI
LSL_Bridge
LSL_Viewer
```

Then run:

```bash
cd Handgrip_Calibration

uv run handgrip-cal preflight \
  --config conf/protocol_holdout_verification.yaml

uv run handgrip-cal record \
  --config conf/protocol_holdout_verification.yaml \
  --session-id 20260603_post_fw_verify_v1
```

### What happens

You record a new independent verification session with the model now implemented in firmware.

### Expected result

New folder:

```text
data/calibration/20260603_post_fw_verify_v1/
```

At this point you need two checks.

---

## Check 9A — Model still validates from raw counts

```bash
uv run handgrip-cal validate-holdout \
  data/calibration/20260603_post_fw_verify_v1 \
  --model data/calibration/20260603_primary_cal_v1/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
```

This confirms the model still maps raw counts to reference force.

But this still does **not** directly prove `target_current_units` in firmware is correct.

---

## Check 9B — Firmware output verification

You must verify:

```text
target_current_units ≈ reference_force_N
```

on accepted holds.

Current CLI does not provide a dedicated `validate-firmware-output` command. So either:

1. add that command, or
2. do a manual/post-hoc check from `target.csv`, `reference.csv`, and `events.ndjson`.

The correct metric is no longer:

```text
model(target_raw_count) vs reference_force_N
```

but:

```text
firmware target_current_units vs reference_force_N
```

### Expected pass condition

For each accepted hold:

```text
abs(median(target_current_units) - median(reference_force_N)) <= threshold
```

with the same or stricter deployment thresholds.

---

# Final result of the full process

At the end you should have:

## Calibration artifacts

```text
data/calibration/<primary_session_id>/
  target.csv
  reference.csv
  events.ndjson
  calibration_dataset.csv
  fit_result.json
  fit_candidates.json
  model_selection_report.json
  calibration_report.md
  calibration_report.html
  plots/
```

## Holdout validation artifacts

```text
data/calibration/<holdout_session_id>/
  holdout_predictions.csv
  holdout_validation.json
  calibration_report.md
  calibration_report.html
```

## Firmware implementation

For affine:

```cpp
#define SCALE_FACTOR  <accepted scale>
#define SCALE_OFFSET  <accepted offset>
```

For nonlinear:

```cpp
static float _raw_to_units(int32_t raw_count)
{
    // accepted nonlinear model implementation
}
```

## Post-deployment verification artifacts

```text
data/calibration/<post_fw_verify_session_id>/
  target.csv
  reference.csv
  events.ndjson
  holdout_validation.json        # model/raw validation
  firmware-output verification   # currently manual or new command needed
```

## Runtime result

`LSL_Bridge` receives firmware `D2` frames where:

```text
raw_count         = preserved raw HX711 count
current_units    = calibrated force in N, if firmware deployment is valid
filtered_units   = filtered version of current_units, if bridge filter enabled
```

# FAQ

The process is **not**:

```text
fit model → put model in firmware → validate
```

The process is:

```text
record primary calibration
→ fit model
→ report/review
→ validate model on independent holdout without refitting
→ only then implement model in firmware
→ validate firmware output after deployment
```

| Question                                                                       | Answer                                                                                      |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| At which step should I implement the model into firmware?                      | **After primary fit + report + independent holdout validation pass.**                       |
| Is the current holdout validation done with the model implemented in firmware? | **No.** It applies `fit_result.json` to independent raw-count holdout data.                 |
| Is that wrong?                                                                 | **No.** It is the correct pre-deployment model validation gate.                             |
| Does that prove firmware implementation is correct?                            | **No.** Firmware output verification is a separate post-deployment step.                    |
| What should firmware validation compare?                                       | `target_current_units` against `reference_force_N`, using accepted holds.                   |
| What is the safest firmware deployment path today?                             | Affine model via `SCALE_FACTOR` / `SCALE_OFFSET`.                                           |
| What if nonlinear wins?                                                        | Validate it first, then either deploy in bridge/downstream or extend firmware deliberately. |

