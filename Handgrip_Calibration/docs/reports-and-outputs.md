# Reports and Outputs

## Summary

- Reports translate calibration artifacts into a deployment decision.
- The report should identify the selected model, candidate comparison, residuals, plots, thresholds, and validation status.
- Generated reports are outputs, not canonical documentation; curated examples belong under `docs/examples/`.

## Report command

The `report` command and its place in the full sequence are documented in [Handgrip_Calibration/docs/workflow.md](workflow.md). This document covers how to read the outputs it produces.

## Expected output classes

| Artifact                      | Purpose                                                  |
| ----------------------------- | -------------------------------------------------------- |
| `calibration_report.md`       | Human-readable report for review and handoff.            |
| `calibration_report.html`     | Browser-friendly report when enabled.                    |
| `fit_result.json`             | Selected model and recommended deployment values.        |
| `fit_candidates.json`         | Candidate model metrics and diagnostics.                 |
| `model_selection_report.json` | Selection rationale, likelihoods, penalties, thresholds. |
| `calibration_dataset.csv`     | Accepted holds used for fitting.                         |
| `calibration_hold_dataset_raw.csv` | Pre-correction hold dataset; written if `calibration_artifact.enabled`. |
| `calibration_artifact_summary.csv` | Per-level direction-balanced medians and exclusions; written if `calibration_artifact.enabled`. |
| `holdout_validation.json`     | Holdout pass/fail metrics (mirrored to primary dir by `validate-holdout`). |
| `holdout_predictions.csv`     | Per-hold predicted vs actual force (mirrored to primary dir by `validate-holdout`). |
| `plots/`                      | Time series, residuals, model comparisons, metric bars.  |
| config snapshots              | Reproducibility of upstream components.                  |

Exact filenames may differ by implementation version. This document defines the expected artifact roles.

## Report summary interpretation

Start with:

- selected model,
- deployable/not deployable status,
- residual threshold pass/fail,
- RMSE and CV RMSE,
- max absolute error,
- max error percent of operating range,
- recommended deployment target.

Decision rule:

```text
If threshold or holdout validation fails, do not deploy without improving data quality or proving the selected correction is repeatable.
```

## Candidate ranking table

Use the candidate table to answer:

1. Did affine perform almost as well as nonlinear models?
2. Did nonlinear models materially reduce structured residuals?
3. Did any candidate fail monotonicity or deployment constraints?
4. Did robust methods down-weight specific contaminated holds?
5. Did diagnostics indicate hysteresis, drift, or load-path problems?

Default deployment preference:

```text
affine_wls or affine_huber > piecewise_linear_monotone > quadratic_wls
```

unless evidence strongly justifies otherwise.

## Plot interpretation

| Plot                        | Meaning                              | What to look for                                   |
| --------------------------- | ------------------------------------ | -------------------------------------------------- |
| target time series          | target raw/units over time           | gaps, jumps, status problems.                      |
| reference time series       | PM58/reference force over time       | stable holds, drift, backlog artifacts.            |
| model comparison curve      | candidate curves over accepted holds | whether nonlinear models are materially different. |
| selected residuals by force | residuals vs force                   | curvature, bias, outlier holds.                    |
| model comparison residuals  | residuals for multiple candidates    | real improvement vs cosmetic complexity.           |
| model metric bars           | RMSE/max error comparison            | best model vs acceptable simple model.             |
| model likelihoods           | relative decision weight             | decisive vs marginal winner.                       |
| robust weights              | robust-fit hold weights              | contaminated holds.                                |
| hysteresis up/down          | direction split                      | mechanical hysteresis or load-path asymmetry.      |

## calibration_dataset.csv columns

The segmentation process produces `calibration_dataset.csv` with the following semantically significant columns (in addition to legacy core columns):

| Column group | Columns | Meaning |
|---|---|---|
| Tail statistics | `target_raw_tail_median`, `target_raw_tail_std`, `target_tail_n_samples`, `reference_force_tail_median_N`, `reference_force_tail_std_N`, `reference_tail_n_samples` | Hold tail-window (last 2 seconds by default) median force, std, and sample count. Used for artifact correction. |
| Shape correlation | `shape_corr_target_reference` | Normalized cross-correlation between target and reference waveform shapes during the hold (0–1 scale). |
| Direction artifact sign | `target_direction_sign_match`, `reference_direction_sign_match` | Whether observed relaxation sign (delta) matches expected sign for ascending/descending holds (direction-balanced fixture compensation diagnostic). |
| Target relaxation metrics | `target_relaxation_start_median`, `target_relaxation_end_median`, `target_relaxation_delta_end_minus_start`, `target_relaxation_slope_per_s`, `target_relaxation_lin_r2`, `target_relaxation_monotonic_fraction`, `target_relaxation_exp_tau_s`, `target_relaxation_exp_r2` | Hold-to-end relaxation behavior: start/end medians, linear slope + R², exponential tau + R², monotonicity. |
| Reference relaxation metrics | Same 8 fields prefixed `reference_relaxation_` | Reference force relaxation behavior over the hold. |
| Artifact flag | `calibration_artifact_applied` | Boolean indicating whether direction-balanced artifact correction was applied to this point. |

---

## Tables to preserve

Reports should preserve at least:

- session metadata,
- protocol name/version,
- input stream names/channels,
- accepted/rejected hold summary,
- selected model parameters,
- candidate metric table,
- deployment recommendation,
- holdout result if available.

## Dynamic validation targets

After static fitting, use dynamic trial data from the session to check behavior beyond static equilibrium. Initial targets for a 100 N operating range:

| Metric                         | Target                                                      |
| ------------------------------ | ----------------------------------------------------------- |
| Static max absolute error      | `<= 0.5 N`                                                  |
| Static RMSE                    | `<= 0.25–0.35 N` preferred                                  |
| Dynamic lag                    | Document first; set a limit once experiment needs are known |
| Post-squeeze baseline recovery | `<= 0.5 N` after settling                                   |
| Slow-ramp monotonicity         | No large reversals outside measured noise                   |

Do not optimize dynamic metrics until the static fit is stable.

## Report lifecycle

`calibration_report.md` is a regenerable artifact — not a one-time output. It reflects all data available in the session dir at the time `report` is called, or at the time `validate-holdout` completes.

**Phase 1 — Preliminary** (after `fit` + `report`):
- Section 3 (Holdout accuracy summary) shows a holdout-pending notice with the exact `validate-holdout` command to run
- `deployment_recommendation` is `fit_available_but_holdout_validation_missing`
- Report is valid and reviewable; the fit quality sections are fully populated

**Phase 2 — Integrated** (after `validate-holdout`):
- `validate-holdout` mirrors `holdout_validation.json` and `holdout_predictions.csv` to the primary session dir
- It then calls `generate_report(primary_session_dir)` automatically — no manual `report` command needed
- Section 3 is populated with full holdout metrics, predictions table, and pass/fail verdict
- `deployment_recommendation` reflects the holdout outcome (`approve_constants_for_deployment` or `do_not_deploy_investigate_protocol_or_model`)

**Idempotency**: Re-running `report <primary_dir>` at any time regenerates `calibration_report.md` from whatever artifacts are currently present. If holdout data is in the dir, the report is integrated. If not, it is preliminary. There is no separate "final" vs "draft" report file.

**Artifact locations**: After `validate-holdout`, `holdout_validation.json` and `holdout_predictions.csv` exist in two places:
- The holdout session dir — raw data provenance, the holdout session's own record
- The primary session dir — consumed by `generate_report` for the integrated view

## Output lifecycle

- Keep full reports with the session folder.
- Do not edit generated reports manually without marking them as edited.
- Re-generating a report after new data is available (e.g. after `validate-holdout`) is the correct workflow — not manual editing.
- If a report is useful for teaching, curate an excerpt under `docs/examples/calibration-session/`.
