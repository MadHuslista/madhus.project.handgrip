# Handgrip Calibration Protocols

## Summary

- The canonical primary calibration protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- `conf/protocol_reference_verification.yaml` should be used before primary calibration to verify the reference chain.
- `conf/protocol_holdout_verification.yaml` should be used after fitting to validate out-of-sample accuracy.
- `conf/protocol_static_staircase.yaml` is retained as a legacy/basic baseline protocol, not the recommended primary handoff workflow.
- All calibration configs should snapshot component configs using the real RS485 GUI config path: `../RS485_GUI/config/config.yaml`.

## Audience

Read this document if you need to choose a calibration protocol, add a protocol, explain why v3 is primary, or preserve legacy compatibility without confusing operators.

## Protocol decision table

| Protocol file | Status | Use for | Avoid using for |
| --- | --- | --- | --- |
| `protocol_reference_verification.yaml` | Canonical pre-check | Verify reference board/PM58 chain before primary calibration. | Primary model fitting. |
| `protocol_static_reversible_staircase_v3.yaml` | **Canonical primary** | Main calibration fit dataset using reversible up/down static holds. | Quick smoke-only checks. |
| `protocol_holdout_verification.yaml` | Canonical validation | Independent post-fit holdout validation. | Training/refitting the primary model. |
| `protocol_low_force_refinement.yaml` | Optional refinement | Improve low-force region if the primary fit is weak near zero. | First-run calibration unless low-force accuracy is specifically required. |
| `protocol_creep_zero_return.yaml` | Optional diagnostic | Quantify creep, zero return, and baseline recovery. | Primary gain/offset fitting. |
| `protocol_dynamic_validation.yaml` | Optional diagnostic | Ramps, squeezes, lag, hysteresis, dynamic behavior. | Static fit parameter estimation. |
| `protocol_fast_smoke_test.yaml` | Developer/operator smoke test | Fast sanity test before a full session. | Final calibration report. |
| `protocol_static_staircase.yaml` | Legacy/basic baseline | Compatibility with older docs or short static-only baseline. | Recommended handoff workflow. |
| `template.yaml` | Authoring template | Create new protocol configs. | Direct operator run unless filled out. |

## Canonical sequence

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record --config conf/protocol_reference_verification.yaml
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal fit data/calibration/<fit_session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal report data/calibration/<fit_session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal report data/calibration/<holdout_session_id> --config conf/protocol_holdout_verification.yaml
```

## What v3 should contain

The v3 primary protocol should provide:

- baseline / zero state,
- preload or mechanical conditioning cycles,
- static holds across the intended force range,
- ascending and descending directions,
- repeats where practical,
- enough stable tail duration for fitting,
- marker events for segmentation,
- quality gates for reference gaps, slope, standard deviation, and target sample count.

## Legacy label policy

Use this wording consistently:

```text
protocol_static_staircase.yaml is legacy/basic baseline. It is retained for compatibility and short baseline checks, but it is not the recommended handoff workflow.
```

## Component config snapshot paths

Each production protocol should copy the component configs needed for provenance:

```yaml
session:
  copy_component_configs:
    - ../LSL_Bridge/conf/config.yaml
    - ../LSL_Viewer/conf/config.yaml
    - ../RS485_GUI/config/config.yaml
```

The stale path below should not appear in current configs or docs:

```yaml
- stale RS485 GUI root-level config path
```

## Adding a protocol

Use `template.yaml` as the starting point and document:

| Section | Required decision |
| --- | --- |
| `metadata` | Human-readable protocol name, version, purpose. |
| `session` | Output root, config snapshots, operator prompts. |
| `lsl` | Required target/reference streams and channel aliases. |
| `events` / `steps` | Protocol marker sequence and hold definitions. |
| `quality` | Minimum samples, gap limits, stable-window rules. |
| `fit` | Whether this protocol is fit-producing, validation-only, or diagnostic. |
| `report` | Expected report sections and plots. |

## Validation checklist

```bash
rg "protocol_static_reversible_staircase_v3.yaml" Handgrip_Calibration/README.md Handgrip_Calibration/docs docs/workflows/handgrip-calibration.md
rg "legacy|basic baseline" Handgrip_Calibration/docs/protocols.md
rg "\.\./RS485_GUI/config/config\.yaml" Handgrip_Calibration/conf
if rg "\.\./RS485_GUI/config\.yaml" Handgrip_Calibration/conf Handgrip_Calibration/docs; then
  echo "ERROR: stale RS485 config path found" >&2
  exit 1
fi
```
