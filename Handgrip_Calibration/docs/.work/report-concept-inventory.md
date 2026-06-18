# Calibration Report — Concept Inventory

---
- **Creation Date**: 2026-06-17
- **Last Updated** : 2026-06-17
- **Branch@Commit**: general_overview@7f9a1d2
- **Scope**: Checklist of every plot, model, and metric that appears in the calibration report, used to drive the extended reference doc and the report-generator interpretation upgrade.
- **Purpose**: Phase A review gate — confirm completeness/accuracy before sourcing and writing.
- **Claude Plan Path**: /home/levi/.claude/plans/lexical-stargazing-noodle.md
- **Version**: 1.0
---

> **REVIEW GATE.** Please review, add missing items, and correct inaccuracies. Nothing else is written until this is approved.

Status legend: `cover?` = will be documented in reference doc + given dynamic interpretation in report (Y), documented only / static (D), or open question (?).

## 1. Plots (9)

| #   | Plot stem                     | What it shows                                                                                  | Source in code               | cover? |
| --- | ----------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------- | ------ |
| 1   | `target_timeseries`           | Target sensor raw counts vs time since start                                                   | `report.py generate_plots()` | Y      |
| 2   | `reference_timeseries`        | Reference force/raw vs time since start                                                        | same                         | Y      |
| 3   | `model_comparison_curve`      | Accepted-hold scatter (raw → force) with each deployable candidate curve; selected highlighted | same                         | Y      |
| 4   | `selected_residuals_by_force` | Residual (N) vs reference force for the selected model                                         | same                         | Y      |
| 5   | `model_comparison_residuals`  | Residual scatter per candidate, overlaid                                                       | same                         | Y      |
| 6   | `model_metric_bars`           | RMSE and Max-abs-error bars per model                                                          | same                         | Y      |
| 7   | `model_likelihoods`           | Selection-likelihood bars per model                                                            | same                         | Y      |
| 8   | `robust_huber_weights`        | Per-hold robust training weight (only when `affine_huber` fitted)                              | same                         | Y      |
| 9   | `hysteresis_up_down`          | Ascending vs descending raw at each force level                                                | same                         | Y      |

## 2. Models (8)

| #   | model_id                       | Family                     | Role                 | One-line                                                            | cover? |
| --- | ------------------------------ | -------------------------- | -------------------- | ------------------------------------------------------------------- | ------ |
| 1   | `affine_ols`                   | affine                     | deployable (default) | Ordinary least-squares straight line `force = a·raw + b`            | Y      |
| 2   | `affine_wls`                   | affine_weighted            | deployable           | Weighted least squares (down-weights noisy holds)                   | Y      |
| 3   | `affine_huber`                 | affine_robust              | deployable           | Robust line via Huber loss (resists outliers), `huber_epsilon=1.35` | Y      |
| 4   | `quadratic_wls`                | polynomial_degree_2        | deployable           | Degree-2 polynomial weighted fit                                    | Y      |
| 5   | `piecewise_linear_monotone`    | monotone_multipoint        | deployable           | Monotone point-to-point interpolation                               | Y      |
| 6   | `odr_affine`                   | affine_odr                 | diagnostic           | Orthogonal distance regression (error in raw and force)             | Y      |
| 7   | `drift_affine_diagnostic`      | affine_plus_time_drift     | diagnostic           | Affine + time-drift term (detects within-session drift)             | Y      |
| 8   | `hysteresis_affine_diagnostic` | direction_dependent_affine | diagnostic           | Separate affine per loading direction (quantifies hysteresis)       | Y      |

## 3. Metrics & fit-result fields

### 3a. Fit error metrics
| Field                         | Meaning                                     | cover? |
| ----------------------------- | ------------------------------------------- | ------ |
| `rmse_N`                      | Root-mean-square error (N)                  | Y      |
| `mae_N`                       | Mean absolute error (N)                     | Y      |
| `max_abs_error_N`             | Worst single-point absolute error (N)       | Y      |
| `max_abs_error_percent_range` | Worst error as % of operating range         | Y      |
| `r2`                          | Coefficient of determination                | Y      |
| `adjusted_r2`                 | R² penalized for parameter count            | Y      |
| `residual_bias_N`             | Mean residual (systematic offset)           | Y      |
| `residual_std_N`              | Std-dev of residuals                        | Y      |
| `aicc`                        | Akaike Information Criterion (small-sample) | Y      |
| `bic`                         | Bayesian Information Criterion              | Y      |

### 3b. Cross-validation metrics
| Field                            | Meaning                                                               | cover? |
| -------------------------------- | --------------------------------------------------------------------- | ------ |
| `cv_rmse_N`                      | RMSE under cross-validation (generalization)                          | Y      |
| `cv_mae_N`                       | MAE under CV                                                          | Y      |
| `cv_max_abs_error_N`             | Max abs error under CV                                                | Y      |
| `cv_max_abs_error_percent_range` | …as % of range                                                        | Y      |
| `cv_rmse_se_N`                   | Std-error of CV RMSE across folds (stability)                         | Y      |
| `cv_fold_count`                  | Number of CV folds                                                    | D      |
| `cv_point_count`                 | Points used in CV                                                     | D      |
| `cv_coverage_fraction`           | Fraction of points covered by CV (vs `min_cv_coverage_fraction=0.50`) | Y      |

### 3c. Selection / deployment fields
| Field                              | Meaning                                                                                                 | cover? |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- | ------ |
| `selection_score`                  | Weighted penalty score (lower=better): `40·cv_rmse/range + 60·maxerr/range + 0.15·n_params` + penalties | Y      |
| `selection_likelihood`             | Softmax of `-score` across eligible models (sums to 1; higher=preferred)                                | Y      |
| `n_parameters`                     | Free parameters in model                                                                                | D      |
| `accepted_for_deployment`          | Passed deploy gates                                                                                     | Y      |
| `diagnostic_only`                  | Excluded from deployment by design                                                                      | Y      |
| `rejection_reasons`                | Why a candidate was rejected                                                                            | Y      |
| `residual_threshold_percent_range` | Advisory max-error gate (% of range)                                                                    | Y      |
| `passes_residual_threshold`        | Whether selected model met the gate                                                                     | Y      |

### 3d. Parameters & firmware export
| Field                            | Meaning                              | cover? |
| -------------------------------- | ------------------------------------ | ------ |
| `model_parameters {a,b}`         | Fitted coefficients                  | Y      |
| `recommended_firmware_constants` | `a,b` + HX711-style `scale`/`offset` | Y      |

### 3e. Holdout validation (`holdout_validation.json`)
| Field                                                             | Meaning                               | cover? |
| ----------------------------------------------------------------- | ------------------------------------- | ------ |
| `metrics.{rmse_N,mae_N,max_abs_error_N,bias_N,residual_std_N,r2}` | Accuracy on independent holdout holds | Y      |
| `thresholds.{max_rmse_N,max_abs_error_N,max_bias_N}`              | Release-gate limits                   | Y      |
| `passes_holdout_gate`                                             | Pass/fail verdict                     | Y      |
| `firmware_deployment_recommendation`                              | Final deploy call                     | Y      |

### 3f. Acquisition / static-fit summary
| Field                                         | Meaning                            | cover? |
| --------------------------------------------- | ---------------------------------- | ------ |
| `sample_rate_hz` / `max_gap_s`                | Stream health (target & reference) | Y      |
| `reference_force_std_N`                       | Reference noise during holds       | Y      |
| `reference_slope_N_s`                         | Reference drift during holds       | Y      |
| `target_seq_gap_count`                        | Dropped-sample count               | D      |
| hysteresis deltas (`*_delta_desc_minus_asc*`) | Up-vs-down difference per level    | Y      |

### 3g. Schema documentation (no value, structural)
| Item                             | Meaning                                            | cover? |
| -------------------------------- | -------------------------------------------------- | ------ |
| `handgrip_fit_result.v2`         | Top-level fit-result schema + field-by-field guide | Y      |
| `model_ranking[]` entry          | Per-candidate ranking record fields                | Y      |
| `handgrip_holdout_validation.v1` | Holdout-result schema                              | Y      |

## Open questions for the reviewer
1. Doc filename `calibration-report-reference.md` acceptable? (sits beside existing `reports-and-outputs.md`).
2. Any concept above marked `D` (static-only) you actually want a **dynamic** interpretation for?
3. Anything missing — e.g. the **reference-chain verification** table, **event counts/summary**, or **firmware HX711 scale/offset** — that you want full reference + interpretation treatment rather than a brief note?
