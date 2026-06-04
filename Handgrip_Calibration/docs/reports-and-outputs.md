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

## Output lifecycle

- Keep full reports with the session folder.
- Do not edit generated reports manually without marking them as edited.
- If a report is useful for teaching, curate an excerpt under `docs/examples/calibration-session/`.
