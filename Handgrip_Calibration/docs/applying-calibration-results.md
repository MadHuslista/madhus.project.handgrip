# Applying Calibration Results

## Summary

- Deployment can be firmware-side, bridge-side, report-only/downstream, or analysis-only depending on the accepted model and traceability requirements.

## Which values to use

Use the values explicitly identified in:

```text
data/calibration/<session_id>/fit_result.json
```

and the human-readable report.


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

