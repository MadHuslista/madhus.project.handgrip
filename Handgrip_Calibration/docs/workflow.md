# Handgrip Calibration Workflow

## Summary

This document covers the complete calibration workflow: preflight, recording, model fitting, report generation, and holdout validation.

The canonical primary protocol is `conf/protocol_static_reversible_staircase_v3.yaml`. Run this workflow only after physical setup, firmware setup, and live stream validation are complete.

## Prerequisites

- PM58 and handgrip are mechanically in the same force path. See [docs/hardware/force-fixture.md](../../docs/hardware/force-fixture.md).
- Firmware emits `D2` frames. See [Handgrip_Firmware/docs/workflow.md](../../Handgrip_Firmware/docs/workflow.md).
- `RS485_GUI` is running and reference data updates. See [RS485_GUI/docs/workflow.md](../../RS485_GUI/docs/workflow.md).
- `LSL_Bridge` publishes `HandgripTarget` and `HandgripReference`. See [LSL_Bridge/docs/workflow.md](../../LSL_Bridge/docs/workflow.md).

## 1 — Preflight

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Preflight verifies: target stream discovered, reference stream discovered, required channels present, protocol YAML valid, output root writable, config snapshot paths resolvable.

Stop if preflight fails. Do not proceed to recording.

## 2 — Record calibration session

```bash
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
```

Follow operator prompts exactly for each baseline, preload, and hold step. Do not skip steps.

Expected result: session folder created under `data/calibration/<session_id>/` containing target/reference samples, protocol events, and a config snapshot.

Session artifacts:

| Artifact          | Purpose                       |
| ----------------- | ----------------------------- |
| Target samples    | Target stream raw counts      |
| Reference samples | Reference force ground truth  |
| Events / markers  | Protocol stage boundaries     |
| Config snapshot   | Reproducibility record        |
| Quality log       | Live quality gates if enabled |

See [Handgrip_Calibration/docs/recording.md](recording.md) for session structure and quality requirements.

## 3 — Fit model candidates

```bash
uv run handgrip-cal fit data/calibration/<session_id> \
  --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result: accepted holds reduced to a fitting dataset, candidate models evaluated, selected model and diagnostics written to the session folder.

See [Handgrip_Calibration/docs/fitting-and-model-selection.md](fitting-and-model-selection.md) for model comparison and selection criteria.

## 4 — Generate report

```bash
uv run handgrip-cal report data/calibration/<session_id> \
  --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result: report files created in the session folder, including model comparison, recommended model, and residual/metric plots.

To interpret the report, answer:

| Question                      | What to inspect                                    |
| ----------------------------- | -------------------------------------------------- |
| Is a linear model sufficient? | Residuals, RMSE/MAE, bias by force level           |
| Is low-force behavior poor?   | Low-force residuals and candidate model comparison |
| Is hysteresis visible?        | Up/down hold comparison if available               |
| Is the validation acceptable? | Holdout metrics, out-of-sample residuals           |

Do not select a more complex model solely because it fits marginally better. Prefer the simplest model that passes validation and residual checks.

See [Handgrip_Calibration/docs/reports-and-outputs.md](reports-and-outputs.md).

## 5 — Holdout validation

Record a separate validation session using the holdout protocol:

```bash
uv run handgrip-cal record --config conf/protocol_holdout_verification.yaml
```

Then validate the accepted model against it:

```bash
uv run handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal report data/calibration/<holdout_session_id> \
  --config conf/protocol_holdout_verification.yaml
```

Expected result: out-of-sample errors within accepted thresholds, no systematic bias across the operating range.

## 6 — Apply calibration values

Use only the model parameters from the accepted fit result/report to map:

```text
target raw_count → reference force (N)
```

Depending on the accepted model, values may be applied in:

| Destination                              | Use case                                                                      |
| ---------------------------------------- | ----------------------------------------------------------------------------- |
| Firmware `SCALE_FACTOR` / `SCALE_OFFSET` | Simple firmware-side linear output                                            |
| `LSL_Bridge` processing config           | Host-side calibration and filtering                                           |
| Report only                              | When raw-count preservation is preferred and conversion is applied downstream |

Preserve raw counts even when calibrated values are also computed.

See [Handgrip_Calibration/docs/applying-calibration-results.md](applying-calibration-results.md).

## Canonical command sequence

```bash
uv sync
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record    --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal fit       data/calibration/<session_id> \
  --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal report    data/calibration/<session_id> \
  --config conf/protocol_static_reversible_staircase_v3.yaml
```

## Stop conditions

Stop and troubleshoot if:

- preflight cannot find both streams,
- captured session lacks target or reference data,
- reference data is frozen, noisy, or saturated,
- fixture slips or force path is ambiguous,
- model comparison shows unacceptable residuals,
- holdout validation fails.

## Troubleshooting links

- [Handgrip_Calibration/docs/recording.md](recording.md)
- [Handgrip_Calibration/docs/protocols.md](protocols.md)
- [docs/troubleshooting/calibration-recording.md](../../docs/troubleshooting/calibration-recording.md)
- [docs/architecture/timestamping-and-synchronization.md](../../docs/architecture/timestamping-and-synchronization.md)
