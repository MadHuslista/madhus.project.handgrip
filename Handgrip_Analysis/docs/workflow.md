# Handgrip_Analysis → LSL_Bridge production-filter workflow

## Summary

You are starting **after calibration is complete**:

```text
Handgrip_Calibration completed
→ model selected
→ model validated on holdout
→ model implemented in firmware
→ firmware output verified
→ LSL_Bridge is alive
→ HandgripTarget + HandgripReference streams exist
```

The goal now is:

```text
firmware calibrated force
→ Handgrip_Analysis staged characterization
→ Stage 6 production-equivalent filter selection
→ LSL_Bridge filter config update
→ deployed-filter validation
→ Handgrip Suite production-ready
```

The key stream contract inherited from calibration is:

```text
HandgripTarget:
  target_raw_count
  target_current_units
  target_filtered_units

HandgripReference:
  reference_force_N
```

The attached calibration workflow defines `HandgripTarget`, `HandgripReference`, `target_raw_count`, and `reference_force_N` as canonical invariants, and maps `current_units` to `target_current_units` and `filtered` to `target_filtered_units`. 

After the latest `Handgrip_Analysis` fix, the analysis library now supports:

```text
raw           → target_raw_count
current_units → target_current_units
filtered      → target_filtered_units
```

So the clean production-filter workflow should use:

```bash
channel=current_units
```

for filter **design**, because the firmware model is already implemented and `target_current_units` is the calibrated force signal.

---

## Production meaning of each signal

After firmware calibration is deployed and verified:

| Signal                  | Meaning                        | Use in this workflow                                                                       |
| ----------------------- | ------------------------------ | ------------------------------------------------------------------------------------------ |
| `target_raw_count`      | Raw HX711 ADC count            | Audit/debug; not the filter-design signal once nonlinear firmware calibration is possible. |
| `target_current_units`  | Firmware-calibrated force in N | **Primary input for Handgrip_Analysis Stage 1–6.**                                         |
| `target_filtered_units` | LSL_Bridge filtered force in N | Production output after filter deployment.                                                 |
| `reference_force_N`     | PM58/reference force in N      | External validation reference.                                                             |

Important: if the firmware model is nonlinear, filtering `target_raw_count` is **not equivalent** to filtering calibrated force. Therefore, use `current_units` for analysis and filter design.

---

## High-level process

```text
Step 1  — Prepare environment
Step 2  — Put LSL_Bridge in unfiltered/identity capture mode
Step 3  — Capture Stage 1 startup/warm-up trial(s)
Step 4  — Capture Stage 2 static rest-noise trial(s)
Step 5  — Capture Stage 3 loaded drift/creep trial(s)
Step 6  — Capture Stage 4 dynamic handgrip trial(s)
Step 7  — Capture Stage 5 interference/condition comparison trial(s)
Step 8  — Build the Handgrip_Analysis manifest
Step 9  — Run Stages 1–5
Step 10 — Run Stage 6 filter design
Step 11 — Review selected filter artifacts
Step 12 — Implement selected filter in LSL_Bridge
Step 13 — Restart LSL_Bridge with selected filter
Step 14 — Validate deployed live filter
Step 15 — Freeze production configuration
```

---

## Step 1 — Prepare environment

Run from repo root:

```bash
uv sync
```

Then verify both tools (all `uv run ha-...` commands in this workflow can be
run from the repo root or from `Handgrip_Analysis/` — `data/...` and
`conf/...` paths resolve to `Handgrip_Analysis/data/...` and
`Handgrip_Analysis/conf/...` either way):

```bash
uv run ha-stage --help
uv run ha-run-all --help
uv run ha-stage6-design --help

cd LSL_Bridge
uv run lsl-bridge --help
```

### What happens

`uv sync` installs local editable packages and dependencies. The CLI entry points become available.

### Expected result

The following commands should exist:

```text
ha-stage
ha-stage1
ha-stage2
ha-stage3
ha-stage4
ha-stage5
ha-stage6-design
ha-stage6-review
ha-run-all
```

### Stop condition

Stop if any CLI cannot import. Do not collect new production data with a broken analysis environment.

---

## Step 2 — Put LSL_Bridge in unfiltered capture mode

Before designing a filter, capture **unfiltered calibrated force**.

Edit:

```text
LSL_Bridge/conf/config.yaml
```

Use either an empty filter chain:

```yaml
processing:
  module: lsl_bridge.core.filter
  timestamp_source: device_clock_us
  filters: []
```

or explicit identity:

```yaml
processing:
  module: lsl_bridge.core.filter
  timestamp_source: device_clock_us
  filters:
    - type: identity
      name: identity_for_analysis_capture
```

Start bridge:

```bash
cd LSL_Bridge

uv run lsl-bridge \
  serial.port=/dev/ttyUSB1 \
  csv.target.enabled=true \
  csv.reference.enabled=true
```

Adjust `serial.port` as needed.

### What happens

`LSL_Bridge` reads firmware `D2` frames and publishes the target stream. With no/identity filtering:

```text
target_filtered_units == target_current_units
```

But the analysis will now use `channel=current_units`, so this equality is no longer required for Stage 6 correctness. It is still useful as a sanity check.

### Expected result

`LSL_Bridge/data/target_handgrip_samples_v2.csv` is produced with columns including:

```text
device_clock_us
target_raw_count
target_current_units
target_filtered_units
```

### Stop condition

Stop if `target_current_units` is not in Newtons or was not verified against `reference_force_N`. The calibration workflow explicitly states that post-firmware validation must compare firmware `target_current_units` against `reference_force_N`; applying `fit_result.json` to raw counts does not prove the firmware implementation itself. 

---

## Step 3 — Capture Stage 1: startup / warm-up

### Why

Stage 1 answers:

```text
How long after power-on should operators wait before trusting the force signal?
```

It measures startup drift, stabilization time, and baseline behavior.

### Capture protocol

1. Power off the handgrip target.
2. Start `LSL_Bridge` CSV capture.
3. Power on the handgrip target.
4. Do not touch or load the sensor.
5. Record 15–30 minutes.
6. Repeat multiple times if practical.

### Save the file

After the trial, copy the bridge CSV:

```bash
mkdir -p Handgrip_Analysis/data/calibration_signals

cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage1_cold_start_trial01.csv
```

### Manifest row

```csv
stage,condition,trial_type,trial_id,session_id,path,channel,load_nominal_n,include,notes
stage1,cold_start,startup,trial01,20260604,../calibration_signals/20260604_stage1_cold_start_trial01.csv,current_units,,true,post-firmware calibrated force startup capture
```

### Execute Stage 1

```bash
uv run ha-stage1 \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage1 \
  channel=current_units \
  time_source=auto \
  warmup_window_s=10.0
```

Equivalent generic command:

```bash
uv run ha-stage \
  stage=stage1 \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage1 \
  channel=current_units \
  time_source=auto \
  warmup_window_s=10.0
```

### What happens

Stage 1 loads the CSV, selects `target_current_units`, estimates sampling timing, computes rolling mean/std/slope, and estimates a suggested ready time.

### Expected outputs

```text
data/analysis_results/production/stage1/
  plan.json
  per_trial_metrics.csv
  condition_summary.csv
  summary.json
  figures/
  tables/
```

Important metrics:

```text
suggested_ready_time_s
final_mean
final_std
final_abs_slope
sampling_fs_median_hz
```

### Result meaning

You get the recommended warm-up/discard rule, for example:

```text
Wait 180 s after firmware startup before production measurements.
```

---

## Step 4 — Capture Stage 2: static rest noise

### Why

Stage 2 answers:

```text
How noisy is the calibrated force signal at rest?
What frequency bands contain noise?
Is low-pass filtering justified?
```

This is one of the main inputs to Stage 6.

### Capture protocol

1. Wait until Stage 1 warm-up time has passed.
2. No hand contact.
3. No load.
4. Record 10–20 minutes.
5. Repeat at least 2–5 times if practical.

### Save the file

```bash
cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage2_rest_after_warmup_trial01.csv
```

### Manifest row

```csv
stage2,rest_after_warmup,rest,trial01,20260604,../calibration_signals/20260604_stage2_rest_after_warmup_trial01.csv,current_units,,true,quiet rest noise after warm-up
```

### Execute Stage 2

```bash
uv run ha-stage2 \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage2 \
  channel=current_units \
  time_source=auto
```

### What happens

Stage 2 computes rest-noise statistics, PSD, Allan deviation, bandpower, and dominant PSD peaks using `target_current_units`.

### Expected outputs

```text
data/analysis_results/production/stage2/
  plan.json
  per_trial_metrics.csv
  condition_summary.csv
  summary.json
  tables/
    current_units_psd.csv
    current_units_allan.csv
    current_units_psd_peaks.csv
  figures/
```

Important metrics:

```text
current_units_std
current_units_robust_std
current_units_rms
current_units_peak_to_peak
current_units_top_peak_hz
current_units_top_peak_prominence_db
bandpower_*_hz
```

### Result meaning

You get the noise floor and spectral evidence that justifies or rejects smoothing.

---

## Step 5 — Capture Stage 3: loaded drift / creep

### Why

Stage 3 answers:

```text
Does calibrated force drift under constant load?
Does it return to zero after unloading?
Is there creep that should be treated mechanically/procedurally instead of filtered away?
```

### Capture protocol

1. Warm up.
2. Apply a stable known load or controlled static handgrip force.
3. Hold 10–20 minutes.
4. Optionally include pre-load and post-unload windows.
5. Repeat for relevant load levels.

### Save the file

```bash
cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage3_loaded_40N_trial01.csv
```

### Manifest row

```csv
stage3,loaded_40N,loaded_hold,trial01,20260604,../calibration_signals/20260604_stage3_loaded_40N_trial01.csv,current_units,40,true,static loaded drift/creep check
```

### Execute Stage 3

```bash
uv run ha-stage3 \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage3 \
  channel=current_units \
  time_source=auto \
  pre_window_s=10.0 \
  post_window_s=10.0
```

### What happens

Stage 3 fits a linear trend to the calibrated force signal, computes drift slope, compares pre/post windows, and estimates zero-return error.

### Expected outputs

```text
data/analysis_results/production/stage3/
  plan.json
  per_trial_metrics.csv
  condition_summary.csv
  summary.json
  figures/
```

Important metrics:

```text
drift_slope_per_s
drift_slope_per_min
pre_window_mean
post_window_mean
return_to_zero_error
detrended_std
```

### Result meaning

You decide whether baseline drift is acceptable, whether a warm-up/loading protocol is needed, or whether mechanics/fixture need correction before DSP filter tuning.

Do **not** solve load-path creep by blindly adding high-pass filtering if absolute force matters.

---

## Step 6 — Capture Stage 4: real handgrip dynamics

### Why

Stage 4 answers:

```text
What does a real useful grip waveform look like?
How fast are onset, peak, hold, and release?
What distortion limits must the filter respect?
```

Stage 4 is the other main input to Stage 6.

### Capture protocol

Record one file per trial type.

Recommended trial types:

```text
fast_max:
  squeeze fast and hard, hold 1–2 s, release

ramp_hold:
  ramp over 1–2 s, hold 3–5 s, release

sustained_hold:
  squeeze, sustain 5–10 s, release
```

Include a quiet baseline of a few seconds before each event.

### Save files

```bash
cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage4_fast_max_trial01.csv

cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage4_ramp_hold_trial01.csv

cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage4_sustained_hold_trial01.csv
```

### Manifest rows

```csv
stage4,fast_max,fast_max,trial01,20260604,../calibration_signals/20260604_stage4_fast_max_trial01.csv,current_units,,true,fast maximum voluntary contraction
stage4,ramp_hold,ramp_hold,trial01,20260604,../calibration_signals/20260604_stage4_ramp_hold_trial01.csv,current_units,,true,ramp hold release
stage4,sustained_hold,sustained_hold,trial01,20260604,../calibration_signals/20260604_stage4_sustained_hold_trial01.csv,current_units,,true,sustained force hold
```

### Execute Stage 4

```bash
uv run ha-stage4 \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage4 \
  channel=current_units \
  time_source=auto \
  baseline_s=2.0 \
  threshold_sigma=5.0 \
  min_duration_s=0.20 \
  merge_gap_s=0.15 \
  pad_s=0.25
```

### What happens

Stage 4 detects grip events and computes event-level metrics:

```text
peak force
peak timing
rise time
release behavior
max derivative
hold noise
```

### Expected outputs

```text
data/analysis_results/production/stage4/
  plan.json
  per_trial_metrics.csv
  condition_summary.csv
  summary.json
  tables/
    event_metrics.csv
    hold_psd.csv
  figures/
```

Important metrics:

```text
n_events
peak_value_max
peak_value_median
rise_10_90_s_median
max_dfdt_max
hold_std_last_20pct_median
```

### Result meaning

You get the dynamic constraints that Stage 6 must preserve. A filter that reduces rest noise but suppresses peak force or delays the peak too much should be rejected.

---

## Step 7 — Capture Stage 5: interference / condition comparison

### Why

Stage 5 answers:

```text
Is the noise/filter problem actually caused by an external condition?
```

Use this before over-tuning DSP.

### Capture protocol

Record rest/no-load captures while changing one condition at a time:

```text
USB power vs battery power
cable fixed vs cable moved
RS485 adapter A vs adapter B
display/board mode A vs B
near EMI source vs away from EMI source
```

### Save files

```bash
cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage5_usb_power_trial01.csv

cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_stage5_battery_power_trial01.csv
```

### Manifest rows

```csv
stage5,usb_power,interference_rest,trial01,20260604,../calibration_signals/20260604_stage5_usb_power_trial01.csv,current_units,,true,rest noise on USB power
stage5,battery_power,interference_rest,trial01,20260604,../calibration_signals/20260604_stage5_battery_power_trial01.csv,current_units,,true,rest noise on battery power
```

### Execute Stage 5

```bash
uv run ha-stage5 \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage5 \
  channel=current_units \
  time_source=auto
```

### What happens

Stage 5 computes per-condition noise and PSD metrics, then lets you compare conditions.

### Expected outputs

```text
data/analysis_results/production/stage5/
  plan.json
  per_trial_metrics.csv
  condition_summary.csv
  summary.json
  tables/
    psd.csv
    psd_peaks.csv
  figures/
```

### Result meaning

If one condition is much noisier, fix the condition before deploying a more aggressive filter.

---

## Step 8 — Build the full production analysis manifest

Create:

```text
Handgrip_Analysis/data/manifests/production_analysis_manifest.csv
```

Example complete manifest:

```csv
stage,condition,trial_type,trial_id,session_id,path,channel,load_nominal_n,include,notes
stage1,cold_start,startup,trial01,20260604,../calibration_signals/20260604_stage1_cold_start_trial01.csv,current_units,,true,post-firmware calibrated force startup capture
stage2,rest_after_warmup,rest,trial01,20260604,../calibration_signals/20260604_stage2_rest_after_warmup_trial01.csv,current_units,,true,quiet rest noise after warm-up
stage3,loaded_40N,loaded_hold,trial01,20260604,../calibration_signals/20260604_stage3_loaded_40N_trial01.csv,current_units,40,true,static loaded drift check
stage4,fast_max,fast_max,trial01,20260604,../calibration_signals/20260604_stage4_fast_max_trial01.csv,current_units,,true,fast max grip
stage4,ramp_hold,ramp_hold,trial01,20260604,../calibration_signals/20260604_stage4_ramp_hold_trial01.csv,current_units,,true,ramp hold release
stage4,sustained_hold,sustained_hold,trial01,20260604,../calibration_signals/20260604_stage4_sustained_hold_trial01.csv,current_units,,true,sustained hold
stage5,usb_power,interference_rest,trial01,20260604,../calibration_signals/20260604_stage5_usb_power_trial01.csv,current_units,,true,USB power rest condition
stage5,battery_power,interference_rest,trial01,20260604,../calibration_signals/20260604_stage5_battery_power_trial01.csv,current_units,,true,battery power rest condition
stage6,rest_after_warmup,rest,trial01,20260604,../calibration_signals/20260604_stage2_rest_after_warmup_trial01.csv,current_units,,true,Stage 6 rest evidence from Stage 2
stage6,fast_max,fast_max,trial01,20260604,../calibration_signals/20260604_stage4_fast_max_trial01.csv,current_units,,true,Stage 6 dynamic evidence from Stage 4
stage6,ramp_hold,ramp_hold,trial01,20260604,../calibration_signals/20260604_stage4_ramp_hold_trial01.csv,current_units,,true,Stage 6 dynamic evidence from Stage 4
stage6,sustained_hold,sustained_hold,trial01,20260604,../calibration_signals/20260604_stage4_sustained_hold_trial01.csv,current_units,,true,Stage 6 dynamic evidence from Stage 4
```

### Why Stage 6 duplicates Stage 2/4 files

Stage 6 does not require new capture. It reuses:

```text
Stage 2 rest/noise evidence
Stage 4 dynamic waveform evidence
```

The duplicate manifest rows tell the pipeline to use those same files for Stage 6.

---

## Step 9 — Run Stages 1–5

You can run each stage separately, or run them as a batch.

### Recommended batch command

```bash
uv run ha-run-all \
  manifest=data/manifests/production_analysis_manifest.csv \
  base_outdir=data/analysis_results/production \
  stages=stage1,stage2,stage3,stage4,stage5 \
  channel=current_units \
  time_source=auto
```

### What happens

The pipeline loads the manifest, filters rows by stage, executes each stage, and writes artifacts under:

```text
data/analysis_results/production/stage1/
data/analysis_results/production/stage2/
data/analysis_results/production/stage3/
data/analysis_results/production/stage4/
data/analysis_results/production/stage5/
```

### Expected result

You get baseline characterization before filter design:

```text
Stage 1 → warm-up/discard rule
Stage 2 → rest noise + PSD
Stage 3 → loaded drift/creep behavior
Stage 4 → dynamic grip waveform metrics
Stage 5 → condition/interference comparison
```

---

## Step 10 — Configure Stage 6

Stage 6 needs one key config file:

```text
Handgrip_Analysis/conf/filters/candidates.yaml
```

The current production-filter candidate set is intentionally constrained to LSL_Bridge-deployable filters:

```text
identity
butterworth_lowpass_2nd
lowpass_1pole
```

Typical active candidates include:

```text
butter_lowpass_3hz
butter_lowpass_4hz
...
butter_lowpass_25hz

one_pole_lowpass_4hz
one_pole_lowpass_6hz
...
one_pole_lowpass_20hz
```

The Stage 6 scoring policy is controlled by:

```text
Handgrip_Analysis/conf/analysis/stage6.yaml
```

Current weights:

```yaml
filter_weights:
  rest_std_norm: 0.25
  mean_peak_relative_error: 0.35
  mean_rise_relative_error: 0.10
  mean_peak_time_shift_norm: 0.10
  mean_dfdt_deviation: 0.20
```

### Why these settings matter

| Parameter                   | Why it matters                                        |
| --------------------------- | ----------------------------------------------------- |
| `rest_std_norm`             | Rewards noise reduction at rest.                      |
| `mean_peak_relative_error`  | Penalizes peak-force suppression.                     |
| `mean_rise_relative_error`  | Penalizes onset/rise distortion.                      |
| `mean_peak_time_shift_norm` | Penalizes latency / timing shift.                     |
| `mean_dfdt_deviation`       | Penalizes excessive smoothing of force-rate dynamics. |

Do not change weights unless you intentionally change the clinical/product priority.

---

## Step 11 — Run Stage 6 filter design

### Command

```bash
uv run ha-stage6-design \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage6 \
  filter_config=conf/filters/candidates.yaml \
  channel=current_units \
  time_source=auto \
  lsl_bridge_config=../LSL_Bridge/conf/config.yaml
```

Alternative generic command:

```bash
uv run ha-stage \
  stage=stage6 \
  manifest=data/manifests/production_analysis_manifest.csv \
  outdir=data/analysis_results/production/stage6 \
  filter_config=conf/filters/candidates.yaml \
  channel=current_units \
  time_source=auto \
  lsl_bridge_config=../LSL_Bridge/conf/config.yaml
```

### What happens

Stage 6:

1. Loads Stage 6 manifest rows.
2. Reads `target_current_units`.
3. Loads production-deployable filter candidates.
4. Simulates each filter with causal, per-sample, LSL_Bridge-equivalent behavior.
5. Computes rest-noise and dynamic-distortion metrics.
6. Scores each candidate.
7. Selects the final filter.
8. Writes a machine-readable LSL_Bridge config recommendation.

### Expected outputs

```text
data/analysis_results/production/stage6/
  plan.json
  per_trial_metrics.csv
  condition_summary.csv
  summary.json

  filter_per_trial_metrics.csv
  filter_validation_scores.csv
  filter_ranking_summary.csv
  filter_design_assessment.csv
  filter_decision_summary.csv
  filter_acceptance_report.md
  stage6_review_design_report.md
  selected_filter_recommendation.json
  lsl_bridge_processing_recommendation.yaml

  tables/
  figures/
```

### Most important files

| File                                        | Purpose                           |
| ------------------------------------------- | --------------------------------- |
| `filter_decision_summary.csv`               | Final decision table.             |
| `stage6_review_design_report.md`            | Human-readable justification.     |
| `filter_acceptance_report.md`               | Acceptance/rejection summary.     |
| `selected_filter_recommendation.json`       | Machine-readable selected filter. |
| `lsl_bridge_processing_recommendation.yaml` | Snippet to apply in LSL_Bridge.   |

---

## Step 12 — Review Stage 6 result

Inspect:

```bash
cat data/analysis_results/production/stage6/filter_decision_summary.csv
cat data/analysis_results/production/stage6/selected_filter_recommendation.json
cat data/analysis_results/production/stage6/lsl_bridge_processing_recommendation.yaml
```

Expected recommendation shape:

```yaml
processing:
  filters:
    - type: butterworth_lowpass_2nd
      name: butter_lowpass_9hz
      sample_rate_hz: 100.0
      cutoff_hz: 9.0
      q: 0.7071067811865476
      reset_on_gap_s: 1.0
      min_dt_s: 0.000001
```

### Decision gate

Accept the computed filter only if:

```text
1. Rest noise improves enough to matter.
2. Peak force error is acceptable.
3. Rise-time distortion is acceptable.
4. Peak timing shift is acceptable.
5. df/dt distortion is acceptable.
6. Filter type is deployable in LSL_Bridge.
7. The selected filter is not winning only because bad/noisy trials biased the score.
```

Because of the S4 changes, Stage 6 active filters are production-equivalent by construction.

---

## Step 13 — Implement computed filter into LSL_Bridge

This is the correct point to implement the computed filter:

```text
after Stage 6 design
after Stage 6 report review
after human acceptance of selected filter
```

Edit:

```text
LSL_Bridge/conf/config.yaml
```

Replace the temporary identity/empty filter with the selected recommendation:

```yaml
processing:
  module: lsl_bridge.core.filter
  timestamp_source: device_clock_us
  filters:
    - type: butterworth_lowpass_2nd
      name: butter_lowpass_9hz
      sample_rate_hz: 100.0
      cutoff_hz: 9.0
      q: 0.7071067811865476
      reset_on_gap_s: 1.0
      min_dt_s: 0.000001
```

### What happens

`LSL_Bridge` will now compute:

```text
target_filtered_units = selected_filter(target_current_units)
```

### Expected result

Runtime stream semantics become:

```text
target_raw_count       raw ADC count, preserved
target_current_units   calibrated force in N from firmware
target_filtered_units  calibrated filtered force in N from LSL_Bridge
```

---

## Step 14 — Restart LSL_Bridge

```bash
cd LSL_Bridge

uv run lsl-bridge \
  serial.port=/dev/ttyUSB1 \
  csv.target.enabled=true \
  csv.reference.enabled=true
```

### What happens

`LSL_Bridge` loads the configured processing module and instantiates the selected filter.

Supported relevant production filter types:

```text
identity
butterworth_lowpass_2nd
biquad_lowpass
butter_lowpass       # compatibility alias, order 2 only
lowpass_1pole
one_pole_lowpass     # compatibility alias
```

Prefer the native Stage 6 output names:

```text
butterworth_lowpass_2nd
lowpass_1pole
identity
```

### Expected result

Bridge logs should show the processor initialized, and the target CSV should now show:

```text
target_current_units != target_filtered_units
```

when the selected filter is active, except for identity or constant signals.

---

## Step 15 — Validate the deployed filter

### Important distinction

Stage 6 validation is **pre-deployment design validation**:

```text
saved current_units CSV
→ simulated production-equivalent filters
→ selected filter
```

It is valid because the simulation matches LSL_Bridge filter semantics.

But production readiness still requires **post-deployment validation**:

```text
LSL_Bridge running selected filter live
→ target_current_units and target_filtered_units recorded
→ verify deployed behavior
```

So the final validation is done **with the computed filter implemented on LSL_Bridge**.

### Capture validation trials

With selected filter enabled, record:

```text
rest_after_warmup
fast_max
ramp_hold
sustained_hold
optional loaded hold
optional interference condition
```

Save:

```bash
cp LSL_Bridge/data/target_handgrip_samples_v2.csv \
  Handgrip_Analysis/data/calibration_signals/20260604_deployed_filter_fast_max_trial01.csv
```

### Build deployed-filter validation manifest

Create:

```text
Handgrip_Analysis/data/manifests/deployed_filter_validation_manifest.csv
```

Use two rows per file if you want to compare calibrated unfiltered vs deployed filtered:

```csv
stage,condition,trial_type,trial_id,session_id,path,channel,load_nominal_n,include,notes
stage2,deployed_rest_current,rest,trial01,20260604,../calibration_signals/20260604_deployed_filter_rest_trial01.csv,current_units,,true,unfiltered calibrated force after filter deployment
stage2,deployed_rest_filtered,rest,trial01,20260604,../calibration_signals/20260604_deployed_filter_rest_trial01.csv,filtered,,true,deployed filtered force
stage4,deployed_fast_current,fast_max,trial01,20260604,../calibration_signals/20260604_deployed_filter_fast_max_trial01.csv,current_units,,true,unfiltered calibrated force after filter deployment
stage4,deployed_fast_filtered,fast_max,trial01,20260604,../calibration_signals/20260604_deployed_filter_fast_max_trial01.csv,filtered,,true,deployed filtered force
```

### Run validation stages

```bash
uv run ha-run-all \
  manifest=data/manifests/deployed_filter_validation_manifest.csv \
  base_outdir=data/analysis_results/deployed_filter_validation \
  stages=stage2,stage4 \
  time_source=auto
```

### What happens

Stage 2 compares rest-noise behavior of `current_units` vs `filtered`.

Stage 4 compares dynamic behavior of `current_units` vs `filtered`.

### Expected outputs

```text
data/analysis_results/deployed_filter_validation/stage2/
data/analysis_results/deployed_filter_validation/stage4/
```

Expected checks:

```text
rest filtered std < current_units std
filtered peak error acceptable
filtered peak-time shift acceptable
filtered rise-time distortion acceptable
no NaN/inf output
no startup transient contaminates usable window
```

---

## Step 16 — Optional reference-force validation after filter deployment

If the reference stream is still available, do a final sanity check:

```text
target_current_units ≈ reference_force_N
target_filtered_units ≈ smoothed reference-compatible force
```

Do **not** expect `target_filtered_units` to equal `reference_force_N` sample-by-sample during fast dynamics, because filtering intentionally changes timing/amplitude slightly.

Use reference mostly for:

```text
static holds
slow ramps
gross sanity
post-deployment regression evidence
```

The calibration workflow explicitly separates raw-model validation from firmware-output validation; firmware-output validation must compare `target_current_units` to `reference_force_N`. 

---

## Step 17 — Freeze production configuration

After deployment validation passes, preserve:

```text
LSL_Bridge/conf/config.yaml
Handgrip_Analysis/conf/filters/candidates.yaml
Handgrip_Analysis/conf/analysis/stage6.yaml
Handgrip_Firmware calibration model/constants
Stage 1–6 analysis artifacts
Deployed-filter validation artifacts
```

Recommended Git commit message:

```bash
git add Handgrip_Analysis LSL_Bridge Handgrip_Firmware
git commit -m "Validate and deploy production handgrip filter"
```

Recommended production record:

```text
Firmware model:
  version / commit / constants / nonlinear coefficients

LSL_Bridge filter:
  type
  cutoff_hz
  sample_rate_hz
  q
  reset_on_gap_s
  min_dt_s

Validation:
  calibration primary session
  calibration holdout session
  firmware-output verification session
  analysis Stage 1–6 session
  deployed-filter validation session
```

---

## Final deliverables

At the end, a production-ready Handgrip Suite should have:

### Calibration side

```text
Handgrip_Calibration/data/calibration/<primary>/
  fit_result.json
  fit_candidates.json
  model_selection_report.json
  calibration_report.md
  calibration_report.html

Handgrip_Calibration/data/calibration/<holdout>/
  holdout_predictions.csv
  holdout_validation.json

Handgrip_Calibration/data/calibration/<post_fw_verify>/
  target.csv
  reference.csv
  firmware-output verification evidence
```

### Firmware side

```text
Handgrip_Firmware:
  calibrated model implemented
  raw_count preserved
  current_units = calibrated force in N
```

### Analysis side

```text
Handgrip_Analysis/data/analysis_results/production/
  stage1/
  stage2/
  stage3/
  stage4/
  stage5/
  stage6/
```

Most important Stage 6 files:

```text
stage6/filter_decision_summary.csv
stage6/stage6_review_design_report.md
stage6/filter_acceptance_report.md
stage6/selected_filter_recommendation.json
stage6/lsl_bridge_processing_recommendation.yaml
```

### Bridge side

```text
LSL_Bridge/conf/config.yaml
```

with selected production filter under:

```yaml
processing:
  filters:
    - type: <selected_filter_type>
      ...
```

### Final runtime behavior

```text
HandgripTarget:
  target_raw_count       preserved raw ADC count
  target_current_units   calibrated force in N from firmware
  target_filtered_units  production filtered force in N from LSL_Bridge

HandgripReference:
  reference_force_N      reference force in N
```

---

## Direct answers

### What is the first step?

Verify the calibrated firmware output is valid and configure `LSL_Bridge` for unfiltered/identity capture before collecting analysis data.

### On which steps are the stages executed?

```text
Stage 1 → Step 3 / Step 9
Stage 2 → Step 4 / Step 9
Stage 3 → Step 5 / Step 9
Stage 4 → Step 6 / Step 9
Stage 5 → Step 7 / Step 9
Stage 6 → Step 11
```

### What channel should the stages use?

Use:

```bash
channel=current_units
```

because the firmware model is already implemented and `target_current_units` is the calibrated force signal.

### How should I use the computed filter?

Copy `stage6/lsl_bridge_processing_recommendation.yaml` into `LSL_Bridge/conf/config.yaml` under `processing.filters`, then restart `LSL_Bridge`.

### At which step should I implement the computed filter into LSL_Bridge?

After Stage 6 completes and the recommendation is reviewed:

```text
Stage 6 complete
→ inspect reports
→ accept selected filter
→ edit LSL_Bridge/conf/config.yaml
→ restart LSL_Bridge
→ validate deployed filter
```

### Is validation done with the computed filter implemented on LSL_Bridge?

There are two layers:

| Validation                 | Filter implemented in LSL_Bridge? | Purpose                                                                                      |
| -------------------------- | --------------------------------: | -------------------------------------------------------------------------------------------- |
| Stage 6 design validation  |                                No | Simulates production-equivalent filters on saved `current_units` data.                       |
| Deployed-filter validation |                               Yes | Records live `target_current_units` and `target_filtered_units` after LSL_Bridge is updated. |

Both are needed. Stage 6 selects the filter; deployed-filter validation proves the live production path behaves as intended.

