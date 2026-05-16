# Handgrip Calibration Protocols

## Summary

- The canonical primary calibration protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- `conf/protocol_reference_verification.yaml` should be used before primary calibration to verify the reference chain.
- `conf/protocol_holdout_verification.yaml` should be used after fitting to validate out-of-sample accuracy.
- `conf/protocol_static_staircase.yaml` is retained as a legacy/basic baseline protocol, not the recommended primary handoff workflow.
- All calibration configs should snapshot component configs using the real RS485 GUI config path: `../RS485_GUI/config/config.yaml`.

## Audience

Read this document if you need to:

- choose the right calibration protocol,
- understand which protocol is canonical,
- run a calibration session consistently,
- update protocol defaults,
- explain why older static-staircase references are no longer the main workflow.

## Status

| Field                 | Value                                               |
| --------------------- | --------------------------------------------------- |
| Canonical             | Yes                                                 |
| Component             | `Handgrip_Calibration`                              |
| Primary protocol      | `conf/protocol_static_reversible_staircase_v3.yaml` |
| Legacy/basic protocol | `conf/protocol_static_staircase.yaml`               |
| Required path fix     | `../RS485_GUI/config/config.yaml`                   |

## Protocol decision table

| Protocol file                                  | Status                        | Use for                                                                   | Avoid using for                                                           |
| ---------------------------------------------- | ----------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `protocol_reference_verification.yaml`         | Canonical pre-check           | Verify reference board/PM58 chain before main calibration                 | Primary target model fit.                                                 |
| `protocol_static_reversible_staircase_v3.yaml` | **Canonical primary**         | Main calibration fit dataset using reversible up/down static holds        | Quick smoke-only validation when time is extremely constrained.           |
| `protocol_holdout_verification.yaml`           | Canonical validation          | Independent post-fit holdout validation                                   | Training/refitting the primary model.                                     |
| `protocol_low_force_refinement.yaml`           | Optional refinement           | Improve low-force region if the primary fit shows weak low-force behavior | First-run calibration unless low-force accuracy is specifically required. |
| `protocol_creep_zero_return.yaml`              | Optional diagnostic           | Quantify creep, zero return, and baseline recovery                        | Primary gain/offset fitting.                                              |
| `protocol_dynamic_validation.yaml`             | Optional diagnostic           | Ramps/squeezes, lag, hysteresis, dynamic behavior                         | Static fit parameter estimation.                                          |
| `protocol_fast_smoke_test.yaml`                | Developer/operator smoke test | Fast sanity test before a full session                                    | Final calibration report.                                                 |
| `protocol_static_staircase.yaml`               | Legacy/basic baseline         | Compatibility with older docs or short static-only baseline               | Recommended handoff workflow.                                             |
| `template.yaml`                                | Authoring template            | Creating new protocol configs                                             | Direct operator run unless filled out.                                    |

## Canonical calibration sequence

Recommended full workflow:

```bash
cd Handgrip_Calibration

handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
handgrip-cal record --config conf/protocol_reference_verification.yaml
handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
handgrip-cal fit data/calibration/<fit_session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
handgrip-cal report data/calibration/<fit_session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
handgrip-cal record --config conf/protocol_holdout_verification.yaml
handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
handgrip-cal report data/calibration/<holdout_session_id> --config conf/protocol_holdout_verification.yaml
```

## CLI default policy

Recommended source behavior:

- `handgrip-cal record` default config should be:

```text
conf/protocol_static_reversible_staircase_v3.yaml
```

not:

```text
conf/protocol_static_staircase.yaml
```

Reason:

- v3 is the documented primary calibration workflow,
- v3 captures reversible up/down static holds,
- v3 better supports model-selection and hysteresis/return-path checks,
- older static-staircase docs should not silently control the default handoff behavior.

If the source default is not changed immediately, all operator docs must explicitly pass:

```bash
--config conf/protocol_static_reversible_staircase_v3.yaml
```

## Component config snapshot paths

Each protocol should snapshot relevant component configs for reproducibility.

Correct RS485 GUI path:

```yaml
session:
  copy_component_configs:
    - ../LSL_Bridge/conf/config.yaml
    - ../LSL_Viewer/conf/config.yaml
    - ../RS485_GUI/config/config.yaml
```

Deprecated/stale path:

```yaml
- ../RS485_GUI/config.yaml
```

The stale path should not appear in calibration configs or canonical docs.

## Why `protocol_static_staircase.yaml` is legacy/basic

`protocol_static_staircase.yaml` can still be useful for:

- backward compatibility,
- short static-only baseline experiments,
- comparing old and new calibration behavior,
- regression tests against older sessions.

It should not be the default recommended operator workflow because v3 carries the current intended calibration design.

## Validation checklist

```bash
# Confirm stale config snapshot path is gone.
rg "\.\./RS485_GUI/config\.yaml" Handgrip_Calibration/conf || true

# Confirm canonical config path is present.
rg "\.\./RS485_GUI/config/config\.yaml" Handgrip_Calibration/conf

# Confirm CLI record default uses v3.
rg "protocol_static_reversible_staircase_v3.yaml" Handgrip_Calibration/src/handgrip_calibration/cli.py

# Confirm legacy protocol is clearly labelled in docs.
rg "legacy|basic baseline" Handgrip_Calibration/docs/protocols.md
```
