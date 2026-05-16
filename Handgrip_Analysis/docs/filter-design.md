# Handgrip Analysis Filter Design

## Summary

- Filter design is a decision workflow, not just a smoothing operation.
- Stage 6 compares candidate filters against dynamic fidelity, noise reduction, distortion, and deployment complexity.
- Current documented recommendation: primary characterization channel should use a **2nd-order Butterworth low-pass at 15 Hz, fs = 100 Hz** when the active data profile matches the refreshed artifact-fixed captures.
- A **2nd-order Butterworth low-pass at 10 Hz** can be used as an optional stable-display channel, not necessarily as the primary scientific characterization channel.
- High-pass, band-pass, and notch filters should not be deployed simply because they are available; they must be justified by metrics and waveform behavior.

## Candidate review workflow

### Step 1 — Frame the signal goal

Decide what the filter must preserve:

- peak force,
- onset timing,
- rise time,
- release behavior,
- hold/plateau stability,
- low-force behavior,
- fatigue/dynamic features.

### Step 2 — Inspect rest/noise evidence

Use Stage 2 outputs:

- standard deviation / RMS noise,
- PSD peaks,
- narrowband contamination,
- baseline drift.

Do not jump to a notch/high-pass filter just because one frequency peak exists. Compare against useful handgrip bandwidth and dynamic distortion.

### Step 3 — Select representative dynamic capture

Use a capture with baseline, rise, hold, and release. The current filter reassessment used a ramp/hold-like trial because it stresses both waveform fidelity and hold stability.

### Step 4 — Build candidate bank

Candidate families to include when relevant:

| Family            | When to test                                                                        | Main risk                                               |
| ----------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------- |
| identity/raw      | Always include baseline.                                                            | None; provides comparison reference.                    |
| low-pass          | High-frequency contamination without needing baseline removal.                      | Over-smoothing, peak error, delayed/flattened dynamics. |
| notch/band-reject | Confirmed narrowband contamination that survives low-pass or is in useful band.     | Ringing, unnecessary complexity.                        |
| high-pass         | Baseline drift must be removed and force DC/slow components are not meaningful.     | Destroys static force interpretation.                   |
| band-pass         | Signal is known to occupy a bounded dynamic band and DC/static force is not needed. | Usually wrong for force magnitude channels.             |

### Step 5 — Evaluate metrics

Important Stage 6 metrics:

| Metric                     | Meaning                                     |
| -------------------------- | ------------------------------------------- |
| peak error                 | Force/count amplitude distortion.           |
| peak-time shift            | Timing shift of maximum force.              |
| rise-time shift            | Distortion of onset/rise behavior.          |
| max dF/dt ratio            | Slope/dynamic suppression.                  |
| plateau standard deviation | Stability/noise during hold.                |
| rest noise impact          | Noise reduction in unloaded/rest condition. |

### Step 6 — Interpret candidate ranking

Prefer the simplest candidate that:

- reduces non-essential noise,
- keeps peak and timing errors acceptable,
- preserves rise/release dynamics,
- does not hide mechanical or sensor problems,
- can be deployed in the intended target component.

## Current recommendation pattern

Based on the current filter reassessment source report:

| Role                             | Recommendation                                       | Rationale                                                                 |
| -------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------- |
| Primary characterization channel | 2nd-order Butterworth low-pass at 15 Hz, fs = 100 Hz | Best realism/noise tradeoff after outlier artifact fix.                   |
| Optional stable-display channel  | 2nd-order Butterworth low-pass at 10 Hz, fs = 100 Hz | Smoother display; more dynamic suppression.                               |
| Baseline handling                | State-based tare and unloaded-only baseline tracking | Avoids corrupting grip-event DC/slow force content.                       |
| High-pass                        | Not recommended for primary force channel            | Distorts ramp/hold events and removes meaningful slow/static force.       |
| Band-pass                        | Not recommended for primary force channel            | Same high-pass problem plus low-pass constraints.                         |
| Notch/band-reject                | Not needed in main path for current data             | Low-pass addresses high-frequency contamination without notch complexity. |

## Deployment targets

| Target                    | When appropriate                                                     | Validation required                                                           |
| ------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `LSL_Bridge` processing   | Filtered stream should be available to viewer/calibration consumers. | Live stream comparison, timestamp/latency review, calibration residual check. |
| `LSL_Viewer` display only | Smoothing is purely visual/operator-facing.                          | Confirm raw data and saved outputs are unchanged.                             |
| Firmware                  | Filter must exist on-device.                                         | Rebuild/upload, D2 validation, repeat calibration/holdout checks.             |
| Analysis only             | Filter supports reports/plots but not live deployment.               | Ensure reports label filtered vs raw outputs clearly.                         |

## What to do after selecting a filter

1. Save the Stage 6 report and metrics.
2. Save the recommendation YAML or equivalent machine-readable output.
3. Decide deployment target.
4. Apply config/code change in the target component.
5. Run validation subset:
   - raw vs filtered plot,
   - latency/phase check,
   - peak/rise/release check,
   - calibration residual comparison if calibration uses filtered output.
6. Update docs/config references to reflect the deployed filter.

## Stop conditions

Do not deploy the selected filter if:

- identity/raw baseline is missing from comparison,
- candidate metrics cannot be traced to source data,
- filter improves visual smoothness but distorts rise/peak/release behavior,
- cutoff frequency is invalid for the actual sampling rate,
- report does not distinguish offline zero-phase vs real-time causal behavior,
- recommendation is based on a single unrepresentative capture.
