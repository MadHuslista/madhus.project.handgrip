# Curated Calibration Session Example

## Summary

This directory is for small, curated examples that teach how to interpret calibration outputs. Do not copy entire calibration session folders here. Keep raw/scientific data in `Handgrip_Calibration/data/calibration/<session_id>/`.

## What a complete calibration session usually contains

| Artifact                          | Purpose                                              | How to interpret                                                             |
| --------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------- |
| `target.csv`                      | Captured `HandgripTarget` samples.                   | Confirms raw target counts, timestamps, and status values.                   |
| `reference.csv`                   | Captured `HandgripReference` samples.                | Confirms PM58/reference force values.                                        |
| `events.ndjson`                   | Protocol/marker events.                              | Segment baseline, preload, static holds, dynamic trials, and holdout events. |
| `quality_live.ndjson`             | Live QA telemetry.                                   | Check sample rates, gaps, unstable holds, and runtime warnings.              |
| `session_manifest.yaml`           | Session metadata.                                    | Identify operator, purpose, protocol, output root, and provenance.           |
| `component_configs/`              | Copied configs from bridge/viewer/RS485/calibration. | Reproduce the acquisition context.                                           |
| `calibration_dataset.csv`         | Segmented/accepted fit dataset.                      | Confirm accepted holds and force levels used for fitting.                    |
| `fit_candidates.json`             | All evaluated model candidates.                      | Compare models and complexity.                                               |
| `fit_result.json`                 | Selected model and deployment values.                | Source of accepted model parameters.                                         |
| `model_selection_report.json`     | Machine-readable model-selection evidence.           | Audit metric/likelihood/residual choices.                                    |
| `calibration_report.md` / `.html` | Human-readable report.                               | Primary review artifact for handoff.                                         |
| `plots/`                          | Diagnostic plots.                                    | Residuals, selected fit curve, hysteresis, weights, likelihoods.             |

## Selected interpretation path

1. Open `calibration_report.md`.
2. Confirm the report identifies the session ID and protocol.
3. Check whether the primary model is selected from accepted candidates.
4. Inspect residual plots by force level.
5. Inspect up/down hysteresis if available.
6. Confirm firmware constants or deployment instructions are explicitly reported.
7. Run or inspect holdout validation before treating the model as accepted.

## Good report signs

- Session ID and protocol are explicit.
- The report states target signal and reference signal names.
- `reference_force_N = f(target_raw_count)` remains the core calibration relation.
- Residuals are not systematically biased by force level.
- The selected model is not more complex than necessary.
- Config snapshots exist and include the real RS485 GUI config path: `../RS485_GUI/config/config.yaml`.

## Anti-example signs

- Missing `target.csv` or `reference.csv`.
- Missing `events.ndjson` or protocol markers.
- Model selected without residual/holdout evidence.
- Report describes fitting against firmware-scaled `current_units` without explicitly saying this is an already-deployed-constant validation.
- Component configs are missing or copied from stale paths.

## Curation rule

Only place small explanatory excerpts here, for example:

```text
docs/examples/calibration-session/
├── README.md
├── selected-report-excerpts.md
└── selected-plot-notes.md
```

Do not copy full session folders or raw datasets into this docs example directory.

## Related docs:

- [docs/workflows/handgrip-calibration.md](../../workflows/handgrip-calibration.md)
- [Handgrip_Calibration/docs/reports-and-outputs.md](../../../Handgrip_Calibration/docs/reports-and-outputs.md)
