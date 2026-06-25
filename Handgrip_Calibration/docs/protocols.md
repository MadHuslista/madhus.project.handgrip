# Handgrip Calibration Protocols

## Summary

- The canonical primary calibration protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- `conf/protocol_reference_verification.yaml` should be used before primary calibration to verify the reference chain.
- `conf/protocol_holdout_verification.yaml` should be used after fitting to validate out-of-sample accuracy.
- `conf/protocol_static_staircase.yaml` is retained as a legacy/basic baseline protocol, not the recommended primary handoff workflow.
- All calibration configs should snapshot component configs using the real RS485 GUI config path: `../RS485_GUI/config/config.yaml`.

## Protocol decision table

| Protocol file                                  | Category                      | Purpose                                                             |
| ---------------------------------------------- | ----------------------------- | ------------------------------------------------------------------- |
| `protocol_reference_verification.yaml`         | Canonical pre-check           | Verify reference board/PM58 chain before primary calibration.       |
| `protocol_static_reversible_staircase_v3.yaml` | **Canonical primary**         | Main calibration fit dataset using reversible up/down static holds. |
| `protocol_holdout_verification.yaml`           | Canonical validation          | Independent post-fit holdout validation.                            |
| `protocol_low_force_refinement.yaml`           | Optional refinement           | Improve low-force region if the primary fit is weak near zero.      |
| `protocol_creep_zero_return.yaml`              | Optional diagnostic           | Quantify creep, zero return, and baseline recovery.                 |
| `protocol_dynamic_validation.yaml`             | Optional diagnostic           | Ramps, squeezes, lag, hysteresis, dynamic behavior.                 |
| `protocol_smoke_test_capture.yaml`             | Pipeline smoke test           | Fast end-to-end capture for smoke-testing record→fit→report path.  |
| `protocol_smoke_test_holdout.yaml`             | Pipeline smoke test           | Fast holdout capture for smoke-testing validate-holdout→integrated-report path. |
| `protocol_fast_smoke_test.yaml`                | Developer/operator smoke test | Fast sanity test before a full session.                             |
| `protocol_static_staircase.yaml`               | Legacy/basic baseline         | Compatibility with older docs or short static-only baseline.        |
| `template.yaml`                                | Authoring template            | Create new protocol configs.                                        |

## Canonical sequence

The end-to-end command sequence that uses these protocols (preflight → record → fit → report → holdout → firmware deployment) lives in [Handgrip_Calibration/docs/workflow.md](workflow.md).

## What the Canonical primary protocol contains

The canonical primary protocol `protocol_static_reversible_staircase_v3.yaml` contains a sequence of operator prompts for recording static holds at various force levels in both ascending and descending directions, with quality gates to ensure stable data for fitting. 

The protocol includes:

- baseline / zero state,
- preload or mechanical conditioning cycles,
- static holds across the intended force range,
- ascending and descending directions,
- repeats where practical,
- enough stable tail duration for fitting,
- marker events for segmentation,
- quality gates for reference gaps, slope, standard deviation, and target sample count.

## Component config snapshot paths

Each production protocol should copy the component configs needed for provenance:

```yaml
session:
  copy_component_configs:
    - ../LSL_Bridge/conf/config.yaml
    - ../LSL_Viewer/conf/config.yaml
    - ../RS485_GUI/config/config.yaml
```

## Smoke test protocols

`protocol_smoke_test_capture.yaml` and `protocol_smoke_test_holdout.yaml` are designed as a matched pair to validate the full pipeline code path without a production session.

Key design properties:

- **Must be used together** — capture first, then holdout — to exercise the complete report lifecycle (preliminary → integrated)
- **Force levels are deliberately interspersed**: capture uses `0, 20, 40 N`; holdout uses `0, 15, 30 N` — the holdout levels fall between capture levels, providing a genuine out-of-sample test
- **Fast timing**: 2 s baseline, 2 s holds, no preload, single repeat — completes quickly with live hardware
- **Relaxed quality thresholds**: `reference_min_hz: 450`, `max_hold_reference_std_N: 2.0` — avoids quality-gate failures on noisy bench setups
- **Holdout thresholds explicitly relaxed**: `max_rmse_N: 5.0`, `max_abs_error_N: 10.0`, `max_bias_N: 2.0` — pass/fail is a pipeline sanity check, not a deployment gate
- **`calibration_artifact.enabled: false`** — keeps the fit pipeline simple
- **Do not use resulting model coefficients in production** — the data quality is not suitable for deployment

After running `validate-holdout` with the smoke holdout session, the primary session's `calibration_report.md` is automatically regenerated as the integrated report. This confirms the full report lifecycle works end-to-end.

See [docs/workflow.md](workflow.md) for the complete 5-command smoke test sequence.

## Adding a protocol

Use `template.yaml` as the starting point and document:

| Section            | Required decision                                                       |
| ------------------ | ----------------------------------------------------------------------- |
| `metadata`         | Human-readable protocol name, version, purpose.                         |
| `session`          | Output root, config snapshots, operator prompts.                        |
| `lsl`              | Required target/reference streams and channel aliases.                  |
| `events` / `steps` | Protocol marker sequence and hold definitions.                          |
| `quality`          | Minimum samples, gap limits, stable-window rules.                       |
| `fit`              | Whether this protocol is fit-producing, validation-only, or diagnostic. |
| `report`           | Expected report sections and plots.                                     |
