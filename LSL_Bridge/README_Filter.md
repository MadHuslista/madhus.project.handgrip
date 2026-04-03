# Filter Module Configuration Guide

This document explains how to configure the filter module used by the bridge, based on:

- `LSL_Bridge/filter.py`
- `LSL_Bridge/conf/config.yaml`

It covers all currently available filters, every supported parameter, valid ranges and constraints, multiple-filter configuration, execution order, and behavior details.

## 1. Where Filter Configuration Lives

Filtering is configured in `processing` inside `LSL_Bridge/conf/config.yaml`:

```yaml
processing:
  module: filter
  timestamp_source: device_clock_us   # device_clock_us | lsl
  filters:
    - type: lowpass_1pole
      cutoff_hz: 1.0
    - type: drift_corrector
      baseline_cutoff_hz: 0.02
```

### `processing` keys used by the filter module

- `module`
  - Must be `filter` to use `LSL_Bridge/filter.py`.
- `timestamp_source`
  - `device_clock_us`: filter time comes from device clock (converted to seconds in bridge).
  - `lsl`: filter time comes from host LSL timestamp.
- `filters`
  - Ordered list of filter nodes.
  - Each node must have `type` matching a supported filter.

## 2. Supported Filter Types

The filter factory (`_build_filter_node`) supports exactly these `type` values:

- `lowpass_1pole`
- `drift_corrector`
- `identity`

Any other type raises:

```text
ValueError: Unsupported filter type: <type>
```

## 3. How Multiple Filters Are Applied

Filters are applied sequentially in declaration order.

If your config is:

```yaml
processing:
  filters:
    - type: A
    - type: B
    - type: C
```

execution is:

```text
raw_value -> A -> B -> C -> filtered_value
```

Important points:

- Order is deterministic and based on YAML list order.
- Order changes output.
- Output of filter N becomes input to filter N+1.
- Each filter is stateful across samples.

## 4. Filter Reference

## `lowpass_1pole`

One-pole low-pass filter (`FirstOrderLowPass`) for smoothing high-frequency noise.

### Typical use

- Reduce sample-to-sample jitter before downstream logic.

### Config snippet

```yaml
processing:
  filters:
    - type: lowpass_1pole
      cutoff_hz: 1.0
      reset_on_gap_s: 1.0
      min_dt_s: 0.000001
```

### Parameters

- `cutoff_hz`
  - Type: float
  - Default: none (required)
  - Constraint: must be `> 0`
  - Meaning: cutoff frequency. Internally sets `tau = 1 / (2 * pi * cutoff_hz)`.
  - Practical effect:
    - lower value = stronger smoothing, more lag
    - higher value = less smoothing, less lag

- `reset_on_gap_s`
  - Type: float
  - Default: `1.0`
  - Hard validation in code: none
  - Expected safe range: `>= 0`
  - Meaning: if time gap `dt` between samples exceeds this threshold, state resets.

- `min_dt_s`
  - Type: float
  - Default: `1e-6`
  - Hard validation in code: none
  - Expected safe range: `> 0`
  - Meaning: lower bound for `dt` used in coefficient calculation, avoiding near-zero issues.

### Algorithm details

- First sample:
  - Initializes internal state and returns raw input value.
- Regular update:
  - `dt = max(min_dt_s, t_now - t_prev)`
  - `alpha = dt / (tau + dt)`
  - `y = y + alpha * (x - y)`
- Gap reset:
  - If `dt > reset_on_gap_s`, logs warning and re-initializes to current sample.

### Runtime warning

```text
Low-pass filter state reset after large gap: dt=...s > ...s
```

## `drift_corrector`

Baseline drift removal filter (`DriftCorrector`). Output is input minus estimated baseline.

### Typical use

- Remove slow baseline drift while preserving faster force changes.

### Config snippet

```yaml
processing:
  filters:
    - type: drift_corrector
      baseline_cutoff_hz: 0.02
      rest_band: 5.0
      stable_slope_threshold_per_s: 5.0
      warmup_samples: 20
      reset_on_gap_s: 1.0
      min_dt_s: 0.000001
```

### Parameters

- `baseline_cutoff_hz`
  - Type: float
  - Default: `0.02`
  - Constraint: must be `> 0`
  - Meaning: smoothing speed of baseline estimate (lower = slower baseline adaptation).

- `rest_band`
  - Type: float
  - Default: `5.0`
  - Constraint: must be `>= 0`
  - Meaning: if `abs(value - baseline) <= rest_band`, signal is treated as near-rest and baseline can update.

- `stable_slope_threshold_per_s`
  - Type: float
  - Default: `5.0`
  - Constraint: must be `>= 0`
  - Meaning: if slope `abs(value - last_input) / dt` is below threshold, baseline can update.

- `warmup_samples`
  - Type: int
  - Default: `20`
  - Constraint: must be `>= 0`
  - Meaning: number of initial samples where baseline updates unconditionally.

- `reset_on_gap_s`
  - Type: float
  - Default: `1.0`
  - Hard validation in code: none
  - Expected safe range: `>= 0`
  - Meaning: reset baseline state after large sample gap.

- `min_dt_s`
  - Type: float
  - Default: `1e-6`
  - Hard validation in code: none
  - Expected safe range: `> 0`
  - Meaning: lower bound for `dt` used in slope and baseline updates.

### Algorithm details

- First sample:
  - Initializes baseline to input and returns `0.0`.
- Regular update:
  - `dt = max(min_dt_s, t_now - t_prev)`
  - `slope = abs(value - last_input) / dt`
  - Update baseline if any is true:
    - still in warmup (`sample_count < warmup_samples`), or
    - near-rest (`abs(value - baseline) <= rest_band`), or
    - stable slope (`slope <= stable_slope_threshold_per_s`)
  - Output: `corrected = value - baseline`
- Gap reset:
  - If `dt > reset_on_gap_s`, state resets and output is `0.0` for that sample.

### Runtime warning

```text
Drift corrector state reset after large gap: dt=...s > ...s
```

## `identity`

Pass-through filter (`IdentityProcessor`): output equals input.

### Typical use

- Disable filtering while keeping pipeline wiring active.
- Compare raw vs filtered path behavior in diagnostics.

### Config snippet

```yaml
processing:
  filters:
    - type: identity
```

### Parameters

- No parameters.

## 5. Validation and Error Conditions

## Hard-validated constraints

From `__post_init__`:

- `lowpass_1pole.cutoff_hz > 0`
- `drift_corrector.baseline_cutoff_hz > 0`
- `drift_corrector.rest_band >= 0`
- `drift_corrector.stable_slope_threshold_per_s >= 0`
- `drift_corrector.warmup_samples >= 0`

Violations raise `ValueError` and stop startup.

## Factory/type errors

- Unknown `type` -> `ValueError`.
- Missing required key for low-pass (`cutoff_hz`) -> config access error during construction.

## 6. Complete Configuration Examples

## A) Default chain (recommended starting point)

```yaml
processing:
  module: filter
  timestamp_source: device_clock_us
  filters:
    - type: lowpass_1pole
      name: lowpass_1hz
      cutoff_hz: 1.0
      reset_on_gap_s: 1.0
      min_dt_s: 0.000001
    - type: drift_corrector
      name: slow_drift_corrector
      baseline_cutoff_hz: 0.02
      rest_band: 5.0
      stable_slope_threshold_per_s: 5.0
      warmup_samples: 20
      reset_on_gap_s: 1.0
      min_dt_s: 0.000001
```

## B) Low-pass only

```yaml
processing:
  module: filter
  timestamp_source: device_clock_us
  filters:
    - type: lowpass_1pole
      cutoff_hz: 2.0
```

## C) Drift corrector only

```yaml
processing:
  module: filter
  timestamp_source: device_clock_us
  filters:
    - type: drift_corrector
      baseline_cutoff_hz: 0.01
      rest_band: 3.0
      stable_slope_threshold_per_s: 4.0
      warmup_samples: 30
```

## D) Passthrough mode

```yaml
processing:
  module: filter
  timestamp_source: device_clock_us
  filters:
    - type: identity
```

## E) Three-stage chain example

```yaml
processing:
  module: filter
  timestamp_source: lsl
  filters:
    - type: lowpass_1pole
      cutoff_hz: 3.0
    - type: drift_corrector
      baseline_cutoff_hz: 0.03
      rest_band: 4.0
    - type: lowpass_1pole
      cutoff_hz: 1.5
```

This is applied exactly in listed order.

## 7. Tuning Guidance

1. Start with `identity` to verify data flow and timing.
2. Add `lowpass_1pole` and tune `cutoff_hz` for acceptable noise/lag balance.
3. Add `drift_corrector` for baseline drift.
4. Tune one parameter at a time.
5. Watch output columns:
   - `value_raw`
   - `value_filtered`
6. If you see frequent reset warnings, review timestamp continuity and `reset_on_gap_s`.

## 8. Time Source Implications

Because filters are time-dependent, `processing.timestamp_source` changes behavior:

- `device_clock_us`
  - Uses device-derived elapsed time.
  - Usually best when device clock is stable and monotonic.
- `lsl`
  - Uses host receive-time basis.
  - Can be useful if device clock has discontinuities.

If timing is non-monotonic or large gaps occur, filters may reset or produce temporary transients.

## 9. Notes on Optional `name` Fields

In `config.yaml`, filter items may include `name` keys (for readability), for example:

```yaml
- type: lowpass_1pole
  name: lowpass_1hz
  cutoff_hz: 1.0
```

Current implementation ignores `name` at runtime. It is safe to keep for documentation clarity.

## 10. Adding a New Filter Type (Developer Workflow)

To add a new configurable filter type:

1. Implement a class with:
   - `process(self, value: float, sample_time_s: float) -> float`
2. Add parameter validation in `__post_init__` if using a dataclass.
3. Add a branch in `_build_filter_node(filter_cfg)` that creates your filter from YAML keys.
4. Add a config example under `processing.filters` in `conf/config.yaml`.
5. Update this `README_Filter.md` with parameter reference and constraints.

Template pattern:

```python
@dataclass(slots=True)
class MyFilter:
    my_param: float = 1.0

    def __post_init__(self) -> None:
        if self.my_param <= 0:
            raise ValueError("my_param must be > 0")

    def process(self, value: float, sample_time_s: float) -> float:
        _ = sample_time_s
        return value
```

And in `_build_filter_node`:

```python
if filter_type == "my_filter":
    return MyFilter(my_param=float(filter_cfg.get("my_param", 1.0)))
```

## 11. Quick Checklist

Before running:

- `processing.module` is `filter`.
- Every filter has a valid `type`.
- `lowpass_1pole.cutoff_hz` is present and `> 0`.
- Drift-corrector constraints are respected.
- Filter order matches intended processing order.
- `timestamp_source` is chosen intentionally.
