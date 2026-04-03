# Handgrip Filter Reassessment v2 — Process and Recommendation

## Executive conclusion

Based on the refreshed captures **after fixing the sharp outlier artifact**, the answer is:

- **High-pass:** **No** for the primary handgrip-force channel.
- **Band-pass:** **No** for the primary handgrip-force channel.
- **Band-reject / notch:** **Not needed** for the main product path with the current data.

### Best implementation recommendation

For the channel intended to approximate the **most realistic original sensor-force curve** while still removing non-essential high-frequency contamination:

- **Primary characterization channel:** **2nd-order Butterworth low-pass at 15 Hz, fs = 100 Hz**
- **Optional secondary UI / stable-display channel:** **2nd-order Butterworth low-pass at 10 Hz, fs = 100 Hz**
- **Baseline / zero handling:** **state-based tare and unloaded-only baseline tracking**, not continuous high-pass filtering during the grip event.

If only **one** filtered channel can be shipped for this use case, choose:

- **2nd-order Butterworth low-pass, 15 Hz cutoff**

because it gave the best overall realism/noise tradeoff once the outlier artifact was removed.

---

## 1. Analysis process

## Step 1 — Reframe the problem after the artifact fix

### Reasoning
The previous design center was dominated by sharp outliers. Once those were fixed, the correct question became:

1. Is the remaining contamination narrowband enough to justify a notch?
2. Is the baseline drift severe enough to justify a high-pass?
3. Is the handgrip waveform bandwidth narrow enough that a low-pass alone is sufficient?

### Tools used
- Existing uploaded outputs in `data/analysis_results/`
- Existing calibration captures in `data/calibration_signals/`
- New script: `scripts/filter_family_review.py`

---

## Step 2 — Inspect the refreshed rest capture

### Reasoning
The rest capture determines the stationary-noise floor and whether there is a narrow deterministic interferer that survives into the raw signal.

### Observations from the uploaded stage-2 results
Top PSD peaks in the refreshed rest capture:

- **0.0488 Hz** — slow baseline movement / drift
- **45.9473 Hz** — modest narrow component

This is materially different from the previous outlier-dominated regime.

### Interpretation
- The **0.0488 Hz** component is baseline drift territory, not something to remove with a continuous high-pass on the grip signal.
- The **45.95 Hz** component is real enough to observe, but it is already small and lies well outside the useful handgrip-force bandwidth.
- Therefore the first candidate to test is a **low-pass-only family**, not high-pass or band-pass.

### Tools used
- Existing stage-2 PSD outputs
- New script: `scripts/filter_family_review.py`

---

## Step 3 — Choose the most suitable calibration signal for stage 6

### Selected signal
`20260402_stage4_ramp_hold_trial01.csv`

### Reasoning
This was the best single calibration signal because it contains all the features that matter for filter discrimination in one capture:

- quiet baseline before activation,
- controlled rise,
- quasi-steady hold,
- release,
- enough duration to expose distortion in both transient and near-steady sections.

`fast_max` is useful for aggressive onset behavior, and `sustained_hold` is useful for plateau/fatigue behavior, but `ramp_hold` is the best **single** input for stage 6 because it stresses both waveform fidelity and hold stability in a balanced way.

### Tools used
- Existing stage-4 event outputs
- New script: `scripts/stage6_filter_design.py`

---

## Step 4 — Build an expanded candidate bank

### Reasoning
The board question explicitly asked whether **band-pass, band-reject, or high-pass** filters now make sense. So the candidate bank had to include them, not just low-pass variants.

### Candidate families tested
- identity
- 2nd-order Butterworth low-pass at 8, 10, 12, 15 Hz
- notch at 45.95 Hz
- notch at 45.95 Hz followed by low-pass 12 Hz
- high-pass at 0.05 Hz and 0.10 Hz
- band-pass at 0.05–12 Hz and 0.10–12 Hz

### Tools used
- New config: `configs/filter_candidates_v2.yaml`
- New script: `scripts/stage6_filter_design.py`
- New script: `scripts/filter_family_review.py`

---

## Step 5 — Run enhanced stage 6 on the selected calibration signal

### Metrics evaluated
For the selected `ramp_hold` signal, each candidate was compared against the raw event using:

- peak error vs raw,
- peak-time shift,
- rise-time shift (10–90%),
- max dF/dt ratio vs raw,
- plateau standard deviation,
- optional rest-capture stationary noise impact.

### Key results
From `outputs/stage6_ramp_hold/filter_comparison.csv`:

- **identity** and **notch-only** are nearly indistinguishable on the dynamic waveform.
- **Low-pass 15 Hz** gives small dynamic distortion while still reducing rest noise.
- **Low-pass 10 Hz** and **12 Hz** are also viable, but they suppress the dynamic slope more strongly.
- **High-pass** and **band-pass** badly distort the ramp/hold event.

Examples on the selected `ramp_hold` signal:

- `butter_lowpass_15hz`
  - peak error: **-4383.7 counts**
  - peak-time shift: **0.00 s**
  - rise shift: **-0.01 s**
  - max dF/dt ratio: **0.8648**
- `butter_lowpass_12hz`
  - peak error: **-5525.9 counts**
  - max dF/dt ratio: **0.8017**
- `butter_lowpass_10hz`
  - peak error: **-6968.3 counts**
  - max dF/dt ratio: **0.7791**
- `highpass_0p10hz`
  - peak error: **-1.285e6 counts**
  - peak-time shift: **0.14 s**
  - event fragmentation: **4 detected events**
- `bandpass_0p10_12hz`
  - peak error: **-1.295e6 counts**
  - peak-time shift: **0.14 s**
  - event fragmentation: **4 detected events**

### Interpretation
This result alone is enough to reject high-pass and band-pass for the primary force path.

---

## Step 6 — Cross-check with rest + all dynamic trials

### Reasoning
A single ramp-hold trial is the right stage-6 input, but the final board recommendation should survive contact with:

- `fast_max`
- `ramp_hold`
- `sustained_hold`
- `rest_after_warmup`

So a second script scored all candidates across all available relevant trials.

### Composite score design
The composite score weighted:

- stationary-noise reduction,
- peak preservation,
- rise-time preservation,
- peak-time stability,
- dF/dt preservation.

This intentionally favored **realistic signal reconstruction** over maximum smoothing.

### Result
From `outputs/filter_family_review/filter_family_assessment.csv`:

Top-ranked candidates:

1. **butter_lowpass_15hz**
2. **butter_lowpass_10hz**
3. **butter_lowpass_8hz**
4. **butter_lowpass_12hz**
5. **notch_45p95hz_then_lowpass_12hz**

Notch-only ranked near identity because it barely changes the signal. High-pass and band-pass ranked worst.

### Interpretation
- The **45.95 Hz** line does not justify a notch in the main path because a modest low-pass already removes it.
- The best tradeoff for **signal realism** ended up at **15 Hz**, not 8–10 Hz, because the outlier problem is gone and preserving the waveform now matters more.

---

## 2. Final recommendation for filter implementation

## Recommended architecture

### A. Keep the raw channel
Do not destroy the original raw stream. Keep it logged for engineering traceability and future model refinement.

### B. Primary filtered channel for sensor-curve characterization
Use:

- **2nd-order Butterworth low-pass**
- **Cutoff = 15 Hz**
- **Sampling rate = 100 Hz**

This is the best single filtered channel for:

- recording realistic sensor curves,
- preserving squeeze onset,
- preserving hold behavior,
- removing irrelevant high-frequency contamination,
- suppressing the small ~45.95 Hz component without needing a notch.

### C. Optional secondary filtered channel for UI / more stable display
Use:

- **2nd-order Butterworth low-pass**
- **Cutoff = 10 Hz**
- **Sampling rate = 100 Hz**

This is useful if the product wants a visibly steadier display or stable exported metric channel. It is **not** the best choice if the priority is maximum realism of the original force curve.

### D. Baseline handling
Do **not** use a continuous high-pass to remove drift during gripping.

Instead:
- gate the tare process,
- track baseline only when the device is confidently unloaded,
- freeze the baseline estimate during grip events.

That solves baseline management without corrupting the force waveform.

---

## Why not high-pass?

Because the signal of interest includes quasi-static hold behavior and slow force evolution. A high-pass removes exactly the low-frequency content that makes the handgrip curve physiologically meaningful.

Observed effect in the refreshed data:
- severe peak distortion,
- event fragmentation,
- false waveform reshaping,
- incorrect plateau behavior.

---

## Why not band-pass?

Because handgrip-force measurement is **not** a narrowband oscillatory phenomenon. The clinically and mechanically relevant signal includes:

- DC / near-DC force level,
- slow ramp,
- hold,
- release,
- moderate transient content.

Band-pass filtering removes the true force baseline and re-centers the waveform into an artificial oscillatory representation.

Observed effect in the refreshed data:
- catastrophic amplitude distortion,
- fragmented event detection,
- incorrect ramp/hold shape.

---

## Why not band-reject / notch?

Because the narrow component around **45.95 Hz** is:

- relatively small,
- outside the handgrip band of interest,
- already strongly attenuated by a 15 Hz low-pass.

For example, with the chosen 2nd-order Butterworth low-pass:

- **15 Hz cutoff** attenuates ~45.95 Hz by roughly **47 dB**
- **12 Hz cutoff** attenuates ~45.95 Hz by roughly **52 dB**

So a notch adds complexity with no meaningful benefit in the main force path.

---

## Embedded implementation coefficients

For **fs = 100 Hz**:

### Recommended primary characterization channel — 2nd-order Butterworth low-pass, 15 Hz
Direct-form coefficients:

- `b = [0.13110644, 0.26221288, 0.13110644]`
- `a = [1.00000000, -0.74778918, 0.27221494]`

Difference equation:

```text
y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
```

with:

- `b0 = 0.13110644`
- `b1 = 0.26221288`
- `b2 = 0.13110644`
- `a1 = -0.74778918`
- `a2 = 0.27221494`

### Optional UI/stable channel — 2nd-order Butterworth low-pass, 10 Hz
Direct-form coefficients:

- `b = [0.06745527, 0.13491055, 0.06745527]`
- `a = [1.00000000, -1.14298050, 0.41280160]`

---

## Recommended product decision

### If the product can expose two filtered channels
Ship:

1. **Raw archived / engineering channel**
2. **15 Hz low-pass characterization channel**
3. **10 Hz low-pass UI/stable channel**

### If the product can expose only one filtered channel
Ship:

- **15 Hz low-pass characterization channel**

because the stated goal is to obtain the **most realistic original sensor signal** for sensor-curve characterization.

---

## Files produced in this package

### Scripts
- `scripts/stage6_filter_design.py`
- `scripts/filter_family_review.py`

### Config
- `configs/filter_candidates_v2.yaml`

### Outputs
- `outputs/stage6_ramp_hold/filter_comparison.csv`
- `outputs/stage6_ramp_hold/time_overlay.png`
- `outputs/stage6_ramp_hold/psd_overlay.png`
- `outputs/filter_family_review/filter_family_assessment.csv`
- `outputs/filter_family_review/rest_psd_peaks.csv`
- `outputs/filter_family_review/composite_score.png`
- `outputs/filter_family_review/rest_psd_top_candidates.png`

---

## Bottom line

After the artifact fix, the best board-level answer is now much simpler:

- **No high-pass on the main grip channel**
- **No band-pass on the main grip channel**
- **No notch needed in the main grip channel**
- **Use a modest low-pass only**
- **Choose 15 Hz if realism is the top priority**
- **Handle baseline separately with gated tare / unloaded-only drift tracking**
