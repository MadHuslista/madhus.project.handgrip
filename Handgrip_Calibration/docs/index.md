# Handgrip Calibration Documentation

## Summary

- `Handgrip_Calibration` records protocol-guided calibration sessions, fits target raw counts to reference force, generates reports, and validates selected models.
- The canonical primary protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- Calibration should fit `reference_force_N = f(target_raw_count)`; firmware `current_units` is a diagnostic/deployment convenience channel, not the primary fitting input.
- Start with `quickstart.md` for operator use, then read `protocols.md`, `recording.md`, `fitting-and-model-selection.md`, and `reports-and-outputs.md` for deeper use.
- Developers should use `architecture.md` and `development.md` before adding protocols, models, or report sections.

## Audience

| Reader | Use this page to... |
| --- | --- |
| Operator | Find the minimal safe workflow for calibration. |
| Principal investigator | Understand protocol choices, outputs, model interpretation, and deployment criteria. |
| Student maintainer | Find config, data, and model docs before editing YAML or code. |
| Developer | Find architecture and extension guidance. |

## Required upstream state

Before running calibration, these upstream checks should pass:

1. `docs/workflows/physical-setup.md` confirms the PM58 and target are in the same force path.
2. `docs/workflows/firmware-setup.md` confirms target firmware emits D2 frames.
3. `docs/workflows/reference-only-quickstart.md` confirms RS485 GUI receives reference force.
4. `docs/workflows/full-live-viewer-quickstart.md` confirms `HandgripTarget` and `HandgripReference` are live.
5. `docs/architecture/stream-contracts.md` confirms target/reference stream semantics.

## Documentation map

| Document | Purpose |
| --- | --- |
| [`quickstart.md`](quickstart.md) | Operator workflow from preflight to report. |
| [`protocols.md`](protocols.md) | Protocol suite, canonical v3 primary protocol, holdout validation, and legacy labels. |
| [`configuration.md`](configuration.md) | Full calibration config/protocol YAML reference and safe override guidance. |
| [`recording.md`](recording.md) | LSL inputs, captured files, session IDs, events, quality telemetry, and provenance. |
| [`fitting-and-model-selection.md`](fitting-and-model-selection.md) | Model alternatives, metrics, likelihoods, residuals, candidate ranking, and selection policy. |
| [`reports-and-outputs.md`](reports-and-outputs.md) | Report files, plots, tables, JSON artifacts, and interpretation map. |
| [`applying-calibration-results.md`](applying-calibration-results.md) | Which fitted values to use, where to apply them, and how to validate deployment. |
| [`architecture.md`](architecture.md) | CLI to modules: preflight, record, segment, fit, report, validate-holdout. |
| [`development.md`](development.md) | Add protocol/model/report sections safely. |

## Related root docs

| Root doc | Why it matters |
| --- | --- |
| [`../../docs/workflows/handgrip-calibration.md`](../../docs/workflows/handgrip-calibration.md) | Canonical operator-facing calibration workflow. |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Target/reference stream and calibration data contracts. |
| [`../../docs/architecture/data-and-output-lifecycle.md`](../../docs/architecture/data-and-output-lifecycle.md) | Generated data/session artifact lifecycle. |
| [`../../docs/architecture/timestamping-and-synchronization.md`](../../docs/architecture/timestamping-and-synchronization.md) | LSL timestamp, interpolation, drift, and gap assumptions. |
| [`../../docs/hardware/force-fixture.md`](../../docs/hardware/force-fixture.md) | PM58 + handgrip mechanical force-path validation. |
| [`../../docs/troubleshooting/calibration-recording.md`](../../docs/troubleshooting/calibration-recording.md) | Symptom-first recording/fitting failures. |

## Minimal command path

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal report data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

## Validation checklist

- [ ] `README.md` links to this docs index.
- [ ] `protocols.md` labels v3 as primary and `protocol_static_staircase.yaml` as legacy/basic.
- [ ] `configuration.md` documents `../RS485_GUI/config/config.yaml` as the correct snapshot path.
- [ ] `recording.md` documents `HandgripTarget`, `HandgripReference`, events, and session IDs.
- [ ] `fitting-and-model-selection.md` states `reference_force_N = f(target_raw_count)`.
- [ ] `reports-and-outputs.md` explains fit/report artifacts and plots.
- [ ] `applying-calibration-results.md` explains firmware/bridge/report deployment targets and validation.
