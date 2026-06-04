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
