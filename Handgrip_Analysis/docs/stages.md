# Handgrip Analysis Stages

## Summary

- The analysis pipeline is organized as six conceptual stages.
- Stages 1–5 characterize signal behavior under different conditions.
- Stage 6 uses the earlier characterization to review/design digital filter candidates and produce recommendations.
- Each stage must clearly state input files, required columns, output artifacts, interpretation rules, and stop conditions.

## Stage overview

| Stage   | Name                                | Purpose                                                        | Typical input                                              | Typical output                                                            |
| ------- | ----------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------- |
| Stage 1 | Startup / warm-up                   | Quantify startup drift, stabilization time, and zero behavior. | Startup or idle capture after power-on.                    | Stabilization metrics, drift plots, recommended warm-up/discard interval. |
| Stage 2 | Static rest noise                   | Characterize stationary noise and spectral content at rest.    | No-load/rest capture.                                      | Noise metrics, PSD/bandpower, narrowband component review.                |
| Stage 3 | Loaded drift / creep                | Characterize drift, creep, and zero return under static load.  | Loaded hold or static force capture.                       | Drift slopes, creep metrics, zero-return assessment.                      |
| Stage 4 | Real handgrip dynamics              | Quantify realistic grip waveform dynamics.                     | Ramp/hold/squeeze/release captures.                        | Rise/peak/release metrics, dynamic plots, event summaries.                |
| Stage 5 | Interference / condition comparison | Compare operating conditions and external interference.        | Multi-condition captures.                                  | Condition comparison table/report.                                        |
| Stage 6 | Filter design / candidate benchmark | Rank and interpret filter candidates against signal goals.     | Selected representative captures plus prior stage metrics. | Candidate comparison, recommendation YAML/report, deployment guidance.    |

## Stage 1 — Startup / warm-up

### Purpose

Determine whether the signal needs an initial warm-up/discard period before reliable use.

### Capture protocol

- Start from power-off or cold start.
- No hand contact, no load on the sensor.
- Begin recording immediately after power-on.
- Record continuously for 15–30 minutes.
- Repeat at least 5 times if possible.

### Inputs

- target or reference capture beginning near startup,
- timestamp column,
- raw or calibrated signal column,
- optional condition labels.

### Outputs

- stabilization time estimate,
- drift slope during startup,
- zero/baseline trend plot,
- recommended discard interval.

### Interpretation

Use Stage 1 to decide whether operators should wait before recording calibration or analysis captures. Do not confuse startup drift with long-term loaded creep.

## Stage 2 — Static rest noise

### Purpose

Measure the noise floor and spectral content when no force is applied.

### Capture protocol

- Wait until the sensor is thermally stable (after Stage 1 warm-up period).
- No load, no hand contact.
- Record 10–20 minutes.

### Inputs

- unloaded rest capture,
- stable timestamp/sampling information,
- signal column.

### Outputs

- RMS/std noise,
- peak-to-peak noise,
- power spectral density (PSD),
- dominant frequency peaks,
- narrowband contamination review.

### Interpretation

Use Stage 2 to decide whether low-pass or notch candidates are justified. A frequency peak visible at rest does not automatically mean a notch is required; compare it against useful handgrip bandwidth and dynamic distortion.

## Stage 3 — Loaded drift / creep

### Purpose

Measure whether the signal changes under constant load.

### Capture protocol

- After warm-up, apply a stable known load.
- Hold for 10–20 minutes.
- Optionally include pre-load and post-unload windows in the same file for zero-return assessment.

### Inputs

- static loaded hold capture,
- optional preload/release sections,
- force-level labels if available.

### Outputs

- drift slope,
- creep estimate,
- hold stability metrics,
- zero-return behavior after release.

### Interpretation

Use Stage 3 to separate sensor/fixture drift from random noise. Do not solve mechanical creep with an always-on high-pass filter unless the downstream scientific interpretation explicitly allows it.

## Stage 4 — Real handgrip dynamics

### Purpose

Characterize realistic grip events such as ramp, hold, squeeze, release, and fatigue-like behavior.

### Capture protocol

- Record one file per trial.
- Include a few seconds of quiet baseline before each grip event.
- Repeat each trial type several times.

Recommended trial types:

| Trial type       | Protocol                                                   |
| ---------------- | ---------------------------------------------------------- |
| `fast_max`       | Squeeze as fast and hard as possible, hold 1–2 s, release. |
| `ramp_hold`      | Ramp over ~1–2 s, hold 3–5 s, release.                     |
| `sustained_hold` | Fast squeeze, sustain 5–10 s, release.                     |

### Inputs

- real or controlled handgrip trials,
- event/condition labels if available,
- target signal column.

### Outputs

- peak amplitude,
- peak timing,
- rise time,
- release time,
- max derivative / slope,
- event plots.

### Interpretation

Use Stage 4 as the main dynamic realism check for candidate filters. A filter that looks smooth at rest may be unacceptable if it delays or distorts grip onset/peak/release.

## Stage 5 — Interference / condition comparison

### Purpose

Compare signal behavior across conditions: cabling, power, board mode, fixture state, filter candidate, or operator condition.

### Capture protocol

- Record one rest capture per condition.
- Change only one condition at a time.

Suggested conditions to compare:

- battery vs USB power,
- display on vs off,
- cable fixed vs intentionally disturbed,
- BLE/radio on vs off,
- enclosure open vs closed.

### Inputs

- multi-condition captures,
- condition labels,
- consistent channel mapping.

### Outputs

- comparison tables,
- condition-level plots,
- before/after metrics,
- recommendations for operating conditions.

### Interpretation

Use Stage 5 to identify environmental or setup conditions that should be fixed before software filtering is tuned.

## Stage 6 — Filter design / candidate benchmark

### Purpose

Evaluate digital filter candidates against the signal goal: preserve realistic force behavior while reducing non-essential noise/contamination.

### Capture protocol

No new capture needed. Stage 6 reuses outputs from Stage 2 (noise evidence) and Stage 4 (dynamic evidence). Ensure both are present in the manifest before running Stage 6.

### Inputs

- selected representative dynamic capture,
- rest/noise evidence from Stage 2,
- dynamic event evidence from Stage 4,
- candidate filter config.

### Outputs

- filter comparison table,
- plots showing raw vs candidates,
- metrics such as peak error, peak-time shift, rise-time shift, derivative ratio, plateau noise,
- recommendation YAML/report,
- deployment guidance.

### Interpretation

Prefer the simplest candidate that preserves dynamics and improves noise enough to justify deployment. For the current documented reassessment, the leading recommendation is a **2nd-order Butterworth low-pass at 15 Hz, fs = 100 Hz** for the primary characterization channel, with a 10 Hz low-pass as an optional stable-display channel.

## Cross-stage validation

Stage recommendations should be consistent:

- Stage 1 warm-up behavior should inform when captures begin.
- Stage 2 noise/PSD should inform filter candidates.
- Stage 3 drift/creep should inform baseline handling.
- Stage 4 dynamics should prevent over-smoothing.
- Stage 5 condition comparisons should identify setup fixes before DSP fixes.
- Stage 6 recommendations should be validated before deployment.
