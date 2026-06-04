# Handgrip Analysis Filter Design

## Summary

- Filter design is a decision workflow, not just a smoothing operation.
- Stage 6 is **production-contract-first**: active candidates are restricted to filters that map 1:1 to an `LSL_Bridge` `processing.filters` entry and are evaluated with the same causal, timestamp-aware per-sample implementation used for live streaming. Offline-only filters can no longer win a Stage 6 ranking.
- Active candidate types: `identity`, `butterworth_lowpass_2nd` (alias `biquad_lowpass`), and `lowpass_1pole`. The deployable vocabulary is owned by [LSL_Bridge/docs/configuration.md](../../LSL_Bridge/docs/configuration.md#supported-filter-types).
- Current documented recommendation: primary characterization channel should use a **2nd-order Butterworth low-pass at 15 Hz, fs = 100 Hz** when the active data profile matches the refreshed artifact-fixed captures.
- A **2nd-order Butterworth low-pass at 10 Hz** can be used as an optional stable-display channel, not necessarily as the primary scientific characterization channel.
- High-pass, band-pass, notch, moving-average, median, and chain filters are offline-only diagnostics: they may exist as **inactive** metadata in `conf/filters/candidates.yaml`, but they are rejected at config load if placed in the active `filters:` list.

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

A single frequency peak at rest does not by itself justify aggressive filtering; compare it against useful handgrip bandwidth and dynamic distortion. Note that notch and high-pass removal are offline-only diagnostics, not deployable Stage 6 candidates (see Step 4).

### Step 3 — Select representative dynamic capture

Use a capture with baseline, rise, hold, and release. The current filter reassessment used a ramp/hold-like trial because it stresses both waveform fidelity and hold stability.

### Step 4 — Build candidate bank

The **active** candidate bank is restricted to production-real-time types. Every active candidate must
map 1:1 to an `LSL_Bridge` filter stanza and is run causally per-sample; `load_filter_specs()` raises a
`ValueError` if an active candidate is not deployable.

| Active type               | When to use                                                    | Main risk                                               |
| ------------------------- | -------------------------------------------------------------- | ------------------------------------------------------- |
| `identity`                | Always include as baseline.                                    | None; provides comparison reference.                    |
| `butterworth_lowpass_2nd` | High-frequency contamination without needing baseline removal. | Over-smoothing, peak error, delayed/flattened dynamics. |
| `lowpass_1pole`           | Lighter, lower-cost smoothing where a 2nd-order roll-off is unnecessary. | Gentler roll-off; less stopband attenuation.  |

Offline-only families — `notch`/band-reject, `butter_highpass`, `butter_bandpass`, `moving_average`,
`median`, and `chain` — address narrowband contamination, baseline drift, or bounded-band signals, but
they cannot run as a causal real-time `LSL_Bridge` filter. They may stay in `candidates.yaml` as
**inactive diagnostic** metadata for investigation, but never in the active `filters:` list. To promote
one to production, follow the process in [Handgrip_Analysis/docs/development.md](development.md#add-a-filter-family).

`LSL_Bridge` also supports a `drift_corrector`, but it is intentionally **not** a Stage 6 candidate:
drift correction is semantically dangerous for calibrated absolute-force baselines and must not be ranked
without explicit validation criteria.

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

Because the active bank is already restricted to deployable types, the Stage 6 winner is guaranteed
deployable. The selection is exported as an `LSL_Bridge` processing snippet through the strict
`lsl_bridge_filter_config_from_spec()` contract — there is no "winner requires manual implementation"
middle state. An unconvertible filter fails before it can be recommended.

## Current recommendation

For the current documented recommendation baseline, see [Handgrip_Analysis/docs/stages.md](stages.md#stage-6--filter-design-candidate-benchmark).

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
- the candidate is not a production-real-time type (Stage 6 evaluates every candidate causally and per-sample, matching `LSL_Bridge`; offline zero-phase filtering is not used),
- recommendation is based on a single unrepresentative capture.
