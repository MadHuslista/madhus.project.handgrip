# Calibration Recording Troubleshooting

## Summary
**Symptoms covered:** Missing target/reference CSV, failed preflight, bad session ID  


Use this guide when `handgrip-cal preflight`, `record`, `fit`, or `report` cannot find expected streams or files.

## Symptom: failed preflight

### Likely causes

| Cause                      | Check                           | Fix                                                       |
| -------------------------- | ------------------------------- | --------------------------------------------------------- |
| `LSL_Bridge` not running   | terminal/logs                   | Start bridge.                                             |
| `RS485_GUI` not running    | reference stream absent         | Start GUI first.                                          |
| Wrong stream names         | preflight output                | Align config with `HandgripTarget` / `HandgripReference`. |
| Stale duplicate LSL stream | repeated inconsistent discovery | Restart bridge/viewer/calibration.                        |
| Wrong protocol config      | command path                    | Use `conf/protocol_static_reversible_staircase_v3.yaml`.  |

Command:

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

## Symptom: missing target/reference CSV

### Likely causes

| Cause                                 | Check                   | Fix                                                                                           |
| ------------------------------------- | ----------------------- | --------------------------------------------------------------------------------------------- |
| Recording stopped before data arrived | session folder contents | Re-run after preflight passes.                                                                |
| One stream missing                    | recording logs          | Fix LSL stream discovery.                                                                     |
| Output path changed                   | config/report path      | Inspect protocol/config output section.                                                       |
| Session ID mistyped                   | folder name             | Copy exact session ID from record output.                                                     |
| File naming differs                   | component version       | Use [Handgrip_Calibration/docs/recording.md](../../Handgrip_Calibration/docs/recording.md). |

Minimum expected artifact classes:

- target samples,
- reference samples,
- events/markers,
- config snapshots,
- quality logs when enabled.

## Symptom: bad session ID

### Signs

- `fit` says session folder not found.
- `report` cannot find fit result.
- `validate-holdout` references wrong fit session.

### Fix

Use exact folder names:

```bash
ls -1 Handgrip_Calibration/data/calibration/
```

Then run from `Handgrip_Calibration/`:

```bash
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

## Symptom: config snapshot missing

Confirm protocol contains:

```yaml
session:
  copy_component_configs:
    - ../LSL_Bridge/conf/config.yaml
    - ../LSL_Viewer/conf/config.yaml
    - ../RS485_GUI/config/config.yaml
```

Do not use stale path:

```yaml
- ../RS485_GUI/config.yaml
```

## Stop conditions

Stop before fitting if:

- target data is missing,
- reference data is missing,
- events/markers are missing,
- stream names were wrong during record,
- force fixture slipped during recording,
- config snapshots did not capture component configs.

## Validation commands

```bash
rg 'protocol_static_reversible_staircase_v3.yaml' Handgrip_Calibration docs/workflows/handgrip-calibration.md
rg 'HandgripTarget|HandgripReference|HandgripCalibrationMarkers' Handgrip_Calibration docs/architecture/stream-contracts.md
rg '\.\./RS485_GUI/config/config\.yaml' Handgrip_Calibration Handgrip_Calibration/docs/configuration.md
```

**Related docs:** [docs/workflows/handgrip-calibration.md](../workflows/handgrip-calibration.md), [Handgrip_Calibration/docs/recording.md](../../Handgrip_Calibration/docs/recording.md), [Handgrip_Calibration/docs/protocols.md](../../Handgrip_Calibration/docs/protocols.md)
