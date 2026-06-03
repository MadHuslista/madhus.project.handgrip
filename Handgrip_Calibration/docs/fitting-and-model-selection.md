# Fitting and Model Selection

## Summary

- Fitting maps target raw counts to reference force.
- The canonical relationship is `reference_force_N = f(target_raw_count)`.
- Candidate models should be compared using residuals, cross-validated metrics, max error, monotonicity, and deployment complexity.
- Diagnostics such as hysteresis and drift should explain failure modes; they should not automatically become deployment models.

## Fitting command

```bash
cd Handgrip_Calibration
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected outputs include a calibration dataset, selected fit result, candidate comparisons, and model-selection report artifacts.

## Primary model form

The simplest deployable model is affine:

```text
force_N = a * raw_count + b
```

This is usually preferred when it passes residual and holdout validation because it is simple, interpretable, and deployable to firmware or bridge processing.

## Candidate model roles

| Candidate                      | Role                                                       | Deployment note                                        |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------ |
| `affine_ols`                   | Baseline straight-line fit.                                | Simple but sensitive to outliers.                      |
| `affine_wls`                   | Weighted affine fit when reference noise varies by hold.   | Often preferred affine candidate.                      |
| `affine_huber`                 | Robust affine fit when some holds are mildly contaminated. | Good candidate when outliers are present.              |
| `quadratic_wls`                | Nonlinear correction candidate.                            | Deploy only if materially justified and repeatable.    |
| `piecewise_linear_monotone`    | Monotone multipoint correction.                            | Useful when nonlinear but monotone behavior is stable. |
| `odr_affine`                   | Errors-in-variables / Deming-style diagnostic.             | Diagnostic unless explicitly deployable.               |
| `hysteresis_affine_diagnostic` | Ascending vs descending split diagnostic.                  | Indicates mechanical/load-path issues.                 |
| `drift_affine_diagnostic`      | Time-dependent drift diagnostic.                           | Indicates warm-up, creep, or baseline issues.          |

## Metrics to inspect

| Metric                               | Meaning                                             | Risk if ignored                                     |
| ------------------------------------ | --------------------------------------------------- | --------------------------------------------------- |
| RMSE                                 | Overall fit error on accepted holds.                | Model may look good visually but fail numerically.  |
| CV RMSE                              | Cross-validated generalization error.               | Overfit models may be selected.                     |
| max absolute error                   | Worst-case error.                                   | Local bad region may be hidden by average metrics.  |
| max error percent of operating range | Normalized deployment threshold.                    | Results cannot be compared across ranges.           |
| monotonicity                         | Force should increase monotonically with raw count. | Nonphysical mapping may be deployed.                |
| residual by force                    | Bias/curvature across force levels.                 | Hidden nonlinearity or low-force weakness.          |
| residual by direction                | Up/down hysteresis.                                 | Mechanical asymmetry can masquerade as model error. |
| residual by time                     | Drift.                                              | Warm-up/creep can invalidate calibration.           |

## Selection policy

Recommended policy:

1. Reject invalid or non-monotone deployable models.
2. Reject models that fail max-error/residual threshold.
3. Prefer lower cross-validated RMSE.
4. Penalize high max absolute error.
5. Penalize unnecessary complexity.
6. Prefer the simpler model when performance is similar.
7. Treat diagnostic models as explanatory unless deliberately promoted.

## Deployment criterion

If the operating range is 100 N and the residual threshold is 0.5% of range:

```text
max_abs_error_N <= 0.005 * 100 N = 0.5 N
```

A selected model should not be deployed unless:

- it passes the residual threshold,
- holdout validation passes,
- residual plots show no unacceptable structure,
- the accepted holds cover the intended operating range,
- the physical fixture was validated.

## Firmware constants from affine fit

If the accepted affine model is:

```text
force_N = a * raw_count + b
```

and firmware computes:

```text
current_units = (raw_count - SCALE_OFFSET) / SCALE_FACTOR
```

then equivalent firmware constants are:

```text
SCALE_FACTOR = 1 / a
SCALE_OFFSET = -b / a
```

Only apply this if:

- `a != 0`,
- the firmware formula has not changed,
- the report explicitly recommends firmware deployment,
- post-deployment validation is run.

## Drift tracking across sessions

When repeating calibration over time, compare these fields across `fit_result.json` files:

```text
session_id, selected_model_id, a, b, rmse_N, max_abs_error_N,
max_abs_error_percent_range, passes_residual_threshold, selection_likelihood
```

| Observation                         | Interpretation                            | Action                                           |
| ----------------------------------- | ----------------------------------------- | ------------------------------------------------ |
| `a` changes, `b` stable             | Sensitivity/span change.                  | Inspect HX711/load-cell gain path and mechanics. |
| `b` changes, `a` stable             | Offset/zero shift.                        | Inspect preload, tare, thermal zero drift.       |
| Both `a` and `b` shift              | Mechanical setup changed or sensor aging. | Repeat reference-only verification.              |
| RMSE rises but coefficients similar | Noisy holds or operator instability.      | Improve hold stability or fixture.               |
| Hysteresis diagnostic worsens       | Fixture compliance/contact issue.         | Inspect load path and preloading.                |
| Drift diagnostic worsens            | Warm-up or creep.                         | Add warm-up; verify auto-zero is disabled.       |

## Common interpretation mistakes

| Mistake                                        | Why it is wrong                                  |
| ---------------------------------------------- | ------------------------------------------------ |
| Choosing the smoothest curve                   | Smoothness is not deployment validity.           |
| Choosing the lowest training RMSE only         | It may overfit.                                  |
| Ignoring max error                             | One force region may be unusable.                |
| Fitting `current_units` instead of `raw_count` | It fits against mutable firmware constants.      |
| Deploying without holdout                      | Fit data is not independent validation.          |
| Treating hysteresis as a pure software problem | It may be mechanical fixture/load-path behavior. |

