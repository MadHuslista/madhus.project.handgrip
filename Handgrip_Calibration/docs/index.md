# Handgrip Calibration Documentation

## Summary

- `Handgrip_Calibration` records protocol-guided sessions, fits target raw counts to reference force, generates reports, and validates selected models.
- The canonical primary protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- Calibration fits `reference_force_N = f(target_raw_count)`. Firmware `current_units` is a diagnostic convenience channel, not the primary fitting input.

## Component contract

| Contract                  | Value                                                                    |
| ------------------------- | ------------------------------------------------------------------------ |
| Primary command           | `uv run handgrip-cal`                                                    |
| Main config               | `Handgrip_Calibration/conf/protocol_static_reversible_staircase_v3.yaml` |
| Session output root       | `Handgrip_Calibration/data/calibration/<session_id>/`                    |
| Required upstream streams | `HandgripTarget`, `HandgripReference`                                    |

## Required upstream state

Before running calibration:

1. [docs/workflows/physical-setup.md](../../docs/workflows/physical-setup.md) — PM58 and target in the same force path
2. [Handgrip_Firmware/docs/workflow.md](../../Handgrip_Firmware/docs/workflow.md) — firmware emits D2 frames
3. [docs/workflows/full-live-viewer-quickstart.md](../../docs/workflows/full-live-viewer-quickstart.md) — both streams live

## Reading guide

| I want to…                                                             | Read                                                                                         |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Run calibration end to end (preflight → record → fit → report → holdout → apply to firmware/bridge) | [Handgrip_Calibration/docs/workflow.md](workflow.md)                              |
| Choose a protocol (canonical v3, holdout, legacy labels)               | [Handgrip_Calibration/docs/protocols.md](protocols.md)                                       |
| Edit protocol YAML safely                                              | [Handgrip_Calibration/docs/configuration.md](configuration.md)                               |
| Understand session output files (events, quality, provenance)          | [Handgrip_Calibration/docs/recording.md](recording.md)                                       |
| Interpret model selection (metrics, residuals, ranking)                | [Handgrip_Calibration/docs/fitting-and-model-selection.md](fitting-and-model-selection.md)   |
| Read reports, plots, and JSON artifacts                                | [Handgrip_Calibration/docs/reports-and-outputs.md](reports-and-outputs.md)                   |
| Understand CLI-to-module internals                                     | [Handgrip_Calibration/docs/architecture.md](architecture.md)                                 |
| Add protocols, models, or report sections                              | [Handgrip_Calibration/docs/development.md](development.md)                                   |

## Related docs

- [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md) — target/reference stream contracts
- [docs/hardware/dual-device-calibration-configuration.md](../../docs/hardware/dual-device-calibration-configuration.md) — recommended acquisition-board + target settings for calibration
- [docs/troubleshooting/calibration-recording.md](../../docs/troubleshooting/calibration-recording.md)

## Minimal command path

Run from the repo root or from `Handgrip_Calibration/` — `conf/...yaml` and
`data/calibration/<session_id>` resolve the same either way, and recorded
sessions always land under `Handgrip_Calibration/data/calibration/`.

```bash
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record    --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal fit       data/calibration/<session_id> \
  --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal report    data/calibration/<session_id>
```
