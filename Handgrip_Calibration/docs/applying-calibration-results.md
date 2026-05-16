# Applying Calibration Results

## Summary

- Apply only values from the accepted report/fit artifact, not from screenshots or intermediate plots.
- The primary fitted relationship is `reference_force_N = f(target_raw_count)`.
- Deployment can be firmware-side, bridge-side, report-only/downstream, or analysis-only depending on the accepted model and traceability requirements.
- Always validate after applying calibration values.

## Which values to use

Use the values explicitly identified in:

```text
data/calibration/<session_id>/fit_result.json
```

and the human-readable report.

Do not copy values from:

- exploratory notebook output,
- a plot annotation,
- an old report from another session,
- firmware `current_units` from before calibration,
- a diagnostic-only model unless deliberately promoted.

## Deployment targets

| Target | Use when | Risk |
| --- | --- | --- |
| Firmware `SCALE_FACTOR` / `SCALE_OFFSET` | Accepted model is simple affine and on-device convenience output is needed. | Requires firmware rebuild/upload and bench validation. |
| `LSL_Bridge` processing config | Host-side calibrated stream is preferred while preserving firmware raw counts. | Must update bridge docs/config and validate downstream consumers. |
| Report/downstream conversion | Scientific traceability prefers raw-count preservation. | Users must apply conversion consistently during analysis. |
| Viewer display-only conversion | Only operator display needs calibrated units. | Must not be confused with saved/calibrated data. |
| Analysis config | Offline analysis needs calibrated signal. | Must document exactly which session/model produced the conversion. |

## Firmware affine conversion

If the accepted model is:

```text
force_N = a * raw_count + b
```

and firmware uses:

```text
current_units = (raw_count - SCALE_OFFSET) / SCALE_FACTOR
```

then:

```text
SCALE_FACTOR = 1 / a
SCALE_OFFSET = -b / a
```

Before applying:

- confirm `a != 0`,
- confirm firmware formula has not changed,
- confirm selected model is affine-compatible,
- preserve raw-count stream even after deployment if possible.

## Bridge-side deployment

Bridge-side deployment is preferred when:

- raw firmware output should remain untouched,
- a more complex model is needed,
- you want reproducible host-side config snapshots,
- you need to A/B test calibration before flashing firmware.

If deployed in `LSL_Bridge`, update:

- bridge processing config,
- bridge stream/channel docs,
- root stream contracts if new channel semantics are introduced,
- viewer/calibration configs if they consume new calibrated channel names.

## Validation after deployment

Run a holdout validation after applying values:

```bash
cd Handgrip_Calibration
uv run handgrip-cal record --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal report data/calibration/<holdout_session_id> --config conf/protocol_holdout_verification.yaml
```

Pass conditions:

- max absolute error is within accepted threshold,
- no systematic force-level bias,
- no unacceptable hysteresis split,
- no unacceptable dynamic lag for intended use,
- report includes session IDs and model path.

## Deployment record

Document every deployment with:

| Field | Example |
| --- | --- |
| source fit session | `2026-05-13_055327_handgrip_cal` |
| holdout session | `<holdout_session_id>` |
| selected model | `affine_wls` |
| deployment target | firmware / bridge / downstream report |
| values applied | `a`, `b`, `SCALE_FACTOR`, `SCALE_OFFSET`, or model file path |
| validation result | pass/fail + threshold |
| commit | git commit that applied values |

## Stop conditions

Do not apply or keep deployed values if:

- the model failed threshold,
- holdout validation was skipped or failed,
- the model is diagnostic-only,
- the conversion formula does not match the deployment target,
- raw-count provenance would be lost,
- the accepted report cannot be found.
