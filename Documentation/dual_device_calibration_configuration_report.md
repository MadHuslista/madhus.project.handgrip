
# Dual-Device Calibration Configuration Report
## Reference acquisition board + HX711 hand-grip target
**Date:** 2026-04-21  
**Goal:** maximize calibration quality of the HX711-based target device using the RS485 load-cell acquisition board as reference, while preserving timing integrity, signal fidelity, and reproducibility.

---
[TOC]

## Overview

### Bottom line

For the calibration use case you described, the strongest default architecture is:

|    # | Domain                        | Parameter               | Setting                                        | Notes                                             |
| ---: | ----------------------------- | ----------------------- | ---------------------------------------------- | ------------------------------------------------- |
|    1 | **Reference chain**           | Internal sampling       | **640 Hz**                                     |                                                   |
|      |                               | ADC gain                | **128**                                        |                                                   |
|      |                               | Filtering               | **median=3, average=5**                        | light filtering                                   |
|      |                               | Dynamic helper features | **Disabled**                                   |                                                   |
|      |                               | RS485 mode              | **Active-send at 100 Hz**                      |                                                   |
|      |                               | Serial                  | **115200, 8N1**                                |                                                   |
|    2 | **Target chain**              | HX711 rate              | **~93 Hz empirical max**                       | keep as-is                                        |
|      |                               | Serial                  | **UART 115200, 8N1**                           | keep as-is                                        |
|      |                               | Calibration output      | **raw counts + seq number + device timestamp** |                                                   |
|      |                               | Firmware smoothing      | **Disabled**                                   | no extra smoothing                                |
|      |                               | Auto-zero logic         | **Disabled**                                   | no auto-zero in firmware                          |
|    3 | **Synchronization / logging** | Acquisition host        | **Same Linux PC**                              | both processes co-located                         |
|      |                               | Streaming framework     | **LSL**                                        |                                                   |
|      |                               | Target stream type      | **Irregular**                                  |                                                   |
|      |                               | Reference stream type   | **Regular**                                    |                                                   |
|      |                               | Recording format        | **XDF**                                        | for post-hoc alignment and dejitter               |
|    4 | **Calibration protocol**      | Reference role          | **Ground-truth force trace generation**        |                                                   |
|      |                               | Model fitting data      | **Static staircase holds**                     | actual target calibration model                   |
|      |                               | Dynamic trials role     | **Validate only**                              | lag, bandwidth, hysteresis (squeezes/ramp trials) |
|    5 | **Transport choice**          | Default (reference)     | **Active mode at 100 Hz**                      | best default after payload validation in practice |
|      |                               | Fallback (reference)    | **Modbus RTU polling at 100 Hz**               | highest-certainty; register map is documented     |

### Executive recommendation

The key design choice is **not** “maximize every rate.”  
The best calibration setup is the one that:

- keeps the **reference chain faster and cleaner** than the target,
- avoids **hidden zeroing / drift compensation / stability gating** during live force capture,
- uses a transport rate that is **close enough to the target to simplify comparison** without wasting bandwidth,
- preserves enough metadata to diagnose **lag, jitter, dropped samples, hysteresis, and nonlinearity**.

That is why the recommended reference output is **100 Hz**, not 500 or 1000 Hz, even though the board can be configured much faster internally.

### Epistemic status

**[Known]**

- The acquisition board supports internal sampling rates **10 / 40 / 640 / 1280 Hz**, gain settings **1 / 2 / 64 / 128**, median and moving-average filters, load or datasheet calibration modes, stability/zero logic, and RS485 settings including **Modbus RTU** and **Active send**. The communication menu exposes address, baud, parity, stop bits, active-send enable, and active-send frequency.[A1]
- The board’s RS485 menu supports baud rates up to **600000**, and Active-send frequencies up to **1000 Hz**.[A1]
- The board’s sensor excitation is **5 V**, and your PM58 reference load cell is approximately **100 kg**, **1.504 mV/V** sensitivity.[A1]
- The HX711 is a 24-bit bridge ADC with selectable **10 SPS / 80 SPS** nominal output rate, and its settling time depends on reset / channel / gain changes. The datasheet also states simultaneous **50/60 Hz rejection** as a feature.[W1]
- LSL supports per-sample timestamps, clock-offset estimation, post-hoc synchronization/dejitter, and explicitly supports **irregularly sampled streams**.[W2][W3][W4]
- Standard Modbus over serial is request/reply master-slave communication over serial links such as RS485.[W5][W6]

**[Could be known with one short bench test]**

- The exact **payload format** and parser robustness of your board’s vendor-specific **Active-send** mode.
- The actual **noise floor** of the PM58 + board chain at your chosen gain/filter settings.
- The effective low-force resolution of the **100 kg reference load cell** in your hand-grip fixture.
- Whether the target stream’s timing irregularity is dominated by **HX711 conversion timing**, **Arduino firmware scheduling**, **USB serial buffering**, or **host-side parsing**.

**[Cannot be known from the provided material alone]**

- The true full-scale mechanical force at the **target fixture** because the target uses two 5 or 10 kg cells in parallel but the force transmission geometry is not defined.
- Whether your reference chain is mechanically exposed to the **same load path** as the target with negligible structural compliance / backlash.
- Whether the board’s Active-send timestamps are device-timed or simply transmission paced; the uploaded manual does not document that.

---

## Summary table of recommended values

### 1) Recommended operating profile

| Domain                    |                     Parameter |    UI    | Recommended value                                                                                     | Why this is the best default for calibration                                                                                                                                                                                   |
| ------------------------- | ----------------------------: | :------: | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Reference board           |             Internal sampling | `100.SP` | **640 Hz**                                                                                            | Keeps the reference chain much faster than the ~93 Hz target without paying the extra noise penalty of 1280 Hz. It gives oversampling margin for clean peak/ramp reconstruction and later down-selection to target timestamps. |
| Reference board           |                      ADC gain | `101.GA` | **128B**                                                                                              | Your PM58 is ~1.504 mV/V at 5 V excitation, so full-scale bridge output is only about 7.52 mV. Gain 128 comfortably fits that range and maximizes useful resolution.                                                           |
| Reference board           |                 Median filter | `102.ME` | **3**                                                                                                 | Suppresses impulsive outliers without introducing the lag of `5` or `9`.                                                                                                                                                       |
| Reference board           |                Average filter | `103.rV` | **5**                                                                                                 | Gives modest smoothing with only a short effective window at 640 Hz; enough to improve SNR while preserving hand-grip dynamics.                                                                                                |
| Reference board           |                          Unit | `105.uN` | **N**                                                                                                 | The target is a force device. Calibrating the reference directly in Newtons removes one later conversion step and makes the fitted model physically consistent.                                                                |
| Reference board           |                 Decimal point | `106.bi` | **1**                                                                                                 | With `N`, one decimal place gives 0.1 N display increments and enough range headroom. It also makes the board’s stability/zero windows less unrealistically tight than `0.01 N` divisions would.                               |
| Reference board           |                    Graduation | `107.dV` | **1**                                                                                                 | Smallest available division for best display granularity.                                                                                                                                                                      |
| Reference board           |                  Max weighing | `108.ro` | **900.0 N**                                                                                           | Safe engineering cap below the nominal 100 kg full-scale (~980.7 N) while still covering strong hand-grip trials.                                                                                                              |
| Reference board           |                      DI input | `109.di` | **NoNE**                                                                                              | Avoids accidental remote tare/zero/peak-clear events during calibration runs.                                                                                                                                                  |
| Reference board           |                Peak threshold | `110.MZ` | **5.0 N**                                                                                             | High enough to prevent trivial noise-driven peak refreshes, low enough to preserve real grip peaks.                                                                                                                            |
| Reference board           |                 Peak interval | `111.MN` | **0.10 s**                                                                                            | Lets you inspect repeated grip peaks without the sluggishness of the 0.5 s default.                                                                                                                                            |
| Reference board           |               Display refresh | `113.uP` | **0.05 s**                                                                                            | Responsive enough for operator feedback, still readable.                                                                                                                                                                       |
| Reference board           |                        Backup | `114.bp` | **YES after validation**                                                                              | Freezes a known-good calibration profile once verified.                                                                                                                                                                        |
| Reference board           |              Calibration mode | `201.Mo` | **Load**                                                                                              | Real-load calibration is higher-epistemic than datasheet-only entry for a reference instrument.                                                                                                                                |
| Reference board           |              Calibration load | `202.WE` | **Largest traceable load point in the intended operating range, preferably 60–80% of max used force** | Best compromise between span accuracy and rig practicality.                                                                                                                                                                    |
| Reference board           |        Datasheet backup range | `203.rA` | **980.7 N** (backup only)                                                                             | Sensible backup if you ever need `data` mode.                                                                                                                                                                                  |
| Reference board           |  Datasheet backup sensitivity | `204.SE` | **1.504 mV/V**                                                                                        | From PM58 certificate / label.                                                                                                                                                                                                 |
| Reference board           |                    Excitation | `205.rE` | **5.000 V**                                                                                           | Matches the board’s excitation.                                                                                                                                                                                                |
| Reference board           |                     Span trim | `206.rV` | **1.000 initially**                                                                                   | Do not “trim blind”; only change after verification loads show a real span error.                                                                                                                                              |
| Reference board           |             Multipoint enable | `207.mE` | **0 (off) initially**                                                                                 | Two-point calibration is the highest ROI default; only open multipoint if residual nonlinearity is measured.                                                                                                                   |
| Reference board           |                Creep tracking | `400.CV` | **0**                                                                                                 | Prevents hidden slow baseline correction during calibration.                                                                                                                                                                   |
| Reference board           |            Display zero range | `401.dZ` | **0**                                                                                                 | Cosmetic zeroing is harmful during calibration because it hides real offset.                                                                                                                                                   |
| Reference board           |              Dynamic tracking | `402.tV` | **0**                                                                                                 | The vendor feature is insufficiently documented and can distort the trace.                                                                                                                                                     |
| Reference board           |          Stable weight switch | `404.SV` | **0**                                                                                                 | You want to see the real evolving signal, not a final settled jump.                                                                                                                                                            |
| Reference board           |                    Zero range | `405.Zr` | **5.0 N**                                                                                             | Allows manual zeroing but limits it to a narrow unloaded neighborhood.                                                                                                                                                         |
| Reference board           |                 Power-on zero | `406.PZ` | **0**                                                                                                 | Prevents silent baseline shifts at startup.                                                                                                                                                                                    |
| Reference board           |                     Auto-zero | `409.AZ` | **0**                                                                                                 | Prevents slow drift compensation from contaminating live force traces.                                                                                                                                                         |
| Reference board           |               Stability range | `412.Wr` | **0**                                                                                                 | Disables stability gating so the board does not block operations based on a very small division-based window.                                                                                                                  |
| Reference board           |                Stability time | `413.Wt` | **1.0 s** (irrelevant when `412=0`)                                                                   | Safe default; not load-bearing when stability gating is off.                                                                                                                                                                   |
| Reference board transport |                    RS485 mode | `504.AS` | **1 (Active-send)**                                                                                   | Best default for a calibration capture path once parser behavior has been validated; avoids host polling jitter.                                                                                                               |
| Reference board transport |              Active-send rate | `505.AF` | **100 Hz**                                                                                            | Closest available rate to the target’s ~93 Hz, preserves comparison simplicity, avoids needless serial load.                                                                                                                   |
| Reference board transport |                          Baud | `501.br` | **115200**                                                                                            | Plenty of margin for 100 Hz capture, more universal/robust than higher nonstandard rates.                                                                                                                                      |
| Reference board transport |                 Parity / stop | `502.Vb` | **None**                                                                                              | Lowest overhead, simplest integration.                                                                                                                                                                                         |
| Reference board transport |                 Parity / stop | `503.so` | **1**                                                                                                 | Lowest overhead, simplest integration.                                                                                                                                                                                         |
| Reference board transport |                       Address | `500.Ar` | **1**                                                                                                 | Fine for a single-device bench link.                                                                                                                                                                                           |
| Target device             |               HX711 rate mode |    -     | **Fastest stable mode already in use (~93 Hz empirical stream)**                                      | Do not down-rate the target during calibration; the goal is to calibrate the actual device as used.                                                                                                                            |
| Target device             |                          UART |    -     | **115200, 8N1**                                                                                       | Easily sufficient for ~93 Hz raw + metadata streaming; likely already validated.                                                                                                                                               |
| Target device             |            Firmware filtering |    -     | **Disabled for calibration output**                                                                   | Calibration should be fit on raw counts or near-raw counts, not on pre-smoothed values.                                                                                                                                        |
| Target device             |             Zero / tare logic |    -     | **Manual only before run**                                                                            | Disable continuous drift compensation during actual captures.                                                                                                                                                                  |
| Target device             |                 Output fields |    -     | **seq, device_timestamp, raw_count, interpreted_value**                                               | Minimal set needed to audit lag, drops, and calibration mapping.                                                                                                                                                               |
| Synchronization           |           Recording framework |    -     | **LSL + XDF / LabRecorder**                                                                           | Best practical way to unify both streams on one host, preserve timing metadata, and enable post-hoc alignment.                                                                                                                 |
| Synchronization           | LSL nominal srate (reference) |    -     | **100 Hz regular**                                                                                    | Matches the actual reference output.                                                                                                                                                                                           |
| Synchronization           |    LSL nominal srate (target) |    -     | **IRREGULAR_RATE / 0**                                                                                | The target’s observed ±15 ms timing variation should not be falsely advertised as fixed-rate.                                                                                                                                  |
| Analysis                  |                  Fitting data |    -     | **Static staircase holds for parameter fit; dynamic trials for validation only**                      | Prevents transport/bandwidth differences from being misinterpreted as gain/offset errors.                                                                                                                                      |

---

## Detailed breakdown of the recommended values

### A. Reference board signal chain

#### `100.SP` - Sampling rate

**Recommended values** 

| Code     | Name            | Recommended value |
| -------- | --------------- | ----------------- |
| `100.SP` | `Sampling rate` | **640 Hz**        |


**Overall reason for the selected value**  
The reference chain should be faster than the target by a comfortable margin, but it does not need to be at the absolute board maximum. `640 Hz` is fast enough to capture the shape of hand-grip ramps, squeezes, and releases while still being a more favorable noise/stability point than `1280 Hz`.

**How it impacts calibration**  
It improves the reference trace’s time resolution and reduces interpolation error when you later align it against the target. At the same time, it avoids pushing the board to its noisiest internal operating point for no meaningful gain, given that the target itself is only ~93 Hz.

**Alternatives rejected**
- **`40 Hz`**: rejected because it is slower than the target and increases temporal ambiguity during alignment.
- **`1280 Hz`**: rejected as the default because it likely adds noise without improving the calibration model once the reference is ultimately compared against a ~93 Hz target.
- **`10 Hz`**: rejected because it destroys dynamic validation value.

#### `101.GA` - Gain adjustment

**Recommended values** 

| Code     | Name              | Recommended value |
| -------- | ----------------- | ----------------- |
| `101.GA` | `Gain adjustment` | **128B**          |

**Overall reason**  
At 5 V excitation and ~1.504 mV/V sensitivity, the PM58 full-scale output is roughly 7.52 mV. HX711-style bridge front ends and this board’s ADC gain options make `128` the natural high-resolution choice while staying within input range.[W1]

**Calibration impact**  
Improves effective resolution of the reference measurement, especially important if your hand-grip fixture uses only a modest fraction of the 100 kg reference cell’s range.

**Alternatives rejected**
- **`64`**: more headroom than needed, lower sensitivity.
- **`2` or `1`**: far too conservative for this bridge amplitude and would waste useful ADC range.

#### `102.ME` - Median filter 
#### `103.rV` - Average filter

**Recommended values** 

| Code     | Name             | Recommended value |
| -------- | ---------------- | ----------------- |
| `102.ME` | `Median filter`  | **3**             |
| `103.rV` | `Average filter` | **5**             |

**Overall reason**  
This is a deliberately light filter stack:
- median-of-3 for impulse robustness,
- moving average of 5 for SNR improvement with modest lag.

**Calibration impact**  
Makes the reference cleaner than the target without smearing the dynamic shape. That is exactly what you want from a ground-truth chain.

**Alternatives rejected**
- **`ME=1`, `rV=1`**: rejected because it exposes too much quantization/noise for no benefit.
- **`ME=5`, `rV=10+`**: rejected because the lag becomes more visible and can bias dynamic comparison.
- **`ME=9`**: rejected because it is excessive unless the board is operating in an unusually noisy environment.

#### `105.uN` - Unit selection
#### `106.bi` - Decimal point position
#### `107.dV` - Graduation value
#### `108.ro` - Maximum weighing

**Recommended values** 

| Code     | Name               | Recommended value |
| -------- | ------------------ | ----------------- |
| `105.uN` | `Unit selection`   | **N**             |
| `106.bi` | `Decimal point`    | **1**             |
| `107.dV` | `Graduation value` | **1**             |
| `108.ro` | `Maximum weighing` | **900.0 N**       |

**Overall reason**  
The target is a force device. Use force units end-to-end. One decimal place in Newtons is a good compromise between readability, stability-window practicality, and dynamic range.

**Calibration impact**  
Reduces downstream ambiguity. The fitted calibration model can be stated directly in physical force units. `108.ro` set to `900.0 N` adds a safety cap below the nominal 100 kg cell full-scale while still covering realistic hand-grip use.

**Alternatives rejected**
- **`kg` / `g` units**: rejected because they are convenient for deadweights but semantically weaker for a force instrument.
- **two decimal places in N**: rejected because it makes division-based stability windows unrealistically small.
- **`108.ro` near exact full-scale (~980.7 N)**: rejected because leaving no operating margin is poor bench practice.

#### `109.di` - DI switch input function

**Recommended values** 

| Code     | Name              | Recommended value |
| -------- | ----------------- | ----------------- |
| `109.di` | `DI switch input` | **NoNE**          |


**Overall reason**  
The DI feature is operationally useful, but not for a calibration bench unless you are deliberately using it as a trigger input.

**Calibration impact**  
Prevents accidental remote tare/zero/peak-clear events that would corrupt a run.

**Alternatives rejected**
- **`SZEro` / `CZEro`**: rejected because a stray short could silently rewrite baseline.
- **`REMAX`**: useful only for a specialized peak test fixture.

#### `110.MZ` - Peak threshold
#### `111.MN` - Peak interval

**Recommended values** 

| Code     | Name             | Recommended value |
| -------- | ---------------- | ----------------- |
| `110.MZ` | `Peak threshold` | **5.0 N**         |
| `111.MN` | `Peak interval`  | **0.10 s**        |

**Overall reason**  
These are operator-assistance values, not core acquisition values. `110.MZ` prevents trivial noise from repeatedly refreshing peak display, while `111.MN` keeps peak updates responsive enough for repeated short squeezes.

**Calibration impact**  
Minimal for fitted calibration parameters, but helpful during validation trials.

**Alternatives rejected**
- **`MZ=0`**: too sensitive; any slightly larger noise bump can refresh the peak.
- **`MN=0.5 s` default**: too slow for repeated short squeezes.

#### `113.uP` - Display refresh

**Recommended values** 

| Code     | Name              | Recommended value |
| -------- | ----------------- | ----------------- |
| `113.uP` | `Display refresh` | **0.05 s**        |

**Overall reason**  
Display refresh should be fast enough for human supervision but it should not be confused with acquisition rate.

**Calibration impact**  
None on stored data, but it improves operator confidence during setup.

**Alternatives rejected**
- **`0.02 s`**: marginally faster, but unnecessary.
- **`>0.1 s`**: makes live feedback feel sluggish.

#### `114.bp` - Backup

**Recommended values** 

| Code     | Name     | Recommended value          |
| -------- | -------- | -------------------------- |
| `114.bp` | `Backup` | **YES (after validation)** |

**Overall reason**  
Once the profile is verified, freeze it.

**Calibration impact**  
Improves reproducibility and reduces configuration drift across sessions.

**Alternatives rejected**
- **Never back up**: increases single-point-of-failure risk.
- **Backing up before verification**: locks in an unvalidated profile.

---

### B. Reference board calibration block

#### `201.Mo` - Calibration mode

**Recommended values** 

| Code     | Name               | Recommended value |
| -------- | ------------------ | ----------------- |
| `201.Mo` | `Calibration mode` | **Load**          |

**Overall reason**  
For a reference instrument, real-load calibration is higher-quality than entering nominal datasheet values only. The board manual itself supports both, but `Load` is the correct primary mode for this use case.[A1]

**Calibration impact**  
Directly improves the credibility of the reference channel that will anchor the target fit.

**Alternatives rejected**
- **`data` mode only**: rejected as the primary method because datasheet sensitivity and mechanical installation tolerance are not enough for best-possible reference calibration.

#### `202.WE` - Calibration load

**Recommended values** 

| Code     | Name               | Recommended value                                            |
| -------- | ------------------ | ------------------------------------------------------------ |
| `202.WE` | `Calibration load` | **Largest traceable load point in intended operating range** |

**Overall reason**  
This parameter is physically rig-dependent. The best value is not a universal constant; it is the best repeatable reference load you can actually apply. Prefer a point high enough to constrain span well, but not so high that the fixture becomes awkward or unsafe.

**Calibration impact**  
Better span accuracy, better repeatability, less operator-induced scatter.

**Alternatives rejected**
- **Very small load point**: poor span leverage.
- **Near-absolute full scale every time**: unnecessary rig stress and worse ergonomics.
- **Purely dynamic calibration without static holds**: wrong tool for gain/offset estimation.

#### `203.rA` - Datasheet backup range
#### `204.SE` - Datasheet backup sensitivity
#### `205.rE` - Excitation

**Recommended values** 

| Code     | Name                           | Recommended value |
| -------- | ------------------------------ | ----------------- |
| `203.rA` | `Datasheet backup range`       | **980.7 N**       |
| `204.SE` | `Datasheet backup sensitivity` | **1.504 mV/V**    |
| `205.rE` | `Excitation`                   | **5.000 V**       |

**Overall reason**  
These are the correct backup parameters if you must fall back to datasheet-entry calibration.

**Calibration impact**  
Good disaster-recovery values; not the first-choice calibration mode.

**Alternatives rejected**
- Leaving them unspecified: reduces recovery robustness.
- Using approximate rounded values too aggressively: unnecessary if the PM58 certificate value is available.

#### `206.rV` - Span trim

**Recommended values** 

| Code     | Name        | Recommended value |
| -------- | ----------- | ----------------- |
| `206.rV` | `Span trim` | **1.000**         |

**Overall reason**  
Do not compensate a problem you have not measured.

**Calibration impact**  
Prevents “tuning by folklore.” Only change this after reference verification loads show a real systematic span error.

**Alternatives rejected**
- Ad hoc span trimming before verification: classic calibration anti-pattern.

#### `207.mE` - Multipoint enable

**Recommended values** 

| Code     | Name                | Recommended value     |
| -------- | ------------------- | --------------------- |
| `207.mE` | `Multipoint enable` | **0 (off) initially** |

**Overall reason**  
Multipoint correction is worthwhile only after you have evidence that two-point calibration is not good enough over the operating band.

**Calibration impact**  
Keeps the reference chain simple and auditable.

**Alternatives rejected**
- **`207.mE = 1` by default**: rejected because it adds process complexity before you know it is needed.
- **Never using multipoint**: also not ideal; if residual nonlinearity is demonstrated, then open it.

#### `208.mC` - Multipoint count
#### `209.Mr` - Multipoint range

**Recommended values** 

| Code     | Name               | Recommended value             |
| -------- | ------------------ | ----------------------------- |
| `208.mC` | `Multipoint count` | **Unused in default profile** |
| `209.Mr` | `Multipoint range` | **Unused in default profile** |

**Overall recommendation**  
Unused in the default profile. If enabled later, use **at least 4–5 points** spread across the actual operating region, not just near zero and full-scale.

**Calibration impact**  
Potentially improves residual nonlinearity, but only if your applied loads are themselves high quality.

**Alternatives rejected**
- 2–3 poorly placed points: often worse than a clean two-point calibration.

---

### C. Reference board advanced functions

#### `400.CV` - Creep tracking

**Recommended values** 

| Code     | Name             | Recommended value |
| -------- | ---------------- | ----------------- |
| `400.CV` | `Creep tracking` | **0 (disabled)**  |

**Overall reason**  
Creep tracking is a convenience feature, not a reference-calibration feature.

**Calibration impact**  
Disabling it prevents slow baseline manipulation during long holds.

**Alternatives rejected**
- Any nonzero value: rejected until you have a quantified creep problem and understand the side effects.

#### `401.dZ` - Display zero range

**Recommended values** 

| Code     | Name                 | Recommended value |
| -------- | -------------------- | ----------------- |
| `401.dZ` | `Display zero range` | **0**             |

**Overall reason**  
The manual explicitly distinguishes “display zeroing” from true zeroing. Cosmetic zero is unacceptable in a reference trace because it hides real offset while retaining it internally.[A1]

**Calibration impact**  
Prevents masked baseline offsets.

**Alternatives rejected**
- Any nonzero cosmetic zero window: rejected for calibration captures.

#### `402.tV` - Dynamic tracking
#### `403.tC` - Dynamic tracking coefficient

**Recommended values** 

| Code     | Name                           | Recommended value |
| -------- | ------------------------------ | ----------------- |
| `402.tV` | `Dynamic tracking`             | **0**             |
| `403.tC` | `Dynamic tracking coefficient` | **default**       |

**Overall reason**  
The “dynamic tracking” feature is insufficiently documented and therefore low-epistemic.

**Calibration impact**  
Disabling it removes an unknown transform from the reference path.

**Alternatives rejected**
- Any nonzero dynamic-tracking configuration: rejected because it can alter transient shape in undocumented ways.

#### `404.SV` - Stable weight switch

**Recommended values** 

| Code     | Name                   | Recommended value |
| -------- | ---------------------- | ----------------- |
| `404.SV` | `Stable weight switch` | **0**             |

**Overall reason**  
The manual states that stable-weight mode can make the display jump straight to the final value instead of showing the change process.[A1]

**Calibration impact**  
For calibration, you want the real evolving signal—not a display/logic abstraction of the final stable value.

**Alternatives rejected**
- `1`: rejected because it suppresses useful operator insight during live dynamic trials.

#### `405.Zr` - Zero range

**Recommended values** 

| Code     | Name         | Recommended value |
| -------- | ------------ | ----------------- |
| `405.Zr` | `Zero range` | **5.0 N**         |

**Overall reason**  
The zero window should be tight enough to prevent zeroing under load, but not so tight that normal unloaded drift blocks manual zero.

**Calibration impact**  
Keeps the zero action meaningful and repeatable.

**Alternatives rejected**
- Much larger windows: risk zeroing on preload.
- Extremely tiny windows: nuisance failures.

#### `406.PZ` - Power-on zero
#### `407.Pt` - Power-on zero time
#### `408.Pr` - Power-on zero range

**Recommended values** 

| Code     | Name                  | Recommended value |
| -------- | --------------------- | ----------------- |
| `406.PZ` | `Power-on zero`       | **0**             |
| `407.Pt` | `Power-on zero time`  | **0**             |
| `408.Pr` | `Power-on zero range` | **5.0 N**         |

**Overall reason**  
Power-on zero is convenient for process equipment, not for a metrology-style reference path. You want startup behavior to be explicit and operator-controlled.

**Calibration impact**  
Avoids silent baseline changes at power-up.

**Alternatives rejected**
- `PZ=1`: rejected because startup auto-zero can erase useful evidence of offset or mechanical preload.

#### `409.AZ` - Auto-zero
#### `410.At` - Auto-zero time
#### `411.Ar` - Auto-zero range

**Recommended values** 

| Code     | Name              | Recommended value |
| -------- | ----------------- | ----------------- |
| `409.AZ` | `Auto-zero`       | **0**             |
| `410.At` | `Auto-zero time`  | **default**       |
| `411.Ar` | `Auto-zero range` | **default**       |

**Overall reason**  
Continuous auto-zero is actively harmful during calibration because it can slowly drag the baseline.

**Calibration impact**  
Preserves true drift and true zero offset, which are important to see and quantify.

**Alternatives rejected**
- Any enabled auto-zero profile: rejected for calibration capture mode.

#### `412.Wr` - Stability range
#### `413.Wt` - Stability time

**Recommended values** 

| Code     | Name              | Recommended value |
| -------- | ----------------- | ----------------- |
| `412.Wr` | `Stability range` | **0**             |
| `413.Wt` | `Stability time`  | **1.0 s**         |

**Overall reason**  
The division-based stable-window logic is useful in process settings, but for calibration it is often an unnecessary gate that can prevent zero/tare operations for reasons tied to display divisions rather than actual engineering judgment.

**Calibration impact**  
Disabling stability gating reduces nuisance behavior and keeps the operator in control. `413.Wt` becomes non-load-bearing in this state.

**Alternatives rejected**
- `Wr=1 or 2`: acceptable for general weighing, rejected here because the chosen engineering units/divisions can make the effective window too tight.
- Very long stability times: slow bench work for no benefit.

---

### D. Reference board communications

#### `500.Ar` - Address

**Recommended values** 

| Code     | Name      | Recommended value |
| -------- | --------- | ----------------- |
| `500.Ar` | `Address` | **1**             |

**Overall reason**  
Single-device bench setup; simplest valid address.

**Calibration impact**  
None, beyond reducing confusion.

**Alternatives rejected**
- Using a higher nonessential device address in a single-device bench setup: rejected because it adds bookkeeping without improving calibration quality.

#### `501.br` - Baud
#### `502.Vb` - Parity
#### `503.so` - Stop bits

**Recommended values** 

| Code     | Name        | Recommended value |
| -------- | ----------- | ----------------- |
| `501.br` | `Baud`      | **115200**        |
| `502.Vb` | `Parity`    | **none**          |
| `503.so` | `Stop bits` | **1**             |

**Overall reason**  
At 100 Hz reference output, 115200 bps is easily sufficient and has stronger interoperability than higher nonstandard rates. Standard 8N1 is simplest to integrate.

**Calibration impact**  
Keeps transport latency small enough that it is not the bottleneck while preserving robustness.

**Alternatives rejected**
- **9600**: too slow; unnecessary increase in round-trip / buffering exposure.
- **230400 / 256000 / higher**: technically attractive, but the practical improvement at 100 Hz is small while driver/adapter variability increases.

#### `504.AS` - RS485 mode
#### `505.AF` - Active-send rate

**Recommended values** 

| Code     | Name               | Recommended value   |
| -------- | ------------------ | ------------------- |
| `504.AS` | `RS485 mode`       | **1 (Active-send)** |
| `505.AF` | `Active-send rate` | **100 Hz**          |

**Overall reason**  
For actual calibration capture, the best default is device-paced transmission close to the target’s sampling regime. `100 Hz` is the closest active-send option to your target’s ~93 Hz empirical stream. It reduces the need for aggressive resampling, limits serial overhead, and avoids poll-cycle jitter from a host-driven Modbus loop.

**Calibration impact**  
Improves temporal regularity of the reference stream and simplifies downstream pairing with the target.

**Alternatives rejected**
- **`AS=0` Modbus RTU polling**: rejected as the *performance-first* default because it introduces host request/response cadence into the timing path. However, it remains the **highest-certainty fallback** because the board’s register map is documented.[A1][W5][W6]
- **`AF=500` or `1000 Hz`**: rejected because the target cannot exploit that bandwidth in the default campaign, and the board’s active payload is not documented in the uploaded manual.
- **`AF=50 Hz`**: rejected because it undersamples the target path instead of slightly oversampling it.

#### Fallback if Active-send is not parser-stable

Use:
- `504.AS = 0`
- same serial format (`115200, 8N1`)
- poll **net weight** at **100 Hz** through the documented register map.

This is the highest-epistemic backup mode.

---

### E. Target-device configuration

#### HX711 operating mode = keep empirical fast mode

**Overall reason**  
The purpose of calibration is to calibrate the device you actually intend to use. If its deployed acquisition path is the ~93 Hz empirical fast path, keep it that way during calibration.

**Calibration impact**  
Makes the fitted model valid for real operation.

**Alternatives rejected**
- Slowing the target for convenience: rejected because it calibrates the wrong system.

#### UART = `115200, 8N1`

**Overall reason**  
At ~93 samples/s, 115200 has ample bandwidth for raw count + timestamp + interpreted value even in text mode, and it is already the stated configuration.

**Calibration impact**  
Keeps transport overhead low while preserving compatibility.

**Alternatives rejected**
- Lower baud: unnecessary and more buffering-sensitive.
- Much higher baud: little benefit unless you also radically change the payload structure.

#### Target firmware filtering = disabled during calibration

**Overall reason**  
Do not fit a calibration model on already-smoothed or auto-zeroed data if you can avoid it.

**Calibration impact**  
Lets you estimate the raw transfer function from counts to force and then decide later what real-time smoothing belongs in the product path.

**Alternatives rejected**
- Moving average or other smoothing in firmware: rejected because it mixes calibration and presentation.
- Dynamic tare / drift tracking: rejected because it distorts baseline.

#### Target output payload = `seq`, `device_timestamp`, `raw_count`, `interpreted_value`

**Overall reason**  
This is the minimum set that lets you diagnose:
- sample drops,
- serial bursts,
- host-side jitter,
- calibration mapping,
- disagreements between raw and interpreted channels.

**Calibration impact**  
Greatly improves auditability.

**Alternatives rejected**
- Only interpreted value: rejected because it hides raw transfer behavior.
- Only raw count: rejected because it prevents quick online sanity checks.

---

### F. Synchronization and recording

#### Use LSL for both devices

**Overall reason**  
LSL is the best practical unification layer here because it provides sample timestamps, clock-offset handling, post-hoc correction/dejitter workflows, and regular vs irregular stream semantics.[W2][W3][W4]

**Calibration impact**  
Improves time alignment, logging reproducibility, and debugging.

**Alternatives rejected**
- Independent CSV files only: rejected because alignment becomes more fragile.
- GUI-only live view without unified recording: rejected because calibration should be replayable and auditable.

#### Reference stream in LSL = regular `100 Hz`

**Overall reason**  
The reference active-send path is intentionally regular.

**Calibration impact**  
Supports cleaner resampling / interpolation and simpler downstream analysis.

#### Target stream in LSL = `IRREGULAR_RATE`

**Overall reason**  
Official LSL guidance is to advertise irregular streams as irregular, not to pretend they are fixed-rate.[W4]

**Calibration impact**  
Prevents downstream tools from imposing a false clock model.

**Alternatives rejected**
- Advertising the target as exactly 93 Hz: rejected because the observed ±15 ms timing variation is too large to ignore.

#### Record to XDF

**Overall reason**  
XDF preserves both sample timestamps and LSL timing metadata.

**Calibration impact**  
Gives you the best post-hoc alignment path.

---

### G. Parameters not in the calibration path

These should be **disabled or left at safe defaults** for the calibration profile.

#### `C3.rEL` - Relay block

**Recommended values** 

| Parameter | Name                                   |                          Recommended value | Reason                                                                                 |
| --------- | -------------------------------------- | -----------------------------------------: | -------------------------------------------------------------------------------------- |
| `300.m1`  | `Relay 1 operating mode`               |                           **0 (disabled)** | Relay actions are outside the calibration path and can create accidental side effects. |
| `306.m2`  | `Relay 2 operating mode`               |                           **0 (disabled)** | Relay actions are outside the calibration path and can create accidental side effects. |
| `312.m3`  | `Relay 3 operating mode`               |                           **0 (disabled)** | Relay actions are outside the calibration path and can create accidental side effects. |
| `301-305` | `Relay 1 threshold/timing setting 1-5` | **leave default / ignored while disabled** | Non-load-bearing when relay modes are disabled.                                        |
| `307-311` | `Relay 2 threshold/timing setting 1-5` | **leave default / ignored while disabled** | Non-load-bearing when relay modes are disabled.                                        |
| `313-317` | `Relay 3 threshold/timing setting 1-5` | **leave default / ignored while disabled** | Non-load-bearing when relay modes are disabled.                                        |

**Rejected alternatives**
- Using relay thresholds as live calibration markers: possible, but unnecessary complication.

#### `C6.aNa` - Analog output block

**Recommended values** 

| Parameter | Name                        |            Recommended value | Reason                                                                                                  |
| --------- | --------------------------- | ---------------------------: | ------------------------------------------------------------------------------------------------------- |
| `600.At`  | `Analog output type`        |                 **0 (NONE)** | Keep analog output out of the reference path unless you are explicitly calibrating an analog DAQ chain. |
| `601-608` | `Analog output setting 601` | **ignored while `600.At=0`** | Non-load-bearing for the recommended digital architecture.                                              |
**Rejected alternatives**
- `AO` to external DAQ: technically valid, but inferior here to the direct digital RS485/LSL path because it adds another conversion stage.

#### `700.oP` - Password enable
#### `701.PW` - Password value
#### `C8.FAC` - Factory calibration
#### `C9.iNF` - Information block

**Recommended values** 

| Block    | Name                  | Recommended value | Reason                                                                            |
| -------- | --------------------- | ----------------: | --------------------------------------------------------------------------------- |
| `700.oP` | `Password enable`     |             **0** | No value in locking a temporary calibration bench profile.                        |
| `701.PW` | `Password value`      |         unchanged | Not part of calibration quality.                                                  |
| `C8.FAC` | `Factory calibration` | **do not modify** | Factory analog/ADC trims should not be touched without traceable instrumentation. |
| `C9.iNF` | `Information block`   |         read only | Informational only.                                                               |

**Rejected alternatives**
- Changing password, factory, or informational blocks as part of calibration setup: rejected because they do not improve calibration quality and can create avoidable configuration risk.

---

## Recommended end-to-end calibration procedure

### Phase 1 — Reference-only verification

1. Warm up the reference board + PM58 for **15–30 min**.
2. Zero unloaded.
3. Apply **at least 5 staircase holds** across the intended operating band.
4. Repeat the sequence once upward and once downward.
5. Confirm:
   - repeatability,
   - no obvious hysteresis anomaly,
   - no spontaneous zero drift,
   - no transport instability.

### Phase 2 — Dual-device capture

1. Run both devices on the same Linux host.
2. Push both streams into LSL.
3. Record to XDF.
4. Acquire:
   - **static staircase holds** for fitting,
   - **slow ramps** for monotonicity/hysteresis,
   - **short squeezes / releases** for lag validation.

### Phase 3 — Fit the target calibration model

1. Use only the **static hold windows** to fit the primary target calibration model.
2. Interpolate the regular reference stream onto the target timestamps.
3. Fit:
   - first-pass: **affine model** (`force = a*raw + b`)
   - only if residual structure remains: **piecewise-linear** or low-order nonlinear correction
4. Use the dynamic trials only to estimate:
   - relative lag,
   - smoothing requirements,
   - bandwidth mismatch,
   - hysteresis / release asymmetry.

---

## Why the chosen profile is better than the obvious alternatives

### Why not “maximum everything”?

Because the target is not a 1 kHz device.  
A 1000 Hz active-send reference stream, 600000 bps serial link, aggressive display precision, and multipoint correction everywhere would create complexity faster than it would create calibration quality.

### Why not keep the board at its defaults?

Because the defaults (`40 Hz`, heavier general-purpose weighing behavior, zero/stability helpers) are better for generic panel-meter use than for generating a clean dynamic reference against an HX711 device.

### Why not calibrate the target directly from dynamic squeezes?

Because dynamic trials mix together:
- gain,
- offset,
- transport latency,
- filter lag,
- fixture compliance,
- hysteresis,
- subject inconsistency.

Static holds identify the calibration model. Dynamic trials validate it.

---

## Limitations and unknowns

1. **Reference cell range mismatch risk.**  
   A 100 kg PM58 is acceptable if the mechanical hand-grip rig really drives a meaningful portion of that range. If your fixture only uses a very small fraction of the PM58 span, a lower-range reference cell would improve low-force SNR.

2. **Active-send epistemic gap.**  
   The board manual documents the existence and configurable rate of Active-send mode, but not its payload format. Therefore:
   - `AS=1, AF=100` is the **best-performing recommended default after one successful parser validation**.
   - `AS=0` Modbus RTU is the **highest-certainty fallback**.

3. **Target timing irregularity source unresolved.**  
   Until you profile the Arduino / USB / host ingestion chain, you should treat the target stream as genuinely irregular.

---

## Final recommendation

### Pick-now profile

**Reference board**
- `100.SP = 640`
- `101.GA = 128B`
- `102.ME = 3`
- `103.rV = 5`
- `105.uN = N`
- `106.bi = 1`
- `107.dV = 1`
- `108.ro = 900.0 N`
- `109.di = NoNE`
- `110.MZ = 5.0 N`
- `111.MN = 0.10 s`
- `113.uP = 0.05 s`
- `201.Mo = Load`
- `206.rV = 1.000`
- `207.mE = 0`
- `400.CV = 0`
- `401.dZ = 0`
- `402.tV = 0`
- `404.SV = 0`
- `405.Zr = 5.0 N`
- `406.PZ = 0`
- `409.AZ = 0`
- `412.Wr = 0`
- `500.Ar = 1`
- `501.br = 115200`
- `502.Vb = none`
- `503.so = 1`
- `504.AS = 1`
- `505.AF = 100`

**Target**
- keep the existing fastest stable acquisition path (~93 Hz empirical),
- keep `UART = 115200, 8N1`,
- emit `seq + device_timestamp + raw + interpreted`,
- disable calibration-time smoothing / auto-zero.

**Recording**
- same Linux host,
- both streams into LSL,
- reference stream advertised as regular 100 Hz,
- target stream advertised as irregular,
- record to XDF.

### Shortlist fallback

If Active-send proves too opaque:
- change only `504.AS = 0`,
- keep the same serial format,
- poll the documented Modbus registers at **100 Hz**.

That is the cleanest high-confidence fallback.

---

## Sources

### Uploaded material
- **[A1]** Reorganized acquisition-board manual extracted from the uploaded board documentation and photos: `high_speed_acquisition_instrument_reorganized_manual.md`.
- **[A2]** Practical PM58 + acquisition-board bring-up / wiring note extracted from your uploaded material: `pm58_acquisition_board_manual.md`.

### Web / primary references
- **[W1] HX711 datasheet** — selectable **10 SPS / 80 SPS**, settling-time behavior, bridge-oriented ADC design, 50/60 Hz rejection.  
  https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf
- **[W2] LSL time synchronization docs** — timestamps, clock-offset estimation, dejitter, regular-vs-irregular timing considerations.  
  https://labstreaminglayer.readthedocs.io/info/time_synchronization.html
- **[W3] LSL FAQ** — local-machine latency typically under 0.1 ms.  
  https://labstreaminglayer.readthedocs.io/info/faqs.html
- **[W4] liblsl StreamInfo docs** — irregular streams should be advertised as `IRREGULAR_RATE`.  
  https://labstreaminglayer.readthedocs.io/projects/liblsl/ref/streaminfo.html
- **[W5] Modbus Application Protocol Specification V1.1b3** — Modbus as application-layer request/reply protocol over serial or TCP transports.  
  https://www.modbus.org/file/secure/modbusprotocolspecification.pdf
- **[W6] Modbus over Serial Line Specification and Implementation Guide V1.02** — serial Modbus master/slave behavior and RS485 context.  
  https://www.modbus.org/file/secure/modbusoverserial.pdf
- **[W7] NI bridge/load-cell measurement fundamentals** — excitation, amplification, filtering, offset nulling, shunt calibration considerations for bridge-based load measurements.  
  https://www.ni.com/en/shop/data-acquisition/sensor-fundamentals/measuring-load-with-bridge-based-sensors.html
