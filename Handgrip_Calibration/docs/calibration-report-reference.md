# Calibration Report Reference

---
- **Creation Date**: 2026-06-17
- **Last Updated**: 2026-06-18
- **Branch@Commit**: general_overview@00d5972
- **Applies to**: `Handgrip_Calibration/data/calibration/*/calibration_report.md`, `fit_result.json`, `fit_candidates.json`, `holdout_validation.json`, and generated `plots/`.
- **Scope**: Static, non-expert reference for every metric, model, plot, table, and schema field shown in the generated calibration report; provides stable concept-ID anchors deep-linked from the generated report.
- **Purpose**: Let a reviewer understand what each number, model, plot, and table means, and how to judge whether a calibration is safe to use.
- **Claude Plan Path**: /home/levi/.claude/plans/lexical-stargazing-noodle.md
- **Version**: 1.0
---

## 1. How to read this reference

This document explains the static concepts used by the Handgrip calibration report. It is written for reviewers who need to understand what each number, model, plot, and table means before deciding whether a calibration is safe to use.

A calibration report is not only a curve fit. It is a chain of evidence:

1. The target and reference streams were captured cleanly.
2. Static holds were segmented and accepted by quality gates.
3. Candidate models were fitted to accepted holds.
4. The selected model was checked against residual thresholds and cross-validation.
5. If available, an independent holdout session was used as a final deployment gate.
6. Firmware constants were exported only after the fit and holdout checks were acceptable.

The report follows the standard calibration idea of relating a sensor response to known or reference loads, then using that fitted relationship to estimate future loads. NIST describes load-cell calibration this way: a model relates a known load to a cell response and is then used for readings of unknown magnitude [R02]. NIST force-calibration service material also notes that calibration commonly derives polynomial equations from force/response data [R18].

## 2. Quick decision reading order

Read the report in this order when making a deployment decision:

1. **Firmware deployment recommendation**: If this says `do_not_deploy...`, stop and investigate.
2. **Holdout accuracy summary**: Prefer decisions based on independent holdout data. A good fit on the same holds used for training is not enough.
3. **Residual threshold pass**: Confirms the selected fit did not exceed the configured worst-error gate.
4. **Model candidate ranking**: Check whether a more complex model only marginally improves the score.
5. **Residual plots**: Look for curvature, load-dependent bias, outliers, or direction-specific effects. NIST emphasizes graphical residual analysis because residual plots reveal patterns that a single number may hide [R01].
6. **Reference-chain verification summary**: Confirm the data capture itself was healthy before trusting the model.
7. **Hysteresis / creep / dynamic sections**: Treat these as diagnostic layers. They should influence whether to trust the calibration, not silently change the primary static fit.

## 3. Core calibration vocabulary

### 3.1 Target stream

The **target stream** is the handgrip sensor being calibrated. In the current report it is usually represented as raw counts or target units. The fitting stage treats its median value during a stable hold as the independent input variable: `target_raw_median`.

Interpretation: if the target raw value is noisy, discontinuous, or direction-dependent, the calibration may be unstable even if a fitted line looks good.

### 3.2 Reference stream

The **reference stream** is the force/reference device used as the temporary ground truth. In this project it is the RS485 reference chain. The fitting stage usually uses `reference_force_median_N` as the output variable in Newtons.

Interpretation: the reference stream must be cleaner and more trustworthy than the target stream. The report therefore starts with stream health and reference-chain verification before model quality.

### 3.3 Static hold

A **static hold** is a protocol interval where the operator holds a nominal force level long enough for the target and reference readings to stabilize. Static staircase holds are the primary fitting material. Dynamic trials are validation/diagnostic material, not primary coefficient estimators.

### 3.4 Residual

A **residual** is the observed response minus the model prediction for the same point. In the calibration report:

```text
residual_N = reference_force_median_N - predicted_force_N
```

Positive residual means the model predicted too low. Negative residual means the model predicted too high. NIST defines residuals as the difference between observed responses and corresponding fitted-model predictions [R01].

### 3.5 Operating range

The **operating range** is the configured force range over which the calibration is expected to be used. Percent-range errors divide Newton error by this configured range. This is useful because a 1 N error has different meaning on a 20 N instrument versus a 100 N instrument.

## 4. Report sections

<a id="sec.summary"></a>
### 4.1 Summary

The summary gives the minimum deployment context:

- `Session ID`: the session directory name.
- `Operator`: operator from the session manifest if available.
- `Purpose`: why the session was recorded.
- `Protocol`: protocol name and type.
- `Selected model`: model selected by the model-selection policy.
- `Model-selection likelihood`: normalized relative decision weight among eligible candidates.
- `Affine-compatible equation`: `force_N = a * raw + b` when available.
- `RMSE`: root-mean-square error on accepted calibration holds.
- `Max abs error`: worst accepted-hold residual magnitude.
- `Residual threshold pass`: selected-model gate result.
- `Firmware deployment recommendation`: final report-level deployment call.

Interpretation: this section is a dashboard. Do not use it alone to approve a calibration.

<a id="sec.reference_chain"></a>
### 4.2 Reference-chain verification summary

This section checks whether target/reference acquisition looked healthy before fitting. It includes:

| Field                       | Meaning                          | How to interpret                                                                   |
| --------------------------- | -------------------------------- | ---------------------------------------------------------------------------------- |
| `stream`                    | Target or reference stream.      | Both should be present for a valid calibration.                                    |
| `n_samples`                 | Number of samples captured.      | Very low counts imply missing data or short capture.                               |
| `duration_s`                | Stream duration in seconds.      | Target/reference durations should roughly cover the same experiment.               |
| `sample_rate_hz`            | Approximate sample rate.         | Compare to expected target/reference rates. Large deviations imply capture issues. |
| `max_gap_s`                 | Largest timestamp gap.           | Large gaps indicate dropped data, blocking, or stream interruption.                |
| `value_col`                 | Data column used for statistics. | Confirms the report selected the intended signal.                                  |
| `mean`, `std`, `min`, `max` | Basic value statistics.          | Useful for detecting saturation, out-of-range values, or unexpected units.         |

Line plots are appropriate here because they show values against elapsed time [R14].

<a id="sec.events"></a>
### 4.3 Event counts and event summary

The report counts each marker event and later lists event rows. These tables check whether the protocol structure was captured correctly.

Important events include `session_start`, `series_start`, `hold_start`, `stable_window_start`, `trial_accept`, `hold_end`, `calibration_candidate_selected`, `firmware_constants_exported`, and `session_end`.

Interpretation: missing or mismatched event counts usually mean the report should be treated as incomplete, even if the numeric fit succeeds.

<a id="sec.static_fit"></a>
### 4.4 Static fit summary

The static fit summary aggregates quality information over accepted holds:

| Field                              | Meaning                                        | Interpretation                                                              |
| ---------------------------------- | ---------------------------------------------- | --------------------------------------------------------------------------- |
| `accepted_holds`                   | Holds accepted by operator/segmentation.       | More force levels and repeats generally make model selection more reliable. |
| `quality_pass_holds`               | Holds passing automatic quality checks.        | If lower than accepted holds, inspect rejection reasons.                    |
| `reference_force_std_N_median/max` | Reference noise during holds.                  | Lower is better. High values mean unstable reference force.                 |
| `reference_slope_N_s_median/max`   | Reference drift trend during holds.            | Near zero is better for static calibration.                                 |
| `reference_sample_rate_hz_*`       | Reference stream sampling health during holds. | Should match expected reference acquisition rate.                           |
| `target_sample_rate_hz_*`          | Target stream sampling health during holds.    | Should match expected target acquisition rate.                              |
| `target_seq_gap_count_*`           | Dropped-sample / sequence gap count.           | Nonzero values indicate target stream discontinuity.                        |

<a id="sec.accepted_holds"></a>
### 4.5 Accepted hold dataset

Each row represents one static hold used or considered for fitting.

| Field                      | Meaning                                             | Interpretation                                                 |
| -------------------------- | --------------------------------------------------- | -------------------------------------------------------------- |
| `trial_id`                 | Unique hold identifier.                             | Use it to trace outliers back to protocol events.              |
| `target_force_nominal_N`   | Nominal force requested by protocol.                | Protocol target, not necessarily the measured reference force. |
| `direction`                | Loading path: `ascending`, `descending`, or `flat`. | Used for hysteresis/reversibility checks.                      |
| `target_raw_median`        | Median target raw value during stable window.       | Main x-value used for fitting.                                 |
| `reference_force_median_N` | Median reference force during stable window.        | Main y-value used for fitting.                                 |
| `reference_force_std_N`    | Reference variability during the hold.              | Used as noise evidence and weighting input.                    |
| `reference_slope_N_s`      | Reference drift over the hold.                      | Large magnitude means the force was still changing.            |
| `accepted_by_quality`      | Automatic quality gate result.                      | False rows should not be trusted for primary fitting.          |
| `quality_rejection_reason` | Gate failure reason.                                | Use it to fix protocol or acquisition issues.                  |

Medians and robust scale estimates are used because they are less sensitive to short spikes than simple means; SciPy describes median absolute deviation as a robust dispersion measure [R12].

<a id="sec.holdout"></a>
### 4.6 Holdout accuracy summary

Holdout validation applies the selected model to an independent session. It does not refit the model. This is the strongest deployment evidence in the report because it estimates performance on data not used for fitting. Cross-validation uses train/test splits for the same general reason: estimate performance on unseen data [R11].

Holdout fields:

| Field                                | Meaning                                  | Interpretation                                       |
| ------------------------------------ | ---------------------------------------- | ---------------------------------------------------- |
| `n_points`                           | Number of accepted holdout points.       | Too few points make the holdout gate weak.           |
| `rmse_N`                             | Holdout RMSE.                            | Typical error magnitude on independent holds.        |
| `mae_N`                              | Holdout MAE.                             | Average absolute error; easier to explain than RMSE. |
| `max_abs_error_N`                    | Worst holdout error.                     | Important for safety/release gate.                   |
| `max_abs_error_percent_range`        | Worst holdout error as percent of range. | Normalized severity.                                 |
| `bias_N`                             | Mean signed holdout residual.            | Nonzero bias indicates systematic offset.            |
| `residual_std_N`                     | Residual spread after bias.              | Shows consistency independent of mean offset.        |
| `r2`                                 | Holdout coefficient of determination.    | Useful but should not override residual errors.      |
| `thresholds.*`                       | Configured release limits.               | Deployment gate values.                              |
| `passes_holdout_gate`                | Boolean holdout verdict.                 | If false, do not deploy without investigation.       |
| `firmware_deployment_recommendation` | Final holdout-based recommendation.      | Should agree with report-level recommendation.       |

<a id="diag.hysteresis_deltas"></a>
### 4.7 Hysteresis / reversibility summary

Hysteresis means the sensor can report a different raw value at the same force depending on whether force is increasing or decreasing. The report computes descending-minus-ascending differences at force levels where both directions exist.

| Field                                    | Meaning                                  | Interpretation                                                           |
| ---------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------ |
| `force_N`                                | Nominal force level compared.            | Only levels with both directions appear.                                 |
| `n_ascending`, `n_descending`            | Number of holds per direction.           | One per direction is a weak estimate; repeated cycles are better.        |
| `target_raw_delta_desc_minus_asc`        | Difference in target raw median.         | Large values indicate load-path dependence in the target sensor/fixture. |
| `reference_force_delta_desc_minus_asc_N` | Reference force difference by direction. | Helps separate target hysteresis from reference/operator force mismatch. |

ISO 376 preview material explicitly distinguishes increasing and decreasing force series and includes reversibility error as a force-proving instrument characteristic [R17].

<a id="diag.creep_zero_return"></a>
### 4.8 Creep / zero-return summary

Creep is slow output change while load is held. Zero-return checks whether the instrument returns close to its unloaded baseline after load removal. ISO 376 preview material includes a creep test and describes readings after force application or removal; it also notes zero changes after unloading as a diagnostic sign [R17].

| Field                     | Meaning                                | Interpretation                          |
| ------------------------- | -------------------------------------- | --------------------------------------- |
| `phase`                   | `creep` or `zero_return`.              | Which diagnostic window was summarized. |
| `target_force_N`          | Target force for the diagnostic phase. | The load level being tested.            |
| `duration_s`              | Phase duration.                        | Longer windows reveal slow effects.     |
| `n_reference_samples`     | Reference samples in the phase.        | Low counts weaken the estimate.         |
| `reference_start_mean_N`  | Mean force near phase start.           | Baseline for change.                    |
| `reference_end_mean_N`    | Mean force near phase end.             | End state.                              |
| `delta_end_minus_start_N` | End minus start.                       | Slow drift or return error.             |
| `slope_N_per_s`           | Linear trend over the phase.           | Direction and magnitude of slow change. |

<a id="diag.dynamic_summary"></a>
### 4.9 Dynamic validation summary

Dynamic trials are ramps or squeezes. The current report records metadata such as `peak_force_N` and `speed_N_per_s`, but does not use them to fit primary static coefficients.

Interpretation: dynamic data is useful for lag, transient behavior, and real-use validation. Do not tune static calibration coefficients to dynamic artifacts before static performance is stable.

<a id="field.firmware_deployment_recommendation"></a>
### 4.10 Firmware deployment recommendation

The report approves firmware constants only when the selected model passes residual gates and, when available, the independent holdout passes its gate.

Interpretation: `approve_constants_for_deployment` means the current evidence supports deployment. It does not mean the calibration is valid outside the calibrated raw-count and force range.

## 5. Plots

<a id="plot.target_timeseries"></a>
### 5.1 `target_timeseries`

A line plot of target raw counts/units against elapsed time. Line plots display y-values against x-values and are appropriate for visualizing streams over time [R14].

Look for:

- missing intervals or sudden timestamp gaps,
- hard clipping or saturation,
- unexpected jumps unrelated to protocol events,
- drift while force should be stable.

<a id="plot.reference_timeseries"></a>
### 5.2 `reference_timeseries`

A line plot of reference raw/force against elapsed time.

Look for:

- whether force steps align with the protocol,
- whether stable windows are actually stable,
- whether the reference device has backlog, sudden jumps, or visible drift.

<a id="plot.model_comparison_curve"></a>
### 5.3 `model_comparison_curve`

A scatter plot of accepted holds plus candidate calibration curves. Scatter plots place paired x/y observations at their data positions [R15]. The candidate curves show how each deployable model maps target raw values to force.

Look for:

- whether a straight line already explains the data,
- whether nonlinear curves are materially different or only cosmetic,
- whether any curve behaves oddly near endpoints,
- whether selected model is reasonable inside the observed raw range.

<a id="plot.selected_residuals_by_force"></a>
### 5.4 `selected_residuals_by_force`

A residual scatter plot for the selected model. NIST recommends residual plots because they can reveal model misspecification that one-number metrics compress away [R01].

Look for:

- residuals centered around zero,
- no clear curve or slope with force,
- no direction-specific clusters,
- no single point dominating the error.

<a id="plot.model_comparison_residuals"></a>
### 5.5 `model_comparison_residuals`

Overlaid residual scatter for candidate models.

Look for:

- whether a more complex model removes a repeated residual pattern,
- whether improvement is consistent across force levels,
- whether reduced RMSE comes from fitting one point rather than improving the whole range.

<a id="plot.model_metric_bars"></a>
### 5.6 `model_metric_bars`

A bar chart comparing RMSE and max absolute error. Bar plots encode values by bar height and are useful for categorical comparison [R16].

Interpretation:

- RMSE estimates typical error magnitude.
- Max absolute error estimates worst displayed/training error.
- A model with slightly lower RMSE but much higher complexity may not be worth deploying.

<a id="plot.model_likelihoods"></a>
### 5.7 `model_likelihoods`

A bar chart of `selection_likelihood`. The implementation computes a softmax over negative selection scores among eligible candidates. Softmax exponentiates scores and normalizes them so the resulting values sum to one [R13].

Interpretation:

- One dominant bar means the model-selection policy clearly preferred that model.
- Similar bars mean the decision is marginal; prefer the simpler model and improve the protocol before increasing firmware complexity.
- A zero likelihood often means the model was rejected or diagnostic-only.

<a id="plot.robust_huber_weights"></a>
### 5.8 `robust_huber_weights`

A scatter plot of Huber robust training weights by accepted hold index. Huber regression combines squared loss for small residuals with absolute loss for larger residuals, reducing outlier influence without completely ignoring those samples [R06].

Interpretation:

- Weight near 1: hold behaved like an ordinary inlier.
- Weight below 1: hold had a larger residual and was down-weighted during robust training.
- Several low weights: investigate protocol quality before trusting robust fit.

<a id="plot.hysteresis_up_down"></a>
### 5.9 `hysteresis_up_down`

A scatter plot of target raw median versus reference force, grouped by direction.

Interpretation:

- Ascending and descending points overlapping: good reversibility.
- Direction-separated clusters: mechanical hysteresis, fixture load-path effects, or protocol mismatch.
- Separation in target raw but not in reference force: target/fixture issue is more likely.

## 6. Models

<a id="model.affine_ols"></a>
### 6.1 `affine_ols`

Formula:

```text
force_N = a * raw + b
```

This is the ordinary least-squares straight-line model. Ordinary least squares chooses coefficients that minimize the sum of squared residuals between observed targets and linear predictions [R03]. NumPy describes polynomial least-squares fitting as minimizing squared error between fitted polynomial values and data [R04].

Use when:

- residuals show no clear curvature,
- the sensor behaves approximately linearly,
- firmware simplicity is important.

Caution: a very high R² can still hide load-dependent residuals. Always inspect residual plots.

<a id="model.affine_wls"></a>
### 6.2 `affine_wls`

Formula is still affine:

```text
force_N = a * raw + b
```

The difference is training: holds with higher reference noise receive less influence. In the implementation, reference standard deviation is converted to inverse-sigma weights before polynomial fitting.

Use when:

- all holds are valid but some are noisier than others,
- the reference noise estimate is meaningful,
- the affine model is otherwise adequate.

Caution: weighting cannot fix systematic bias, bad markers, or wrong force labels.

<a id="model.affine_huber"></a>
### 6.3 `affine_huber`

Formula exported to firmware remains affine, but the training loop uses Huber robust weights.

Huber regression is less influenced by outliers because it transitions from squared loss for small residuals to absolute loss for large residuals [R06]. The implementation initializes scale using a MAD-style robust residual scale; MAD is a robust dispersion estimate based on median absolute deviations [R12].

Use when:

- one or two holds may be contaminated,
- the rest of the data supports the same line,
- robust weights identify a small number of questionable points.

Caution: if many holds are down-weighted, the issue is probably protocol quality, not model choice.

<a id="model.quadratic_wls"></a>
### 6.4 `quadratic_wls`

Formula:

```text
force_N = a2 * raw^2 + a1 * raw + a0
```

This is a degree-2 polynomial fit. NumPy documents polynomial least-squares fitting and warns that polynomial fits can become poorly conditioned depending on degree and data centering [R04]. NIST force calibration material notes that second- or third-order polynomial equations are commonly derived from force/response calibration data [R18].

Use when:

- residuals show repeatable curvature,
- holdout data confirms the curvature generalizes,
- firmware can implement the polynomial safely.

Caution: with few calibration points, a quadratic can look better on training data but fail cross-validation.

<a id="model.piecewise_linear_monotone"></a>
### 6.5 `piecewise_linear_monotone`

This model stores calibration knots and interpolates between them. NumPy defines one-dimensional linear interpolation as evaluating the piecewise-linear interpolant through known data points [R05].

Use when:

- the sensor is monotone but not well represented by a line,
- there are enough repeated force levels to define trustworthy knots,
- firmware can enforce calibrated-range limits.

Caution: do not extrapolate beyond the calibrated raw-count range unless explicitly validated.

<a id="model.odr_affine"></a>
### 6.6 `odr_affine`

This diagnostic affine model is a **pure-NumPy Deming regression** (a closed-form errors-in-variables fit), conceptually related to orthogonal distance regression but **not** computed with `scipy.odr`. It accounts for uncertainty in both the input (target raw) and output (reference force) variables. Deming regression assumes a known ratio of error variances λ = Var(y-error)/Var(x-error); the implementation estimates λ from the per-hold noise medians and stores it as `variance_ratio_y_over_x`. SciPy's ODR documentation [R07] is included as the conceptual reference for errors-in-variables fitting; the orthogonal-regression special case of Deming (λ = 1) is the geometric ODR fit.

Use when:

- target raw values and reference forces both have meaningful uncertainty,
- you want to know whether ordinary least squares is sensitive to x-axis uncertainty.

Caution: in this project it is diagnostic-only by default. If it materially changes the result, investigate uncertainty and reference quality before deploying.

<a id="model.hysteresis_affine_diagnostic"></a>
### 6.7 `hysteresis_affine_diagnostic`

This diagnostic fits separate affine relationships for loading directions.

Use when:

- ascending and descending holds differ at the same force,
- the `hysteresis_up_down` plot shows separated clusters,
- reversibility must be quantified before deployment.

Caution: direction-dependent firmware behavior is usually the wrong first fix. Prefer mechanical/protocol investigation unless direction dependence is intentional and validated.

<a id="model.drift_affine_diagnostic"></a>
### 6.8 `drift_affine_diagnostic`

Formula:

```text
force_N = a * raw + b + drift_N_per_s * (time - time_center)
```

This model tests whether time explains residuals inside the session.

Use when:

- residuals improve materially after adding time,
- reference or target readings drift over the session,
- creep or warm-up effects are suspected.

Caution: time drift is usually a diagnostic symptom. Prefer stabilizing the hardware/protocol before baking time into firmware.

## 7. Metrics

<a id="metric.rmse_N"></a>
### 7.1 RMSE: `rmse_N`

RMSE is:

```text
sqrt(mean(residual_N^2))
```

The underlying MSE is the mean squared error between true and predicted values [R08]. RMSE returns to Newton units by taking the square root.

Interpretation:

- Lower is better.
- Penalizes large errors more than MAE.
- Useful as typical error magnitude, but not a worst-case guarantee.

<a id="metric.mae_N"></a>
### 7.2 MAE: `mae_N`

MAE is the mean absolute residual. scikit-learn defines MAE as a non-negative regression loss with best value 0.0 [R09].

Interpretation:

- Lower is better.
- Easier to explain than RMSE.
- Less sensitive to one large outlier than RMSE.

<a id="metric.max_abs_error_N"></a>
### 7.3 Max absolute error: `max_abs_error_N`

This is the largest absolute residual among evaluated points.

Interpretation:

- Lower is better.
- Directly relevant to worst-case visible calibration error.
- A model with good RMSE but bad max error may still be unsafe to deploy.

<a id="metric.max_abs_error_percent_range"></a>
### 7.4 Max absolute error percent range

Formula:

```text
100 * max_abs_error_N / operating_range_N
```

Interpretation:

- Lower is better.
- Normalizes error severity to the expected force range.
- Used by the residual threshold gate.

<a id="metric.r2"></a>
### 7.5 R²: `r2`

R² is the coefficient of determination. scikit-learn documents that best possible R² is 1.0, and R² can be negative if a model performs worse than a constant-average predictor [R10].

Interpretation:

- High is generally good.
- Do not rely on R² alone for calibration approval.
- In narrow/noisy datasets, R² can look excellent while residual plots reveal systematic error.

<a id="metric.adjusted_r2"></a>
### 7.6 Adjusted R²: `adjusted_r2`

Adjusted R² penalizes additional parameters. The report computes it only when there are enough data points relative to parameter count.

Interpretation:

- Useful for comparing models with different parameter counts.
- If sample count is very small, it may be unavailable or unstable.

<a id="metric.residual_bias_N"></a>
### 7.7 Residual bias: `residual_bias_N` / `bias_N`

Mean signed residual.

Interpretation:

- Near zero is desirable.
- Positive bias means model predictions are low on average.
- Negative bias means model predictions are high on average.

<a id="metric.residual_std_N"></a>
### 7.8 Residual standard deviation: `residual_std_N`

Residual spread after accounting for mean bias.

Interpretation:

- Low residual standard deviation with high bias means a consistent offset.
- High residual standard deviation means inconsistent errors.

<a id="metric.aicc"></a>
### 7.9 AICc and BIC: `aicc`, `bic`

These are information-criterion-style diagnostics calculated from residual variance, sample count, and parameter count.

Interpretation in this project:

- Lower is better within the same dataset.
- Use as secondary diagnostics, not deployment gates.
- With very small calibration datasets, prefer residual plots, holdout behavior, and simple-model preference.

<a id="metric.cv"></a>
### 7.10 Cross-validation metrics

Cross-validation trains on part of the data and validates on held-out folds; scikit-learn describes k-fold CV as fitting on `k-1` folds and validating on the remaining fold, then summarizing performance [R11].

Fields:

| Field                            | Meaning                                     | Interpretation                                    |
| -------------------------------- | ------------------------------------------- | ------------------------------------------------- |
| `cv_rmse_N`                      | RMSE from out-of-fold predictions.          | Generalization estimate; lower is better.         |
| `cv_mae_N`                       | MAE from out-of-fold predictions.           | Average independent-fold absolute error.          |
| `cv_max_abs_error_N`             | Worst CV residual.                          | Worst generalization point.                       |
| `cv_max_abs_error_percent_range` | Worst CV residual as percent of range.      | Normalized worst CV error.                        |
| `cv_rmse_se_N`                   | Standard error of fold RMSEs.               | Decision uncertainty/stability signal.            |
| `cv_fold_count`                  | Number of successful folds.                 | Too few folds means weak CV evidence.             |
| `cv_point_count`                 | Number of points with finite CV prediction. | Low count means coverage problem.                 |
| `cv_coverage_fraction`           | `cv_point_count / n_points`.                | Below gate means candidate is rejected or warned. |

## 8. Model selection and gates

<a id="field.selection_score"></a>
### 8.1 Selection score

The project selection score is lower-is-better:

```text
score = 40 * cv_rmse_N / operating_range_N
      + 60 * max_abs_error_N / operating_range_N
      + 0.15 * n_parameters
      + gate penalties
```

Interpretation:

- CV RMSE rewards generalization.
- Max error penalizes worst-case behavior.
- Parameter count penalizes complexity.
- Diagnostic-only and monotonicity failures add penalties or rejection reasons.

<a id="field.selection_likelihood"></a>
### 8.2 Selection likelihood

The report transforms eligible candidates' negative selection scores with softmax. SciPy defines softmax as exponentiating each input and dividing by the sum of all exponentials; the result sums to 1 [R13].

Interpretation:

- It is a relative decision weight, not a calibrated probability of truth.
- Similar likelihoods mean the winner is not decisive.
- Zero can mean rejected or outside the eligible set.

<a id="field.deployment"></a>
### 8.3 Deployment fields

| Field                              | Meaning                                       | Interpretation                                    |
| ---------------------------------- | --------------------------------------------- | ------------------------------------------------- |
| `n_parameters`                     | Number of fitted/exported degrees of freedom. | More parameters need stronger evidence.           |
| `deployable_to_firmware`           | Implementation can export firmware constants. | Does not imply safe; only technically exportable. |
| `accepted_for_deployment`          | Candidate passed gates.                       | Eligible for automatic selection.                 |
| `diagnostic_only`                  | Candidate is diagnostic by design.            | Use to find causes, not to deploy by default.     |
| `rejection_reasons`                | Why a candidate failed gates.                 | Read before trusting ranking order.               |
| `residual_threshold_percent_range` | Selected-model max-error gate.                | Advisory static gate.                             |
| `passes_residual_threshold`        | Whether selected model met that gate.         | False means investigate before deployment.        |

## 9. Firmware constants

<a id="firmware.force_N_ab"></a>
### 9.1 Affine constants

For affine models:

```text
force_N = a * raw + b
```

The report exports:

```json
"force_N_equals_a_raw_plus_b": { "a": ..., "b": ... }
```

Interpretation: firmware can implement this directly if runtime units and raw counts match the calibration dataset.

<a id="firmware.hx711_scale_offset"></a>
### 9.2 HX711-style approximation

The report also exports:

```text
scale  = 1/a
offset = -b/a
```

This corresponds approximately to:

```text
force_N = (raw - offset) / scale
```

Caution: the report itself warns that HX711 library semantics must be verified before flashing. Some libraries apply tare, offset, sign, averaging, and scaling in specific orders.

<a id="firmware.recommended_firmware_constants"></a>
### 9.3 Nonlinear firmware constants

Quadratic and piecewise models export either polynomial coefficients or lookup-table knots.

Interpretation:

- Use the exact selected model export, not the legacy affine approximation, when a nonlinear model is selected.
- Enforce calibrated-range limits for lookup tables unless extrapolation has been validated.

## 10. Extended `calibration_dataset.csv` concepts

Some columns are documented even when not displayed in the short accepted-hold table.

| Group                 | Fields                                                                                                                                                 | Meaning                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| Tail statistics       | `target_raw_tail_median`, `target_raw_tail_std`, `reference_force_tail_median_N`, `reference_force_tail_std_N`, sample counts                          | Stable end-of-hold summary window.                                       |
| Shape correlation     | `shape_corr_target_reference`                                                                                                                          | Similarity between target and reference waveform shapes during hold.     |
| Direction sign checks | `target_direction_sign_match`, `reference_direction_sign_match`                                                                                        | Whether observed relaxation sign agrees with expected loading direction. |
| Relaxation metrics    | `*_relaxation_start_median`, `*_end_median`, `*_delta_end_minus_start`, `*_slope_per_s`, `*_lin_r2`, `*_monotonic_fraction`, `*_exp_tau_s`, `*_exp_r2` | Slow settling/relaxation behavior during a hold.                         |
| Artifact flag         | `calibration_artifact_applied`                                                                                                                         | Whether direction-balanced artifact correction was applied.              |

Interpretation: these fields are diagnostic. They explain why a hold may look unstable, direction-dependent, or contaminated.

## 11. Schema references

### 11.1 `handgrip_fit_result.v2`

Top-level selected-fit artifact. Contains:

- selected model ID/family,
- model parameters,
- fit metrics,
- CV metrics,
- residual gate result,
- selection likelihood,
- full ranking,
- recommended firmware constants,
- notes.

### 11.2 `model_ranking[]`

Per-candidate summary used by the report candidate table. Contains rank, model ID, family, deployment flags, score, likelihood, key metrics, parameter count, and rejection reasons.

### 11.3 `handgrip_holdout_validation.v1`

Independent validation artifact. Contains holdout session path, model reference, selected model, holdout metrics, thresholds, pass/fail gate, recommendation, and notes.

## 12. Practical interpretation rules

### 12.1 Prefer simple models unless evidence is strong

If affine OLS/WLS/Huber models perform similarly to nonlinear models, choose the affine model. A nonlinear model needs clear residual improvement, cross-validation support, and holdout support.

### 12.2 Residual plots beat dashboard metrics

A single RMSE can hide curvature or direction dependence. NIST explicitly notes that graphical methods reveal broader model/data relationships than narrow numerical summaries [R01].

### 12.3 Holdout is the strongest deployment check

The selected fit should pass the independent holdout gate. Without holdout validation, firmware constants should be considered provisional.

### 12.4 Do not deploy diagnostics as fixes

`odr_affine`, `hysteresis_affine_diagnostic`, and `drift_affine_diagnostic` are evidence-gathering tools. If they outperform deployable models, treat that as a request to investigate reference uncertainty, mechanical load path, thermal drift, creep, or protocol timing.

### 12.5 Stay inside the calibrated range

All model interpretations are strongest inside the observed raw-count and force range. Piecewise interpolation is especially range-sensitive; NumPy notes that `interp` expects increasing x-coordinate sample points and gives endpoint behavior outside the known range unless controlled [R05].

## 13. References

- **R01** — [NIST/SEMATECH e-Handbook — Model validation and residual analysis](https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm).
- **R02** — [NIST/SEMATECH e-Handbook — Load Cell Calibration case study](https://www.itl.nist.gov/div898/handbook/pmd/section6/pmd61.htm).
- **R03** — [scikit-learn — LinearRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html).
- **R04** — [NumPy — numpy.polyfit](https://numpy.org/doc/stable/reference/generated/numpy.polyfit.html).
- **R05** — [NumPy — numpy.interp](https://numpy.org/doc/stable/reference/generated/numpy.interp.html).
- **R06** — [scikit-learn — HuberRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.HuberRegressor.html).
- **R07** — [SciPy — Orthogonal distance regression](https://docs.scipy.org/doc/scipy/reference/odr.html).
- **R08** — [scikit-learn — mean_squared_error](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_squared_error.html).
- **R09** — [scikit-learn — mean_absolute_error](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_error.html).
- **R10** — [scikit-learn — r2_score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html).
- **R11** — [scikit-learn User Guide — Cross-validation: evaluating estimator performance](https://scikit-learn.org/stable/modules/cross_validation.html).
- **R12** — [SciPy — median_abs_deviation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.median_abs_deviation.html).
- **R13** — [SciPy — softmax](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.softmax.html).
- **R14** — [Matplotlib — pyplot.plot](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.plot.html).
- **R15** — [Matplotlib — pyplot.scatter](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html).
- **R16** — [Matplotlib — pyplot.bar](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.bar.html).
- **R17** — [ISO 376:2011 preview — Calibration of force-proving instruments](https://standards.iteh.ai/catalog/standards/sist/9bf90770-4ac1-49dd-9564-8ef3bbdb281f/sist-en-iso-376-2012).
- **R18** — [NIST — Force Measurement Services: Equipment, Procedures, and Uncertainty](https://www.nist.gov/system/files/documents/calibrations/97ncs4b.pdf).
