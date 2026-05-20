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

## Documentation map

| Document                                                           | Purpose                                                                   |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| [workflow.md](workflow.md)                                         | Preflight → record → fit → report → holdout validation                    |
| [protocols.md](protocols.md)                                       | Protocol suite, canonical v3 protocol, holdout validation, legacy labels  |
| [configuration.md](configuration.md)                               | Full protocol YAML reference and safe override guidance                   |
| [recording.md](recording.md)                                       | LSL inputs, session files, events, quality telemetry, provenance          |
| [fitting-and-model-selection.md](fitting-and-model-selection.md)   | Model alternatives, metrics, residuals, candidate ranking                 |
| [reports-and-outputs.md](reports-and-outputs.md)                   | Report files, plots, tables, JSON artifacts                               |
| [applying-calibration-results.md](applying-calibration-results.md) | Which values to use, where to apply them, deployment validation           |
| [architecture.md](architecture.md)                                 | CLI to modules: preflight, record, segment, fit, report, validate-holdout |
| [development.md](development.md)                                   | Add protocols, models, or report sections safely                          |

## Reading guide

- To run calibration: [Handgrip_Calibration/docs/workflow.md](workflow.md)
- To understand protocol options: [Handgrip_Calibration/docs/protocols.md](protocols.md)
- To interpret model selection: [Handgrip_Calibration/docs/fitting-and-model-selection.md](fitting-and-model-selection.md)
- To understand session output files: [Handgrip_Calibration/docs/recording.md](recording.md)
- To apply results to firmware or bridge: [Handgrip_Calibration/docs/applying-calibration-results.md](applying-calibration-results.md)
- To extend or maintain the component: [Handgrip_Calibration/docs/development.md](development.md)

## Related docs

- [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md) — target/reference stream contracts
- [docs/troubleshooting/calibration-recording.md](../../docs/troubleshooting/calibration-recording.md)

## Minimal command path

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record    --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal fit       data/calibration/<session_id> \
  --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal report    data/calibration/<session_id> \
  --config conf/protocol_static_reversible_staircase_v3.yaml
```
