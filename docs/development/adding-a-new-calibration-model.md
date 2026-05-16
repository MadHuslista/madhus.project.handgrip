# Adding a New Calibration Model

## Summary

- Calibration models map target raw counts to reference force.
- The root calibration contract is `reference_force_N = f(target_raw_count)`.
- New models must be evaluated against existing alternatives with clear metrics, residuals, and validation behavior.
- Do not promote a more complex model unless it improves validated accuracy without creating interpretation/deployment risk.

## Files to edit

| File area | Purpose |
| --- | --- |
| `Handgrip_Calibration/src/handgrip_calibration/...` | Model implementation and fitting logic. |
| `Handgrip_Calibration/conf/*.yaml` | Candidate enable/disable flags and model-specific parameters. |
| `Handgrip_Calibration/docs/fitting-and-model-selection.md` | Model rationale, metrics, residual interpretation. |
| `Handgrip_Calibration/docs/reports-and-outputs.md` | New fit/report artifacts if any. |
| `Handgrip_Calibration/docs/applying-calibration-results.md` | Deployment guidance if model is deployable. |
| `docs/configuration/handgrip-calibration.md` | Root config reference if config keys are user-facing. |
| tests under `Handgrip_Calibration/tests/` | Synthetic, noisy, outlier, and report behavior tests. |

## Data contracts affected

A new model can affect:

- fit result JSON schema,
- report metrics/tables,
- exported firmware constants,
- LSL bridge processing recommendations,
- holdout validation interpretation,
- analysis assumptions.

It must not change the input contract unless explicitly documented:

| Input | Required role |
| --- | --- |
| `target_raw_count` | Model input. |
| `reference_force_N` | Ground-truth output. |
| protocol events | Segmentation and hold labels. |
| config snapshots | Reproducibility. |

## Tests to update

Minimum test categories:

```bash
cd Handgrip_Calibration
uv run pytest
```

Recommended model-specific tests:

| Test | Purpose |
| --- | --- |
| synthetic exact mapping | Model recovers known parameters. |
| noisy mapping | Model is stable under measurement noise. |
| outlier mapping | Robust models behave as expected. |
| monotonicity | Force mapping does not violate physical assumptions unless diagnostic-only. |
| serialization | Fit result JSON contains required fields. |
| report rendering | Model appears correctly in comparison tables. |
| holdout validation | Model can be applied to independent data. |

## Validation workflow

1. Define model purpose: deployable, diagnostic, or exploratory.
2. Implement model with explicit parameter names and units.
3. Add config entry to candidate list.
4. Add synthetic tests.
5. Run on a known calibration session.
6. Compare with baseline models.
7. Inspect residuals by force level and by ascending/descending holds.
8. Run holdout validation.
9. Update report interpretation and deployment docs.
10. Only then mark model as candidate for production selection.

## Common failure modes

| Failure | Cause | Fix |
| --- | --- | --- |
| Model overfits fit session | Too many parameters, no holdout discipline | Prefer simpler model or require holdout pass. |
| Non-monotonic mapping | Polynomial/spline behavior unconstrained | Add monotonic constraint or mark diagnostic-only. |
| Cannot export to firmware | Model not representable as scale/offset | Document host-side deployment or non-deployable status. |
| Report selection unclear | Missing metric or likelihood explanation | Update model-selection report and docs. |
| Residuals improve but dynamics worsen | Filter/model hides lag/hysteresis | Validate against dynamic/holdout protocols. |
| Units ambiguous | Parameters not labelled | Add units to fit JSON and report tables. |
