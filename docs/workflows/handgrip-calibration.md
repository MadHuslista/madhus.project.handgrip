# Handgrip Calibration Workflow

**Status:** Canonical operator workflow  
**Audience:** Calibration operators, maintainers, and principal investigator  
**Scope:** From validated live streams to calibration recording, fitting, report generation, applying values, and validation  
**Related docs:** [`Handgrip_Calibration/docs/protocols.md`](../../Handgrip_Calibration/docs/protocols.md), [`docs/hardware/force-fixture.md`](../hardware/force-fixture.md), [`docs/architecture/stream-contracts.md`](../architecture/stream-contracts.md)

## Summary

This workflow calibrates the target handgrip against the PM58/reference acquisition chain. The canonical primary protocol is:

```text
Handgrip_Calibration/conf/protocol_static_reversible_staircase_v3.yaml
```

The calibration should be performed only after the physical setup, firmware setup, reference-only quickstart, and full live viewer quickstart have passed.

## Prerequisites

- PM58 and handgrip are mechanically in the same force path.
- Screw press / controlled force fixture is stable.
- `RS485_GUI` is running and reference data updates.
- `LSL_Bridge` publishes `HandgripTarget` and `HandgripReference`.
- Optional `LSL_Viewer` shows both streams.
- Phase 4 fixes are applied: D2 docs, v3 protocol default/docs, and RS485 config snapshot path.

## 1 — Physical setup with force fixture

Use these image references:

- `docs/hardware/assets/pm58_n_handgrip_setup.jpg`
- `docs/hardware/assets/acq_board_n_pm58_n_handgrip_setup.jpg`
- `docs/hardware/assets/force_application_setup.jpg`

Validation:

- applying force changes PM58/reference display,
- applying force changes target raw counts,
- no obvious slip, binding, off-axis loading, or preload drift occurs.

## 2 — Preflight

From `Handgrip_Calibration/`:

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- target stream discovered,
- reference stream discovered,
- required channels exist,
- protocol/config passes validation.

Stop if preflight fails. Do not proceed to recording.

## 3 — Recording

```bash
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- operator prompts guide protocol steps,
- session folder is created under `data/calibration/<session_id>/`,
- target/reference samples and events are saved.

## 4 — Where captured data appears

Expected session root:

```text
Handgrip_Calibration/data/calibration/<session_id>/
```

Expected artifact classes:

| Artifact       | Purpose                                        |
| -------------- | ---------------------------------------------- |
| target data    | Target stream samples.                         |
| reference data | Reference stream samples.                      |
| events/markers | Protocol stage boundaries and operator events. |
| copied configs | Reproducibility snapshot.                      |
| quality logs   | Live/preflight quality if enabled.             |

## 5 — Fitting

```bash
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- calibration dataset is constructed,
- candidate models are evaluated,
- selected fit result is written,
- residuals/metrics are available for reporting.

## 6 — Report generation

```bash
uv run handgrip-cal report data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- Markdown and/or HTML report generated,
- model comparison included,
- recommended calibration model identified,
- plots/tables available.

## 7 — How to interpret model comparison

Use the report to answer:

| Question                         | What to inspect                                     |
| -------------------------------- | --------------------------------------------------- |
| Is a simple linear model enough? | Residuals, RMSE/MAE, bias by force level.           |
| Is low-force behavior poor?      | Low-force residuals and candidate model comparison. |
| Is hysteresis visible?           | Up/down hold comparison if available.               |
| Is validation acceptable?        | Holdout metrics, out-of-sample residuals.           |
| Is the reference chain credible? | Preflight/reference verification and board profile. |

Do not select a more complex model only because it looks marginally better on fit data. Prefer the simplest model that passes validation and residual checks.

## 8 — Which fitted values to use

Use only the model parameters from the accepted fit result/report. The key output should define how to map:

```text
target raw_count → reference force
```

Do not manually copy values from intermediate plots or exploratory outputs.

## 9 — Where to apply calibration values

Depending on the accepted model and current software design, calibration values may be applied in:

| Destination                              | Use case                                                                       |
| ---------------------------------------- | ------------------------------------------------------------------------------ |
| firmware `SCALE_FACTOR` / `SCALE_OFFSET` | Simple firmware-side linear convenience output.                                |
| `LSL_Bridge` processing config           | Host-side processing/filtering/calibration output.                             |
| analysis/calibration report only         | When raw-count preservation is preferred and conversion is applied downstream. |

For scientific traceability, preserve raw counts even when calibrated engineering values are also computed.

## 10 — Validation after applying calibration

Run a holdout validation session after applying the accepted model:

```bash
uv run handgrip-cal record --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal report data/calibration/<holdout_session_id> --config conf/protocol_holdout_verification.yaml
```

Expected result:

- out-of-sample errors are within accepted thresholds,
- no systematic bias appears across the operating range,
- result is documented with session IDs.

## Canonical command set

```bash
uv sync
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal report data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

## Stop conditions

Stop and troubleshoot if:

- preflight cannot find both streams,
- captured session lacks target or reference data,
- reference data is frozen/noisy/saturated,
- fixture slips or force path is ambiguous,
- model comparison shows unacceptable residuals,
- holdout validation fails.

## Troubleshooting links

- [`Handgrip_Calibration/docs/protocols.md`](../../Handgrip_Calibration/docs/protocols.md)
- [`docs/troubleshooting/calibration-recording.md`](../troubleshooting/calibration-recording.md)
- [`docs/architecture/data-and-output-lifecycle.md`](../architecture/data-and-output-lifecycle.md)
- [`docs/architecture/timestamping-and-synchronization.md`](../architecture/timestamping-and-synchronization.md)
