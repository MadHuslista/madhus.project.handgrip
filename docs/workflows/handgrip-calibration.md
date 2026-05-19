# Handgrip Calibration Workflow

## Summary

This workflow calibrates the target handgrip against the PM58 reference chain. It requires the physical setup, firmware, and live streams to be working first.

For the full step-by-step workflow — preflight, recording, fitting, reporting, holdout validation, and applying values — see [Handgrip_Calibration/docs/workflow.md](../../Handgrip_Calibration/docs/workflow.md).

## Required upstream state

Before calibrating:

1. PM58 and handgrip setup mechanically in series, so the force applied to the setup can be shared equally by both devices. See [docs/workflows/physical-setup.md](physical-setup.md).
2. Firmware emitting D2 frames. See [Handgrip_Firmware/docs/workflow.md](../../Handgrip_Firmware/docs/workflow.md).
3. `RS485_GUI` running and reference data updating. See [RS485_GUI/docs/workflow.md](../../RS485_GUI/docs/workflow.md).
4. `LSL_Bridge` publishing `HandgripTarget` and `HandgripReference`. See [LSL_Bridge/docs/workflow.md](../../LSL_Bridge/docs/workflow.md).
5. Optional: `LSL_Viewer` showing both streams with plausible XY behavior.

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

Stop if preflight fails. Do not proceed to recording.

## Holdout validation

```bash
uv run handgrip-cal record --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
```

## Detailed documentation

- [Handgrip_Calibration/docs/workflow.md](../../Handgrip_Calibration/docs/workflow.md) — complete step-by-step workflow
- [Handgrip_Calibration/docs/recording.md](../../Handgrip_Calibration/docs/recording.md) — session structure and quality requirements
- [Handgrip_Calibration/docs/fitting-and-model-selection.md](../../Handgrip_Calibration/docs/fitting-and-model-selection.md) — model selection criteria
- [Handgrip_Calibration/docs/applying-calibration-results.md](../../Handgrip_Calibration/docs/applying-calibration-results.md) — where to apply values
- [docs/troubleshooting/calibration-recording.md](../troubleshooting/calibration-recording.md)
